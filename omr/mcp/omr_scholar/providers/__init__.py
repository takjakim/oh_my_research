"""Literature providers.

MVP (functional, default): ``crossref``, ``openalex``.
Post-MVP (stubs, NOT wired into default): ``europepmc``, ``semanticscholar``.

All provider modules import ``httpx`` lazily *inside* their functions so
that importing this package performs no network setup and works even when
``httpx`` is absent (e.g. the stdlib-only ``scholar.version`` path).
"""

DEFAULT_PROVIDERS = ["crossref", "openalex"]
ALL_PROVIDERS = ["crossref", "openalex", "europepmc", "semanticscholar"]

__all__ = ["DEFAULT_PROVIDERS", "ALL_PROVIDERS", "get_provider"]


def get_provider(name: str):
    """Return the provider module by name (lazy import)."""
    name = (name or "").strip().lower()
    if name == "crossref":
        from . import crossref
        return crossref
    if name == "openalex":
        from . import openalex
        return openalex
    if name == "europepmc":
        from . import europepmc
        return europepmc
    if name == "semanticscholar":
        from . import semanticscholar
        return semanticscholar
    raise KeyError(f"unknown provider: {name!r}")
