# oh-my-research

A one-time-installable bundle that turns the **OpenAI Codex desktop app** into a
guided research assistant for non-technical researchers. It supports a complete
four-stage workflow:

```
Hypothesis → Literature → Analysis → Manuscript
```

---

## 빠른 설치 (Quick Start)

> 선수 조건: **Codex 데스크톱 앱**이 이미 설치돼 있어야 하며, Python ≥ 3.10 ·
> R ≥ 4.2 · Quarto ≥ 1.4 · pandoc ≥ 3.1 가 필요합니다(없으면 설치 프로그램이
> 안내하며 중단 — 도구 설치 후 다시 실행하면 자동 복구). `knitr`/`rmarkdown`
> R 패키지는 `$omr-doctor`가 동의 기반으로 설치할 수 있습니다.

**방법 A — 터미널에서 직접 (가장 확실, 권장):**

```bash
git clone https://github.com/takjakim/oh_my_research.git
cd oh_my_research
bash install.sh           # Windows: 우클릭 → install.ps1 (또는 install.bat)
```

**방법 B — Codex 앱 에이전트에게 지시:** Codex 세션에서 아래를 그대로 입력
(워크스페이스 밖 쓰기·pip·네트워크에 대한 승인 클릭이 필요합니다):

```
github.com/takjakim/oh_my_research 를 클론하고 bash install.sh 를 실행해줘
```

**설치 후 (공통):**

1. **Codex 데스크톱 앱을 재시작**(또는 새 스레드) — 7개 스킬과 MCP 서버는
   세션 시작 시 로드됩니다.
2. `$omr-doctor` 실행 → **판정 OK** 확인 (`knitr`/`rmarkdown` 미설치 시
   동의하면 자동 설치).
3. 빈 연구 폴더를 만들어 Codex에서 **워크스페이스로 열고** → `$omr-start`.

> 되돌리기: `bash uninstall.sh` (Windows: `uninstall.ps1`) — 관리 영역만
> 제거하고 기존 Codex 설정·MCP 서버는 그대로 보존합니다.

---

## What it is

oh-my-research is a **Codex Agent Skills + MCP server bundle**, not a standalone
application. It plugs into Codex's existing extensibility surface:

- **Seven Agent Skills** (installed to `~/.agents/skills/`) that appear in the
  Codex `/` skill list and `codex://skills` panel.
- **Two MCP servers** (`omr-scholar`, `omr-render`) registered as top-level
  `[mcp_servers.*]` entries in `~/.codex/config.toml` — making their tools
  session-global.
- A **global `~/.codex/AGENTS.md` block** with always-on research norms
  (no fabricated citations, no invented statistics).
- **Local R + Quarto execution** — analysis is performed by your local
  R installation via the `omr-render` MCP server. No cloud analysis.

---

## 언어 / Language

이 도구는 **기본 언어가 한국어**입니다. 모든 사용자 대면 상호작용과 생성 산출물(research-question.md, analysis-plan.md, manuscript, doctor/installer 메시지)은 한국어로 작성됩니다.
This tool operates with **Korean as the default language** for all user-facing interaction and generated artifacts (research-question.md, analysis-plan.md, manuscript, doctor/installer messages).

Machine-interop tokens remain ASCII/English: BibTeX citation keys, results.json keys, YAML frontmatter keys, folder/file names, R code, MCP tool names, config keys, state.json keys, and CSL.

---

## The seven skills

| Skill | Invocation | Purpose |
|-------|-----------|---------|
| `omr-start` | `/` list or `$omr-start` | Hypothesis facilitation + workspace setup |
| `omr-lit` | `/` list or `$omr-lit` | Literature search, dedup, evidence table, BibTeX |
| `omr-analyze` | `/` list or `$omr-analyze` | Statistical analysis via local R/Quarto |
| `omr-write` | `/` list or `$omr-write` | IMRaD manuscript with citations → DOCX |
| `omr-status` | `/` list or `$omr-status` | Project state reporter / next-step guidance |
| `omr-doctor` | `/` list or `$omr-doctor` | Setup verification + toolchain detection |
| `omr-advisor` | `/` list or `$omr-advisor` | 지도교수 페르소나 콘텐츠 교차검증 + 실제 지도교수 프로필 학습 |

---

## The four workflow stages

### Stage 1 — Hypothesis (skill: `omr-start`)

Describe your research idea in plain language. The skill structures it into:
- A falsifiable research question
- Null (H0) and alternative (H1) hypotheses
- Variables table (IV/DV with measurement scales)
- Scaffolded project tree in your workspace

**Artifact:** `00_question/research-question.md`

### Stage 2 — Literature (skill: `omr-lit`, MCP: `omr-scholar`)

- Searches Crossref + OpenAlex (no API key required)
- Deduplicates records (exact DOI → merge; near-title fuzzy match with
  over-merge guard for papers with different DOIs)
- Exports `library.bib` (stable citation keys: `firstauthorYYYYword`)
- Produces `evidence-table.csv` (claim/finding/citation-key per row)

**Artifacts:** `10_literature/library.bib`, `evidence-table.csv`, `results.jsonl`

### Stage 3 — Analysis (skill: `omr-analyze`, MCP: `omr-render`)

- Profiles your dataset (types, missingness)
- Selects the statistically appropriate test via a decision table:
  - Independent Student t-test, Welch's t-test, paired t-test
  - One-way ANOVA, χ² test of independence, simple OLS regression
  - Mann-Whitney U / Wilcoxon signed-rank (mandatory non-parametric fallbacks)
- Enforces assumption violations (Shapiro-Wilk, var.test — all base-R, no `car`)
- STOPS and marks stage `blocked` when no test fits or data has problems
- Executes real local R via `omr-render`; emits `results.json` with a base-R
  writer using a generic key `statistic` (uniform across t/F/χ²/W) plus `df`,
  `p_value`, effect sizes (`cohen_d`/`mean_diff`/…), and a canonical ASCII
  `label` (e.g. `Student two-sample t-test`, `Welch`, `Mann-Whitney U`)

Workflow state is tracked in `.omr/state.json` using the schema `state["stages"]["stage3"]["status"]` with ASCII status values: `done` / `blocked` / `blocked-pending-user-decision` / `pending`. Stages mark `blocked` (never silently `done`) when assumption violations, no-fit conditions, or missing data are detected.

**Artifacts:** `20_analysis/analysis.qmd`, `analysis.html`, `outputs/results.json`

### Stage 4 — Manuscript (skill: `omr-write`)

- Assembles an IMRaD `manuscript.qmd` from template
- Fills Results from `results.json`, Introduction from `evidence-table.csv`
- Renders to **DOCX** (no PDF/TinyTeX in MVP) via Quarto + pandoc
- Verifies every in-text citation key resolves in `library.bib`
- Refuses to proceed if Stage 3 is blocked

**Artifact:** `30_manuscript/manuscript.docx`

### Stage — Advisor review (skill: `omr-advisor`)

On-demand cross-verification over existing workspace stage artifacts. The skill operates as a 지도교수 (research advisor) persona and performs active validation:

- **(A) Hypothesis ↔ Analysis-design fit:** Checks that analysis design matches stated hypotheses and variables
- **(B) Citations ↔ Claims:** Verifies every claim is backed by a citation key in `library.bib`; optional DOI spot-check via `omr-scholar`
- **(C) Analysis ↔ Conclusions:** Cross-checks manuscript numbers against `results.json` values
- **(D) Integrity:** Detects fabricated statistics or citations; prevents write-up of blocked stages

Findings are classified as 치명적 (fatal), 주의 (warning), or 경미 (minor). The skill also learns your real advisor's profile (name, affiliation, research field, methodological standards) from workspace metadata (ORCID, DOI list, `.bib` files), persisting the profile to `.omr/advisor-profile.md` and calibrating reviews accordingly.

**Read-only artifact access;** writes only `.omr/advisor-report.md` and `.omr/advisor-profile.md`. Non-blocking to workflow (does not alter `state.json` stages).

**Output:** Korean report with ASCII machine tokens.

---

## Installation

### Get the bundle

```bash
git clone https://github.com/takjakim/oh_my_research.git
cd oh_my_research
```

(Or download the release ZIP from the
[Releases page](https://github.com/takjakim/oh_my_research/releases) and unzip.)

### Prerequisites

**OpenAI Codex desktop app must already be installed.** The installer will abort with guidance if `~/.codex` is absent.

### macOS

```bash
# Download and unzip the bundle, then:
bash install.sh
```

Or double-click `install.command` (Gatekeeper-friendly).

**Optional flag:** `bash install.sh --skip-email` skips the polite-pool contact-email prompt. Email is optional, never required; when provided, it is stored as `OMR_SCHOLAR_MAILTO` in your config.

### Windows

Right-click `install.ps1` → Run with PowerShell. Or double-click `install.bat`.

**Optional flag:** `install.ps1 -SkipEmail` skips the contact-email prompt.

### Version requirements and hard failures

The installer **hard-fails (exit ≠0) if R, Quarto, or pandoc are missing or below the minimum version floor** (R ≥ 4.2, Quarto ≥ 1.4, pandoc ≥ 3.1) — by design, no partial or misleading setup. Skills, MCP servers, and config are still written; **re-running the installer after installing the missing tool self-heals idempotently**.

**R render packages (`knitr`, `rmarkdown`).** Quarto's knitr engine needs these
two R packages to execute the `.qmd` R chunks (the statistics themselves use
only base R / `stats` — no extra packages). `$omr-doctor` probes for them; if
absent it reports a failure with the exact fix and can install **only**
`knitr`+`rmarkdown` after explicit consent (interactive prompt or `--fix`),
never silently. Manual fix:
`Rscript -e 'install.packages(c("knitr","rmarkdown"), repos="https://cloud.r-project.org")'`.
Statistical packages are never auto-installed (reproducibility/integrity).

### Next steps after installation

1. Open Codex
2. Run **설정 점검** (`$omr-doctor`) to verify tools and dependencies
3. Run **연구 프로젝트 시작** (`$omr-start`) to begin your first project

### Safe config merge

The installer merges into `~/.codex/config.toml` as **two self-healing sentinel regions**:

- **ROOT-scalar region:** `sandbox_mode`, `approval_policy` — placed at the TOP of the file so they parse at TOML document root
- **TABLE region:** `[sandbox_workspace_write]`, `[mcp_servers.omr_scholar]`, `[mcp_servers.omr_render]` — appended at the END of the file

Both regions are **idempotent and self-healing** across re-runs. Pre-existing user config and user MCP servers are preserved byte-for-byte and never contaminated. A backup of `config.toml` and `AGENTS.md` is taken before any change.

## Uninstall / 되돌리기

To remove oh-my-research:

**macOS / Linux:**
```bash
bash uninstall.sh
```

**Windows:**
```powershell
.\uninstall.ps1
```

The uninstaller removes the two managed config regions, the seven skills, and the MCP bundle, while **preserving any user edits outside the managed regions byte-for-byte** (verified). Full-backup restore (`~/.codex/backups/omr/<timestamp>/`) is available as a corruption-only fallback.

---

## Requirements

| Tool | Minimum version | Purpose |
|------|----------------|---------|
| OpenAI Codex desktop app | Any | The host environment |
| Python | 3.10+ | MCP server runtime |
| R | 4.2.0+ | Local statistical analysis |
| Quarto | 1.4.0+ | Document rendering (DOCX) |
| pandoc | 3.1+ | Bundled with Quarto (standalone optional) |

R and Quarto are **detected but not installed** by oh-my-research.
`omr-doctor` reports their presence and version and provides install guidance
when they are absent or below the minimum floor.

**macOS Quarto installation:** On macOS, Quarto can be installed via `brew install --cask quarto` (requires admin password) or downloaded from [quarto.org](https://quarto.org). The installer self-heals idempotently on re-run after Quarto is installed.

---

## MVP scope

**In MVP (shipped):**
- Installer (macOS + Windows), backup/merge/uninstall, manifest
- Config region with sandbox/approval/MCP registration (no profiles)
- `omr-scholar` MCP: Crossref + OpenAlex, dedup, BibTeX/CSL-JSON, cache
- `omr-render` MCP: toolchain detection, scratch redirection, render, verify
- All seven skills (`omr-start`, `omr-lit`, `omr-analyze`, `omr-write`, `omr-status`, `omr-doctor`, `omr-advisor`)
- Student t / Welch t / paired t / ANOVA / χ² / OLS + Mann-Whitney U / Wilcoxon
- Mandatory assumption-violation handling (no silent coercion)
- DOCX output (no PDF/TinyTeX)

**Deferred (post-MVP):**
- Europe PMC + Semantic Scholar providers; Zotero API; PDF full-text ingest
- `renv.lock` reproducibility automation; Docker recipe
- Domain presets (clinical/RCT/psychometrics)
- Richer stats (mixed models, survival, power analysis)
- Linux installer; PDF/LaTeX manuscript output
- Multi-study workspace management

**Post-MVP additions (Addendum A8):**
- `omr-advisor` skill: 지도교수 cross-verification + advisor-profile learning

---

## Plan and tests

- Approved architectural plan: [`.omc/plans/oh-my-research.md`](.omc/plans/oh-my-research.md)
- Post-build hardening decisions and backlog: [`.omc/plans/oh-my-research-addendum.md`](.omc/plans/oh-my-research-addendum.md)
  - A1: Research-agent-toolkit
  - A2: Polish
  - A3: Korean-default
  - A4: State-schema
  - A5: Sentinel idempotency
  - A6: TOML two-region split
  - A7: results.json `statistic` key pin + AC10 chosen-label assertion precision
  - A8: omr-advisor skill (지도교수 cross-verification + advisor-profile learning)
- Acceptance test harness: [`tests/`](tests/) — see [`tests/README.md`](tests/README.md)

**Verification status:** Verified end-to-end on macOS with live Codex + R 4.5
+ Quarto 1.9. Offline 51 pass, MCP 79 pass, full live AC suite 64 pass / 1 skip,
zero product defects. Clean install/uninstall is byte-safe and preserves
pre-existing user Codex config & MCP servers.

Run the offline test subset (CI-safe, no external tools):

```bash
python -m pytest tests/ -m offline -v
```
