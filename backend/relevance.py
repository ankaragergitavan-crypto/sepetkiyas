from __future__ import annotations

import re

_SNACK_NOISE = re.compile(
    r"(kraker|cracker|crax|cizi|cizivic|cips|\bcip\b|cubuk|cerez|"
    r"cheetos|doritos|lays|ruffles|gong|patla|"
    r"aromali|cikolata|biskuvi|gofret|wafer|"
    r"peynirli\s*(kraker|cubuk|cip|cerez|sogan|biftek)|"
    r"kus\s*mamasi|kedi\s*mama|kopek\s*mama)",
    re.I,
)

_STOP = {"ve", "ile", "icin", "bir", "en", "gr", "g", "kg", "ml", "lt", "l"}

# "1l", "500g", "30", "30lu" — ürün adını elemez; hacim/adet tercihi
_SOFT_QTY = re.compile(
    r"^\d+[.,]?\d*(kg|g|gr|ml|lt|l|cl|adet|li|lı|lu|lü)?$",
    re.I,
)


def fold_tr(text: str) -> str:
    table = str.maketrans(
        {
            "ı": "i",
            "İ": "i",
            "I": "i",
            "ş": "s",
            "Ş": "s",
            "ğ": "g",
            "Ğ": "g",
            "ü": "u",
            "Ü": "u",
            "ö": "o",
            "Ö": "o",
            "ç": "c",
            "Ç": "c",
        }
    )
    return text.translate(table).casefold()


def query_tokens(query: str) -> list[str]:
    """Sert ürün tokenları (hacim/adet hariç)."""
    hard, _soft = split_query_tokens(query)
    return hard


def split_query_tokens(query: str) -> tuple[list[str], list[str]]:
    parts = re.findall(r"[a-z0-9]+", fold_tr(query))
    hard: list[str] = []
    soft: list[str] = []
    for p in parts:
        if len(p) < 2 or p in _STOP:
            continue
        if _SOFT_QTY.fullmatch(p):
            soft.append(p)
            continue
        hard.append(p)
    return hard, soft


def _has_token(text: str, token: str) -> bool:
    """'peynir' → 'peynirli' eşleşmesin."""
    return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", text) is not None


def _qty_patterns(tok: str) -> list[str]:
    """'1l' / '500g' / '30' için esnek başlık/hacim kalıpları."""
    m = re.fullmatch(r"(\d+[.,]?\d*)(kg|g|gr|ml|lt|l|cl|adet|li|lı|lu|lü)?", tok)
    if not m:
        return [re.escape(tok)]
    num = m.group(1).replace(",", ".")
    try:
        n = float(num)
    except ValueError:
        return [re.escape(tok)]
    unit = (m.group(2) or "").lower()
    n_int = int(n) if n == int(n) else None
    n_str = str(n_int) if n_int is not None else num
    pats: list[str] = []
    if unit in {"l", "lt"}:
        pats += (
            [rf"\b{n_str}\s*(l|lt)\b", rf"\b{int(n * 1000)}\s*ml\b"]
            if n_int is not None
            else [rf"\b{re.escape(num)}\s*(l|lt)\b"]
        )
        if n_int == 1:
            pats.append(r"\b1000\s*ml\b")
    elif unit in {"ml"}:
        pats.append(rf"\b{n_str}\s*ml\b")
        if n_int and n_int >= 1000 and n_int % 1000 == 0:
            pats.append(rf"\b{n_int // 1000}\s*(l|lt)\b")
    elif unit in {"kg"}:
        pats += [rf"\b{n_str}\s*kg\b", rf"\b{int(n * 1000)}\s*g\b"] if n_int else [
            rf"\b{re.escape(num)}\s*kg\b"
        ]
    elif unit in {"g", "gr"}:
        pats.append(rf"\b{n_str}\s*g(r|ram)?\b")
        if n_int and n_int >= 1000 and n_int % 1000 == 0:
            pats.append(rf"\b{n_int // 1000}\s*kg\b")
    elif unit in {"adet", "li", "lı", "lu", "lü"} or unit == "":
        pats.append(rf"\b{n_str}\s*(adet|li|lı|lu|lü)?\b")
        pats.append(rf"\b{n_str}'?li\b")
    else:
        pats.append(re.escape(tok))
    return pats


def qty_matches_offer(title: str, volume: str | None, soft_tokens: list[str]) -> bool:
    if not soft_tokens:
        return True
    blob = fold_tr(f"{title} {volume or ''}")
    for tok in soft_tokens:
        for pat in _qty_patterns(tok):
            if re.search(pat, blob, re.I):
                return True
    return False


def relevance_score(
    title: str,
    query: str,
    *,
    volume: str | None = None,
) -> int:
    """0 = alakasız (elenir). Hacim/adet tokenları ürünü elemez; eşleşirse puan ekler."""
    t = fold_tr(title)
    hard, soft = split_query_tokens(query)
    if not hard and not soft:
        return 1

    snack_query = any(
        x in hard for x in ("kraker", "cips", "cip", "crax", "cizi", "cubuk", "cerez")
    )
    if not snack_query and _SNACK_NOISE.search(t):
        return 0

    score = 0
    tokens = hard or soft  # yalnızca "1l" gibi sorguda soft üzerinden ilerle
    use_hard = bool(hard)
    for tok in hard if use_hard else soft:
        if tok == "kasar":
            if "kasar" not in t:
                return 0
            score += 6
            continue

        if tok == "peynir":
            if "kasar" in t or _has_token(t, "peynir") or "peyniri" in t:
                score += 4
                continue
            return 0

        if _has_token(t, tok) or tok in t:
            score += 4
        else:
            if use_hard:
                return 0

    if soft and qty_matches_offer(title, volume, soft):
        score += 5
    elif soft and use_hard:
        # Hacim yazılmış ama ürün uyuyor → eleme; hafif düşür
        score = max(score, 4)

    joined = " ".join(hard)
    if joined and joined in t:
        score += 5

    return score


def is_relevant(
    title: str,
    query: str,
    *,
    min_score: int = 4,
    volume: str | None = None,
) -> bool:
    return relevance_score(title, query, volume=volume) >= min_score
