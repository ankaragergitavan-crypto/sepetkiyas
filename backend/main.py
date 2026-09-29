from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

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
from .relevance import is_relevant, relevance_score
from .volume import extract_volume_options, filter_offers_by_volume, normalize_volume_label

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "frontend"

app = FastAPI(title="SepetKıyas", version="1.2.0")

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
    }


@app.get("/api/markets")
async def markets() -> dict[str, Any]:
    return {
        "markets": [
            {
                "id": m.id,
                "label": "Getir Çarşı" if m.id == "getir_buyuk" else m.label,
                "color": m.color,
                "live": True,
                "source": m.source,
                "hint": (
                    "Getir ağı · Çarşı (konumlu). Büyük depo için REEF_API_KEY."
                    if m.id == "getir_buyuk"
                    else None
                ),
            }
            for m in MARKETS
        ],
        "cities": CITY_PRESETS,
        "defaults": {
            "latitude": DEFAULT_LAT,
            "longitude": DEFAULT_LON,
            "distance": DEFAULT_DISTANCE_KM,
        },
    }


@app.post("/api/search")
async def search(body: SearchBody) -> dict[str, Any]:
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Ürün adı gerekli")

    # Sadece Ankara konumları
    lat, lon = clamp_to_ankara(body.latitude, body.longitude)
    distance = min(body.distance, 12)

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
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Canlı fiyat alınamadı: {exc}") from exc

    for offer in result["offers"]:
        offer["volume"] = normalize_volume_label(offer.get("volume")) or offer.get("volume")
        offer["relevance"] = relevance_score(offer.get("title") or "", query)

    # Alakasız teklifleri ele (ör. kaşar peynir → peynirli kraker)
    result["offers"] = [
        o for o in result["offers"] if is_relevant(o.get("title") or "", query, min_score=4)
    ]

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
        except Exception as exc:  # noqa: BLE001
            getir_status = {
                "available": False,
                "channel": "error",
                "note": f"Getir araması başarısız: {exc}",
                "offerCount": 0,
            }

    # Önce alaka, sonra fiyat
    result["offers"].sort(
        key=lambda o: (
            -(o.get("relevance") or relevance_score(o.get("title") or "", query)),
            o["price"],
            o.get("marketLabel") or "",
            o["title"],
        )
    )
    by_market: dict[str, int] = {}
    for offer in result["offers"]:
        by_market[offer["marketId"]] = by_market.get(offer["marketId"], 0) + 1
    result["byMarket"] = by_market
    result["offerCount"] = len(result["offers"])

    volumes = extract_volume_options(result["offers"])
    if body.volume:
        result["offers"] = filter_offers_by_volume(result["offers"], body.volume)
        result["offerCount"] = len(result["offers"])

    sources = [result.get("source", "marketfiyati.org.tr")]
    if getir_status and getir_status.get("available"):
        sources.append(getir_status.get("channelLabel") or "Getir")

    return {
        **result,
        "source": " + ".join(sources),
        "volumeOptions": volumes,
        "activeVolume": body.volume,
        "getir": getir_status,
        "sorted": "price_asc",
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
