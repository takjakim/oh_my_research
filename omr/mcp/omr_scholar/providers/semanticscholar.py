"""Semantic Scholar Graph provider -- POST-MVP STUB.

Present for interface completeness but intentionally NOT wired into the
default provider set (see ``providers.DEFAULT_PROVIDERS``). Returns an
empty result set with a post-MVP note rather than raising.
"""

from __future__ import annotations

NAME = "semanticscholar"
POST_MVP = True
_NOTE = (
    "semanticscholar provider is post-MVP: not implemented in the MVP build"
)


def search(query: str, year_from=None, limit: int = 25,
           *, client=None, rate_limiter=None) -> list[dict]:
    """Post-MVP stub: returns [] (degraded, not default)."""
    return []


def resolve_doi(doi: str, *, client=None, rate_limiter=None) -> dict | None:
    """Post-MVP stub."""
    return None


def note() -> str:
    return _NOTE
