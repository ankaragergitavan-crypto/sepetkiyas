"""Barkod / görüntüden gelen kod → ürün adı önerisi (Open Food Facts)."""

from __future__ import annotations

import re
from typing import Any

import httpx

OFF_UA = "SepetKiyas/1.4 (https://sepetkiyas.onrender.com; barcode lookup)"


def _clean_name(name: str) -> str:
    name = re.sub(r"\s+", " ", (name or "").strip())
    return name[:80]


async def lookup_barcode(code: str) -> dict[str, Any]:
    raw = re.sub(r"\D", "", code or "")
    if len(raw) < 8:
        return {
            "found": False,
            "code": code,
            "note": "Geçerli barkod değil.",
        }

    url = f"https://world.openfoodfacts.org/api/v2/product/{raw}.json"
    try:
        async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": OFF_UA}) as client:
            resp = await client.get(url)
            if resp.status_code >= 500:
                return {
                    "found": False,
                    "code": raw,
                    "available": False,
                    "note": "Open Food Facts şu an yanıt vermiyor.",
                }
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {
            "found": False,
            "code": raw,
            "available": False,
            "note": f"Barkod servisi erişilemedi: {exc}",
        }

    if data.get("status") != 1 or not data.get("product"):
        return {
            "found": False,
            "code": raw,
            "available": True,
            "query": raw,
            "note": "Barkod okundu ama açık veritabanında ürün adı yok; kod ile aranacak.",
        }

    p = data["product"]
    name = (
        p.get("product_name_tr")
        or p.get("product_name")
        or p.get("generic_name_tr")
        or p.get("generic_name")
        or ""
    )
    brand = (p.get("brands") or "").split(",")[0].strip()
    quantity = p.get("quantity") or ""
    parts = [brand, _clean_name(name)]
    if quantity and quantity.lower() not in _clean_name(name).lower():
        parts.append(quantity)
    query = " ".join(x for x in parts if x).strip() or raw

    return {
        "found": True,
        "code": raw,
        "available": True,
        "query": query,
        "productName": _clean_name(name) or None,
        "brand": brand or None,
        "quantity": quantity or None,
        "imageUrl": p.get("image_front_small_url") or p.get("image_url"),
        "url": f"https://world.openfoodfacts.org/product/{raw}",
        "note": "Barkod Open Food Facts kaydıyla eşleşti; canlı market araması bu adla yapılacak.",
    }
