---
name: omr-write
description: >-
  Write up / draft the manuscript / paper / results section. Use this when the
  researcher wants to write up their study, draft the manuscript or paper,
  produce a results section, assemble an IMRaD article, or render a DOCX of
  their findings (Stage 4). Also triggered by Korean phrases: "원고 작성",
  "논문 작성", "논문 초안", "결과 섹션 작성", "IMRaD 작성", "DOCX 만들기".
  Assembles an IMRaD manuscript from the prior stages' artifacts and renders it
  to DOCX via the omr_render MCP server.
---

# omr-write — 4단계: 원고 작성

> **언어 정책:** 이 스킬은 사용자와의 모든 상호작용과 생성 산출물의
> 서술(prose)을 한국어로 작성한다. 단, 기계 처리 토큰(BibTeX 인용키,
> results.json 키, YAML frontmatter 키, 폴더/파일명, R 코드, MCP 도구명,
> state.json 키, CSL)은 ASCII/영문을 유지한다.

2단계(근거 표 + library.bib)와 3단계(analysis-plan + results.json +
figures/tables)로부터 IMRaD 원고를 조립한 뒤 Quarto를 통해 **DOCX**로
렌더링한다. 모든 사실 주장은 인용되어야 하고, 모든 인용키는 해소되어야
한다.

## 사전 조건 (충족되지 않으면 일찍 거부)

1. `.omr/state.json`이 존재한다. 읽는다.
2. **3단계 게이트:** `stages.stage3.status`가 `"blocked"` 또는
   `"blocked-pending-user-decision"`이면 진행을 **거부**한다. 연구자가
   먼저 **omr-analyze**에서 무엇을 해결해야 하는지 설명한다. 멈춘다.
3. `10_literature/library.bib`가 반드시 존재해야 한다. 없으면 **크게
   실패**한다 — 인용을 날조하거나 참고문헌을 지어내지 마라. 연구자에게
   **omr-lit**를 다시 실행하라고 안내한다. 멈춘다.
4. `20_analysis/outputs/results.json`과
   `20_analysis/analysis-plan.md`가 존재해야 한다(3단계 done). 없으면
   연구자에게 **omr-analyze**를 완료하라고 안내한다.

## 1단계 — 입력 수집

- `10_literature/evidence-table.csv` — 주장 + 해당 `citation_key`.
- `10_literature/library.bib` — 인용키 전체 집합.
- `20_analysis/analysis-plan.md` — 선택된 검정, 가정 결과, 폴백 /
  결측 데이터 처리.
- `20_analysis/outputs/results.json` — 검증된 수치 결과.
- `20_analysis/outputs/figures/`, `tables/` — 삽입 가능한 자산.

## 2단계 — manuscript.qmd 조립

`assets/manuscript.qmd.tmpl`에서 `30_manuscript/manuscript.qmd`를
인스턴스화한다. `assets/apa.csl`을 `30_manuscript/apa.csl`로 복사하고
참조한다.

- **Introduction:** `evidence-table.csv`의 주장에서 종합한다. **모든
  사실 주장은 in-text 인용 `[@citation_key]`을 지녀야 하며** 그 키는
  `library.bib`에 존재해야 한다. 인용 없는 사실 주장은 금지.
- **Methods:** `analysis-plan.md`로부터 — 선택된 검정, 가정 점검과
  그 결과, 그리고 3단계에서 취한 비모수 폴백(Mann–Whitney / Wilcoxon
  / Welch) 또는 결측 데이터 처리를 명시적으로.
- **Results:** 숫자를 **`results.json`에서 그대로** 보고한다(예:
  `t`, `df`, `p_value`, 효과크기). `outputs/`의 figures/tables를
  삽입한다.
- **Discussion:** 연구자가 완성할 스캐폴딩 프롬프트(해석, 한계, 향후
  연구).

## 3단계 — omr_render로 DOCX 렌더링

`render.render`(세션 전역 MCP 도구; `dependencies.tools[]` 항목은
자문용이고 없을 수 있음)를 호출하여 `manuscript.qmd` →
`manuscript.docx`를 `library.bib` + `apa.csl`과 함께 렌더링한다.
(PDF/TinyTeX는 post-MVP; DOCX는 LaTeX가 필요 없음.) 로그 →
`.omr/render-log/<ts>.log`.

## 4단계 — 인용 검증

렌더링된 원고의 모든 in-text 인용키를 파싱하고 각각이 `library.bib`의
항목으로 해소되는지 확인한다. **어떤** 키라도 해소되지 않으면 4단계를
done으로 표시하지 말고 — 미해소 키를 보고하고 주장을 고치거나 제거한다.
미해소 인용키 0개가 필수이다.

## 5단계 — 상태 갱신 & 인계

`.omr/state.json`의 `stages.stage4.status = "done"`로 설정하고
`manuscript.docx` 체크섬을 기록하며 프로젝트 `AGENTS.md`를 갱신한다.
연구자에게 DOCX 위치와 산문(특히 Discussion 스캐폴드)을 검토/편집해야
함을 알린다. 전체 체크리스트를 위해 **omr-status**를 권장한다.

## 가정하는 MCP 도구

`render.render`, `render.version` (omr_render); 인용 해소는
`library.bib`를 직접 읽는다. `dependencies.tools[]`가 없는 경우도
허용한다.
