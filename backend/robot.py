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
    (r"\bcavdar\b|\bçavdar\b|\byulaf\b|\bkinoa\b", 8, "çavdar/yulaf/kinoa"),
    (r"\bzeytinyagi\b|\bzeytinyağı\b|\bnatürel\b|\bsızma\b|\bextra\s*virgin\b", 10, "zeytinyağı/sızma"),
    (r"\bfermente\b|\bprobiyotik\b", 8, "fermente/probiyotik"),
    (r"\beski\s*kasar\b|\bkars\s*kasar\b", 10, "eski/Kars kaşar"),
    (r"\btaze\b", 4, "taze"),
    (r"\bsade\b", 4, "sade"),
    (r"\bdogal\b|\bdoğal\b", 4, "doğal"),
    (r"\bgunluk\b|\bgünlük\b", 4, "günlük"),
    (r"\bpasteurize\b|\bpastorize\b|\bpastörize\b", 3, "pastörize"),
    (r"\btam\s*yagli\b|\btam\s*yağlı\b", 3, "tam yağlı"),
    (r"\byagisz\b|\byağsız\b|\byarim\s*yagli\b|\byarım\s*yağlı\b|%\s*0[.,]?5|\b%1\b|\b%1[.,]5\b", 3, "yağ oranı belirtilmiş"),
    (r"\bkeçi\b|\bkecı\b|\bkeci\b", 4, "keçi"),
    (r"\bdana\b|\bkuzu\b|\bpili[cç]\b|\btavuk\b|\bbalik\b|\bbalık\b|\bsomon\b", 2, "et/balık türü belirtilmiş"),
    (r"\brife\b|\brifle\b|\b%100\b|\b100\s*%", 4, "saf/oran vurgusu"),
    (r"\bozel\s*yumurta|\bözel\s*yumurta|\bkgb\b|\bgezen\b|\bkafessiz\b|\bkoy\b|\bköy\b", 6, "özel yumurta/gezen/köy"),
    (r"\bglütensiz\b|\bglutensiz\b|\bgluten\s*free\b", 6, "glutensiz"),
    (r"\bseker\s*ilavesiz\b|\bşeker\s*ilavesiz\b", 8, "şeker ilavesiz"),
    (r"\blaktozsuz\b|\blactose\s*free\b", 6, "laktozsuz"),
    (r"\bomega\s*-?\s*3\b|\bprotein\b|\blif\b|\bvita?min\b", 5, "besin vurgusu (protein/lif/vitamin/omega)"),
    (r"\beski\s*hasat\b|\bsoğuk\s*pres\b|\bsoguk\s*pres\b", 8, "soğuk pres/eski hasat"),
    (r"\bsebzeli\b|\bmeyve\b|\btaze\s*sikma\b|\btaze\s*sıkma\b", 3, "meyve/sebze vurgusu"),
    (r"\bio\b|\beu\s*organik\b", 8, "organik sertifika sinyali"),
]
_LABEL_MINUS = [
    (r"\baromali\b|\baromalı\b|\baroma\b", 12, "aroma/aromalı"),
    (r"\bislenmis\b|\bişlenmiş\b", 14, "işlenmiş"),
    (r"\bglikoz\b|\bfruktoz\b|\baspartam\b|\bglukoz\b", 16, "şeker katkı sinyali"),
    (r"\bmargarin\b|\btrans\s*yag\b|\btrans\s*yağ\b|\bhidrojen\b", 16, "margarin/trans/hidrojenize"),
    (r"\bkraker\b|\bcips\b|\bbiskuvi\b|\bbisküvi\b|\bgofret\b|\bcikolata\b|\bcikolatali\b|\bçikolata\b|\bçikolatalı\b", 14, "atıştırmalık/tatlı"),
    (r"\bspread\b|\beritme\b|\bkrem\s*peynir\s*arom", 10, "eritme/spread"),
    (r"\bsoslu\b|\bacili\b|\bacılı\b|\bbaharatli\b|\bbaharatl[ıi]\b", 6, "soslu/baharatlı"),
    (r"\bhazir\b|\bhazır\b|\benstantane\b", 6, "hazır ürün"),
    (r"\bkoncentre\b|\bkonsantre\b|\bnektar\b", 5, "konsantre/nektar"),
    (r"\bpalm\b|\bpalmiye\b", 10, "palm yağı sinyali"),
    (r"\bmsg\b|\bmonosodyum\b|\bnitrit\b|\bnitrat\b", 12, "katkı (MSG/nitrit) sinyali"),
    (r"\bsekerli\b|\bşekerli\b", 8, "şekerli"),
    (r"\bkızartma\b|\bkizartma\b|\bfritoz\b|\bfried\b", 8, "kızartma"),
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


def _parse_unit_price(offer: dict[str, Any]) -> tuple[float | None, str | None]:
    """(₺/birim, birim etiketi). kg/L → ₺/kg veya ₺/L; adet → ₺/adet."""
    price = offer.get("price")
    if price is None:
        return None, None
    try:
        price_f = float(price)
    except (TypeError, ValueError):
        return None, None
    if price_f <= 0:
        return None, None

    adet = parse_adet_count(offer.get("volume"), offer.get("title"))
    if adet:
        return price_f / adet, "adet"

    vol = normalize_volume_label(offer.get("volume"))
    if vol:
        upper = vol.upper()
        grams, _ = volume_sort_key(vol)
        if 0 < grams < 10**8:
            try:
                per = price_f / (grams / 1000.0)
            except (TypeError, ValueError, ZeroDivisionError):
                per = None
            if per is not None:
                if "ML" in upper or re.search(r"\bL\b", upper):
                    return per, "L"
                return per, "kg"

    raw = offer.get("unitPrice")
    if isinstance(raw, (int, float)):
        return float(raw), "kg"
    if isinstance(raw, str):
        cleaned = raw.replace(" ", "").replace("₺", "").replace("TL", "")
        m = _UNIT_RE.search(cleaned) or _UNIT_RE.search(raw)
        if m:
            try:
                num = float(m.group("num").replace(",", "."))
            except ValueError:
                return None, None
            unit = m.group("unit").lower()
            if unit == "g":
                return num * 1000, "kg"
            if unit == "ml":
                return num * 1000, "L"
            if unit in {"lt", "l"}:
                return num, "L"
            if unit == "kg":
                return num, "kg"
            return num, "kg"
    return None, None


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
        evidence.append("güçlü etiket sinyali yok (nötr ≈ 50)")

    score = max(5, min(95, score))
    return score, evidence[:8], notes


def _economy_score(unit_price: float | None, price: float, units: list[float], unit_label: str | None) -> tuple[int, str]:
    ul = unit_label or "birim"
    if unit_price is not None and units:
        lo, hi = min(units), max(units)
        if hi <= lo:
            return 80, f"birim fiyat (canlı): makul ≈ {unit_price:.0f} ₺/{ul}"
        norm = (hi - unit_price) / (hi - lo)
        score = int(25 + norm * 70)
        if unit_price <= lo * 1.08:
            return min(98, score), f"birim fiyat düşük ≈ {unit_price:.0f} ₺/{ul}"
        if unit_price <= lo + (hi - lo) * 0.35:
            return score, f"birim fiyat uygun ≈ {unit_price:.0f} ₺/{ul}"
        return max(15, score), f"birim fiyat yüksek ≈ {unit_price:.0f} ₺/{ul}"
    return 50, f"paket fiyatı (canlı) {price:.2f} ₺"


def annotate_offers(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Her teklifte zorunlu etiket taraması + sağlık/fiyat % (uydurma yok)."""
    units: list[float] = []
    parsed: list[tuple[float | None, str | None]] = []
    for o in offers:
        up, ul = _parse_unit_price(o)
        parsed.append((up, ul))
        if up is not None and up > 0:
            units.append(up)

    for o, (up, ul) in zip(offers, parsed):
        # Her aramada etiket analizi yeniden yapılır (skor her zaman dolu)
        h_score, evidence, notes = _label_evidence_score(
            o.get("title") or "", o.get("brand"), o
        )
        e_score, e_reason = _economy_score(up, float(o["price"]), units, ul)
        value_pick = e_score >= 65 and h_score >= 58
        o["healthScore"] = int(h_score)
        o["economyScore"] = int(e_score)
        o["valuePick"] = value_pick
        o["unitPriceEstimate"] = round(up, 2) if up else None
        o["unitPriceUnit"] = ul
        o["labelEvidence"] = evidence
        o["labelNotes"] = notes
        o["scoreHints"] = {
            "healthReasons": evidence[:4],
            "economyReason": e_reason,
        }
        o["scoreKind"] = "live_price_plus_source_text_evidence"
        o["analysisNote"] = (
            "Sağlık %: başlık/marka/kategori etiket metni taraması. "
            "Laboratuvar veya içerik listesi API'de yok."
        )
    return offers


def _pick_reasons(o: dict[str, Any], e_score: int, h_score: int, total: float) -> list[str]:
    hints = o.get("scoreHints") or {}
    reasons: list[str] = [
        f"Sağlık skoru {h_score}/100 (etiket metni analizi)",
    ]
    for ev in (hints.get("healthReasons") or o.get("labelEvidence") or [])[:4]:
        reasons.append(str(ev))
    econ = hints.get("economyReason") or "canlı fiyat"
    reasons.append(f"Fiyat skoru {e_score}/100 — {econ}")
    if o.get("unitPriceEstimate") is not None:
        ul = o.get("unitPriceUnit") or "birim"
        reasons.append(f"Birim fiyat ≈ {float(o['unitPriceEstimate']):.0f} ₺/{ul}")
    reasons.append(
        f"Canlı paket: {o.get('marketLabel')} {float(o['price']):.2f} ₺"
        + (f" · {o['depotName']}" if o.get("depotName") else "")
    )
    if o.get("distanceKm") is not None:
        reasons.append(f"Uzaklık {o['distanceKm']} km (Ankara canlı şube)")
    reasons.append(
        f"Neden önerildi: birleşik skor {total:.0f} "
        f"(fiyat ağırlığı %55 + sağlık ağırlığı %45"
        + (", uygun fiyat+etiket bonusu" if o.get("valuePick") else "")
        + ")"
    )
    return reasons


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
        why = _pick_reasons(o, e_score, h_score, total)

        ranked.append(
            {
                "offer": o,
                "score": round(total, 1),
                "economyScore": e_score,
                "healthScore": h_score,
                "unitPriceEstimate": o.get("unitPriceEstimate"),
                "unitPriceUnit": o.get("unitPriceUnit"),
                "valuePick": bool(o.get("valuePick")),
                "reasons": why,
                "whyTitle": "Neden önerildi",
                "summary": (
                    f"“{query}” için tüm market canlı fiyat + etiket tarandı. "
                    f"Sağlık {h_score}/100, fiyat {e_score}/100."
                ),
            }
        )

    by_price = sorted(
        ranked,
        key=lambda x: (
            x["offer"].get("unitPriceEstimate")
            if x["offer"].get("unitPriceEstimate") is not None
            else x["offer"]["price"],
            x["offer"]["price"],
        ),
    )
    by_health = sorted(
        ranked,
        key=lambda x: (-int(x.get("healthScore") or 0), x["offer"]["price"]),
    )
    by_recommend = sorted(
        ranked,
        key=lambda x: (
            -int(x.get("valuePick") or 0),
            -x["score"],
            x["offer"]["price"],
        ),
    )

    top = by_recommend[0]
    return {
        "query": query,
        "pick": top,
        "bestPrice": by_price[0],
        "bestHealth": by_health[0],
        "alternatives": by_recommend[1:3],
        "disclaimer": (
            "Fiyatlar canlı · tüm market tarandı. "
            "En uygun = birim/paket fiyatı · Kaliteli = etiket sinyali · "
            "Öneri = fiyat+kalite birleşik skor. Tıbbi tavsiye değildir."
        ),
    }
