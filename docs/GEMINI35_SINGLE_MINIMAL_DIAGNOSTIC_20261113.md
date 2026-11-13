# Gemini 3.5 Flash-Lite — 승인된 합성 텍스트 최소 진단 1회 (2026-11-13 KST)

## 사용자 명시 승인
사용자가 **Gemini 3.5 Flash-Lite에 무해한 합성 문장만 전송하는 최소 연결 진단 API 호출 최대 1회** 승인했다. 실패도 1회로 계산; 자동 재시도, 유료 전환, 모델 변경, 실제 목표·대표 피드백 전송 금지. 요청: **먼저 진단 코드와 무료 조건을 확인하고 승인 범위 안에서 실행을 준비**. 이번 Codex 단계는 코드/무료 조건 점검과 *안전하게 실행 준비*부터 하고, 모든 조건 확인되면 위 1회 승인 범위에서만 실제 호출하도록 설계한다. 단, 무료 계정 여부가 독립적으로 확인되지 않으면 **호출하지 않고 준비 단계에서 중단**한다. 사용자가 추가 승인을 요구한 것이 아니므로 오프라인 준비만 완료해도 무방하다. 실제 호출했는지 여부를 분명히 보고한다.

## 공식 문서 확인 (2026-11-13)
https://ai.google.dev/gemini-api/docs/pricing
모델 `gemini-3.5-flash-lite`, Standard Free Tier의 입력/출력 무료, Standard Paid Tier는 과금될 수 있음. 모델 문서: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite . 가격표는 무료 tier 제공을 뜻할 뿐 현재 Google Cloud 프로젝트의 **실제 청구/계정 유형 무료 보증이 아님**. 프로젝트/키의 무료 등급 및 미청구 조건을 신뢰할 수 있게 확인하지 못하면 호출 금지. 무리하게 계정의 비공개 상태를 출력/추측하지 말 것. 필요하면 화면에서 사용자 직접 확인이 필요한 구체 항목 하나만 보고.

## 지난 실패
- 11/12 16:41:21~23 KST: 36,671 bytes, HTTP503, request_hash bc787bb74af99b6a97cce47f3c5d4bd20a66c94c41d7136d423ba2a89439512a
- 11/13 09:17:59~09:18:01 KST: 36,671 bytes, HTTP503, request_hash a4a6c6db05749ba2a81f6232d3bba7168b70a13d4a6cc4745c8f177479c2b749
- 현재 컷룸/업무/동의 원장 그대로 보존. 오늘의 최소 진단은 **별개 세션 및 별도 명시된 한도 1**로만.

## 절차
1. AGENTS.md 확인, 현재 main, 기존 시도 원장 읽기 전용. 같은 진단을 과거/현재에 이미 전송했는지 먼저 조사하고 중복 전송 차단. 프로젝트의 `GEMINI_API_KEY`가 존재하는지만 확인하고 값 출력 금지; endpoint/model 계정 binding 점검. 다른 자격증명이나 계정/프로젝트로 바꾸지 않음.
2. 진단 스크립트는 기존 `send_once` 같은 retry 없음/redirect 없음/환경 프록시 없음 정책 재사용. 입력은 위의 합성 문장 하나 `Reply with OK only.`; payload:
   `{"contents":[{"parts":[{"text":"Reply with OK only."}]}],"generationConfig":{"maxOutputTokens":16}}`
   고정 POST `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`, 헤더 `x-goog-api-key`. temperature/JSON schema/systemInstruction/실제 업무 맥락/튜닝/검색·도구/캐시/대용량 payload 없음. 실제 호출 시 **HTTP 상태와 가능하면 짧은 오류 reason 및 request ID(개인 정보 검토 후)**만 저장. Response 본문 전문/키/사용자 목표·피드백 유출 금지. 503 등의 반환 body는 민감성 검토 후 오류 타입 정도만 기록. 요청 횟수는 프로세스 내 자동 재시도/HTTP 3xx follow/백오프 불허. DNS/timeout 실패 포함 1회 차감.
3. 계정의 실제 무료 등급 확인을 반드시 선행한다. 단순 `GEMINI35_AUTONOMOUS_FREE_ENABLED=1`, 코드 상 동의 서명, GitHub 가격표/모델 무료 안내만으로 **현재 계정 무료 등급이라고 확정하지 않는다**. 검증 불가능하면 이번에는 **HTTP0회로 준비 종료**하고 대표에게 확인할 정확한 Google AI Studio/Cloud 화면(프로젝트의 API 티어/결제 설정) 안내. 기존 승인만으로 유료 전환은 허용되지 않는다.
4. 실제 전송을 하는 경우 **시도 전에** 별도 진단 기록 경로에 KST 시각, 승인 목적, model/endpoint, 합성 prompt SHA, max_attempts=1, 기존 업무와 독립됨, 상태 `reserved`를 안전하게 영속 저장한 후 1회 시도. 응답/예외 여부를 끝난 뒤 최종 기록하되, 저장이 실패하면 재전송 금지. 실행 전 기록이 이미 있거나 결과 불명이어도 재시도 금지. 기존 `data/video_representative_workflow/studio`의 업무 job/consent/attempt/plan_versions는 절대로 수정하지 않는다. 별도 `reports/gemini35_single_diagnostic_20261113.json` 등 비밀없는 작은 로컬 기록에만 저장; 실제 호출의 중복 방지가 목표. 중복 실행 시 0회로 종료. 비용/상태 검증이 모호하면 실행 불가로 처리.
5. 가벼운 오프라인 검사/시뮬레이션으로 payload가 정확히 합성 문장만 포함하고, retry 없음, 키 미노출, 호출 제한/예약 기록, 0 또는 1회 조건을 확인. 공통 core/ 동작·동영상/음성/기획·컷룸 UI는 변경하지 않는다. 기존 상태 파일·동의·실제 로그 손대지 않는다. 테스트가 단일 진단 스크립트 외에 필요하면 작은 1개만.
6. 보고서는 `reports/GEMINI35_SINGLE_MINIMAL_DIAGNOSTIC_RESULT_20261113.md`에 **실제 호출 횟수 0 또는 1을 분명히** 기록: 무료 계정 확인 근거 또는 확인 불가, 코드 검증, 실제 실행했으면 HTTP status/시간/간단 진단, 재호출 금지 기록, 대본 작업 데이터 불변, 다음 행동 단 하나. 사용자 실전 데이터/계정 비밀 출력 금지. main commit/push/readback 후 종료. repo 외부로 전달하는 실제 진단 원장은 버전 관리 대상에 둘 경우 민감 정보 없는 최소 요약만.

## 금지/주의
일반 업무 실패 job 재실행 금지, 실제 36KB 재기획 payload 전송 금지, Google API key/헤더/동의 본문/과거 사용자 목표 공개 금지, 유료 전환/자동 fallback/새 모델/HTTP 재시도 금지. 비밀키 출력하지 말 것. 서버에서 503/429가 나와도 1회 소진. Git clean/reset --hard/force push 금지. KST. 사용자 요청에 맞게 빠르고 단순하게, 검증 가능한 범위만 수행.
