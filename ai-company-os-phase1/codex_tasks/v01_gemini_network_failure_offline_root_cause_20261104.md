# AI Company OS v0.1 — Gemini 1회 연결 실패의 로컬 예외 분류 정확화 (오프라인 전용)

날짜: 2026-11-04 KST

## 목적 및 사실
사용자는 Groq API에서 HTTP 403, Gemini API에서 실제 HTTP status 없이 `network`로 표시된 실패 때문에 핵심 AI Company OS 개발이 지연되는 상황을 원치 않는다. 이번 작업은 공급자 변경/반복 호출이 아니라 **가장 짧은 경로로 실제 연결 차단 위치를 확인할 진단을 개선하는 오프라인 작업**이다.

직전 보고서: `reports/v01_gemini_free_one_call_execute_after_secret_restart_20261104.md`. 사용자는 GEMINI_API_KEY 존재와 Google AI Studio Free Tier 확인. 실제 Gemini POST는 2026-11-04 13:30:59 KST에 1회 시도 후 `network`, http_status=null, 재시도 0. `data/gemini-connection-once-20261104.json`은 소진 상태. Groq 기존 실패 원장 및 OpenRouter 실패 원장도 보존.

중요 관찰: 현재 `gemini_connection_once.py`의 `except Exception: record['error']='network'`는 URLError/SSL/socket과 다른 예상 밖의 로컬 Python 예외까지 모두 network로 분류한다. 따라서 `network`는 통신 오류 확정 증거가 아니다. 기존 원장에 실제 예외 타입이 없다면 **과거 실패의 종류를 사후 복원할 수 없음을 명시**한다.

## 필독 및 작업 범위
`AI_COMPANY_OS_CORE_PRINCIPLES.md`, `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`, 위 이전 보고서, `gemini_connection_once.py`, `tests/test_gemini_connection_once.py`, `ai_safety.py`, Groq 진단 보고서를 읽어라.

1. **실제 AI API 요청 0회**, 외부 HTTPS/DNS/curl/ping/healthz/모델 목록 인증 요청 0회. 기존 Gemini 1회 소진 원장 삭제·수정·재사용 금지, 새 operation/승인 생성 및 모델 전환 금지. 새 Gemini live POST 실행 금지. Codespaces proxy/security/TLS 우회 금지.
2. 네트워크를 사용하지 않는 정적 코드 분석으로, 실행의 각 단계(키 조회→Request 생성→원장 예약→실시간 타이머→DNS/socket/SSL→urllib HTTP→응답 수신→JSON parse→답변 검증→원장 저장)에서 발생할 수 있는 예외 클래스가 현재 어느 `except`로 귀속되는지 명확히 정리. 특히 `urllib.error.URLError`, `socket.timeout`, `TimeoutError`, `ssl.SSLError`, `ConnectionError`, `http.client.RemoteDisconnected`, `OSError`, 예상 밖 `Exception`, HTTPError와 HTTP status의 차이.
3. 진단이 실제 원인을 가리키게 최소 수정: **미래 요청에 한해** 예외의 타입/단계에서만 파생되는 고정 enum(category)·고정 stage(사전 정의된 목록)·HTTP status를 사용. 예: dns_error/tls_error/connect_timeout/connection_reset/transport_error/local_unexpected_error/parse_error/invalid_response/timeout (상태에 맞게 설계). `exception.__str__`, errno 메시지, response body/header, 키·URL query·프록시 host, IP, 프로젝트 식별정보 등 **원문 자유 문자열은 절대로 기록하지 않는다.** 보안상 오류 코드 분류를 안전하게 허용한 경우만 numeric; origin/server가 403을 반환했음을 검증하지 않고 임의 추측 금지.
4. 외부 요청 없는 fake fixtures로 다양한 예외를 inject 해 분류를 검증. 기존 진단 범위 fake 성공/HTTP403/HTTP429/redirect/timeout 및 1회 소진 보호 회귀 포함. 기존 data/backup/checkpoints/기존 사용자 파일 보존.
5. 가능하다면 **실제 네트워크 없이** Codespaces의 정적 네트워크 설정(HTTP_PROXY/HTTPS_PROXY/ALL_PROXY/NO_PROXY 값은 표시하지 않고 이름의 존재 여부), default urllib opener의 getproxies 선택 및 redirect/SSL 정책, 현재 Groq와 Gemini 호출 경로 차이를 확인해 보고하되 이 정보만으로 서버 원인을 확정하지 말 것. Git transport 성공 ≠ generativelanguage.googleapis.com 성공.
6. 실제 접속 없이 재현 가능한 명백한 로컬 구성 버그가 발견되면 최소 수정하고 fake unit tests로 검증. **진단만 추가하고 끝나는 경우에는 원인 미확정을 분명히 기록**.
7. 산출물 `reports/v01_gemini_network_failure_offline_root_cause_20261104.md`에 (a) 실제 HTTP 응답 부재 / 1회 소진 (b) 복구 가능한 관측/불가능한 과거 내역 (c) 현재 코드 분류 오류 (d) 코드 변경 및 테스트 성적 (e) Groq와 Gemini 실패 공통 원인 주장에 대한 한계 (f) **사용자에게 가장 간단한 다음 액션 정확히 한 가지**를 KST/한국어로 작성.
8. 테스트 및 `git diff --check`, 비밀없는 관련 파일만 선택적 commit/push. 현재 제품 개발의 다음 단계에서 관리자→실제 AI 직원→검토→MP4를 막는 구조를 따로 요약하되 이번 작업의 외부 API 없이 실사용 성공을 주장하지 않는다.

## 명시적 금지
- 외부 생성형 AI API/Google/Groq/OpenRouter 연결 재시도, 새로운 공급자 도입, 과금, API 키 재발급/교체
- 기존 실패 원장을 지우고 '처음 시도'처럼 새로 시작, 기존 사용자가 만든 작업/코드 삭제, reset/clean/force push
- 허가 없이 사용자 사업정보를 무료 모델에 입력하거나 계정 보안 제한을 우회
- 과거 `network`를 DNS/방화벽/프록시 원인으로 확정하거나, 앞으로 출력하는 enum을 실제 provider origin 검증으로 과장
