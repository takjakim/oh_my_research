"""Toolchain detection: probe Rscript / quarto / pandoc (plan section 4.1).

Probe order per tool: PATH first, then per-OS known install dirs. Parse
versions from ``--version`` and enforce hard floors (see versions.py).

subprocess is isolated to ``_probe_version`` so unit tests can monkeypatch
candidate discovery and version probing without any toolchain installed.
"""

from __future__ import annotations

import glob
import os
import platform
import shutil
import subprocess
from typing import List, Optional

from .versions import check_floor

_PROBE_TIMEOUT = 20  # seconds for a `--version` call


def _known_dirs_r() -> List[str]:
    sysname = platform.system()
    if sysname == "Windows":
        cands: List[str] = []
        for pat in (
            r"C:\Program Files\R\R-*\bin\Rscript.exe",
            r"C:\Program Files\R\R-*\bin\x64\Rscript.exe",
        ):
            cands += sorted(glob.glob(pat))
        return cands
    if sysname == "Darwin":
        return [
            "/usr/local/bin/Rscript",
            "/opt/homebrew/bin/Rscript",
            "/Library/Frameworks/R.framework/Resources/bin/Rscript",
        ]
    # Linux / other POSIX
    return ["/usr/local/bin/Rscript", "/usr/bin/Rscript"]


def _known_dirs_quarto() -> List[str]:
    sysname = platform.system()
    if sysname == "Windows":
        local = os.environ.get("LOCALAPPDATA", "")
        cands = []
        if local:
            cands.append(os.path.join(local, "Programs", "Quarto", "bin", "quarto.exe"))
        cands.append(r"C:\Program Files\Quarto\bin\quarto.exe")
        return cands
    if sysname == "Darwin":
        return [
            "/usr/local/bin/quarto",
            "/opt/homebrew/bin/quarto",
            "/Applications/quarto/bin/quarto",
        ]
    return ["/usr/local/bin/quarto", "/usr/bin/quarto"]


def _known_dirs_pandoc() -> List[str]:
    sysname = platform.system()
    if sysname == "Windows":
        local = os.environ.get("LOCALAPPDATA", "")
        cands = []
        if local:
            cands.append(os.path.join(local, "Pandoc", "pandoc.exe"))
        cands.append(r"C:\Program Files\Pandoc\pandoc.exe")
        return cands
    if sysname == "Darwin":
        return ["/usr/local/bin/pandoc", "/opt/homebrew/bin/pandoc"]
    return ["/usr/local/bin/pandoc", "/usr/bin/pandoc"]


def find_candidates(tool: str) -> List[str]:
    """Return ordered absolute-path candidates for ``tool``.

    PATH hit first (resolved to abs path), then per-OS known dirs that exist.
    """
    exe = {"R": "Rscript", "quarto": "quarto", "pandoc": "pandoc"}[tool]
    found: List[str] = []
    which = shutil.which(exe)
    if which:
        found.append(os.path.realpath(which))
    known = {
        "R": _known_dirs_r,
        "quarto": _known_dirs_quarto,
        "pandoc": _known_dirs_pandoc,
    }[tool]()
    for p in known:
        if os.path.isfile(p):
            rp = os.path.realpath(p)
            if rp not in found:
                found.append(rp)
    return found


def _probe_version(binary: str) -> Optional[str]:
    """Run ``<binary> --version`` and return raw stdout (or None on failure)."""
    try:
        proc = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = (proc.stdout or "") + (proc.stderr or "")
    return out if out.strip() else None


def detect_tool(tool: str) -> dict:
    """Detect a single tool: locate binary, parse version, floor-check.

    Returns:
      {
        "tool": "R",
        "found": bool,
        "path": "<abs>" | None,
        "candidates": [...abs...],
        "version": "4.2.1" | None,
        "floor": "4.2.0",
        "below_floor": bool,
        "ok": bool,           # found AND parseable AND >= floor
        "error": None | "not-found" | "unparseable-version",
      }
    """
    candidates = find_candidates(tool)
    if not candidates:
        return {
            "tool": tool,
            "found": False,
            "path": None,
            "candidates": [],
            "version": None,
            "floor": check_floor(tool, "")["floor"],
            "below_floor": True,
            "ok": False,
            "error": "not-found",
        }
    for cand in candidates:
        raw = _probe_version(cand)
        if raw is None:
            continue
        fc = check_floor(tool, raw)
        return {
            "tool": tool,
            "found": True,
            "path": cand,
            "candidates": candidates,
            "version": fc["version"],
            "floor": fc["floor"],
            "below_floor": fc["below_floor"],
            "ok": fc["ok"],
            "error": None if fc["parseable"] else "unparseable-version",
        }
    # Located but none responded to --version.
    return {
        "tool": tool,
        "found": True,
        "path": candidates[0],
        "candidates": candidates,
        "version": None,
        "floor": check_floor(tool, "")["floor"],
        "below_floor": True,
        "ok": False,
        "error": "unparseable-version",
    }


def detect_all() -> dict:
    """Detect R, quarto, pandoc. Returns per-tool results + overall pass."""
    r = detect_tool("R")
    q = detect_tool("quarto")
    p = detect_tool("pandoc")
    # pandoc floor only matters if a STANDALONE pandoc is used instead of
    # Quarto's bundled one; quarto+R passing is sufficient for MVP DOCX.
    core_ok = r["ok"] and q["ok"]
    return {
        "tools": {"R": r, "quarto": q, "pandoc": p},
        "ok": core_ok,
        "core_tools_ok": core_ok,
        "notes": (
            "R and Quarto are required (DOCX MVP). Standalone pandoc is "
            "optional -- Quarto bundles its own pandoc."
        ),
    }
