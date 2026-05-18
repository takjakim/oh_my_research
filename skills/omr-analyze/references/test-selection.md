# 검정 선택 결정 표 (3단계 정확성 핵심)

이 파일은 **권위 있는 기준**이다. `omr-analyze`는 이를 정확히 따라야
한다. MVP 검정 집합은 의도적으로 얇고 무결성에 결정적이다: 조용한 대체
없음, 데이터를 부적절한 검정으로 강제하지 않음, 가정 점검 없는 통계량
없음.

## MVP 검정 집합 (MVP test set)

- 독립 2표본 **t-test (Student)** — 등분산
- **Welch t-test (unequal variance)** — 2표본 t-검정의 이분산 변형
- **paired t-test** (대응표본 t-검정)
- **one-way ANOVA** (일원배치 분산분석)
- **χ² test of independence** (chi-squared 독립성 검정)
- **simple OLS regression** (단순 OLS 회귀)
- **Mann–Whitney U (non-parametric fallback) / Wilcoxon signed-rank**
  — *문서화된 비모수 폴백*(무결성에 결정적: 이것이 없으면 정규성
  위반에 대한 유일하게 정직한 응답은 거부뿐이다).

## 0. 정준 ASCII 검정 라벨 (필수 — 기계 검증 토큰)

`analysis-plan.md`와 원고 Methods 가이드는 선택된 검정을 한국어 산문
안에서도 다음 **정확한 ASCII 라벨 중 하나**를 축자(verbatim)로
기록해야 한다(기계 검증이 이 토큰을 직접 grep 한다; 한국어 설명은 라벨
옆에 병기):

| 정준 ASCII 라벨 | 의미 |
|---|---|
| `Welch` | Welch's t-test (이분산 2표본) |
| `Student` | Student's t-test (등분산 독립 2표본) |
| `paired t-test` | 대응표본 t-검정 |
| `one-way ANOVA` | 일원배치 분산분석 |
| `chi-square` | χ² 독립성 검정 (`χ²` 병기 허용) |
| `OLS` | 단순 OLS 회귀 |
| `Mann-Whitney U` | 정규성 위반 비모수 폴백(독립 2집단) |
| `Wilcoxon signed-rank` | 정규성 위반 비모수 폴백(대응 2집단) |

- **분산 불균등(이분산)**으로 t-검정을 전환하면 계획서는 반드시
  `Welch`라고 적어야 하며 절대 `Student`라고 적어서는 **안 된다**.
- 등분산이 확인된 독립 2표본만 `Student`로 적는다.
- 이 라벨 토큰은 한국어 산문 안에 있어도 ASCII 그대로 유지한다.

## 1. 기본 선택 표 (가정 충족 시)

| Outcome (DV) | Predictor / design | Groups | Paired? | → Test |
|---|---|---|---|---|
| Continuous | 1 binary factor | 2 | No | Independent t-test (Student) |
| Continuous | 1 binary factor | 2 | Yes | Paired t-test |
| Continuous | 1 categorical factor | ≥3 | No | One-way ANOVA |
| Continuous | 1 continuous predictor | — | — | Simple OLS regression |
| Categorical | 1 categorical factor | any | No | χ² test of independence |

### 대응표본 설계 탐지 신호 (대응 vs 독립 선택을 명확하게)

다음 중 **하나라도** 참이면 설계를 **paired(대응)**로 처리한다:

- **(a)** 연구자가 1단계 Q&A에서 피험자 내 / 반복측정 / 사전-사후
  설계를 명시적으로 진술했고 —
  `00_question/research-question.md`(Data plan / Design)와
  `.omr/state.json`의 `paired_design: true`에 기록됨; 또는
- **(b)** 데이터셋에 **반복 피험자-ID 열**이 있음 — 두 집단/조건에서
  동일한 식별자가 나타남.

두 신호 **모두** 없으면 설계는 **independent(독립)**이다. 대응 신호가
있을 때 독립 검정을 선택하지 말고, 대응 신호가 없을 때 대응 검정을
선택하지 마라.

## 2. 가정 점검 & 필수 위반 동작

모든 점검은 **base R / `stats` 패키지만** 사용한다. `car` 없음,
`jsonlite` 없음 — 이 점검에는 비-base 패키지가 필요하거나 설치되지
않는다.

| Assumption | Check (base R) | 위반 시 → 정의된 동작 |
|---|---|---|
| **Normality** (집단별, 연속 DV) | `stats::shapiro.test` + QQ 판단, **n-aware 컷오프** 적용(아래 참조) | 비모수 동등 검정으로 전환하고 `analysis-plan.md` AND 원고 Methods에 진술: 2집단 **independent** → **Mann–Whitney U** (`wilcox.test`, unpaired); 2집단 **paired** → **Wilcoxon signed-rank** (`wilcox.test`, paired); **≥3 groups** → **STOP**, stage `blocked` (Kruskal–Wallis는 MVP 밖), 평이한 설명 |
| **Equal variance** (t-test) | base-R `stats::var.test` (F-test) 또는 `stats::bartlett.test` — **NEVER `car::leveneTest`** 를 무결성 경로에서 | **Welch's t-test** (`stats::t.test(var.equal=FALSE)`) 사용, 명시적으로 **Welch**로 보고, 절대 Student로 보고하지 않음 |
| **Expected cell counts** (χ²) | 모든 기대 빈도 ≥ 5 (`chisq.test(...)$expected`) | 기대값 < 5 가 하나라도 있으면 → **STOP**, stage `blocked`, 설명(Fisher's exact는 MVP 밖). 유효하지 않은 χ²를 보고하지 마라 |
| **Independence of observations** | 진술된 설계로부터 | 군집/반복이고 MVP 집합으로 모델링 불가하면 → **STOP**, stage `blocked`, 설명 |
| **OLS: linearity / homoscedasticity / residual normality** | 잔차 진단(residual vs fitted, QQ of residuals) | 진단 보고. **심각하게 위반**되면 → **STOP**, stage `blocked`, 통계학자 상담 권고. 오해를 부르는 모델을 조용히 보고하지 마라 |

### n-aware 정규성 컷오프 (Shapiro–Wilk 신뢰도)

- **n < ~10:** SW는 검정력이 부족함 → 비유의한 SW를 신뢰하지 **마라**.
  QQ + 편차 효과크기에 의존하고, 보수적 **STOP-on-doubt** 기본을
  적용한다(정규성이 불확실하면 비모수 경로를 선호).
- **n > ~5000:** SW가 과민함(사소한 편차도 기각) → 원 SW p-value 대신
  QQ + 편차 효과크기로 판단한다.
- **~10 ≤ n ≤ ~5000:** SW p-value를 α = 0.05 에서 사용하고 QQ로
  보강한다.
- n 구간이 SW를 신뢰 불가하게 만들 때마다 **STOP-on-doubt가 기본**이다.

## 3. 지원 검정 없음 분기 (no-fit → blocked)

(변수 척도 × 설계) 조합이 기본 표의 **어떤 행에도** 매핑되지 않으면
(예: time-to-event/생존, 다수준/군집, 다항, count 결과), `omr-analyze`는
반드시:

1. **NO statistic** — 통계량을 산출하지 않는다.
2. *왜* MVP 검정이 맞지 않는지 `analysis-plan.md`에 문서화한다.
3. `.omr/state.json`의 `stages.stage3.status = "blocked"`로 평이한
   사유와 함께 설정한다.
4. 4단계로 진행하지 않는다.

데이터를 부적절한 검정으로 결코 강제해서는 안 된다.

## 4. 결측 데이터 정책 (기본 = 공개하고 STOP)

데이터 프로파일은 열별·행별 결측을 보고한다. 기본적으로 하니스는 조용히
목록 삭제하거나 대체하지 **않는다**.

분석 변수에 결측값(missing values)이 있으면:

1. `data-dictionary.md`와 연구자에게 결측을 진술한다.
2. `.omr/state.json`의
   `stages.stage3.status = "blocked-pending-user-decision"`로 설정한다.
3. 연구자에게 명시적으로 선택하게 요청한다: 공개된 N과 함께 완전 사례
   분석, **또는** 중단.
4. 그들이 선택한 것을 `analysis-plan.md`와 Methods 섹션에 기록한다.

MVP에서는 어떤 대체(imputation) 방법도 제공하지 않는다.

## 5. 결정 흐름 (요약)

```
profile data (cols, types, n, missingness)
  └─ any analysis var has missing values?
       └─ YES → stage3 = blocked-pending-user-decision; disclose; ask; STOP
  └─ map (DV scale × predictor × groups × paired-signal) to primary table
       └─ no matching row → stage3 = blocked (no-fit); write analysis-plan.md; STOP
  └─ run assumption checks for the candidate test
       ├─ normality violated, 2-group indep  → Mann–Whitney U  (state switch)
       ├─ normality violated, 2-group paired  → Wilcoxon signed-rank (state switch)
       ├─ normality violated, ≥3 groups        → stage3 = blocked; STOP
       ├─ unequal variance (t-test)            → Welch's t-test (label Welch)
       ├─ χ² expected cell < 5                 → stage3 = blocked; STOP
       ├─ non-independence (not modellable)    → stage3 = blocked; STOP
       └─ OLS grossly violated                 → stage3 = blocked; STOP
  └─ all assumptions OK → run the primary-table test
  └─ verify results.json (freshness, intended keys, p∈[0,1], n match)
       └─ stage3 = done ONLY if verified AND no unresolved violation/non-fit
```
