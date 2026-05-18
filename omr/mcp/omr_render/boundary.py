"""The authoritative in-server security boundary (plan section 4.2).

This module is correct regardless of whether the MCP child process runs at
host privilege or is workspace-sandboxed. It enforces, BEFORE any process is
spawned:

  1. Fixed command allow-list (no free-form shell, ever).
  2. Forced cwd = canonicalized study_root.
  3. Path-escape rejection (realpath + symlink resolution; any arg escaping
     study_root => reject before exec).
  4. Scratch/output redirected INTO the workspace via env + flags.
  5. Absolute-path binary invocation (caller supplies abs paths from detect()).

Pure / stdlib-only / no subprocess here -> fully unit-testable. The actual
spawn happens in runner.py which depends on the decisions made here.
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Allow-list
# ---------------------------------------------------------------------------
# Each entry is a fixed *shape*. The model never supplies free-form shell;
# it may only pick one of these forms and supply file/path arguments which
# are then path-escape checked.
ALLOWED_FORMS = (
    "quarto_render",        # quarto render <file> [--output-dir <dir>]
    "quarto_check",         # quarto check
    "quarto_version",       # quarto --version
    "rscript_render",       # Rscript -e 'rmarkdown::render(...)'
    "rscript_sessioninfo",  # Rscript -e 'sessionInfo()'
    "rscript_version",      # Rscript --version
    "rscript_install",      # Rscript -e 'install.packages(...)'  (GATED, off by default)
)

# Forms that are NEVER allowed on the integrity-critical analysis path.
# install.packages is gated and disabled unless explicitly opted-in per request.
GATED_FORMS = ("rscript_install",)


class BoundaryError(Exception):
    """Raised when the security boundary rejects a request before exec."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind  # e.g. "path-escape", "allow-list", "gated"
        self.message = message


def canonical_root(study_root: str) -> str:
    """Canonicalize the study root (realpath; resolves symlinks)."""
    if not study_root:
        raise BoundaryError("invalid-root", "study_root is empty")
    return os.path.realpath(os.path.abspath(os.path.expanduser(study_root)))


def _is_within(root: str, candidate: str) -> bool:
    """True iff ``candidate`` (already canonicalized) is inside ``root``."""
    root = root.rstrip(os.sep)
    if candidate == root:
        return True
    return candidate.startswith(root + os.sep)


def resolve_within_root(study_root_canon: str, path_arg: str) -> str:
    """Resolve ``path_arg`` and assert it stays within the study root.

    ``path_arg`` may be relative (interpreted against study_root) or absolute.
    Symlinks and ``..`` are fully resolved via realpath. Any escape (absolute
    path outside root, ``..`` traversal, or symlink pointing out) raises
    BoundaryError("path-escape", ...) BEFORE any process is spawned.
    """
    if path_arg is None or path_arg == "":
        raise BoundaryError("path-escape", "empty path argument")
    if os.path.isabs(path_arg):
        joined = path_arg
    else:
        joined = os.path.join(study_root_canon, path_arg)
    resolved = os.path.realpath(joined)
    if not _is_within(study_root_canon, resolved):
        raise BoundaryError(
            "path-escape",
            "path %r resolves to %r which escapes study_root %r"
            % (path_arg, resolved, study_root_canon),
        )
    return resolved


def check_allowed(form: str, allow_install: bool = False) -> None:
    """Validate the requested command form against the allow-list.

    Raises BoundaryError("allow-list", ...) for unknown forms and
    BoundaryError("gated", ...) for gated forms unless explicitly enabled.
    """
    if form not in ALLOWED_FORMS:
        raise BoundaryError(
            "allow-list",
            "command form %r is not in the fixed allow-list" % (form,),
        )
    if form in GATED_FORMS and not allow_install:
        raise BoundaryError(
            "gated",
            "command form %r is gated and disabled by default "
            "(requires explicit per-request approval)" % (form,),
        )


def redirected_env(study_root_canon: str, base_env: Optional[dict] = None) -> dict:
    """Build an env dict with scratch/output redirected INTO the workspace.

    Sets TMPDIR/TEMP/TMP -> <study>/.omr/tmp/ and
    R_LIBS_USER -> <study>/.omr/rlib/ so that every would-be out-of-workspace
    write collapses into the already-writable workspace (correct under a
    write-confining sandbox AND at host privilege).
    """
    env = dict(base_env if base_env is not None else os.environ)
    tmp = os.path.join(study_root_canon, ".omr", "tmp")
    rlib = os.path.join(study_root_canon, ".omr", "rlib")
    env["TMPDIR"] = tmp
    env["TEMP"] = tmp
    env["TMP"] = tmp
    env["R_LIBS_USER"] = rlib
    return env


def scratch_dirs(study_root_canon: str) -> Tuple[str, str, str]:
    """Return (tmp_dir, rlib_dir, render_log_dir) absolute paths in-workspace."""
    base = os.path.join(study_root_canon, ".omr")
    return (
        os.path.join(base, "tmp"),
        os.path.join(base, "rlib"),
        os.path.join(base, "render-log"),
    )


def build_argv(
    form: str,
    *,
    quarto_bin: Optional[str] = None,
    rscript_bin: Optional[str] = None,
    qmd_resolved: Optional[str] = None,
    output_dir_resolved: Optional[str] = None,
    r_expr: Optional[str] = None,
) -> List[str]:
    """Construct the exact argv for an allowed form using ABSOLUTE binary paths.

    Caller is responsible for having already path-escape-checked every
    resolved path argument and validated ``form`` via ``check_allowed``.
    """
    if form == "quarto_render":
        if not quarto_bin or not qmd_resolved:
            raise BoundaryError("invalid-args", "quarto_render needs quarto_bin + qmd")
        argv = [quarto_bin, "render", qmd_resolved]
        if output_dir_resolved:
            argv += ["--output-dir", output_dir_resolved]
        return argv
    if form == "quarto_check":
        if not quarto_bin:
            raise BoundaryError("invalid-args", "quarto_check needs quarto_bin")
        return [quarto_bin, "check"]
    if form == "quarto_version":
        if not quarto_bin:
            raise BoundaryError("invalid-args", "quarto_version needs quarto_bin")
        return [quarto_bin, "--version"]
    if form == "rscript_render":
        if not rscript_bin or not r_expr:
            raise BoundaryError("invalid-args", "rscript_render needs rscript_bin + r_expr")
        return [rscript_bin, "-e", r_expr]
    if form == "rscript_sessioninfo":
        if not rscript_bin:
            raise BoundaryError("invalid-args", "rscript_sessioninfo needs rscript_bin")
        return [rscript_bin, "-e", "sessionInfo()"]
    if form == "rscript_version":
        if not rscript_bin:
            raise BoundaryError("invalid-args", "rscript_version needs rscript_bin")
        return [rscript_bin, "--version"]
    if form == "rscript_install":
        if not rscript_bin or not r_expr:
            raise BoundaryError("invalid-args", "rscript_install needs rscript_bin + r_expr")
        return [rscript_bin, "-e", r_expr]
    raise BoundaryError("allow-list", "unknown form %r" % (form,))
