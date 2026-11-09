# AI Company OS — Groq provider_rejected의 정확한 원인 파악을 위한 최소 진단 보완 (오프라인 전용)

작성: 2026-11-04 KST.

## 최우선 목표
AI Company OS 실제 자율 영상 한 사이클 완주가 목적이다. 두 공급자 실사용 첫 요청이 모두 실패했으므로 **API 연결 오류를 실제로 구분하여 다음 한 번의 실전 검증에서 바로 문제를 해결할 수 있도록** 보완한다. 불필요한 아키텍처 재설계, 새로운 공급자 추가, 무한 안전장치 추가, 대시보드 작업을 하지 않는다.

## 확정된 실제 현황
반드시 `AI_COMPANY_OS_CORE_PRINCIPLES.md`, `AGENTS.md`, `reports/v01_groq_real_autonomous_video_first_run_20261104.md`, `reports/v01_provider_agnostic_groq_free_integration_20261104.md`, `reports/v01_real_free_provider_response_recovery_20261104.md`를 읽고 코드 경로를 직접 조사하라.

실제 Groq 프로젝트 `groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e`는 승인된 2026-11-04 첫 run에서 `openai/gpt-oss-20b` 관리자 plan **송신 시도 1회 → provider_rejected → stopped/plan**. 모델의 정상 envelope, 토큰/finish_reason 없음. _request_json의 포괄 오류 분류 때문에 정확한 HTTP status/provider 오류 유형은 과거 기록으로 복원할 수 없다. 해당 프로젝트의 승인과 사용 가능한 최초 실행 1회는 이미 소비되었다. **원본 상태 hash `4fe0593cb0a1834a972fa42d31c54744ff5b64f619fbdfa57a4a9b514e01c0ca` 및 active_operation `5202abf79d95474091a7cb84fc84ecc3`를 보존**한다. 과거 실제 응답에 임의 status를 붙이거나 '스키마 400'으로 단정하지 말 것. OpenRouter 실패 원장 및 기타 유저 데이터도 불변.

## 이번 Codex 개발 작업 (추가 실제 AI API 요청 **0회**)
1. `groq_provider.py`, `ai_provider_adapter.py`, `autonomous_live.py`, `autonomous_free.py`, `autonomous_groq.py`, 실제 HTTP transport 및 예외 변환 경로를 분석한다. HTTP 400/401/403/404/413/422/429/5xx, 연결/인증/모델 접근/요청 JSON Schema/지원 불가 parameter/토큰·속도 제한/서버 오류를 **응답 status와 유한 error category**만으로 분류 가능한지 확인. 모델 입력이나 provider 임의 메시지 원문을 기록하지 않는다.
2. **최소 진단 기능:** 앞으로 수신하는 HTTP 오류에서 유효한 숫자 status(100~599), 제한된 enum 오류 category, Groq 표준 오류 code가 안전한 allowlist에 정확히 들어갈 때만 해당 코드(아니면 'other')를 저장. 가능한 요청 경로에서는 response가 거절되기 전에 읽을 수 있었던 제한된 응답 헤더의 **숫자 쿼터 정보만** 기록. URL query string, HTTP response body, 사용자 입력·프롬프트, API 키/Authorization header, 임의 공급자 오류문구, token/secret hash 등 민감 정보 로그 금지. HTTP body를 디버그 목적으로 붙이지 말 것. 실패한 attempt의 error_code는 기존 인터페이스와 호환 유지하되 `response_diagnostics` 혹은 `provider_error_diagnostics` 형태의 제한된 필드를 추가한다.
3. **실제 요청 계약 분석:** 선택 모델 `openai/gpt-oss-20b`, Groq fixed endpoint, `response_format` strict JSON Schema, `max_completion_tokens`, `reasoning_effort`, JSON schema의 nested `anyOf` 및 각 object required/additionalProperties=false 등이 공급자 공식 규칙과 합치하는지 구체적으로 점검. 특히 Groq API는 모델/엔드포인트/지원 옵션의 조건이 있으므로 **현재 구현의 요청 내용이 불필요하게 거절될 위험이 있는 부분**을 찾아 고쳐라. 지원 여부가 불확실하면 증명 없이 production에서 자동으로 파서를 완화하거나 fallback하지 말고 오프라인 fixture와 후속 실전 계획으로 제시한다. 실제 status 미확정인 만큼 원인을 확정한 듯 주장하지 말 것.
4. 이미 failed-but-unvalidated인 실사용 원장에 대한 재송신/continue/승인 재사용/다른 store로 복제하는 자동 workaround 금지. **실패 재현은 오프라인 fake Groq HTTPS/합성 키/별도 임시 store로만** 실시한다.
5. 테스트: 최소 fake HTTP 400(invalid JSON Schema/unsupported parameter), 401, 403, 404, 422, 429, 5xx, timeout/connection error, 200 valid strict JSON, abnormal finish, provider error envelope를 검증. HTTP 거절의 status가 최신 원장에 보존되면서 body·secret이 남지 않아야 한다. 기존 Groq 정상 fake AI 협업+실물 MP4 경로 및 OpenRouter 구경로 회귀 보존. 테스트 숫자 경쟁보다 실제 확인될 원인과 최단 수정 경로에 집중한다.
6. **향후 실전 검증 계획:** 왜 다음에는 '풀 자율 운영 run'보다 먼저 **공급자가 API 요청을 수락하는지 판별 가능한 최소 무료 API 호환성 테스트**가 필요할 수 있는지 논증. 만일 추가 실제 API 요청이 필요하면 (i) 과거 운영 승인/실패 attempt 재활용 금지 (ii) 별도의 전송 범위·정확한 모델·최대 추가 호출 수·무료 플랜/유료 금지·한 번의 명시 승인 필요 (iii) 결과와 status를 안전하게 관찰하는 절차를 구체화하라. **이번 지시서는 진단 코드 수정 동의이지 새로운 외부 API 송신 동의가 아니다. 실제 ping/실제 compat call 0회.**
7. 실행 전후 기존 프로젝트·grant·active_operation·서명 키·작업 파일/백업/MP4 SHA 검증, `git diff --check` 및 관련 회귀 테스트 수행. 불필요한 파일 수정/삭제, reset/clean/force push 금지. 기존 .env·키·계정 절대 건드리지 말 것.
8. 결과를 `reports/v01_groq_provider_rejected_diagnostics_20261104.md`에 한국어/KST로 기록: (a) 확정 사실과 불확실성 (b) 실제 바뀐 최소 코드와 HTTP diagnostics field (c) 지원되지 않는 요청 옵션/JSON schema 위험 확인 결과 (d) 테스트 (e) 기존 원장 불변 (f) **다음 실제 무료 API 호환성 테스트에 필요한 단 한 번의 정확한 승인 자료**. 보고서/코드/테스트만 선택적 Git commit/push. 거절 응답 원문·키·유저 작업 자료를 Git에 올리지 않는다.

## 완료 기준
'provider_rejected'만 남던 새 HTTP 오류를 상태 번호/안전 범주로 구별할 수 있어야 하며, 만약 현재 Groq 요청에 명백한 계약 오류가 있다면 정상 계약 보호를 유지하며 최소 수정한다. **이번 오프라인 작업에서 실제 Groq 통신/MP4 완주를 성공했다고 주장하지 않는다.**
