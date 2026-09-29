from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

# Render free disk ephemeral — yine de gerçek gözlem; uydurma ok yok.
_STORE = Path(__file__).resolve().parent.parent / "data" / "price_history.json"
_LOCK = threading.Lock()
_MAX_KEYS = 8000


def _load() -> dict[str, Any]:
    try:
        if _STORE.exists():
            return json.loads(_STORE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"items": {}}


def _save(data: dict[str, Any]) -> None:
    try:
        _STORE.parent.mkdir(parents=True, exist_ok=True)
        items = data.get("items") or {}
        if len(items) > _MAX_KEYS:
            # En eski gözlemleri budar
            ordered = sorted(items.items(), key=lambda kv: kv[1].get("ts") or 0)
            data["items"] = dict(ordered[-_MAX_KEYS:])
        _STORE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def offer_key(offer: dict[str, Any]) -> str:
    pid = offer.get("productId") or offer.get("id") or offer.get("title")
    depot = offer.get("depotId") or offer.get("marketId") or ""
    return f"{pid}|{depot}"


def apply_price_trends(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Önceki gerçek kayda göre up/down/flat; yoksa trend=null (ok yok)."""
    now = time.time()
    with _LOCK:
        data = _load()
        items: dict[str, Any] = data.setdefault("items", {})
        for offer in offers:
            key = offer_key(offer)
            try:
                price = float(offer["price"])
            except (KeyError, TypeError, ValueError):
                offer["trend"] = None
                continue

            prev = items.get(key)
            trend = None
            prev_price = None
            delta = None
            delta_pct = None

            if prev and isinstance(prev.get("price"), (int, float)):
                prev_price = float(prev["price"])
                delta = round(price - prev_price, 2)
                if abs(delta) < 0.005:
                    trend = "flat"
                    delta = 0.0
                    delta_pct = 0.0
                else:
                    trend = "up" if delta > 0 else "down"
                    if prev_price:
                        delta_pct = round((delta / prev_price) * 100, 2)

            offer["trend"] = trend
            offer["prevPrice"] = prev_price
            offer["priceDelta"] = delta
            offer["priceDeltaPct"] = delta_pct

            # Yeni gözlemi kaydet (aynı fiyat da ts güncellenir)
            items[key] = {
                "price": price,
                "ts": now,
                "title": offer.get("title"),
                "marketId": offer.get("marketId"),
            }

        _save(data)
    return offers
