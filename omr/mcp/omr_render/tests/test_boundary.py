"""Security-boundary tests: path-escape, allow-list, env redirection, argv.

These tests NEVER spawn a process -- they prove rejection happens before exec.
"""

import os

import pytest

from omr_render.boundary import (
    ALLOWED_FORMS,
    GATED_FORMS,
    BoundaryError,
    build_argv,
    canonical_root,
    check_allowed,
    redirected_env,
    resolve_within_root,
    scratch_dirs,
)


@pytest.fixture()
def study(tmp_path):
    root = tmp_path / "study"
    (root / "outputs").mkdir(parents=True)
    (root / "analysis.qmd").write_text("ok")
    return canonical_root(str(root))


# ---- path-escape ---------------------------------------------------------

def test_relative_path_within_root_ok(study):
    resolved = resolve_within_root(study, "analysis.qmd")
    assert resolved == os.path.join(study, "analysis.qmd")


def test_dotdot_escape_rejected(study):
    with pytest.raises(BoundaryError) as ei:
        resolve_within_root(study, "../evil.qmd")
    assert ei.value.kind == "path-escape"


def test_absolute_path_outside_root_rejected(study):
    with pytest.raises(BoundaryError) as ei:
        resolve_within_root(study, "/etc/passwd")
    assert ei.value.kind == "path-escape"


def test_symlink_escape_rejected(study, tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    link = os.path.join(study, "link.qmd")
    os.symlink(str(outside), link)
    with pytest.raises(BoundaryError) as ei:
        resolve_within_root(study, "link.qmd")
    assert ei.value.kind == "path-escape"


def test_empty_path_rejected(study):
    with pytest.raises(BoundaryError):
        resolve_within_root(study, "")


def test_nested_relative_within_root_ok(study):
    resolved = resolve_within_root(study, "outputs")
    assert resolved == os.path.join(study, "outputs")


# ---- allow-list ----------------------------------------------------------

def test_disallowed_free_form_command_rejected():
    with pytest.raises(BoundaryError) as ei:
        check_allowed("rm -rf /")
    assert ei.value.kind == "allow-list"


def test_unknown_form_rejected():
    with pytest.raises(BoundaryError) as ei:
        check_allowed("python_eval")
    assert ei.value.kind == "allow-list"


def test_allowed_form_passes():
    check_allowed("quarto_render")
    check_allowed("rscript_render")
    check_allowed("quarto_check")


def test_gated_install_rejected_by_default():
    with pytest.raises(BoundaryError) as ei:
        check_allowed("rscript_install")
    assert ei.value.kind == "gated"


def test_gated_install_allowed_when_opted_in():
    check_allowed("rscript_install", allow_install=True)


def test_install_is_a_gated_form():
    assert "rscript_install" in GATED_FORMS
    assert "rscript_install" in ALLOWED_FORMS


# ---- env redirection -----------------------------------------------------

def test_redirected_env_points_into_workspace(study):
    env = redirected_env(study, base_env={"PATH": "/usr/bin"})
    tmp = os.path.join(study, ".omr", "tmp")
    rlib = os.path.join(study, ".omr", "rlib")
    assert env["TMPDIR"] == tmp
    assert env["TEMP"] == tmp
    assert env["TMP"] == tmp
    assert env["R_LIBS_USER"] == rlib
    assert env["PATH"] == "/usr/bin"  # base env preserved


def test_scratch_dirs_all_inside_workspace(study):
    tmp, rlib, logdir = scratch_dirs(study)
    for d in (tmp, rlib, logdir):
        assert d.startswith(study + os.sep)


# ---- argv construction (absolute binary paths) ---------------------------

def test_build_argv_quarto_render_with_output_dir():
    argv = build_argv(
        "quarto_render",
        quarto_bin="/abs/quarto",
        qmd_resolved="/study/analysis.qmd",
        output_dir_resolved="/study/outputs",
    )
    assert argv == [
        "/abs/quarto",
        "render",
        "/study/analysis.qmd",
        "--output-dir",
        "/study/outputs",
    ]


def test_build_argv_rscript_sessioninfo():
    argv = build_argv("rscript_sessioninfo", rscript_bin="/abs/Rscript")
    assert argv == ["/abs/Rscript", "-e", "sessionInfo()"]


def test_build_argv_missing_required_args_raises():
    with pytest.raises(BoundaryError):
        build_argv("quarto_render", quarto_bin=None, qmd_resolved=None)


def test_canonical_root_empty_rejected():
    with pytest.raises(BoundaryError):
        canonical_root("")
