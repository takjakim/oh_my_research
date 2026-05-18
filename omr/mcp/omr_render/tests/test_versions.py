"""Version parse / semantic compare / hard-floor tests."""

from omr_render.versions import (
    HARD_FLOORS,
    check_floor,
    compare_versions,
    meets_floor,
    parse_version,
)


def test_parse_r_version_string():
    raw = "R scripting front-end version 4.2.1 (2022-06-23)"
    assert parse_version(raw) == (4, 2, 1)


def test_parse_quarto_bare_version():
    assert parse_version("1.4.553") == (1, 4, 553)


def test_parse_pandoc_multiline():
    assert parse_version("pandoc 3.1.11\nFeatures: +server") == (3, 1, 11)


def test_parse_two_component_version_patch_defaults_zero():
    assert parse_version("1.4") == (1, 4, 0)


def test_parse_unparseable_returns_none():
    assert parse_version("no version here") is None
    assert parse_version("") is None
    assert parse_version(None) is None


def test_compare_versions():
    assert compare_versions((4, 2, 0), (4, 2, 0)) == 0
    assert compare_versions((4, 1, 9), (4, 2, 0)) == -1
    assert compare_versions((4, 3, 0), (4, 2, 0)) == 1
    assert compare_versions((4, 2, 1), (4, 2, 0)) == 1


def test_meets_floor_exact_boundary_passes():
    assert meets_floor("R", (4, 2, 0)) is True
    assert meets_floor("quarto", (1, 4, 0)) is True
    assert meets_floor("pandoc", (3, 1, 0)) is True


def test_meets_floor_below_fails():
    assert meets_floor("R", (4, 1, 9)) is False
    assert meets_floor("quarto", (1, 3, 999)) is False
    assert meets_floor("pandoc", (3, 0, 9)) is False


def test_meets_floor_unparseable_is_hard_fail():
    assert meets_floor("R", None) is False
    assert meets_floor("unknown-tool", (9, 9, 9)) is False


def test_check_floor_structure_pass():
    fc = check_floor("R", "R version 4.3.2 (2023-10-31)")
    assert fc["ok"] is True
    assert fc["below_floor"] is False
    assert fc["parseable"] is True
    assert fc["version"] == "4.3.2"
    assert fc["floor"] == "4.2.0"


def test_check_floor_below_floor_flag():
    fc = check_floor("quarto", "1.3.450")
    assert fc["ok"] is False
    assert fc["below_floor"] is True
    assert fc["parseable"] is True


def test_check_floor_unparseable_hard_fail():
    fc = check_floor("pandoc", "garbage output")
    assert fc["parseable"] is False
    assert fc["below_floor"] is True
    assert fc["ok"] is False
    assert fc["version"] is None


def test_hard_floors_match_plan():
    assert HARD_FLOORS["R"] == (4, 2, 0)
    assert HARD_FLOORS["quarto"] == (1, 4, 0)
    assert HARD_FLOORS["pandoc"] == (3, 1, 0)
