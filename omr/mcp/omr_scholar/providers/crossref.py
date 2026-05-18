"""Crossref REST provider (functional, MVP, no API key).

Politeness: ``mailto`` polite-pool param from ``OMR_SCHOLAR_MAILTO`` env
(optional; never required). ``httpx`` is imported lazily inside functions
so importing this module is side-effect-free and dependency-light.
"""

from __future__ import annotations

import os

NAME = "crossref"
_BASE = "https://api.crossref.org"


def _mailto() -> str | None:
    v = os.environ.get("OMR_SCHOLAR_MAILTO", "").strip()
    return v or None


def _abstract_from_jats(jats: str | None) -> str | None:
    if not jats:
        return None
    import re
    return re.sub(r"<[^>]+>", "", jats).strip() or None


def normalize_work(work: dict) -> dict:
    """Map a Crossref ``work`` object to the normalized record schema."""
    title_list = work.get("title") or []
    title = title_list[0] if title_list else (work.get("title") or "")

    authors = []
    for a in work.get("author", []) or []:
        fam = a.get("family", "")
        giv = a.get("given", "")
        if fam or giv:
            authors.append({"family": fam, "given": giv})

    year = None
    for k in ("issued", "published-print", "published-online", "created"):
        dp = (work.get(k) or {}).get("date-parts")
        if dp and dp[0] and dp[0][0]:
            year = dp[0][0]
            break

    container = work.get("container-title") or []
    venue = container[0] if container else None

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "doi": work.get("DOI"),
        "venue": venue,
        "abstract": _abstract_from_jats(work.get("abstract")),
        "provider": NAME,
        "url": work.get("URL") or (
            f"https://doi.org/{work['DOI']}" if work.get("DOI") else None
        ),
    }


def _params(query: str, year_from, limit: int) -> dict:
    params = {"query": query, "rows": str(max(1, min(int(limit), 100)))}
    if year_from:
        params["filter"] = f"from-pub-date:{int(year_from)}-01-01"
    m = _mailto()
    if m:
        params["mailto"] = m
    return params


def search(query: str, year_from=None, limit: int = 25,
           *, client=None, rate_limiter=None) -> list[dict]:
    """Search Crossref works. Network call (httpx, imported lazily)."""
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

    items = (data.get("message") or {}).get("items", []) or []
    return [normalize_work(w) for w in items]


def resolve_doi(doi: str, *, client=None, rate_limiter=None) -> dict | None:
    """Resolve a single DOI to a normalized record via Crossref."""
    import httpx
    from ..normalize import normalize_doi

    nd = normalize_doi(doi)
    if not nd:
        return None
    if rate_limiter is not None:
        rate_limiter.acquire(NAME)

    headers = {"User-Agent": "omr-scholar/0.1 (+https://github.com/omr)"}
    params = {}
    m = _mailto()
    if m:
        params["mailto"] = m
    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=30.0, headers=headers)
    try:
        resp = client.get(f"{_BASE}/works/{nd}", params=params)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
    finally:
        if owns_client:
            client.close()

    work = data.get("message")
    return normalize_work(work) if work else None
