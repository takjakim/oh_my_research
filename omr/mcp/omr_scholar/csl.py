"""Normalized records -> CSL-JSON array (for Quarto / citeproc).

Pure stdlib. The ``id`` of each CSL item is the stable citation key from
:mod:`omr_scholar.bibtex`, so a Quarto ``[@key]`` matches both the emitted
``library.bib`` and the CSL-JSON.
"""

from __future__ import annotations

from .bibtex import assign_keys

__all__ = ["to_csl_json"]


def _csl_authors(authors) -> list[dict]:
    if not authors:
        return []
    out: list[dict] = []
    if isinstance(authors, str):
        for chunk in authors.split(" and "):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "," in chunk:
                fam, giv = chunk.split(",", 1)
                out.append({"family": fam.strip(), "given": giv.strip()})
            else:
                bits = chunk.split(" ")
                out.append({"family": bits[-1], "given": " ".join(bits[:-1])})
        return out
    for a in authors:
        if isinstance(a, dict):
            fam = a.get("family") or a.get("last")
            giv = a.get("given") or a.get("first")
            if fam or giv:
                item = {}
                if fam:
                    item["family"] = fam
                if giv:
                    item["given"] = giv
                out.append(item)
            elif a.get("name"):
                out.append({"literal": a["name"]})
        else:
            s = str(a).strip()
            if "," in s:
                fam, giv = s.split(",", 1)
                out.append({"family": fam.strip(), "given": giv.strip()})
            else:
                bits = s.split(" ")
                out.append({"family": bits[-1], "given": " ".join(bits[:-1])})
    return out


def _csl_type(rec: dict) -> str:
    return "article-journal" if rec.get("venue") else "document"


def to_csl_json(records: list[dict]) -> list[dict]:
    """Return a CSL-JSON array (list of dicts)."""
    keys = assign_keys(records)
    items: list[dict] = []
    for key, rec in zip(keys, records):
        if not isinstance(rec, dict):
            continue
        item: dict = {"id": key, "type": _csl_type(rec)}
        if rec.get("title"):
            item["title"] = rec["title"]
        authors = _csl_authors(rec.get("authors"))
        if authors:
            item["author"] = authors
        year = rec.get("year")
        if year:
            try:
                item["issued"] = {"date-parts": [[int(str(year)[:4])]]}
            except (ValueError, TypeError):
                pass
        if rec.get("venue"):
            item["container-title"] = rec["venue"]
        if rec.get("doi"):
            item["DOI"] = rec["doi"]
        if rec.get("url"):
            item["URL"] = rec["url"]
        if rec.get("abstract"):
            item["abstract"] = rec["abstract"]
        items.append(item)
    return items
