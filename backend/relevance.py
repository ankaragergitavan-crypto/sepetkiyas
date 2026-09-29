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
    parts = re.findall(r"[a-z0-9]+", fold_tr(query))
    return [p for p in parts if len(p) >= 2 and p not in _STOP]


def _has_token(text: str, token: str) -> bool:
    """'peynir' → 'peynirli' eşleşmesin."""
    return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", text) is not None


def relevance_score(title: str, query: str) -> int:
    """0 = alakasız (elenir)."""
    t = fold_tr(title)
    tokens = query_tokens(query)
    if not tokens:
        return 1

    snack_query = any(
        x in tokens for x in ("kraker", "cips", "cip", "crax", "cizi", "cubuk", "cerez")
    )
    if not snack_query and _SNACK_NOISE.search(t):
        return 0

    score = 0
    for tok in tokens:
        if tok == "kasar":
            if "kasar" not in t:
                return 0
            score += 6
            continue

        if tok == "peynir":
            # Gerçek peynir / kaşar ürünü
            if "kasar" in t or _has_token(t, "peynir") or "peyniri" in t:
                score += 4
                continue
            # Sadece aroma: peynirli kraker vb.
            return 0

        if _has_token(t, tok) or tok in t:
            score += 4
        else:
            return 0

    # Tam ifade
    joined = " ".join(tokens)
    if joined in t:
        score += 5

    return score


def is_relevant(title: str, query: str, *, min_score: int = 4) -> bool:
    return relevance_score(title, query) >= min_score
