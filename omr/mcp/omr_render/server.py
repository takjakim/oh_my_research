"""omr-render stdio MCP server entrypoint.

Launch (stdio):  python -m omr_render.server

Exposes (exact tool names other workers depend on):
  - render.version()                       -> {"server","version"}  (EV5, zero side effects)
  - render.detect()                        -> toolchain detection + floors
  - render.render(qmd_path, study_root, ...) -> rendered manifest (boundary-enforced)
  - render.classify_privilege(study_root, ...) -> AC9 privilege classification

The heavy logic lives in stdlib-only sibling modules (versions, boundary,
detect, runner, classify) which are unit-tested WITHOUT the `mcp` package or
R/Quarto installed. This module only wires those into the MCP protocol.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from . import SERVER_NAME, SERVER_VERSION
from .classify import classify_privilege as _classify_privilege
from .detect import detect_all
from .runner import DEFAULT_TIMEOUT, render_qmd

# ---------------------------------------------------------------------------
# Plain (transport-independent) tool implementations
# ---------------------------------------------------------------------------


def tool_version() -> dict:
    """EV5 probe -- ZERO side effects."""
    return {"server": SERVER_NAME, "version": SERVER_VERSION}


def tool_detect() -> dict:
    return detect_all()


def tool_render(arguments: dict) -> dict:
    qmd_path = arguments.get("qmd_path")
    study_root = arguments.get("study_root")
    if not qmd_path or not study_root:
        return {
            "ok": False,
            "error": "invalid-args",
            "message": "qmd_path and study_root are required",
        }
    det = detect_all()
    quarto = det["tools"]["quarto"]
    rscript = det["tools"]["R"]
    if not quarto["ok"]:
        # Absent / below-floor toolchain -> structured blocked error (4.4).
        return {
            "ok": False,
            "error": "toolchain-blocked",
            "message": "Quarto absent or below floor (>=1.4.0 required).",
            "detect": det,
            "guidance": "Install/upgrade Quarto, then re-run; stage stays 'blocked'.",
        }
    return render_qmd(
        qmd_path,
        study_root,
        quarto_bin=quarto["path"],
        rscript_bin=rscript["path"] if rscript["ok"] else None,
        form=arguments.get("form", "quarto_render"),
        timeout=int(arguments.get("timeout", DEFAULT_TIMEOUT)),
        allow_install=bool(arguments.get("allow_install", False)),
        output_subdir=arguments.get("output_subdir", "outputs"),
    )


def tool_classify_privilege(arguments: dict) -> dict:
    study_root = arguments.get("study_root")
    if not study_root:
        return {"ok": False, "error": "invalid-args",
                "message": "study_root is required"}
    det = detect_all()
    return _classify_privilege(
        study_root,
        rscript_bin=det["tools"]["R"]["path"] if det["tools"]["R"]["found"] else None,
        quarto_bin=det["tools"]["quarto"]["path"]
        if det["tools"]["quarto"]["found"]
        else None,
    )


# Registry maps the EXACT MCP tool name -> (callable, takes_args).
TOOLS = {
    "render.version": (lambda _a: tool_version(), False),
    "render.detect": (lambda _a: tool_detect(), False),
    "render.render": (tool_render, True),
    "render.classify_privilege": (tool_classify_privilege, True),
}

TOOL_SCHEMAS = [
    {
        "name": "render.version",
        "description": "Return server name/version. Zero side effects (EV5 probe).",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "render.detect",
        "description": (
            "Detect Rscript/quarto/pandoc (PATH + per-OS dirs), parse versions, "
            "enforce hard floors R>=4.2.0 Quarto>=1.4.0 pandoc>=3.1."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "render.render",
        "description": (
            "Render a Qmd via local Quarto/R under the in-server security "
            "boundary (allow-list + path-escape + forced cwd + in-workspace "
            "scratch). Returns a verified manifest + parsed results.json."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "qmd_path": {"type": "string"},
                "study_root": {"type": "string"},
                "form": {"type": "string", "default": "quarto_render"},
                "timeout": {"type": "integer", "default": DEFAULT_TIMEOUT},
                "allow_install": {"type": "boolean", "default": False},
                "output_subdir": {"type": "string", "default": "outputs"},
            },
            "required": ["qmd_path", "study_root"],
            "additionalProperties": False,
        },
    },
    {
        "name": "render.classify_privilege",
        "description": (
            "AC9: empirically classify the active Codex privilege model "
            "(out-of-workspace write, abs-path exec, tiny end-to-end render)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"study_root": {"type": "string"}},
            "required": ["study_root"],
            "additionalProperties": False,
        },
    },
]


def _dispatch(name: str, arguments: dict) -> dict:
    entry = TOOLS.get(name)
    if entry is None:
        return {"ok": False, "error": "unknown-tool", "message": name}
    fn, _takes = entry
    return fn(arguments or {})


async def _amain() -> None:
    # Imported lazily so the package + unit tests work without `mcp` installed.
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    import mcp.types as types

    server = Server(SERVER_NAME)

    @server.list_tools()
    async def _list_tools() -> list:  # type: ignore[no-redef]
        return [
            types.Tool(
                name=s["name"],
                description=s["description"],
                inputSchema=s["inputSchema"],
            )
            for s in TOOL_SCHEMAS
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict) -> list:  # type: ignore[no-redef]
        result = _dispatch(name, arguments or {})
        return [types.TextContent(type="text", text=json.dumps(result))]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
