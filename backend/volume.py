from __future__ import annotations

import re
from typing import Any


_VOL_RE = re.compile(
    r"(?P<num>\d+[.,]?\d*)\s*(?P<unit>kg|g|gr|gram|ml|lt|l|cl|adet|lı|li|lu|lü)?",
    re.I,
)


def normalize_volume_label(raw: str | None) -> str | None:
    if not raw:
        return None
    text = re.sub(r"\s+", " ", raw.strip().upper().replace(",", "."))
    text = text.replace("GR", "G").replace("GRAM", "G").replace("LT", "L")
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
        return f"{int(value)} L" if value == int(value) else f"{value} L"
    if unit in {"ml"}:
        if value >= 1000:
            lit = value / 1000
            return f"{int(lit)} L" if lit == int(lit) else f"{lit} L"
        return f"{int(value)} ML" if value == int(value) else f"{value} ML"
    return text


def volume_sort_key(label: str | None) -> tuple[float, str]:
    if not label:
        return (10**9, "")
    m = re.match(r"(\d+[.,]?\d*)\s*(KG|G|L|ML|ADET)?", label.upper().replace(",", "."))
    if not m:
        return (10**9, label)
    n = float(m.group(1))
    unit = m.group(2) or ""
    if unit == "ADET":
        # Adet kütle değil — birim fiyat hesabına sokma
        return (10**9, label)
    grams = n
    if unit == "KG":
        grams = n * 1000
    elif unit == "L":
        grams = n * 1000
    elif unit == "ML":
        grams = n
    elif unit == "":
        return (10**9, label)
    return (grams, label)


def parse_adet_count(volume: str | None, title: str | None = None) -> int | None:
    blob = f"{volume or ''} {title or ''}"
    m = re.search(r"(\d+)\s*(?:adet|['’]?li|['’]?lı|['’]?lu|['’]?lü)\b", blob, re.I)
    if not m:
        return None
    n = int(m.group(1))
    return n if n > 0 else None


def extract_volume_options(offers: list[dict[str, Any]]) -> list[str]:
    labels = {
        normalize_volume_label(o.get("volume"))
        for o in offers
        if o.get("volume")
    }
    labels.discard(None)
    return sorted(labels, key=volume_sort_key)  # type: ignore[arg-type]


def filter_offers_by_volume(
    offers: list[dict[str, Any]], volume: str | None
) -> list[dict[str, Any]]:
    if not volume or volume.lower() in {"all", "hepsi", "*"}:
        return offers
    want = normalize_volume_label(volume)
    if not want:
        return offers
    out = []
    for o in offers:
        got = normalize_volume_label(o.get("volume"))
        if got == want:
            out.append(o)
            continue
        # soft match: title contains 500 G / 1 KG etc.
        title = (o.get("title") or "").upper().replace("GR", "G")
        compact = want.replace(" ", "")
        if compact in title.replace(" ", "") or want in title:
            out.append(o)
    return out
