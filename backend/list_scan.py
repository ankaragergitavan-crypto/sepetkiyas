"""Alışveriş listesi: satır satır canlı tarama, marka/kg önceliği, benzer öneriler."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from .grouping import sort_offers_by_unit_price, unit_sort_key
from .relevance import (
    fold_tr,
    is_relevant,
    qty_matches_offer,
    query_tokens,
    relevance_score,
    split_query_tokens,
)
from .robot import annotate_offers
from .typo import correct_query
from .volume import normalize_volume_label

_BULLET = re.compile(r"^(?:[\-\*\u2022\u00b7]+|\d{1,3}[\.\)\-:]+)\s*")
_MAX_LINES = 40

# Sorguda marka gibi duran bilinenler (fold)
_KNOWN_BRANDS = {
    "pinar",
    "sek",
    "icim",
    "sutas",
    "dost",
    "ulker",
    "eti",
    "torku",
    "nestle",
    "nutella",
    "algida",
    "lipton",
    "caykur",
    "migros",
    "birlesik",
    "tarabya",
    "binvezir",
    "gures",
    "yorsan",
    "sutas",
}


def parse_shopping_list(text: str) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        line = _BULLET.sub("", line).strip()
        line = re.sub(r"\s+", " ", line)
        if len(line) < 2:
            continue
        key = fold_tr(line)
        if key in seen:
            continue
        seen.add(key)
        lines.append(line)
        if len(lines) >= _MAX_LINES:
            break
    return lines


def _brand_tokens(query: str) -> list[str]:
    hard, _ = split_query_tokens(query)
    return [t for t in hard if t in _KNOWN_BRANDS or len(t) >= 5 and t.endswith(("as", "an", "er"))]


def _product_tokens(query: str) -> tuple[list[str], list[str]]:
    hard, soft = split_query_tokens(query)
    brands = set(_brand_tokens(query))
    return [t for t in hard if t not in brands], soft


def match_quality(offer: dict[str, Any], query: str) -> dict[str, Any]:
    """Aynı ürün mü, marka/kg uyumu, skor."""
    title = offer.get("title") or ""
    brand = fold_tr(offer.get("brand") or "")
    blob = fold_tr(f"{title} {brand} {offer.get('volume') or ''}")
    product_toks, soft = _product_tokens(query)
    brand_toks = _brand_tokens(query)
    hard, _ = split_query_tokens(query)

    covered = all(t in blob for t in product_toks) if product_toks else bool(hard)
    brand_ok = True
    if brand_toks:
        brand_ok = any(b in blob for b in brand_toks)
    volume_ok = True
    if soft:
        volume_ok = qty_matches_offer(title, offer.get("volume"), soft)

    rel = int(offer.get("relevance") or relevance_score(title, query, volume=offer.get("volume")))

    # exact: ürün kelimeleri + (marka varsa marka) + (kg/adet varsa hacim)
    is_exact = covered and brand_ok and volume_ok and rel >= 4
    # strong similar: ürün kelimeleri var ama marka veya kg farklı
    is_similar = (not is_exact) and (
        (covered and rel >= 3)
        or (sum(1 for t in product_toks if t in blob) >= max(1, len(product_toks) - 1) and rel >= 3)
    )

    reasons: list[str] = []
    if brand_toks and not brand_ok:
        reasons.append("marka farklı")
    if soft and not volume_ok:
        reasons.append("kg/adet farklı")
    if covered and brand_ok and volume_ok:
        reasons.append("aynı ürün")
    elif covered:
        reasons.append("benzer ürün")

    return {
        "exact": is_exact,
        "similar": is_similar or is_exact,
        "brandOk": brand_ok,
        "volumeOk": volume_ok,
        "covered": covered,
        "relevance": rel,
        "reasons": reasons,
    }


def _serialize_offer(o: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": o.get("id"),
        "title": o.get("title"),
        "brand": o.get("brand"),
        "price": o.get("price"),
        "volume": o.get("volume"),
        "marketId": o.get("marketId"),
        "marketLabel": o.get("marketLabel"),
        "marketColor": o.get("marketColor"),
        "imageUrl": o.get("imageUrl"),
        "unitPriceEstimate": o.get("unitPriceEstimate"),
        "unitPriceLabel": o.get("unitPriceLabel"),
        "relevance": o.get("relevance"),
        "depotName": o.get("depotName"),
        "distanceKm": o.get("distanceKm"),
    }


def classify_and_pick(offers: list[dict[str, Any]], query: str) -> dict[str, Any]:
    """
    Öncelik: aynı ürün (marka+kg) → en ucuz birim fiyat.
    Yoksa benzer adaylar (istenirse eklenebilir).
    """
    if not offers:
        return {"status": "missing", "best": None, "similars": [], "note": "Sonuç yok"}

    annotated = []
    for o in offers:
        o = dict(o)
        o["volume"] = normalize_volume_label(o.get("volume")) or o.get("volume")
        o["relevance"] = relevance_score(o.get("title") or "", query, volume=o.get("volume"))
        if not is_relevant(o.get("title") or "", query, min_score=3, volume=o.get("volume")):
            # çok alakasız ele
            if o["relevance"] < 2:
                continue
        qinfo = match_quality(o, query)
        o["_mq"] = qinfo
        annotated.append(o)

    if not annotated:
        return {
            "status": "missing",
            "best": None,
            "similars": [],
            "note": "Canlı fiyatta uygun ürün bulunamadı",
        }

    annotate_offers(annotated)

    exact = [o for o in annotated if o["_mq"]["exact"]]
    similar = [o for o in annotated if o["_mq"]["similar"] and not o["_mq"]["exact"]]

    def _cheap(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            items,
            key=lambda o: (
                0 if o["_mq"]["brandOk"] else 1,
                0 if o["_mq"]["volumeOk"] else 1,
                -o["_mq"]["relevance"],
                *unit_sort_key(o),
                o.get("title") or "",
            ),
        )

    if exact:
        best = _cheap(exact)[0]
        mq = best["_mq"]
        note_bits = ["Aynı ürün · en uygun birim fiyat"]
        if mq.get("reasons"):
            note_bits.append(", ".join(mq["reasons"]))
        return {
            "status": "found",
            "matchType": "exact",
            "best": best,
            "similars": [_serialize_offer(x) for x in _cheap(exact + similar)[1:4]],
            "note": " · ".join(note_bits),
            "similarNote": None,
        }

    if similar:
        # Sepete otomatik ekleme: sadece güçlü benzer (covered)
        strong = [o for o in similar if o["_mq"]["covered"]]
        if strong:
            best = _cheap(strong)[0]
            mq = best["_mq"]
            why = []
            if not mq["brandOk"]:
                why.append("marka farklı")
            if not mq["volumeOk"]:
                why.append("kg/adet farklı")
            similar_note = (
                f"Benzeri: “{best.get('title')}”"
                + (f" ({', '.join(why)})" if why else "")
                + f" · aranan “{query}”"
            )
            return {
                "status": "found",
                "matchType": "similar",
                "best": best,
                "similars": [_serialize_offer(x) for x in _cheap(similar)[1:4]],
                "note": "Benzer ürün · en uygun fiyat (aynı ürün net bulunamadı)",
                "similarNote": similar_note,
            }

        # Zayıf benzer → bulunamayanlar + öneriler
        top = _cheap(similar)[:3]
        return {
            "status": "missing",
            "matchType": "similar_only",
            "best": None,
            "similars": [_serialize_offer(x) for x in top],
            "note": "Aynı ürün yok; benzer öneriler aşağıda (istersen ekle)",
            "similarNote": f"Aranan “{query}” için benzer adaylar var",
        }

    # Alakasız yığın — en ucuz 3'ü benzer olarak sun
    top = sort_offers_by_unit_price(annotated)[:3]
    return {
        "status": "missing",
        "matchType": "none",
        "best": None,
        "similars": [_serialize_offer(x) for x in top],
        "note": "Aynı ürün bulunamadı; yakın sonuçlar önerildi",
        "similarNote": f"Aranan “{query}”",
    }


async def scan_list_items(
    lines: list[str],
    *,
    search_one,
    concurrency: int = 3,
) -> dict[str, Any]:
    sem = asyncio.Semaphore(concurrency)
    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    async def one(line: str) -> None:
        typo = correct_query(line)
        q = typo["query"] or line
        async with sem:
            try:
                payload = await search_one(q)
            except Exception as exc:  # noqa: BLE001
                unmatched.append(
                    {
                        "listItem": line,
                        "query": q,
                        "reason": f"Arama hatası: {exc}",
                        "similars": [],
                    }
                )
                return

        offers = payload.get("offers") or []
        result = classify_and_pick(offers, q)

        if result["status"] == "found" and result.get("best"):
            best = result["best"]
            matched.append(
                {
                    "listItem": line,
                    "query": q,
                    "originalQuery": typo.get("originalQuery") or line,
                    "typoCorrected": typo.get("corrected"),
                    "typoNote": typo.get("note"),
                    "matchType": result.get("matchType") or "exact",
                    "similarNote": result.get("similarNote"),
                    "note": result.get("note"),
                    "offer": _serialize_offer(best),
                    "similars": result.get("similars") or [],
                }
            )
        else:
            unmatched.append(
                {
                    "listItem": line,
                    "query": q,
                    "typoNote": typo.get("note"),
                    "reason": result.get("note") or "Bulunamadı",
                    "similarNote": result.get("similarNote"),
                    "similars": result.get("similars") or [],
                }
            )

    await asyncio.gather(*(one(line) for line in lines))

    order = {fold_tr(x): i for i, x in enumerate(lines)}
    matched.sort(key=lambda m: order.get(fold_tr(m["listItem"]), 999))
    unmatched.sort(key=lambda m: order.get(fold_tr(m["listItem"]), 999))

    by_market: dict[str, int] = {}
    for m in matched:
        mid = (m.get("offer") or {}).get("marketId")
        if mid:
            by_market[mid] = by_market.get(mid, 0) + 1

    return {
        "itemCount": len(lines),
        "matchedCount": len(matched),
        "unmatchedCount": len(unmatched),
        "matched": matched,
        "unmatched": unmatched,
        "byMarket": by_market,
        "note": (
            "Öncelik: aynı ürün (marka + kg/adet) ve en ucuz birim fiyat → ilgili market sepeti. "
            "Bulunamayanlar ayrı; yanında benzer, istersen ekle."
        ),
    }
