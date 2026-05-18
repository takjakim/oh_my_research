# Analysis Fixture Oracle

This file is the correctness oracle for AC10 analysis fixture datasets.
It records the **required** statistical selection and outcome for each file,
with statistical rationale. Tests MUST assert against these outcomes.

---

## ac5_clean.csv

**Design:** Independent two-sample, 2 groups (`placebo` / `caffeine`),
continuous outcome (`reaction_time_ms`), N=30 per group.

**Required selection:** Independent two-sample **Student t-test**
(`stats::t.test(var.equal=TRUE)` in base R).

**Statistical rationale:**
- Both groups are drawn from normal distributions (μ=250, σ=20 for placebo;
  μ=280, σ=20 for caffeine) — `stats::shapiro.test` should return p > 0.05
  for each group at N=30.
- Equal variance: both groups have the same σ=20, so `stats::var.test`
  should return p > 0.05 (F-ratio ≈ 1.0).
- No pairing signal: no repeated subject_id, no within-subject design stated.
- Outcome: `results.json` must contain keys `{t, df, p_value, effect_size}`;
  `analysis-plan.md` must record both assumption checks as PASSED and
  test labeled **Student** (NOT Welch, NOT Mann-Whitney).
- No package installation required (base-R path only).

---

## ac10a_nonnormal.csv

**Design:** Independent two-sample, 2 groups (`control` / `treatment`),
continuous outcome (`score`), N=15 per group.

**Required selection:** **Mann-Whitney U test**
(`stats::wilcox.test(paired=FALSE)` in base R).

**Statistical rationale:**
- The `control` group scores cluster tightly near 1.0–2.4 (narrow range).
- The `treatment` group spans 40–145 with extreme right skew.
- This distribution pattern produces a clear Shapiro-Wilk violation
  (p < 0.05) for at least one group, indicating non-normality.
- Since normality assumption is violated, the Student t-test is
  inappropriate. The mandatory non-parametric fallback is Mann-Whitney U.
- `analysis-plan.md` and Methods MUST explicitly state the switch and reason.
- `results.json` / `analysis-plan.md` MUST NOT present Student or Welch t
  as the headline result.

---

## ac10b_unequalvar.csv

**Design:** Independent two-sample, 2 groups (`control` / `treatment`),
continuous outcome (`score`), N=15 per group.

**Required selection:** **Welch's t-test**
(`stats::t.test(var.equal=FALSE)` in base R).

**Statistical rationale:**
- The `control` group has very low variance (range ≈ 97.9–102.1, σ ≈ 1.3).
- The `treatment` group has very high variance (range ≈ 40–200, σ ≈ 57).
- Both groups are approximately normal (no extreme skew).
- `stats::var.test` will detect severely unequal variances (F-ratio >> 1,
  p << 0.05), so the Student t-test (equal-variance assumption) is violated.
- The mandatory action per §3.1 is Welch's t-test.
- `analysis-plan.md` / Methods MUST label the result **Welch** (NOT Student).
- No `car` package required; `stats::var.test` is base R.

---

## ac10c_paired.csv

**Design:** Repeated-measures / paired, subjects measured at `pre` and `post`
conditions. Subject IDs (P001–P015) appear in BOTH conditions.

**Required selection:** **Paired t-test**
(`stats::t.test(paired=TRUE)` in base R).

**Paired-design detection signal (per §3.1):**
- The `subject_id` column (P001–P015) repeats across both `condition` levels
  — this is the repeated subject-ID signal that mandates paired analysis.

**Statistical rationale:**
- The pre-post differences are small and normally distributed.
- Treating this as independent samples would be incorrect (pseudoreplication).
- The harness MUST detect the repeated subject_id and route to paired t-test.
- `analysis-plan.md` MUST record the paired-design detection and assert
  the test is **paired** (NOT independent t, NOT Mann-Whitney).

---

## ac10d_nofit.csv

**Design:** Time-to-event outcome (`days_to_event`) with censoring indicator
(`event_occurred`). Two groups (`control` / `treatment`).

**Required selection:** **BLOCKED — no MVP test fits.**

**Statistical rationale:**
- The outcome is time-to-event (survival analysis), which requires
  Kaplan-Meier / log-rank / Cox proportional hazards — none of which
  are in the MVP test set.
- Applying a t-test or Mann-Whitney U to right-censored survival times
  would be statistically invalid (censored observations would be
  treated as actual event times).
- The harness MUST:
  - Produce NO statistic in `results.json`.
  - Set `.omr/state.json` stage3=`blocked` with a plain-language reason
    explaining why no MVP test fits.
  - NOT advance to Stage 4.
  - Explain to the researcher that survival analysis is required.

---

## ac10e_missing.csv

**Design:** Independent two-sample, 2 groups (`placebo` / `caffeine`),
continuous outcome (`reaction_time_ms`), but with **4 missing values**
in the outcome column (subjects S003, S008, S014, S019).

**Required selection:** **BLOCKED-PENDING-USER-DECISION.**

**Statistical rationale (per §3.2 missing-data policy):**
- The default behavior is to STOP and disclose — no silent listwise deletion
  or imputation.
- The harness MUST:
  - Report the 4 missing values in `data-dictionary.md`.
  - Set `.omr/state.json` stage3=`blocked-pending-user-decision`.
  - Present the missingness to the researcher and ask for a decision
    (complete-case vs. stop).
  - NOT silently drop rows and report results.
  - NOT impute values.
- Note: 4/20 = 20% missingness, which is not trivially ignorable and
  warrants explicit disclosure regardless.
