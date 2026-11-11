# 미션 01 — 연구 검토 계약 수정 결과

2026-11-11T15:22:58+09:00 (KST). 기준 GitHub `3cd3d30`.

## 변경

`companies/video/video_mission_one.py`만 제품 코드에서 수정했다. 공통 엔진·다른 모델의 전역 스키마는 변경하지 않았다.

- 게임 미션의 **research/review** 요청에만 명시적 `selection` 객체 스키마를 적용한다. `feedback`은 일반 검토 텍스트이며 accept에는 선정 객체, 그 외 행동에는 selection=null을 요구한다. 프롬프트·전송 스키마·payload 검증·역할 응답 검증을 동일 계약으로 맞췄다. 다른 역할/단계는 기존 스키마 그대로다.
- 선정 객체의 9개 필드, 정수 길이 4–180초, 실제 조사 결과 및 증거 ID, Shorts 미확인, 권리 계획을 기존 `validate_selection`으로 검증한다. 검증 완료된 객체만 기존 공통 엔진의 feedback 저장 형식으로 JSON 직렬화해 `_manager_selection`→대본 직원 인수에 재사용한다. 자연어 해석·JSON 자동 수선·실패 검토 강제 수락은 없다. 기존 저장 형식을 위한 명시적 직렬화이며 미검증 문자열을 파싱해 선정안으로 채택하지 않는다.
- 신규 승인 제안의 `mission_research_review`에 버전·스키마 해시·저장 형식·자동 수선 금지를 포함한다. 필드 없는 구 제안은 새 게임 미션 계약 승인으로 사용하지 못한다. 실제 기존 서명/원장은 변경하지 않았다.
- 실패는 `mission_research_review_json_invalid`(바깥 JSON 문법), `mission_research_review_structure_invalid`(selection 누락·문자열·필드 구조 불일치), `mission_research_selection_invalid`(null accept·길이/증거 등 의미 검증)로 구분한다. 마지막 시도의 `mission_review_diagnostics`에는 stage/category/content_bytes/content_hash만 기록한다. parse 단계와 선정 검증 단계가 분리되고 내부 원인 코드는 기존 검증 코드로 남는다. 원문·키·헤더·전체 조사 자료는 이 진단에 넣지 않는다. 과거 저장된 feedback을 읽는 경로를 소급 재검증·수정하지 않았다.

## 오프라인 검증

`tests/test_video_mission_one.py`에 **명시적 합성 fixture**를 적용했다. 실제 세 번째 응답 원문은 보관되지 않았으며 이번 fixture가 실물 응답의 문법을 재현한다고 주장하지 않는다.

실행: `PYTHONPATH=core:companies/video python -B -m unittest tests.test_video_mission_one tests.test_employee_web_research tests.test_quality_provider`

**27개 통과, 5.872초**, `git diff --check` 통과. 테스트는 임시 저장소에서 소켓/DNS를 차단하고 HTTP 전송을 모의했다.

검증한 범위:
- 구조화된 선정 accept → 대본 직원에게 동일 선정 객체 인수 → 내부 검토 → 같은 임시 컷룸의 대표 승인 대기. fixture 출처 유지, 실제 AI 산출물로 등록하지 않음.
- selection 없이 일반 feedback만 반환하거나 잘못된 내부 JSON 문자열을 반환하면 구조 단계에서 거부. 선정 객체 필드 누락, 길이 0, 조작된 evidence ID도 거부.
- 바깥 JSON 오류의 별도 원인 코드, revise의 텍스트 feedback/selection=null, 비연구 단계의 기존 전송 스키마 유지.
- 오류 시 연구 review 미저장, 모의 요청 3회에서 중단, run 재호출 거부 및 추가 전송 없음. 기존 분리 업무 9회 상한/실패 이력 보존 테스트와 키·승인 검증도 통과. 구 제안의 새 계약 필드 누락 승인 거부 확인.

## 실제 데이터와 남은 한계

실제 외부 Gemini·YouTube/API 요청 **0회**, 실제 업무 재개/재실행 **0회**, 신규 실제 업무·제안·서명 발급 **0건**이다. 두 stopped 업무와 컷룸 및 동의/lock 포함 기존 관련 파일 7개의 SHA-256이 이전 진단 시 기록과 동일함을 확인했다.

- `qualityprovider-504d90900918450f98dd62b6f7704f1b`: stopped/free_request_failed, 기존 DNS 실패 시도/active_operation 보존.
- `qualityprovider-299a51b38e6d4d50b651b9fbb39dabad`: stopped/invalid_model_json, active_operation `2c9ccf0e1edb4a088b6cb4e9afc14fca` 보존.
- 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`: research_planning 유지.
- 소모 Gemini **4/10**, YouTube search **2/4**, videos **2/4** 유지. 기존 키·미디어·백업·미추적 파일 7개 보존.

이는 합성 오프라인 계약 검증 결과다. 실제 모델의 새 스키마 수용/출력 품질이나 과거 원문 오류의 완전 해결을 입증하지 않는다. 기존 stopped 업무에 run을 다시 실행할 수 있게 바꾸지 않았고 이전 승인 잔여량을 재호출 허가로 사용하지 않았다.

**다음 한 단계:** 사용자 검토 후, 남은 예산 Gemini 최대 6회·YouTube 각각 최대 2회와 두 실패 이력을 보존하는 다음 실행 승인/연결 절차를 별도로 결정한다. 실제 호출·새 업무 생성은 별도 사용자 명시적 승인 전까지 금지한다. 이번 코드·관련 테스트·이 보고서만 GitHub에 저장하고 중단한다.
