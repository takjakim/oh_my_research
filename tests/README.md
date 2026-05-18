# oh-my-research Test Suite

Acceptance test harness for AC1–AC10. Tests are organized into two tiers:

- **Offline subset** — no network, no `codex`, no R, no Quarto required.
  Safe to run in CI with zero external tools.
- **Full suite** — requires the `codex` CLI, R >= 4.2.0, and Quarto >= 1.4.0.
  Tests guarded by absent tools are automatically skipped with a clear message.

---

## Running tests

### Offline subset (CI-safe)

```bash
# From the repo root:
python -m pytest tests/ -m offline -v
```

### Full suite (requires codex + R + Quarto)

```bash
python -m pytest tests/ -v
```

### Specific tool subsets

```bash
# Only R-backed tests (needs R >= 4.2.0):
python -m pytest tests/ -m "offline or r"

# Only codex-backed tests:
python -m pytest tests/ -m codex
```

---

## Markers

| Marker   | Meaning                                            |
|----------|----------------------------------------------------|
| `offline`| No external tools required; always runs in CI      |
| `codex`  | Requires `codex` CLI binary in PATH                |
| `r`      | Requires R >= 4.2.0 (`Rscript`) in PATH            |
| `quarto` | Requires Quarto >= 1.4.0 (`quarto`) in PATH        |

Tests without a marker run in all modes.

---

## Fixture files

### `tests/fixtures/lit/`

Version-pinned oracle for AC4 (literature dedup):

| File | Purpose |
|------|---------|
| `records.json` | 12 normalized records (crossref + openalex providers) |
| `cache_crossref.json` | Pinned cache entry for crossref (served offline) |
| `cache_openalex.json` | Pinned cache entry for openalex (served offline) |
| `EXPECTED.json` | Oracle: merge pair, no-merge pair, expected keys, min counts |

The `records.json` fixture contains:
- A **true-duplicate pair** (records[0] and records[1]): same DOI `10.1000/xyz001`
  across crossref and openalex — must merge to ONE `library.bib` entry.
- A **negative pair** (records[2] and records[3]): near-identical titles
  ("Caffeine and alertness: a meta-analysis...") but different DOIs
  (`10.1000/xyz002` vs `10.9999/DIFFERENT001`) — must NOT merge (over-merge guard).

### `tests/fixtures/analysis/`

Canned datasets for AC5 and AC10 statistical test selection:

| File | Required statistical selection |
|------|-------------------------------|
| `ac5_clean.csv` | Student t-test (both normal, equal variance) |
| `ac10a_nonnormal.csv` | Mann-Whitney U (non-normality violation) |
| `ac10b_unequalvar.csv` | Welch t-test (unequal variance) |
| `ac10c_paired.csv` | Paired t-test (repeated subject_id) |
| `ac10d_nofit.csv` | BLOCKED — time-to-event, no MVP test fits |
| `ac10e_missing.csv` | BLOCKED-PENDING-USER-DECISION — missing outcome values |
| `EXPECTED.md` | Full statistical oracle with rationale for each fixture |

---

## Prerequisites for full suite

1. **codex CLI**: Install the OpenAI Codex desktop app; ensure `codex` is in PATH.
2. **R >= 4.2.0**: Install from https://cran.r-project.org/
3. **Quarto >= 1.4.0**: Install from https://quarto.org/docs/get-started/
4. **Python 3.10+** with `pytest` installed (`pip install pytest`).

---

## Integration risks flagged

Tests that are currently `skip`-ped because other workers have not yet completed
their output emit a clear reason. The following are known dependencies:

- **AC1 installer scripts** (`install.sh`, `install.ps1`): Expected from W2/W3
  installer worker. If absent, AC1 syntax tests skip gracefully.
- **AC3/AC5/AC6/AC7/AC8/AC9/AC10 codex-exec tests**: Require the full bundle
  to be wired. If skills are not yet installed, tests skip cleanly.
- **AC10 test-selection.md**: Expected from W4 omr-analyze worker. If absent,
  AC10 logic tests skip with a clear integration-risk message.
- **AC10 analysis.qmd.tmpl**: Expected from W4 omr-analyze worker.
