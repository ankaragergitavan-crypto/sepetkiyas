from __future__ import annotations

import re
from typing import Any

from .relevance import fold_tr
from .volume import normalize_volume_label, volume_sort_key

# Basit etiket ipuçları — tıbbi tavsiye değil.
_HEALTH_PLUS = re.compile(
    r"(organik|tam\s*yagli|tam\s*yağlı|taze|dogal|doğal|sade|katkisiz|katkısız|"
    r"sekersiz|şekersiz|tam\s*bugday|tam\s*buğday|yulaf|zeytinyagi|zeytinyağı|"
    r"birinci\s*kalite|gunluk|günlük|fermente|eski\s*kasar|kars\s*kasar)",
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
    """Önce gramajdan hesapla (daha güvenilir); yoksa unitPrice metni."""
    vol = normalize_volume_label(offer.get("volume"))
    price = offer.get("price")
    if vol and price is not None:
        grams, _ = volume_sort_key(vol)
        if 0 < grams < 10**8:
            try:
                return float(price) / (grams / 1000.0)
            except (TypeError, ValueError, ZeroDivisionError):
                pass

    raw = offer.get("unitPrice")
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        cleaned = raw.replace(" ", "").replace("₺", "").replace("TL", "")
        m = _UNIT_RE.search(cleaned) or _UNIT_RE.search(raw)
        if m:
            try:
                num = float(m.group("num").replace(",", "."))
            except ValueError:
                return None
            unit = m.group("unit").lower()
            if unit == "g":
                return num * 1000
            if unit == "ml":
                return num * 1000
            if unit in {"lt", "l", "kg"}:
                return num
            return num
    return None


def _health_score(title: str, brand: str | None = None) -> tuple[int, list[str]]:
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

    if "kasar" in t or "peynir" in t:
        if "eski" in t or "kars" in t:
            score += 10
            reasons.append("eski/kaliteli kaşar profili")
        if "dilim" in t or "blok" in t or "topak" in t or re.search(r"\b1\s*kg\b", t):
            score += 6
            reasons.append("sade peynir/kaşar formu")
        if "light" in t and "arom" not in t:
            score += 2
        if "ucgen" in t or ("labne" in t and "kasar" in t):
            score -= 6

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
        norm = (hi - unit_price) / (hi - lo)
        score = int(25 + norm * 70)
        if unit_price <= lo * 1.08:
            return min(98, score), "birim fiyatta en ucuzlara yakın"
        if unit_price <= lo + (hi - lo) * 0.35:
            return score, "birim fiyat uygun"
        return max(15, score), "birim fiyat orta/yüksek"
    prices = units  # misuse fallback unused
    _ = prices
    return 50, f"paket fiyatı {price:.2f} ₺"


def annotate_offers(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Her teklife healthScore / economyScore / valuePick yazar."""
    units: list[float] = []
    parsed: list[float | None] = []
    for o in offers:
        up = _parse_unit_price(o)
        parsed.append(up)
        if up is not None and up > 0:
            units.append(up)

    for o, up in zip(offers, parsed):
        h_score, h_reasons = _health_score(o.get("title") or "", o.get("brand"))
        e_score, e_reason = _economy_score(up, float(o["price"]), units)
        value_pick = e_score >= 65 and h_score >= 55
        o["healthScore"] = h_score
        o["economyScore"] = e_score
        o["valuePick"] = value_pick
        o["unitPriceEstimate"] = round(up, 2) if up else None
        o["scoreHints"] = {
            "healthReasons": h_reasons[:2],
            "economyReason": e_reason,
        }
    return offers


def build_robot_pick(offers: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
    if not offers:
        return None

    annotate_offers(offers)

    ranked: list[dict[str, Any]] = []
    for o in offers:
        e_score = int(o.get("economyScore") or 50)
        h_score = int(o.get("healthScore") or 50)
        total = 0.55 * e_score + 0.45 * h_score + min(8, (o.get("relevance") or 0))
        # Uygun fiyat + kalite bonus
        if o.get("valuePick"):
            total += 12
        hints = o.get("scoreHints") or {}
        why = [
            hints.get("economyReason") or "fiyat değerlendirildi",
            *(hints.get("healthReasons") or [])[:2],
            f"{o.get('marketLabel')}: {float(o['price']):.2f} ₺",
        ]
        if o.get("unitPriceEstimate"):
            why.insert(0, f"birim ≈ {o['unitPriceEstimate']:.0f} ₺/kg-L")
        if o.get("valuePick"):
            why.insert(0, "uygun fiyat + kaliteli profil")

        ranked.append(
            {
                "offer": o,
                "score": round(total, 1),
                "economyScore": e_score,
                "healthScore": h_score,
                "unitPriceEstimate": o.get("unitPriceEstimate"),
                "valuePick": bool(o.get("valuePick")),
                "reasons": why,
                "summary": (
                    (
                        "Uygun fiyatlı ve daha kaliteli/sade profil dengesiyle öne çıktı."
                        if o.get("valuePick")
                        else f"Ekonomik ({e_score}/100) ve sağlık profili ({h_score}/100) dengesiyle öne çıktı."
                    )
                ),
            }
        )

    ranked.sort(
        key=lambda x: (
            -int(x.get("valuePick") or 0),
            -x["score"],
            x["offer"]["price"],
        )
    )
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
