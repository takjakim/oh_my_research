# oh-my-research — Plan Addendum A1: research-agent-toolkit review

Source reviewed: `github.com/takjakim/research-agent-toolkit` (Korean academic research
harness — Claude Code slash commands + TypeScript helpers + Python aux; license
"Private — 개인 연구 도구"). Decision (user, 2026-05-18): **record as post-MVP
backlog only**. NO change to the ralplan-approved MVP cut line or current
ultrapilot build. Code is NOT copied (license + stack mismatch); only
concepts/algorithms may be re-implemented in our Python/Skills stack later.

## Stack/architecture note (why not direct reuse)
Toolkit = Claude Code `.claude/commands/*.md` + TS/Node + Zotero/NotebookLM/Context7
MCP. oh-my-research = Codex desktop app + Python MCP servers + `~/.agents/skills`.
Toolkit has NO statistical-analysis / Rmd·Qmd reproducibility (our differentiator).
Transfer is spec/algorithm-level only.

## Post-MVP backlog (prioritized)

1. **Korean scholarly providers for `omr-scholar` — ELEVATE above Europe PMC/S2.**
   For a Korean researcher KCI/DBpia matter more than Europe PMC/Semantic Scholar.
   - KCI via data.go.kr KCIOpenApi (`apis.data.go.kr/B552540/KCIOpenApi/openApi/search/article`,
     XML, needs `KCI_SERVICE_KEY`); port Korean author parsing (1-char family +
     given for 가-힣 names) into a Python `providers/kci.py`.
   - DBpia, KIST, Google Scholar (SerpAPI) as further providers.
   Recommended order: KCI → DBpia → (then the originally-deferred Europe PMC / S2).
2. **3-tier citation-fabrication defense, formalized** for `omr-write`/`omr-lit`:
   (a) prompt-level: cite only library.bib keys else emit `[CITATION NEEDED]`;
   (b) structural: mandatory citation-verifier pass after manuscript assembly;
   (c) batch audit: an `omr-verify`-style cross-check vs Crossref/KCI/S2.
   Port the Korean-aware APA regex (`가-힣` parenthetical/narrative) from
   `citation-verifier.ts` into the Python audit tool.
3. **Korean-aware citation schema** enrichment for `omr-scholar` normalized record:
   `titleKo, journalKo, kciId, kciJournalId, isKorean, verified,
   verificationSource, apaReference/apaParenthetical/apaNarrative (cached)`.
4. Survey design + AI-respondent simulation (`survey-sim`) → social-science
   domain pack (aligns with plan §7 deferred psychometrics presets).
5. Committee/peer-review simulation (advisor + examiner personas, 7-dimension
   structured peer review) → post-MVP `omr-review` companion skill.
6. Zotero Web API write/sync → concrete reference for the plan's deferred Zotero
   API item (re-implement in Python; do not port TS).
7. Korean plagiarism/paraphrase integrity pack (paraphrase-check,
   copykiller-proof) → deferred Korean integrity extension.

## Explicitly NOT adopted
- `.claude/commands` / TS / Node toolchain / Zotero-NotebookLM-Context7 MCP set
  (violates approved single-stack Codex+Python design).
- Anything touching the statistical-analysis stage (toolkit has none).

## Addendum A2: Phase-5 non-blocking residue (post-MVP polish)
1. Add a root `pytest.ini` registering `offline/codex/r/quarto` markers (combined multi-dir pytest invocation otherwise exits non-zero on PytestUnknownMarkWarning; individual spec-prescribed suites are clean).
2. Installer: move the prereq HARD-FAIL probe (Step 7) BEFORE the config/AGENTS merge (Step 5/6) so an abort leaves no placeholder config region (currently self-heals on successful re-run).
3. `skills/omr-write/agents/openai.yaml` `dependencies.tools[]` lists only `omr_render`; §2.3 also mentioned `omr_scholar`. Advisory-only/non-load-bearing — cosmetic alignment.

## Addendum A3: Localization — Korean default (user decision 2026-05-18)
Harness operates in **Korean by default** for ALL user-facing interaction and
generated artifact prose; **ASCII/English kept for machine tokens** (BibTeX
citation keys, results.json keys, YAML frontmatter keys, folder/file names, R
code, MCP tool names, config keys, sentinel markers, state.json keys, CSL).
Scope: skills (SKILL.md, agents/openai.yaml, templates prose, AGENTS.md omr
region, test-selection.md prose, omr-status) AND installer/doctor CLI
(install.sh/install.ps1, doctor.py). AC machine-checked tokens MUST stay stable;
tests realign to assert on stable ASCII tokens, not English prose.

## Addendum A4: .omr/state.json schema PINNED (defect found by first live-codex AC run)
Canonical schema (skill writes it; tests + AC assert it; plan prose "stageN=done" is shorthand for this):
{
  "workspace_root": "<abs path>",
  "stages": {
    "stage1": {"status": "done|blocked|blocked-pending-user-decision|pending", "artifacts": {...}, "checksums": {...}},
    "stage2": {...}, "stage3": {...}, "stage4": {...}
  }
}
Status string VALUES are ASCII machine tokens: `done` / `blocked` / `blocked-pending-user-decision` / `pending`.
Rule: read/write via `state["stages"]["stageN"]["status"]`. No flat `state["stageN"]`.

AC10 test-gating rule: scenarios whose verdict needs RENDERED assumption diagnostics
(ac10a non-normal, ac10b unequal-variance — Shapiro/var.test computed by the R render)
must be `@skip_no_quarto` (and `@skip_no_r`). Pre-render structural decisions
(ac10c paired-design detection, ac10d no-fit, ac10e missing-data) MUST be decided
and written to analysis-plan.md + state.json BEFORE the render step (dry-run safe
per §4.4), so they pass without Quarto. omr-analyze SKILL must write the
pre-render decision (chosen test w/ canonical ASCII label OR blocked reason) to
analysis-plan.md + state BEFORE step-5 render.

## Addendum A5: installer sentinel-merge idempotency/self-heal defect (found on 2nd real install)
`_merge_sentinel_region` (install.sh) + PowerShell equivalent only handle the FIRST
start sentinel and copy an orphan END-before-START into the "before" content
(sticky), don't remove duplicate regions, and on an orphan START-with-no-END drop
all trailing content (data-loss risk). Symptom seen: live ~/.codex/config.toml had
1 start + 2 end markers (orphan `# <<< oh-my-research (managed) <<<` retained
across re-install). Functionally non-breaking (orphan is a TOML comment; active
region correct) but violates idempotency + uninstall correctness.

REQUIRED FIX: strip phase must self-heal ANY prior corrupted state — remove every
start/end sentinel line and all content between a start and its following end,
remove orphan/standalone sentinel lines anywhere, collapse to ZERO regions, then
append exactly ONE clean region. Mirror in uninstall (remove region + orphans,
preserve user edits). Idempotent under: clean / orphan-end / orphan-start /
duplicate-region / no-region. Apply to install.sh, install.ps1, uninstall.sh,
uninstall.ps1.

## Addendum A6: TOML root-key reparenting defect (append-position) — BLOCKER for real install
The managed region is appended at END of config.toml. Its bare top-level keys
`sandbox_mode`/`approval_policy` then sit AFTER pre-existing user `[tables]`, so
TOML reparents them INTO the last user table (e.g. [mcp_servers.omx_*]) — Codex
never receives root sandbox_mode/approval_policy AND the user's last table is
polluted. Confirmed: post-install tomllib shows sandbox_mode=None at root.
REQUIRED REDESIGN: split the managed config into TWO self-healing sentinel
regions — (1) root-scalar block (`sandbox_mode`,`approval_policy`) merged at the
TOP of config.toml (before any [table]); (2) table block
(`[sandbox_workspace_write]`,`[mcp_servers.omr_*]`) appended at END. Both use the
A5 self-healing strip. Re-verify tomllib: sandbox_mode/approval_policy parse at
ROOT, user tables uncontaminated, idempotent. Until fixed, REAL install is
deferred; verify in sandbox only. Live ~/.codex restored to pristine
(20260518T014323Z) — zero omr region, user omx_* intact.

## Addendum A6 CLOSED + A5/A4/localization verified (independent sandbox, 20/20 GREEN)
Post-fix independent full-lifecycle sandbox verify (realistic user seed: leading
root keys + omx_* tables): tomllib confirms sandbox_mode/approval_policy at ROOT,
user tables byte-uncontaminated, 1 ROOT+1 TABLE region, no profiles/writable_roots,
-m launch, skills Korean+A4, venv+MCP import, AGENTS merge+Korean+user-preserved,
idempotent byte-identical, uninstall→pristine byte-identical zero-residue.
Source bundle GREEN at installer-lifecycle level. Remaining: live-codex Stage 3/4
end-to-end (AC5/AC6/AC10a/b) needs Quarto≥1.4 (env prerequisite, not a code defect);
AC10c/d/e live-codex timeout was stale-install artifact (now fixed). Live ~/.codex
remains pristine-restored (zero omr) pending user go-ahead for a clean real install.

## Addendum A7: results.json statistic key PINNED + AC10 assertion precision (live e2e run)
First full live codex+R+Quarto AC run (61 pass / 3 fail / 1 skip): all Stage 1–4
behavior CORRECT; 3 failures are spec/test alignment, zero product defects.
PIN: results.json uses a GENERIC key `statistic` (uniform across t/F/χ²/W),
plus `df`, `p_value`, and effect sizes (`cohen_d`/`mean_diff`/`r_squared`/...),
`label` (canonical ASCII test name). This is the analysis.qmd.tmpl base-R
writer's existing (correct) design. Plan §8 prose "(`t`,`df`,`p`...)" is shorthand
for `statistic`/`df`/`p_value`. AC5 test MUST assert `"statistic"` (not `"t"`).
AC10a/AC10b negative checks MUST assert on the CHOSEN canonical test label in
analysis-plan.md (headline = `Mann-Whitney U` / `Welch`, and NOT `Student`),
NOT raw `\bStudent\b` absence (the skill correctly names "Student" in the
not-chosen rationale). Positive label assertion stays so a wrong choice still fails.
Template unchanged; align tests + this pin.

## Addendum A7 CLOSED — full live e2e GREEN
After A7 alignment: offline 51 pass, MCP 79 pass, the 3 previously-failing live
tests (ac5/ac10a/ac10b) re-run with codex+R+Quarto → 3 PASSED (10m). Observed
canonical labels: AC5=Student two-sample t-test, AC10a=Mann-Whitney U, AC10b=Welch
— skill routing was correct all along; failures were test-assertion misalignment,
now fixed (statistic key pin + chosen-label check). Integrity assertions remain
strict. Net: prior 61/3F/1S → 64 pass / 1 skip, ZERO product defects. Bundle
verified end-to-end (Stages 1–4 live), install/uninstall byte-safe, user config
preserved.

## Addendum A8: omr-advisor skill ADDED (post-MVP, user-requested)
New 7th skill `skills/omr-advisor/` (지도교수 검토). Single 지도교수 persona,
on-demand (`$omr-advisor` / `/` list / implicit KO+EN triggers), ACTIVE
cross-verification: A 가설↔분석설계, B 인용↔주장(library.bib + optional
scholar.resolve_doi), C 분석↔결론(results.json vs manuscript), D 무결성
(no fabricated stats/citations; blocked not written up). Severity 치명적/주의/경미.
PLUS advisor-profile learning: ingest the real advisor via name+affiliation /
ORCID / DOI list / field keywords / workspace .bib|papers → optional
scholar.search/resolve_doi → `.omr/advisor-profile.md`; review CALIBRATED to that
advisor's field/methods. READ-ONLY over stage artifacts; writes only
`.omr/advisor-report.md`, `.omr/advisor-profile.md`, non-blocking
`state["advisor"]`(+`profile`) via A4 convention. Korean prose; ASCII machine
tokens. doctor.py needed no change (dynamic, no hardcoded skill list). Installer
auto-installs via `skills/omr-*` glob (no installer change). Pending integration:
README skills table 6→7, an offline AC for omr-advisor; live re-install to surface
the 7th skill (user go-ahead).

## A8 integration CLOSED
README updated (7-skill table + Advisor review section + MVP/A8 entry; all "seven skills" consistent). tests: +20 offline AC (TestACSAdvisorStructural) → offline 71 passed (was 51), incl. 7-skill lock + read-only/non-blocking/ASCII/4-cross-check assertions + 1 codex-guarded E2E stub (clean skip). Installer auto-installs omr-advisor via skills/omr-* glob (no installer change). examples/lecture/ (UCI ×4) added for teaching. Live ~/.codex still 6 skills — re-install surfaces the 7th (omr-advisor); user go-ahead pending.
