# omr-render

The **authoritative in-server security boundary** + toolchain render MCP
server for oh-my-research. It is correct regardless of whether the MCP child
process runs at host privilege or is workspace-sandboxed (plan section 4.2).

## stdio launch command

The server speaks the MCP **stdio** transport. Launch it as:

```
python -m omr_render.server
```

Run from inside the package's parent directory (so `omr_render` is importable),
or install the package and use the console script:

```
omr-render
```

For Codex `config.toml` registration (installer worker):

```toml
[mcp_servers.omr_render]
command = "<venv-python>"
args = ["-m", "omr_render.server"]
```

`<venv-python>` is the isolated venv interpreter at `~/.codex/omr/venv`.

## Exact MCP tool names & signatures

Other workers (installer / skills) MUST use these exact names:

| Tool name | Arguments | Returns |
|---|---|---|
| `render.version` | *(none)* | `{"server":"omr-render","version":"0.1.0"}` — **zero side effects** (EV5 probe). |
| `render.detect` | *(none)* | `{"tools":{"R":{...},"quarto":{...},"pandoc":{...}}, "ok":bool, "core_tools_ok":bool, "notes":str}` — each tool entry has `found,path,candidates,version,floor,below_floor,ok,error`. |
| `render.render` | `qmd_path:str` (req), `study_root:str` (req), `form:str="quarto_render"`, `timeout:int=600`, `allow_install:bool=false`, `output_subdir:str="outputs"` | On success: `{"ok":true,"ts","study_root","qmd","log","manifest":[{path,rel,size,mtime}],"results_json":obj|null,"spawned":true}`. On failure: `{"ok":false,"error":<class>,"message",...}`. |
| `render.classify_privilege` | `study_root:str` (req) | `{"verdict":"host-privilege"|"sandbox-confined"|"indeterminate","checks":[...],"render_works":bool,"note":str}` (AC9). |

### Hard version floors (HARD FAIL below; unparseable => HARD FAIL)

- **R ≥ 4.2.0**
- **Quarto ≥ 1.4.0**
- **pandoc ≥ 3.1** (only relevant if a standalone pandoc is used instead of
  Quarto's bundled one)

### Render error classes (`render.render` failure `error` field)

`path-escape`, `allow-list`, `gated`, `toolchain-blocked`, `timeout`,
`missing-r-package`, `quarto-pandoc`, `data-error`, `unknown`,
`invalid-args`, `invalid-root`.

## The security boundary (enforced BEFORE any process spawn)

1. **Fixed command allow-list only** — `quarto render <file>`, `quarto check`,
   `quarto --version`, `Rscript -e 'rmarkdown::render(...)'`,
   `Rscript -e 'sessionInfo()'`, `Rscript --version`,
   `Rscript -e 'install.packages(...)'` (gated, off by default — never on the
   integrity-critical analysis path). No free-form shell, ever.
2. **Forced cwd** = canonicalized `study_root`.
3. **Path-escape rejection** — every path arg is realpath-resolved (symlinks
   too); any `..`/symlink/abs path escaping `study_root` is rejected **before
   spawning any process**, with an explicit error logged to
   `<study_root>/.omr/render-log/<ts>.log` (AC9).
4. **Scratch/output redirected into the workspace** — `TMPDIR`/`TEMP`/`TMP` →
   `<study_root>/.omr/tmp/`, `R_LIBS_USER` → `<study_root>/.omr/rlib/`,
   `quarto render --output-dir` inside the study.
5. **Absolute-path binary invocation** (from `render.detect`), never PATH.
6. **Timeout** default 600 s; full stdout/stderr captured to
   `<study_root>/.omr/render-log/<ts>.log`.

## Output verification (plan 4.3)

`render.render` returns a **manifest** (produced file paths + sizes + mtime,
filtered to files modified at/after render start) and the parsed `results.json`
the Qmd emits (searched at `<study>/outputs/results.json` then
`<study>/results.json`). It never fabricates results and never claims success
without the verified manifest.

## Failure handling (plan 4.4)

Absent/below-floor toolchain → structured `toolchain-blocked` error so the
caller marks the stage `blocked` (never `done`) and emits dry-run guidance.
Render errors are classified (missing R package / quarto-pandoc / data error).

## Tests

Pure offline unit tests (no R/Quarto/pandoc, no `mcp` package required):

```
python -m pytest omr/mcp/omr_render/
```
