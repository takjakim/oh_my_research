"""OpenAlex provider (functional, MVP, no API key).

Reconstructs abstracts from OpenAlex's inverted index. ``mailto`` polite
pool from ``OMR_SCHOLAR_MAILTO`` (optional). ``httpx`` imported lazily.
"""

from __future__ import annotations

import os

NAME = "openalex"
_BASE = "https://api.openalex.org"


def _mailto() -> str | None:
    v = os.environ.get("OMR_SCHOLAR_MAILTO", "").strip()
    return v or None


def _abstract_from_inverted(idx: dict | None) -> str | None:
    if not idx:
        return None
    positions: list[tuple[int, str]] = []
    for word, locs in idx.items():
        for loc in locs:
            positions.append((loc, word))
    if not positions:
        return None
    positions.sort(key=lambda t: t[0])
    return " ".join(w for _, w in positions).strip() or None


def _short_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    d = doi
    for p in ("https://doi.org/", "http://doi.org/"):
        if d.startswith(p):
            d = d[len(p):]
    return d


def normalize_work(work: dict) -> dict:
    """Map an OpenAlex ``work`` object to the normalized record schema."""
    authors = []
    for au in work.get("authorships", []) or []:
        name = (au.get("author") or {}).get("display_name") or ""
        if name:
            authors.append({"name": name})

    venue = None
    pl = work.get("primary_location") or {}
    src = pl.get("source") or {}
    if src.get("display_name"):
        venue = src["display_name"]
    elif (work.get("host_venue") or {}).get("display_name"):
        venue = work["host_venue"]["display_name"]

    return {
        "title": work.get("title") or work.get("display_name") or "",
        "authors": authors,
        "year": work.get("publication_year"),
        "doi": _short_doi(work.get("doi")),
        "venue": venue,
        "abstract": _abstract_from_inverted(
            work.get("abstract_inverted_index")
        ),
        "provider": NAME,
        "url": work.get("doi") or (work.get("id")),
    }


def _params(query: str, year_from, limit: int) -> dict:
    params = {
        "search": query,
        "per-page": str(max(1, min(int(limit), 100))),
    }
    if year_from:
        params["filter"] = f"from_publication_date:{int(year_from)}-01-01"
    m = _mailto()
    if m:
        params["mailto"] = m
    return params


def search(query: str, year_from=None, limit: int = 25,
           *, client=None, rate_limiter=None) -> list[dict]:
    """Search OpenAlex works. Network call (httpx, imported lazily)."""
    import httpx

    if rate_limiter is not None:
        rate_limiter.acquire(NAME)

    params = _params(query, year_from, limit)
    headers = {"User-Agent": "omr-scholar/0.1 (+https://github.com/omr)"}
    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=30.0, headers=headers)
    try:
        resp = client.get(f"{_BASE}/works", params=params)
        resp.raise_for_status()
        data = resp.json()
    finally:
        if owns_client:
            client.close()

    return [normalize_work(w) for w in data.get("results", []) or []]


def resolve_doi(doi: str, *, client=None, rate_limiter=None) -> dict | None:
    """Resolve a DOI via OpenAlex (secondary; Crossref is primary)."""
    import httpx
    from ..normalize import normalize_doi

    nd = normalize_doi(doi)
    if not nd:
        return None
    if rate_limiter is not None:
        rate_limiter.acquire(NAME)

    headers = {"User-Agent": "omr-scholar/0.1 (+https://github.com/omr)"}
    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=30.0, headers=headers)
    try:
        resp = client.get(f"{_BASE}/works/https://doi.org/{nd}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
    finally:
        if owns_client:
            client.close()
    return normalize_work(data) if data else None
