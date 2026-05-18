"""AC9 privilege-model classifier (plan section 4.2 / AC9).

From inside the MCP server, empirically determine the active privilege model:

  (a) attempt a write to a host path OUTSIDE the workspace AND a write to
      <study>/.omr/tmp/  -> host-write vs sandbox-confined signal
  (b) exec Rscript --version / quarto --version by ABSOLUTE path
  (c) tiny end-to-end `quarto render` of a one-line generated qmd INTO the
      workspace (must PASS under BOTH models thanks to scratch redirection)

Reports PASS/FAIL per check + a definite host-privilege vs sandbox-confined
verdict. The verdict NEVER changes the authoritative in-server boundary.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from typing import Optional

from .boundary import canonical_root, redirected_env, scratch_dirs


def _check_out_of_workspace_write() -> dict:
    """(a1) Attempt a write to a host temp path OUTSIDE the workspace."""
    try:
        fd, p = tempfile.mkstemp(prefix="omr_priv_probe_")
        with os.fdopen(fd, "w") as fh:
            fh.write("omr-probe")
        os.unlink(p)
        return {"check": "host-write-outside-workspace", "pass": True, "path": p}
    except OSError as e:
        return {
            "check": "host-write-outside-workspace",
            "pass": False,
            "error": str(e),
        }


def _check_workspace_tmp_write(study_root_canon: str) -> dict:
    """(a2) Attempt a write into <study>/.omr/tmp/ (must always succeed)."""
    tmp, _, _ = scratch_dirs(study_root_canon)
    try:
        os.makedirs(tmp, exist_ok=True)
        p = os.path.join(tmp, "omr_priv_probe_%d" % int(time.time() * 1000))
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("omr-probe")
        os.unlink(p)
        return {"check": "workspace-tmp-write", "pass": True, "path": tmp}
    except OSError as e:
        return {"check": "workspace-tmp-write", "pass": False, "error": str(e)}


def _check_exec_version(label: str, binary: Optional[str]) -> dict:
    """(b) Exec ``<binary> --version`` by ABSOLUTE path."""
    if not binary:
        return {"check": "exec-%s-version" % label, "pass": False,
                "error": "binary not detected"}
    try:
        proc = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        ok = proc.returncode == 0
        return {
            "check": "exec-%s-version" % label,
            "pass": ok,
            "binary": binary,
            "stdout_head": (proc.stdout or "")[:120],
        }
    except (OSError, subprocess.SubprocessError) as e:
        return {"check": "exec-%s-version" % label, "pass": False,
                "binary": binary, "error": str(e)}


def _check_tiny_render(study_root_canon: str, quarto_bin: Optional[str]) -> dict:
    """(c) Tiny end-to-end `quarto render` of a one-line qmd into workspace.

    Designed to PASS under both privilege models because all scratch/output
    is redirected into the workspace.
    """
    if not quarto_bin:
        return {"check": "tiny-quarto-render", "pass": False,
                "error": "quarto not detected"}
    probe_dir = os.path.join(study_root_canon, ".omr", "tmp", "priv_render")
    try:
        os.makedirs(probe_dir, exist_ok=True)
        qmd = os.path.join(probe_dir, "probe.qmd")
        with open(qmd, "w", encoding="utf-8") as fh:
            fh.write(
                "---\ntitle: probe\nformat: docx\n---\n\nomr privilege probe.\n"
            )
        env = redirected_env(study_root_canon)
        proc = subprocess.run(
            [quarto_bin, "render", qmd, "--output-dir", probe_dir],
            cwd=study_root_canon,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        produced = [
            f for f in os.listdir(probe_dir) if f.endswith((".docx", ".html"))
        ]
        ok = proc.returncode == 0 and bool(produced)
        return {
            "check": "tiny-quarto-render",
            "pass": ok,
            "returncode": proc.returncode,
            "produced": produced,
            "stderr_tail": (proc.stderr or "")[-400:] if not ok else "",
        }
    except (OSError, subprocess.SubprocessError) as e:
        return {"check": "tiny-quarto-render", "pass": False, "error": str(e)}


def classify_privilege(
    study_root: str,
    *,
    rscript_bin: Optional[str] = None,
    quarto_bin: Optional[str] = None,
) -> dict:
    """Run all AC9 probes and return PASS/FAIL per check + verdict."""
    root = canonical_root(study_root)
    a1 = _check_out_of_workspace_write()
    a2 = _check_workspace_tmp_write(root)
    b_r = _check_exec_version("rscript", rscript_bin)
    b_q = _check_exec_version("quarto", quarto_bin)
    c = _check_tiny_render(root, quarto_bin)

    # Verdict: out-of-workspace write succeeding => host privilege; failing
    # while in-workspace write succeeds => sandbox-confined (write-restricted).
    if a1["pass"]:
        verdict = "host-privilege"
    elif a2["pass"]:
        verdict = "sandbox-confined"
    else:
        verdict = "indeterminate"

    checks = [a1, a2, b_r, b_q, c]
    return {
        "verdict": verdict,
        "checks": checks,
        # (c) must pass under both models -- this is the operative gate.
        "render_works": bool(c.get("pass")),
        "note": (
            "Verdict is informational only; the authoritative in-server "
            "boundary (allow-list + path-escape + forced cwd + scratch "
            "redirection) applies regardless of the verdict."
        ),
    }
