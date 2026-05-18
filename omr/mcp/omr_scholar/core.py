"""Tool logic, independent of the MCP SDK.

Every public function here is import-safe (no network, no third-party
imports at module load). ``search`` / ``resolve_doi`` only touch the
network when a cache miss occurs *and* a real provider is invoked; they
serve pinned offline fixtures from the on-disk cache first (AC4).
"""

from __future__ import annotations

from .bibtex import to_bibtex as _to_bibtex
from .cache import CacheStore, RateLimiterRegistry
from .csl import to_csl_json as _to_csl_json
from .dedup import dedup_records as _dedup_records
from .providers import DEFAULT_PROVIDERS, get_provider
from .version import get_version

__all__ = [
    "version", "search", "resolve_doi", "dedup", "to_bibtex", "to_csl_json",
]


def version() -> dict:
    """EV5 zero-side-effect availability probe."""
    return {"server": "omr-scholar", "version": get_version()}


def _normalize_provider_list(providers) -> list[str]:
    if not providers:
        return list(DEFAULT_PROVIDERS)
    out = []
    for p in providers:
        p = str(p).strip().lower()
        if p and p not in out:
            out.append(p)
    return out or list(DEFAULT_PROVIDERS)


def search(query: str, providers=None, year_from=None, limit: int = 25,
           *, cache: CacheStore | None = None,
           rate_limiter: RateLimiterRegistry | None = None) -> dict:
    """Search across providers with on-disk cache + graceful degradation.

    Returns ``{"records": [...], "providers": [...], "degraded": [...]}``.
    A pinned cache fixture is served offline without any network call.
    """
    prov_names = _normalize_provider_list(providers)
    store = cache if cache is not None else CacheStore()
    limiter = rate_limiter if rate_limiter is not None else RateLimiterRegistry()

    records: list[dict] = []
    used: list[str] = []
    degraded: list[dict] = []

    cache_q = f"{query}|year_from={year_from}|limit={limit}"

    for name in prov_names:
        cached = store.get(name, cache_q)
        if cached is not None:
            records.extend(cached)
            used.append(name)
            continue
        try:
            mod = get_provider(name)
        except KeyError as exc:
            degraded.append({"provider": name, "error": str(exc)})
            continue
        try:
            recs = mod.search(
                query, year_from=year_from, limit=limit,
                rate_limiter=limiter,
            )
        except Exception as exc:  # noqa: BLE001 - degrade, keep others
            degraded.append({"provider": name, "error": repr(exc)})
            continue
        if recs:
            store.set(name, cache_q, recs)
        records.extend(recs)
        used.append(name)

    return {"records": records, "providers": used, "degraded": degraded}


def resolve_doi(doi: str, *, cache: CacheStore | None = None,
                rate_limiter: RateLimiterRegistry | None = None) -> dict | None:
    """Resolve a single DOI via Crossref (cache-first)."""
    store = cache if cache is not None else CacheStore()
    limiter = rate_limiter if rate_limiter is not None else RateLimiterRegistry()
    cache_q = f"doi:{doi}"
    cached = store.get("crossref", cache_q)
    if cached is not None:
        return cached or None
    from .providers import crossref
    rec = crossref.resolve_doi(doi, rate_limiter=limiter)
    if rec:
        store.set("crossref", cache_q, rec)
    return rec


def dedup(records: list[dict]) -> dict:
    """Deduplicate records (exact-DOI + guarded fuzzy)."""
    return _dedup_records(records or [])


def to_bibtex(records: list[dict]) -> str:
    """Serialize records to a BibTeX string with stable citation keys."""
    return _to_bibtex(records or [])


def to_csl_json(records: list[dict]) -> list[dict]:
    """Serialize records to a CSL-JSON array."""
    return _to_csl_json(records or [])
