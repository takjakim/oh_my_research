"""Pure-python BibTeX serialization with stable citation keys.

Citation key: ``<firstauthorsurname><YYYY><firstsignificantword>`` all
lowercase, ASCII-folded. Collisions are de-duplicated deterministically
with ``a``/``b``/``c`` ... suffixes in input order.

No third-party dependency is required to *emit* BibTeX (we hand-roll it),
keeping the import surface stdlib-only.
"""

from __future__ import annotations

import re

from .normalize import _strip_accents, first_significant_word

__all__ = ["citation_key", "to_bibtex", "assign_keys"]

_KEY_CLEAN_RE = re.compile(r"[^a-z0-9]+")


def _surname(authors) -> str:
    if not authors:
        return "anon"
    if isinstance(authors, str):
        first = authors.split(",")[0].split(" and ")[0].strip()
    elif isinstance(authors, (list, tuple)) and authors:
        a0 = authors[0]
        if isinstance(a0, dict):
            first = (a0.get("family") or a0.get("last")
                     or a0.get("name") or "").strip()
        else:
            first = str(a0).strip()
    else:
        first = str(authors).strip()
    if not first:
        return "anon"
    # "Surname, Given" or "Given Surname"
    if "," in first:
        surname = first.split(",")[0]
    else:
        surname = first.split(" ")[-1]
    surname = _strip_accents(surname).lower()
    surname = _KEY_CLEAN_RE.sub("", surname)
    return surname or "anon"


def _year_str(rec) -> str:
    y = rec.get("year")
    if y is None or y == "":
        return "0000"
    try:
        return f"{int(str(y)[:4]):04d}"
    except (ValueError, TypeError):
        return "0000"


def citation_key(rec: dict) -> str:
    """Stable base citation key (pre-collision-resolution)."""
    surname = _surname(rec.get("authors"))
    year = _year_str(rec)
    word = first_significant_word(rec.get("title"))
    word = _KEY_CLEAN_RE.sub("", _strip_accents(word).lower()) or "untitled"
    return f"{surname}{year}{word}"


def assign_keys(records: list[dict]) -> list[str]:
    """Return one citation key per record, de-collided in input order."""
    seen: dict[str, int] = {}
    keys: list[str] = []
    for rec in records:
        base = citation_key(rec if isinstance(rec, dict) else {})
        n = seen.get(base, 0)
        seen[base] = n + 1
        if n == 0:
            keys.append(base)
        else:
            # 1 -> 'a', 26 -> 'z', 27 -> 'aa' (bijective base-26)
            suffix = ""
            x = n
            while x > 0:
                x, rem = divmod(x - 1, 26)
                suffix = chr(ord("a") + rem) + suffix
            keys.append(base + suffix)
    return keys


def _bib_escape(value: str) -> str:
    return str(value).replace("{", "(").replace("}", ")").strip()


def _entry_type(rec: dict) -> str:
    if rec.get("venue"):
        return "article"
    return "misc"


def _authors_bib(authors) -> str:
    if not authors:
        return ""
    if isinstance(authors, str):
        return authors
    parts = []
    for a in authors:
        if isinstance(a, dict):
            fam = a.get("family") or a.get("last") or ""
            giv = a.get("given") or a.get("first") or ""
            if fam and giv:
                parts.append(f"{fam}, {giv}")
            else:
                parts.append((a.get("name") or fam or giv or "").strip())
        else:
            parts.append(str(a).strip())
    return " and ".join(p for p in parts if p)


def to_bibtex(records: list[dict]) -> str:
    """Serialize records to a deterministic BibTeX string."""
    keys = assign_keys(records)
    blocks: list[str] = []
    for key, rec in zip(keys, records):
        if not isinstance(rec, dict):
            continue
        etype = _entry_type(rec)
        fields: list[tuple[str, str]] = []
        title = rec.get("title")
        if title:
            fields.append(("title", _bib_escape(title)))
        authors = _authors_bib(rec.get("authors"))
        if authors:
            fields.append(("author", _bib_escape(authors)))
        year = rec.get("year")
        if year:
            fields.append(("year", _bib_escape(str(year)[:4])))
        venue = rec.get("venue")
        if venue:
            fields.append(("journal", _bib_escape(venue)))
        doi = rec.get("doi")
        if doi:
            fields.append(("doi", _bib_escape(doi)))
        url = rec.get("url")
        if url:
            fields.append(("url", _bib_escape(url)))
        abstract = rec.get("abstract")
        if abstract:
            fields.append(("abstract", _bib_escape(abstract)))
        body = ",\n".join(
            f"  {name} = {{{val}}}" for name, val in fields
        )
        blocks.append(f"@{etype}{{{key},\n{body}\n}}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")
