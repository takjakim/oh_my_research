# oh-my-research — Research Harness for the OpenAI Codex Desktop App

> A one-time-installable bundle that turns the OpenAI Codex desktop app into a
> guided research assistant: idea → literature → analysis → manuscript, for
> low-technical-skill general researchers.

---

## 0. Grounding Facts (from OpenAI Codex docs, May 2026; Architect-validated)

These shaped the architecture. Citations at end of file. The Architect verified
the capability model against official docs; the 5 corrections below are baked in.

- **Shared config home:** The Codex desktop app and CLI share `~/.codex/`
  (`CODEX_HOME` overridable). `config.toml` is editable from the app via
  *Settings → Open config.toml*. → We can ship one config layer for both.
- **AGENTS.md hierarchy:** Codex reads instruction files per directory in order
  (`AGENTS.override.md`, `AGENTS.md`, `TEAM_GUIDE.md`, `.agents.md`), global at
  `~/.codex/AGENTS.md`, capped by `project_doc_max_bytes` (default 32 KiB).
  *Confirmed valid as assumed.*
- **Agent Skills (primary AND discoverable capability unit):** A skill = a
  directory with `SKILL.md` (YAML frontmatter `name`/`description` + Markdown
  body) plus optional `scripts/`, `references/`, `assets/`, and
  `agents/openai.yaml`. **Global skills live at `~/.agents/skills/` (USER scope =
  `$HOME/.agents/skills`), NOT `~/.codex/skills`.** Repo-scoped skills live at
  `.agents/skills/` (scanned cwd→repo-root). `[[skills.config]]` in `config.toml`
  is only for *disabling* skills, never for *locating* them. Skills are
  first-class in the desktop app: enabled skills appear in the `/` command list,
  as `$skillname` mentions, and in the `codex://skills` panel. Progressive
  disclosure: only name/description loaded until invoked.
- **Custom slash prompts do NOT work in the desktop app.** `~/.codex/prompts/*.md`
  slash prompts are a CLI/IDE-only, *deprecated* surface; the GUI does not
  surface them. They therefore CANNOT be the researcher-facing entry point. We
  keep optional thin prompt shims **only** as a CLI/IDE/test-harness
  convenience, explicitly outside the GUI UX.
- **MCP servers:** stdio (and streaming HTTP) servers registered as top-level
  `[mcp_servers.*]` tables in `config.toml`; launched at session start; tools
  appear next to built-ins; inspectable via the app's built-in `/mcp`.
  *Confirmed valid as assumed.* This is the mechanism for real new capabilities
  (scholarly search, R/Quarto execution wrappers).
- **Profiles are NOT a usable delivery mechanism.** `[profiles.*]` is
  experimental, unsupported in the IDE extension; the desktop app has no profile
  selector and never receives `--profile`. Sandbox/approval/MCP settings must be
  written as **top-level** `config.toml` keys (global, not scoped):
  `sandbox_mode = "workspace-write"`, `approval_policy = "on-request"`,
  `[sandbox_workspace_write]`, `[mcp_servers.omr_scholar]`,
  `[mcp_servers.omr_render]`.
- **Sandbox + approval:** modes `read-only`, `workspace-write`,
  `danger-full-access`; approval policy `on-request`/`never`/etc.
  `workspace-write` restricts **writes only** — reads and exec are broadly
  allowed and there is **no `readable_roots` key**. **MCP child-process
  sandboxing is undocumented**, so the design is correct under **BOTH**
  host-privilege and workspace-sandboxed outcomes: the security boundary lives
  inside `omr-render` (command allow-list + forced cwd + path-escape rejection),
  all render scratch/output is redirected into the writable workspace, binaries
  are invoked by absolute path, and `omr-doctor` empirically *classifies* the
  active privilege model per machine.
- **`agents/openai.yaml` (Architect-corrected):** presentation+policy only,
  does NOT drive triggering (SKILL.md `description` does). Keys:
  `interface.{display_name,short_description,default_prompt,icon_small}`
  (no `icon` key), top-level `policy.allow_implicit_invocation`,
  `dependencies.tools[]` for MCP-dependent skills.
- **Automation:** `codex exec --cd <folder> --skip-git-repo-check --sandbox
  workspace-write --ask-for-approval never --json --output-schema <schema>` is a
  high-fidelity proxy for automating AC1–AC10 (same bundle), with a small
  enumerated GUI-only manual checklist. *Confirmed valid.*
- **Python runtime:** local Python 3.10+ venv for the two MCP servers is
  acceptable for MVP; single-file binaries deferred. *Confirmed valid.*

**Net architectural decision:** Capabilities are built as **Agent Skills**
(installed to `~/.agents/skills/`, each with `agents/openai.yaml` making them
the discoverable GUI entry points) **+ MCP servers** (top-level `config.toml`
registration) **+ global AGENTS.md** for always-on research norms. No profiles,
no GUI slash prompts. (Codex has no Claude-style subagents and no plugin
marketplace; this composition replaces both.)

---

## 1. Goal & Non-Goals

### Goal
Ship an installable bundle that, after a one-time setup, lets a non-technical
researcher carry a paper through four connected stages — (1) hypothesis /
research-question, (2) literature organization, (3) statistical analysis via
**real local R/Quarto execution**, (4) manuscript writing with citations —
entirely inside the Codex desktop app, with explicit handoff artifacts between
stages and reproducible outputs.

### Non-Goals (explicitly out)
- No custom GUI application. No standalone CLI binary. We only plug into Codex's
  existing extensibility surface.
- No deep/expert depth in any single stage (thin end-to-end MVP; depth deferred).
- No domain-specific presets (clinical, psychometrics, RCT templates) in MVP —
  they are a designed extension point only.
- No cloud-hosted analysis. Analysis is the researcher's *local* R/Quarto.
- No bundling/installing R, Quarto, or pandoc for the user (we *detect* and
  *guide*, we do not vendor toolchains).
- No paid/keyed scholarly APIs as a hard dependency (key-optional only).
- Not building Codex itself, model routing, or auth.

---

## 2. Architecture

### 2.1 Capability-to-Surface Mapping

| Capability | Codex Surface | Why |
|---|---|---|
| Always-on research norms (citation honesty, no fabricated stats, ask before destructive ops, stage discipline, **data privacy: researcher dataset contents are NEVER sent to scholarly providers and NEVER logged or written outside the study workspace**) | **Global `~/.codex/AGENTS.md`** (oh-my-research section, size-budgeted) | Must apply to every session unconditionally |
| Per-project research context (the active study's question, data dictionary) | **Project `AGENTS.md`** generated into workspace | Hierarchical, project-scoped |
| Stage 1 hypothesis facilitation + workspace onboarding | **Skill** `omr-start` | Interactive reasoning workflow w/ template assets |
| Stage 2 literature workflow logic | **Skill** `omr-lit` (calls scholarly MCP) | Orchestrates search → dedup → evidence table |
| Scholarly search / metadata / dedup / BibTeX | **MCP server** `omr-scholar` (stdio) | Real network capability + structured tools |
| Stage 3 analysis planning + execution logic | **Skill** `omr-analyze` (calls R/Quarto MCP) | Maps hypothesis → test → Rmd/Qmd |
| Detect + invoke local R/Quarto, render, verify outputs | **MCP server** `omr-render` (stdio, wraps local shell) | Deterministic tool surface > free-form shell |
| Stage 4 manuscript assembly + citation insertion | **Skill** `omr-write` (calls scholar MCP for CSL) | Template-driven writing |
| Project state reporting / next-step guidance | **Skill** `omr-status` | Reads `.omr/state.json`; tells low-skill user where they are |
| Sandbox/approval/MCP registration defaults | **Top-level `config.toml` keys** (`sandbox_mode`, `approval_policy`, `[sandbox_workspace_write]`, `[mcp_servers.*]`) inside a sentinel-delimited, backed-up, reversible region | Profiles are unsupported in the GUI; top-level keys are global Codex settings the app honors |
| Skill → MCP tool access | **SOLE hard requirement = the installer-registered `[mcp_servers.omr_scholar]`/`[mcp_servers.omr_render]` entries.** MCP stdio tools are SESSION-GLOBAL once registered (launched at session start, exposed session-wide next to built-ins; only server-global gates `enabled`/`enabled_tools`/`disabled_tools` exist — no per-skill scoping). `agents/openai.yaml` `dependencies.tools[]` is ADVISORY wiring/UX metadata only, explicitly non-load-bearing | Skills call `scholar.*`/`render.*` because they are globally available, regardless of any `dependencies.tools[]` declaration |
| Discoverable entry points (researcher-facing) | **The Skills themselves** — researcher-friendly skill names (`omr-start`, `omr-lit`, `omr-analyze`, `omr-write`, `omr-status`, `omr-doctor`). **Trigger matching comes from each SKILL.md YAML `description`** (front-loaded with researcher phrases). `agents/openai.yaml` is presentation+policy ONLY: `interface.display_name`, `interface.short_description`, `interface.default_prompt`, `interface.icon_small` (→ small SVG/PNG in skill `assets/`; optional `interface.icon_large`, `interface.brand_color`), and a TOP-LEVEL `policy.allow_implicit_invocation: true` (doc default is already true; set explicitly for self-documentation) | GUI surfaces enabled skills in the `/` list, as `$skillname`, and in `codex://skills`; custom slash prompts do NOT work in the GUI |
| Optional CLI/IDE/test convenience | **Thin `~/.codex/prompts/*.md` shims** (NOT part of GUI UX) | Lets `codex exec` / IDE drive the same skills for automated AC testing |
| One-time install | **Installer scripts** (`install.sh`, `install.ps1`) + `omr-doctor` skill | Low-skill setup, cross-platform |

Rationale for MCP-wrapping R/Quarto instead of letting the model free-type shell
commands: deterministic inputs/outputs, structured failure reporting, and a
verifiable artifact manifest. The design is correct under **both** MCP-privilege
outcomes (host-privilege OR workspace-sandboxed): `workspace-write` restricts
*writes* only — reads and exec are broadly allowed — so `omr-render` (a) enforces
its own security boundary (command allow-list, forced cwd, path-escape
rejection), and (b) redirects all scratch/output into the already-writable study
workspace so renders never depend on out-of-workspace writes (Section 4.2).

### 2.2 Component Diagram (ASCII)

```
                       OpenAI Codex Desktop App
                                  │
              ┌───────────────────┼─────────────────────────┐
              │                   │                         │
        config.toml          AGENTS.md                 Skills (GUI-native)
   (top-level keys, NO        (global norms +       (~/.agents/skills/*,
    profile): sandbox_mode    project context)       each w/ agents/openai.yaml;
   =workspace-write,                                  shown in / list, $name,
   approval_policy,                                   codex://skills panel)
   [mcp_servers.*]                                          │
              │                                              │
              │                              ┌───────────────┼───────────────┐
              │                              │       │       │       │       │
              │                        hypothesis literature analysis manuscript doctor
              │                          Skill     Skill     Skill    Skill    Skill
              │                                       │         │        │
              ▼                                       ▼         ▼        ▼
   ┌──────────────────────┐              ┌────────────────┐  ┌──────────────────┐
   │  MCP: omr-scholar     │◄─────────────┤ literature /    │  │ MCP: omr-render  │
   │  (stdio, Python)      │              │ manuscript      │  │ (stdio, Python)  │
   │  Crossref/OpenAlex/   │              │ Skills          │  │ wraps local      │
   │  PubMed/S2 + dedup +  │              └────────────────┘  │ Rscript/quarto/  │
   │  BibTeX/CSL export    │                                  │ pandoc, verify   │
   └──────────┬───────────┘                                   └────────┬─────────┘
              │ HTTPS (key-optional, polite pool)         host-privilege exec     │
              │                                          (allow-list + forced cwd)│
              ▼                                                         ▼
   Crossref / OpenAlex / Europe PMC / Semantic Scholar          Researcher's local
                                                                R + Quarto + pandoc
                                                                  (+ optional renv)

   Handoff artifacts flow left→right inside the project workspace:
   00_question/ ──► 10_literature/ ──► 20_analysis/ ──► 30_manuscript/
```

### 2.3 On-Disk Layout — Installed Bundle

Skills install to **`~/.agents/skills/`** (USER scope). Config/AGENTS.md/bundle
home/optional shims live under `~/.codex/`.

Each `SKILL.md` YAML `description` is the **trigger surface** and MUST
front-load researcher phrases (it, not `openai.yaml`, fires implicit
invocation):
- `omr-start`: "start a research project, set a research question / hypothesis"
- `omr-lit`: "literature search, find papers, organize references / citations"
- `omr-analyze`: "analyze my data, run a statistical test on a CSV"
- `omr-write`: "write up / draft the manuscript / paper / results section"
- `omr-status`: "what's next, project status / progress"
- `omr-doctor`: "check / verify my setup, is everything installed"

Each `agents/openai.yaml` is **presentation + policy only** (does NOT affect
triggering): `interface.display_name`, `interface.short_description`,
`interface.default_prompt`, `interface.icon_small` (→ asset in skill `assets/`;
optional `interface.icon_large`, `interface.brand_color`), and top-level
`policy.allow_implicit_invocation: true`. Skills that call an MCP server MAY
declare it via `dependencies.tools[]` (`type: "mcp"`, `value: "<server name>"`;
stdio → omit `transport`/`url`) but this is **advisory wiring/UX metadata only,
explicitly non-load-bearing** — it is NOT a runtime access gate. The SOLE hard
requirement for tool access is the installer-registered `[mcp_servers.*]`
entries (tools are session-global once registered). **Skill bodies reference
MCP tool names directly (`scholar.search`, `render.render`, …) and MUST tolerate
the `dependencies.tools[]` declaration being absent or imperfect.**

```
~/.agents/skills/                    # GLOBAL skills (USER scope) — discoverable in GUI
├── omr-start/                       # Stage 1 entry skill (researcher-friendly name)
│   ├── SKILL.md                     # YAML name: omr-start; description: trigger phrases
│   ├── agents/openai.yaml           # interface.display_name "Start a Research Project",
│   │                                #   short_description, default_prompt, icon_small;
│   │                                #   policy.allow_implicit_invocation: true
│   ├── assets/icon.svg
│   ├── references/picot-frap.md
│   └── assets/research-question.md.tmpl
├── omr-lit/
│   ├── SKILL.md                     # description front-loads literature triggers
│   ├── agents/openai.yaml           # display_name "Find & Organize Literature",
│   │                                #   icon_small; dependencies.tools[]: omr_scholar
│   ├── assets/icon.svg
│   └── assets/evidence-table.csv.tmpl
├── omr-analyze/
│   ├── SKILL.md                     # description front-loads "analyze my data" triggers
│   ├── agents/openai.yaml           # display_name "Run Statistical Analysis",
│   │                                #   icon_small; dependencies.tools[]: omr_render
│   ├── assets/icon.svg
│   ├── references/test-selection.md # decision table (see §3 Stage 3) — correctness core
│   └── assets/analysis.qmd.tmpl
├── omr-write/
│   ├── SKILL.md                     # description front-loads "write the manuscript"
│   ├── agents/openai.yaml           # display_name "Write the Manuscript", icon_small;
│   │                                #   dependencies.tools[]: omr_render, omr_scholar
│   ├── assets/icon.svg
│   └── assets/manuscript.qmd.tmpl, apa.csl
├── omr-status/
│   ├── SKILL.md                     # description: "project status / what's next"
│   ├── agents/openai.yaml           # display_name "Project Status", icon_small
│   └── assets/icon.svg
└── omr-doctor/
    ├── SKILL.md                     # description: "check / verify my setup"
    ├── agents/openai.yaml           # display_name "Check Setup", icon_small;
    │                                #   dependencies.tools[]: omr_render, omr_scholar
    ├── assets/icon.svg
    └── scripts/doctor.py            # env probe + version-floor + MCP-privilege
                                     #   classifier + EV5 session-global gate
                                     #   (bare codex exec → scholar/render .version)

~/.codex/
├── config.toml                      # gets top-level sentinel-delimited region:
│                                    #   sandbox_mode, approval_policy,
│                                    #   [sandbox_workspace_write],
│                                    #   [mcp_servers.omr_scholar/omr_render]
├── AGENTS.md                        # gets an <!-- omr:start -->...<!-- omr:end --> block
├── prompts/                         # OPTIONAL: CLI/IDE/test shims ONLY (not GUI UX)
│   ├── omr-start.md                 # `codex exec`/IDE convenience → invokes omr-start skill
│   ├── omr-lit.md                   #   (mirrors the skills for automated AC testing)
│   ├── omr-analyze.md
│   ├── omr-write.md
│   └── omr-status.md
├── omr/                             # bundle home (versioned, not Codex-native)
│   ├── VERSION
│   ├── mcp/
│   │   ├── omr_scholar/             # Python pkg: scholarly search MCP server
│   │   │   ├── server.py  (stdio MCP entrypoint; exposes scholar.version)
│   │   │   ├── providers/{crossref,openalex,europepmc,semanticscholar}.py
│   │   │   ├── dedup.py  bibtex.py  csl.py  cache.py
│   │   └── omr_render/
│   │       └── server.py            # detect + run Rscript/quarto/pandoc, verify;
│   │                                #   exposes render.version (EV5 gate)
│   ├── venv/                        # isolated Python venv for the two MCP servers
│   └── manifest.json                # records every file/region written (clean uninstall)
└── backups/omr/<timestamp>/         # pre-install copies of config.toml & AGENTS.md
```

The installer's `manifest.json` records files written to **both**
`~/.agents/skills/omr-*` and `~/.codex/*` so `uninstall` removes only
oh-my-research assets and restores `config.toml`/`AGENTS.md` from backup.

### 2.4 On-Disk Layout — Researcher Project Workspace

**Invariant: study folder == the thread's active workspace root.** The workspace
root is user-driven and fixed for the life of a thread; a skill cannot
programmatically create-and-switch it mid-thread. The `omr-start` skill detects
whether the active workspace is empty/uninitialized and, if so, instructs the
researcher to create/Open a study folder (Cmd+O / a `codex://new?path=<abs>`
deeplink) and re-run; once the workspace IS the (empty) study folder it
scaffolds the tree below **into that already-active root** (never a sibling
dir). See Stage 1 in Section 3.

```
<study-folder>  ==  <thread workspace root>/
├── AGENTS.md                        # project context: the question, data dictionary,
│                                    #   stage status table (kept ≤ a few KiB)
├── .agents/skills/                  # (empty; reserved for future per-project skills)
├── 00_question/
│   └── research-question.md         # Stage 1 artifact (hypothesis, PICO/FRAP, vars)
├── 10_literature/
│   ├── search-queries.md            # generated queries per provider
│   ├── results.jsonl                # raw normalized hits (provenance kept)
│   ├── library.bib                  # deduped BibTeX (Stage 2 → Stage 4 handoff)
│   └── evidence-table.csv           # claim/finding/measure/citation-key table
├── 20_analysis/
│   ├── data/                        # researcher drops CSV/xlsx here
│   ├── data-dictionary.md           # variable name/type/role
│   ├── analysis-plan.md             # hypothesis → chosen test → assumptions
│   ├── analysis.qmd                 # generated, executable
│   ├── analysis.html               # rendered output (Quarto)
│   └── outputs/                     # figures/, tables/, results.json (verified)
├── 30_manuscript/
│   ├── manuscript.qmd               # IMRaD template, references library.bib
│   ├── manuscript.docx / .pdf       # rendered
│   └── apa.csl
├── _quarto.yml                      # ties the project together (stretch: renv.lock)
└── .omr/
    ├── state.json                   # stage completion + artifact checksums
    └── render-log/                  # stdout/stderr of every render attempt
```

---

## 3. The Four Workflow Stages

Each stage: **Researcher does / Harness does / Artifacts / Handoff**.

### Stage 1 — Hypothesis & Research Question (skill: `omr-start`; GUI: `/` list, `$omr-start`, or implicit invocation)
- **Onboarding / workspace gate (NEW):** `omr-start` first checks the active
  thread workspace root. (a) If it is missing/non-existent or already contains a
  *different* project: it does NOT try to switch workspace; instead it tells the
  researcher in plain language to create an empty study folder and Open it as
  the workspace (macOS Cmd+O; or click the generated
  `codex://new?path=<abs-study-folder>` deeplink), then re-run `omr-start`. It
  also points them to `omr-doctor` if setup hasn't been verified. (b) If the
  active workspace root is empty (or already an omr project), it proceeds.
- **Researcher does:** creates/Opens the study folder as the workspace (one-time
  per study), then describes their idea in plain language and answers a short
  guided Q&A (population, comparison, outcome, expected direction, data they
  have or can get).
- **Harness does:** structures the idea into a falsifiable research question +
  primary hypothesis (H1) and null (H0); identifies independent/dependent
  variables and their measurement scale; flags whether stated data can answer
  it; scaffolds the project tree **into the already-active workspace root**
  (folders, project `AGENTS.md`, `_quarto.yml`, `.omr/state.json`).
- **Artifacts:** `00_question/research-question.md` (sections: Background,
  Research Question, Hypotheses H0/H1, Variables table with scale, Data plan,
  Out-of-scope), generated project `AGENTS.md`, `.omr/state.json` stage1=done
  with the resolved workspace-root path recorded.
- **Handoff → Stage 2:** the Variables table + Research Question become the
  source for literature search query generation; `research-question.md` path is
  recorded in `state.json`.

### Stage 2 — Literature Organization (skill: `omr-lit`; MCP `omr-scholar`)
- **Researcher does:** confirms/edits auto-generated search terms; optionally
  pastes seed DOIs or a Zotero export; marks results as include/exclude.
- **Harness does:** generates per-provider queries from Stage 1; calls
  `omr-scholar` to query Crossref + OpenAlex + Europe PMC + Semantic Scholar;
  normalizes, dedups (DOI → normalized-title+year fuzzy); builds an evidence
  table; exports a single deduped `library.bib`.
- **Artifacts:** `10_literature/search-queries.md`, `results.jsonl` (with per-hit
  provider provenance), `library.bib`, `evidence-table.csv`
  (columns: `citation_key, year, claim, finding, measure/effect, relevance,
  doi`).
- **Handoff → Stage 3:** evidence table informs expected effect direction /
  prior measures for the analysis plan; `library.bib` is reserved for Stage 4
  citations. `state.json` stage2=done + bib checksum.

### Stage 3 — Statistical Analysis (skill: `omr-analyze`; MCP `omr-render`)
- **Researcher does:** places data file(s) in `20_analysis/data/`; confirms the
  auto-derived data dictionary; approves the proposed statistical test (or the
  defined non-fit / blocked outcome).
- **Harness does:** profiles the dataset (columns, types, n, **missingness**);
  applies the `references/test-selection.md` decision table (§3.1) to map
  (variable scales × group count × paired/independent × design) → a concrete
  test with explicit assumption checks; generates `analysis.qmd`; calls
  `omr-render` to execute it with **local** R/Quarto; parses `results.json` and
  confirms the intended statistic actually appears (`t`, `df`, `p`, effect size,
  etc.).
- **Artifacts:** `20_analysis/data-dictionary.md`, `analysis-plan.md` (states
  chosen test, every assumption check + its result, and any fallback taken),
  `analysis.qmd`, `analysis.html`, `outputs/{figures,tables,results.json}`,
  `.omr/render-log/<ts>.log`.
- **Handoff → Stage 4:** `results.json` numeric values + figure/table file paths
  are injected into the manuscript template; `analysis-plan.md` feeds the
  Methods section. `state.json` stage3=done only if render succeeded **and**
  verification matched **and** no unresolved assumption violation / non-fit.

#### 3.1 Test-selection decision table (`references/test-selection.md` MUST encode this)

MVP test set is intentionally thin: **independent two-sample t-test (Student),
Welch's t-test (unequal-variance variant), paired t-test, one-way ANOVA,
χ² test of independence, simple OLS regression**, plus **Mann–Whitney U /
Wilcoxon signed-rank** included specifically as the documented non-parametric
fallback (integrity-critical, not scope creep — without it the only honest
response to a normality violation would be to refuse).

| Outcome (DV) | Predictor / design | Groups | Paired? | → Test (assumptions OK) |
|---|---|---|---|---|
| Continuous | 1 binary factor | 2 | No | Independent t-test (Student) |
| Continuous | 1 binary factor | 2 | Yes | Paired t-test |
| Continuous | 1 categorical factor | ≥3 | No | One-way ANOVA |
| Continuous | 1 continuous predictor | — | — | Simple OLS regression |
| Categorical | 1 categorical factor | any | No | χ² test of independence |

**Assumption checks and MANDATORY violation behavior (no silent substitution):**

| Assumption | Check | If VIOLATED → defined action |
|---|---|---|
| Normality (per group, continuous DV) | `stats::shapiro.test` (base R, no package) + QQ judgement; **n-aware cutoffs**: for **n < ~10** SW is underpowered → do NOT trust a non-significant SW; lean on QQ + effect-size-of-deviation and apply the conservative STOP-on-doubt default; for **n > ~5000** SW is over-sensitive (rejects trivial deviations) → judge by QQ + effect-size-of-deviation rather than the raw SW p; for **~10 ≤ n ≤ ~5000** use SW p (α=0.05) corroborated by QQ. STOP-on-doubt is the default whenever the n-band makes the test unreliable | Switch to non-parametric equivalent and **state it in `analysis-plan.md` and the manuscript Methods**: 2-group indep → Mann–Whitney U; 2-group paired → Wilcoxon signed-rank; ≥3 groups → **STOP**, mark stage `blocked` (Kruskal–Wallis is out of MVP set), explain in plain language |
| Equal variance (t-test) | **base-R `stats::var.test` (F) or `stats::bartlett.test`** — NO non-base package; `car::leveneTest` is NOT used on the integrity-critical path | Use **Welch's t-test** (report as Welch), never Student |
| Expected cell counts (χ²) | all expected ≥5 | If violated → **STOP**, mark `blocked`, explain (Fisher's exact is out of MVP set); do not report an invalid χ² |
| Independence of observations | from stated design | If clustered/repeated and not modellable by the MVP set → **STOP**, mark `blocked`, explain |
| OLS: linearity / homoscedasticity / residual normality | residual diagnostics | Report diagnostics; if grossly violated → **STOP**, mark `blocked`, recommend the researcher consult a statistician (do NOT silently report a misleading model) |

**Paired-design detection signal:** a design is treated as paired iff EITHER
(a) the researcher explicitly stated a within-subject / repeated-measures /
before-after design in the Stage 1 Q&A (recorded in `research-question.md`), OR
(b) the dataset contains a repeated subject-ID column (same identifier appearing
in both groups/conditions). Absent both signals the design is independent. This
makes AC10(c) unambiguously testable.

**Assumption-check dependency note (no silent install):** every
integrity-critical assumption check uses **base R / the `stats` package only**
(`stats::shapiro.test`, `stats::var.test`/`stats::bartlett.test`,
`stats::t.test(var.equal=FALSE)` for Welch, `stats::wilcox.test`,
`stats::chisq.test`, `stats::aov`, `stats::lm`). **No `car`/non-base package is
required for AC5 or AC10.** The `install.packages` allow-list entry in §4.2
therefore stays genuinely optional and approved-only — it exists solely for the
*rare* case a researcher's own analysis needs an extra package, which routes
through the §4.4 detect-and-instruct path (never silent). All AC5/AC10 fixtures
run on the base-R path with zero package installation.

**No-supported-test branch:** if the (scale × design) combination maps to no row
above (e.g., time-to-event, multilevel, multinomial, count outcome), `omr-analyze`
MUST: produce NO statistic, write `analysis-plan.md` documenting why no MVP test
fits, set `.omr/state.json` stage3=`blocked` with a plain-language reason, and
NOT proceed to Stage 4. It must never coerce the data into an inappropriate test.

#### 3.2 Missing-data policy (default = disclose and STOP)

The data profile reports per-column and row-wise missingness. **By default the
harness does NOT silently listwise-delete or impute.** If any analysis variable
has missing values it: states the missingness in `data-dictionary.md` and to the
researcher, sets stage3=`blocked-pending-user-decision`, and asks the researcher
to explicitly choose (complete-case analysis with disclosed N, or stop). Any
chosen handling is recorded in `analysis-plan.md` and the Methods section. No
imputation method is offered in MVP.

### Stage 4 — Manuscript Writing (skill: `omr-write`)
- **Researcher does:** reviews/edits prose; optionally chooses citation style
  (default APA via `apa.csl`); requests the rendered **DOCX** (PDF/TinyTeX is
  post-MVP — DOCX needs no LaTeX and keeps the bundle minimal, per D5).
- **Harness does:** assembles an IMRaD `manuscript.qmd` from the template;
  fills Introduction from `evidence-table.csv` claims (each backed by a
  `library.bib` key — no uncited factual claims), Methods from
  `analysis-plan.md` (incl. any test fallback / missing-data handling from
  §3.1/§3.2), Results from `results.json` + embedded figures/tables, Discussion
  as scaffolded prompts; renders via `omr-render` (**Quarto → DOCX** with
  `library.bib` + CSL); verifies every in-text citation key resolves in
  `library.bib`. Refuses to proceed if stage3 is `blocked`/`blocked-pending-user-decision`.
- **Artifacts:** `30_manuscript/manuscript.qmd`, `manuscript.docx`, `apa.csl`.
  `state.json` stage4=done. (`.pdf` deferred to post-MVP.)

The `omr-status` skill reads `.omr/state.json` and prints a stage checklist +
the next recommended skill to invoke, so a low-skill user always knows where
they are. (Invoked from the GUI `/` list / `$omr-status`, not a slash prompt.)

---

## 4. Reproducibility Design

### 4.1 Toolchain detection + minimum version floors (`omr-render` MCP + `omr-doctor` skill)
- On first analyze (and in `doctor`), probe in PATH and known install dirs:
  - **R:** `Rscript --version`; Win fallback `C:\Program Files\R\R-*\bin\Rscript.exe`,
    macOS `/usr/local/bin/Rscript`, `/opt/homebrew/bin/Rscript`,
    `/Library/Frameworks/R.framework/Resources/bin/Rscript`.
  - **Quarto:** `quarto --version`; Win `%LOCALAPPDATA%\Programs\Quarto\bin\quarto.exe`
    & `C:\Program Files\Quarto\bin`; macOS `/usr/local/bin`, `/opt/homebrew/bin`,
    `/Applications/quarto/bin`.
  - **pandoc:** `quarto` ships its own (preferred); also probe standalone
    `pandoc --version`.
- **Minimum supported versions (hard floor — `omr-doctor` reports below-floor as
  a HARD FAIL with upgrade guidance and refuses to mark setup OK):**
  **R ≥ 4.2.0**, **Quarto ≥ 1.4.0**, and if a standalone pandoc is used instead
  of Quarto's bundled one, **pandoc ≥ 3.1**. Versions are parsed from
  `--version` output and compared semantically; unparseable version → HARD FAIL.
- Resolved absolute paths + detected versions cached in
  `~/.codex/omr/manifest.json` → `tool_paths`/`tool_versions` (re-probed if
  invocation fails or version is below floor).

### 4.2 Invocation & the real security boundary (correct under BOTH privilege models)
- **MCP child-process sandboxing is undocumented.** The design is deliberately
  correct whether `omr-render`'s child processes run at **host privilege** OR
  are **workspace-sandboxed**. Decisive fact: Codex `workspace-write` restricts
  **writes only** — reads and exec are broadly allowed by default, and there is
  no `readable_roots` key. So the plan never relies on out-of-workspace writes
  and never relies on a restricted PATH.
- **Config (top-level keys, no profile).** `sandbox_mode = "workspace-write"`,
  `approval_policy = "on-request"`, and a `[sandbox_workspace_write]` table.
  The installer MUST keep tmp writable: assert
  `exclude_slash_tmp = false` and `exclude_tmpdir_env_var = false` (both are
  defaults — verify, never set to `true`). `writable_roots` (array of absolute
  paths) is a documented FALLBACK only and is **not** written for MVP (no silent
  install, no TinyTeX/PDF — DOCX only); documented as the post-MVP escape hatch
  for renv/TinyTeX.
- **Scratch/output redirected INTO the workspace (makes render work under either
  model).** Per invocation `omr-render` sets, before exec:
  `TMPDIR`/`TEMP`/`TMP` → `<study>/.omr/tmp/`;
  `quarto render --output-dir` inside the study;
  knitr/rmarkdown `intermediates_dir`/`output_dir` inside the study;
  `R_LIBS_USER` → `<study>/.omr/rlib/` (also aids reproducibility). This
  collapses every would-be out-of-workspace write into the already-writable
  workspace, so sandbox-confinement (if present) does not break rendering.
- **Absolute-path binary resolution.** All toolchain binaries (Rscript, quarto,
  pandoc) are invoked by ABSOLUTE path (from §4.1) — essential because exec of
  absolute system paths is allowed (read/exec, not write) even under a sandbox,
  sidestepping any restricted PATH.
- **`omr-render` is the security boundary** (authoritative regardless of the
  privilege model). Before executing anything it enforces:
  1. **Fixed command allow-list only:** `Rscript -e 'rmarkdown::render(...)'`,
     `quarto render <file>`, `quarto check`, `Rscript -e 'sessionInfo()'`,
     `Rscript -e 'install.packages(...)'` (NEVER on the integrity-critical
     analysis/assumption-check path — that path is base-R/`stats`-only per
     §3.1; this entry exists ONLY for a researcher's own optional extra package
     and fires only on explicit per-request approval via §4.4). No
     arbitrary/free-form shell from the model — ever.
  2. **Forced cwd = resolved study folder** (= thread workspace root, taken from
     `.omr/state.json`, canonicalized).
  3. **Path-escape rejection:** every file/path argument is resolved and must
     stay within the study-folder root; any `..`/symlink/absolute path escaping
     the root is rejected before exec.
  4. **Timeouts** (default 600 s) and full stdout/stderr captured to
     `.omr/render-log/<ts>.log`.
- Practical side effect: if MCP children are host-privilege, renders do **not**
  trigger per-command sandbox approval prompts — which is why the in-server
  boundary above is mandatory rather than relying on Codex's sandbox.
- **`omr-doctor` empirically CLASSIFIES the active privilege model** per machine
  (see AC9 / EV1 / Section 10): from inside the MCP server it attempts
  (a) a write to a host path *outside* the workspace and a write to
  `<study>/.omr/tmp/`; (b) exec of `Rscript --version` / `quarto --version` by
  ABSOLUTE path; (c) a tiny end-to-end `quarto render` of a one-line qmd into
  the workspace — reporting PASS/FAIL per check so the operator knows the real
  boundary and that rendering works on that machine.
- **Session-global MCP availability gate (EV5, installer-time PASS/FAIL).** Both
  servers expose a trivial **`version`/`ping`** tool (returns server name +
  version, zero side effects). `omr-doctor` runs a bare `codex exec` prompt that
  invokes **no omr skill** and calls `omr_scholar`'s and `omr_render`'s
  `version` tool directly; success empirically proves the tools are
  session-global from the `config.toml` `[mcp_servers.*]` registration alone —
  independent of any skill or `dependencies.tools[]` declaration. It also
  asserts both servers appear under the app's built-in `/mcp`. This converts EV5
  from an open assumption into an install-time gate.

### 4.3 Output verification
- After render, `omr-render` returns a **manifest**: produced file paths + sizes
  + mtime, plus a parsed `results.json` the Qmd is required to emit.
- **`results.json` emission has NO external R dependency.** `jsonlite` is an
  R-side package (NOT base R) and is deliberately **avoided**: the
  `analysis.qmd` template's final chunk uses a tiny **base-R JSON writer**
  (a ~15-line helper that serializes a flat named list of scalars/short vectors
  — all the harness needs for `results.json`). This removes any package
  dependency for the integrity-critical results path. (Note: the earlier
  installer wording "jsonlite-free pure-python" referred to the Python MCP
  side; clarified — the R template is jsonlite-free by using base-R, and the
  Python servers have no jsonlite dependency at all.) Any *other* R package the
  chosen test needs (e.g. `car` for Levene) follows the §4.4 detect-and-instruct
  path — never silent install.
- The `omr-analyze` skill asserts: (a) expected output files exist and are
  non-empty and newer than the render start time (freshness, no stale reuse);
  (b) `results.json` contains the intended statistic keys for the chosen test;
  (c) p-value within [0,1], n matches dataset rows used. Failing any → stage NOT
  marked done; surface a plain-language explanation.

### 4.4 Failure handling when R/Quarto absent or render fails
- **Absent toolchain:** stop before generating misleading output; emit a
  platform-specific install guide (links + the exact missing tool) via
  `omr-doctor`; offer a **dry-run mode** that still produces `analysis.qmd` +
  `analysis-plan.md` so the researcher can run it elsewhere — but `state.json`
  stage3 stays `blocked`, never `done`.
- **Render error:** classify (missing R package → suggest
  `install.packages()` line and ask approval; Quarto/pandoc error → surface log
  tail; data error → point to offending column). Never fabricate numeric
  results; never claim success without the verified manifest.

### 4.5 Reproducible project structure
- `_quarto.yml` makes the study a Quarto project (consistent render).
- **Stretch (not blocking MVP):** generate `renv.lock` / `renv::init()` and a
  `repro.md` "how to reproduce" recipe. MVP guarantees re-runnable Qmd + pinned
  `sessionInfo()` captured into `outputs/session-info.txt`.

---

## 5. Literature Subsystem (`omr-scholar` MCP server)

### 5.1 Providers (all usable without an API key)
| Provider | Use | Key needed | Politeness |
|---|---|---|---|
| **Crossref REST** | DOI metadata, broad coverage | No | Add `mailto` polite-pool param (from setup) |
| **OpenAlex** | Works/concepts, abstracts (inverted index) | No | `mailto` polite pool |
| **Europe PMC** | Biomed/life-sci full coverage of PubMed + more | No | UA + email header |
| **Semantic Scholar Graph** | TLDR/citation context | Optional key raises limits | Backoff on 429 |

Zotero: **optional** import of a user-exported `.bib`/RIS (no Zotero API in MVP).

### 5.2 Tools exposed (stdio MCP)
- `scholar.version()` → `{server: "omr-scholar", version}` (zero side effects;
  the EV5 session-global availability probe; mirrored by `render.version()` on
  `omr-render`).
- `scholar.search(query, providers[], year_from, limit)` → normalized records
  `{title, authors, year, doi, venue, abstract, provider, url}`.
- `scholar.resolve_doi(doi)` → single normalized record.
- `scholar.dedup(records[])` → deduped set + merge report (rule: exact DOI →
  merge; else normalized-title (lowercased, punctuation-stripped) + year within
  ±1 → fuzzy merge ≥ 0.92 token-set ratio).
- `scholar.to_bibtex(records[])` → BibTeX string with stable citation keys
  (`firstauthorYYYYword`).
- `scholar.to_csl_json(records[])` → CSL-JSON (for Quarto citeproc).

### 5.3 Rate-limit / no-key resilience
- Per-provider token-bucket limiter (conservative defaults: Crossref/OpenAlex
  ≤ ~3 req/s, S2 ≤ ~1 req/s); exponential backoff + jitter on HTTP 429/503;
  on persistent failure of one provider, continue with the rest and record the
  degradation in `results.jsonl` metadata.
- On-disk response cache (`~/.codex/omr/cache/`, keyed by provider+query,
  TTL 14 days) → reproducible and limit-friendly re-runs.
- `mailto`/contact email captured at setup, stored as an `env` entry on the
  top-level `[mcp_servers.omr_scholar]` table in `config.toml` (no profile),
  passed to enter polite pools; **never** required to be a real account.

---

## 6. Installer / Setup UX (one-time, low-skill, Win + Mac)

### 6.1 What the researcher does
1. Download the `oh-my-research` bundle (zip) and unzip.
2. Double-click / run one script:
   - **macOS:** `install.command` (wraps `install.sh`) — Gatekeeper-friendly note included.
   - **Windows:** `install.ps1` (right-click → Run with PowerShell), or `install.bat` shim.
3. Open the Codex desktop app, run the **Check Setup** skill (`omr-doctor`,
   from the `/` list or `$omr-doctor`) to verify, then create/Open an empty
   study folder as the workspace and run **Start a Research Project**
   (`omr-start`).

### 6.2 What the installer does (idempotent, reversible)
1. Detect `CODEX_HOME` (default `~/.codex`); abort with guidance if Codex not
   installed.
2. **Backup** `config.toml` and `AGENTS.md` → `~/.codex/backups/omr/<ts>/`.
3. Copy the six `omr-*` skill directories into **`~/.agents/skills/`** (USER
   scope; create the dir if absent — resolve `$HOME` / `%USERPROFILE%`). Copy
   `omr/` and the optional CLI/IDE `prompts/` shims into `~/.codex/`.
4. Create isolated Python venv `~/.codex/omr/venv`; `pip install` the two MCP
   server packages + pure-Python deps only (httpx, bibtexparser) — the Python
   servers have **no** `jsonlite`/R dependency; `results.json` is emitted by a
   base-R writer in the analysis template (§4.3). Probe for Python 3.10+; if
   absent, print platform install guidance and exit non-zero (no partial
   install).
5. **Merge** (not overwrite) into `config.toml` a single sentinel-delimited
   region containing exactly these **top-level** keys (NO `[profiles.*]`):
   - `sandbox_mode = "workspace-write"`
   - `approval_policy = "on-request"`
   - `[sandbox_workspace_write]` with `exclude_slash_tmp = false` and
     `exclude_tmpdir_env_var = false` (defaults — asserted, never set true);
     `writable_roots` NOT written for MVP (post-MVP escape hatch only)
   - `[mcp_servers.omr_scholar]` and `[mcp_servers.omr_render]` pointing at the
     venv interpreter (absolute path, OS-correct)
   The summary explicitly states these are **global Codex settings**, not scoped
   to oh-my-research. Sentinel region enables clean idempotent
   re-install/uninstall.
6. **Merge** an `<!-- omr:start -->…<!-- omr:end -->` block into
   `~/.codex/AGENTS.md` (size-budgeted, well under 32 KiB cap).
7. Prerequisite probe (reported): R, Quarto, pandoc — print detected
   versions/paths; **below the hard floor (R≥4.2 / Quarto≥1.4 / pandoc≥3.1) is a
   HARD FAIL with upgrade guidance**; write results to `manifest.json`.
8. Prompt once for a contact email (polite pool) — optional, skippable; written
   as `env` on `[mcp_servers.omr_scholar]`.
9. Print a "you're set" summary that (a) notes the config keys are global,
   (b) directs the user to run **Check Setup** then **Start a Research Project**
   from the app's `/` skill list (NOT slash prompts), and (c) states setup is
   only confirmed once **Check Setup** passes the EV5 session-global MCP gate
   (`omr_scholar.version` / `omr_render.version` callable + both under `/mcp`).
10. Write `manifest.json` listing every file/region added under BOTH
    `~/.agents/skills/omr-*` and `~/.codex/*`. **Uninstall design (M2):**
    `uninstall.sh` / `uninstall.ps1` delete the `omr-*` skill dirs + the
    `~/.codex/omr` bundle + shims, and remove **only the omr sentinel-delimited
    regions** from `config.toml` and `AGENTS.md` (leaving any user edits made
    after install intact — never a blanket overwrite). Full restore from
    `backups/<ts>/` is reserved strictly as a *corruption fallback* (offered
    only if the sentinel markers are missing/damaged), not the default path.

### 6.3 Cross-platform path handling
- All bundle code resolves `CODEX_HOME` via env then OS default
  (`%USERPROFILE%\.codex` on Windows, `$HOME/.codex` elsewhere) and the global
  skills dir as `%USERPROFILE%\.agents\skills` / `$HOME/.agents/skills`.
- MCP server config uses absolute interpreter path with OS-correct separators
  written by the installer at install time (no runtime guessing).
- Tool detection uses per-OS candidate lists (Section 4.1).
- Verification: the `omr-doctor` skill runs an end-to-end self-test
  (Section 10), incl. version-floor + MCP-privilege classification.

---

## 7. MVP Cut Line (ordered; thin end-to-end first)

**In MVP (ship order):**
1. Installer (mac+win), backup/merge/uninstall, manifest, doctor self-test.
2. Top-level config.toml keys (sandbox/approval) + MCP registration + global &
   project AGENTS.md blocks. Skills installed to `~/.agents/skills/` with
   `agents/openai.yaml`.
3. `omr-scholar` MCP: Crossref + OpenAlex only, dedup (positive + over-merge
   guard), BibTeX + CSL-JSON, cache.
4. `omr-render` MCP: version-floor detection, scratch redirection into
   workspace, render Qmd, return verified manifest, MCP-privilege classifier.
5. `omr-start` skill: workspace-gate onboarding + `research-question.md`
   scaffold + project init into the active workspace root.
6. `omr-lit` skill (queries → search → dedup → evidence table + library.bib).
7. `omr-analyze` skill: dataset profile + §3.1 decision table — **Student/Welch
   t-test, paired t-test, χ², one-way ANOVA, simple OLS, + Mann–Whitney U /
   Wilcoxon as the non-parametric fallback** (integrity-critical, not scope
   creep); mandatory assumption-violation behavior + no-fit/missing-data STOP;
   base-R `results.json`; local render + verification.
8. `omr-write` skill: IMRaD Qmd from template, citations from library.bib,
   render to **DOCX** (no PDF/TinyTeX in MVP), citation-key resolution check.
9. `omr-status` skill (state reporter); optional CLI/IDE prompt shims for
   automated AC testing (not GUI UX).

**Deferred (post-MVP extensions):**
- Europe PMC + Semantic Scholar providers; Zotero API; PDF full-text ingest.
- `renv.lock` reproducibility automation; Docker recipe.
- Domain presets (clinical/RCT/psychometrics) as drop-in skill packs.
- Richer stats (mixed models, survival, multiple comparisons, power analysis).
- Linux installer; PDF/LaTeX manuscript polish; figure styling themes.
- Multi-study workspace management; collaboration/export bundles.

---

## 8. Concrete Acceptance Criteria (measurable)

- **AC1 Install:** On a clean Mac and clean Windows machine with Codex
  installed, running the installer completes with exit 0, writes the six
  `omr-*` skill dirs (each with `SKILL.md` + `agents/openai.yaml`) to
  `~/.agents/skills/` and bundle/shims to `~/.codex/`, and the merged
  `config.toml` contains **top-level** `sandbox_mode`/`approval_policy`/
  `[sandbox_workspace_write]`/`[mcp_servers.*]` (NO `[profiles.*]`) inside one
  sentinel region; `config.toml`/`AGENTS.md` remain valid (Codex starts a
  session without config errors). Re-running the installer is idempotent (no
  duplicate skill dirs or config regions). **`uninstall` removes the `omr-*`
  skills + bundle and removes ONLY the omr sentinel-delimited regions from
  `config.toml`/`AGENTS.md`; a user edit added (outside the omr region) after
  install survives uninstall** (full-backup restore is a corruption-only
  fallback, asserted NOT to fire in the normal-uninstall test).
- **AC2 Doctor + EV5 session-global gate:** The `omr-doctor` skill (invoked
  from the app's `/` list / `$omr-doctor`) reports presence/version/abs-path of
  R, Quarto, pandoc, Python; both MCP servers appear under the app's built-in
  `/mcp`; and the six `omr-*` skills appear in the `/` list and `codex://skills`
  panel. **EV5 install-time PASS/FAIL gate:** a bare `codex exec` prompt that
  invokes NO omr skill successfully calls `omr_scholar`'s and `omr_render`'s
  `version` tool — empirically proving the MCP tools are session-global from the
  `[mcp_servers.*]` registration alone, independent of any skill or
  `dependencies.tools[]` declaration. Installer setup is not "OK" unless this
  gate passes.
- **AC3 Stage 1:** With an empty study folder Opened as the workspace and the
  prompt *"I think daily caffeine affects reaction time"*, the `omr-start`
  skill produces `00_question/research-question.md` containing an explicit
  H0/H1 and a Variables table naming IV (caffeine) and DV (reaction time) with
  measurement scales, scaffolds the project tree **into the active workspace
  root**, and records that root path in `.omr/state.json`. If the workspace is
  non-empty/uninitialized, `omr-start` instead emits the create/Open-folder
  guidance + `codex://new?path=` deeplink and does NOT scaffold elsewhere.
- **AC4 Stage 2 (deterministic, both dedup directions):** Run against a
  **version-pinned fixture** — a fixed query string plus a frozen
  expected-records JSON fixture served from the on-disk cache (NOT a live
  network call, so "≥10 hits" is deterministic and not network-flaky). Assert:
  (a) ≥ 10 normalized records across ≥ 2 providers; (b) **positive dedup** — a
  seeded true-duplicate pair (same DOI / same normalized title+year, two
  providers) merges into exactly ONE `library.bib` entry, recorded in the merge
  report; (c) **negative dedup (over-merge guard)** — a seeded pair of *distinct
  papers with near-identical titles but different DOIs* must produce **TWO**
  separate entries and MUST NOT be merged; (d) `evidence-table.csv` has ≥ 5 rows
  each carrying a citation key present in `library.bib`. The fixture (query,
  inputs, expected entry keys, expected merge/no-merge pairs) is checked into
  `tests/fixtures/lit/` and version-pinned.
- **AC5 Stage 3 (core end-to-end, POSITIVE correctness):** The canned
  `data.csv` (numeric outcome, 2-level group) is constructed so it
  **demonstrably passes `stats::shapiro.test` per group AND base-R equal-variance
  (`stats::var.test`)** — i.e. the independent two-sample **Student** t-test is
  the *correct* selection (this pairs with AC10's wrong-fit negatives to prove
  selection is right, not just output-shaped). With the Stage 1 hypothesis,
  `omr-analyze` generates `analysis.qmd`, renders via `omr-render`, and
  `outputs/results.json` contains a Student two-sample t-test with numeric `t`,
  `df`, `p_value` (∈[0,1]) and an effect size; `analysis-plan.md` records both
  assumption checks as PASSED and the test as Student (not Welch/non-parametric);
  `analysis.html` exists and is newer than the run start. Assert NO package was
  installed (base-R path only). If R/Quarto absent or below floor, stage is
  reported `blocked` (not `done`) with version/install guidance and a dry-run
  `analysis.qmd` still produced.
- **AC6 Stage 4:** The `omr-write` skill produces `manuscript.docx` rendered
  via Quarto with the Results section reporting the AC5 t/df/p values verbatim
  from `results.json`, an Introduction containing ≥ 3 in-text citations all
  resolving to keys in `library.bib`, and zero unresolved citation keys.
- **AC7 Handoff integrity:** `.omr/state.json` shows stages 1–4 done with
  artifact checksums; deleting `library.bib` makes `omr-write` fail loudly
  rather than fabricate citations.
- **AC8 No-fabrication guard:** With network disabled, `omr-lit` reports
  failure/degradation and does **not** invent references; `omr-analyze` with a
  malformed CSV reports the data error and does **not** invent results.
- **AC9 MCP boundary classification & path-escape rejection:** `omr-doctor`
  empirically CLASSIFIES the active privilege model — from inside the MCP server
  it (a) attempts a write to a host path *outside* the workspace AND a write to
  `<study>/.omr/tmp/`; (b) execs `Rscript --version`/`quarto --version` by
  absolute path; (c) runs a tiny end-to-end `quarto render` of a one-line qmd
  into the workspace — reporting PASS/FAIL per check and a definite
  host-privilege vs sandbox-confined verdict; the verdict does not change the
  authoritative in-server boundary, and (c) must PASS on both models.
  Independently, requesting `omr-render` to render a Qmd whose path argument
  resolves outside the study-folder root is **rejected before exec** (no process
  spawned, explicit path-escape error logged to `.omr/render-log/`).
- **AC10 Wrong-fit / assumption-violation guard (research-integrity):** Given a
  dataset+hypothesis combination that violates the chosen test's assumptions or
  fits no MVP test, `omr-analyze` must NOT silently report an inappropriate
  statistic. Specifically: (a) **non-normal 2-group** data → it switches to
  Mann–Whitney U *and* `analysis-plan.md` + Methods explicitly state the switch
  and why (assert no Student/Welch t reported as the headline result);
  (b) **unequal-variance 2-group** (detected via base-R `stats::var.test`, no
  `car`) → reports **Welch's** t (assert it is not labeled Student);
  (c) **paired data analyzed as if independent is prevented** — fixture supplies
  the paired signal per §3.1 (a repeated subject-ID column AND/OR an explicit
  within-subject statement recorded in `research-question.md`); assert a paired
  test is chosen, never an independent one;
  (d) **no-fit design** (e.g. a time-to-event / count outcome) → `results.json`
  contains NO statistic, `state.json` stage3=`blocked` with a plain-language
  reason, and Stage 4 refuses to proceed;
  (e) **missing data in an analysis variable** → stage3=`blocked-pending-user-decision`,
  no silent listwise-deletion/imputation, missingness disclosed in
  `data-dictionary.md`.

---

## 9. Risks & Mitigations

> The prompt-vs-skill, profile, and skills-path uncertainties are **resolved
> decisions** now (see Section 11), not open risks. Remaining risks:

| Risk | Impact | Mitigation |
|---|---|---|
| MCP child-process privilege undocumented (host OR sandboxed) | Render could fail (sandboxed) or over-reach (host) | Design correct under BOTH: in-server boundary (allow-list + forced cwd + path-escape) + all scratch/output redirected into workspace + absolute-path binaries (§4.2); `omr-doctor` AC9 classifies per machine |
| Non-expert user gets an inappropriate statistical test silently | Research-integrity failure (invalid published results) | §3.1 decision table with mandatory assumption-violation behavior (Welch / non-parametric fallback / STOP+blocked) + AC10 wrong-fit guard; never coerce data into a non-fitting test |
| R/Quarto/pandoc absent OR below version floor OR skewed across machines | Stage 3/4 fail or behave inconsistently | Detection + **hard minimum-version floor** (R≥4.2, Quarto≥1.4, pandoc≥3.1) reported by `omr-doctor` + per-OS install/upgrade guidance + dry-run fallback; never fake outputs; `sessionInfo()` captured |
| Scholarly API rate limits / outages / no key | Stage 2 weak or fails | Multi-provider fallback, token buckets, backoff, on-disk cache, polite-pool email; degrade gracefully + record provenance |
| `config.toml`/`AGENTS.md` corruption on merge | Breaks user's Codex | Pre-install backup, sentinel-delimited regions, idempotent merge, reversible uninstall, validate config parses post-merge |
| AGENTS.md 32 KiB budget exceeded | Instructions truncated | omr block size-budgeted (<~6 KiB); deep logic lives in Skills (progressive disclosure), not AGENTS.md |
| Model fabricates citations/stats | Research integrity failure | AGENTS.md hard rule + AC8 guards + verification gates that mark stages blocked, not done |
| Scope creep (depth in one stage) | Misses thin end-to-end | Section 7 cut line is contractual; extensions are explicitly post-MVP |
| Python not present for MCP servers | Install fails | Probe + clear guidance + non-partial install; consider future single-file binary (deferred) |

---

## 10. Verification Steps (per AC)

Automation harness: `codex exec --cd <study-folder> --skip-git-repo-check
--sandbox workspace-write --ask-for-approval never --json --output-schema
<schema>` against the same `~/.codex` + `~/.agents/skills` bundle (high-fidelity
proxy). GUI-only manual checklist is small and enumerated below.

- **AC1:** Fresh VM/clean-account on macOS + Windows; run installer; assert exit
  0; assert six `~/.agents/skills/omr-*` dirs each contain `SKILL.md` (with a
  trigger-phrase `description`) + `agents/openai.yaml`; assert merged
  `config.toml` sentinel region has `sandbox_mode`, `approval_policy`,
  `[sandbox_workspace_write]` with `exclude_slash_tmp=false` &
  `exclude_tmpdir_env_var=false` & **no** `writable_roots`, `[mcp_servers.*]`,
  and **no `[profiles.*]`**; run installer again → diffs empty (idempotent);
  **append a user-owned key OUTSIDE the omr region to `config.toml` and a user
  line outside the omr block in `AGENTS.md`, then run uninstall → assert the omr
  regions are gone, the skill dirs/bundle removed, and the user's
  outside-region edits SURVIVE byte-for-byte (corruption-fallback restore did
  NOT fire)**; launch Codex session → no config error.
- **AC2:** Invoke `omr-doctor` skill (via `codex exec` + the prompt shim, and
  **manually in the GUI**); assert it prints versions+abs paths; `/mcp` in app
  → both `omr_scholar`, `omr_render` listed with tools. **EV5 gate:** run a bare
  `codex exec` prompt invoking NO omr skill that directly calls
  `omr_scholar.version` and `omr_render.version` → assert both return their
  server name+version (proves session-global availability from `[mcp_servers.*]`
  alone, no skill / `dependencies.tools[]` involved); fail the setup if either
  errors. **GUI-manual:** confirm the six `omr-*` skills appear in the `/` list
  and `codex://skills` panel.
- **AC3:** Scripted `codex exec --cd <empty-folder>` feeding the caffeine
  prompt → assert `research-question.md` regex-matches H0/H1 headings + a
  Variables table with IV/DV rows; assert tree scaffolded **in that folder**
  and its path in `.omr/state.json`. Negative: `codex exec --cd <non-empty>` →
  assert no scaffold + Open-folder/deeplink guidance emitted.
- **AC4:** Preload the cache from `tests/fixtures/lit/` (version-pinned query +
  expected records) so the run is offline-deterministic. Run `omr-lit` on the
  pinned query; assert ≥10 records, ≥2 providers in `results.jsonl`; parse
  `library.bib` → exact expected entry-key set, no duplicate DOIs; assert the
  seeded true-dup pair collapsed to ONE entry in the merge report; assert the
  seeded distinct-but-near-title pair (different DOIs) produced TWO entries and
  did NOT merge; `evidence-table.csv` ≥5 rows, every key ∈ bib.
- **AC5:** Provide canned `data.csv` constructed to PASS `stats::shapiro.test`
  per group AND base-R `stats::var.test` (so Student t is the correct pick);
  run `omr-analyze`; assert render exit 0, `outputs/results.json` keys
  `{t,df,p_value,effect_size}` with valid ranges, `analysis-plan.md` records
  both assumption checks PASSED and test=Student (not Welch/non-parametric),
  assert NO `install.packages` ran (base-R path), `analysis.html` mtime > run
  start; then rename Rscript off PATH → assert stage `blocked` + dry-run qmd
  present + version/install guidance shown. Also run `omr-doctor` against a
  deliberately old R/Quarto → assert below-floor HARD FAIL.
- **AC6:** Run `omr-write`; parse `manuscript.docx` (unzip → document.xml) for
  the exact t/df/p strings from `results.json`; count ≥3 citation keys, assert
  all resolve in `library.bib`; assert zero unresolved keys in render log.
- **AC7:** Inspect `.omr/state.json` checksums; delete `library.bib`; rerun
  `omr-write` → asserts hard failure message, no `.docx` produced.
- **AC8:** Disable network; `omr-lit` → degraded/failure message, no `.bib`
  invented; feed malformed CSV to `omr-analyze` → data-error message, no
  `results.json` written.
- **AC9:** Run `omr-doctor`; assert it reports per-check PASS/FAIL for
  (a) host-outside-workspace write attempt + `<study>/.omr/tmp/` write,
  (b) absolute-path `Rscript --version`/`quarto --version` exec, (c) tiny
  end-to-end `quarto render` into the workspace — and a definite
  host-privilege/sandbox-confined verdict; assert check (c) PASSES regardless of
  verdict. Separately, drive `omr-render` with a Qmd path arg resolving outside
  the study root → assert NO subprocess spawned and an explicit path-escape
  error in `.omr/render-log/`.
- **AC10:** Run four pinned `tests/fixtures/analysis/` datasets through
  `omr-analyze`: (a) non-normal 2-group → assert `results.json`/`analysis-plan.md`
  report **Mann–Whitney U** with the switch stated, and assert NO Student/Welch
  t is presented as the headline result; (b) unequal-variance 2-group → assert
  result labeled **Welch** (regex on `analysis-plan.md`/Methods), not Student;
  (c) paired design → assert a paired test is chosen (assert it is NOT the
  independent t); (d) count/time-to-event outcome → assert `results.json` has NO
  statistic, `state.json` stage3=`blocked` with a plain-language reason, and
  `omr-write` refuses to proceed; (e) dataset with missing values in an analysis
  variable → assert stage3=`blocked-pending-user-decision`, missingness
  disclosed in `data-dictionary.md`, and no rows silently dropped.

**GUI-only manual checklist (cannot be `codex exec`-automated):** (1) AC2 skill
visibility in the `/` list & `codex://skills` panel; (2) `omr-start` implicit
invocation triggering in a fresh GUI thread; (3) the `codex://new?path=`
deeplink opening the chosen folder as the workspace. All other ACs are fully
automatable via the `codex exec` proxy.

---

## 11. Resolved Architecture Decisions

The Architect researched the official OpenAI Codex docs and validated the
capability model. All prior open questions are now closed (D1–D8, incl. D2a/D2b;
EV5 closed at install time):

| # | Decision | Resolution (baked into the plan) |
|---|---|---|
| D1 | Global skills path | **`~/.agents/skills/`** (USER scope = `$HOME/.agents/skills`), NOT `~/.codex/skills`. Repo-scoped skills stay at `.agents/skills` (cwd→root scan). `[[skills.config]]` is for *disabling* only. (Sections 0, 2.1, 2.3, 6.2, AC1, §10.) |
| D2 | Researcher-facing entry points & trigger surface | **The Skills themselves**, not slash prompts (custom `~/.codex/prompts/*.md` do NOT work in the desktop app). **Triggering (incl. implicit invocation) is driven by each SKILL.md YAML `description`**, which MUST front-load researcher phrases; `agents/openai.yaml` is presentation+policy ONLY and does NOT affect matching. GUI surfaces them in the `/` list, as `$skillname`, and in `codex://skills`. Prompt shims kept ONLY for CLI/IDE/test automation. |
| D2a | `agents/openai.yaml` schema (Architect-corrected) | File path `<skill>/agents/openai.yaml` confirmed; the file is OPTIONAL. Use `interface.display_name`, `interface.short_description`, `interface.default_prompt`, **`interface.icon_small`** (→ asset in skill `assets/`; optional `interface.icon_large`, `interface.brand_color`) — there is **no `icon` key**. `allow_implicit_invocation` lives under a **top-level `policy:`** block (NOT `interface:`); doc default already `true`, set explicitly for self-documentation. `dependencies.tools[]` (`type: "mcp"`, `value: "<server name>"`; stdio → omit `transport`/`url`) is **ADVISORY wiring/UX metadata only — NOT a runtime access gate**; kept as best-effort documentation, explicitly non-load-bearing. |
| D2b | MCP tool access model (EV5 closed) | **MCP stdio tools are SESSION-GLOBAL once registered in `config.toml`** (launched at session start, exposed session-wide next to built-ins; only server-global gates `enabled`/`enabled_tools`/`disabled_tools` exist — no per-skill scoping). The **SOLE hard requirement** for tool access is the installer-registered `[mcp_servers.omr_scholar]`/`[mcp_servers.omr_render]` entries; skills call `scholar.*`/`render.*` directly and tolerate `dependencies.tools[]` being absent/imperfect. Both servers expose a side-effect-free `version`/`ping` tool; `omr-doctor` converts EV5 into an **install-time PASS/FAIL gate** (bare `codex exec`, no skill, calls each `version` tool + asserts `/mcp` listing). EV5 confidence: effectively closed at install time. |
| D3 | Sandbox/approval/MCP delivery | **Drop `[profiles.*]`** (experimental, no GUI selector, IDE-unsupported). Write **top-level** `sandbox_mode = "workspace-write"`, `approval_policy = "on-request"`, `[sandbox_workspace_write]` (`exclude_slash_tmp=false`, `exclude_tmpdir_env_var=false`; NO `writable_roots` for MVP), `[mcp_servers.*]` in a sentinel-delimited, backed-up, reversible region. Installer states these are global Codex settings. |
| D4 | Workspace root | **User-driven and fixed per thread**; a skill cannot create-and-switch the active workspace mid-thread. `omr-start` gates on workspace state, guides the user to create/Open the study folder (Cmd+O / `codex://new?path=<abs>` deeplink), then scaffolds **into the already-active root**. Invariant: study folder == workspace root. |
| D5 | MCP child-process privilege (Architect-corrected) | **Undocumented; design correct under BOTH host-privilege AND workspace-sandboxed.** `workspace-write` restricts *writes* only (no `readable_roots`; reads/exec broadly allowed). Boundary lives in `omr-render` (allow-list + forced cwd + path-escape). Render works regardless because all scratch/output is **redirected into the workspace** (`TMPDIR`/`TEMP`/`TMP`→`.omr/tmp`, `--output-dir`, `intermediates_dir`, `R_LIBS_USER`→`.omr/rlib`) and binaries are invoked by **absolute path**. `writable_roots` is the documented post-MVP escape hatch (renv/TinyTeX), unused in MVP. |
| D6 | Statistical correctness (new — Critic C2) | §3.1 decision table + mandatory assumption-violation behavior (Welch for unequal variance; Mann–Whitney U / Wilcoxon as the documented non-parametric fallback; STOP→`blocked` where no MVP test fits or ≥3-group non-normal / χ² low-cell / non-independence); explicit no-fit branch; default missing-data policy = disclose & STOP (§3.2). Enforced by AC10. |
| D7 | Dedup correctness (new — Critic C3) | AC4 uses a version-pinned offline fixture; asserts BOTH positive merge (true dups → 1 entry) AND negative no-merge (distinct papers, different DOIs, near titles → 2 entries) to guard over-merging. |
| D8 | Automation & runtime | `codex exec --cd <folder> --skip-git-repo-check --sandbox workspace-write --ask-for-approval never --json --output-schema` is a high-fidelity AC1–AC10 proxy; small enumerated GUI-only manual checklist (Section 10). Python 3.10+ venv acceptable for MVP; single-file binaries deferred. |

### Doctor-probe empirical-verification items

These cannot be answered from docs and are verified per machine at runtime by
`omr-doctor` (gating onboarding, encoded as ACs):

- **EV1 (→ AC9):** Active MCP privilege model classified — from inside the MCP
  server: (a) write to a host path *outside* workspace AND to `<study>/.omr/tmp/`;
  (b) absolute-path `Rscript/quarto --version` exec; (c) tiny end-to-end
  `quarto render` into the workspace. Report PASS/FAIL per check + a definite
  host vs sandboxed verdict; the in-server boundary is authoritative regardless,
  and (c) must PASS under either model.
- **EV2 (→ AC2/AC5):** R / Quarto / pandoc / Python presence, version (vs the
  hard floor R≥4.2 / Quarto≥1.4 / pandoc≥3.1 → below-floor = HARD FAIL),
  absolute path on this machine (PATH + per-OS candidate dirs).
- **EV3 (→ AC2, GUI-manual):** The six `omr-*` skills are visible in the app's
  `/` list and `codex://skills` panel, and `omr-start` implicit invocation
  fires in a fresh GUI thread **from its SKILL.md `description`** (not
  `openai.yaml`).
- **EV4 (→ AC9):** `omr-render` path-escape rejection actually blocks (no
  subprocess spawned) for a path argument outside the study root.
- **EV5 (→ AC2) — CLOSED at install time:** MCP stdio tools are session-global
  from `[mcp_servers.*]` registration alone (no per-skill scoping;
  `dependencies.tools[]` is advisory/non-load-bearing). Converted from an open
  assumption into an **install-time PASS/FAIL gate**: a bare `codex exec` prompt
  invoking NO omr skill calls `omr_scholar.version` and `omr_render.version`
  successfully, and both servers appear under `/mcp`. This empirically confirms
  availability independent of any skill declaration; installer setup is not
  "OK" unless the gate passes.

---

## Sources
- [Configuration Reference – Codex](https://developers.openai.com/codex/config-reference)
- [Config basics – Codex](https://developers.openai.com/codex/config-basic)
- [Advanced Configuration – Codex](https://developers.openai.com/codex/config-advanced)
- [Sample Configuration – Codex](https://developers.openai.com/codex/config-sample)
- [Custom instructions with AGENTS.md – Codex](https://developers.openai.com/codex/guides/agents-md)
- [Agent Skills – Codex](https://developers.openai.com/codex/skills)
- [Customization – Codex](https://developers.openai.com/codex/concepts/customization)
- [Custom Prompts – Codex](https://developers.openai.com/codex/custom-prompts)
- [Slash commands – Codex IDE](https://developers.openai.com/codex/ide/slash-commands)
- [Commands – Codex app](https://developers.openai.com/codex/app/commands)
- [Settings – Codex app](https://developers.openai.com/codex/app/settings)
- [Sandbox – Codex](https://developers.openai.com/codex/concepts/sandboxing)
- [Slash commands in Codex CLI](https://developers.openai.com/codex/cli/slash-commands)
- [openai/skills catalog](https://github.com/openai/skills)
