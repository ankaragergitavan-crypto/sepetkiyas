from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import httpx

from .markets import MARKET_BY_ID

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%d.%m.%Y %H:%M")


def _offer(
    *,
    market_id: str,
    title: str,
    price: float,
    image_url: str | None = None,
    brand: str | None = None,
    volume: str | None = None,
    old_price: float | None = None,
    discount_ratio: float | None = None,
    campaign: str | None = None,
    product_url: str | None = None,
    source: str,
    cadence: str,
) -> dict[str, Any]:
    meta = MARKET_BY_ID[market_id]
    important = bool(discount_ratio and discount_ratio >= 15)
    return {
        "id": f"aktuel:{market_id}:{abs(hash((title, price, campaign))) % 10**12}",
        "productId": None,
        "title": title,
        "brand": brand,
        "imageUrl": image_url,
        "volume": volume,
        "marketId": market_id,
        "marketLabel": meta.label,
        "marketColor": meta.color,
        "price": price,
        "oldPrice": old_price,
        "unitPrice": None,
        "depotName": campaign,
        "depotId": None,
        "discount": bool(discount_ratio or (old_price and old_price > price)),
        "discountRatio": discount_ratio,
        "promotionText": campaign,
        "updatedAt": _now_iso(),
        "source": source,
        "cadence": cadence,  # weekly | live
        "importantDeal": important,
        "productUrl": product_url,
        "isAktuel": True,
    }


async def fetch_bim_aktuel(limit: int = 80) -> dict[str, Any]:
    """BİM aktüel katalogları haftalık yayınlanır; sayfa anlık okunur."""
    url = "https://www.bim.com.tr/Categories/100/aktuel-urunler.aspx"
    async with httpx.AsyncClient(headers=UA, timeout=25.0, follow_redirects=True) as client:
        home = await client.get(url)
        home.raise_for_status()
        html = home.text
        keys = re.findall(r"Bim_AktuelTarihKey=(\d+)[^>]*>\s*([^<]+)", html)
        # Prefer richest current leaflet
        best_key = None
        best_label = "Güncel aktüel"
        best_count = -1
        best_html = html
        seen: set[str] = set()
        for key, label in keys:
            if key in seen:
                continue
            seen.add(key)
            page = await client.get(f"{url}?Bim_AktuelTarihKey={key}")
            if page.status_code != 200:
                continue
            count = page.text.count('class="product ')
            if count > best_count:
                best_count = count
                best_key = key
                best_label = re.sub(r"\s+", " ", label).strip()
                best_html = page.text

    pattern = re.compile(
        r'<div class="product[^"]*".*?'
        r'<img src="(?P<img>[^"]+)".*?'
        r'<h2 class="subTitle">(?P<brand>.*?)</h2>\s*'
        r'<h2 class="title">(?P<title>.*?)</h2>.*?'
        r'<div class="textArea">(?P<gram>.*?)</div>.*?'
        r'<div class="text quantify">(?P<whole>[^<]*)</div>\s*'
        r'<div class="kusurArea">\s*<span class="number">(?P<frac>[^<]*)</span>',
        re.S | re.I,
    )

    offers: list[dict[str, Any]] = []
    for m in pattern.finditer(best_html):
        brand = re.sub(r"\s+", " ", re.sub("<[^>]+>", "", m.group("brand"))).strip()
        title = re.sub(r"\s+", " ", re.sub("<[^>]+>", "", m.group("title"))).strip()
        gram = re.sub(r"\s+", " ", re.sub("<[^>]+>", "", m.group("gram"))).strip(" •\n\r\t")
        whole = m.group("whole").strip().replace(".", "").replace(",", "")
        frac = m.group("frac").strip()
        try:
            price = float(f"{whole}.{frac}")
        except ValueError:
            continue
        if not title or price <= 0:
            continue
        full_title = f"{brand} {title}".strip() if brand else title
        offers.append(
            _offer(
                market_id="bim",
                title=full_title,
                price=price,
                image_url=m.group("img"),
                brand=brand or None,
                volume=gram or None,
                campaign=f"BİM Aktüel · {best_label}",
                source="bim.com.tr",
                cadence="weekly",
            )
        )
        if len(offers) >= limit:
            break

    return {
        "marketId": "bim",
        "available": bool(offers),
        "cadence": "weekly",
        "catalogLabel": best_label,
        "leafletKey": best_key,
        "count": len(offers),
        "offers": offers,
        "note": "BİM aktüel katalogları genelde haftalık değişir; liste sayfadan anlık çekilir.",
    }


async def fetch_migros_deals(query: str = "indirim", limit: int = 40) -> dict[str, Any]:
    """Migros online indirimleri daha anlık (raf/kampanya)."""
    url = "https://www.migros.com.tr/rest/products/search"
    params = {"q": query, "sayfa": 1}
    async with httpx.AsyncClient(headers={**UA, "Accept": "application/json"}, timeout=25.0) as client:
        # Prefer discounted results: search common groceries + filter discountRate
        queries = [query, "peynir", "yağ", "süt", "deterjan", "makarna"]
        seen_ids: set[Any] = set()
        offers: list[dict[str, Any]] = []
        for q in queries:
            try:
                resp = await client.get(url, params={"q": q, "sayfa": 1})
                resp.raise_for_status()
                payload = resp.json()
            except Exception:
                continue
            items = ((payload.get("data") or {}).get("storeProductInfos")) or []
            for item in items:
                pid = item.get("id")
                if pid in seen_ids:
                    continue
                rate = item.get("discountRate") or 0
                shown = item.get("shownPrice")
                regular = item.get("regularPrice")
                if shown is None:
                    continue
                # kuruş -> TL
                price = float(shown) / 100.0
                old = float(regular) / 100.0 if regular else None
                if rate < 10 and not (old and old > price):
                    continue
                seen_ids.add(pid)
                brand = None
                if isinstance(item.get("brand"), dict):
                    brand = item["brand"].get("name")
                images = item.get("images") or []
                image = None
                if images and isinstance(images[0], dict):
                    image = (images[0].get("urls") or {}).get("PRODUCT_LIST")
                pretty = item.get("prettyName")
                product_url = f"https://www.migros.com.tr/{pretty}" if pretty else None
                offers.append(
                    _offer(
                        market_id="migros",
                        title=item.get("name") or "Ürün",
                        price=price,
                        old_price=old,
                        discount_ratio=float(rate) if rate else (
                            round((1 - price / old) * 100, 1) if old and old > 0 else None
                        ),
                        image_url=image,
                        brand=brand,
                        campaign="Migros online indirim",
                        product_url=product_url,
                        source="migros.com.tr",
                        cadence="live",
                    )
                )
                if len(offers) >= limit:
                    break
            if len(offers) >= limit:
                break

    offers.sort(key=lambda o: (-(o.get("discountRatio") or 0), o["price"]))
    return {
        "marketId": "migros",
        "available": bool(offers),
        "cadence": "live",
        "catalogLabel": "Online indirimler",
        "count": len(offers),
        "offers": offers,
        "note": "Migros indirimleri online raftan anlık çekilir (kampanya oranı ≥ %10).",
    }


async def fetch_a101_aktuel() -> dict[str, Any]:
    """A101 Aldın Aldın çoğu zaman bot korumalı; dürüst durum döndür."""
    urls = [
        "https://www.a101.com.tr/aldin-aldin-bu-hafta-brosuru",
        "https://www.a101.com.tr/aldin-aldin",
    ]
    async with httpx.AsyncClient(headers=UA, timeout=15.0, follow_redirects=True) as client:
        for url in urls:
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and "cloudflare" not in resp.text.lower()[:2000]:
                    # Broşür görselleri olabilir; fiyatlı ürün listesi yoksa boş bırak
                    imgs = re.findall(r'https://cdn2\.a101\.com\.tr[^"\']+', resp.text)
                    if imgs:
                        return {
                            "marketId": "a101",
                            "available": False,
                            "cadence": "weekly",
                            "catalogLabel": "Aldın Aldın",
                            "count": 0,
                            "offers": [],
                            "note": (
                                "A101 aktüel broşür sayfası açıldı ama fiyatlı ürün JSON’u "
                                "bot koruması nedeniyle alınamadı."
                            ),
                            "brochureHint": True,
                        }
            except Exception:
                continue
    return {
        "marketId": "a101",
        "available": False,
        "cadence": "weekly",
        "catalogLabel": "Aldın Aldın",
        "count": 0,
        "offers": [],
        "note": "A101 aktüel şu an Cloudflare koruması nedeniyle canlı çekilemiyor (haftalık katalog).",
    }


async def fetch_all_aktuels(query: str | None = None) -> dict[str, Any]:
    bim, migros, a101 = await _gather_aktuels(query)
    offers: list[dict[str, Any]] = []
    for block in (bim, migros, a101):
        offers.extend(block.get("offers") or [])
    # Important deals first, then price
    offers.sort(
        key=lambda o: (
            0 if o.get("importantDeal") else 1,
            -(o.get("discountRatio") or 0),
            o.get("price") or 10**9,
        )
    )
    important = [o for o in offers if o.get("importantDeal")]
    return {
        "fetchedAt": _now_iso(),
        "summary": {
            "bim": {"cadence": "weekly", "available": bim.get("available"), "count": bim.get("count"), "label": bim.get("catalogLabel"), "note": bim.get("note")},
            "migros": {"cadence": "live", "available": migros.get("available"), "count": migros.get("count"), "label": migros.get("catalogLabel"), "note": migros.get("note")},
            "a101": {"cadence": "weekly", "available": a101.get("available"), "count": a101.get("count"), "label": a101.get("catalogLabel"), "note": a101.get("note")},
        },
        "importantDeals": important[:20],
        "importantCount": len(important),
        "offers": offers,
        "sources": [bim, migros, a101],
    }


async def _gather_aktuels(query: str | None):
    import asyncio

    q = (query or "indirim").strip() or "indirim"
    return await asyncio.gather(
        fetch_bim_aktuel(),
        fetch_migros_deals(q),
        fetch_a101_aktuel(),
    )
