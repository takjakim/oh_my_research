"""Runner tests: error classification + path-escape rejection WITHOUT spawn.

subprocess is monkeypatched/asserted-unused so no R/Quarto is needed.
"""

import os

import omr_render.runner as runner
from omr_render.runner import classify_render_error, render_qmd


# ---- error classification (plan 4.4) -------------------------------------

def test_classify_missing_r_package():
    err = "Error in library(car) : there is no package called 'car'"
    assert classify_render_error("", err, 1) == "missing-r-package"


def test_classify_missing_function_is_r_package():
    assert classify_render_error("", "could not find function \"foo\"", 1) == (
        "missing-r-package"
    )


def test_classify_quarto_pandoc_error():
    err = "pandoc: error producing document\nnot found"
    assert classify_render_error("", err, 1) == "quarto-pandoc"


def test_classify_data_error_object_not_found():
    err = "Error: object 'price' not found"
    assert classify_render_error("", err, 1) == "data-error"


def test_classify_unknown():
    assert classify_render_error("", "some other failure", 1) == "unknown"


# ---- path-escape rejection BEFORE spawn (AC9) ----------------------------

def _no_spawn(*a, **k):  # pragma: no cover - must never be called
    raise AssertionError("subprocess.run must NOT be called on path-escape")


def test_render_path_escape_rejected_no_process(tmp_path, monkeypatch):
    study = tmp_path / "study"
    study.mkdir()
    monkeypatch.setattr(runner.subprocess, "run", _no_spawn)

    result = render_qmd(
        "../outside.qmd",
        str(study),
        quarto_bin="/abs/quarto",
    )
    assert result["ok"] is False
    assert result["error"] == "path-escape"
    assert result["spawned"] is False
    # explicit path-escape error logged to .omr/render-log/<ts>.log (AC9)
    logdir = study / ".omr" / "render-log"
    logs = list(logdir.glob("*.log"))
    assert len(logs) == 1
    assert "PATH-ESCAPE REJECTION (no process spawned)" in logs[0].read_text()


def test_render_disallowed_form_rejected_no_process(tmp_path, monkeypatch):
    study = tmp_path / "study"
    study.mkdir()
    (study / "analysis.qmd").write_text("ok")
    monkeypatch.setattr(runner.subprocess, "run", _no_spawn)

    result = render_qmd(
        "analysis.qmd",
        str(study),
        quarto_bin="/abs/quarto",
        form="evil_shell",
    )
    assert result["ok"] is False
    assert result["error"] == "allow-list"
    assert result["spawned"] is False


def test_render_gated_install_rejected_no_process(tmp_path, monkeypatch):
    study = tmp_path / "study"
    study.mkdir()
    (study / "analysis.qmd").write_text("ok")
    monkeypatch.setattr(runner.subprocess, "run", _no_spawn)

    result = render_qmd(
        "analysis.qmd",
        str(study),
        quarto_bin="/abs/quarto",
        rscript_bin="/abs/Rscript",
        form="rscript_install",
    )
    assert result["ok"] is False
    assert result["error"] == "gated"
    assert result["spawned"] is False


def test_render_missing_qmd_is_data_error_no_spawn(tmp_path, monkeypatch):
    study = tmp_path / "study"
    study.mkdir()
    monkeypatch.setattr(runner.subprocess, "run", _no_spawn)

    result = render_qmd("analysis.qmd", str(study), quarto_bin="/abs/quarto")
    assert result["ok"] is False
    assert result["error"] == "data-error"
    assert result["spawned"] is False


def test_render_success_builds_manifest_with_mocked_subprocess(
    tmp_path, monkeypatch
):
    study = tmp_path / "study"
    (study / "outputs").mkdir(parents=True)
    (study / "analysis.qmd").write_text("---\ntitle: t\n---\n")

    class FakeProc:
        returncode = 0
        stdout = "rendered ok"
        stderr = ""

    def fake_run(argv, cwd=None, env=None, capture_output=None,
                 text=None, timeout=None):
        # boundary contract: abs binary, forced cwd, redirected env
        assert argv[0] == "/abs/quarto"
        assert cwd == os.path.realpath(str(study))
        assert env["TMPDIR"].endswith(os.path.join(".omr", "tmp"))
        # simulate produced outputs + results.json
        out = study / "outputs"
        (out / "analysis.docx").write_bytes(b"DOCX")
        (out / "results.json").write_text('{"p_value": 0.03, "n": 42}')
        return FakeProc()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = render_qmd("analysis.qmd", str(study), quarto_bin="/abs/quarto")
    assert result["ok"] is True
    rels = {e["rel"] for e in result["manifest"]}
    assert "outputs/analysis.docx" in rels
    assert result["results_json"] == {"p_value": 0.03, "n": 42}
    assert os.path.isfile(result["log"])
