# omr-scholar

A pure-Python **stdio MCP server** for scholarly literature search,
deduplication, and citation export. Part of the *oh-my-research* MCP layer
(worker 1/5 of the build).

## How the installer launches it

The server speaks **MCP over stdio**. Launch with either:

```bash
python -m omr_scholar.server      # preferred (package entrypoint)
# or, from this directory:
python server.py                  # direct-script fallback
# or, after `pip install .`:
omr-scholar                       # console_scripts entrypoint
```

Recommended `config.toml` MCP server entry (Codex-style):

```toml
[mcp_servers.omr_scholar]
command = "python"
args = ["-m", "omr_scholar.server"]

[mcp_servers.omr_scholar.env]
# Optional polite-pool contact; NEVER required, never a real account.
OMR_SCHOLAR_MAILTO = "you@example.org"
# Optional cache root override (defaults to ~/.codex/omr/cache).
# CODEX_HOME = "/custom/.codex"
```

## Exposed MCP tools (exact names)

| Tool | Signature | Returns |
|---|---|---|
| `scholar.version` | `()` | `{"server":"omr-scholar","version":"0.1.0"}` — **zero side effects** (EV5 probe) |
| `scholar.search` | `(query, providers=[], year_from=None, limit=25)` | `{"records":[...], "providers":[...], "degraded":[...]}` |
| `scholar.resolve_doi` | `(doi)` | one normalized record or `null` (Crossref) |
| `scholar.dedup` | `(records[])` | `{"records":[...], "merge_report":[...], "stats":{...}}` |
| `scholar.to_bibtex` | `(records[])` | BibTeX string |
| `scholar.to_csl_json` | `(records[])` | CSL-JSON array |

### Normalized record schema

```json
{ "title": "", "authors": [{"family":"","given":""}|{"name":""}],
  "year": 2021, "doi": "10.x/y", "venue": "", "abstract": "",
  "provider": "crossref", "url": "https://doi.org/10.x/y" }
```

## Providers

| Provider | Status |
|---|---|
| **Crossref** | functional, **default**, no key |
| **OpenAlex** | functional, **default**, no key (abstract from inverted index) |
| Europe PMC | post-MVP **stub** — present, NOT default, returns `[]` |
| Semantic Scholar | post-MVP **stub** — present, NOT default, returns `[]` |

Default provider set = `["crossref", "openalex"]`. Opting into a stub
degrades gracefully (recorded in `degraded`) rather than crashing.

## Resilience

- **On-disk cache** under `~/.codex/omr/cache/` (resolves `CODEX_HOME`,
  then `$HOME/.codex` / `%USERPROFILE%\.codex`), keyed by
  `sha256(provider + normalized-query)`, TTL **14 days**, JSON files.
  A **pinned fixture** JSON dropped into the cache dir is honored
  regardless of age → deterministic offline runs (AC4).
- **Per-provider token-bucket rate limiter** (Crossref/OpenAlex ≤ ~3 req/s),
  **exponential backoff + jitter** on HTTP 429/503.
- On persistent single-provider failure: continue with the rest and record
  the degradation in the result metadata.
- Polite-pool `mailto` read from `OMR_SCHOLAR_MAILTO` (optional; never
  required, never a real account).

## Dedup rules (AC4)

1. **Exact DOI match** (normalized) → merge.
2. Else **fuzzy**: normalized title + year within ±1 **and**
   token-set ratio ≥ **0.92** → merge.
3. **Over-merge guard**: if *both* records have DOIs and they **differ**,
   fuzzy merge is **blocked** — two near-identical-title papers with
   different DOIs stay as **two** entries.

Token-set ratio is pure-Python (token sets + Dice/overlap), no external
fuzzy libraries.

## Tests

Offline, deterministic, no network, inline fixtures:

```bash
python -m pytest omr/mcp/omr_scholar/
```
