"""omr-scholar: stdio MCP server for scholarly literature search.

MVP providers: Crossref + OpenAlex (functional).
Post-MVP stubs: Europe PMC, Semantic Scholar.

Core logic (dedup, bibtex, csl, version) is pure-stdlib and import-safe:
no network calls and no third-party imports happen at module import time.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
