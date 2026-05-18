"""Pure-stdlib text normalization + token-set ratio.

No external fuzzy libraries. The token-set ratio is a deterministic
Sorensen-Dice-style overlap over token *sets* combined with a contained
"sorted intersection" comparison, mirroring the spirit of RapidFuzz's
``token_set_ratio`` but implemented purely in Python.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = [
    "normalize_title",
    "normalize_doi",
    "tokenize",
    "token_set_ratio",
    "first_significant_word",
]

_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+", flags=re.UNICODE)

# Common title stop-words excluded only when picking a citation-key word.
_STOPWORDS = {
    "a", "an", "the", "of", "on", "in", "and", "or", "for", "to", "with",
    "from", "by", "at", "as", "is", "are", "be", "this", "that", "into",
}


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def normalize_title(title: str | None) -> str:
    """Lowercase, strip accents, drop punctuation, collapse whitespace."""
    if not title:
        return ""
    text = _strip_accents(str(title)).lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text)
    return text.strip()


def normalize_doi(doi: str | None) -> str:
    """Normalize a DOI for exact comparison.

    Strips any ``https://doi.org/`` / ``doi:`` prefix and lowercases.
    Returns ``""`` for falsy / non-DOI input.
    """
    if not doi:
        return ""
    d = str(doi).strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/",
                   "http://dx.doi.org/", "doi.org/", "doi:"):
        if d.startswith(prefix):
            d = d[len(prefix):]
            break
    return d.strip()


def tokenize(text: str | None) -> list[str]:
    """Token list from a normalized form of ``text``."""
    norm = normalize_title(text)
    if not norm:
        return []
    return norm.split(" ")


def token_set_ratio(a: str | None, b: str | None) -> float:
    """Deterministic token-set similarity in ``[0.0, 1.0]``.

    Algorithm (pure python, order-independent):
      * tokenize both strings into *sets*
      * intersection = sorted common tokens
      * remainders   = tokens unique to each side
      * build three comparison strings:
          t0 = intersection
          t1 = intersection + a-only
          t2 = intersection + b-only
      * score each pair with a Sorensen-Dice token-set coefficient and
        return the maximum (matching the token_set_ratio intuition that a
        full subset match should score very high).
    """
    sa = set(tokenize(a))
    sb = set(tokenize(b))
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0

    inter = sa & sb
    a_only = sa - sb
    b_only = sb - sa

    t0 = inter
    t1 = inter | a_only
    t2 = inter | b_only

    def dice(x: set[str], y: set[str]) -> float:
        if not x and not y:
            return 1.0
        denom = len(x) + len(y)
        if denom == 0:
            return 0.0
        return (2.0 * len(x & y)) / denom

    return max(dice(t0, t1), dice(t0, t2), dice(t1, t2), dice(sa, sb))


def first_significant_word(title: str | None) -> str:
    """First non-stopword token of a title (for citation keys)."""
    for tok in tokenize(title):
        if tok and tok not in _STOPWORDS:
            return tok
    toks = tokenize(title)
    return toks[0] if toks else "untitled"
