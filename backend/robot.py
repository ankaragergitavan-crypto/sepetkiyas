from __future__ import annotations

import re
from typing import Any

from .relevance import fold_tr
from .volume import normalize_volume_label, volume_sort_key

# Basit etiket ipuçları — tıbbi tavsiye değil.
_HEALTH_PLUS = re.compile(
    r"(organik|tam\s*yagli|tam\s*yağlı|taze|dogal|doğal|sade|katkisiz|katkısız|"
    r"sekersiz|şekersiz|tam\s*bugday|tam\s*buğday|yulaf|zeytinyagi|zeytinyağı|"
    r"birinci\s*kalite|gunluk|günlük|fermente)",
    re.I,
)
_HEALTH_MINUS = re.compile(
    r"(aromali|aromalı|islenmis|işlenmiş|ultra|light\s*arom|"
    r"margarin|trans\s*yag|trans\s*yağ|glikoz|fruktoz|aspartam|"
    r"kraker|cips|biskuvi|bisküvi|gofret|soslu|acili|acılı|"
    r"karisim|karışım|spread|eritme|ucuz\s*karisim)",
    re.I,
)
_UNIT_RE = re.compile(
    r"(?P<num>\d+[.,]?\d*)\s*(?:₺|tl)?\s*/\s*(?P<unit>kg|g|l|lt|ml)",
    re.I,
)


def _parse_unit_price(offer: dict[str, Any]) -> float | None:
    raw = offer.get("unitPrice")
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        m = _UNIT_RE.search(raw.replace(" ", ""))
        if not m:
            m = _UNIT_RE.search(raw)
        if m:
            try:
                num = float(m.group("num").replace(",", "."))
            except ValueError:
                return None
            unit = m.group("unit").lower()
            if unit == "g":
                return num * 1000  # → ₺/kg eşdeğeri
            if unit == "ml":
                return num * 1000  # → ₺/L eşdeğeri
            if unit in {"lt", "l", "kg"}:
                return num
            return num
    # Gramajdan birim fiyat tahmin et
    vol = normalize_volume_label(offer.get("volume"))
    price = offer.get("price")
    if not vol or price is None:
        return None
    grams, _ = volume_sort_key(vol)
    if grams <= 0 or grams >= 10**8:
        return None
    try:
        return float(price) / (grams / 1000.0)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _health_score(title: str, brand: str | None = None) -> tuple[int, list[str]]:
    """0–100 arası kaba skor + kısa gerekçe parçaları."""
    text = f"{title} {brand or ''}"
    t = fold_tr(text)
    score = 55
    reasons: list[str] = []

    if _HEALTH_PLUS.search(text):
        score += 18
        reasons.append("etikette olumlu/sade ifadeler var")
    if _HEALTH_MINUS.search(text):
        score -= 28
        reasons.append("işlenmiş/aromalı ürün sinyali")

    # Peynir / kaşar: sade dilim tercih
    if "kasar" in t or "peynir" in t:
        if "dilim" in t or "blok" in t or "topak" in t:
            score += 8
            reasons.append("sade peynir/kaşar formu")
        if "light" in t and "arom" not in t:
            score += 2
            reasons.append("light seçenek (tercihe bağlı)")
        if "ucgen" in t or "labne" in t and "kasar" in t:
            score -= 6

    # İçecekler: şekersiz / sade
    if "sut" in t or "süt" in title.casefold():
        if "aroma" in t or "cikolata" in t or "muz" in t:
            score -= 12
            reasons.append("aromalı süt yerine sade daha dengeli")
        else:
            score += 6
            reasons.append("sade süt profili")

    score = max(5, min(98, score))
    if not reasons:
        reasons.append("liste içinde dengeli bir ürün")
    return score, reasons


def _economy_score(unit_price: float | None, price: float, units: list[float]) -> tuple[int, str]:
    if unit_price is not None and units:
        lo, hi = min(units), max(units)
        if hi <= lo:
            return 80, "birim fiyat makul"
        # Düşük birim fiyat → yüksek ekonomi skoru
        norm = (hi - unit_price) / (hi - lo)
        score = int(25 + norm * 70)
        if unit_price <= lo * 1.05:
            return min(98, score), "birim fiyatta en ucuzlara yakın"
        if unit_price <= lo + (hi - lo) * 0.35:
            return score, "birim fiyat uygun"
        return max(20, score), "birim fiyat orta/yüksek"
    # Paket fiyatına göre kaba skor
    return 50, f"paket fiyatı {price:.2f} ₺"


def build_robot_pick(offers: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
    if not offers:
        return None

    unit_prices: list[float] = []
    enriched: list[dict[str, Any]] = []
    for o in offers:
        up = _parse_unit_price(o)
        if up is not None and up > 0:
            unit_prices.append(up)
        h_score, h_reasons = _health_score(o.get("title") or "", o.get("brand"))
        enriched.append({**o, "_unit": up, "_health": h_score, "_h_reasons": h_reasons})

    ranked: list[dict[str, Any]] = []
    for o in enriched:
        e_score, e_reason = _economy_score(o["_unit"], float(o["price"]), unit_prices)
        # Dengeli skor: ekonomi %55, sağlık %45
        total = 0.55 * e_score + 0.45 * o["_health"]
        # Alaka bonusu
        total += min(8, (o.get("relevance") or 0))
        why = [
            e_reason,
            *o["_h_reasons"][:2],
            f"{o.get('marketLabel')}: {float(o['price']):.2f} ₺",
        ]
        if o["_unit"]:
            why.insert(0, f"birim ≈ {o['_unit']:.0f} ₺/kg-L")
        ranked.append(
            {
                "offer": {k: v for k, v in o.items() if not str(k).startswith("_")},
                "score": round(total, 1),
                "economyScore": e_score,
                "healthScore": o["_health"],
                "unitPriceEstimate": round(o["_unit"], 2) if o["_unit"] else None,
                "reasons": why,
                "summary": (
                    f"Ekonomik ({e_score}/100) ve daha sade/sağlıklı profil "
                    f"({o['_health']}/100) dengesiyle öne çıktı."
                ),
            }
        )

    ranked.sort(key=lambda x: (-x["score"], x["offer"]["price"]))
    top = ranked[0]
    alts = ranked[1:3]
    return {
        "query": query,
        "pick": top,
        "alternatives": alts,
        "disclaimer": (
            "Kıyas robotu etiket adına ve fiyata göre tahmin yapar; "
            "tıbbi tavsiye değildir. İçerik için ambalajı kontrol edin."
        ),
    }
