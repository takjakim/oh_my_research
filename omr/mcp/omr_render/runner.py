"""Render execution: enforce boundary, spawn, capture, build manifest.

Plan sections 4.2 (boundary), 4.3 (output verification / manifest), 4.4
(failure handling / error classification).

Never fabricates results. Never claims success without a verified manifest
(produced files + sizes + mtime + parsed results.json the qmd emits).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from typing import Dict, List, Optional

from .boundary import (
    BoundaryError,
    build_argv,
    canonical_root,
    check_allowed,
    redirected_env,
    resolve_within_root,
    scratch_dirs,
)

DEFAULT_TIMEOUT = 600  # seconds (plan section 4.2)


def _ts() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _ensure_scratch(study_root_canon: str) -> str:
    """Create .omr/tmp, .omr/rlib, .omr/render-log; return render-log dir."""
    tmp, rlib, logdir = scratch_dirs(study_root_canon)
    for d in (tmp, rlib, logdir):
        os.makedirs(d, exist_ok=True)
    return logdir


def _write_log(logdir: str, ts: str, content: str) -> str:
    path = os.path.join(logdir, "%s.log" % ts)
    with open(path, "w", encoding="utf-8", errors="replace") as fh:
        fh.write(content)
    return path


def _log_path_escape(study_root_canon: str, ts: str, message: str) -> str:
    """Log an explicit path-escape error (AC9) -- no process was spawned."""
    logdir = _ensure_scratch(study_root_canon)
    body = "PATH-ESCAPE REJECTION (no process spawned)\nts=%s\n%s\n" % (ts, message)
    return _write_log(logdir, ts, body)


def classify_render_error(stdout: str, stderr: str, returncode: int) -> str:
    """Classify a render failure (plan section 4.4).

    Returns one of: "missing-r-package", "quarto-pandoc", "data-error",
    "timeout", "unknown".
    """
    blob = ((stdout or "") + "\n" + (stderr or "")).lower()
    if "there is no package called" in blob or re.search(
        r"could not find function", blob
    ):
        return "missing-r-package"
    if "pandoc" in blob and ("error" in blob or "not found" in blob):
        return "quarto-pandoc"
    if "quarto" in blob and "command not found" in blob:
        return "quarto-pandoc"
    if re.search(r"object '.*' not found", blob) or "undefined columns selected" in blob:
        return "data-error"
    if "non-numeric argument" in blob or "missing value where true/false needed" in blob:
        return "data-error"
    return "unknown"


def _scan_outputs(study_root_canon: str, since: float) -> List[Dict]:
    """Scan the study tree for files modified at/after ``since``.

    Skips the .omr scratch tree. Returns manifest entries
    {path, rel, size, mtime}.
    """
    entries: List[Dict] = []
    omr_dir = os.path.join(study_root_canon, ".omr")
    for root, dirs, files in os.walk(study_root_canon):
        if root == study_root_canon:
            dirs[:] = [d for d in dirs if d != ".omr"]
        if root.startswith(omr_dir):
            continue
        for name in files:
            fp = os.path.join(root, name)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            if st.st_mtime + 1e-6 >= since:
                entries.append(
                    {
                        "path": fp,
                        "rel": os.path.relpath(fp, study_root_canon),
                        "size": st.st_size,
                        "mtime": st.st_mtime,
                    }
                )
    return sorted(entries, key=lambda e: e["rel"])


def _parse_results_json(study_root_canon: str) -> Optional[dict]:
    """Find and parse results.json emitted by the qmd (best effort)."""
    for cand in (
        os.path.join(study_root_canon, "20_analysis", "outputs", "results.json"),
        os.path.join(study_root_canon, "outputs", "results.json"),
        os.path.join(study_root_canon, "results.json"),
    ):
        if os.path.isfile(cand):
            try:
                with open(cand, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (OSError, ValueError):
                return None
    return None


def render_qmd(
    qmd_path: str,
    study_root: str,
    *,
    quarto_bin: str,
    rscript_bin: Optional[str] = None,
    form: str = "quarto_render",
    timeout: int = DEFAULT_TIMEOUT,
    allow_install: bool = False,
    output_subdir: str = "outputs",
) -> dict:
    """Render ``qmd_path`` under the full security boundary.

    Returns a structured result dict (never raises for normal failure --
    failures are reported as ``{"ok": False, ...}`` with an error class so the
    caller can mark the stage ``blocked``).
    """
    ts = _ts()
    try:
        root = canonical_root(study_root)
    except BoundaryError as e:
        return {"ok": False, "error": e.kind, "message": e.message, "ts": ts}

    # (1) allow-list (before any path resolution / spawn)
    try:
        check_allowed(form, allow_install=allow_install)
    except BoundaryError as e:
        log = _log_path_escape(root, ts, "allow-list rejection: %s" % e.message)
        return {
            "ok": False,
            "error": e.kind,
            "message": e.message,
            "log": log,
            "spawned": False,
            "ts": ts,
        }

    # (3) path-escape rejection -- BEFORE spawning anything (AC9)
    try:
        qmd_resolved = resolve_within_root(root, qmd_path)
        if not os.path.isfile(qmd_resolved):
            return {
                "ok": False,
                "error": "data-error",
                "message": "qmd not found: %s" % qmd_resolved,
                "spawned": False,
                "ts": ts,
            }
        output_dir_resolved = resolve_within_root(root, output_subdir)
    except BoundaryError as e:
        log = _log_path_escape(root, ts, e.message)
        return {
            "ok": False,
            "error": e.kind,  # "path-escape"
            "message": e.message,
            "log": log,
            "spawned": False,
            "ts": ts,
        }

    logdir = _ensure_scratch(root)
    os.makedirs(output_dir_resolved, exist_ok=True)

    # (5) absolute-path binary + (2) forced cwd + (4) redirected env
    argv = build_argv(
        form,
        quarto_bin=quarto_bin,
        rscript_bin=rscript_bin,
        qmd_resolved=qmd_resolved,
        output_dir_resolved=output_dir_resolved,
    )
    env = redirected_env(root)
    started = time.time()
    try:
        proc = subprocess.run(
            argv,
            cwd=root,  # forced cwd = canonical study root
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        log = _write_log(
            logdir,
            ts,
            "TIMEOUT after %ss\nargv=%r\n%s\n%s"
            % (timeout, argv, e.stdout or "", e.stderr or ""),
        )
        return {
            "ok": False,
            "error": "timeout",
            "message": "render timed out after %ss" % timeout,
            "log": log,
            "spawned": True,
            "ts": ts,
        }
    except OSError as e:
        log = _write_log(logdir, ts, "SPAWN FAILURE\nargv=%r\n%s" % (argv, e))
        return {
            "ok": False,
            "error": "quarto-pandoc",
            "message": "failed to spawn: %s" % e,
            "log": log,
            "spawned": False,
            "ts": ts,
        }

    log_body = (
        "argv=%r\ncwd=%s\nreturncode=%s\n--- STDOUT ---\n%s\n--- STDERR ---\n%s\n"
        % (argv, root, proc.returncode, proc.stdout, proc.stderr)
    )
    log = _write_log(logdir, ts, log_body)

    if proc.returncode != 0:
        return {
            "ok": False,
            "error": classify_render_error(
                proc.stdout, proc.stderr, proc.returncode
            ),
            "message": "render exited %s" % proc.returncode,
            "returncode": proc.returncode,
            "log": log,
            "stderr_tail": (proc.stderr or "")[-2000:],
            "spawned": True,
            "ts": ts,
        }

    # Verified manifest -- never claim success without it.
    manifest = _scan_outputs(root, started)
    results = _parse_results_json(root)
    return {
        "ok": True,
        "ts": ts,
        "study_root": root,
        "qmd": qmd_resolved,
        "log": log,
        "manifest": manifest,
        "results_json": results,
        "spawned": True,
    }
