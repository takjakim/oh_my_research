"""omr-scholar stdio MCP server entrypoint.

Launch (how the installer starts it):

    python -m omr_scholar.server

(or, from this directory, ``python server.py``) -- speaks MCP over stdio.

The ``mcp`` SDK is imported lazily inside :func:`main` so that importing
this module, running ``scholar.version`` logic, and the offline test
suite all work with **stdlib only** (plus ``mcp`` only when actually
serving). Tool implementations live in :mod:`omr_scholar.core`.

Exposed tools (exact names):
    scholar.version       -> {"server","version"}            (zero side effects)
    scholar.search        -> {"records","providers","degraded"}
    scholar.resolve_doi   -> normalized record | null
    scholar.dedup         -> {"records","merge_report","stats"}
    scholar.to_bibtex     -> BibTeX string
    scholar.to_csl_json   -> CSL-JSON array
"""

from __future__ import annotations

import sys

try:  # Allow ``python server.py`` (no package context) as well.
    from . import core
except ImportError:  # pragma: no cover - direct-script fallback
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from omr_scholar import core  # type: ignore


SERVER_NAME = "omr-scholar"


def build_server():
    """Construct the MCP ``Server`` with all tools registered.

    Imports the ``mcp`` SDK lazily; raises ImportError with an actionable
    message if the SDK is not installed.
    """
    try:
        from mcp.server import Server
        from mcp.types import TextContent, Tool
    except ImportError as exc:  # pragma: no cover - depends on env
        raise ImportError(
            "The 'mcp' package is required to run the omr-scholar server. "
            "Install it with: pip install mcp"
        ) from exc

    import json

    server = Server(SERVER_NAME)

    tools = [
        Tool(
            name="scholar.version",
            description="Availability probe. Returns {server, version}. "
                        "Zero side effects.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="scholar.search",
            description="Search literature providers (Crossref + OpenAlex) "
                        "and return normalized records.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "providers": {
                        "type": "array", "items": {"type": "string"},
                        "default": [],
                    },
                    "year_from": {"type": ["integer", "null"]},
                    "limit": {"type": "integer", "default": 25},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="scholar.resolve_doi",
            description="Resolve a DOI to one normalized record (Crossref).",
            inputSchema={
                "type": "object",
                "properties": {"doi": {"type": "string"}},
                "required": ["doi"],
            },
        ),
        Tool(
            name="scholar.dedup",
            description="Deduplicate records (exact-DOI + guarded fuzzy "
                        "title/year). Returns deduped set + merge report.",
            inputSchema={
                "type": "object",
                "properties": {
                    "records": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["records"],
            },
        ),
        Tool(
            name="scholar.to_bibtex",
            description="Serialize records to BibTeX with stable keys.",
            inputSchema={
                "type": "object",
                "properties": {
                    "records": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["records"],
            },
        ),
        Tool(
            name="scholar.to_csl_json",
            description="Serialize records to a CSL-JSON array.",
            inputSchema={
                "type": "object",
                "properties": {
                    "records": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["records"],
            },
        ),
    ]

    @server.list_tools()
    async def _list_tools():  # noqa: D401
        return tools

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict):
        args = arguments or {}
        if name == "scholar.version":
            result = core.version()
        elif name == "scholar.search":
            result = core.search(
                args["query"],
                providers=args.get("providers") or [],
                year_from=args.get("year_from"),
                limit=args.get("limit", 25),
            )
        elif name == "scholar.resolve_doi":
            result = core.resolve_doi(args["doi"])
        elif name == "scholar.dedup":
            result = core.dedup(args.get("records") or [])
        elif name == "scholar.to_bibtex":
            result = core.to_bibtex(args.get("records") or [])
        elif name == "scholar.to_csl_json":
            result = core.to_csl_json(args.get("records") or [])
        else:
            raise ValueError(f"unknown tool: {name}")

        if isinstance(result, str):
            payload = result
        else:
            payload = json.dumps(result, ensure_ascii=False)
        return [TextContent(type="text", text=payload)]

    return server


def main() -> None:
    """Run the stdio MCP server (blocking)."""
    import anyio
    from mcp.server.stdio import stdio_server

    server = build_server()

    async def _run() -> None:
        async with stdio_server() as (read, write):
            await server.run(
                read, write, server.create_initialization_options()
            )

    anyio.run(_run)


if __name__ == "__main__":
    main()
