# Gemini 503 — 호출 없이 두 실패의 원인 범위 진단 (2026-11-13 KST)

## 절대 목표
실제 게임 쇼츠의 **대본·영상·음성 품질 개선** 작업이 반복된 구현 수정과 외부 서비스 오류 때문에 지연되고 있다. **이번은 진단만** 한다. 실 API/YouTube/네트워크 전송 금지, 서비스 연결 테스트도 API 요청이면 금지. 대체 모델/유료 전환/자동 재시도/신규 job/새 동의/불필요한 UI 변경 금지. Codex가 실제로 할 일은 현 코드와 저장된 호출 기록을 검증하고 **다음 행동을 한 번에 결정할 수 있는 간결한 보고서** 작성이다.

## 외부 확인된 사실 (2026-11-13)
Google 공식 Gemini 문서에서 `gemini-3.5-flash-lite`는 안정된 지원 모델, structured outputs 지원, 엔드포인트 `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent` 형식 사용. Google 공식 API 오류 문서에서 HTTP 503은 service_unavailable/서비스 과부하 또는 일시적 장애. 따라서 503만으로 JSON 검증/프롬프트 구조가 원인이라고 단정 금지. 공식 정보:
https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
https://ai.google.dev/gemini-api/docs/api-errors
https://discuss.ai.google.dev/t/handling-429-503-errors-from-the-gemini-api/124640

## 확정 요청 기록
- 11/12 16:41:21~23 KST, plan, HTTP503 failed, provider_unavailable, unvalidated, response_hash null, request_hash bc787bb74af99b6a97cce47f3c5d4bd20a66c94c41d7136d423ba2a89439512a. job qualityprovider-63f5d501fc34496292167736371b990c.
- 11/13 09:17:59~09:18:01 KST, plan, HTTP503 failed, provider_unavailable, unvalidated, response_hash null, request_hash a4a6c6db05749ba2a81f6232d3bba7168b70a13d4a6cc4745c8f177479c2b749. **현재 새 job ID는 실제 프로젝트 파일을 읽어서 찾되 추측하지 말 것.**
- 더 이전 다른 일자 HTTP200 후 invalid_dependencies 실패 역시 별개 이슈로 보존. 서로 혼동 금지.

## 진단 — 로컬 읽기만
1. 먼저 AGENTS.md와 현재 git 상태/최신 코드 확인. 로컬 작업중 변경·미추적 파일 덮어쓰기/정리 금지. 데이터 파일은 메모리에 읽어 확인만 하고 쓰지 말 것. 실패 job과 실제 컷룸 프로젝트 링크, 서명/실제 전송 기록 상태(완료/예약/미확정) 확인. 비밀 키값·헤더·API payload 전문·민감한 goal/피드백 전문/동의서 전문 출력 금지. 보고에는 요청 hash/크기/구조적 지표만.
2. core/autonomous_gemini35.py, core/autonomous_gemini.py, core/ai_provider_adapter.py (실제 파일명을 찾을 것), companies/video/representative_rework.py, 호출/응답 수신 처리 코드를 파악. HTTP 503이 **어느 계층에서 분류**됐는지; 서버 응답 body/header의 에러 메시지/Google request ID 등이 **실제 원장에 저장되었는지** 읽기만 확인. 저장되지 않은 원인은 재구성했다고 주장 금지. 모델/endpoint/timeout/retry-disabled 정책/무료 계정 binding 확인. 실제 코드에서 생성되는 rework-plan 요청 스키마의 크기·토큰 추정·duplicated output_contract/systemInstruction/JSON Schema 포함 여부, 실제 저장 request_hash의 재현 가능 여부를 확인하되 필요시 합성 상태/임시 오프라인 데이터로만 수행. 기존 프로젝트 저장 호출 원장 변경 금지. 단순 HTTP 503을 JSON schema 오류로 오진 금지.
3. **원인 구별표**: 서비스 503, 과도하거나 중복된 payload, 전송/프록시 문제, 모델·설정 오류 중 '검증됨/가능성/근거 부족'으로 구분. Google 공식 모델 문서상 모델 ID는 유효하다는 사실 포함. 그저 추측으로 운영 중 모델/계약 서명/요청형식을 수정하지 말 것.
4. 사용자에게 다음 단계 하나만 추천: (a) 기존 local log로 충분한 원인 확정이면 그에 맞는 최소 코드 수정 후보, 또는 (b) 정보 부족이면 **별도의 명시적 동의가 필요한 최대 1회 최소 연결 진단 호출**(모델 고정, 별도 예산, 실패도 차감, 반환 status만, 요청 내용 무해한 합성 텍스트, 실제 업무 goal 미전송), 또는 (c) 공식 상태가 불안정하면 호출 연기. **이번 Codex에서는 실제 호출 하지 않는다.** 진단용 API도 무료인지 미확인 상태이므로 자동 승인하지 않는다.
5. 오프라인 테스트는 필요할 경우 특정 함수만 1개 이내. 기존 테스트 전체 회귀/재실행/새 코드 수정 불필요. 요청 전문/키/개인 정보 유출 방지.
6. 짧은 결과를 `reports/GEMINI503_OFFLINE_ROOT_CAUSE_AUDIT_RESULT_20261113.md`로 저장: 실제 저장된 두 요청의 상태·비교, HTTP 응답 본문 보존 여부, 요청 크기/스키마 구조 근거, 검증된 원인과 불확실성, 다음 단계 하나. **이번 외부 호출0회**, 원장/산출물/동의 불변, 검사 결과 명시. main commit/push/readback 후 종료.

## 사용자 운영 원칙
한국어만. 코드는 수정하지 않는 것이 기본. 기존 데이터/data/backups/artifacts/.env/완료 음성 영상/서명/승인/attempt/unknown call/미추적 파일 보존. git clean/reset --hard/force push 금지. KST. 정책·승인 및 무료 모델 조건 유지. 실제 품질 작업으로 돌아가기 위한 진단이므로 새 분석 도구나 지속적 모니터링 시스템을 개발하지 않는다.
