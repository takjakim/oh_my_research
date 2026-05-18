---
name: omr-lit
description: >-
  Literature search, find papers, organize references / citations. Use this when
  the researcher wants to do a literature search, find papers or prior work,
  build a bibliography, organize references or citations, or create an evidence
  table for their study (Stage 2). Also triggered by Korean phrases: "문헌
  검색", "문헌 조사", "논문 찾기", "선행 연구", "참고문헌 정리", "인용 정리",
  "근거 표 작성". Queries scholarly providers via the omr_scholar MCP server,
  dedups, and writes a deduped library.bib.
---

# omr-lit — 2단계: 문헌 정리

> **언어 정책:** 이 스킬은 사용자와의 모든 상호작용과 생성 산출물의
> 서술(prose)을 한국어로 작성한다. 단, 기계 처리 토큰(BibTeX 인용키,
> results.json 키, YAML frontmatter 키, 폴더/파일명, R 코드, MCP 도구명,
> state.json 키, CSL)은 ASCII/영문을 유지한다.

1단계의 연구 질문 + 변수 표를 가져와 중복이 제거된 참고문헌 목록과
근거 표를 구축한다.

## 사전 조건

1. 활성 워크스페이스가 omr 연구인지 확인한다: `.omr/state.json`이
   존재하고 `stages.stage1.status == "done"`. 그렇지 않으면 연구자에게
   먼저 **omr-start**를 실행하라고 안내하고 멈춘다.
2. `00_question/research-question.md`를 읽는다(Research Question +
   Variables 표 + 핵심 용어).

## 1단계 — 제공자별 쿼리 생성

연구 질문과 변수로부터 검색어를 도출한다(모집단 용어, 예측/IV 용어,
결과/DV 용어; 동의어 포함). 쿼리 문자열을 구성하고 연구자가
확인/편집하게 한다. 선택적으로 시드 DOI나 붙여넣은 Zotero/BibTeX
내보내기를 받는다.

쿼리 문자열, 용어 그룹, 어떤 제공자를 조회할지를 문서화하여
`10_literature/search-queries.md`에 작성한다.

## 2단계 — omr_scholar MCP 서버로 검색

MCP 도구를 **이름으로** 호출한다(설치 프로그램이
`[mcp_servers.omr_scholar]`를 등록하면 세션 전역으로 사용 가능하며,
`agents/openai.yaml`의 `dependencies.tools[]` 항목은 자문용이고 없을
수도 있다):

1. `scholar.search` — **Crossref + OpenAlex**(가능하면 Europe PMC +
   Semantic Scholar)에 걸쳐 쿼리를 실행한다. 히트별 제공자 출처가
   포함된 정규화 레코드를 수집한다.
2. `scholar.dedup` — 중복을 병합한다(DOI 정확 일치 → 정규화된
   제목+연도 퍼지 일치). 히트별 출처와 병합 보고서를 유지한다. 서버의
   중복 제거를 신뢰한다: 거의 동일한 제목이지만 DOI가 다른 별개 논문을
   과도하게 병합해서는 안 된다.
3. `scholar.to_bibtex` — 중복 제거된 집합을 안정적인 인용키와 함께
   BibTeX로 내보낸다.
4. CSL-JSON 사본이 유용하면 선택적으로 `scholar.to_csl_json`.

**날조 방지 가드:** 네트워크를 사용할 수 없거나 서버가 성능 저하/실패를
보고하면, 그 사실을 연구자에게 솔직하게 보고하고 참고문헌을 **지어내지
마라**. 검색된 것(없을 수도 있음)만 작성하고 단계를 미완료로
표시한다.

## 3단계 — 산출물 작성

- `10_literature/results.jsonl` — 줄당 하나의 정규화 레코드, 제공자
  출처를 보존한다.
- `10_literature/library.bib` — 단일 중복 제거 BibTeX 라이브러리(4단계
  인용 소스).
- `10_literature/evidence-table.csv` — `assets/evidence-table.csv.tmpl`
  기반, 열은 정확히:
  `citation_key,year,claim,finding,measure/effect,relevance,doi`.
  모든 행의 `citation_key`는 `library.bib`에 존재해야 한다. 관련 논문
  하나당 한 행을 채우되, 그 논문이 뒷받침하는 주장과 보고된
  측정/효과를 기록한다.

## 4단계 — 상태 갱신

`.omr/state.json` 갱신: `stages.stage2.status = "done"`으로 설정하고
`stages.stage2.artifact = "10_literature/library.bib"`와
`library.bib`의 체크섬(sha256)을 기록한다. 프로젝트 `AGENTS.md`의 단계
상태 표를 갱신한다.

## 5단계 — 인계

요약: 레코드 수, 중복 제거 후 수, 근거 표 행 수. 연구자가
`20_analysis/data/`에 데이터를 넣은 뒤 다음으로 **omr-analyze** 실행을
권장한다.

## 가정하는 MCP 도구

`scholar.search`, `scholar.dedup`, `scholar.to_bibtex`,
`scholar.to_csl_json`, `scholar.version`. `dependencies.tools[]`가 없는
경우도 허용한다.
