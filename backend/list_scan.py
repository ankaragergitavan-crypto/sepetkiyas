"""Alışveriş listesi: esnek ayraçlar, marka/kg/tür önceliği, benzer öneriler."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from .grouping import sort_offers_by_unit_price, unit_sort_key
from .relevance import (
    fold_tr,
    is_relevant,
    qty_matches_offer,
    relevance_score,
    split_query_tokens,
)
from .robot import annotate_offers
from .typo import correct_query
from .volume import normalize_volume_label

_BULLET = re.compile(
    r"^(?:[\-\*\u2022\u00b7]+\s+|\d{1,3}[\.\)]\s+|\d{1,3}[-:]\s+)"
)
_MAX_ITEMS = 40

# Güçlü ayraçlar: satır, virgül, noktalı virgül, |, madde, / veya +
_STRONG_SPLIT = re.compile(
    r"[\n\r\t,;|•·]+|(?:\s+[+/]\s+)|(?:\s+-\s+)|(?:\s+ve\s+)",
    re.I,
)

# Bilinen market markaları (fold)
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
    "danone",
    "activia",
    "ichim",
    "superfresh",
    "namet",
    "koska",
    "erikli",
    "saka",
    "hayat",
    "pinar",
    "yumurta",  # not a brand — removed below
    "kardelen",
    "munzur",
    "beypazari",
    "damla",
    "sirma",
    "fuse",
    "fuse tea",
    "banvit",
    "erpiliç",
    "erpılıc",
    "erpiliç",
    "lezzet",
    "kalkander",
    "ozdilek",
    "içim",
}
_KNOWN_BRANDS.discard("yumurta")

# Ürün cinsi / sınıf (fold) — yeni ürün başlangıcı
_PRODUCT_NOUNS = {
    "su",
    "sut",
    "yogurt",
    "ayran",
    "kefir",
    "peynir",
    "kasar",
    "lor",
    "labne",
    "tereyag",
    "kaymak",
    "yumurta",
    "sucuk",
    "salam",
    "sosis",
    "pastirma",
    "kiyma",
    "tavuk",
    "dana",
    "kofte",
    "et",
    "balik",
    "ton",
    "ekmek",
    "un",
    "seker",
    "tuz",
    "pirinc",
    "makarna",
    "bulgur",
    "nohut",
    "mercimek",
    "fasulye",
    "yag",
    "zeytin",
    "salca",
    "sirke",
    "bal",
    "recel",
    "pekmez",
    "tahin",
    "helva",
    "cay",
    "kahve",
    "cola",
    "kola",
    "gazoz",
    "soda",
    "maden",
    "icecek",
    "cips",
    "kraker",
    "cikolata",
    "biskuvi",
    "gofret",
    "dondurma",
    "meyve",
    "sebze",
    "domates",
    "salatalik",
    "patates",
    "sogan",
    "sarimsak",
    "muz",
    "elma",
    "portakal",
    "limon",
    "detergent",
    "sapun",
    "sampuan",
    "bez",
    "mendil",
    "cop",
    "poset",
}

# Marka sonrası tür/sınıf (hindi salam, dana sucuk) — ürün ismine yapışır
_TYPE_MODS = {
    "hindi",
    "dana",
    "kuzu",
    "tavuk",
    "kecı",
    "keci",
    "keçi",
    "yagli",
    "yagsiz",
    "yarim",
    "tam",
    "light",
    "organik",
    "gunluk",
    "taze",
    "dilim",
    "dilimli",
    "blok",
    "rendelenmis",
    "cekirdeksiz",
    "cilekli",
    "muzlu",
    "findikli",
    "klasik",
    "ozel",
}

_QTY_TOKEN = re.compile(
    r"^\d+[.,]?\d*(?:kg|g|gr|ml|lt|l|cl|adet|li|lı|lu|lü|lik|l[iı]k)?$",
    re.I,
)


def _fold_tok(t: str) -> str:
    return fold_tr(t)


def _is_brand(tok: str) -> bool:
    return _fold_tok(tok) in _KNOWN_BRANDS


def _is_product_noun(tok: str) -> bool:
    f = _fold_tok(tok)
    return f in _PRODUCT_NOUNS


def _is_type_mod(tok: str) -> bool:
    return _fold_tok(tok) in _TYPE_MODS or _fold_tok(tok) in {
        "hindi",
        "dana",
        "tavuk",
        "kuzu",
        "keci",
    }


def _is_qty(tok: str) -> bool:
    return bool(_QTY_TOKEN.fullmatch(tok.replace(" ", "")))


def _tokenize_phrase(text: str) -> list[str]:
    """Kelimeleri ayır; 0,5 / 500ml / 1.5L tek token kalsın."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    # rakam ile harf arasını ayır: 0.5erikli → 0.5 erikli (ondalığı bozma)
    text = re.sub(
        r"(\d+(?:[.,]\d+)?)([A-Za-zĞÜŞİÖÇğüşıöç])",
        r"\1 \2",
        text,
    )
    text = re.sub(
        r"([A-Za-zĞÜŞİÖÇğüşıöç])(\d+(?:[.,]\d+)?)",
        r"\1 \2",
        text,
    )
    # birleşik miktar: 0,5lik 500ml 1.5L
    text = re.sub(
        r"(\d+)\s*[,.]\s*(\d+)\s*(kg|g|gr|ml|lt|l|cl|lik|l[iı]k)\b",
        lambda m: f"{m.group(1)}.{m.group(2)}{m.group(3)}",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"(\d+)\s*[,.]\s*(\d+)\b",
        lambda m: f"{m.group(1)}.{m.group(2)}",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"(\d+)\s*(kg|g|gr|ml|lt|l|cl)\b",
        lambda m: f"{m.group(1)}{m.group(2)}",
        text,
        flags=re.I,
    )
    return [t for t in text.split(" ") if t]


def _chunk_space_items(text: str) -> list[str]:
    """
    Boşlukla yazılmış listeyi ürünlere böl.
    'pınar hindi salam' tek kalır; 'süt yumurta ekmek' üçe ayrılır.
    """
    toks = _tokenize_phrase(text)
    if not toks:
        return []
    if len(toks) == 1:
        return toks

    items: list[str] = []
    i = 0
    n = len(toks)
    while i < n:
        # Miktar: önceki ürüne ekle veya sonraki ürün adıyla birleştir
        if _is_qty(toks[i]):
            if i + 1 < n and _is_product_noun(toks[i + 1]):
                chunk = [toks[i], toks[i + 1]]
                i += 2
                # "0.5 su 1.5" gibi çift miktar olmasın — sonraki miktar yeni ürün
                items.append(" ".join(chunk))
                continue
            if items:
                items[-1] = f"{items[-1]} {toks[i]}"
                i += 1
                continue
            if i + 1 < n and not _is_qty(toks[i + 1]):
                items.append(f"{toks[i]} {toks[i + 1]}")
                i += 2
                continue
            i += 1
            continue

        if _is_brand(toks[i]):
            chunk = [toks[i]]
            i += 1
            saw_noun = False
            while i < n:
                if _is_brand(toks[i]):
                    break
                if _is_product_noun(toks[i]):
                    chunk.append(toks[i])
                    saw_noun = True
                    i += 1
                    if i < n and _is_qty(toks[i]):
                        chunk.append(toks[i])
                        i += 1
                    break
                if _is_qty(toks[i]):
                    if saw_noun:
                        chunk.append(toks[i])
                        i += 1
                    break
                if _is_type_mod(toks[i]):
                    chunk.append(toks[i])
                    i += 1
                    continue
                # bilinmeyen ara kelime (Lezzet Keyfi vb.)
                if not _is_product_noun(toks[i]) and not _is_brand(toks[i]):
                    chunk.append(toks[i])
                    i += 1
                    continue
                break
            items.append(" ".join(chunk))
            continue

        if _is_product_noun(toks[i]):
            chunk = [toks[i]]
            i += 1
            if i < n and _is_qty(toks[i]):
                chunk.append(toks[i])
                i += 1
            items.append(" ".join(chunk))
            continue

        if _is_type_mod(toks[i]):
            # "hindi salam" markasız
            chunk = [toks[i]]
            i += 1
            while i < n and not _is_brand(toks[i]) and not (_is_product_noun(toks[i]) and len(chunk) > 1):
                if _is_product_noun(toks[i]):
                    chunk.append(toks[i])
                    i += 1
                    break
                if _is_qty(toks[i]):
                    chunk.append(toks[i])
                    i += 1
                    break
                chunk.append(toks[i])
                i += 1
                break
            if i < n and _is_product_noun(toks[i]):
                chunk.append(toks[i])
                i += 1
            if i < n and _is_qty(toks[i]):
                chunk.append(toks[i])
                i += 1
            items.append(" ".join(chunk))
            continue

        # bilinmeyen kelime — tek başına veya sonraki miktarla
        chunk = [toks[i]]
        i += 1
        if i < n and _is_qty(toks[i]):
            chunk.append(toks[i])
            i += 1
        items.append(" ".join(chunk))

    return [x.strip() for x in items if len(x.strip()) >= 2]


def parse_shopping_list(text: str) -> list[str]:
    """
    Alt alta şart değil.
    Virgül / ; / | / • / satır / ' ve ' / boşlukla yan yana yazılan ürünleri ayırır.
    'pınar hindi salam' gibi marka+tür+cins tek kalır.
    """
    raw = (text or "").strip()
    if not raw:
        return []

    # Ondalık virgülü ayraç sanma: 0,5 / 1,5 → 0.5 / 1.5
    raw = re.sub(r"(\d),(\d)", r"\1.\2", raw)

    # Önce güçlü ayraçlar
    pieces: list[str] = []
    for part in _STRONG_SPLIT.split(raw):
        part = part.strip()
        if not part:
            continue
        part = _BULLET.sub("", part).strip()
        if part:
            pieces.append(part)

    items: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        # Parçada birden fazla ürün adı / marka varsa boşlukla böl
        folded_words = [_fold_tok(w) for w in _tokenize_phrase(piece)]
        noun_hits = sum(1 for w in folded_words if w in _PRODUCT_NOUNS)
        brand_hits = sum(1 for w in folded_words if w in _KNOWN_BRANDS)
        if noun_hits + brand_hits >= 2 and " " in piece:
            chunks = _chunk_space_items(piece)
        else:
            chunks = [piece]
        for c in chunks:
            c = re.sub(r"\s+", " ", c).strip()
            if len(c) < 2:
                continue
            key = fold_tr(c)
            if key in seen:
                continue
            seen.add(key)
            items.append(c)
            if len(items) >= _MAX_ITEMS:
                return items
    return items


def _brand_tokens(query: str) -> list[str]:
    hard, _ = split_query_tokens(query)
    out = [t for t in hard if t in _KNOWN_BRANDS]
    # bilinen listede yoksa ama başta marka gibi (4+ harf, ürün cinsi değil)
    if not out and hard:
        first = hard[0]
        if first not in _PRODUCT_NOUNS and first not in _TYPE_MODS and len(first) >= 4:
            out = [first]
    return out


def _type_tokens(query: str) -> list[str]:
    hard, _ = split_query_tokens(query)
    brands = set(_brand_tokens(query))
    return [t for t in hard if t in _TYPE_MODS and t not in brands]


def _product_tokens(query: str) -> tuple[list[str], list[str]]:
    hard, soft = split_query_tokens(query)
    brands = set(_brand_tokens(query))
    types = set(_type_tokens(query))
    return [t for t in hard if t not in brands], soft


def match_quality(offer: dict[str, Any], query: str) -> dict[str, Any]:
    """Marka + tür/sınıf + kg öncelikli aynı ürün mü?"""
    title = offer.get("title") or ""
    brand = fold_tr(offer.get("brand") or "")
    blob = fold_tr(f"{title} {brand} {offer.get('volume') or ''}")
    product_toks, soft = _product_tokens(query)
    brand_toks = _brand_tokens(query)
    type_toks = _type_tokens(query)
    hard, _ = split_query_tokens(query)

    # Ürün kelimeleri (marka hariç — tür dahil)
    covered = all(t in blob for t in product_toks) if product_toks else bool(hard)
    type_ok = True
    if type_toks:
        type_ok = all(t in blob for t in type_toks)

    brand_ok = True
    if brand_toks:
        brand_ok = any(b in blob for b in brand_toks)

    volume_ok = True
    if soft:
        volume_ok = qty_matches_offer(title, offer.get("volume"), soft)

    rel = int(offer.get("relevance") or relevance_score(title, query, volume=offer.get("volume")))
    # Marka + tür tam oturuyorsa skor bonusu
    if brand_ok and type_ok and brand_toks:
        rel += 4
    if type_ok and type_toks:
        rel += 2

    is_exact = covered and brand_ok and type_ok and volume_ok and rel >= 4
    is_similar = (not is_exact) and (
        (covered and rel >= 3)
        or (
            sum(1 for t in product_toks if t in blob) >= max(1, len(product_toks) - 1)
            and rel >= 3
        )
    )

    reasons: list[str] = []
    if brand_toks and not brand_ok:
        reasons.append("marka farklı")
    if type_toks and not type_ok:
        reasons.append("tür/sınıf farklı")
    if soft and not volume_ok:
        reasons.append("kg/adet/hacim farklı")
    if covered and brand_ok and type_ok and volume_ok:
        reasons.append("aynı ürün")
    elif covered:
        reasons.append("benzer ürün")

    return {
        "exact": is_exact,
        "similar": is_similar or is_exact,
        "brandOk": brand_ok,
        "typeOk": type_ok,
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
    Öncelik: marka + tür/sınıf + kg → en ucuz birim fiyat.
    Örn. pınar hindi salam → Pınar hindi salam ara.
    """
    if not offers:
        return {"status": "missing", "best": None, "similars": [], "note": "Sonuç yok"}

    annotated = []
    for o in offers:
        o = dict(o)
        o["volume"] = normalize_volume_label(o.get("volume")) or o.get("volume")
        o["relevance"] = relevance_score(o.get("title") or "", query, volume=o.get("volume"))
        if not is_relevant(o.get("title") or "", query, min_score=2, volume=o.get("volume")):
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
                0 if o["_mq"].get("typeOk", True) else 1,
                0 if o["_mq"]["volumeOk"] else 1,
                -o["_mq"]["relevance"],
                *unit_sort_key(o),
                o.get("title") or "",
            ),
        )

    if exact:
        best = _cheap(exact)[0]
        mq = best["_mq"]
        note_bits = ["Aynı ürün (marka+tür+hacim) · en uygun birim fiyat"]
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
        strong = [
            o
            for o in similar
            if o["_mq"]["covered"] and o["_mq"].get("typeOk", True)
        ]
        if not strong:
            strong = [o for o in similar if o["_mq"]["covered"]]
        if strong:
            best = _cheap(strong)[0]
            mq = best["_mq"]
            why = []
            if not mq["brandOk"]:
                why.append("marka farklı")
            if not mq.get("typeOk", True):
                why.append("tür farklı")
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

        top = _cheap(similar)[:3]
        return {
            "status": "missing",
            "matchType": "similar_only",
            "best": None,
            "similars": [_serialize_offer(x) for x in top],
            "note": "Aynı ürün yok; benzer öneriler aşağıda (istersen ekle)",
            "similarNote": f"Aranan “{query}” için benzer adaylar var",
        }

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
            "Öncelik: marka + tür/sınıf + kg/hacim → en ucuz birim fiyat → market sepeti. "
            "Liste yan yana/virgülle de yazılabilir. Bulunamayanlarda benzer önerilir."
        ),
    }
