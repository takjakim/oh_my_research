# Version-pinned literature fixtures (AC4)

Frozen, network-free inputs for the deterministic AC4 Stage-2 run.

- `query.txt` — the fixed query string.
- `crossref.json` — frozen Crossref result set (records to pin into cache).
- `openalex.json` — frozen OpenAlex result set (records to pin into cache).
- `expected.json` — expected dedup outcome:
  - `expected_entry_keys` — citation keys that MUST appear in `library.bib`.
  - `positive_merge_pair` — a true-duplicate pair that MUST merge to ONE.
  - `negative_no_merge_pair` — distinct papers, near-identical titles,
    DIFFERENT DOIs, that MUST stay as TWO entries (over-merge guard).
  - `min_records`, `min_providers` — AC4 (a) thresholds.

These files are version-pinned: do not regenerate from a live API.
