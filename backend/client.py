from __future__ import annotations

import asyncio
from typing import Any

import httpx

from .markets import (
    API_NAME_TO_ID,
    DEFAULT_DISTANCE_KM,
    DEFAULT_LAT,
    DEFAULT_LON,
    MARKET_BY_ID,
    MARKETS,
)

MARKETFIYATI_BASE = "https://api.marketfiyati.org.tr"
BROWSER_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://marketfiyati.org.tr",
    "Referer": "https://marketfiyati.org.tr/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
}


def _normalize_market(api_name: str | None) -> str | None:
    if not api_name:
        return None
    key = api_name.strip().lower().replace(" ", "_")
    return API_NAME_TO_ID.get(key)


def _flatten_offers(product: dict[str, Any], target_ids: set[str]) -> list[dict[str, Any]]:
    offers: list[dict[str, Any]] = []
    for depot in product.get("productDepotInfoList") or []:
        market_id = _normalize_market(depot.get("marketAdi"))
        if not market_id or market_id not in target_ids:
            continue
        price = depot.get("price")
        if price is None:
            continue
        try:
            price_f = float(price)
        except (TypeError, ValueError):
            continue
        meta = MARKET_BY_ID[market_id]
        offers.append(
            {
                "id": f"{product.get('id')}:{depot.get('depotId')}",
                "productId": product.get("id"),
                "title": product.get("title") or "Ürün",
                "brand": product.get("brand"),
                "imageUrl": product.get("imageUrl"),
                "volume": product.get("refinedVolumeOrWeight"),
                "marketId": market_id,
                "marketLabel": meta.label,
                "marketColor": meta.color,
                "price": price_f,
                "unitPrice": depot.get("unitPrice"),
                "unitPriceValue": depot.get("unitPriceValue"),
                "depotName": depot.get("depotName"),
                "depotId": depot.get("depotId"),
                "discount": bool(depot.get("discount")),
                "discountRatio": depot.get("discountRatio"),
                "percentage": depot.get("percentage"),
                "promotionText": depot.get("promotionText"),
                "updatedAt": depot.get("indexTime"),
                "source": "marketfiyati",
            }
        )
    return offers


async def _nearest_depot_ids(
    client: httpx.AsyncClient,
    latitude: float,
    longitude: float,
    distance: int,
) -> list[str]:
    try:
        response = await client.post(
            "/api/v2/nearest",
            json={"latitude": latitude, "longitude": longitude, "distance": distance},
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            return [d["id"] for d in data if isinstance(d, dict) and d.get("id")]
    except Exception:
        return []
    return []


async def search_marketfiyati(
    keywords: str,
    latitude: float = DEFAULT_LAT,
    longitude: float = DEFAULT_LON,
    distance: int = DEFAULT_DISTANCE_KM,
    size: int = 48,
    market_ids: list[str] | None = None,
) -> dict[str, Any]:
    target = set(market_ids or [m.id for m in MARKETS if m.source == "marketfiyati"])
    # Always include only marketfiyati-backed markets for this source
    target &= {m.id for m in MARKETS if m.source == "marketfiyati"}

    async with httpx.AsyncClient(
        base_url=MARKETFIYATI_BASE,
        headers=BROWSER_HEADERS,
        timeout=30.0,
    ) as client:
        depots = await _nearest_depot_ids(client, latitude, longitude, distance)
        payload: dict[str, Any] = {
            "keywords": keywords,
            "pages": 0,
            "size": size,
            "latitude": latitude,
            "longitude": longitude,
            "distance": distance,
        }
        if depots:
            payload["depots"] = depots

        response = await client.post("/api/v2/search", json=payload)
        response.raise_for_status()
        data = response.json()

    offers: list[dict[str, Any]] = []
    for product in data.get("content") or []:
        offers.extend(_flatten_offers(product, target))

    offers.sort(key=lambda o: (o["price"], o["marketLabel"], o["title"]))

    by_market: dict[str, int] = {}
    for offer in offers:
        by_market[offer["marketId"]] = by_market.get(offer["marketId"], 0) + 1

    return {
        "query": keywords,
        "totalFound": data.get("numberOfFound", len(offers)),
        "offerCount": len(offers),
        "byMarket": by_market,
        "offers": offers,
        "source": "marketfiyati.org.tr",
        "location": {"latitude": latitude, "longitude": longitude, "distance": distance},
    }


async def try_getir_buyuk(keywords: str) -> dict[str, Any]:
    """Best-effort Getir Büyük probe. Returns empty offers if unavailable."""
    meta = MARKET_BY_ID["getir_buyuk"]
    # Getir's public web APIs are location/session locked and frequently blocked.
    # Keep a stable empty response so the UI can show an honest status.
    await asyncio.sleep(0)
    return {
        "marketId": meta.id,
        "marketLabel": meta.label,
        "available": False,
        "reason": (
            "Getir Büyük resmi açık API sunmuyor; marketfiyati.org.tr "
            "kaynağında da yer almıyor. Diğer 5 market canlı çekiliyor."
        ),
        "offers": [],
    }
