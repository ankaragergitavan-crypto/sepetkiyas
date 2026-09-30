from __future__ import annotations

import re
from typing import Any


_VOL_RE = re.compile(
    r"(?P<num>\d+[.,]?\d*)\s*(?P<unit>kg|g|gr|gram|ml|lt|l|cl|adet|lı|li|lu|lü)?",
    re.I,
)


def _ml_from_parts(value: float, unit: str) -> float | None:
    u = (unit or "").lower()
    if u in {"l", "lt"}:
        return value * 1000.0
    if u in {"ml"}:
        return value
    if u in {"cl"}:
        return value * 10.0
    if u in {"kg"}:
        return value * 1000.0
    if u in {"g", "gr", "gram"}:
        return value
    return None


def normalize_volume_label(raw: str | None) -> str | None:
    if not raw:
        return None
    text = re.sub(r"\s+", " ", raw.strip().upper().replace(",", "."))
    text = text.replace("GR", "G").replace("GRAM", "G").replace("LT", "L")
    # 12x0.5 → tek şişe hacmi 0.5 L (paket adedi ayrı)
    pack = re.search(r"(\d+)\s*[X×]\s*(\d+[.,]?\d*)\s*(L|LT|ML)?", text, re.I)
    if pack and pack.group(3):
        text = f"{pack.group(2)} {pack.group(3)}"
    m = _VOL_RE.search(text)
    if not m:
        return text or None
    num = m.group("num").rstrip(".")
    try:
        value = float(num)
    except ValueError:
        return text
    unit = (m.group("unit") or "").lower()
    if unit in {"kg"}:
        if value == int(value):
            return f"{int(value)} KG"
        return f"{value} KG"
    if unit in {"g", "gr", "gram"}:
        if value >= 1000:
            kg = value / 1000
            return f"{int(kg)} KG" if kg == int(kg) else f"{kg} KG"
        return f"{int(value)} G" if value == int(value) else f"{value} G"
    if unit in {"l", "lt"}:
        # 0.5 L kalsın (500 ML ile eşdeğer)
        if value == int(value):
            return f"{int(value)} L"
        return f"{value} L"
    if unit in {"ml"}:
        if value >= 1000:
            lit = value / 1000
            return f"{int(lit)} L" if lit == int(lit) else f"{lit} L"
        # 500 ML → 0.5 L (su şişeleri için chip'te görünsün)
        if value > 0 and value < 1000 and abs(value / 1000 - round(value / 1000, 3)) < 1e-9:
            lit = value / 1000
            if lit in {0.25, 0.33, 0.5, 0.75} or (value % 50 == 0):
                return f"{lit} L" if lit != int(lit) else f"{int(lit)} L"
        return f"{int(value)} ML" if value == int(value) else f"{value} ML"
    if unit in {"cl"}:
        return normalize_volume_label(f"{value * 10} ml")
    return text


def volume_canonical_ml(label: str | None) -> float | None:
    """Eşdeğer karşılaştırma için ml/g cinsinden sayı."""
    if not label:
        return None
    text = label.upper().replace(",", ".")
    m = re.search(r"(\d+[.,]?\d*)\s*(KG|G|L|ML|CL|ADET)?", text)
    if not m:
        return None
    try:
        value = float(m.group(1))
    except ValueError:
        return None
    unit = (m.group(2) or "").lower()
    if unit == "adet":
        return None
    return _ml_from_parts(value, unit or "")


def volumes_equivalent(a: str | None, b: str | None, *, tol: float = 1.0) -> bool:
    if not a or not b:
        return False
    na = normalize_volume_label(a)
    nb = normalize_volume_label(b)
    if na and nb and na == nb:
        return True
    ma = volume_canonical_ml(na or a)
    mb = volume_canonical_ml(nb or b)
    if ma is None or mb is None:
        return False
    return abs(ma - mb) <= tol


def volume_sort_key(label: str | None) -> tuple[float, str]:
    if not label:
        return (10**9, "")
    ml = volume_canonical_ml(label)
    if ml is None:
        return (10**9, label)
    return (ml, label or "")


def parse_adet_count(volume: str | None, title: str | None = None) -> int | None:
    blob = f"{volume or ''} {title or ''}"
    m = re.search(r"(\d+)\s*(?:adet|['’]?li|['’]?lı|['’]?lu|['’]?lü)\b", blob, re.I)
    if not m:
        return None
    n = int(m.group(1))
    return n if n > 0 else None


def extract_volume_options(offers: list[dict[str, Any]]) -> list[str]:
    """Benzersiz hacimler; 500 ML ile 0.5 L birleştirilir (0.5 L gösterilir)."""
    by_ml: dict[float, str] = {}
    extras: list[str] = []
    for o in offers:
        lab = normalize_volume_label(o.get("volume"))
        if not lab:
            # başlıktan yakala
            lab = normalize_volume_label(o.get("title") or "")
        if not lab:
            continue
        ml = volume_canonical_ml(lab)
        if ml is None:
            if lab not in extras:
                extras.append(lab)
            continue
        key = round(ml, 1)
        prev = by_ml.get(key)
        # L etiketini tercih et
        if prev is None or ("L" in lab and "ML" in prev):
            by_ml[key] = lab
    labels = list(by_ml.values()) + extras
    return sorted(set(labels), key=volume_sort_key)


def filter_offers_by_volume(
    offers: list[dict[str, Any]], volume: str | None
) -> list[dict[str, Any]]:
    if not volume or volume.lower() in {"all", "hepsi", "*"}:
        return offers
    want = normalize_volume_label(volume) or volume
    out = []
    for o in offers:
        got = normalize_volume_label(o.get("volume"))
        if volumes_equivalent(got, want) or volumes_equivalent(o.get("volume"), want):
            out.append(o)
            continue
        title = o.get("title") or ""
        if volumes_equivalent(normalize_volume_label(title), want):
            out.append(o)
            continue
        # soft: title metninde
        t = title.upper().replace(",", ".").replace("GR", "G")
        compact = (want or "").replace(" ", "").upper()
        if compact and compact in t.replace(" ", ""):
            out.append(o)
            continue
        # 0.5 ↔ 500
        if volume_canonical_ml(want) is not None:
            for m in re.finditer(
                r"(\d+[.,]?\d*)\s*(L|LT|ML|CL)", title, re.I
            ):
                cand = f"{m.group(1)} {m.group(2)}"
                if volumes_equivalent(cand, want):
                    out.append(o)
                    break
    return out
