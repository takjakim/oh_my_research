---
name: omr-analyze
description: >-
  Analyze my data, run a statistical test on a CSV. Use this when the researcher
  wants to analyze their data, run a statistical test, test a hypothesis on a
  CSV/dataset, profile a dataset, or choose and run the right statistical test
  for their study (Stage 3). Also triggered by Korean phrases: "데이터 분석",
  "통계 분석", "통계 검정 실행", "가설 검정", "데이터 프로파일링", "맞는 검정
  선택". Selects the correct test via a strict decision table and renders an
  executable analysis via the omr_render MCP server.
---

# omr-analyze — 3단계: 통계 분석

> **언어 정책:** 이 스킬은 사용자와의 모든 상호작용과 생성 산출물의
> 서술(prose)을 한국어로 작성한다. 단, 기계 처리 토큰(BibTeX 인용키,
> results.json 키, YAML frontmatter 키, 폴더/파일명, R 코드, MCP 도구명,
> state.json 키, CSL)은 ASCII/영문을 유지한다.

데이터셋을 프로파일링하고, 권위 있는 결정 표를 사용해 **올바른** 통계
검정을 선택하며, 실행 가능한 `analysis.qmd`를 생성하고, `omr_render`
MCP 서버를 통해 로컬에서 렌더링한 뒤 결과를 검증한다 — 부적절한 통계량
보고를 거부한다.

**`references/test-selection.md`가 권위 있는 기준이다. 읽고 정확히
따른다. 이것이 이 도구의 연구 무결성 핵심이다.**

## 사전 조건

1. `.omr/state.json`이 존재하고
   `state["stages"]["stage1"]["status"] == "done"` (A4 정준 중첩
   스키마; 평탄 `state["stage1"]` 아님). (2단계는 권장이나 분석에
   엄격히 필수는 아니다.) 그렇지 않으면 연구자에게 **omr-start**를
   실행하라고 안내하고 멈춘다.
2. 연구자가 `20_analysis/data/`에 데이터 파일을 두었다. 없으면
   CSV/xlsx를 거기에 넣어 달라고 요청하고 멈춘다.
3. 가설, 변수 표, **Design** 줄(대응표본 vs 독립)을 위해
   `00_question/research-question.md`를 읽는다. `.omr/state.json`의
   `paired_design`를 읽는다.

## 1단계 — 데이터셋 프로파일링

열, 유형, **n**, 그리고 **열별 + 행별 결측**을 파악한다. 1단계 변수
표를 사용해 열을 역할에 매핑한다(DV/결과, 예측, 집단 요인, 반복
피험자-ID).

## 2단계 — 결측 데이터 게이트 (§3.2 — 공개하고 멈춤, **렌더 전**)

**어떤 분석 변수**라도 결측값이 있으면 (5단계 렌더보다 **먼저**):

- `data-dictionary.md`와 연구자에게 결측을 진술한다.
- `.omr/state.json`에
  `state["stages"]["stage3"]["status"] = "blocked-pending-user-decision"`로
  설정한다(A4 정준 중첩 스키마; 평탄 `state["stage3"]` 아님).
- 결정을 `analysis-plan.md`에 기록한다 — 이 기록은 **렌더 전**에
  완료되므로 ac10e가 Quarto 없이 결정 가능하다. **렌더하지 않는다.
  results.json 없음.**
- 연구자에게 완전 사례 분석(공개된 N과 함께) 또는 중단을 명시적으로
  선택하게 요청한다. 조용히 목록 삭제하거나 대체하지 **마라**. 그들이
  결정할 때까지 여기서 멈춘다; 결정을 `analysis-plan.md`와 Methods에
  기록한다.

## 3단계 — 검정 선택 (§3.1 결정 표)

`references/test-selection.md`를 적용한다:

- (DV 척도 × 예측 × 집단 수 × **대응 신호**)를 기본 표에 매핑한다.
  대응 신호 = 명시적 1단계 피험자 내 진술(`paired_design: true` /
  Design 줄) **또는** 반복 피험자-ID 열. 둘 다 없으면 독립으로
  처리한다. 대응 신호 탐지 여부(어떤 신호로 무엇을 판정했는지)를
  4단계에서 `analysis-plan.md`에 **렌더 전** 기록한다.
- 조합이 **어떤 행에도 매칭되지 않으면**(no-fit) → 통계량을 산출하지
  말고 4단계에서 MVP 검정이 맞지 않는 이유를 `analysis-plan.md`에
  작성하고, `state["stages"]["stage3"]["status"] = "blocked"`로
  설정하며, 5단계 렌더로 진행하지 않는다(results.json 없음). 멈춘다.

### 정준 ASCII 검정 라벨 (필수 — 기계 검증용)

선택된 검정은 한국어 서술 안에서도 다음 **정확한 ASCII 라벨 중
하나**를 축자(verbatim)로 `analysis-plan.md`와 Methods 가이드에
기록해야 한다(한국어 설명은 라벨 옆에 병기). 정준 라벨 집합:

`Welch` (Welch's t-test) / `Student` (Student's t-test) /
`paired t-test` / `one-way ANOVA` / `chi-square` (χ² 병기 허용) /
`OLS` / `Mann-Whitney U` / `Wilcoxon signed-rank`.

- **분산 불균등(이분산)**으로 t-검정을 전환할 때 계획서는 반드시
  `Welch`라고 적어야 하며 절대 `Student`라고 적어서는 안 된다.
- 등분산이 확인된 독립 2표본은 `Student`로 적는다.
- 라벨 토큰은 한국어 산문 안에 있더라도 ASCII 그대로 유지한다(기계
  검증이 이 토큰을 직접 grep 한다).

## 4단계 — **렌더 전** 결정 기록 (analysis-plan.md + state.json 먼저)

> **순서 불변 규칙(critical ordering invariant):** 5단계
> `analysis.qmd` 생성·렌더보다 **먼저** 데이터셋 프로파일 + §3.1/§3.2
> 결정 표 적용 결과를 `20_analysis/analysis-plan.md`와
> `.omr/state.json`에 **기록(write)한 뒤** 5단계로 진행한다. 이로써
> 구조적 결정(no-fit, 결측, 대응 탐지, 초기 선택 검정)이 Quarto/R
> 없이도 결정 가능해진다(드라이런 안전).

이 단계에서 다음을 **렌더 전에** 반드시 기록한다:

1. **데이터셋 프로파일** + 변수→역할 매핑을
   `20_analysis/data-dictionary.md`에 작성한다.
2. §3.2 결측 게이트: 분석 변수에 결측이 있으면 →
   `analysis-plan.md`에 결측을 진술하고
   `state["stages"]["stage3"]["status"] = "blocked-pending-user-decision"`로
   설정한다. **렌더하지 않는다. results.json 없음.** 멈추고
   연구자 결정을 기다린다.
3. §3.1 no-fit: 어떤 행에도 매칭되지 않으면 →
   `analysis-plan.md`에 평이한 사유를 작성하고
   `state["stages"]["stage3"]["status"] = "blocked"`로 설정한다.
   **렌더하지 않는다. results.json 없음.** 멈춘다.
4. **대응표본 설계 탐지** 결과(반복 피험자-ID 열 발견 또는 명시적
   피험자 내 진술 → paired, 둘 다 없으면 independent)를 어떤 신호로
   판정했는지와 함께 `analysis-plan.md`에 기록한다.
5. **초기 선택 검정**을 §3.1 결정 표 + 위 정준 ASCII 라벨로
   `analysis-plan.md`에 기록한다. 가정 점검(정규성/등분산 등)이
   렌더된 R 진단을 필요로 하는 경우에도, **계획된(초기) 검정과 수행할
   가정 점검 목록을 렌더 전에** 먼저 기록한다(렌더 후 6단계에서
   사후-진단 최종 검정으로 갱신).

`.omr/state.json` 기록은 항상 정준 중첩 스키마(A4)를 사용한다 — 절대
평탄 키(`state["stage3"]` 또는 최상위 `"stage3"`)를 쓰지 않는다:

```python
# 표준 상태 기록 — A4 정준 중첩 스키마 (ASCII 머신 토큰)
state["workspace_root"] = "<abs path>"
state["stages"]["stage3"]["status"] = "<token>"  # pending|blocked|blocked-pending-user-decision|done
# (해당 시) state["stages"]["stage3"]["artifacts"] / ["checksums"]
```

status 값은 정확히 `pending` / `blocked` /
`blocked-pending-user-decision` / `done` 중 하나(ASCII)이다. 어떤
분기에서도 `state["stages"]["stage3"]["status"]` 경로로만 쓴다.

## 5단계 — analysis.qmd 생성

(4단계의 렌더 전 결정이 `blocked`/`blocked-pending-user-decision`이면
이 단계로 진행하지 않는다.)

`assets/analysis.qmd.tmpl`에서 `20_analysis/analysis.qmd`를
인스턴스화하고 `{{DATA_FILE}}`, `{{OUTCOME_COL}}`, `{{GROUP_COL}}`,
`{{PREDICTOR_COL}}`, `{{SUBJECT_ID_COL}}`, `{{CHOSEN_TEST}}`(4단계에
기록한 초기 선택 검정)를 채운다. 템플릿은 가정 점검을 실행하고 내장된
**base-R JSON writer(jsonlite 없음, car 없음)**를 통해
`outputs/results.json`을 산출한다.

## 6단계 — omr_render로 렌더링

`render.detect` 다음 `render.render`(세션 전역 MCP 도구;
`dependencies.tools[]` 항목은 자문용이고 없을 수 있음)를 호출하여
**로컬** R/Quarto로 `analysis.qmd`를 실행한다. 로그는
`.omr/render-log/<ts>.log`로 간다.

R/Quarto가 **없거나 버전 하한 미만**이면(R ≥ 4.2, Quarto ≥ 1.4,
pandoc ≥ 3.1): `state["stages"]["stage3"]["status"] = "blocked"`로
설정하고 버전/설치 안내를 보고하되, 여전히 드라이런 `analysis.qmd`를
생성한다(4단계의 렌더 전 결정 기록은 이미 완료되어 있어 ac10c/d/e는
Quarto 없이도 결정 가능하다). 연구자를 **omr-doctor**로 안내한다.

## 7단계 — 가정 결과 읽기 & 필수 위반 동작 적용 (사후-진단 갱신)

렌더링된 출력에서 Shapiro–Wilk p(**n-aware 컷오프**: n<~10 검정력
부족 → 의심 시 STOP 기본; n>~5000 과민 → QQ로 판단; ~10–~5000은 SW p
α=0.05 사용)와 base-R `var.test` p를 읽는다. 그런 다음:

이 단계는 4단계에 기록한 **초기 선택 검정**을 렌더된 진단으로 확정하는
**사후-진단 갱신**이다. 전환이 일어나면 `analysis-plan.md`의 최종 검정
라벨을 위 §3단계 정준 ASCII 라벨로 갱신하고 Methods에 전환과 이유를
진술한다.

- **정규성 위반, 2집단 독립** → `CHOSEN_TEST=mannwhitney`(`Mann-Whitney
  U`)로 재렌더링한다. 전환과 이유를 `analysis-plan.md`와 Methods에
  `Mann-Whitney U` 라벨로 진술한다.
- **정규성 위반, 2집단 대응** → `CHOSEN_TEST=wilcoxon`(`Wilcoxon
  signed-rank`)로. 전환을 진술한다.
- **정규성 위반, ≥3 집단** → 멈춤,
  `state["stages"]["stage3"]["status"] = "blocked"`, 평이한
  설명(Kruskal–Wallis는 MVP 범위 밖).
- **분산 불균등(t-검정, base-R var.test 경유)** →
  `CHOSEN_TEST=welch`, `analysis-plan.md`·Methods에 정준 라벨 `Welch`로
  보고(절대 `Student` 안 됨). 절대 `car::leveneTest` 사용 안 함.
- **χ² 기대 셀 < 5** → 멈춤,
  `state["stages"]["stage3"]["status"] = "blocked"`, 설명(Fisher
  정확검정 MVP 밖). 유효하지 않은 χ²를 보고하지 마라.
- **MVP로 모델링 불가한 비독립성** → 멈춤,
  `state["stages"]["stage3"]["status"] = "blocked"`, 설명.
- **OLS 심각 위반** → 진단 보고, 멈춤,
  `state["stages"]["stage3"]["status"] = "blocked"`, 통계학자 상담
  권고. 오해를 부르는 모델을 조용히 보고하지 마라.

검정 전환 후에는 재렌더링하여 `results.json`이 실제 실행된 검정을
반영하게 한다.

## 8단계 — results.json 검증

확인: 파일이 존재하고 **실행 시작보다 새로움**(freshness); 선택된
검정의 **의도된 통계량 키**를 포함(예: `statistic`, `df`, `p_value`,
t-검정의 효과크기); `p_value` ∈ [0, 1]; 보고된 `n`이 데이터셋 n과
일치. 검증 실패 시 done으로 표시하지 말고 불일치를 보고한다.

## 9단계 — 산출물 작성 & 상태 갱신

- `20_analysis/data-dictionary.md` — 변수 이름/유형/역할 + 결측.
- `20_analysis/analysis-plan.md` — 가설 → 선택된 검정(정준 ASCII
  라벨로), **모든** 가정 점검과 그 결과, 취한 폴백(과 이유), 선택된
  결측 데이터 처리. (구조적 결정은 4단계에서 렌더 전에 이미 기록되어
  있으며 여기서는 사후-진단 최종 검정으로 보강한다.)
- `20_analysis/analysis.html`,
  `20_analysis/outputs/{results.json,figures,tables}`.
- `.omr/state.json`: 렌더링 성공 **AND** 검증 일치 **AND** 미해결
  가정 위반/부적합 없음일 때 **만**
  `state["stages"]["stage3"]["status"] = "done"`로 설정한다.
  `state["stages"]["stage3"]["checksums"]`에 results.json 체크섬을,
  `state["stages"]["stage3"]["artifacts"]`에 산출물 경로를 기록한다.
  평탄 키(`state["stage3"]`)는 절대 쓰지 않는다. 프로젝트 `AGENTS.md`
  단계 표를 갱신한다.

## 10단계 — 인계

선택된 검정, 가정 결과, 핵심 결과를 요약한다. `done`이면
**omr-write**를 권장한다. `blocked`/`blocked-pending-user-decision`이면
연구자가 무엇을 결정해야 하는지, 그리고 해결될 때까지 4단계가 거부함을
명확히 설명한다.

## 가정하는 MCP 도구

`render.detect`, `render.render`, `render.version`.
`dependencies.tools[]`가 없는 경우도 허용한다.
