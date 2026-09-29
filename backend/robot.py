from __future__ import annotations

import re
from typing import Any

from .relevance import fold_tr
from .volume import normalize_volume_label, parse_adet_count, volume_sort_key

# Tüm ürünler için kaynak metni sinyalleri (başlık/kategori/marka). Lab skoru değil.
_LABEL_PLUS = [
    (r"\borganik\b", 16, "organik"),
    (r"\bkatkisiz\b|\bkatkısız\b", 10, "katkısız"),
    (r"\bsekersiz\b|\bşekersiz\b", 10, "şekersiz"),
    (r"\btuzsuz\b", 6, "tuzsuz"),
    (r"\btam\s*bugday\b|\btam\s*buğday\b", 10, "tam buğday"),
    (r"\bcavdar\b|\bçavdar\b|\byulaf\b", 8, "çavdar/yulaf"),
    (r"\bzeytinyagi\b|\bzeytinyağı\b|\bnatürel\b|\bsızma\b", 10, "zeytinyağı/sızma"),
    (r"\bfermente\b|\bprobiyotik\b", 8, "fermente/probiyotik"),
    (r"\beski\s*kasar\b|\bkars\s*kasar\b", 10, "eski/Kars kaşar"),
    (r"\btaze\b", 4, "taze"),
    (r"\bsade\b", 4, "sade"),
    (r"\bdogal\b|\bdoğal\b", 4, "doğal"),
    (r"\bgunluk\b|\bgünlük\b", 4, "günlük"),
    (r"\bpasteurize\b|\bpastorize\b|\bpastörize\b", 3, "pastörize"),
    (r"\btam\s*yagli\b|\btam\s*yağlı\b", 3, "tam yağlı"),
    (r"\byagisz\b|\byağsız\b|\byarim\s*yagli\b|\byarım\s*yağlı\b", 3, "yağ oranı belirtilmiş"),
    (r"\bkeçi\b|\bkecı\b|\bkeci\b", 4, "keçi"),
    (r"\bdana\b|\bkuzu\b|\bpili[cç]\b|\btavuk\b", 2, "et türü belirtilmiş"),
    (r"\brife\b|\brifle\b|\b%100\b|\b100\s*%", 4, "saf/oran vurgusu"),
    (r"\bozel\s*yumurta|\bözel\s*yumurta|\bkgb\b|\bgezen\b|\bkafessiz\b", 6, "özel yumurta/gezen"),
    (r"\bglütensiz\b|\bglutensiz\b|\bgluten\s*free\b", 6, "glutensiz"),
    (r"\bseker\s*ilavesiz\b|\bşeker\s*ilavesiz\b", 8, "şeker ilavesiz"),
]
_LABEL_MINUS = [
    (r"\baromali\b|\baromalı\b|\baroma\b", 12, "aroma/aromalı"),
    (r"\bislenmis\b|\bişlenmiş\b", 14, "işlenmiş"),
    (r"\bglikoz\b|\bfruktoz\b|\baspartam\b|\bglukoz\b", 16, "şeker katkı sinyali"),
    (r"\bmargarin\b|\btrans\s*yag\b|\btrans\s*yağ\b", 16, "margarin/trans yağ"),
    (r"\bkraker\b|\bcips\b|\bbiskuvi\b|\bbisküvi\b|\bgofret\b|\bcikolata\b|\bçikolata\b", 14, "atıştırmalık/tatlı"),
    (r"\bspread\b|\beritme\b|\bkrem\s*peynir\s*arom", 10, "eritme/spread"),
    (r"\bsoslu\b|\bacili\b|\bacılı\b|\bbaharatli\b|\bbaharatl[ıi]\b", 6, "soslu/baharatlı"),
    (r"\bhazir\b|\bhazır\b|\benstantane\b", 6, "hazır ürün"),
    (r"\bkoncentre\b|\bkonsantre\b|\bnektar\b", 5, "konsantre/nektar"),
]


def _offer_text_blob(offer: dict[str, Any] | None, title: str, brand: str | None) -> str:
    parts = [title or "", brand or ""]
    if offer:
        parts.append(offer.get("promotionText") or "")
        parts.append(offer.get("mainCategory") or "")
        parts.append(offer.get("menuCategory") or "")
        cats = offer.get("categories") or []
        if isinstance(cats, list):
            parts.extend(str(c) for c in cats)
    return " ".join(p for p in parts if p)


_UNIT_RE = re.compile(
    r"(?P<num>\d+[.,]?\d*)\s*(?:₺|tl)?\s*/\s*(?P<unit>kg|g|l|lt|ml)",
    re.I,
)


def _parse_unit_price(offer: dict[str, Any]) -> float | None:
    """kg/L için ₺/kg(L); adet için ₺/adet. Adeti gram sanma."""
    price = offer.get("price")
    if price is None:
        return None
    try:
        price_f = float(price)
    except (TypeError, ValueError):
        return None
    if price_f <= 0:
        return None

    adet = parse_adet_count(offer.get("volume"), offer.get("title"))
    if adet:
        return price_f / adet

    vol = normalize_volume_label(offer.get("volume"))
    if vol:
        grams, _ = volume_sort_key(vol)
        if 0 < grams < 10**8:
            try:
                return price_f / (grams / 1000.0)
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


def _label_evidence_score(
    title: str,
    brand: str | None = None,
    offer: dict[str, Any] | None = None,
) -> tuple[int, list[str], list[str]]:
    """Kaynak metnindeki ifadeleri tarar; kanıt listesi döner. Lab skoru değildir."""
    raw = _offer_text_blob(offer, title, brand)
    folded = fold_tr(raw)
    score = 50
    evidence: list[str] = []
    notes: list[str] = []

    for pat, pts, label in _LABEL_PLUS:
        if re.search(pat, folded, re.I):
            score += pts
            evidence.append(f"+ «{label}» geçiyor (+{pts})")
    for pat, pts, label in _LABEL_MINUS:
        if re.search(pat, folded, re.I):
            score -= pts
            evidence.append(f"− «{label}» geçiyor (−{pts})")

    # Marka: yalnızca API'de gerçek marka varsa not düş (Markasız/boş yükseltmez)
    b = (brand or "").strip()
    bf = fold_tr(b)
    if b and bf not in {"markasiz", "markasız", "yok", "-", "nan"}:
        notes.append(f"marka: {b}")
    else:
        notes.append("marka kaynağı: Markasız / belirtilmemiş")

    if not any(e.startswith("+") or e.startswith("−") for e in evidence):
        evidence.append("güçlü etiket sinyali yok (nötr)")

    score = max(5, min(95, score))
    return score, evidence[:6], notes


def _economy_score(unit_price: float | None, price: float, units: list[float]) -> tuple[int, str]:
    if unit_price is not None and units:
        lo, hi = min(units), max(units)
        if hi <= lo:
            return 80, "birim fiyat (canlı): makul"
        norm = (hi - unit_price) / (hi - lo)
        score = int(25 + norm * 70)
        if unit_price <= lo * 1.08:
            return min(98, score), f"birim fiyat (canlı) düşük ≈ {unit_price:.0f}"
        if unit_price <= lo + (hi - lo) * 0.35:
            return score, f"birim fiyat (canlı) uygun ≈ {unit_price:.0f}"
        return max(15, score), f"birim fiyat (canlı) yüksek ≈ {unit_price:.0f}"
    return 50, f"paket fiyatı (canlı) {price:.2f} ₺"


def annotate_offers(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Canlı fiyat + kaynak metni kanıtlarıyla skorlar (uydurma açıklama yok)."""
    units: list[float] = []
    parsed: list[float | None] = []
    for o in offers:
        up = _parse_unit_price(o)
        parsed.append(up)
        if up is not None and up > 0:
            units.append(up)

    for o, up in zip(offers, parsed):
        # Zaten tarandıysa tekrar bozma (main + robot çift çağrı)
        if o.get("scoreKind") == "live_price_plus_source_text_evidence" and "labelEvidence" in o:
            # ekonomi skorunu güncel birim listesine göre yenile
            e_score, e_reason = _economy_score(up, float(o["price"]), units)
            o["economyScore"] = e_score
            o["unitPriceEstimate"] = round(up, 2) if up else o.get("unitPriceEstimate")
            hints = o.get("scoreHints") or {}
            hints["economyReason"] = e_reason
            o["scoreHints"] = hints
            o["valuePick"] = e_score >= 65 and int(o.get("healthScore") or 0) >= 58
            continue
        h_score, evidence, notes = _label_evidence_score(
            o.get("title") or "", o.get("brand"), o
        )
        e_score, e_reason = _economy_score(up, float(o["price"]), units)
        value_pick = e_score >= 65 and h_score >= 58
        o["healthScore"] = h_score
        o["economyScore"] = e_score
        o["valuePick"] = value_pick
        o["unitPriceEstimate"] = round(up, 2) if up else None
        o["labelEvidence"] = evidence
        o["labelNotes"] = notes
        o["scoreHints"] = {
            "healthReasons": evidence[:3],
            "economyReason": e_reason,
        }
        o["scoreKind"] = "live_price_plus_source_text_evidence"
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
        if o.get("valuePick"):
            total += 12
        hints = o.get("scoreHints") or {}
        why = [
            hints.get("economyReason") or "canlı fiyat",
            *(hints.get("healthReasons") or [])[:3],
            *(o.get("labelNotes") or [])[:1],
            f"{o.get('marketLabel')}: {float(o['price']):.2f} ₺ (canlı)",
        ]
        if o.get("unitPriceEstimate"):
            why.insert(0, f"birim ≈ {o['unitPriceEstimate']:.0f} (canlı hesabı)")
        if o.get("valuePick"):
            why.insert(0, "canlı fiyatta uygun + etiket metninde olumlu sinyal")

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
                    "Canlı fiyat + kaynak etiket/kategori metni tarandı. "
                    "Bu bir laboratuvar sağlık notu değil; metinde geçen ifadelerin özeti."
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
            "Fiyatlar canlı. Etiket skoru yalnızca başlık/marka/kategori metninde geçen "
            "ifadelerden üretilir; içerik listesi API'de yok. Tıbbi tavsiye değildir."
        ),
    }
