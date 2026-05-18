"""Semantic version parsing and hard-floor enforcement.

Pure, stdlib-only, fully unit-testable without R/Quarto/pandoc installed.

Hard floors (per plan section 4.1):
  - R       >= 4.2.0
  - Quarto  >= 1.4.0
  - pandoc  >= 3.1

Unparseable version => HARD FAIL (raises ValueError or returns below_floor=True
depending on the call site; see ``check_floor``).
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

# (major, minor, patch) hard floors keyed by canonical tool name.
HARD_FLOORS = {
    "R": (4, 2, 0),
    "quarto": (1, 4, 0),
    "pandoc": (3, 1, 0),
}

# Matches the first dotted numeric token, e.g. "4.2.1", "1.4", "3.1.11".
_VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def parse_version(text: str) -> Optional[Tuple[int, int, int]]:
    """Extract a (major, minor, patch) tuple from raw ``--version`` output.

    Returns ``None`` when no semantic version can be found (caller must treat
    this as a HARD FAIL -- never silently pass).

    Handles representative formats:
      - R:      "R scripting front-end version 4.2.1 (2022-06-23)"
      - Quarto: "1.4.553"
      - pandoc: "pandoc 3.1.11\nFeatures: ..."
    """
    if not text or not isinstance(text, str):
        return None
    m = _VERSION_RE.search(text.strip())
    if not m:
        return None
    major = int(m.group(1))
    minor = int(m.group(2))
    patch = int(m.group(3)) if m.group(3) is not None else 0
    return (major, minor, patch)


def compare_versions(
    a: Tuple[int, int, int], b: Tuple[int, int, int]
) -> int:
    """Return -1 if a<b, 0 if a==b, 1 if a>b (semantic, tuple compare)."""
    if a < b:
        return -1
    if a > b:
        return 1
    return 0


def meets_floor(tool: str, version: Optional[Tuple[int, int, int]]) -> bool:
    """True iff ``version`` is parseable AND >= the tool's hard floor.

    Unparseable (``version is None``) or unknown tool => False (HARD FAIL).
    """
    if version is None:
        return False
    floor = HARD_FLOORS.get(tool)
    if floor is None:
        return False
    return compare_versions(version, floor) >= 0


def check_floor(tool: str, raw_version_text: str) -> dict:
    """Parse + floor-check raw ``--version`` output for ``tool``.

    Returns a structured dict:
      {
        "tool": "R",
        "raw": "<raw text>",
        "version": "4.2.1" | None,
        "version_tuple": [4,2,1] | None,
        "floor": "4.2.0",
        "parseable": bool,
        "below_floor": bool,   # True if unparseable OR < floor
        "ok": bool,            # True iff parseable AND >= floor
      }
    """
    parsed = parse_version(raw_version_text)
    floor = HARD_FLOORS.get(tool)
    ok = meets_floor(tool, parsed)
    return {
        "tool": tool,
        "raw": raw_version_text,
        "version": ".".join(str(x) for x in parsed) if parsed else None,
        "version_tuple": list(parsed) if parsed else None,
        "floor": ".".join(str(x) for x in floor) if floor else None,
        "parseable": parsed is not None,
        "below_floor": not ok,
        "ok": ok,
    }
