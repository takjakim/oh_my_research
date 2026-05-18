"""Version resolution with zero side effects.

Resolution order:
  1. ``omr/VERSION`` file (repo-level, if present)
  2. hardcoded fallback ``0.1.0``

This module imports only stdlib. ``get_version()`` performs a single
read-only filesystem lookup and never touches the network.
"""

from __future__ import annotations

import os

_FALLBACK_VERSION = "0.1.0"


def _candidate_version_paths() -> list[str]:
    here = os.path.dirname(os.path.abspath(__file__))
    # omr_scholar/ -> mcp/ -> omr/  ->  omr/VERSION
    omr_dir = os.path.abspath(os.path.join(here, os.pardir, os.pardir))
    return [
        os.path.join(omr_dir, "VERSION"),
    ]


def get_version() -> str:
    """Return the server version string. Read-only, no network."""
    for path in _candidate_version_paths():
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read().strip()
            if text:
                return text
        except OSError:
            continue
    return _FALLBACK_VERSION
