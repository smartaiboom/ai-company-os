# 일반 조사 Gemini 재차 중단 — 실제 전송 계약/400 원인 진단 및 검증 (2026-11-23)

## 운영 상황
대표가 최신 컷룸에서 후속 조사를 시작했으나 "Gemini 호출 또는 응답 확인 중 중단됐습니다. transport_or_response_failed · 공급자 오류 응답 · Gemini 예약 1회/완료 0회, Tavily 0/0" 발생. 직전 원본 v5는 Gemini research-1 완료+YouTube search/videos 각 1회 후 research-2가 HTTP 400 INVALID_ARGUMENT (reports/GENERAL_RESEARCH_GEMINI_FAILURE_CONTINUATION_RESULT_20261123.md). 새로운 실행의 HTTP 코드는 UI만으로 미확인. **원인이 같은 400이라고 단정 금지**. 최신 작업 상태와 실제 어느 scope(원본/continuation), 버전, 요청 단계인지 로컬 원장 read-only 조사. 기존 approval, signed ledger, reports, video observations, backup 등 보존.

## 문제 목적
API 횟수 제한을 늘리거나 새 승인을 반복 받기 전에, 실제 Gemini 요청이 왜 거절되는지 파악하고 구조 오류를 해결한다. 대표의 정책: 정상 조사/검증 API를 최대한 충분히 사용하고 무의미한 오류 반복과 유료 전환만 차단.

## 작업
1. 최근 중단 시도의 로컬 stage/operation, HTTP status, Gemini response status, 모델 endpoint, 전송 시점, 실제 요청 바이트 수, 도구 선택 이력 및 완료된 증거, 계약 hash, 헤더/인증 여부(비밀값 비출력) 점검. 확인된 사실/추정 분리. 응답 원문이 저장되지 않았으면 원래 정보를 꾸며내지 말고 '원문 미보존'으로 남길 것. 재현을 위해 같은 실패 요청을 외부로 재전송하지 않는다.
2. Gemini SDK/REST 요청 생성부와 JSON Schema, system instruction, tool options, payload 필드, structured output의 제약, maxOutputTokens, 모델 지정, token/context 크기, 1회차와 2회차 payload 차이를 실제 파일을 통해 점검. HTTP 400 INVALID_ARGUMENT가 스키마·크기·요청 형식 등 로컬 버그로 유발될 수 있는지 증거 기반으로 원인을 좁혀라. Google 공식 API 문서와 비교하되 공개 문서 조회는 가능. 400을 단순 네트워크로 간주하거나 무한 retry하지 말 것.
3. 기존 Gemini 성공 요청을 기준으로 **실패 단계의 응답 스키마/필드/크기 차이**를 비밀정보를 제거한 구조 비교로 확인하고, 명확한 결함이 있으면 최소 수정. 결함 근거가 없으면 보존된 로그 수준에서 가능한 원인들을 우선순위로 기록하고, 다음 신규 승인 실행에서 원인을 바로 식별하도록 HTTP 400 안전 진단 필드(예: sanitized enum reason/field indicators, response size/hash)만 기록하도록 개선. 예외 본문에 token/key/원 목표/민감정보 원문 노출 금지.
4. 새 실행에서 Gemini 1회 0완료라면 기존 v5 Gemini/YouTube 관측이 continuation에 제대로 승계됐는지도 확인. 원본 실패 예약 재전송 없음, 정상 이전 완료 재호출 없음, 새로운 직원 조사 이어가기 프로세스에서 불필요하게 같은 에러 프롬프트를 재생산하는지 확인.
5. Python/Node 오프라인 검증은 저장된 실제 구조 또는 익명화한 유사 payload + 모의 HTTP 400, 200으로 테스트. 실제 Gemini/Tavily/YouTube 호출 0회. 기존 v1~v5 파일 및 승인/원장 SHA 보존. 무료/서명 한도나 자동 공개 GitHub 보고서 정책 변경 금지. API 정상 호출 기회를 임의 소량 제한하는 추가 로직 금지.
6. GitHub reports/GEMINI_REPEATED_PROVIDER_REQUEST_DIAGNOSIS_RESULT_20261123.md 에 운영 실제 증거, 코드 결함/수정 여부, 미해결 사항, 오프라인 검증/실사용 미검증, 대표가 할 다음 행동 단 하나만 작성. 관련 코드·테스트·보고서만 안전 commit/push main 및 remote SHA 검증. 기존 로컬 서버 중지하거나 리셋하지 말 것.

## 완료 기준
"또 재시도"가 아니라 오류를 구체적 원인과 수정 가능성으로 설명할 수 있고, 같은 무의미한 Gemini 요청을 남용하지 않은 상태에서 후속 실제 조사를 할 준비가 됨. 만약 원인을 확정 못하면 '미확인'으로 남기되 다음 실행에서 진단 가능하도록 보완. 개발 완료를 실제 조사 성공으로 표현 금지.
