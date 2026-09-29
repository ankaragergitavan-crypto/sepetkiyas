"""Ürün içeriği: market API alanları + varsa Open Food Facts (uydurma yok)."""

from __future__ import annotations

import re
from typing import Any

import httpx

from .relevance import fold_tr, relevance_score

OFF_SEARCH = "https://world.openfoodfacts.org/cgi/search.pl"
OFF_UA = "SepetKiyas/1.3 (https://sepetkiyas.onrender.com; product-content lookup)"


def market_source_content(offer: dict[str, Any]) -> dict[str, Any]:
    """marketfiyati / Getir cevabında gerçekten gelen alanlar."""
    cats = offer.get("categories") or []
    if isinstance(cats, str):
        cats = [cats]
    return {
        "title": offer.get("title"),
        "brand": offer.get("brand"),
        "volume": offer.get("volume"),
        "categories": cats,
        "mainCategory": offer.get("mainCategory"),
        "menuCategory": offer.get("menuCategory"),
        "promotionText": offer.get("promotionText"),
        "imageUrl": offer.get("imageUrl"),
        "marketLabel": offer.get("marketLabel"),
        "depotName": offer.get("depotName"),
        "price": offer.get("price"),
        "unitPriceEstimate": offer.get("unitPriceEstimate"),
        "unitPriceUnit": offer.get("unitPriceUnit"),
        "healthScore": offer.get("healthScore"),
        "economyScore": offer.get("economyScore"),
        "labelEvidence": offer.get("labelEvidence") or [],
        "labelNotes": offer.get("labelNotes") or [],
        "analysisNote": offer.get("analysisNote"),
        "source": offer.get("source"),
        "updatedAt": offer.get("updatedAt"),
        "ingredientsAvailableFromMarketApi": False,
        "note": (
            "Market fiyat API’si içindekiler / besin tablosu göndermiyor. "
            "Aşağıda yalnızca canlı kaynaktan gelen alanlar + etiket metni analizi var."
        ),
    }


def _token_overlap(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z0-9]{3,}", fold_tr(a)))
    tb = set(re.findall(r"[a-z0-9]{3,}", fold_tr(b)))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


async def lookup_open_food_facts(title: str, brand: str | None = None) -> dict[str, Any]:
    from .security import STRICT_PRIVACY

    if STRICT_PRIVACY:
        return {
            "found": False,
            "available": False,
            "privacy": True,
            "source": "disabled",
            "note": "Gizlilik modu: dış gıda veritabanı kapalı. Yalnızca market etiket alanları.",
        }
    """Açık veriden içindekiler; eşleşme zayıfsa boş döner (uydurma yok)."""
    q = " ".join(x for x in [brand or "", title] if x).strip()
    if len(q) < 3:
        return {
            "found": False,
            "source": "openfoodfacts",
            "note": "Arama metni yetersiz.",
        }

    params = {
        "search_terms": q,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": 8,
        "lc": "tr",
        "cc": "tr",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": OFF_UA}) as client:
            resp = await client.get(OFF_SEARCH, params=params)
            if resp.status_code >= 500:
                return {
                    "found": False,
                    "source": "openfoodfacts",
                    "available": False,
                    "note": "Open Food Facts şu an yanıt vermiyor; içindekiler alınamadı.",
                }
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {
            "found": False,
            "source": "openfoodfacts",
            "available": False,
            "note": f"Open Food Facts erişilemedi: {exc}",
        }

    products = data.get("products") or []
    best = None
    best_score = 0.0
    for p in products:
        pname = p.get("product_name_tr") or p.get("product_name") or ""
        pbrand = p.get("brands") or ""
        if not pname:
            continue
        score = _token_overlap(title, pname)
        if brand:
            score += 0.25 * _token_overlap(brand, pbrand)
        # relevance soft check
        score += min(0.2, relevance_score(pname, title) / 50.0)
        if score > best_score:
            best_score = score
            best = p

    if not best or best_score < 0.28:
        return {
            "found": False,
            "source": "openfoodfacts",
            "available": True,
            "note": (
                "Açık gıda veritabanında güvenilir eşleşme yok; "
                "içindekiler uydurulmadı."
            ),
            "matchScore": round(best_score, 3),
        }

    ingredients = (
        best.get("ingredients_text_tr")
        or best.get("ingredients_text")
        or best.get("ingredients_text_en")
        or ""
    ).strip()
    allergens = best.get("allergens_from_ingredients") or best.get("allergens") or ""
    nutriscore = best.get("nutriscore_grade")
    nova = best.get("nova_group")
    quantity = best.get("quantity")
    code = best.get("code")

    return {
        "found": bool(ingredients) or bool(nutriscore) or bool(nova),
        "source": "openfoodfacts",
        "available": True,
        "matchScore": round(best_score, 3),
        "matchedName": best.get("product_name_tr") or best.get("product_name"),
        "matchedBrand": best.get("brands"),
        "barcode": code,
        "quantity": quantity,
        "ingredientsText": ingredients or None,
        "allergens": allergens or None,
        "nutriscore": nutriscore,
        "novaGroup": nova,
        "url": f"https://world.openfoodfacts.org/product/{code}" if code else None,
        "note": (
            "İçindekiler Open Food Facts açık verisinden; "
            "ambalajla birebir aynı olmayabilir. Eşleşme skoru gösterilir."
            if ingredients
            else "Eşleşme bulundu ama içindekiler metni kayıtlı değil."
        ),
    }


async def build_product_content(offer: dict[str, Any]) -> dict[str, Any]:
    market = market_source_content(offer)
    off = await lookup_open_food_facts(offer.get("title") or "", offer.get("brand"))
    return {
        "market": market,
        "openFoodFacts": off,
        "hasIngredients": bool((off or {}).get("ingredientsText")),
    }
