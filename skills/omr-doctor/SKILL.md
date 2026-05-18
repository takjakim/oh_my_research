---
name: omr-doctor
description: >-
  Check / verify my setup, is everything installed. Use this when the
  researcher wants to check or verify their setup, confirm everything is
  installed, diagnose why the tools or analysis are not working, or validate
  the environment (R, Quarto, pandoc, Python) and the MCP servers. Also
  triggered by Korean phrases: "설정 점검", "설치 확인", "환경 점검", "제대로
  설치됐는지", "도구가 안 돼요", "셋업 확인". Runs the doctor probe including
  the EV5 session-global MCP availability gate.
---

# omr-doctor — 설정 검증

> **언어 정책:** 이 스킬은 사용자와의 모든 상호작용과 생성 산출물의
> 서술(prose)을 한국어로 작성한다. 단, 기계 처리 토큰(BibTeX 인용키,
> results.json 키, YAML frontmatter 키, 폴더/파일명, R 코드, MCP 도구명,
> state.json 키, CSL)은 ASCII/영문을 유지한다.

연구자의 머신이 실제로 oh-my-research 워크플로를 실행할 수 있는지
검증하고, `config.toml`의 `[mcp_servers.*]` 등록만으로 `omr_scholar` /
`omr_render` 도구가 사용 가능함을 증명하는 **EV5 세션 전역 MCP
게이트**를 실행한다.

## 1단계 — 환경 프로브 실행

`scripts/doctor.py`를 실행한다(순수 표준 라이브러리 Python 3.10+):

```
python3 scripts/doctor.py              # EV5 codex 게이트 포함 전체 프로브
python3 scripts/doctor.py --skip-mcp   # 빠름: 환경/버전 프로브만
```

EV5 `codex exec` 호출은 비대화형(stdin 닫힘)이며 시간 제한이
있어(`OMR_DOCTOR_CODEX_TIMEOUT` 초, 기본 90) 멈추는 대신
FAIL/SKIPPED로 우아하게 저하된다.

**R, Quarto, pandoc, Python**에 대해 보고한다: 존재 여부, 버전, 절대
경로; **버전 하한 HARD FAIL**(R ≥ 4.2, Quarto ≥ 1.4, pandoc ≥ 3.1)을
적용; MCP 권한 모델(host vs sandbox-confined,
`render.classify_privilege` 의미)을 분류; 그리고 어떤 omr 스킬도
호출하지 않고 `omr_scholar`와 `omr_render`의 `version` 도구를 호출하여
둘 다 앱 내장 `/mcp`에 나타나는지 확인하는 **EV5** 베어 `codex exec`
게이트를 실행한다. `codex` CLI가 없으면 EV5/권한 점검은 **SKIPPED**로
보고된다(충돌이 아님).

## 2단계 — 해석 & 보고

스크립트의 PASS / FAIL / SKIPPED 표를 연구자에게 평이한 말로 전달한다:

- **버전 하한 HARD FAIL** → 무엇을 설치/업그레이드해야 하는지, 그리고
  수정될 때까지 3단계(`omr-analyze`)가 `blocked`임을 안내한다.
- **EV5 FAIL** → MCP 서버가 세션 전역이 아니다; 설정이 **OK 아님**.
  설치 프로그램 재실행을 안내한다.
- **EV5 SKIPPED** (PATH에 `codex` CLI 없음) → 자동으로 검증할 수
  없었음과 `/mcp`를 수동으로 확인하는 방법을 안내한다.
- 전체 PASS → 환경이 준비되었음을 확인하고 **omr-start**를 권장한다.

## 3단계 — (정성적으로) 함께 확인

- 여섯 개 `omr-*` 스킬이 앱의 `/` 목록과 `codex://skills`에 나타난다.
- 두 MCP 서버가 모두 내장 `/mcp`에 나타난다.

이 스킬은 `scripts/doctor.py`를 통해 간접적으로
`render.classify_privilege`, `scholar.version`, `render.version`을
호출한다. `dependencies.tools[]`가 없는 경우도 허용한다 — 자문용이다.
