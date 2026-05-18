"""AC4 Stage-2 deterministic OFFLINE run.

Pins the version-pinned fixtures into a temp on-disk cache (so NO network
is touched), runs the full scholar.search -> dedup -> to_bibtex/to_csl_json
pipeline, and asserts:
  (a) >= 10 normalized records across >= 2 providers
  (b) positive dedup: seeded true-duplicate (same DOI, two providers)
      merges into exactly ONE library.bib entry, recorded in the report
  (c) negative dedup (over-merge guard): seeded distinct papers with
      near-identical titles but different DOIs -> TWO entries, NOT merged
  (d) every record carries a citation key present in library.bib
"""

import json
import os

import pytest

from omr_scholar import core
from omr_scholar.bibtex import assign_keys
from omr_scholar.cache import CacheStore

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "lit")


def _load(name):
    with open(os.path.join(FIXTURE_DIR, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture()
def pinned_cache(tmp_path, monkeypatch):
    """Pin crossref+openalex fixtures into an offline cache dir."""
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    # Block real network: any httpx use would fail loudly.
    monkeypatch.setenv("OMR_SCHOLAR_MAILTO", "")

    cache_root = os.path.join(str(tmp_path), "omr", "cache")
    os.makedirs(cache_root, exist_ok=True)
    store = CacheStore(cache_root)

    with open(os.path.join(FIXTURE_DIR, "query.txt"), encoding="utf-8") as fh:
        query = fh.read().strip()

    # Must match the cache-query string core.search builds.
    cache_q = f"{query}|year_from={None}|limit={25}"
    store.set("crossref", cache_q, _load("crossref.json"), pinned=True)
    store.set("openalex", cache_q, _load("openalex.json"), pinned=True)
    return query, store


def test_ac4_offline_pipeline(pinned_cache):
    query, store = pinned_cache
    expected = _load("expected.json")

    # --- search (offline, served from pinned cache) ---
    res = core.search(query, providers=["crossref", "openalex"], cache=store)
    records = res["records"]

    # (a) >= 10 records across >= 2 providers
    assert len(records) >= expected["min_records"], (
        f"only {len(records)} records"
    )
    provs = {r["provider"] for r in records}
    assert len(provs) >= expected["min_providers"]
    assert res["degraded"] == [], "no provider should be degraded offline"

    # --- dedup ---
    dd = core.dedup(records)
    deduped = dd["records"]
    assert len(deduped) == expected["expected_total_after_dedup"]

    # (b) positive dedup: same-DOI pair -> exactly ONE entry, in report
    pos_doi = expected["positive_merge_pair"]["doi"].lower()
    matching = [
        r for r in deduped
        if (r.get("doi") or "").lower().endswith(pos_doi.split("/")[-1])
    ]
    assert len(matching) == 1, "true duplicate must merge to ONE entry"
    merged = matching[0]
    assert "crossref" in merged["provider"]
    assert "openalex" in merged["provider"]
    assert any(
        e["action"] == "merged" and e["reason"] == "exact-doi"
        for e in dd["merge_report"]
    )

    # (c) negative dedup over-merge guard: two distinct surveys survive
    neg = expected["negative_no_merge_pair"]
    survey_titles = [
        r for r in deduped
        if (r.get("title") or "").lower().startswith("a survey of transformer")
    ]
    assert len(survey_titles) == 2, "distinct DOIs must NOT over-merge"
    dois = sorted((r.get("doi") or "").lower() for r in survey_titles)
    assert dois == sorted([neg["doi_a"].lower(), neg["doi_b"].lower()])
    assert dd["stats"]["kept_separate_guard"] >= 1

    # --- exports ---
    bib = core.to_bibtex(deduped)
    csl = core.to_csl_json(deduped)
    keys = assign_keys(deduped)

    # (d) every record's citation key is present in library.bib
    assert len(keys) == len(deduped)
    for k in keys:
        assert f"{{{k}," in bib, f"citation key {k} missing from bibtex"
    csl_ids = {item["id"] for item in csl}
    assert csl_ids == set(keys), "CSL ids must match bibtex keys"

    # expected pinned entry keys are present
    for ek in expected["expected_entry_keys"]:
        assert ek in keys, f"expected entry key {ek} not produced"

    # determinism: a second run yields identical output
    res2 = core.search(query, providers=["crossref", "openalex"], cache=store)
    assert core.to_bibtex(core.dedup(res2["records"])["records"]) == bib
