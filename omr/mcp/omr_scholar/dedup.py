"""Deterministic record deduplication with an over-merge guard (AC4).

Merge rules:
  * **Exact DOI match** (case/prefix-normalized, both non-empty) -> merge.
  * Otherwise *fuzzy*: normalized titles, publication years within +/-1,
    AND ``token_set_ratio >= 0.92`` -> merge.

Over-merge guard (AC4 negative case): if BOTH records carry a DOI and the
DOIs differ, fuzzy merging is **blocked** even when titles are near-identical.
Two distinct papers with near-identical titles but different DOIs therefore
stay as two entries.

Pure stdlib; deterministic (input order preserved for cluster roots).
"""

from __future__ import annotations

from .normalize import normalize_doi, normalize_title, token_set_ratio

__all__ = ["dedup_records", "FUZZY_THRESHOLD"]

FUZZY_THRESHOLD = 0.92


def _year_of(rec) -> int | None:
    y = rec.get("year")
    if y is None or y == "":
        return None
    try:
        return int(str(y)[:4])
    except (ValueError, TypeError):
        return None


def _merge_into(base: dict, other: dict) -> None:
    """Fill empty fields of ``base`` from ``other`` (base wins ties)."""
    for key, val in other.items():
        if key == "provider":
            continue
        if not base.get(key) and val:
            base[key] = val
    bp = base.get("provider")
    op = other.get("provider")
    provs: list[str] = []
    for p in (bp, op):
        if not p:
            continue
        for piece in str(p).split(","):
            piece = piece.strip()
            if piece and piece not in provs:
                provs.append(piece)
    if provs:
        base["provider"] = ",".join(provs)


def _is_duplicate(a: dict, b: dict) -> tuple[bool, str]:
    """Return (is_dup, reason)."""
    da = normalize_doi(a.get("doi"))
    db = normalize_doi(b.get("doi"))

    if da and db:
        if da == db:
            return True, "exact-doi"
        # Both have DOIs and they differ -> over-merge guard.
        return False, "doi-mismatch-blocked"

    ta = normalize_title(a.get("title"))
    tb = normalize_title(b.get("title"))
    if not ta or not tb:
        return False, "no-title"

    ya = _year_of(a)
    yb = _year_of(b)
    if ya is not None and yb is not None and abs(ya - yb) > 1:
        return False, "year-gap"

    ratio = token_set_ratio(ta, tb)
    if ratio >= FUZZY_THRESHOLD:
        return True, f"fuzzy-title({ratio:.3f})"
    return False, f"below-threshold({ratio:.3f})"


def dedup_records(records: list[dict]) -> dict:
    """Deduplicate ``records``.

    Returns ``{"records": [...], "merge_report": [...], "stats": {...}}``.
    Earlier records are cluster roots (input order is preserved & stable).
    """
    clusters: list[dict] = []
    report: list[dict] = []

    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            continue
        rec = dict(rec)
        placed = False
        for cluster in clusters:
            root = cluster["record"]
            is_dup, reason = _is_duplicate(root, rec)
            if is_dup:
                _merge_into(root, rec)
                cluster["members"].append(idx)
                report.append({
                    "action": "merged",
                    "into_index": cluster["root_index"],
                    "from_index": idx,
                    "reason": reason,
                    "title": rec.get("title"),
                })
                placed = True
                break
            if reason == "doi-mismatch-blocked":
                report.append({
                    "action": "kept-separate",
                    "compared_with_index": cluster["root_index"],
                    "from_index": idx,
                    "reason": reason,
                    "title": rec.get("title"),
                })
        if not placed:
            clusters.append({
                "root_index": idx,
                "record": rec,
                "members": [idx],
            })

    deduped = [c["record"] for c in clusters]
    stats = {
        "input": sum(1 for r in records if isinstance(r, dict)),
        "output": len(deduped),
        "merged": sum(1 for e in report if e["action"] == "merged"),
        "kept_separate_guard": sum(
            1 for e in report if e["action"] == "kept-separate"
        ),
    }
    return {"records": deduped, "merge_report": report, "stats": stats}
