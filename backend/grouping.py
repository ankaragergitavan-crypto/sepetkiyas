from __future__ import annotations

import re
from typing import Any

from .relevance import fold_tr


def _simplify_title(title: str) -> str:
    t = fold_tr(title or "")
    # Gramaj / adet gürültüsünü düş
    t = re.sub(r"\b\d+[.,]?\d*\s*(kg|g|gr|ml|l|lt|cl|adet|li|lı|lu|lü)\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def product_group_key(offer: dict[str, Any]) -> str:
    brand = fold_tr((offer.get("brand") or "").strip()) or "markasiz"
    if brand in {"markasiz", "yok", "-", "nan"}:
        brand = "markasiz"
    title = _simplify_title(offer.get("title") or "")
    vol = fold_tr((offer.get("volume") or "").strip())
    # productId varsa daha sağlam grup
    pid = offer.get("productId")
    if pid:
        return f"id:{pid}|{vol}"
    return f"{brand}|{title}|{vol}"


def unit_sort_key(offer: dict[str, Any]) -> tuple[float, float, str]:
    unit = offer.get("unitPriceEstimate")
    if unit is None and offer.get("unitPriceValue") is not None:
        try:
            unit = float(offer["unitPriceValue"])
        except (TypeError, ValueError):
            unit = None
    price = float(offer.get("price") or 0)
    # Birim yoksa paket fiyatıyla geri düş (büyük ceza yok ama sonda kalsın biraz)
    primary = float(unit) if unit is not None and unit > 0 else price * 1000
    return (primary, price, offer.get("marketLabel") or "")


def sort_offers_by_unit_price(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        offers,
        key=lambda o: (
            -(o.get("relevance") or 0),
            *unit_sort_key(o),
            o.get("title") or "",
        ),
    )


def build_product_groups(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for offer in offers:
        buckets.setdefault(product_group_key(offer), []).append(offer)

    groups: list[dict[str, Any]] = []
    for key, items in buckets.items():
        items = sort_offers_by_unit_price(items)
        head = items[0]
        best_unit = head.get("unitPriceEstimate")
        if best_unit is None and head.get("unitPriceValue") is not None:
            try:
                best_unit = float(head["unitPriceValue"])
            except (TypeError, ValueError):
                best_unit = None
        groups.append(
            {
                "key": key,
                "title": head.get("title"),
                "brand": head.get("brand"),
                "volume": head.get("volume"),
                "imageUrl": head.get("imageUrl"),
                "bestPrice": head.get("price"),
                "bestUnitPrice": best_unit,
                "bestMarketId": head.get("marketId"),
                "bestMarketLabel": head.get("marketLabel"),
                "marketCount": len({i.get("marketId") for i in items}),
                "offers": items,
            }
        )

    groups.sort(
        key=lambda g: (
            g.get("bestUnitPrice") is None,
            float(g["bestUnitPrice"]) if g.get("bestUnitPrice") is not None else 10**12,
            float(g.get("bestPrice") or 10**12),
        )
    )
    return groups
