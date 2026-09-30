"""Türkçe market aramalarında yazım hatası / yakın eşleme düzeltmesi."""

from __future__ import annotations

import re
from typing import Any

from .relevance import _SOFT_QTY, _STOP, fold_tr

# folded → görünen doğru yazım
_VOCAB: dict[str, str] = {
    # süt / süt ürünleri
    "sut": "süt",
    "sutlac": "sütlaç",
    "ayran": "ayran",
    "kefir": "kefir",
    "yogurt": "yoğurt",
    "peynir": "peynir",
    "kasar": "kaşar",
    "lor": "lor",
    "beyazpeynir": "beyaz peynir",
    "labne": "labne",
    "tereyag": "tereyağ",
    "tereyagi": "tereyağı",
    "kaymak": "kaymak",
    # et / şarküteri
    "yumurta": "yumurta",
    "sucuk": "sucuk",
    "salam": "salam",
    "sosis": "sosis",
    "pastirma": "pastırma",
    "kiyma": "kıyma",
    "tavuk": "tavuk",
    "dana": "dana",
    "kofte": "köfte",
    "et": "et",
    "balik": "balık",
    "ton": "ton",
    # temel gıda
    "ekmek": "ekmek",
    "un": "un",
    "seker": "şeker",
    "tuz": "tuz",
    "pirinc": "pirinç",
    "makarna": "makarna",
    "bulgur": "bulgur",
    "nohut": "nohut",
    "mercimek": "mercimek",
    "fasulye": "fasulye",
    "yag": "yağ",
    "aycicek": "ayçiçek",
    "aycicekyagi": "ayçiçek yağı",
    "zeytinyagi": "zeytinyağı",
    "zeytin": "zeytin",
    "salca": "salça",
    "sirke": "sirke",
    "bal": "bal",
    "recel": "reçel",
    "pekmez": "pekmez",
    "tahin": "tahin",
    "helva": "helva",
    # içecek
    "cay": "çay",
    "kahve": "kahve",
    "caykur": "çaykur",
    "cola": "cola",
    "kola": "kola",
    "gazoz": "gazoz",
    "meyvesuyu": "meyve suyu",
    "maden": "maden",
    "su": "su",
    "soda": "soda",
    "icecek": "içecek",
    # atıştırmalık
    "cips": "cips",
    "kraker": "kraker",
    "cikolata": "çikolata",
    "biskuvi": "bisküvi",
    "gofret": "gofret",
    "dondurma": "dondurma",
    "cerez": "çerez",
    "lokum": "lokum",
    # meyve sebze
    "domates": "domates",
    "salatalik": "salatalık",
    "patates": "patates",
    "sogan": "soğan",
    "biber": "biber",
    "patlican": "patlıcan",
    "kabak": "kabak",
    "havuc": "havuç",
    "elma": "elma",
    "muz": "muz",
    "portakal": "portakal",
    "limon": "limon",
    "uzum": "üzüm",
    "cilek": "çilek",
    "karpuz": "karpuz",
    "kavun": "kavun",
    # temizlik / kişisel
    "deterjan": "deterjan",
    "sabun": "sabun",
    "sampuan": "şampuan",
    "dis": "diş",
    "macun": "macun",
    "dismacunu": "diş macunu",
    "pecete": "peçete",
    "mendil": "mendil",
    "bebek": "bebek",
    "bezi": "bezi",
    "bez": "bez",
    "cop": "çöp",
    "torba": "torba",
    # marka / sık aranan
    "ulker": "Ülker",
    "eti": "Eti",
    "pinar": "Pınar",
    "sek": "Sek",
    "icim": "İçim",
    "sutas": "Sütaş",
    "dost": "Dost",
    "torku": "Torku",
    "nestle": "Nestlé",
    "nutella": "Nutella",
    "algida": "Algida",
    "lipton": "Lipton",
    "coca": "Coca",
    "pepsi": "Pepsi",
    "fanta": "Fanta",
    "sprite": "Sprite",
    "hayat": "Hayat",
    "erikli": "Erikli",
    "sirmasi": "Sırma",
    "sirma": "Sırma",
    "migros": "Migros",
    "bim": "BİM",
    "a101": "A101",
    "carrefour": "Carrefour",
}

# Bilinen yazım hataları / kısaltmalar (folded → folded canonical)
_ALIASES: dict[str, str] = {
    "peinir": "peynir",
    "peynr": "peynir",
    "peyniri": "peynir",
    "peynır": "peynir",
    "penir": "peynir",
    "peinr": "peynir",
    "kasarr": "kasar",
    "qasar": "kasar",
    "kasarı": "kasar",
    "sutt": "sut",
    "sütü": "sut",
    "sutu": "sut",
    "silt": "sut",
    "süıt": "sut",
    "yogurd": "yogurt",
    "yogrt": "yogurt",
    "yoğurt": "yogurt",
    "yumrta": "yumurta",
    "yumurtaa": "yumurta",
    "yumruta": "yumurta",
    "ekmk": "ekmek",
    "ekme": "ekmek",
    "makarnaa": "makarna",
    "makrana": "makarna",
    "pirnic": "pirinc",
    "pirnç": "pirinc",
    "bulgr": "bulgur",
    "sekerr": "seker",
    "şekr": "seker",
    "cayy": "cay",
    "çayi": "cay",
    "kahvee": "kahve",
    "zeytnyagi": "zeytinyagi",
    "zeytinyağ": "zeytinyagi",
    "zeytinyag": "zeytinyagi",
    "aycicekyag": "aycicekyagi",
    "tereyagı": "tereyagi",
    "tereyg": "tereyag",
    "sucukk": "sucuk",
    "pastırm": "pastirma",
    "kiymaa": "kiyma",
    "tavukk": "tavuk",
    "domatesi": "domates",
    "patatesi": "patates",
    "sogann": "sogan",
    "salatalikk": "salatalik",
    "cikolataa": "cikolata",
    "biskivi": "biskuvi",
    "bisküv": "biskuvi",
    "deterjanı": "deterjan",
    "sampua": "sampuan",
    "şampu": "sampuan",
    "dismacun": "dismacunu",
    "dişmacunu": "dismacunu",
    "pecete": "pecete",
    "peçete": "pecete",
    "mercımek": "mercimek",
    "fasulye": "fasulye",
    "nohutt": "nohut",
    "recell": "recel",
    "salcaa": "salca",
    "icecekk": "icecek",
    "meyveusu": "meyvesuyu",
    "meyve suyu": "meyvesuyu",
    "madensuyu": "maden",
    "maden suyu": "maden",
    "beyazpeyniri": "beyazpeynir",
    "beyaz peynir": "beyazpeynir",
    "kasarpeynir": "kasar",
    "kaşarpeynir": "kasar",
    "kaşar peynir": "kasar",
    "kasar peynir": "kasar",
}


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    if abs(len(a) - len(b)) > 2:
        return 99
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


def _max_distance(token: str) -> int:
    n = len(token)
    if n <= 3:
        return 1
    if n <= 5:
        return 1
    if n <= 8:
        return 2
    return 2


def _fuzzy_vocab(token: str) -> str | None:
    """En yakın tekil sözlük eşleşmesi; belirsizse None."""
    max_d = _max_distance(token)
    best: list[tuple[int, str]] = []
    for key in _VOCAB:
        # çok kısa kelimeleri (et, su, un) yanlış düzeltme
        if len(key) <= 2 and token != key:
            continue
        if abs(len(key) - len(token)) > max_d:
            continue
        d = _levenshtein(token, key)
        if d == 0:
            return key
        if d <= max_d:
            best.append((d, key))
    if not best:
        return None
    best.sort(key=lambda x: (x[0], abs(len(x[1]) - len(token)), len(x[1])))
    # Aynı mesafede birden fazla aday → düzeltme
    top_d = best[0][0]
    same = [k for d, k in best if d == top_d]
    if len(same) != 1:
        return None
    # 3 harfli tokenlerde sadece d=1 ve hedef ≥3
    if len(token) <= 3 and top_d > 1:
        return None
    return same[0]


def resolve_token(folded: str) -> tuple[str, bool]:
    """
    folded token → (gösterim/aranacak kelime, değişti mi).
    Dönüş değeri Türkçe karakterli doğru yazım olabilir.
    """
    if len(folded) < 2 or folded in _STOP or _SOFT_QTY.fullmatch(folded):
        return folded, False

    # Önce alias
    via = _ALIASES.get(folded)
    if via:
        display = _VOCAB.get(via, via)
        return display, fold_tr(display) != folded or display != folded

    if folded in _VOCAB:
        display = _VOCAB[folded]
        # "sut" → "süt" gibi görsel düzeltme; arama için faydalı
        return display, fold_tr(display) != folded or display != folded

    fuzzy = _fuzzy_vocab(folded)
    if fuzzy and fuzzy != folded:
        return _VOCAB[fuzzy], True

    return folded, False


_TOKEN_RE = re.compile(
    r"[A-Za-z0-9ĞÜŞİÖÇğüşıöç]+|[^A-Za-z0-9ĞÜŞİÖÇğüşıöç]+"
)


def correct_query(query: str) -> dict[str, Any]:
    """
    Yazım hatalarını düzeltir.
    Döner: originalQuery, query (aranacak), corrected, corrections, note
    """
    original = (query or "").strip()
    if not original:
        return {
            "originalQuery": "",
            "query": "",
            "corrected": False,
            "corrections": [],
            "note": None,
        }

    # Hacim / "0,5'lik" / yarım litre düzeltmeleri
    pre = original
    pre = re.sub(r"\byar[iı]m\s*(litre|lt|l\.?|şişe)?\b", "0.5 L", pre, flags=re.I)
    pre = re.sub(
        r"\b(\d+)\s*[,.]\s*(\d+)\s*[\'’]?l[iı]k\b",
        r"\1.\2 L",
        pre,
        flags=re.I,
    )
    pre = re.sub(
        r"\b(\d+)\s*[,.]\s*(\d+)\s*m\b",
        r"\1.\2 L",
        pre,
        flags=re.I,
    )
    # 0,5 su / 0.5su → 0.5 L su
    pre = re.sub(
        r"\b(\d+)\s*[,.]\s*(\d+)\s*(?=su|süt|sut|ayran|soda|maden|içecek|icecek)\b",
        r"\1.\2 L ",
        pre,
        flags=re.I,
    )
    pre = re.sub(
        r"\b(\d+)\s*[,.]\s*(\d+)\s*(l|lt|litre)\b",
        r"\1.\2 L",
        pre,
        flags=re.I,
    )
    pre = re.sub(
        r"\b(\d+)\s*[,.]\s*(\d+)\s*(ml)\b",
        r"\1.\2 ml",
        pre,
        flags=re.I,
    )
    # yalnız "0,5" / "0.5" (birim yok) → 0.5 L
    pre = re.sub(
        r"(?<![A-Za-z0-9])(\d+)\s*[,.]\s*(\d+)(?!\s*(?:kg|g|gr|ml|l|lt|litre|cl|%))",
        r"\1.\2 L",
        pre,
        flags=re.I,
    )
    pre = re.sub(r"\b(\d+)\s*m\b(?!\w)", r"\1 L", pre, flags=re.I)
    pre = re.sub(r"\s+", " ", pre).strip()
    working = pre
    volume_fix = fold_tr(pre) != fold_tr(original)

    parts = _TOKEN_RE.findall(working)
    out: list[str] = []
    corrections: list[dict[str, str]] = []
    if volume_fix:
        corrections.append({"from": original, "to": pre})

    for part in parts:
        if not re.fullmatch(r"[A-Za-z0-9ĞÜŞİÖÇğüşıöç]+", part):
            out.append(part)
            continue
        folded = fold_tr(part)
        if len(folded) < 2 or folded in _STOP or _SOFT_QTY.fullmatch(folded):
            out.append(part)
            continue
        fixed, changed = resolve_token(folded)
        if changed and fold_tr(fixed) != folded:
            out.append(fixed)
            corrections.append({"from": part, "to": fixed})
        elif changed and fold_tr(fixed) == folded and fixed != part:
            # sadece Türkçe karakter düzeltmesi (sut→süt) — arama için kullan
            out.append(fixed)
            if part.casefold() != fixed.casefold():
                corrections.append({"from": part, "to": fixed})
        else:
            out.append(part)

    corrected = re.sub(r"\s+", " ", "".join(out)).strip()
    # "beyazpeynir" gibi birleşik → boşluklu
    if fold_tr(corrected) in _VOCAB:
        corrected = _VOCAB[fold_tr(corrected)]

    changed_fold = bool(corrections) and fold_tr(corrected) != fold_tr(original)
    show = bool(corrections) and corrected != original

    note = None
    if show:
        bits = [f"“{c['from']}” → “{c['to']}”" for c in corrections[:4]]
        note = "Yazım düzeltildi: " + ", ".join(bits)

    return {
        "originalQuery": original,
        "query": corrected if show else original,
        "corrected": show,
        "corrections": corrections,
        "note": note,
        "foldChanged": changed_fold,
    }
