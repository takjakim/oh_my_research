"""Dedup unit tests: positive merge AND negative over-merge guard (AC4)."""

from omr_scholar.dedup import dedup_records


def test_exact_doi_merge_two_providers():
    recs = [
        {"title": "Attention Is All You Need", "year": 2017,
         "doi": "10.5555/3295222.3295349", "provider": "crossref"},
        {"title": "Attention is all you need", "year": 2017,
         "doi": "https://doi.org/10.5555/3295222.3295349",
         "provider": "openalex"},
    ]
    out = dedup_records(recs)
    assert len(out["records"]) == 1
    assert out["stats"]["merged"] == 1
    merged = out["records"][0]
    # provider list is unioned
    assert "crossref" in merged["provider"] and "openalex" in merged["provider"]
    assert any(e["reason"] == "exact-doi" for e in out["merge_report"])


def test_fuzzy_title_year_merge_when_no_doi():
    recs = [
        {"title": "Deep Residual Learning for Image Recognition",
         "year": 2016, "provider": "crossref"},
        {"title": "Deep residual learning for image recognition.",
         "year": 2016, "provider": "openalex"},
    ]
    out = dedup_records(recs)
    assert len(out["records"]) == 1
    assert out["stats"]["merged"] == 1


def test_fuzzy_blocked_by_year_gap():
    recs = [
        {"title": "Deep Residual Learning", "year": 2010,
         "provider": "crossref"},
        {"title": "Deep Residual Learning", "year": 2016,
         "provider": "openalex"},
    ]
    out = dedup_records(recs)
    assert len(out["records"]) == 2


def test_negative_over_merge_guard_distinct_dois():
    """Near-identical titles, DIFFERENT DOIs -> MUST stay TWO entries."""
    recs = [
        {"title": "A Survey of Transformer Models for Text Classification",
         "year": 2021, "doi": "10.1000/survey.aaa.2021",
         "provider": "crossref"},
        {"title": "A Survey of Transformer Models for Text Classification",
         "year": 2021, "doi": "10.2000/survey.bbb.2021",
         "provider": "openalex"},
    ]
    out = dedup_records(recs)
    assert len(out["records"]) == 2, "distinct DOIs must NOT merge"
    assert out["stats"]["merged"] == 0
    assert out["stats"]["kept_separate_guard"] == 1
    assert any(
        e["action"] == "kept-separate"
        and e["reason"] == "doi-mismatch-blocked"
        for e in out["merge_report"]
    )


def test_below_threshold_not_merged():
    recs = [
        {"title": "Neural machine translation", "year": 2015,
         "provider": "crossref"},
        {"title": "Statistical phrase based decoding", "year": 2015,
         "provider": "openalex"},
    ]
    out = dedup_records(recs)
    assert len(out["records"]) == 2


def test_dedup_is_deterministic_and_stable_order():
    recs = [
        {"title": "Paper One", "year": 2020, "doi": "10.1/a"},
        {"title": "Paper Two", "year": 2020, "doi": "10.1/b"},
        {"title": "Paper One", "year": 2020, "doi": "10.1/a"},
    ]
    o1 = dedup_records(recs)
    o2 = dedup_records(recs)
    assert o1 == o2
    assert [r["title"] for r in o1["records"]] == ["Paper One", "Paper Two"]
