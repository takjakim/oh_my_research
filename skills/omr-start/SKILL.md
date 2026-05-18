---
name: omr-start
description: >-
  Start a research project, set a research question / hypothesis. Use this when
  the researcher wants to start a research project, define or set a research
  question, state a hypothesis, frame a study, or begin a new paper/study from a
  plain-language idea. Also triggered by Korean phrases: "연구 시작", "연구
  프로젝트 시작", "연구 가설", "연구 질문 설정", "가설 세우기", "연구 시작하고
  싶어". Performs the workspace-gate onboarding, runs a guided Q&A, and scaffolds
  the study project (Stage 1).
---

# omr-start — 1단계: 가설 및 연구 질문

> **언어 정책:** 이 스킬은 사용자와의 모든 상호작용과 생성 산출물의
> 서술(prose)을 한국어로 작성한다. 단, 기계 처리 토큰(BibTeX 인용키,
> results.json 키, YAML frontmatter 키, 폴더/파일명, R 코드, MCP 도구명,
> state.json 키, CSL)은 ASCII/영문을 유지한다.

연구자의 평범한 말로 표현된 아이디어를 반증 가능한 연구 질문, 명시적
H0/H1, 유형이 지정된 변수 표, 그리고 스캐폴딩된 연구 프로젝트로
전환한다. 이것은 네 단계 oh-my-research 워크플로의 진입점이다
(`omr-start` → `omr-lit` → `omr-analyze` → `omr-write`, 보조 스킬로
`omr-status`와 `omr-doctor`).

## 0단계 — 워크스페이스 게이트 (항상 가장 먼저 수행)

**불변 규칙: 연구 폴더 자체가 이 스레드의 활성 워크스페이스 루트이다.**
스킬은 스레드 도중에 워크스페이스를 프로그램적으로 생성하고 전환할 수
없다. 따라서 다른 무엇보다 먼저 활성 워크스페이스 루트(이 스레드의 현재
작업 디렉터리)를 점검한다:

1. 활성 워크스페이스 루트의 절대 경로를 확인한다.
2. 다음과 같이 분류한다:
   - **(A) 없음/존재하지 않음, 또는 이미 *다른* 프로젝트** (관련 없는
     소스 코드, 다른 프로젝트의 `.git`, 앱 파일 등을 포함하고 omr
     연구가 *아님*): **여기에 스캐폴딩하지 말고 워크스페이스를 전환하려
     하지 마라.** 대신 연구자에게 평범한 말로 안내한다:
     - 이 연구를 위한 새 빈 폴더를 만든다 (예: `~/research/<topic>/`).
     - 그것을 Codex 워크스페이스로 연다: macOS **Cmd+O**로 폴더 선택,
       또는 이 딥링크 클릭(권장하는 절대 경로로 치환):
       `codex://new?path=/ABSOLUTE/PATH/TO/STUDY-FOLDER`
     - 그런 다음 그 새 스레드/워크스페이스에서 **omr-start**를 다시
       실행한다.
     - 아직 툴체인을 검증하지 않았다면 먼저 **omr-doctor**를 안내한다.
     그 후 멈춘다. 어디에도 파일을 만들지 마라.
   - **(B) 비어 있음 (또는 이미 omr 연구 — `.omr/state.json` 보유)**:
     1단계로 진행한다. 형제 디렉터리가 아니라 이 이미 활성화된 루트에
     스캐폴딩한다.

"omr 연구"는 `.omr/state.json`의 존재로 식별된다. "비어 있는"
워크스페이스는 파일이 없거나 숨김/OS 잔여물(`.DS_Store`, 커밋 없는
`.git` 초기화)만 있는 경우다. 판단을 사용하되 불확실하면 스캐폴딩 전에
연구자에게 확인을 요청한다.

## 1단계 — 안내형 Q&A

연구자에게 짧고 평범한 말의 안내형 Q&A를 한다(한 메시지, 번호 매김;
부분 답변을 받아들이고 나머지는 추론하되 추론한 부분은 표시한다):

1. **모집단 / 참여자** — 누구 또는 무엇을 연구하는가?
2. **비교 / 예측 변수** — 어떤 집단, 조건, 또는 예측 변수인가?
3. **결과** — 무엇을 측정하는가(종속 변수)?
4. **예상 방향** — 무엇이 일어날 것으로 기대하며, 그 이유는?
5. **설계** — **피험자 내 / 반복측정 / 사전-사후**(대응표본)인가,
   아니면 **피험자 간 / 독립 집단**인가? (답변을 그대로 기록한다 — 이는
   3단계를 위한 §3.1 대응표본 설계 탐지 신호이다.)
6. **데이터** — 어떤 데이터를 가지고 있거나 얻을 수 있는가(파일 형식,
   대략적 N, 열)?

## 2단계 — 질문 구조화

답변으로부터 다음을 도출한다:

- 단일 **반증 가능한 연구 질문** (PICO/FRAP 프레이밍 —
  `references/picot-frap.md` 참조).
- **H0**(영가설)과 **H1**(대립가설, 방향을 진술했다면 방향성 포함),
  각각 정밀하고 검정 가능한 진술.
- **변수 표**: 각 변수의 역할(IV / DV / 공변량), 데이터 유형,
  **측정 척도**(명목 / 순서 / 등간 / 비율).
- **데이터 계획**과, 진술된 데이터가 실제로 질문에 답할 수 있는지
  여부의 명시적 **표시**(표본 크기, 누락 변수, 설계 적합성).
- **범위 외** 목록.

## 3단계 — 프로젝트 스캐폴딩 (활성 루트에만)

다음 트리를 **활성 워크스페이스 루트**에 생성한다
(`assets/research-question.md.tmpl` 사용):

```
00_question/research-question.md
10_literature/        (비어 있음, omr-lit 준비)
20_analysis/data/     (연구자가 CSV/xlsx를 여기에 둠)
30_manuscript/
.agents/skills/        (비어 있음; 예약)
AGENTS.md             (프로젝트 컨텍스트: 질문, 변수, 단계 상태 표)
_quarto.yml
.omr/state.json
.omr/render-log/      (비어 있음)
```

`research-question.md` 섹션(정확한 순서): **Background**, **Research
Question**, **Hypotheses (H0/H1)**, **Variables**(측정 척도가 있는 표),
**Data plan**, **Out-of-scope**. 설계 답변(대응표본 vs 독립)을 Data
plan 또는 "Design" 노트 안에 명시적으로 기록하여 3단계가 대응표본 탐지
신호로 읽을 수 있게 한다.

프로젝트 `AGENTS.md`를 생성한다: 연구 질문, 변수 표, 단계 상태
표(1단계 done; 2~4단계 pending)를 포함한다. 수 KiB 이내로 유지한다.

`_quarto.yml` 생성:

```yaml
project:
  title: "<short study title>"
```

`.omr/state.json` 작성 — **A4 정준 중첩 스키마**를 emit 한다.
규칙: 상태는 항상 `state["stages"]["stageN"]["status"]` 경로로
쓴다(평탄 `state["stageN"]` 절대 금지). `status` 값은 정확히
`done` / `blocked` / `blocked-pending-user-decision` / `pending`
중 하나(ASCII 머신 토큰). `workspace_root`는 활성 루트의 절대
경로. 후속 단계가 채울 수 있도록 stage1은 `artifacts`/`checksums`
키도 함께 emit 한다(stage2~4는 status만 `pending`).

```json
{
  "schema": 1,
  "workspace_root": "/ABSOLUTE/PATH/TO/ACTIVE/ROOT",
  "study_title": "<title>",
  "stages": {
    "stage1": {"status": "done", "artifacts": {"research_question": "00_question/research-question.md"}, "checksums": {}},
    "stage2": {"status": "pending"},
    "stage3": {"status": "pending"},
    "stage4": {"status": "pending"}
  },
  "paired_design": false
}
```

연구자가 피험자 내 / 반복측정 / 사전-사후 설계를 진술한 경우에만
`paired_design`을 `true`로 설정한다.

## 4단계 — 인계

연구자에게 1단계가 완료되었음을 알리고, 질문 + H0/H1을 요약한 뒤,
문헌 수집을 위해 다음으로 **omr-lit** 실행을 권장한다.

## 참고

- 이 스킬은 MCP 도구를 사용하지 않는다.
- 연구자의 의도를 결코 날조하지 마라 — 답변이 누락되었고 안전하게
  추론할 수 없으면 질문한다.
