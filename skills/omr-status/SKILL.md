---
name: omr-status
description: >-
  What's next, project status / progress. Use this when the researcher asks
  what's next, what to do next, the project status or progress, where they are
  in the research workflow, or which step/skill to run next. Also triggered by
  Korean phrases: "진행 상황", "다음 단계", "다음에 뭐 해", "프로젝트 상태",
  "어디까지 했지", "지금 뭐 하면 돼". Reads .omr/state.json and prints a stage
  checklist with the next recommended skill.
---

# omr-status — 프로젝트 상태 & 다음 단계

> **언어 정책:** 이 스킬은 사용자와의 모든 상호작용과 생성 산출물의
> 서술(prose)을 한국어로 작성한다. 단, 기계 처리 토큰(BibTeX 인용키,
> results.json 키, YAML frontmatter 키, 폴더/파일명, R 코드, MCP 도구명,
> state.json 키, CSL)은 ASCII/영문을 유지한다.

저비용 연구자에게 그들의 연구가 어디쯤 와 있고 정확히 다음에 무엇을
해야 하는지를 즉시, 평이한 말로 보여 준다.

## 단계

1. 활성 워크스페이스 루트에서 `.omr/state.json`을 찾는다.
   - 없으면: 이 워크스페이스는 omr 연구가 아니다. 연구자에게 시작을
     위해 **omr-start**를 실행하라고 안내한다(설정을 검증하지 않았다면
     **omr-doctor**도). 멈춘다.
2. `.omr/state.json`을 읽고 파싱한다. 각 단계의 `status`와 `artifact`를
   읽는다.
3. 단계당 한 줄로 체크리스트를 출력하되 명확한 기호를 사용한다:
   - `[x]` done
   - `[~]` blocked 또는 `[~]` blocked-pending-user-decision (기록된
     사유가 있으면 표시)
   - `[ ]` pending

   ```
   oh-my-research — <study_title>
   workspace: <workspace_root>

   [x] 1단계  연구 질문 & 가설        (omr-start)
   [x] 2단계  문헌 & 참고문헌         (omr-lit)
   [~] 3단계  통계 분석              (omr-analyze)  blocked-pending-user-decision: `rt`에 결측값
   [ ] 4단계  원고                  (omr-write)
   ```

4. **다음 권장 스킬**을 결정하고 진술한다:
   - 1단계 pending → **omr-start** 실행
   - 1단계 done, 2단계 pending → **omr-lit** 실행
   - 2단계 done, 3단계 pending → **omr-analyze** 실행
     (`20_analysis/data/`에 데이터를 넣으라고 상기)
   - 3단계 `blocked` / `blocked-pending-user-decision` → 진술된 문제를
     해결한 뒤 **omr-analyze** 재실행; 해결 전까지 4단계는 거부됨을
     안내
   - 3단계 done, 4단계 pending → **omr-write** 실행
   - 모두 done → 연구 완료; `30_manuscript/manuscript.docx` 검토 제안

5. 간결하게. 이 스킬은 읽기 전용이다: 어떤 파일도 수정하지 마라. MCP
   도구를 사용하지 않는다.
