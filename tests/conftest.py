"""
Shared pytest configuration and fixtures for oh-my-research acceptance tests.

Marker semantics:
  offline  — No network / no codex / no R / no Quarto required. Always runs in CI.
  codex    — Requires the `codex` CLI binary in PATH.
  r        — Requires R >= 4.2.0 installed locally.
  quarto   — Requires Quarto >= 1.4.0 installed locally.

Run subsets:
  pytest -m offline            # CI-safe, no external tools
  pytest -m "offline or r"     # add R-only tests
  pytest                       # everything (skip-guarded tests skip cleanly)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Repository root (parent of tests/)
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent.resolve()

# ---------------------------------------------------------------------------
# Fixture data roots
# ---------------------------------------------------------------------------
FIXTURES_LIT = REPO_ROOT / "tests" / "fixtures" / "lit"
FIXTURES_ANALYSIS = REPO_ROOT / "tests" / "fixtures" / "analysis"

# ---------------------------------------------------------------------------
# omr_scholar import path
# ---------------------------------------------------------------------------
OMR_MCP_ROOT = REPO_ROOT / "omr" / "mcp"

def _insert_omr_path():
    """Insert omr/mcp into sys.path so `import omr_scholar` works."""
    p = str(OMR_MCP_ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)

# ---------------------------------------------------------------------------
# Tool-presence helpers
# ---------------------------------------------------------------------------

def _has_codex() -> bool:
    return shutil.which("codex") is not None


def _has_r() -> bool:
    """True if Rscript is present AND reports >= 4.2.0."""
    rscript = shutil.which("Rscript")
    if not rscript:
        return False
    try:
        result = subprocess.run(
            [rscript, "--version"], capture_output=True, text=True, timeout=15
        )
        raw = (result.stdout or "") + (result.stderr or "")
        import re
        m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", raw)
        if not m:
            return False
        major, minor = int(m.group(1)), int(m.group(2))
        return (major, minor) >= (4, 2)
    except Exception:
        return False


def _has_quarto() -> bool:
    """True if quarto is present AND reports >= 1.4.0."""
    quarto = shutil.which("quarto")
    if not quarto:
        return False
    try:
        result = subprocess.run(
            [quarto, "--version"], capture_output=True, text=True, timeout=15
        )
        raw = (result.stdout or "") + (result.stderr or "")
        import re
        m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", raw)
        if not m:
            return False
        major, minor = int(m.group(1)), int(m.group(2))
        return (major, minor) >= (1, 4)
    except Exception:
        return False


def _has_omr_scholar() -> bool:
    """True if omr_scholar can be imported from omr/mcp/."""
    _insert_omr_path()
    try:
        import importlib
        importlib.import_module("omr_scholar")
        return True
    except ImportError:
        return False


def _has_omr_bundle_installed() -> bool:
    """True if the omr skills are installed to ~/.agents/skills/ (bundle installed)."""
    home = os.path.expanduser("~")
    skills_dir = Path(home) / ".agents" / "skills"
    # Check for at least one of the six omr-* skill dirs with SKILL.md
    for skill in ["omr-start", "omr-lit", "omr-analyze", "omr-write"]:
        skill_md = skills_dir / skill / "SKILL.md"
        if skill_md.exists():
            return True
    return False


# ---------------------------------------------------------------------------
# Skip conditions (reusable)
# ---------------------------------------------------------------------------
skip_no_codex = pytest.mark.skipif(
    not _has_codex(),
    reason="codex CLI not found in PATH — skipping codex-exec scenario tests",
)

skip_no_bundle = pytest.mark.skipif(
    not _has_omr_bundle_installed(),
    reason=(
        "oh-my-research bundle not installed to ~/.agents/skills/ — "
        "run install.sh first to enable full codex-exec scenario tests"
    ),
)

skip_no_r = pytest.mark.skipif(
    not _has_r(),
    reason="R >= 4.2.0 not found — skipping R-dependent tests",
)

skip_no_quarto = pytest.mark.skipif(
    not _has_quarto(),
    reason="Quarto >= 1.4.0 not found — skipping Quarto-dependent tests",
)

skip_no_omr_scholar = pytest.mark.skipif(
    not _has_omr_scholar(),
    reason="omr_scholar not importable from omr/mcp/ — skipping dedup unit tests",
)

# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def fixtures_lit() -> Path:
    return FIXTURES_LIT


@pytest.fixture(scope="session")
def fixtures_analysis() -> Path:
    return FIXTURES_ANALYSIS


@pytest.fixture(scope="session")
def expected_lit() -> dict:
    """Load the pinned lit fixture oracle."""
    with open(FIXTURES_LIT / "EXPECTED.json", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def pinned_records() -> list:
    """Load the full 12-record pinned input list (pre-dedup)."""
    with open(FIXTURES_LIT / "records.json", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def omr_scholar():
    """Import and return the omr_scholar package, skipping if unavailable."""
    _insert_omr_path()
    try:
        import omr_scholar
        return omr_scholar
    except ImportError as exc:
        pytest.skip(f"omr_scholar not importable: {exc}")


@pytest.fixture(scope="session")
def dedup_module():
    """Import omr_scholar.dedup, skipping if unavailable."""
    _insert_omr_path()
    try:
        from omr_scholar import dedup
        return dedup
    except ImportError as exc:
        pytest.skip(f"omr_scholar.dedup not importable: {exc}")


@pytest.fixture(scope="session")
def bibtex_module():
    """Import omr_scholar.bibtex, skipping if unavailable."""
    _insert_omr_path()
    try:
        from omr_scholar import bibtex
        return bibtex
    except ImportError as exc:
        pytest.skip(f"omr_scholar.bibtex not importable: {exc}")


@pytest.fixture(scope="session")
def cache_module():
    """Import omr_scholar.cache, skipping if unavailable."""
    _insert_omr_path()
    try:
        from omr_scholar import cache
        return cache
    except ImportError as exc:
        pytest.skip(f"omr_scholar.cache not importable: {exc}")


@pytest.fixture
def tmp_study(tmp_path):
    """Create a minimal study folder structure for boundary/path tests."""
    study = tmp_path / "study"
    study.mkdir()
    (study / ".omr").mkdir()
    (study / ".omr" / "tmp").mkdir()
    return study


@pytest.fixture
def tmp_cache_dir(tmp_path, cache_module):
    """Return a temp cache dir pre-populated with the pinned fixtures."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    store = cache_module.CacheStore(str(cache_dir))

    query = "caffeine reaction time cognitive performance"

    # Load and inject crossref payload
    with open(FIXTURES_LIT / "cache_crossref.json", encoding="utf-8") as fh:
        cr_doc = json.load(fh)
    store.set("crossref", query, cr_doc["payload"], pinned=True)

    # Load and inject openalex payload
    with open(FIXTURES_LIT / "cache_openalex.json", encoding="utf-8") as fh:
        oa_doc = json.load(fh)
    store.set("openalex", query, oa_doc["payload"], pinned=True)

    return store, cache_dir, query
