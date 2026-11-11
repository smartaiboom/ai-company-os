# 미션 01 — 관리자 연구 검토 결과 계약 최소 수정 및 오프라인 검증
작성일: 2026-11-11 KST

## 기존 검증 결과
`AGENTS.md`, `reports/VIDEO_MISSION_01_APPROVED_DNS_RESUME_RESULT_20261111.md`, `reports/VIDEO_MISSION_01_MANAGER_REVIEW_JSON_DIAGNOSIS_RESULT_20261111.md` 참고.
- 새 실제 업무 `qualityprovider-299a51b38e6d4d50b651b9fbb39dabad`는 `stopped/invalid_model_json`. 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`는 `research_planning`.
- Gemini 3회 HTTP 200 및 YouTube search 2회, videos 2회 HTTP 200. 기존 DNS 실패 1회 포함 Gemini 합산 4/10, YouTube 각 2/4 사용.
- 관리자 계획·연구 직원 출력은 validated; 세 번째 관리자 `review/task_research`의 바깥 역할 응답은 유효하지만 `feedback` 문자열을 내부 JSON으로 파싱하는 미션 분기(`companies/video/video_mission_one.py`의 `MissionOneCompany._call` 연구 review accept 처리)에서 `invalid_model_json` 발생.
- 실제 세 번째 응답 원문은 저장되지 않아 구체적인 잘못된 문자열은 모른다. 실물에 기반한 fixture라고 주장하지 않는다.

## 이번 작업 승인 범위
오프라인에서 필요한 **최소 코드 수정과 표적 테스트만** 수행. 사용자로부터 새로운 실제 호출 승인을 아직 받지 않았으므로 **Gemini·YouTube 등 외부 AI/API 호출은 0회**. 기존 stopped 업무의 재실행/재개, 새로운 실제 분리 업무 생성 및 제안·서명 발급도 이번 작업에서 하지 않는다.

## 작업 지시
1. 관련 코드를 읽고 관리자 검토 구조를 정확히 확인한다: `core/`의 역할 응답/검토 스키마, `companies/video/video_mission_one.py`의 `_tool_notice`, `_call`, `validate_selection`, `_manager_selection`, research→manager→writer 인수 경로. 기존 일반적인 `feedback` 텍스트 요구와 미션만의 구조화된 게임·길이 결정 JSON 요구 사이의 이중 계약을 해결한다.
2. **미션 연구 검토에 한정하여** 모델이 구조화된 선정 판단을 일관되게 출력하도록 프롬프트·역할 스키마/어댑터/검증 로직의 가장 작은 범위를 조정한다. `feedback` 텍스트를 JSON이라고 가정하는 암묵적 계약보다, 가능한 경우 기존 역할/응답 스키마에서 구조적 결과를 명시적으로 지원하는 편을 우선 검토한다. 다만 공통 엔진의 다른 업무/모델/프로젝트를 깨뜨리는 전역 스키마 변경은 피한다.
3. 검증은 절대로 완화하지 말 것: `game, selected_topic, duration_seconds, duration_reason, selection_reason, other_candidates_reason, evidence_ids, shorts_status, rights_plan` 등 필요한 내용, 실제 YouTube 증거 ID, 유효한 조사 결과·길이·권리/Shorts 불확실성을 계속 강제한다. 잘못된 문자열을 프로그램에서 임의로 고치거나 자연어를 임의 선정안으로 변환하는 자동 수선, 모호한 검토를 accept 처리하는 편법 금지. 재검토를 위해 외부 호출을 자동 재시도하는 동작도 금지.
4. 내부 JSON 파싱 실패와 필수 필드/증거 검증 실패를 별도 진단 단계/원인 코드로 안전하게 구분해 추후 원인 추적 가능하게 한다. 예외 처리에 비밀키·원문·공개 조사 전체 데이터를 저장하지 않고 오류 단계·비민감 코드·응답 크기 및 적절한 해시만 기록. 실제 raw 답변이 이번에 보관되지 않았다는 사실 유지.
5. **명시적으로 합성한 오프라인 fixture**로 (i) 정상 구조화된 관리자 accept→직원 대본 인수 및 컷룸 대표 승인 대기까지의 흐름, (ii) 일반 텍스트 feedback/불량 내부 JSON, (iii) 잘못된 선정 필드/증거 ID, (iv) 자동 수선·재시도 차단을 검증한다. 통합 fixture를 **실제 AI 산출물로 등록하지 않는다**. 관련 테스트만 돌리고 코드 변경 없으면 전체 회귀 반복하지 않는다.
6. 기존 사용자 프로젝트 JSON/서명/attempt/active_operation, 동의/비용/사용량 원장, 키·미디어·백업·미추적 파일을 수정하거나 지우지 않는다. 두 stopped 업무와 컷룸은 읽기 전용으로 유지한다. 이전 사용량 Gemini 4/10, YouTube 각 2/4 유지. 새로운 실제 호출과 재개에는 추후 **별도 사용자 명시적 승인**이 필요하다.
7. 보고서 `reports/VIDEO_MISSION_01_RESEARCH_REVIEW_CONTRACT_FIX_RESULT_20261111.md`를 **성공·실패·차단 모두** 작성하고 GitHub에 커밋·push한다. 정확한 수정 파일/오류 분기/오프라인 시험 개수·결과/데이터 보존 및 실제 외부 요청 0회/남은 위험/다음 한 단계만 간결하게 작성한다. 실물 응답이 없으므로 완전 해결을 입증했다고 과장하지 않는다.

## 금지
`git clean`, `git reset --hard`, force push, 비밀 출력, 구 요청 재발송, 원장 초기화, 코드 무관 대규모 정리, 프롬프트에 게임명·길이 정답 강제 주입, 실패 시도 삭제, 승인 없이 외부 API 호출. KST 고정. 작업 완료 후 중단.
