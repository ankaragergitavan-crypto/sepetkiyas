from __future__ import annotations

import asyncio
import math
from typing import Any

import httpx

from .markets import (
    ANKARA_BOUNDS,
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


def fold_ascii(text: str) -> str:
    table = str.maketrans(
        {
            "ı": "i",
            "İ": "i",
            "I": "i",
            "ş": "s",
            "Ş": "s",
            "ğ": "g",
            "Ğ": "g",
            "ü": "u",
            "Ü": "u",
            "ö": "o",
            "Ö": "o",
            "ç": "c",
            "Ç": "c",
        }
    )
    return (text or "").translate(table)


def _normalize_market(api_name: str | None) -> str | None:
    if not api_name:
        return None
    key = api_name.strip().lower().replace(" ", "_")
    return API_NAME_TO_ID.get(key)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _in_ankara(lat: float, lon: float) -> bool:
    b = ANKARA_BOUNDS
    return b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]


def _flatten_offers(
    product: dict[str, Any],
    target_ids: set[str],
    *,
    origin_lat: float,
    origin_lon: float,
    max_km: float,
) -> list[dict[str, Any]]:
    """Yalnızca geçerli fiyat + seçilen konumdaki şube (uzak şehir yok)."""
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
        if price_f <= 0:
            continue

        try:
            dlat = float(depot.get("latitude"))
            dlon = float(depot.get("longitude"))
        except (TypeError, ValueError):
            continue
        if not _in_ankara(dlat, dlon):
            continue
        dist = _haversine_km(origin_lat, origin_lon, dlat, dlon)
        if dist > max_km + 0.35:
            continue

        meta = MARKET_BY_ID[market_id]
        offers.append(
            {
                "id": f"{product.get('id')}:{depot.get('depotId')}",
                "productId": product.get("id"),
                "title": product.get("title") or "Ürün",
                "brand": product.get("brand"),
                "imageUrl": product.get("imageUrl"),
                "volume": product.get("refinedVolumeOrWeight")
                or product.get("refinedQuantityUnit"),
                "categories": product.get("categories") or [],
                "mainCategory": product.get("main_category"),
                "menuCategory": product.get("menu_category"),
                "marketId": market_id,
                "marketLabel": meta.label,
                "marketColor": meta.color,
                "price": price_f,
                "unitPrice": depot.get("unitPrice"),
                "unitPriceValue": depot.get("unitPriceValue"),
                "depotName": depot.get("depotName"),
                "depotId": depot.get("depotId"),
                "depotLat": dlat,
                "depotLon": dlon,
                "distanceKm": round(dist, 2),
                "discount": bool(depot.get("discount")),
                "discountRatio": depot.get("discountRatio"),
                "percentage": depot.get("percentage"),
                "promotionText": depot.get("promotionText"),
                "updatedAt": depot.get("indexTime"),
                "source": "marketfiyati",
                "inStockLive": True,
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


async def _search_pages(
    client: httpx.AsyncClient,
    *,
    keywords: str,
    latitude: float,
    longitude: float,
    distance: int,
    size: int,
    max_pages: int,
    depots: list[str] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """A–Z: tüm sayfaları tara, ürünleri birleştir."""
    all_content: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    last: dict[str, Any] = {}
    for page in range(max_pages):
        payload: dict[str, Any] = {
            "keywords": keywords,
            "pages": page,
            "size": size,
            "latitude": latitude,
            "longitude": longitude,
            "distance": distance,
        }
        if depots:
            payload["depots"] = depots
        response = await client.post("/api/v2/search", json=payload)
        response.raise_for_status()
        last = response.json()
        chunk = last.get("content") or []
        if not chunk:
            break
        for product in chunk:
            pid = str(product.get("id") or "")
            if pid and pid in seen_ids:
                continue
            if pid:
                seen_ids.add(pid)
            all_content.append(product)
        # Son sayfa kısa geldiyse daha yok
        if len(chunk) < size:
            break
    return last, all_content


async def search_marketfiyati(
    keywords: str,
    latitude: float = DEFAULT_LAT,
    longitude: float = DEFAULT_LON,
    distance: int = DEFAULT_DISTANCE_KM,
    size: int = 48,
    market_ids: list[str] | None = None,
    max_pages: int = 6,
) -> dict[str, Any]:
    """
    Markette geçen tüm eşleşen ürünleri A–Z (çok sayfa) tara.
    Depo kısıtı sonuçları bozarsa depo olmadan tekrar dener.
    """
    target = set(market_ids or [m.id for m in MARKETS if m.source == "marketfiyati"])
    target &= {m.id for m in MARKETS if m.source == "marketfiyati"}
    keywords = (keywords or "").strip()
    if not keywords:
        return {
            "query": "",
            "totalFound": 0,
            "offerCount": 0,
            "byMarket": {},
            "offers": [],
            "source": "marketfiyati.org.tr",
            "location": {"latitude": latitude, "longitude": longitude, "distance": distance},
        }

    offers: list[dict[str, Any]] = []
    data: dict[str, Any] = {}
    used_kw = keywords

    async with httpx.AsyncClient(
        base_url=MARKETFIYATI_BASE,
        headers=BROWSER_HEADERS,
        timeout=45.0,
    ) as client:
        # Geniş tarama: önce depo kısıtı OLMADAN (tüm market ürünleri)
        data, content = await _search_pages(
            client,
            keywords=keywords,
            latitude=latitude,
            longitude=longitude,
            distance=distance,
            size=size,
            max_pages=max_pages,
            depots=None,
        )
        offers = []
        for product in content:
            offers.extend(
                _flatten_offers(
                    product,
                    target,
                    origin_lat=latitude,
                    origin_lon=longitude,
                    max_km=float(distance) + 2.0,
                )
            )

        # Boşsa ASCII anahtar
        if not offers:
            ascii_kw = fold_ascii(keywords)
            if ascii_kw and ascii_kw.casefold() != keywords.casefold():
                used_kw = ascii_kw
                data, content = await _search_pages(
                    client,
                    keywords=ascii_kw,
                    latitude=latitude,
                    longitude=longitude,
                    distance=distance,
                    size=size,
                    max_pages=max_pages,
                    depots=None,
                )
                for product in content:
                    offers.extend(
                        _flatten_offers(
                            product,
                            target,
                            origin_lat=latitude,
                            origin_lon=longitude,
                            max_km=float(distance) + 4.0,
                        )
                    )

        # Hâlâ boşsa en yakın depolarla dene
        if not offers:
            depots = await _nearest_depot_ids(client, latitude, longitude, distance)
            if depots:
                data, content = await _search_pages(
                    client,
                    keywords=used_kw,
                    latitude=latitude,
                    longitude=longitude,
                    distance=max(distance, 12),
                    size=size,
                    max_pages=max_pages,
                    depots=depots,
                )
                for product in content:
                    offers.extend(
                        _flatten_offers(
                            product,
                            target,
                            origin_lat=latitude,
                            origin_lon=longitude,
                            max_km=float(distance) + 6.0,
                        )
                    )

    # Tekrarlayan teklifleri ele
    uniq: dict[str, dict[str, Any]] = {}
    for o in offers:
        uniq[o["id"]] = o
    offers = list(uniq.values())
    offers.sort(key=lambda o: (o["price"], o["marketLabel"], o["title"]))

    by_market: dict[str, int] = {}
    for offer in offers:
        by_market[offer["marketId"]] = by_market.get(offer["marketId"], 0) + 1

    return {
        "query": keywords,
        "searchKeywords": used_kw,
        "totalFound": data.get("numberOfFound", len(offers)),
        "offerCount": len(offers),
        "byMarket": by_market,
        "offers": offers,
        "source": "marketfiyati.org.tr",
        "location": {"latitude": latitude, "longitude": longitude, "distance": distance},
        "pagesScanned": True,
    }


async def try_getir_buyuk(keywords: str) -> dict[str, Any]:
    meta = MARKET_BY_ID["getir_buyuk"]
    await asyncio.sleep(0)
    return {
        "marketId": meta.id,
        "marketLabel": meta.label,
        "available": False,
        "reason": (
            "Getir Büyük resmi açık API sunmuyor; marketfiyati.org.tr "
            "kaynağında da yer almıyor."
        ),
        "offers": [],
    }
