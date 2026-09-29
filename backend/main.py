from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Query, Request, Response as FastAPIResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from .aktuel import fetch_all_aktuels
from .client import search_marketfiyati
from .getir import search_getir
from .markets import (
    CITY_PRESETS,
    DEFAULT_DISTANCE_KM,
    DEFAULT_LAT,
    DEFAULT_LON,
    MARKETS,
    clamp_to_ankara,
)
from .relevance import is_relevant, relevance_score, split_query_tokens, qty_matches_offer
from .grouping import build_product_groups, sort_offers_by_unit_price
from .robot import annotate_offers, build_robot_pick
from .price_trend import apply_price_trends
from .volume import extract_volume_options, filter_offers_by_volume, normalize_volume_label
from .product_content import build_product_content
from .cart_pdf import build_carts_pdf
from .barcode_lookup import lookup_barcode
from .typo import correct_query
from .list_scan import parse_shopping_list, scan_list_items

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "frontend"

# Render free: ~15 dk işlem yoksa uyur. Sayaç her istekte sıfırlanır.
SLEEP_AFTER_SECONDS = int(os.getenv("SLEEP_AFTER_SECONDS", "900"))
FREE_HOURS_PER_MONTH = float(os.getenv("FREE_HOURS_PER_MONTH", "750"))
_last_activity = time.monotonic()
_awake_started = time.monotonic()


def touch_activity() -> None:
    global _last_activity
    _last_activity = time.monotonic()


def timer_payload() -> dict[str, Any]:
    now = time.monotonic()
    idle = max(0.0, now - _last_activity)
    until_sleep = max(0, int(SLEEP_AFTER_SECONDS - idle))
    session_hours = (now - _awake_started) / 3600.0
    # Takvim ayı: kota her ayın 1'inde 750'ye sıfırlanır (Render free).
    y, m, _ = time.localtime()[:3]
    if m == 12:
        renew_y, renew_m = y + 1, 1
    else:
        renew_y, renew_m = y, m + 1
    return {
        "sleepAfterSeconds": SLEEP_AFTER_SECONDS,
        "secondsUntilSleep": until_sleep,
        "idleSeconds": int(idle),
        "sessionHours": round(session_hours, 3),
        "freeHoursPerMonth": FREE_HOURS_PER_MONTH,
        "renewsMonthly": True,
        "renewsOn": f"{renew_y:04d}-{renew_m:02d}-01",
        "label": "Aktif kalan",
        "note": (
            "İşlem yoksa ~15 dk sonra uyur (uyurken saat sayılmaz). "
            f"Aylık ücretsiz kota {FREE_HOURS_PER_MONTH:.0f} saat; "
            f"her ayın 1'inde yenilenir ({renew_y:04d}-{renew_m:02d}-01). "
            "Kota bitince ay sonuna kadar kilitlenir — Render Billing'den bak."
        ),
    }


class ActivityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> FastAPIResponse:
        touch_activity()
        return await call_next(request)


app = FastAPI(title="AGT MARKET KARŞILAŞTIRMA", version="1.4.0")

app.add_middleware(ActivityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=120)
    latitude: float = DEFAULT_LAT
    longitude: float = DEFAULT_LON
    distance: int = Field(DEFAULT_DISTANCE_KM, ge=1, le=50)
    markets: list[str] | None = None
    volume: str | None = None
    include_getir: bool = True


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "platforms": ["web", "android", "ios", "desktop"],
        "getir": "carsi_live_optional_reef",
        "timer": timer_payload(),
    }


@app.get("/api/timer")
async def timer() -> dict[str, Any]:
    """Bağlanan herkese kalan aktif süre (uyku öncesi)."""
    return timer_payload()


def _market_hint(m: Any) -> str | None:
    if m.id == "getir_buyuk":
        return "Getir ağı · Çarşı (konumlu). Büyük depo için REEF_API_KEY."
    if m.id == "carrefour":
        return "marketfiyati.org.tr canlı (CarrefourSA)."
    if m.source == "pending":
        return "Henüz açık canlı fiyat API’si yok; listede görünür, sonuç gelmez."
    return None


@app.get("/api/markets")
async def markets() -> dict[str, Any]:
    return {
        "markets": [
            {
                "id": m.id,
                "label": "Getir Çarşı" if m.id == "getir_buyuk" else m.label,
                "color": m.color,
                "live": m.source in ("marketfiyati", "getir"),
                "source": m.source,
                "hint": _market_hint(m),
            }
            for m in MARKETS
        ],
        "quickQueries": [
            "süt 1L",
            "yumurta 30",
            "ekmek",
            "kaşar 500g",
            "ayçiçek yağı",
            "tuz",
            "domates",
            "tavuk göğüs",
        ],
        "cities": CITY_PRESETS,
        "cityLabel": "Ankara ilçe",
        "defaults": {
            "latitude": DEFAULT_LAT,
            "longitude": DEFAULT_LON,
            "distance": DEFAULT_DISTANCE_KM,
        },
    }


@app.post("/api/search")
async def search(body: SearchBody) -> dict[str, Any]:
    raw_query = body.query.strip()
    if not raw_query:
        raise HTTPException(status_code=400, detail="Ürün adı gerekli")

    typo = correct_query(raw_query)
    query = typo["query"] or raw_query

    # Sadece Ankara konumları
    lat, lon = clamp_to_ankara(body.latitude, body.longitude)
    # CarrefourSA şubeleri biraz daha uzak olabilir — geniş tarama
    distance = min(max(body.distance, 10), 20)

    selected = body.markets
    marketfiyati_ids = [m.id for m in MARKETS if m.source == "marketfiyati"]
    if selected:
        marketfiyati_ids = [m for m in marketfiyati_ids if m in selected]

    try:
        result = await search_marketfiyati(
            keywords=query,
            latitude=lat,
            longitude=lon,
            distance=distance,
            market_ids=marketfiyati_ids,
            size=48,
            max_pages=6,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Canlı fiyat alınamadı: {exc}") from exc

    for offer in result["offers"]:
        offer["volume"] = normalize_volume_label(offer.get("volume")) or offer.get("volume")
        offer["relevance"] = relevance_score(
            offer.get("title") or "",
            query,
            volume=offer.get("volume"),
        )

    scored = list(result["offers"])
    # Alakasız teklifleri ele — hepsi elenirse en iyi skorluları tut (arama kesilmesin)
    filtered = [
        o
        for o in scored
        if is_relevant(o.get("title") or "", query, min_score=3, volume=o.get("volume"))
    ]
    if filtered:
        result["offers"] = filtered
    elif scored:
        scored.sort(key=lambda o: (-(o.get("relevance") or 0), o.get("price") or 0))
        result["offers"] = scored[:40]
    else:
        result["offers"] = []

    getir_status: dict[str, Any] | None = None
    want_getir = body.include_getir and (not selected or "getir_buyuk" in selected)
    if want_getir:
        try:
            getir = await search_getir(
                keywords=query,
                latitude=lat,
                longitude=lon,
                reef_api_key=os.getenv("REEF_API_KEY"),
            )
            getir_status = {
                "available": getir.get("available"),
                "channel": getir.get("channel"),
                "channelLabel": getir.get("channelLabel"),
                "note": getir.get("note"),
                "offerCount": getir.get("offerCount", 0),
            }
            result["offers"].extend(getir.get("offers") or [])
            again = [
                o
                for o in result["offers"]
                if is_relevant(
                    o.get("title") or "",
                    query,
                    min_score=3,
                    volume=o.get("volume"),
                )
            ]
            result["offers"] = again if again else result["offers"]
        except Exception as exc:  # noqa: BLE001
            getir_status = {
                "available": False,
                "channel": "error",
                "note": f"Getir araması başarısız: {exc}",
                "offerCount": 0,
            }

    # Sorguda "1L" / "500g" varsa ve eşleşen canlı teklif varsa yalnızca onları tut
    _, soft_qty = split_query_tokens(query)
    if soft_qty:
        matched = [
            o
            for o in result["offers"]
            if qty_matches_offer(o.get("title") or "", o.get("volume"), soft_qty)
        ]
        if matched:
            result["offers"] = matched

    by_market: dict[str, int] = {}
    for offer in result["offers"]:
        by_market[offer["marketId"]] = by_market.get(offer["marketId"], 0) + 1
    result["byMarket"] = by_market
    result["offerCount"] = len(result["offers"])

    volumes = extract_volume_options(result["offers"])
    if body.volume:
        result["offers"] = filter_offers_by_volume(result["offers"], body.volume)
        result["offerCount"] = len(result["offers"])

    # Gerçek fiyat değişimi (önceki arama kaydı); yoksa ok yok
    apply_price_trends(result["offers"])
    # Birim fiyat + etiket kanıtı
    annotate_offers(result["offers"])
    # Birim fiyata göre sırala (paket fiyatı yanıltmasın)
    result["offers"] = sort_offers_by_unit_price(result["offers"])
    groups = build_product_groups(result["offers"])

    robot = build_robot_pick(result["offers"], query)

    sources = [result.get("source", "marketfiyati.org.tr")]
    if getir_status and getir_status.get("available"):
        sources.append(getir_status.get("channelLabel") or "Getir")

    return {
        **result,
        "query": query,
        "originalQuery": typo["originalQuery"],
        "typoCorrected": typo["corrected"],
        "typoCorrections": typo["corrections"],
        "typoNote": typo["note"],
        "source": " + ".join(sources),
        "volumeOptions": volumes,
        "activeVolume": body.volume,
        "getir": getir_status,
        "robot": robot,
        "groups": groups,
        "sorted": "unit_price_asc",
        "dataPolicy": {
            "livePricesOnly": True,
            "noFabricatedOffers": True,
            "trendsRequirePriorObservation": True,
            "sort": "unit_price_then_relevance",
            "note": "Yalnızca canlı kaynak fiyatı; uydurma teklif/trend yok. Sıra birim fiyata göre.",
        },
    }


@app.get("/api/search")
async def search_get(
    q: str = Query(..., min_length=1, max_length=120),
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    distance: int = Query(DEFAULT_DISTANCE_KM, ge=1, le=50),
    volume: str | None = None,
) -> dict[str, Any]:
    return await search(
        SearchBody(
            query=q,
            latitude=lat,
            longitude=lon,
            distance=distance,
            volume=volume,
        )
    )


class ListScanBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    latitude: float = DEFAULT_LAT
    longitude: float = DEFAULT_LON
    distance: int = Field(DEFAULT_DISTANCE_KM, ge=1, le=50)
    markets: list[str] | None = None


@app.post("/api/list-scan")
async def list_scan(body: ListScanBody) -> dict[str, Any]:
    """Alışveriş listesi (max 40 satır): aynı ürün+kg+marka önceliği, en ucuz → market sepeti."""
    lines = parse_shopping_list(body.text)
    if not lines:
        raise HTTPException(status_code=400, detail="Listede geçerli satır yok")

    lat, lon = clamp_to_ankara(body.latitude, body.longitude)
    distance = min(max(body.distance, 8), 15)
    selected = body.markets
    marketfiyati_ids = [m.id for m in MARKETS if m.source == "marketfiyati"]
    if selected:
        marketfiyati_ids = [m for m in marketfiyati_ids if m in selected]

    async def search_one(q: str) -> dict[str, Any]:
        return await search_marketfiyati(
            keywords=q,
            latitude=lat,
            longitude=lon,
            distance=distance,
            market_ids=marketfiyati_ids,
            size=36,
            max_pages=4,
        )

    result = await scan_list_items(lines, search_one=search_one, concurrency=3)
    return {
        **result,
        "lines": lines,
        "location": {"latitude": lat, "longitude": lon, "distance": distance},
        "source": "marketfiyati.org.tr",
    }



class ProductContentBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    brand: str | None = None
    volume: str | None = None
    categories: list[str] | None = None
    mainCategory: str | None = None
    menuCategory: str | None = None
    promotionText: str | None = None
    imageUrl: str | None = None
    marketLabel: str | None = None
    depotName: str | None = None
    price: float | None = None
    unitPriceEstimate: float | None = None
    unitPriceUnit: str | None = None
    healthScore: int | None = None
    economyScore: int | None = None
    labelEvidence: list[str] | None = None
    labelNotes: list[str] | None = None
    analysisNote: str | None = None
    source: str | None = None
    updatedAt: str | None = None


@app.post("/api/product-content")
async def product_content(body: ProductContentBody) -> dict[str, Any]:
    """Tıklanan ürün: market kaynağı + varsa Open Food Facts içindekiler."""
    offer = body.model_dump()
    return await build_product_content(offer)


@app.get("/api/product-content")
async def product_content_get(
    title: str = Query(..., min_length=1, max_length=200),
    brand: str | None = None,
) -> dict[str, Any]:
    return await build_product_content({"title": title, "brand": brand})


class CartItemIn(BaseModel):
    id: str
    title: str = ""
    price: float = 0
    qty: int = 1
    marketId: str | None = None
    marketLabel: str | None = None


class CartsPdfBody(BaseModel):
    carts: dict[str, list[CartItemIn]]
    cityLabel: str | None = "Ankara"
    note: str | None = None


@app.post("/api/carts/pdf")
async def carts_pdf(body: CartsPdfBody) -> Response:
    """Sepetleri tarihli detaylı PDF olarak indir (telefon/PC)."""
    payload = {
        "carts": {
            mid: [i.model_dump() for i in items if int(i.qty or 0) > 0]
            for mid, items in (body.carts or {}).items()
        },
        "cityLabel": body.cityLabel or "Ankara",
        "note": body.note or "",
    }
    try:
        pdf_bytes = build_carts_pdf(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"PDF oluşturulamadı: {exc}") from exc

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"sepetkiyas-sepetler-{stamp}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/barcode/{code}")
async def barcode_lookup(code: str) -> dict[str, Any]:
    """Foto/kameradan okunan barkod → ürün adı önerisi."""
    return await lookup_barcode(code)


@app.get("/api/aktuel")
async def aktuel(q: str | None = None) -> dict[str, Any]:
    try:
        return await fetch_all_aktuels(q)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Aktüel alınamadı: {exc}") from exc


@app.get("/api/desktop-shortcut")
async def desktop_shortcut() -> Response:
    """İndirilebilir Windows .url masaüstü kısayolu."""
    content = (
        "[InternetShortcut]\r\n"
        "URL=http://127.0.0.1:8000/\r\n"
        "IconFile=http://127.0.0.1:8000/static/icons/icon-192.png\r\n"
        "IconIndex=0\r\n"
    )
    return Response(
        content=content,
        media_type="application/internet-shortcut",
        headers={
            "Content-Disposition": 'attachment; filename="SepetKiyas.url"',
        },
    )


@app.post("/api/install-desktop")
async def install_desktop() -> dict[str, Any]:
    """Masaüstüne .url ve başlatıcı .bat kopyalar (Windows)."""
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        desktop = Path.home() / "OneDrive" / "Desktop"
    if not desktop.exists():
        raise HTTPException(status_code=500, detail="Masaüstü klasörü bulunamadı")

    url_path = desktop / "SepetKiyas.url"
    url_path.write_text(
        "[InternetShortcut]\n"
        "URL=http://127.0.0.1:8000/\n"
        f"IconFile={ROOT / 'frontend' / 'icons' / 'icon-192.png'}\n"
        "IconIndex=0\n",
        encoding="utf-8",
    )

    bat_src = ROOT / "SepetKiyas.bat"
    bat_dst = desktop / "SepetKiyas-Baslat.bat"
    bat_dst.write_text(bat_src.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")

    return {
        "ok": True,
        "urlShortcut": str(url_path),
        "launcher": str(bat_dst),
        "message": "Masaüstüne SepetKiyas.url ve SepetKiyas-Baslat.bat eklendi.",
    }


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/sw.js")
async def service_worker() -> FileResponse:
    return FileResponse(
        STATIC / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@app.get("/manifest.webmanifest")
async def manifest_root() -> FileResponse:
    return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/robots.txt")
async def robots() -> PlainTextResponse:
    return PlainTextResponse("User-agent: *\nDisallow:\n")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
