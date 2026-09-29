from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketMeta:
    id: str
    label: str
    api_names: tuple[str, ...]
    color: str
    source: str  # marketfiyati | getir


MARKETS: tuple[MarketMeta, ...] = (
    MarketMeta("a101", "A101", ("a101",), "#00A0E3", "marketfiyati"),
    MarketMeta("migros", "Migros", ("migros",), "#FF6600", "marketfiyati"),
    MarketMeta("sok", "Şok", ("sok",), "#FFD100", "marketfiyati"),
    MarketMeta("tarim_kredi", "Tarım Kredi", ("tarim_kredi",), "#2E7D32", "marketfiyati"),
    MarketMeta("bim", "BİM", ("bim",), "#E30613", "marketfiyati"),
    MarketMeta("getir_buyuk", "Getir", ("getir_buyuk", "getirbuyuk", "getir"), "#5D3EBC", "getir"),
)

MARKET_BY_ID = {m.id: m for m in MARKETS}
API_NAME_TO_ID = {name: m.id for m in MARKETS for name in m.api_names}

# Sadece Ankara
DEFAULT_LAT = 39.9777
DEFAULT_LON = 32.8670
DEFAULT_DISTANCE_KM = 8

CITY_PRESETS = [
    {"id": "ankara-kecioren", "label": "Ankara · Keçiören", "lat": 39.9777, "lon": 32.8670},
    {"id": "ankara-cankaya", "label": "Ankara · Çankaya", "lat": 39.9208, "lon": 32.8541},
    {"id": "ankara-yenimahalle", "label": "Ankara · Yenimahalle", "lat": 39.9667, "lon": 32.8111},
    {"id": "ankara-mamak", "label": "Ankara · Mamak", "lat": 39.9200, "lon": 32.9100},
    {"id": "ankara-etimesgut", "label": "Ankara · Etimesgut", "lat": 39.9500, "lon": 32.6700},
    {"id": "ankara-sincan", "label": "Ankara · Sincan", "lat": 39.9660, "lon": 32.5800},
    {"id": "ankara-pursaklar", "label": "Ankara · Pursaklar", "lat": 40.0400, "lon": 32.9000},
]

# Ankara bounding box (yaklaşık) — dış konumları reddetmek için
ANKARA_BOUNDS = {
    "lat_min": 39.70,
    "lat_max": 40.20,
    "lon_min": 32.45,
    "lon_max": 33.15,
}


def clamp_to_ankara(lat: float, lon: float) -> tuple[float, float]:
    """Ankara dışındaki koordinatları varsayılan Keçiören'e çeker."""
    b = ANKARA_BOUNDS
    if b["lat_min"] <= lat <= b["lat_max"] and b["lon_min"] <= lon <= b["lon_max"]:
        return lat, lon
    return DEFAULT_LAT, DEFAULT_LON
