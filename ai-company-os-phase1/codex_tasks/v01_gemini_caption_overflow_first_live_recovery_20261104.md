# Gemini 첫 실사용 중단 `caption_overflow` 원인 확인 및 안전한 회복 준비

기준 2026-11-04 KST. 사용자 실제 실행 결과:
```json
{"id":"geminicompany-db22e41adcc4446d9904e44c363df5fc","status":"stopped","reason_code":"caption_overflow","phase":"work","artifacts":{}}
```
**최초 실사용 Gemini 요청은 사용자 명시 동의 후 실행됐다. 이번 작업 지시서는 오프라인 분석/최소 코드수정만 허용하며 추가 외부 API 호출·기존 프로젝트 재실행은 허용하지 않는다.**

## 제품 우선순위
목표 한번 입력→실제 Gemini 관리자가 계획/평가기준/업무 분담→직원 실작업/인계→관리자 검토 및 수정→실제 결과물 MP4 최종 보고. 사용자는 수차례 API 연결/오프라인 진단에 막혀 제품 완료가 지연된 상태다. 결과 및 실행 흐름을 분석해 **실제 AI 협업이 어디까지 진행됐고 무엇 하나만 고치면 다음 새 실사용 프로젝트를 준비할 수 있는지** 확인하라. 새 UI/대규모 테스트보다 최종 결과물 실제 완주에 집중.

## 먼저 읽을 파일
`AI_COMPANY_OS_CORE_PRINCIPLES.md`, `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`, `reports/v01_gemini_autonomous_company_integration_ready_20261104.md`, `local_artifacts.py`, `autonomous_live.py`, `autonomous_free.py`, `autonomous_gemini.py`, `gemini_first_project.py`, 관련 tests.

## 1. 현재 실패 상태 **읽기 전용** 사실확인
- 기존 로컬 프로젝트 위치 `data/gemini-first-autonomous-20261104`, ID `geminicompany-db22e41adcc4446d9904e44c363df5fc`.
- 프로젝트 상태·이벤트·시도 원장을 **읽기 전용으로** 확인. API 호출 횟수, manager/employee 종류 및 단계, validated vs failed, 마지막 작업/정지 위치, 실제 사용자 목표로 생성된 plan/assignment/직원 결과/검토/최종 파일 유무를 요약. 저장 상태에 `storage_hash` 등 무결성 검증이 있으면 기존 store 로더로 검증. 비밀키, raw request/response 또는 수집된 불필요한 데이터 출력 금지. 실제 호출 횟수 모르겠으면 모른다고 기록. Gemini 실제 사용을 오프라인 fake test와 구분.
- `caption_overflow`가 발생한 정확한 실행 위치·규칙·입력 크기 확인. 현재 `local_artifacts.validate_video`에는 scene마다 최대 120자 이외에 **줄당 28자 이하, 최대 4줄** 조건이 있고 위반 시 `caption_overflow`. raw caption 전문이나 회사 자료 노출 없이 초과한 줄 길이/줄수/scene index만 제한하여 로컬 분석할 것. 단계의 어느 직원 작업인지 확인.
- 기존 프로젝트 상태가 stopped이며 예약/작업 이력을 보존해야 하므로 **동일 command 재실행, 기존 status 변조/새 attempt 추가/실패 원장 초기화, 소진 시작 마커 삭제, 승인의 재사용 절대 금지**.

## 2. 실제 실패 재발을 막는 최소 수정
- 입력 계약을 모델에게 명확히 알리는 최소 해결 우선: `caption_video_v1` tool schema/시스템 prompt에 줄당 28자/최대 4줄/씬당 총120자, 씬 개수와 duration 등 실제 `validate_video` 조건을 충분히 제공. 현재 `TOOLS` 설명은 글자 수/영상길이만 제시하고 줄 수·줄 길이는 누락돼 있는 것이 GitHub 코드에서 확인됨. 이 불일치를 바로잡아라.
- 자막이 단어/의미 단위로 끊겨야 할 한국어 문장이라면 **기계적으로 중간 글자를 삭제하거나 임의 변형하여 'AI가 그렇게 작성했다'고 주장하지 말 것**. 안전하게 의미를 유지하는 결정적 줄바꿈(공백/문장 경계)만 가능하고, 자동 변환 시 원문과 변환 후 결과가 추적 가능해야 함. 잘림/넘침 시 내부 품질 검토 대상이며 사용자의 중간 업무 승인 요구하지 않음.
- 다른 길이·음성 길이 `narration_exceeds_scene`·FFmpeg 실패 가능성도 코드에서 확인하되 이번 범위는 자막 넘침 차단에 필요한 변경으로 최소화. 기존 소리/영상 시각 품질 미달은 사실대로 보고. 영상 20~30초 목표를 코드에 하드코딩 금지.
- 가능하다면 1회 local-tool 입력 오류에 대해 **Gemini manager에게 피드백 후 직원에게 수정 지시**하는 정상 업무 흐름을 구현하되, 큰 상태 전이/안전 원장 변경이 필요하다면 이번 범위에서는 무리하지 않고 후속 설계로 명시. 일단 안전한 deterministic reflow + 분명한 모델 계약으로 성공률을 높이는 것을 우선. 원장은 합법적인 신규 프로젝트 실행에서만 생성됨.
- 새 외부 호출 없음. 기존 Gemini 503/과거 실패 코드/other provider와 데이터 불변.

## 3. 오프라인 집중 테스트
- 긴 한국어 문장/단어 경계/4줄 초과/28자 경계/개행/scene 120자/다수 scene 테스트, 검사 실패 시 정확한 범주. local video renderer와 AI tool contract 일치 여부.
- 실제 사용 없이 fake Gemini workflow manager→employee→tool→review→final report 최소 회귀. 기존 로컬 오디오/MP4 테스트 가능한 경우 실행하되 fixture 결과를 실제 Gemini 성공이라 주장 금지.
- 필요 범위만 빠르게 실행. `git diff --check`, 관련 tests 통과 확인.

## 4. 후속 첫 완주 실사용 준비
- **현재 프로젝트는 stopped이므로 새 독립 프로젝트로만 다음 실전 테스트를 준비**. 사용자의 기존 시험 목적/전송 범위와 같아도 기존 동의 자동 적용 금지. 재사용 가능한 초안/템플릿 제안은 가능하나 Codex가 사용자의 새로운 서명 동의를 꾸며내면 안 됨.
- 다음 실행에서 테스트용 목표/허용 모델 `gemini-3.1-flash-lite` / 실제 Free Tier / 외부 송신 범위 / 무상 운영 조건 / 파일 출력·중복 원장 보호 확인. 준비/오프라인 검증까지 허용. 실제 다회 Gemini POST는 이번 작업 지시서에서 **0회**.
- `reports/v01_gemini_caption_overflow_first_live_recovery_20261104.md`에 한국어/KST로 **실제 성공한 API 호출 수와 manager/employee 단계, 생성된 plan/results/검토 여부, 실패 원인의 구체적 규칙, 수정 내용, fake tests, 기존 프로젝트 보존, 다음 실제 완주 1회 실행을 위해 필요한 정확한 한 가지 조치**를 적는다.
- 비밀 없는 코드/테스트/보고서만 선택적 commit/push; reset/clean/force push 금지. 기존 프로젝트/원장/동의/동영상/backup 상태 불변 hash 검증. 미해결 테스트 실패·갈등이면 중단해 알리기.

**완료 목표:** 더 이상 실제 API가 안 붙는다고 막연히 추측하지 않는다. 첫 실사용의 어느 단계까지 실제 Gemini가 수행했는지 사실로 확인하고, 정확히 `caption_overflow`를 해결해 사용자의 최종 MP4 완주 테스트를 위한 안전한 새 실행 경로를 준비한다.
