"""Detect logic (mocked subprocess/PATH) + transport-independent dispatch.

No R/Quarto installed and no `mcp` package required.
"""

import omr_render.detect as detect
from omr_render.detect import detect_tool
from omr_render.server import _dispatch, tool_version


def test_version_tool_zero_side_effects():
    assert tool_version() == {"server": "omr-render", "version": "0.1.0"}


def test_dispatch_version():
    assert _dispatch("render.version", {}) == {
        "server": "omr-render",
        "version": "0.1.0",
    }


def test_dispatch_unknown_tool():
    r = _dispatch("render.bogus", {})
    assert r["ok"] is False
    assert r["error"] == "unknown-tool"


def test_dispatch_render_missing_args():
    r = _dispatch("render.render", {})
    assert r["ok"] is False
    assert r["error"] == "invalid-args"


def test_dispatch_classify_missing_args():
    r = _dispatch("render.classify_privilege", {})
    assert r["ok"] is False
    assert r["error"] == "invalid-args"


def test_detect_tool_not_found(monkeypatch):
    monkeypatch.setattr(detect, "find_candidates", lambda tool: [])
    r = detect_tool("R")
    assert r["found"] is False
    assert r["ok"] is False
    assert r["error"] == "not-found"
    assert r["below_floor"] is True


def test_detect_tool_below_floor(monkeypatch):
    monkeypatch.setattr(detect, "find_candidates", lambda tool: ["/abs/Rscript"])
    monkeypatch.setattr(
        detect, "_probe_version", lambda b: "R version 4.1.3 (2022-03-10)"
    )
    r = detect_tool("R")
    assert r["found"] is True
    assert r["ok"] is False
    assert r["below_floor"] is True
    assert r["version"] == "4.1.3"


def test_detect_tool_ok(monkeypatch):
    monkeypatch.setattr(detect, "find_candidates", lambda tool: ["/abs/quarto"])
    monkeypatch.setattr(detect, "_probe_version", lambda b: "1.4.553")
    r = detect_tool("quarto")
    assert r["found"] is True
    assert r["ok"] is True
    assert r["below_floor"] is False
    assert r["path"] == "/abs/quarto"
    assert r["version"] == "1.4.553"


def test_detect_tool_unparseable_hard_fail(monkeypatch):
    monkeypatch.setattr(detect, "find_candidates", lambda tool: ["/abs/Rscript"])
    monkeypatch.setattr(detect, "_probe_version", lambda b: "weird build")
    r = detect_tool("R")
    assert r["found"] is True
    assert r["ok"] is False
    assert r["error"] == "unparseable-version"
