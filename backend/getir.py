from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.request
from typing import Any

import httpx

from .markets import MARKET_BY_ID
from .relevance import is_relevant, relevance_score
from .volume import normalize_volume_label

LOCALS_SEARCH = "https://locals-web-api-gateway.artisan.getirapi.com/v2/search"
REEF_SEARCH = "https://api.reefapi.com/getir/v1/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Language": "tr",
}


def _extract_volume_from_title(title: str) -> str | None:
    m = re.search(
        r"(\d+[.,]?\d*)\s*(kg|g|gr|ml|lt|l|cl)\b|\((\d+[.,]?\d*\s*(?:kg|g|gr|ml|lt|l))\)",
        title,
        re.I,
    )
    if not m:
        return None
    raw = m.group(0).strip("()")
    return normalize_volume_label(raw)


def _locals_search_sync(keywords: str, latitude: float, longitude: float) -> dict[str, Any]:
    payload = {
        "enableBestPriceSorting": True,
        "listingSize": 80,
        "shopSize": 40,
        "searchText": keywords,
        "location": {"lat": latitude, "lon": longitude},
    }
    req = urllib.request.Request(
        LOCALS_SEARCH,
        data=json.dumps(payload).encode("utf-8"),
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def search_getir_carsi(
    keywords: str,
    latitude: float,
    longitude: float,
    limit: int = 40,
) -> dict[str, Any]:
    """
    Getir Çarşı (Locals) canlı arama — konumdaki Getir ağı marketleri.
    Getir Büyük depo kataloğu giriş/token ister; bu yöntem girişsiz çalışır.
    """
    meta = MARKET_BY_ID["getir_buyuk"]
    try:
        data = await asyncio.to_thread(_locals_search_sync, keywords, latitude, longitude)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:200]
        raise RuntimeError(f"Getir Çarşı HTTP {exc.code}: {detail}") from exc

    offers: list[dict[str, Any]] = []
    shops = ((data.get("data") or {}).get("shops")) or []
    for shop in shops:
        shop_name = shop.get("name") or "Getir Çarşı"
        for product in shop.get("searchedProducts") or []:
            title = product.get("name") or product.get("shortName") or ""
            if not title:
                continue
            if not is_relevant(title, keywords, min_score=4):
                continue
            price = product.get("price")
            if price is None:
                continue
            try:
                price_f = float(price)
            except (TypeError, ValueError):
                continue
            struck = product.get("struckPrice")
            old = float(struck) if struck not in (None, 0, "0") else None
            ratio = None
            if old and old > price_f:
                ratio = round((1 - price_f / old) * 100, 1)
            image = None
            for key in ("imageURL", "squareImageURL", "wideImageURL"):
                if product.get(key):
                    image = product[key]
                    break
            if not image:
                imgs = product.get("images") or []
                if imgs and isinstance(imgs[0], dict):
                    image = imgs[0].get("url") or imgs[0].get("imageURL")
                elif imgs and isinstance(imgs[0], str):
                    image = imgs[0]

            volume = _extract_volume_from_title(title)
            offers.append(
                {
                    "id": f"getir:{product.get('id') or product.get('productId')}:{shop.get('id')}",
                    "productId": str(product.get("productId") or product.get("id")),
                    "title": title,
                    "brand": product.get("brand") if isinstance(product.get("brand"), str) else None,
                    "imageUrl": image,
                    "volume": volume,
                    "marketId": meta.id,
                    "marketLabel": "Getir Çarşı",
                    "marketColor": meta.color,
                    "price": price_f,
                    "oldPrice": old,
                    "unitPrice": None,
                    "depotName": shop_name,
                    "depotId": shop.get("id"),
                    "discount": bool(ratio),
                    "discountRatio": ratio,
                    "promotionText": "Getir Çarşı",
                    "updatedAt": None,
                    "source": "getir_carsi",
                    "importantDeal": bool(ratio and ratio >= 15),
                    "getirChannel": "carsi",
                    "relevance": relevance_score(title, keywords),
                }
            )

    offers.sort(key=lambda o: (-o.get("relevance", 0), o["price"], o["title"]))
    offers = offers[:limit]
    if offers:
        note = (
            "Getir Büyük depo API’si giriş ister. "
            "Bunun yerine Getir Çarşı üzerinden konumundaki Getir ağı fiyatları çekildi."
        )
    elif shops:
        note = (
            "Getir Çarşı bu konumda açık ama aranan ürüne canlı eşleşme yok "
            "(sahte fiyat eklenmedi)."
        )
    else:
        note = (
            "Getir Çarşı bu konumda şu an canlı ürün döndürmedi "
            "(bölge/kapasite). Sahte fiyat eklenmedi; diğer marketler canlı."
        )
    return {
        "available": bool(offers),
        "channel": "getir_carsi",
        "channelLabel": "Getir Çarşı (konumlu yerel marketler)",
        "note": note,
        "offerCount": len(offers),
        "offers": offers,
        "shopCount": len(shops),
    }


async def search_getir_buyuk_reef(
    keywords: str,
    api_key: str,
    limit: int = 30,
) -> dict[str, Any]:
    """Opsiyonel: ReefAPI anahtarı varsa gerçek Getir Büyük kataloğu."""
    meta = MARKET_BY_ID["getir_buyuk"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            REEF_SEARCH,
            headers={"x-api-key": api_key, "content-type": "application/json"},
            json={"query": keywords, "service": "buyuk", "page_size": limit},
        )
        resp.raise_for_status()
        payload = resp.json()

    rows = payload.get("data") or payload.get("products") or []
    if isinstance(rows, dict):
        rows = rows.get("products") or rows.get("items") or []

    offers: list[dict[str, Any]] = []
    for row in rows:
        title = row.get("title") or row.get("name") or ""
        price = row.get("price") or row.get("shelf_price")
        if not title or price is None:
            continue
        offers.append(
            {
                "id": f"getirbuyuk:{row.get('id') or title}",
                "productId": str(row.get("id") or ""),
                "title": title,
                "brand": row.get("brand"),
                "imageUrl": row.get("image") or row.get("image_url"),
                "volume": normalize_volume_label(row.get("pack_size") or row.get("unit")),
                "marketId": meta.id,
                "marketLabel": "Getir Büyük",
                "marketColor": meta.color,
                "price": float(price),
                "oldPrice": row.get("struck_price") or row.get("original_price"),
                "unitPrice": row.get("unit_price"),
                "depotName": "Getir Büyük",
                "depotId": None,
                "discount": bool(row.get("discount_percent")),
                "discountRatio": row.get("discount_percent"),
                "promotionText": "Getir Büyük",
                "updatedAt": None,
                "source": "reefapi_getir_buyuk",
                "importantDeal": bool((row.get("discount_percent") or 0) >= 15),
                "getirChannel": "buyuk",
            }
        )

    offers.sort(key=lambda o: o["price"])
    return {
        "available": bool(offers),
        "channel": "getir_buyuk",
        "channelLabel": "Getir Büyük",
        "note": "ReefAPI ile Getir Büyük kataloğu",
        "offerCount": len(offers),
        "offers": offers,
    }


async def search_getir(
    keywords: str,
    latitude: float,
    longitude: float,
    reef_api_key: str | None = None,
) -> dict[str, Any]:
    if reef_api_key:
        try:
            reef = await search_getir_buyuk_reef(keywords, reef_api_key)
            if reef.get("available"):
                return reef
        except Exception:
            pass
    return await search_getir_carsi(keywords, latitude, longitude)
