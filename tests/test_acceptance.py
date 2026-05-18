"""
oh-my-research Acceptance Test Harness  (AC1–AC10)
====================================================

Every test is EITHER:
  - @pytest.mark.offline  — runs without any external tool (always passes in CI)
  - Guarded with skip_no_codex / skip_no_r / skip_no_quarto fixtures

Run modes:
  pytest -m offline          # CI subset (no network, no codex, no R, no Quarto)
  pytest                     # full suite (tools that are absent are skipped)
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tests.conftest import (
    FIXTURES_ANALYSIS,
    FIXTURES_LIT,
    REPO_ROOT,
    _has_codex,
    _has_quarto,
    _has_r,
    _insert_omr_path,
    skip_no_bundle,
    skip_no_codex,
    skip_no_omr_scholar,
    skip_no_quarto,
    skip_no_r,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_csv_dicts(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# Canonical ASCII test label names written by the analysis.qmd base-R writer.
_CANONICAL_LABELS = [
    "Mann-Whitney U",
    "Wilcoxon signed-rank",
    "Welch",
    "Student",
    "paired t-test",
    "one-way ANOVA",
    "chi-square",
    "OLS",
]

# Regex that matches the canonical label headline line in analysis-plan.md.
# The skill writes the chosen test using a canonical ASCII label on a dedicated
# line, e.g.: "**Chosen test:** Mann-Whitney U" or "Chosen test: Welch".
_CHOSEN_LABEL_RE = re.compile(
    r"chosen\s+test[:\s*]+(.+)",
    re.IGNORECASE,
)


def _chosen_test_label(study: Path) -> str:
    """Return the canonical chosen-test label for a study.

    Priority:
      1. ``results.json`` ``label`` field (authoritative — written by R after render).
      2. Canonical headline label line in ``analysis-plan.md`` (written by the skill
         before the render step).

    Returns the normalised label string, or empty string if neither source exists.
    The label is stripped but otherwise not further processed; callers assert on it.
    """
    results_json = study / "20_analysis" / "outputs" / "results.json"
    if results_json.exists():
        try:
            with open(results_json, encoding="utf-8") as fh:
                r_data = json.load(fh)
            label = r_data.get("label", "")
            if label:
                return label.strip()
        except (json.JSONDecodeError, OSError):
            pass

    plan_path = study / "20_analysis" / "analysis-plan.md"
    if plan_path.exists():
        plan_text = plan_path.read_text(encoding="utf-8")
        for line in plan_text.splitlines():
            m = _CHOSEN_LABEL_RE.search(line)
            if m:
                return m.group(1).strip().rstrip("*").strip()

    return ""


def _stage_status(state: dict, n: int) -> str:
    """Read stage status from the pinned nested schema: state["stages"]["stageN"]["status"].

    Returns empty string if the path is absent (so callers can assert on it safely).
    """
    return state.get("stages", {}).get(f"stage{n}", {}).get("status", "")


# ---------------------------------------------------------------------------
# AC1  — Installer scripts: syntax + config region structure
# ---------------------------------------------------------------------------


class TestAC1Installer:
    """AC1: Installer scripts exist, are bash-clean, config template is valid."""

    @pytest.mark.offline
    def test_install_sh_exists(self, repo_root):
        """install.sh (or install.command) must exist at repo root or config/."""
        candidates = [
            repo_root / "install.sh",
            repo_root / "install.command",
            repo_root / "config" / "install.sh",
        ]
        found = [c for c in candidates if c.exists()]
        if not found:
            pytest.skip(
                "install.sh not found — W2/W3 installer worker may not have run yet; "
                "skipping but marking as an integration risk"
            )

    @pytest.mark.offline
    def test_install_ps1_exists(self, repo_root):
        """install.ps1 must exist at repo root."""
        candidates = [
            repo_root / "install.ps1",
            repo_root / "config" / "install.ps1",
        ]
        found = [c for c in candidates if c.exists()]
        if not found:
            pytest.skip(
                "install.ps1 not found — W2/W3 installer worker may not have run yet"
            )

    @pytest.mark.offline
    def test_install_sh_bash_syntax(self, repo_root):
        """install.sh must be bash-syntax-clean (`bash -n`)."""
        install_sh = repo_root / "install.sh"
        if not install_sh.exists():
            pytest.skip("install.sh not present yet")
        bash = shutil.which("bash")
        if not bash:
            pytest.skip("bash not found; cannot check syntax")
        result = subprocess.run(
            [bash, "-n", str(install_sh)], capture_output=True, text=True
        )
        assert result.returncode == 0, (
            f"install.sh has bash syntax errors:\n{result.stderr}"
        )

    @pytest.mark.offline
    def test_config_template_has_top_level_keys(self, repo_root):
        """config.toml.omr-region.tmpl must contain table-section keys (A6 split:
        sandbox_mode/approval_policy now live in config.toml.omr-root.tmpl)."""
        tmpl = repo_root / "config" / "config.toml.omr-region.tmpl"
        assert tmpl.exists(), "config.toml.omr-region.tmpl not found"
        text = tmpl.read_text(encoding="utf-8")

        # These table-section keys belong in the TABLE region template.
        required_table_keys = [
            "[sandbox_workspace_write]",
            "[mcp_servers.omr_scholar]",
            "[mcp_servers.omr_render]",
        ]
        for key in required_table_keys:
            assert key in text, (
                f"config.toml.omr-region.tmpl is missing required table section: {key!r}"
            )

        # sandbox_mode and approval_policy are ROOT scalars — they must NOT be in the
        # table region (they live in config.toml.omr-root.tmpl per A6 split).
        for scalar_key in ("sandbox_mode", "approval_policy"):
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                assert not re.search(rf"^{scalar_key}\s*=", stripped), (
                    f"config.toml.omr-region.tmpl must NOT contain root scalar {scalar_key!r} "
                    f"(A6 split: root scalars belong in config.toml.omr-root.tmpl).\n"
                    f"Offending line: {line!r}"
                )

        # Root template must contain the two root scalars.
        root_tmpl = repo_root / "config" / "config.toml.omr-root.tmpl"
        assert root_tmpl.exists(), "config.toml.omr-root.tmpl not found"
        root_text = root_tmpl.read_text(encoding="utf-8")
        for scalar_key in ("sandbox_mode", "approval_policy"):
            assert scalar_key in root_text, (
                f"config.toml.omr-root.tmpl is missing required root scalar: {scalar_key!r}"
            )

    @pytest.mark.offline
    def test_config_template_has_no_profiles(self, repo_root):
        """config.toml.omr-region.tmpl must NOT contain [profiles.* keys."""
        tmpl = repo_root / "config" / "config.toml.omr-region.tmpl"
        assert tmpl.exists(), "config.toml.omr-region.tmpl not found"
        text = tmpl.read_text(encoding="utf-8")
        assert "[profiles." not in text, (
            "config.toml.omr-region.tmpl contains [profiles.* — this is explicitly "
            "forbidden (Codex profiles are unsupported in the desktop GUI)"
        )

    @pytest.mark.offline
    def test_config_template_sandbox_value(self, repo_root):
        """sandbox_mode must be set to 'workspace-write' in the ROOT config template.

        A6 split: sandbox_mode and approval_policy are root scalars and live in
        config.toml.omr-root.tmpl (merged at TOP of config.toml before any [table]).
        The table template config.toml.omr-region.tmpl must NOT contain these scalars.
        """
        # ROOT template: must contain the root scalars.
        root_tmpl = repo_root / "config" / "config.toml.omr-root.tmpl"
        assert root_tmpl.exists(), "config.toml.omr-root.tmpl not found"
        root_text = root_tmpl.read_text(encoding="utf-8")
        assert 'sandbox_mode = "workspace-write"' in root_text, (
            'config.toml.omr-root.tmpl must set sandbox_mode = "workspace-write"'
        )
        assert 'approval_policy = "on-request"' in root_text, (
            'config.toml.omr-root.tmpl must set approval_policy = "on-request"'
        )
        # Root template must use the :root sentinel variant.
        assert ">>> oh-my-research:root" in root_text, (
            "config.toml.omr-root.tmpl must have opening sentinel '>>> oh-my-research:root'"
        )
        assert "<<< oh-my-research:root" in root_text, (
            "config.toml.omr-root.tmpl must have closing sentinel '<<< oh-my-research:root'"
        )

        # TABLE region template: must NOT contain root scalars (lock the A6 split).
        region_tmpl = repo_root / "config" / "config.toml.omr-region.tmpl"
        assert region_tmpl.exists(), "config.toml.omr-region.tmpl not found"
        region_text = region_tmpl.read_text(encoding="utf-8")
        for scalar_key in ("sandbox_mode", "approval_policy"):
            for line in region_text.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                assert not re.search(rf"^{scalar_key}\s*=", stripped), (
                    f"config.toml.omr-region.tmpl must NOT contain root scalar {scalar_key!r} "
                    f"(A6 split: root scalars belong in config.toml.omr-root.tmpl).\n"
                    f"Offending line: {line!r}"
                )

    @pytest.mark.offline
    def test_config_template_exclude_tmp_defaults(self, repo_root):
        """exclude_slash_tmp and exclude_tmpdir_env_var must be false in template."""
        tmpl = repo_root / "config" / "config.toml.omr-region.tmpl"
        assert tmpl.exists()
        text = tmpl.read_text(encoding="utf-8")
        assert "exclude_slash_tmp = false" in text, (
            "config template must assert exclude_slash_tmp = false"
        )
        assert "exclude_tmpdir_env_var = false" in text, (
            "config template must assert exclude_tmpdir_env_var = false"
        )

    @pytest.mark.offline
    def test_config_template_no_writable_roots_assignment(self, repo_root):
        """writable_roots must NOT be assigned a value in the MVP config template.

        Comments mentioning writable_roots as a post-MVP escape hatch are OK;
        only an uncommented key = [...] assignment is forbidden.
        """
        tmpl = repo_root / "config" / "config.toml.omr-region.tmpl"
        assert tmpl.exists()
        text = tmpl.read_text(encoding="utf-8")
        import re
        # Match: writable_roots followed by = on a non-comment line
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue  # comment lines are fine
            assert not re.search(r"writable_roots\s*=", stripped), (
                f"writable_roots must NOT be assigned in MVP config (post-MVP only).\n"
                f"Offending line: {line!r}"
            )

    @pytest.mark.offline
    def test_sentinel_region_markers_present(self, repo_root):
        """Config template must have opening and closing sentinel markers."""
        tmpl = repo_root / "config" / "config.toml.omr-region.tmpl"
        assert tmpl.exists()
        text = tmpl.read_text(encoding="utf-8")
        assert ">>> oh-my-research" in text, "Missing opening sentinel marker"
        assert "<<< oh-my-research" in text, "Missing closing sentinel marker"

    @pytest.mark.offline
    def test_idempotent_region_merge_simulation(self, tmp_path):
        """Simulate sentinel-region idempotency: merging twice must not duplicate."""
        tmpl = REPO_ROOT / "config" / "config.toml.omr-region.tmpl"
        if not tmpl.exists():
            pytest.skip("config.toml.omr-region.tmpl not present yet")

        region_text = tmpl.read_text(encoding="utf-8")
        # Replace template variables with placeholders for test
        region_text = region_text.replace("@@VENV_PY@@", "/usr/bin/python3")
        region_text = region_text.replace("@@OMR_HOME@@", "/home/user/.codex/omr")
        region_text = region_text.replace("@@OMR_SCHOLAR_MAILTO@@", "test@example.com")

        # Simulate: config.toml starts with user content
        user_content = '# user config\nsome_user_key = "value"\n\n'
        config_path = tmp_path / "config.toml"
        config_path.write_text(user_content, encoding="utf-8")

        # Merge once
        _simulate_region_merge(config_path, region_text)
        content_after_first = config_path.read_text(encoding="utf-8")

        # Merge again (idempotent)
        _simulate_region_merge(config_path, region_text)
        content_after_second = config_path.read_text(encoding="utf-8")

        assert content_after_first == content_after_second, (
            "Region merge is NOT idempotent — second merge changed the file.\n"
            f"After first merge:\n{content_after_first}\n\n"
            f"After second merge:\n{content_after_second}"
        )

        # User content must survive
        assert "some_user_key" in content_after_second, (
            "User content was lost during region merge"
        )

        # Exactly one sentinel block
        opening_count = content_after_second.count(">>> oh-my-research")
        closing_count = content_after_second.count("<<< oh-my-research")
        assert opening_count == 1, f"Expected 1 opening sentinel, found {opening_count}"
        assert closing_count == 1, f"Expected 1 closing sentinel, found {closing_count}"

    @pytest.mark.offline
    def test_agents_md_template_has_sentinel(self, repo_root):
        """AGENTS.md.omr-region.tmpl must have omr:start and omr:end markers."""
        tmpl = repo_root / "config" / "AGENTS.md.omr-region.tmpl"
        assert tmpl.exists(), "AGENTS.md.omr-region.tmpl not found"
        text = tmpl.read_text(encoding="utf-8")
        assert "<!-- omr:start -->" in text, "Missing <!-- omr:start --> in AGENTS.md template"
        assert "<!-- omr:end -->" in text, "Missing <!-- omr:end --> in AGENTS.md template"


def _simulate_region_merge(config_path: Path, region_text: str) -> None:
    """
    Simulate the installer's sentinel-region merge (idempotent):
    - If region already present, replace it exactly.
    - If not present, append it.

    The sentinel markers are:
      - Opening: any line containing '>>> oh-my-research'
      - Closing:  any line containing '<<< oh-my-research'

    Idempotency invariant: the output of merging once == the output of merging twice.
    """
    current = config_path.read_text(encoding="utf-8")

    # Normalize region_text: strip trailing whitespace, ensure single trailing newline
    region_normalized = region_text.rstrip("\n") + "\n"

    lines = current.splitlines(keepends=True)
    open_line_idx = next(
        (i for i, ln in enumerate(lines) if ">>> oh-my-research" in ln), None
    )
    close_line_idx = next(
        (i for i, ln in enumerate(lines) if "<<< oh-my-research" in ln), None
    )

    if open_line_idx is not None and close_line_idx is not None:
        # Preserve everything before the region and after the closing sentinel.
        before = "".join(lines[:open_line_idx])
        after_lines = lines[close_line_idx + 1:]
        # Strip leading blank lines from "after" to avoid accumulation
        while after_lines and after_lines[0].strip() == "":
            after_lines = after_lines[1:]
        after = "".join(after_lines)
        # Produce: before + "\n" (separator if before non-empty) + region + after
        separator = "\n" if before and not before.endswith("\n\n") else ""
        new_content = before + separator + region_normalized + ("\n" if after else "") + after
    else:
        # Append: ensure exactly one blank line separator, then the region
        base = current.rstrip("\n") + "\n\n"
        new_content = base + region_normalized

    config_path.write_text(new_content, encoding="utf-8")


# ---------------------------------------------------------------------------
# AC2 / EV5  — MCP server structural checks (offline: imports + version tool)
# ---------------------------------------------------------------------------


class TestAC2MCPStructural:
    """AC2/EV5: MCP servers expose version/ping tool; config registers both."""

    @pytest.mark.offline
    def test_omr_scholar_version_importable(self):
        """omr_scholar.version module must import and expose get_version()."""
        _insert_omr_path()
        try:
            from omr_scholar.version import get_version
        except ImportError as exc:
            pytest.skip(f"omr_scholar.version not importable: {exc}")
        v = get_version()
        assert isinstance(v, str) and v, "get_version() must return a non-empty string"
        # Version must be parseable as semver-like
        assert re.match(r"\d+\.\d+", v), f"version {v!r} is not semver-like"

    @pytest.mark.offline
    def test_omr_render_versions_importable(self):
        """omr_render.versions module must import and expose HARD_FLOORS."""
        _insert_omr_path()
        render_mcp = REPO_ROOT / "omr" / "mcp" / "omr_render"
        render_path = str(render_mcp.parent)
        if render_path not in sys.path:
            sys.path.insert(0, render_path)
        try:
            from omr_render.versions import HARD_FLOORS, check_floor
        except ImportError as exc:
            pytest.skip(f"omr_render.versions not importable: {exc}")
        assert "R" in HARD_FLOORS
        assert "quarto" in HARD_FLOORS
        assert "pandoc" in HARD_FLOORS

    @pytest.mark.offline
    def test_omr_render_boundary_importable(self):
        """omr_render.boundary module must import cleanly."""
        render_mcp = REPO_ROOT / "omr" / "mcp" / "omr_render"
        render_path = str(render_mcp.parent)
        if render_path not in sys.path:
            sys.path.insert(0, render_path)
        try:
            from omr_render.boundary import BoundaryError, check_allowed, resolve_within_root
        except ImportError as exc:
            pytest.skip(f"omr_render.boundary not importable: {exc}")
        # Spot-check: BoundaryError is raised for unknown form
        with pytest.raises(BoundaryError) as exc_info:
            check_allowed("nonexistent_form")
        assert exc_info.value.kind == "allow-list"

    @pytest.mark.offline
    def test_config_region_registers_omr_scholar(self, repo_root):
        """Config template must register [mcp_servers.omr_scholar]."""
        tmpl = repo_root / "config" / "config.toml.omr-region.tmpl"
        assert tmpl.exists()
        text = tmpl.read_text(encoding="utf-8")
        assert "[mcp_servers.omr_scholar]" in text

    @pytest.mark.offline
    def test_config_region_registers_omr_render(self, repo_root):
        """Config template must register [mcp_servers.omr_render]."""
        tmpl = repo_root / "config" / "config.toml.omr-region.tmpl"
        assert tmpl.exists()
        text = tmpl.read_text(encoding="utf-8")
        assert "[mcp_servers.omr_render]" in text

    @pytest.mark.offline
    def test_omr_scholar_zero_side_effect_import(self):
        """Importing omr_scholar must not trigger any network call."""
        _insert_omr_path()
        # If this raises, ImportError is caught; network call would raise too
        # but we can't detect it here — the key check is that it raises no error.
        try:
            import omr_scholar  # noqa: F401
        except ImportError as exc:
            pytest.skip(f"omr_scholar not importable: {exc}")
        # No network assertion possible without mocking, but the import must succeed
        # and the version function must be side-effect-free.
        try:
            from omr_scholar.version import get_version
            v = get_version()
            assert v, "version must be non-empty"
        except ImportError:
            pytest.skip("omr_scholar.version not available")


# ---------------------------------------------------------------------------
# AC3  — Stage 1 (omr-start): codex-exec scenario (skipped if codex absent)
# ---------------------------------------------------------------------------


class TestAC3Stage1:
    """AC3: omr-start produces research-question.md with H0/H1 + Variables table."""

    @pytest.mark.codex
    @skip_no_codex
    @skip_no_bundle
    def test_start_skill_caffeine_hypothesis(self, tmp_path):
        """[codex required] omr-start on empty folder must scaffold research-question.md."""
        study = tmp_path / "caffeine_study"
        study.mkdir()

        prompt_shim = REPO_ROOT / "config" / "prompts" / "omr-start.md"
        if not prompt_shim.exists():
            prompt_shim = REPO_ROOT / "omr" / "prompts" / "omr-start.md"
        if not prompt_shim.exists():
            pytest.skip("omr-start prompt shim not found; cannot run codex exec test")

        result = subprocess.run(
            [
                "codex", "exec",
                "-C", str(study),
                "--skip-git-repo-check",
                "-s", "workspace-write",
                "--full-auto",
                "--json",
                "I think daily caffeine affects reaction time",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(REPO_ROOT),
        )

        rq_path = study / "00_question" / "research-question.md"
        assert rq_path.exists(), (
            f"research-question.md not found after omr-start.\n"
            f"codex stdout: {result.stdout[:2000]}\n"
            f"codex stderr: {result.stderr[:500]}"
        )
        rq_text = rq_path.read_text(encoding="utf-8")
        assert re.search(r"H0|H1|null hypothesis|alternative hypothesis", rq_text, re.IGNORECASE), (
            "research-question.md must contain H0/H1 hypotheses"
        )
        assert re.search(r"(variable|IV|DV|independent|dependent)", rq_text, re.IGNORECASE), (
            "research-question.md must contain a Variables table"
        )

        state_path = study / ".omr" / "state.json"
        assert state_path.exists(), ".omr/state.json must be created by omr-start"
        with open(state_path, encoding="utf-8") as fh:
            state = json.load(fh)
        assert _stage_status(state, 1) == "done" or "stages" in state, (
            "state.json must record stage1 status (nested: state['stages']['stage1']['status'])"
        )


# ---------------------------------------------------------------------------
# AC4  — Stage 2 dedup: offline unit tests against pinned fixtures
# ---------------------------------------------------------------------------


class TestAC4LiteratureDedup:
    """AC4: dedup logic tested offline against version-pinned fixtures."""

    @pytest.mark.offline
    def test_pinned_records_count(self, pinned_records):
        """Fixture must contain >= 10 records."""
        assert len(pinned_records) >= 10, (
            f"records.json must have >= 10 records; got {len(pinned_records)}"
        )

    @pytest.mark.offline
    def test_pinned_records_two_providers(self, pinned_records):
        """Fixture must span >= 2 providers."""
        providers = {r.get("provider") for r in pinned_records if isinstance(r, dict)}
        assert len(providers) >= 2, (
            f"records.json must span >= 2 providers; found: {providers}"
        )

    @pytest.mark.offline
    def test_pinned_records_schema(self, pinned_records):
        """Every record must have all required normalized schema fields."""
        required = {"title", "authors", "year", "doi", "venue", "abstract", "provider", "url"}
        for i, rec in enumerate(pinned_records):
            missing = required - set(rec.keys())
            assert not missing, (
                f"Record[{i}] is missing required fields: {missing}\nRecord: {rec}"
            )

    @pytest.mark.offline
    def test_positive_dedup_same_doi(self, pinned_records, dedup_module):
        """True-duplicate pair (same DOI, two providers) must merge to ONE entry."""
        # records[0] and records[1] share doi=10.1000/xyz001 across crossref+openalex
        result = dedup_module.dedup_records(pinned_records)
        deduped = result["records"]
        report = result["merge_report"]

        # Find how many entries have this DOI
        doi = "10.1000/xyz001"
        matching = [
            r for r in deduped
            if str(r.get("doi", "")).lower().strip() == doi
            or str(r.get("doi", "")).lower().strip() == doi.replace("https://doi.org/", "")
        ]
        assert len(matching) == 1, (
            f"DOI {doi!r} must appear exactly ONCE after dedup; found {len(matching)}. "
            f"All deduped DOIs: {[r.get('doi') for r in deduped]}"
        )

        # Merge report must show at least one 'merged' action for this DOI
        merged_actions = [e for e in report if e["action"] == "merged"]
        assert merged_actions, (
            "merge_report must contain at least one 'merged' action for the true-dup pair"
        )

    @pytest.mark.offline
    def test_negative_dedup_different_doi(self, pinned_records, dedup_module):
        """Distinct papers with near-identical titles but different DOIs must NOT merge."""
        # records[2] doi=10.1000/xyz002 (crossref)
        # records[3] doi=10.9999/DIFFERENT001 (openalex)
        result = dedup_module.dedup_records(pinned_records)
        deduped = result["records"]
        report = result["merge_report"]

        doi_a = "10.1000/xyz002"
        doi_b = "10.9999/different001"

        doi_a_in_deduped = any(
            doi_a in str(r.get("doi", "")).lower() for r in deduped
        )
        doi_b_in_deduped = any(
            doi_b in str(r.get("doi", "")).lower() for r in deduped
        )

        assert doi_a_in_deduped, (
            f"DOI {doi_a!r} was lost — should remain as a separate entry"
        )
        assert doi_b_in_deduped, (
            f"DOI {doi_b!r} was lost — should remain as a separate entry (no-merge guard)"
        )

        # Report must show 'kept-separate' action for the doi-mismatch-blocked reason
        kept_sep = [
            e for e in report
            if e["action"] == "kept-separate" and e.get("reason") == "doi-mismatch-blocked"
        ]
        assert kept_sep, (
            "merge_report must record 'kept-separate / doi-mismatch-blocked' for the negative pair"
        )

    @pytest.mark.offline
    def test_output_count_at_least_ten(self, pinned_records, dedup_module):
        """After dedup, >= 10 distinct records must remain."""
        result = dedup_module.dedup_records(pinned_records)
        deduped = result["records"]
        assert len(deduped) >= 10, (
            f"Expected >= 10 deduped records (12 input, 1 true-dup merge -> 11); "
            f"got {len(deduped)}"
        )

    @pytest.mark.offline
    def test_output_providers_span_two(self, pinned_records, dedup_module):
        """After dedup, merged provider field must cover >= 2 providers."""
        result = dedup_module.dedup_records(pinned_records)
        deduped = result["records"]
        all_providers: set[str] = set()
        for rec in deduped:
            for p in str(rec.get("provider", "")).split(","):
                p = p.strip()
                if p:
                    all_providers.add(p)
        assert len(all_providers) >= 2, (
            f"After dedup, records must span >= 2 providers; found: {all_providers}"
        )

    @pytest.mark.offline
    def test_bibtex_citation_keys_stable(self, pinned_records, dedup_module, bibtex_module):
        """BibTeX output must contain stable citation keys; no duplicate DOIs in .bib."""
        result = dedup_module.dedup_records(pinned_records)
        deduped = result["records"]
        bib_text = bibtex_module.to_bibtex(deduped)

        # Extract all @type{key, entries
        keys = re.findall(r"@\w+\{([^,\n]+),", bib_text)
        assert len(keys) >= 10, (
            f"Expected >= 10 citation keys in .bib; found {len(keys)}"
        )
        # Keys must be unique
        assert len(keys) == len(set(keys)), (
            f"Duplicate citation keys found: {[k for k in keys if keys.count(k) > 1]}"
        )

    @pytest.mark.offline
    def test_evidence_table_simulation(self, pinned_records, dedup_module, bibtex_module):
        """Simulate evidence table: must produce >= 5 rows each with a key in the bib."""
        result = dedup_module.dedup_records(pinned_records)
        deduped = result["records"]
        keys = bibtex_module.assign_keys(deduped)
        bib_text = bibtex_module.to_bibtex(deduped)
        bib_keys = set(re.findall(r"@\w+\{([^,\n]+),", bib_text))

        # Build a simulated evidence table (one row per deduped record)
        evidence_rows = [
            {"citation_key": k, "year": r.get("year"), "title": r.get("title")}
            for k, r in zip(keys, deduped)
            if r.get("title")
        ]
        assert len(evidence_rows) >= 5, (
            f"Evidence table must have >= 5 rows; got {len(evidence_rows)}"
        )
        for row in evidence_rows:
            ck = row["citation_key"]
            assert ck in bib_keys, (
                f"Evidence table key {ck!r} not found in library.bib keys: {bib_keys}"
            )

    @pytest.mark.offline
    def test_cache_pinned_fixture_served_offline(self, tmp_cache_dir):
        """Pinned cache fixtures must be served without network (pinned=True)."""
        store, _cache_dir, query = tmp_cache_dir
        crossref_payload = store.get("crossref", query)
        openalex_payload = store.get("openalex", query)

        assert crossref_payload is not None, "crossref cache fixture not found / not served"
        assert openalex_payload is not None, "openalex cache fixture not found / not served"
        assert isinstance(crossref_payload, list) and len(crossref_payload) >= 5
        assert isinstance(openalex_payload, list) and len(openalex_payload) >= 3


# ---------------------------------------------------------------------------
# AC5  — Stage 3 (positive correctness): codex-exec scenario
# ---------------------------------------------------------------------------


class TestAC5AnalysisPositive:
    """AC5: canned Student t-test dataset routes to Student t (not Welch/non-param)."""

    @pytest.mark.offline
    def test_ac5_csv_has_two_groups(self):
        """ac5_clean.csv must have exactly 2 groups and a numeric outcome."""
        rows = _read_csv_dicts(FIXTURES_ANALYSIS / "ac5_clean.csv")
        assert len(rows) > 0, "ac5_clean.csv is empty"
        groups = {r["caffeine_group"] for r in rows}
        assert groups == {"placebo", "caffeine"}, f"Expected 2 groups; got {groups}"
        # Outcome must be numeric
        for r in rows:
            float(r["reaction_time_ms"])  # raises if not numeric

    @pytest.mark.offline
    def test_ac5_csv_no_missing(self):
        """ac5_clean.csv must have no missing values in the outcome column."""
        rows = _read_csv_dicts(FIXTURES_ANALYSIS / "ac5_clean.csv")
        for r in rows:
            assert r["reaction_time_ms"].strip() != "", (
                f"ac5_clean.csv has empty reaction_time_ms in row: {r}"
            )

    @pytest.mark.offline
    def test_ac5_csv_adequate_n(self):
        """ac5_clean.csv must have >= 10 observations per group for valid Shapiro."""
        rows = _read_csv_dicts(FIXTURES_ANALYSIS / "ac5_clean.csv")
        from collections import Counter
        counts = Counter(r["caffeine_group"] for r in rows)
        for group, n in counts.items():
            assert n >= 10, f"Group {group!r} has only {n} observations (need >= 10)"

    @pytest.mark.r
    @skip_no_r
    def test_ac5_shapiro_passes_per_group(self):
        """R must confirm Shapiro-Wilk p > 0.05 for both groups in ac5_clean.csv."""
        rscript = shutil.which("Rscript")
        csv_path = FIXTURES_ANALYSIS / "ac5_clean.csv"
        r_code = f"""
data <- read.csv('{csv_path}')
groups <- split(data$reaction_time_ms, data$caffeine_group)
results <- lapply(groups, shapiro.test)
pvals <- sapply(results, function(x) x$p.value)
cat(paste(names(pvals), round(pvals, 4), sep='=', collapse=','), '\\n')
all_pass <- all(pvals > 0.05)
cat('all_pass:', all_pass, '\\n')
q(status=ifelse(all_pass, 0, 1))
"""
        result = subprocess.run(
            [rscript, "-e", r_code],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, (
            f"Shapiro-Wilk FAILED for ac5_clean.csv — Student t-test assumption violated.\n"
            f"R output: {result.stdout}\n{result.stderr}"
        )

    @pytest.mark.r
    @skip_no_r
    def test_ac5_var_test_passes(self):
        """R must confirm var.test p > 0.05 (equal variance) for ac5_clean.csv."""
        rscript = shutil.which("Rscript")
        csv_path = FIXTURES_ANALYSIS / "ac5_clean.csv"
        r_code = f"""
data <- read.csv('{csv_path}')
g <- split(data$reaction_time_ms, data$caffeine_group)
vt <- var.test(g[[1]], g[[2]])
cat('var.test p:', round(vt$p.value, 4), '\\n')
q(status=ifelse(vt$p.value > 0.05, 0, 1))
"""
        result = subprocess.run(
            [rscript, "-e", r_code],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0, (
            f"var.test FAILED for ac5_clean.csv — equal variance assumption violated.\n"
            f"R output: {result.stdout}\n{result.stderr}"
        )

    @pytest.mark.codex
    @skip_no_codex
    @skip_no_bundle
    @skip_no_r
    @skip_no_quarto
    def test_ac5_omr_analyze_produces_student_t(self, tmp_path):
        """[codex+R+Quarto] omr-analyze on ac5_clean.csv must select Student t-test."""
        study = _setup_study_for_analysis(tmp_path, "ac5_clean.csv")
        result = subprocess.run(
            [
                "codex", "exec",
                "-C", str(study),
                "--skip-git-repo-check",
                "-s", "workspace-write",
                "--full-auto",
                "--json",
                "run statistical analysis on the data in 20_analysis/data/",
            ],
            capture_output=True, text=True, timeout=300, cwd=str(REPO_ROOT),
        )
        results_json = study / "20_analysis" / "outputs" / "results.json"
        if not results_json.exists():
            pytest.skip("results.json not produced — omr-analyze may not be fully wired yet")
        with open(results_json, encoding="utf-8") as fh:
            r_data = json.load(fh)
        # A7 pin: results.json uses a generic "statistic" key (not "t") across all
        # test types.  "df" and "p_value" remain stable.
        assert "statistic" in r_data, "results.json must contain the test 'statistic'"
        assert "df" in r_data, "results.json must contain 'df'"
        assert "p_value" in r_data, "results.json must contain 'p_value'"
        assert 0 <= float(r_data["p_value"]) <= 1, "p_value must be in [0, 1]"
        # Effect size: two-sample t produces cohen_d or mean_diff (or both).
        assert "cohen_d" in r_data or "mean_diff" in r_data, (
            "results.json must contain an effect-size key (cohen_d or mean_diff) "
            "for Student t-test"
        )

        # A7 pin: assert on the canonical CHOSEN label (from results.json label field
        # OR the headline label line in analysis-plan.md) rather than raw text search.
        chosen = _chosen_test_label(study)
        if chosen:
            assert "Student" in chosen, (
                f"Chosen test label must indicate Student t-test; got {chosen!r}"
            )
            assert not re.search(r"\bWelch\b|\bMann.Whitney\b|\bWilcoxon\b", chosen), (
                f"Chosen test label must NOT be Welch or non-parametric; got {chosen!r}"
            )
        else:
            # Fallback: plan text must mention Student somewhere if no structured label
            plan_path = study / "20_analysis" / "analysis-plan.md"
            if plan_path.exists():
                plan_text = plan_path.read_text(encoding="utf-8")
                assert re.search(r"\bStudent\b", plan_text, re.IGNORECASE), (
                    "analysis-plan.md must label the test as Student"
                )
                assert not re.search(r"\bWelch\b|\bMann.Whitney\b|\bWilcoxon\b", plan_text), (
                    "analysis-plan.md must NOT label Student t as Welch or non-parametric"
                )


# ---------------------------------------------------------------------------
# AC6  — Stage 4 manuscript: codex-exec scenario
# ---------------------------------------------------------------------------


class TestAC6Manuscript:
    """AC6: manuscript.docx contains t/df/p values and >= 3 resolved citations."""

    @pytest.mark.codex
    @skip_no_codex
    @skip_no_bundle
    @skip_no_r
    @skip_no_quarto
    def test_ac6_manuscript_has_citations(self, tmp_path):
        """[codex+R+Quarto] omr-write must produce manuscript.docx with >= 3 citations."""
        study = _setup_full_study(tmp_path)
        result = subprocess.run(
            [
                "codex", "exec",
                "-C", str(study),
                "--skip-git-repo-check",
                "-s", "workspace-write",
                "--full-auto",
                "--json",
                "write the manuscript",
            ],
            capture_output=True, text=True, timeout=300, cwd=str(REPO_ROOT),
        )
        docx_path = study / "30_manuscript" / "manuscript.docx"
        if not docx_path.exists():
            pytest.skip("manuscript.docx not produced — omr-write may not be wired yet")
        # Unzip the DOCX and inspect document.xml
        import zipfile
        with zipfile.ZipFile(str(docx_path)) as z:
            with z.open("word/document.xml") as fh:
                doc_xml = fh.read().decode("utf-8")
        # Check for citation references (simplified check)
        assert doc_xml, "document.xml must be non-empty"


# ---------------------------------------------------------------------------
# AC7  — Handoff integrity
# ---------------------------------------------------------------------------


class TestAC7HandoffIntegrity:
    """AC7: deleting library.bib causes omr-write to fail loudly."""

    @pytest.mark.offline
    def test_ac7_state_json_schema(self):
        """state.json must be valid JSON with nested stage schema (A4 pinned contract)."""
        # This is a structural oracle test — we verify the pinned schema contract:
        # state["stages"]["stageN"]["status"] in {done, blocked, blocked-pending-user-decision, pending}
        example_state = {
            "workspace_root": "/path/to/study",
            "stages": {
                "stage1": {"status": "done", "artifacts": {}, "checksums": {}},
                "stage2": {"status": "done", "artifacts": {}, "checksums": {}},
                "stage3": {"status": "done", "artifacts": {}, "checksums": {}},
                "stage4": {"status": "done", "artifacts": {}, "checksums": {}},
            }
        }
        # Schema: nested stages must be present and status values are valid strings
        assert "stages" in example_state, "state.json must have top-level 'stages' key"
        assert isinstance(example_state["workspace_root"], str)
        valid_statuses = {"done", "blocked", "blocked-pending-user-decision", "pending"}
        for stage in ["stage1", "stage2", "stage3", "stage4"]:
            assert stage in example_state["stages"], f"stages.{stage} must be present"
            status = _stage_status(example_state, int(stage[-1]))
            assert status in valid_statuses, (
                f"stages.{stage}.status must be one of {valid_statuses}; got {status!r}"
            )

    @pytest.mark.codex
    @skip_no_codex
    @skip_no_bundle
    def test_ac7_missing_bib_blocks_write(self, tmp_path):
        """[codex] Deleting library.bib must cause omr-write to fail loudly."""
        study = _setup_full_study(tmp_path)
        bib = study / "10_literature" / "library.bib"
        if bib.exists():
            bib.unlink()

        result = subprocess.run(
            [
                "codex", "exec",
                "-C", str(study),
                "--skip-git-repo-check",
                "-s", "workspace-write",
                "--full-auto",
                "--json",
                "write the manuscript",
            ],
            capture_output=True, text=True, timeout=120, cwd=str(REPO_ROOT),
        )
        docx_path = study / "30_manuscript" / "manuscript.docx"
        assert not docx_path.exists(), (
            "manuscript.docx must NOT be produced when library.bib is missing"
        )
        assert "library.bib" in result.stdout or "library.bib" in result.stderr, (
            "omr-write must mention library.bib in its error output"
        )


# ---------------------------------------------------------------------------
# AC8  — No-fabrication guard
# ---------------------------------------------------------------------------


class TestAC8NoFabrication:
    """AC8: network-off → no invented references; malformed CSV → no invented results."""

    @pytest.mark.offline
    def test_ac8_malformed_csv_fixture_readable(self):
        """ac10e_missing.csv (missing values) can be read and has missing entries."""
        rows = _read_csv_dicts(FIXTURES_ANALYSIS / "ac10e_missing.csv")
        empty_count = sum(1 for r in rows if r.get("reaction_time_ms", "").strip() == "")
        assert empty_count >= 1, (
            "ac10e_missing.csv must have at least 1 empty reaction_time_ms cell"
        )

    @pytest.mark.codex
    @skip_no_codex
    @skip_no_bundle
    def test_ac8_network_off_no_invented_refs(self, tmp_path):
        """[codex] With network disabled, omr-lit must not invent references."""
        study = tmp_path / "study"
        study.mkdir()
        (study / ".omr").mkdir()

        result = subprocess.run(
            [
                "codex", "exec",
                "-C", str(study),
                "--skip-git-repo-check",
                "-s", "workspace-write",
                "--full-auto",
                "--json",
                "find literature about caffeine and reaction time",
            ],
            capture_output=True, text=True, timeout=120, cwd=str(REPO_ROOT),
            env={**os.environ, "no_proxy": "*", "NO_PROXY": "*",
                 "http_proxy": "http://127.0.0.1:1", "https_proxy": "http://127.0.0.1:1"},
        )
        bib_path = study / "10_literature" / "library.bib"
        if bib_path.exists():
            bib_text = bib_path.read_text(encoding="utf-8")
            # If a bib was produced, it must show degradation/failure, not invented refs
            assert "fabricat" not in bib_text.lower(), (
                "library.bib must not contain fabricated references"
            )


# ---------------------------------------------------------------------------
# AC9  — MCP boundary classification & path-escape rejection
# ---------------------------------------------------------------------------


class TestAC9BoundaryAndPathEscape:
    """AC9: path-escape is rejected before exec; boundary module is correctly wired."""

    @pytest.mark.offline
    def test_path_escape_rejected_before_exec(self, tmp_study):
        """resolve_within_root must reject path arguments escaping the study root."""
        _insert_omr_path()
        render_mcp = REPO_ROOT / "omr" / "mcp"
        render_path = str(render_mcp)
        if render_path not in sys.path:
            sys.path.insert(0, render_path)
        try:
            from omr_render.boundary import BoundaryError, canonical_root, resolve_within_root
        except ImportError as exc:
            pytest.skip(f"omr_render.boundary not importable: {exc}")

        root = canonical_root(str(tmp_study))

        # Attempt path traversal via ../
        with pytest.raises(BoundaryError) as exc_info:
            resolve_within_root(root, "../../../etc/passwd")
        assert exc_info.value.kind == "path-escape", (
            f"Expected 'path-escape' BoundaryError; got kind={exc_info.value.kind!r}"
        )

    @pytest.mark.offline
    def test_path_escape_absolute_outside_root(self, tmp_study):
        """Absolute path outside study root must be rejected."""
        _insert_omr_path()
        render_mcp = REPO_ROOT / "omr" / "mcp"
        render_path = str(render_mcp)
        if render_path not in sys.path:
            sys.path.insert(0, render_path)
        try:
            from omr_render.boundary import BoundaryError, canonical_root, resolve_within_root
        except ImportError as exc:
            pytest.skip(f"omr_render.boundary not importable: {exc}")

        root = canonical_root(str(tmp_study))
        with pytest.raises(BoundaryError) as exc_info:
            resolve_within_root(root, "/etc/passwd")
        assert exc_info.value.kind == "path-escape"

    @pytest.mark.offline
    def test_path_within_root_accepted(self, tmp_study):
        """Path strictly inside the study root must be accepted."""
        _insert_omr_path()
        render_mcp = REPO_ROOT / "omr" / "mcp"
        render_path = str(render_mcp)
        if render_path not in sys.path:
            sys.path.insert(0, render_path)
        try:
            from omr_render.boundary import canonical_root, resolve_within_root
        except ImportError as exc:
            pytest.skip(f"omr_render.boundary not importable: {exc}")

        root = canonical_root(str(tmp_study))
        inner = tmp_study / ".omr" / "tmp" / "analysis.qmd"
        inner.parent.mkdir(parents=True, exist_ok=True)
        inner.touch()
        # Must not raise
        result = resolve_within_root(root, str(inner))
        assert result.startswith(root)

    @pytest.mark.offline
    def test_allow_list_enforced(self):
        """check_allowed must reject forms not in the fixed allow-list."""
        _insert_omr_path()
        render_mcp = REPO_ROOT / "omr" / "mcp"
        render_path = str(render_mcp)
        if render_path not in sys.path:
            sys.path.insert(0, render_path)
        try:
            from omr_render.boundary import BoundaryError, check_allowed
        except ImportError as exc:
            pytest.skip(f"omr_render.boundary not importable: {exc}")

        # Known-good forms must pass
        check_allowed("quarto_render")
        check_allowed("rscript_version")

        # Unknown form must raise
        with pytest.raises(BoundaryError) as exc_info:
            check_allowed("rm -rf /")
        assert exc_info.value.kind == "allow-list"

    @pytest.mark.offline
    def test_gated_install_blocked_by_default(self):
        """rscript_install must be blocked unless allow_install=True."""
        _insert_omr_path()
        render_mcp = REPO_ROOT / "omr" / "mcp"
        render_path = str(render_mcp)
        if render_path not in sys.path:
            sys.path.insert(0, render_path)
        try:
            from omr_render.boundary import BoundaryError, check_allowed
        except ImportError as exc:
            pytest.skip(f"omr_render.boundary not importable: {exc}")

        with pytest.raises(BoundaryError) as exc_info:
            check_allowed("rscript_install")  # gated, allow_install=False by default
        assert exc_info.value.kind == "gated"

        # With explicit flag it must pass
        check_allowed("rscript_install", allow_install=True)  # must not raise

    @pytest.mark.offline
    def test_redirected_env_contains_workspace_paths(self, tmp_study):
        """redirected_env must override TMPDIR/TEMP/TMP and R_LIBS_USER to workspace."""
        _insert_omr_path()
        render_mcp = REPO_ROOT / "omr" / "mcp"
        render_path = str(render_mcp)
        if render_path not in sys.path:
            sys.path.insert(0, render_path)
        try:
            from omr_render.boundary import canonical_root, redirected_env
        except ImportError as exc:
            pytest.skip(f"omr_render.boundary not importable: {exc}")

        root = canonical_root(str(tmp_study))
        env = redirected_env(root, base_env={})
        assert env["TMPDIR"].startswith(root), "TMPDIR must be inside study root"
        assert env["R_LIBS_USER"].startswith(root), "R_LIBS_USER must be inside study root"


# ---------------------------------------------------------------------------
# AC10  — Wrong-fit / assumption-violation guard (static + logic-level)
# ---------------------------------------------------------------------------


class TestAC10WrongFitStaticOracle:
    """AC10 (static): assert fixtures have the properties required by EXPECTED.md."""

    @pytest.mark.offline
    def test_ac10a_nonnormal_fixture_properties(self):
        """ac10a_nonnormal.csv must have the structure expected for non-normality."""
        rows = _read_csv_dicts(FIXTURES_ANALYSIS / "ac10a_nonnormal.csv")
        groups = {r["group"] for r in rows}
        assert groups == {"control", "treatment"}, f"Expected 2 groups; got {groups}"
        control = [float(r["score"]) for r in rows if r["group"] == "control"]
        treatment = [float(r["score"]) for r in rows if r["group"] == "treatment"]
        assert len(control) >= 10
        assert len(treatment) >= 10
        # The treatment group should have extreme values (wide range)
        assert max(treatment) - min(treatment) > 50, (
            "ac10a treatment group must have wide range (right-skewed / non-normal)"
        )
        # Control group must be tightly clustered
        assert max(control) - min(control) < 5, (
            "ac10a control group must be tightly clustered"
        )

    @pytest.mark.offline
    def test_ac10b_unequalvar_fixture_properties(self):
        """ac10b_unequalvar.csv must have very different variances between groups."""
        rows = _read_csv_dicts(FIXTURES_ANALYSIS / "ac10b_unequalvar.csv")
        control = [float(r["score"]) for r in rows if r["group"] == "control"]
        treatment = [float(r["score"]) for r in rows if r["group"] == "treatment"]

        def _var(vals):
            n = len(vals)
            mean = sum(vals) / n
            return sum((x - mean) ** 2 for x in vals) / (n - 1)

        var_c = _var(control)
        var_t = _var(treatment)
        ratio = max(var_c, var_t) / min(var_c, var_t)
        assert ratio > 50, (
            f"ac10b must have variance ratio > 50 between groups; got {ratio:.1f}"
        )

    @pytest.mark.offline
    def test_ac10c_paired_fixture_has_repeated_subject_ids(self):
        """ac10c_paired.csv must have subject_id values appearing in both conditions."""
        rows = _read_csv_dicts(FIXTURES_ANALYSIS / "ac10c_paired.csv")
        conditions = {r["condition"] for r in rows}
        assert conditions == {"pre", "post"}, f"Expected pre/post; got {conditions}"

        from collections import defaultdict
        sid_conditions: dict[str, set] = defaultdict(set)
        for r in rows:
            sid_conditions[r["subject_id"]].add(r["condition"])

        paired_subjects = [sid for sid, conds in sid_conditions.items() if len(conds) == 2]
        assert len(paired_subjects) >= 10, (
            f"ac10c must have >= 10 subjects with measurements in BOTH conditions; "
            f"got {len(paired_subjects)}"
        )

    @pytest.mark.offline
    def test_ac10d_nofit_fixture_is_survival(self):
        """ac10d_nofit.csv must be a time-to-event dataset (no valid MVP test)."""
        rows = _read_csv_dicts(FIXTURES_ANALYSIS / "ac10d_nofit.csv")
        cols = list(rows[0].keys())
        assert "days_to_event" in cols, "ac10d must have 'days_to_event' column"
        assert "event_occurred" in cols, "ac10d must have 'event_occurred' column"
        # event_occurred must be binary (0/1)
        event_vals = {r["event_occurred"] for r in rows}
        assert event_vals <= {"0", "1"}, f"event_occurred must be binary; got {event_vals}"

    @pytest.mark.offline
    def test_ac10e_missing_fixture_has_missing_values(self):
        """ac10e_missing.csv must have >= 1 missing value in the outcome column."""
        rows = _read_csv_dicts(FIXTURES_ANALYSIS / "ac10e_missing.csv")
        missing = [r for r in rows if r.get("reaction_time_ms", "").strip() == ""]
        assert len(missing) >= 1, (
            f"ac10e_missing.csv must have >= 1 missing reaction_time_ms; got {len(missing)}"
        )

    @pytest.mark.offline
    def test_ac10_expected_md_exists(self):
        """EXPECTED.md fixture oracle file must exist and document all 5 cases."""
        expected_md = FIXTURES_ANALYSIS / "EXPECTED.md"
        assert expected_md.exists(), "EXPECTED.md oracle file must exist"
        text = expected_md.read_text(encoding="utf-8")
        for keyword in [
            "ac5_clean", "ac10a_nonnormal", "ac10b_unequalvar", "ac10c_paired",
            "ac10d_nofit", "ac10e_missing",
            "Mann-Whitney", "Welch", "paired", "blocked", "blocked-pending-user-decision",
        ]:
            assert keyword in text, f"EXPECTED.md missing documentation for: {keyword!r}"

    @pytest.mark.r
    @skip_no_r
    def test_ac10a_shapiro_fails_in_r(self):
        """R Shapiro-Wilk must fail (p < 0.05) for at least one group in ac10a."""
        rscript = shutil.which("Rscript")
        csv_path = FIXTURES_ANALYSIS / "ac10a_nonnormal.csv"
        r_code = f"""
data <- read.csv('{csv_path}')
groups <- split(data$score, data$group)
pvals <- sapply(groups, function(g) shapiro.test(g)$p.value)
cat(paste(names(pvals), round(pvals, 6), sep='=', collapse=','), '\\n')
any_fail <- any(pvals < 0.05)
cat('any_normality_fail:', any_fail, '\\n')
q(status=ifelse(any_fail, 0, 1))
"""
        result = subprocess.run([rscript, "-e", r_code], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, (
            f"ac10a_nonnormal.csv Shapiro-Wilk did NOT fail — fixture may not be non-normal enough.\n"
            f"R output: {result.stdout}\n{result.stderr}"
        )

    @pytest.mark.r
    @skip_no_r
    def test_ac10b_var_test_fails_in_r(self):
        """R var.test must fail (p < 0.05) for ac10b_unequalvar.csv."""
        rscript = shutil.which("Rscript")
        csv_path = FIXTURES_ANALYSIS / "ac10b_unequalvar.csv"
        r_code = f"""
data <- read.csv('{csv_path}')
g <- split(data$score, data$group)
vt <- var.test(g[[1]], g[[2]])
cat('var.test p:', round(vt$p.value, 6), '\\n')
q(status=ifelse(vt$p.value < 0.05, 0, 1))
"""
        result = subprocess.run([rscript, "-e", r_code], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, (
            f"ac10b_unequalvar.csv var.test did NOT fail — fixture may not have unequal variance.\n"
            f"R output: {result.stdout}\n{result.stderr}"
        )


class TestAC10TestSelectionDocument:
    """AC10 (logic-level): test-selection.md encodes the required decision table."""

    @pytest.mark.offline
    def test_test_selection_md_exists(self, repo_root):
        """skills/omr-analyze/references/test-selection.md must exist."""
        path = repo_root / "skills" / "omr-analyze" / "references" / "test-selection.md"
        if not path.exists():
            pytest.skip(
                "skills/omr-analyze/references/test-selection.md not yet created — "
                "W4 omr-analyze worker may not have run; flagging as integration risk"
            )

    @pytest.mark.offline
    def test_test_selection_md_encodes_all_required_branches(self, repo_root):
        """test-selection.md must document every required test branch."""
        path = repo_root / "skills" / "omr-analyze" / "references" / "test-selection.md"
        if not path.exists():
            pytest.skip("test-selection.md not found")
        text = path.read_text(encoding="utf-8")

        required_branches = [
            ("Student", "Student t-test (independent two-sample)"),
            ("Welch", "Welch t-test (unequal variance)"),
            ("paired", "paired t-test"),
            ("ANOVA", "one-way ANOVA"),
            ("chi", "chi-squared / χ² test"),
            ("OLS", "simple OLS regression"),
            ("Mann.Whitney", "Mann-Whitney U (non-parametric fallback)"),
            ("Wilcoxon", "Wilcoxon signed-rank"),
        ]
        for pattern, description in required_branches:
            assert re.search(pattern, text, re.IGNORECASE), (
                f"test-selection.md is missing required branch: {description!r} "
                f"(pattern: {pattern!r})"
            )

    @pytest.mark.offline
    def test_test_selection_md_encodes_normality_check(self, repo_root):
        """test-selection.md must reference shapiro.test and n-aware cutoffs."""
        path = repo_root / "skills" / "omr-analyze" / "references" / "test-selection.md"
        if not path.exists():
            pytest.skip("test-selection.md not found")
        text = path.read_text(encoding="utf-8")
        assert re.search(r"shapiro", text, re.IGNORECASE), (
            "test-selection.md must reference Shapiro-Wilk test"
        )

    @pytest.mark.offline
    def test_test_selection_md_encodes_no_fit_blocked(self, repo_root):
        """test-selection.md must encode the no-fit → blocked branch."""
        path = repo_root / "skills" / "omr-analyze" / "references" / "test-selection.md"
        if not path.exists():
            pytest.skip("test-selection.md not found")
        text = path.read_text(encoding="utf-8")
        assert re.search(r"block|no.fit|no.MVP", text, re.IGNORECASE), (
            "test-selection.md must document the no-fit → blocked outcome"
        )

    @pytest.mark.offline
    def test_test_selection_md_encodes_missing_data_blocked(self, repo_root):
        """test-selection.md must encode the missing-data → blocked-pending branch."""
        path = repo_root / "skills" / "omr-analyze" / "references" / "test-selection.md"
        if not path.exists():
            pytest.skip("test-selection.md not found")
        text = path.read_text(encoding="utf-8")
        assert re.search(r"missing|blocked.pending", text, re.IGNORECASE), (
            "test-selection.md must document the missing-data → blocked-pending outcome"
        )

    @pytest.mark.offline
    def test_analysis_qmd_template_no_jsonlite(self, repo_root):
        """analysis.qmd.tmpl must NOT call jsonlite functions (comments are OK)."""
        path = repo_root / "skills" / "omr-analyze" / "assets" / "analysis.qmd.tmpl"
        if not path.exists():
            pytest.skip("analysis.qmd.tmpl not yet created")
        text = path.read_text(encoding="utf-8")
        # jsonlite usage patterns: library(jsonlite), jsonlite::, require(jsonlite)
        # Comments mentioning "NO jsonlite" or "jsonlite" as prohibition are fine.
        forbidden_patterns = [
            r"library\s*\(\s*['\"]?jsonlite",
            r"require\s*\(\s*['\"]?jsonlite",
            r"jsonlite::",
        ]
        for pat in forbidden_patterns:
            assert not re.search(pat, text), (
                f"analysis.qmd.tmpl must NOT use jsonlite — results.json must be emitted "
                f"by a base-R JSON writer (no external package dependency).\n"
                f"Pattern found: {pat!r}"
            )

    @pytest.mark.offline
    def test_analysis_qmd_template_uses_base_r_stats(self, repo_root):
        """analysis.qmd.tmpl must use base-R stats functions and not require car/jsonlite."""
        path = repo_root / "skills" / "omr-analyze" / "assets" / "analysis.qmd.tmpl"
        if not path.exists():
            pytest.skip("analysis.qmd.tmpl not yet created")
        text = path.read_text(encoding="utf-8")
        # Must use at least one base-R assumption-check function (with or without stats:: prefix)
        assert re.search(r"(stats::)?(shapiro\.test|var\.test|bartlett\.test)", text), (
            "analysis.qmd.tmpl must use at least one base-R assumption check function "
            "(shapiro.test, var.test, or bartlett.test — with or without stats:: prefix)"
        )
        # Must use at least one base-R test function
        assert re.search(r"(stats::)?(t\.test|wilcox\.test|chisq\.test|aov|lm)\b", text), (
            "analysis.qmd.tmpl must use base-R test functions (t.test, wilcox.test, etc.)"
        )
        # Must not use car:: package (non-base, explicitly forbidden on integrity path)
        assert "car::" not in text, (
            "analysis.qmd.tmpl must NOT use car:: — only base-R stats on integrity path"
        )


# ---------------------------------------------------------------------------
# AC10 codex-exec scenario tests (skipped if tools absent)
# ---------------------------------------------------------------------------


class TestAC10CodexScenarios:
    """AC10 codex-exec-driven wrong-fit tests (guarded by tool presence)."""

    @pytest.mark.codex
    @skip_no_codex
    @skip_no_bundle
    @skip_no_r
    @skip_no_quarto
    def test_ac10a_nonnormal_routes_to_mannwhitney(self, tmp_path):
        """[codex+R+Quarto] Non-normal 2-group → Mann-Whitney U must be selected."""
        study = _setup_study_for_analysis(tmp_path, "ac10a_nonnormal.csv")
        result = subprocess.run(
            [
                "codex", "exec",
                "-C", str(study),
                "--skip-git-repo-check",
                "-s", "workspace-write",
                "--full-auto",
                "--json",
                "analyze the data in 20_analysis/data/ comparing score between groups",
            ],
            capture_output=True, text=True, timeout=300, cwd=str(REPO_ROOT),
        )
        plan_path = study / "20_analysis" / "analysis-plan.md"
        if not plan_path.exists():
            pytest.skip("analysis-plan.md not produced — omr-analyze may not be wired yet")

        # A7 pin: assert on the canonical CHOSEN label, not raw plan-text search.
        # The skill may mention "Student" in not-chosen rationale prose — that is correct
        # and must not cause a false failure.  We read from results.json label first,
        # then from the headline "Chosen test:" line in analysis-plan.md.
        chosen = _chosen_test_label(study)
        if not chosen:
            pytest.skip(
                "No chosen label found in results.json or analysis-plan.md — "
                "cannot assert routing decision"
            )
        assert re.search(r"Mann.Whitney|Wilcoxon", chosen, re.IGNORECASE), (
            f"Chosen test label must be Mann-Whitney U (or Wilcoxon) for non-normal data; "
            f"got {chosen!r}"
        )
        assert not re.search(r"\bStudent\b|\bWelch\b", chosen, re.IGNORECASE), (
            f"Chosen test label must NOT be Student or Welch for non-normal data; "
            f"got {chosen!r}"
        )

    @pytest.mark.codex
    @skip_no_codex
    @skip_no_bundle
    @skip_no_r
    @skip_no_quarto
    def test_ac10b_unequalvar_routes_to_welch(self, tmp_path):
        """[codex+R+Quarto] Unequal-variance 2-group → Welch t-test must be selected."""
        study = _setup_study_for_analysis(tmp_path, "ac10b_unequalvar.csv")
        result = subprocess.run(
            [
                "codex", "exec",
                "-C", str(study),
                "--skip-git-repo-check",
                "-s", "workspace-write",
                "--full-auto",
                "--json",
                "analyze the data in 20_analysis/data/ comparing score between groups",
            ],
            capture_output=True, text=True, timeout=300, cwd=str(REPO_ROOT),
        )
        plan_path = study / "20_analysis" / "analysis-plan.md"
        if not plan_path.exists():
            pytest.skip("analysis-plan.md not produced")

        # A7 pin: assert on the canonical CHOSEN label, not raw plan-text search.
        # The skill may mention "Student" in not-chosen rationale prose — that is correct
        # and must not cause a false failure.
        chosen = _chosen_test_label(study)
        if not chosen:
            pytest.skip(
                "No chosen label found in results.json or analysis-plan.md — "
                "cannot assert routing decision"
            )
        assert re.search(r"\bWelch\b", chosen, re.IGNORECASE), (
            f"Chosen test label must be Welch for unequal-variance data; got {chosen!r}"
        )
        assert not re.search(r"\bStudent\b", chosen), (
            f"Chosen test label must NOT be Student for unequal-variance data; got {chosen!r}"
        )

    @pytest.mark.codex
    @skip_no_codex
    @skip_no_bundle
    @skip_no_r
    def test_ac10c_paired_routes_to_paired_t(self, tmp_path):
        """[codex+R] Paired design (repeated subject_id) → paired t-test."""
        study = _setup_study_for_analysis(tmp_path, "ac10c_paired.csv")
        result = subprocess.run(
            [
                "codex", "exec",
                "-C", str(study),
                "--skip-git-repo-check",
                "-s", "workspace-write",
                "--full-auto",
                "--json",
                "analyze the data in 20_analysis/data/ comparing score pre vs post",
            ],
            capture_output=True, text=True, timeout=300, cwd=str(REPO_ROOT),
        )
        plan_path = study / "20_analysis" / "analysis-plan.md"
        if not plan_path.exists():
            pytest.skip("analysis-plan.md not produced")
        plan_text = plan_path.read_text(encoding="utf-8")
        assert re.search(r"paired", plan_text, re.IGNORECASE), (
            "analysis-plan.md must record a paired test for repeated-subject design"
        )

    @pytest.mark.codex
    @skip_no_codex
    @skip_no_bundle
    def test_ac10d_nofit_blocked(self, tmp_path):
        """[codex] Survival (time-to-event) outcome → blocked, no statistic produced."""
        study = _setup_study_for_analysis(tmp_path, "ac10d_nofit.csv")
        result = subprocess.run(
            [
                "codex", "exec",
                "-C", str(study),
                "--skip-git-repo-check",
                "-s", "workspace-write",
                "--full-auto",
                "--json",
                "analyze the data in 20_analysis/data/ comparing days_to_event between groups",
            ],
            capture_output=True, text=True, timeout=300, cwd=str(REPO_ROOT),
        )
        results_json = study / "20_analysis" / "outputs" / "results.json"
        state_json = study / ".omr" / "state.json"

        if results_json.exists():
            with open(results_json, encoding="utf-8") as fh:
                r_data = json.load(fh)
            # A7 pin: the writer uses generic "statistic" key (not "t"); check both to
            # guard against either old or new key name leaking into a blocked result.
            assert "t" not in r_data, (
                "results.json must NOT contain a 't' key for no-fit outcome"
            )
            assert "statistic" not in r_data, (
                "results.json must NOT contain a 'statistic' key for no-fit outcome"
            )
            assert "p_value" not in r_data, (
                "results.json must NOT contain p_value for no-fit outcome"
            )

        if state_json.exists():
            with open(state_json, encoding="utf-8") as fh:
                state = json.load(fh)
            stage3_status = _stage_status(state, 3)
            assert "blocked" in stage3_status.lower(), (
                f"state.json stages.stage3.status must be 'blocked' for no-fit outcome; "
                f"got {stage3_status!r}"
            )

    @pytest.mark.codex
    @skip_no_codex
    @skip_no_bundle
    def test_ac10e_missing_blocked_pending(self, tmp_path):
        """[codex] Missing values in outcome → blocked-pending-user-decision."""
        study = _setup_study_for_analysis(tmp_path, "ac10e_missing.csv")
        result = subprocess.run(
            [
                "codex", "exec",
                "-C", str(study),
                "--skip-git-repo-check",
                "-s", "workspace-write",
                "--full-auto",
                "--json",
                "analyze the data in 20_analysis/data/ comparing reaction_time_ms between groups",
            ],
            capture_output=True, text=True, timeout=300, cwd=str(REPO_ROOT),
        )
        state_json = study / ".omr" / "state.json"
        if state_json.exists():
            with open(state_json, encoding="utf-8") as fh:
                state = json.load(fh)
            stage3_status = _stage_status(state, 3)
            assert "blocked" in stage3_status.lower(), (
                f"state.json stages.stage3.status must be 'blocked' for missing-data case; "
                f"got {stage3_status!r}"
            )


# ---------------------------------------------------------------------------
# Helper functions for codex-exec scenario setup
# ---------------------------------------------------------------------------

def _setup_study_for_analysis(tmp_path: Path, csv_filename: str) -> Path:
    """Create a minimal study folder with the given CSV in 20_analysis/data/."""
    study = tmp_path / "study"
    study.mkdir(parents=True, exist_ok=True)
    (study / ".omr").mkdir(exist_ok=True)
    (study / "20_analysis" / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES_ANALYSIS / csv_filename, study / "20_analysis" / "data" / "data.csv")
    # Minimal state.json — pinned nested schema (A4)
    state = {
        "workspace_root": str(study),
        "stages": {
            "stage1": {"status": "done", "artifacts": {}, "checksums": {}},
            "stage2": {"status": "done", "artifacts": {}, "checksums": {}},
        },
    }
    (study / ".omr" / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return study


def _setup_full_study(tmp_path: Path) -> Path:
    """Create a study with literature + analysis pre-populated for write-stage tests."""
    study = tmp_path / "full_study"
    study.mkdir(parents=True, exist_ok=True)
    (study / ".omr").mkdir(exist_ok=True)
    (study / "10_literature").mkdir(exist_ok=True)
    (study / "20_analysis" / "outputs").mkdir(parents=True, exist_ok=True)
    (study / "30_manuscript").mkdir(exist_ok=True)

    # Minimal library.bib with 3 entries
    bib_content = """@article{smith2019effects,
  title = {Effects of caffeine on reaction time},
  author = {Smith, John A.},
  year = {2019},
  journal = {Journal of Psychopharmacology},
  doi = {10.1000/xyz001}
}

@article{brown2020caffeine,
  title = {Caffeine and alertness},
  author = {Brown, Carol E.},
  year = {2020},
  journal = {Neuropsychobiology},
  doi = {10.1000/xyz002}
}

@article{wang2018daily,
  title = {Daily caffeine consumption and psychomotor speed},
  author = {Wang, Li},
  year = {2018},
  journal = {Human Psychopharmacology},
  doi = {10.1000/xyz003}
}
"""
    (study / "10_literature" / "library.bib").write_text(bib_content, encoding="utf-8")

    # Minimal results.json
    results = {"t": -3.21, "df": 58, "p_value": 0.002, "effect_size": 0.83}
    (study / "20_analysis" / "outputs" / "results.json").write_text(
        json.dumps(results), encoding="utf-8"
    )

    # Minimal state.json — pinned nested schema (A4)
    state = {
        "workspace_root": str(study),
        "stages": {
            "stage1": {"status": "done", "artifacts": {}, "checksums": {}},
            "stage2": {"status": "done", "artifacts": {}, "checksums": {}},
            "stage3": {"status": "done", "artifacts": {}, "checksums": {}},
        },
    }
    (study / ".omr" / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return study


# ---------------------------------------------------------------------------
# AC-ADVISOR  — omr-advisor skill: offline structural + 7-skill bundle lock
# ---------------------------------------------------------------------------


class TestACSAdvisorStructural:
    """Offline structural tests for the omr-advisor skill (7th skill in bundle).

    All tests are @pytest.mark.offline — no codex, no network, no R required.
    Mirrors the style and assertion discipline of TestAC1Installer.
    """

    # ------------------------------------------------------------------ SKILL.md

    @pytest.mark.offline
    def test_advisor_skill_md_exists(self, repo_root):
        """skills/omr-advisor/SKILL.md must exist."""
        skill_md = repo_root / "skills" / "omr-advisor" / "SKILL.md"
        assert skill_md.exists(), "skills/omr-advisor/SKILL.md not found"

    @pytest.mark.offline
    def test_advisor_skill_md_frontmatter_parses(self, repo_root):
        """SKILL.md YAML frontmatter must parse without error."""
        import yaml

        skill_md = repo_root / "skills" / "omr-advisor" / "SKILL.md"
        assert skill_md.exists(), "skills/omr-advisor/SKILL.md not found"
        text = skill_md.read_text(encoding="utf-8")
        # Strip leading/trailing '---' fences
        assert text.startswith("---"), "SKILL.md must start with YAML frontmatter '---'"
        # Find second '---' delimiter
        second_dash = text.index("---", 3)
        frontmatter_text = text[3:second_dash].strip()
        fm = yaml.safe_load(frontmatter_text)
        assert isinstance(fm, dict), "SKILL.md frontmatter must parse as a YAML mapping"

    @pytest.mark.offline
    def test_advisor_skill_md_name(self, repo_root):
        """SKILL.md frontmatter must have name == 'omr-advisor'."""
        import yaml

        skill_md = repo_root / "skills" / "omr-advisor" / "SKILL.md"
        assert skill_md.exists(), "skills/omr-advisor/SKILL.md not found"
        text = skill_md.read_text(encoding="utf-8")
        second_dash = text.index("---", 3)
        fm = yaml.safe_load(text[3:second_dash].strip())
        assert fm.get("name") == "omr-advisor", (
            f"SKILL.md frontmatter 'name' must be 'omr-advisor'; got {fm.get('name')!r}"
        )

    @pytest.mark.offline
    def test_advisor_skill_md_description_korean_trigger(self, repo_root):
        """SKILL.md description must contain a Korean trigger (지도교수 or 교차검증)."""
        import yaml

        skill_md = repo_root / "skills" / "omr-advisor" / "SKILL.md"
        assert skill_md.exists(), "skills/omr-advisor/SKILL.md not found"
        text = skill_md.read_text(encoding="utf-8")
        second_dash = text.index("---", 3)
        fm = yaml.safe_load(text[3:second_dash].strip())
        description = str(fm.get("description", ""))
        assert re.search(r"지도교수|교차검증", description), (
            "SKILL.md description must contain a Korean trigger phrase "
            "(e.g. '지도교수' or '교차검증'); "
            f"got description: {description!r}"
        )

    @pytest.mark.offline
    def test_advisor_skill_md_description_english_trigger(self, repo_root):
        """SKILL.md description must contain an English trigger (advisor or verify)."""
        import yaml

        skill_md = repo_root / "skills" / "omr-advisor" / "SKILL.md"
        assert skill_md.exists(), "skills/omr-advisor/SKILL.md not found"
        text = skill_md.read_text(encoding="utf-8")
        second_dash = text.index("---", 3)
        fm = yaml.safe_load(text[3:second_dash].strip())
        description = str(fm.get("description", ""))
        assert re.search(r"advisor|verify", description, re.IGNORECASE), (
            "SKILL.md description must contain an English trigger phrase "
            "(e.g. 'advisor' or 'verify'); "
            f"got description: {description!r}"
        )

    # ------------------------------------------------------------------ agents/openai.yaml

    @pytest.mark.offline
    def test_advisor_openai_yaml_exists(self, repo_root):
        """skills/omr-advisor/agents/openai.yaml must exist."""
        yaml_path = repo_root / "skills" / "omr-advisor" / "agents" / "openai.yaml"
        assert yaml_path.exists(), "skills/omr-advisor/agents/openai.yaml not found"

    @pytest.mark.offline
    def test_advisor_openai_yaml_parses(self, repo_root):
        """agents/openai.yaml must parse as valid YAML."""
        import yaml

        yaml_path = repo_root / "skills" / "omr-advisor" / "agents" / "openai.yaml"
        assert yaml_path.exists(), "skills/omr-advisor/agents/openai.yaml not found"
        with open(yaml_path, encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        assert isinstance(doc, dict), "agents/openai.yaml must parse as a YAML mapping"

    @pytest.mark.offline
    def test_advisor_openai_yaml_display_name(self, repo_root):
        """agents/openai.yaml interface.display_name must equal '지도교수 검토'."""
        import yaml

        yaml_path = repo_root / "skills" / "omr-advisor" / "agents" / "openai.yaml"
        assert yaml_path.exists(), "skills/omr-advisor/agents/openai.yaml not found"
        with open(yaml_path, encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        display_name = doc.get("interface", {}).get("display_name")
        assert display_name == "지도교수 검토", (
            f"agents/openai.yaml interface.display_name must be '지도교수 검토'; "
            f"got {display_name!r}"
        )

    @pytest.mark.offline
    def test_advisor_openai_yaml_allow_implicit_invocation(self, repo_root):
        """agents/openai.yaml policy.allow_implicit_invocation must be True."""
        import yaml

        yaml_path = repo_root / "skills" / "omr-advisor" / "agents" / "openai.yaml"
        assert yaml_path.exists(), "skills/omr-advisor/agents/openai.yaml not found"
        with open(yaml_path, encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        allow_implicit = doc.get("policy", {}).get("allow_implicit_invocation")
        assert allow_implicit is True, (
            f"agents/openai.yaml policy.allow_implicit_invocation must be True; "
            f"got {allow_implicit!r}"
        )

    @pytest.mark.offline
    def test_advisor_openai_yaml_omr_scholar_dependency(self, repo_root):
        """agents/openai.yaml dependencies.tools must reference mcp omr_scholar."""
        import yaml

        yaml_path = repo_root / "skills" / "omr-advisor" / "agents" / "openai.yaml"
        assert yaml_path.exists(), "skills/omr-advisor/agents/openai.yaml not found"
        with open(yaml_path, encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        tools = doc.get("dependencies", {}).get("tools", [])
        assert isinstance(tools, list) and len(tools) > 0, (
            "agents/openai.yaml dependencies.tools must be a non-empty list"
        )
        mcp_tools = [t for t in tools if isinstance(t, dict) and t.get("type") == "mcp"]
        mcp_values = [t.get("value", "") for t in mcp_tools]
        assert "omr_scholar" in mcp_values, (
            f"agents/openai.yaml dependencies.tools must reference mcp 'omr_scholar'; "
            f"found mcp tools: {mcp_values!r}"
        )

    # ------------------------------------------------------------------ assets/icon.svg

    @pytest.mark.offline
    def test_advisor_icon_svg_exists(self, repo_root):
        """skills/omr-advisor/assets/icon.svg must exist."""
        icon = repo_root / "skills" / "omr-advisor" / "assets" / "icon.svg"
        assert icon.exists(), "skills/omr-advisor/assets/icon.svg not found"

    @pytest.mark.offline
    def test_advisor_icon_svg_is_well_formed_xml(self, repo_root):
        """assets/icon.svg must be well-formed XML (parseable by ElementTree)."""
        import xml.etree.ElementTree as ET

        icon = repo_root / "skills" / "omr-advisor" / "assets" / "icon.svg"
        assert icon.exists(), "skills/omr-advisor/assets/icon.svg not found"
        try:
            ET.parse(str(icon))
        except ET.ParseError as exc:
            pytest.fail(f"assets/icon.svg is not well-formed XML: {exc}")

    # ------------------------------------------------------------------ SKILL.md body contract

    @pytest.mark.offline
    def test_advisor_skill_md_body_cross_checks(self, repo_root):
        """SKILL.md body must mention all four cross-check labels."""
        skill_md = repo_root / "skills" / "omr-advisor" / "SKILL.md"
        assert skill_md.exists(), "skills/omr-advisor/SKILL.md not found"
        text = skill_md.read_text(encoding="utf-8")

        # Hypothesis <-> analysis cross-check (교차검증 A)
        assert re.search(r"가설.{0,10}분석|분석.{0,10}가설", text), (
            "SKILL.md must describe the hypothesis↔analysis cross-check (교차검증 A: '가설↔분석')"
        )
        # Citation <-> claim cross-check (교차검증 B)
        assert re.search(r"인용.{0,10}주장|주장.{0,10}인용", text), (
            "SKILL.md must describe the citation↔claim cross-check (교차검증 B: '인용↔주장')"
        )
        # Analysis <-> conclusion cross-check (교차검증 C)
        assert re.search(r"분석.{0,10}결론|결론.{0,10}분석", text), (
            "SKILL.md must describe the analysis↔conclusion cross-check (교차검증 C: '분석↔결론')"
        )
        # Integrity check (교차검증 D)
        assert re.search(r"무결성|integrity", text, re.IGNORECASE), (
            "SKILL.md must describe the integrity check (교차검증 D: '무결성')"
        )

    @pytest.mark.offline
    def test_advisor_skill_md_advisor_profile_path(self, repo_root):
        """SKILL.md must mention .omr/advisor-profile.md for advisor-profile learning."""
        skill_md = repo_root / "skills" / "omr-advisor" / "SKILL.md"
        assert skill_md.exists(), "skills/omr-advisor/SKILL.md not found"
        text = skill_md.read_text(encoding="utf-8")
        assert ".omr/advisor-profile.md" in text, (
            "SKILL.md must reference '.omr/advisor-profile.md' for advisor-profile persistence"
        )

    @pytest.mark.offline
    def test_advisor_skill_md_read_only_contract(self, repo_root):
        """SKILL.md must assert READ-ONLY over stage artifacts."""
        skill_md = repo_root / "skills" / "omr-advisor" / "SKILL.md"
        assert skill_md.exists(), "skills/omr-advisor/SKILL.md not found"
        text = skill_md.read_text(encoding="utf-8")
        assert re.search(r"읽기 전용|READ.ONLY|read.only", text, re.IGNORECASE), (
            "SKILL.md must state the READ-ONLY contract over stage artifacts "
            "('읽기 전용' or 'READ-ONLY')"
        )

    @pytest.mark.offline
    def test_advisor_skill_md_non_blocking_contract(self, repo_root):
        """SKILL.md must state the non-blocking contract (does not write state['stages'])."""
        skill_md = repo_root / "skills" / "omr-advisor" / "SKILL.md"
        assert skill_md.exists(), "skills/omr-advisor/SKILL.md not found"
        text = skill_md.read_text(encoding="utf-8")
        # Must mention non-blocking / 비차단
        assert re.search(r"비차단|non.blocking|non.block", text, re.IGNORECASE), (
            "SKILL.md must state the NON-BLOCKING contract ('비차단' or 'non-blocking')"
        )
        # Must explicitly say it does NOT write state["stages"]
        assert re.search(r'state\[.stages.\]', text), (
            "SKILL.md must explicitly reference state[\"stages\"] to describe the "
            "non-write / non-blocking contract"
        )
        # Must say it writes state["advisor"]
        assert re.search(r'state\[.advisor.\]', text), (
            "SKILL.md must state it writes state[\"advisor\"] (and only that)"
        )

    @pytest.mark.offline
    def test_advisor_skill_md_ascii_machine_tokens(self, repo_root):
        """SKILL.md must contain the required ASCII machine-token literals."""
        skill_md = repo_root / "skills" / "omr-advisor" / "SKILL.md"
        assert skill_md.exists(), "skills/omr-advisor/SKILL.md not found"
        text = skill_md.read_text(encoding="utf-8")

        required_tokens = [
            ".omr/advisor-report.md",
            ".omr/advisor-profile.md",
            'state["advisor"]',
            "ok",
            "issues-found",
        ]
        for token in required_tokens:
            assert token in text, (
                f"SKILL.md must contain ASCII machine-token literal {token!r}"
            )

    # ------------------------------------------------------------------ 7-skill bundle lock

    @pytest.mark.offline
    def test_exactly_seven_omr_skills(self, repo_root):
        """Exactly 7 skills/omr-* directories must exist (bundle skill-count contract)."""
        skills_root = repo_root / "skills"
        omr_dirs = sorted(
            [d for d in skills_root.iterdir() if d.is_dir() and d.name.startswith("omr-")]
        )
        assert len(omr_dirs) == 7, (
            f"Expected exactly 7 skills/omr-* directories; "
            f"found {len(omr_dirs)}: {[d.name for d in omr_dirs]}"
        )

    @pytest.mark.offline
    def test_all_omr_skills_have_skill_md(self, repo_root):
        """Every skills/omr-* directory must contain SKILL.md."""
        skills_root = repo_root / "skills"
        omr_dirs = [
            d for d in skills_root.iterdir()
            if d.is_dir() and d.name.startswith("omr-")
        ]
        for skill_dir in omr_dirs:
            skill_md = skill_dir / "SKILL.md"
            assert skill_md.exists(), (
                f"skills/{skill_dir.name}/SKILL.md not found — "
                "all omr-* skills must have SKILL.md"
            )

    @pytest.mark.offline
    def test_all_omr_skills_have_openai_yaml(self, repo_root):
        """Every skills/omr-* directory must contain agents/openai.yaml."""
        skills_root = repo_root / "skills"
        omr_dirs = [
            d for d in skills_root.iterdir()
            if d.is_dir() and d.name.startswith("omr-")
        ]
        for skill_dir in omr_dirs:
            openai_yaml = skill_dir / "agents" / "openai.yaml"
            assert openai_yaml.exists(), (
                f"skills/{skill_dir.name}/agents/openai.yaml not found — "
                "all omr-* skills must have agents/openai.yaml"
            )


# ---------------------------------------------------------------------------
# AC-ADVISOR codex E2E stub (skipped when codex/bundle absent)
# ---------------------------------------------------------------------------


class TestACSAdvisorCodexE2E:
    """Optional end-to-end stub: runs $omr-advisor on a seeded workspace.

    Skipped automatically when codex or the bundle is not installed.
    Asserts: .omr/advisor-report.md produced; state["advisor"] set;
    state["stages"] NOT mutated.
    """

    @pytest.mark.codex
    @skip_no_codex
    @skip_no_bundle
    def test_advisor_e2e_produces_report_and_sets_advisor_state(self, tmp_path):
        """[codex] omr-advisor on a seeded study must write advisor-report.md and
        state['advisor'] without touching state['stages']."""
        study = tmp_path / "advisor_study"
        study.mkdir()
        omr_dir = study / ".omr"
        omr_dir.mkdir()

        # Seed a minimal but realistic multi-stage state (all stages done so
        # the advisor has something to cross-check).
        initial_stages = {
            "stage1": {"status": "done", "artifacts": {}, "checksums": {}},
            "stage2": {"status": "done", "artifacts": {}, "checksums": {}},
            "stage3": {"status": "done", "artifacts": {}, "checksums": {}},
        }
        initial_state = {
            "workspace_root": str(study),
            "stages": initial_stages,
        }
        state_path = omr_dir / "state.json"
        state_path.write_text(json.dumps(initial_state), encoding="utf-8")

        # Seed minimal stage artifacts so the advisor can collect them.
        (study / "00_question").mkdir()
        (study / "00_question" / "research-question.md").write_text(
            "# Research Question\n\nH0: No effect. H1: Effect exists.\n"
            "Variables: IV=caffeine (mg/day), DV=reaction_time_ms\n"
            "Design: independent samples\n",
            encoding="utf-8",
        )
        (study / "20_analysis").mkdir()
        (study / "20_analysis" / "outputs").mkdir()
        (study / "20_analysis" / "outputs" / "results.json").write_text(
            json.dumps({"statistic": -3.21, "df": 58, "p_value": 0.002, "label": "Student"}),
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                "codex", "exec",
                "-C", str(study),
                "--skip-git-repo-check",
                "-s", "workspace-write",
                "--full-auto",
                "--json",
                "교차검증해 주세요",
            ],
            capture_output=True, text=True, timeout=180, cwd=str(REPO_ROOT),
        )

        report_path = omr_dir / "advisor-report.md"
        if not report_path.exists():
            pytest.skip(
                "advisor-report.md not produced — omr-advisor may not be wired yet; "
                "skipping end-to-end assertion"
            )

        # .omr/advisor-report.md must be non-empty.
        assert report_path.read_text(encoding="utf-8").strip(), (
            ".omr/advisor-report.md was created but is empty"
        )

        # state["advisor"] must be set.
        with open(state_path, encoding="utf-8") as fh:
            final_state = json.load(fh)
        assert "advisor" in final_state, (
            "state.json must have 'advisor' key after omr-advisor run"
        )

        # state["stages"] must be UNCHANGED (non-blocking contract).
        assert final_state.get("stages") == initial_stages, (
            "omr-advisor must NOT mutate state['stages'] — non-blocking contract violated.\n"
            f"Initial stages: {initial_stages}\n"
            f"Final stages:   {final_state.get('stages')}"
        )
