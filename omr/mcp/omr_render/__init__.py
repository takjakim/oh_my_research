"""omr-render: the authoritative in-server security boundary MCP server.

Stdio MCP server that detects the R/Quarto/pandoc toolchain, enforces a fixed
command allow-list + path-escape rejection + forced cwd + in-workspace scratch
redirection, renders Qmd files, and empirically classifies the active Codex
privilege model (AC9).
"""

SERVER_NAME = "omr-render"
SERVER_VERSION = "0.1.0"

__all__ = ["SERVER_NAME", "SERVER_VERSION"]
