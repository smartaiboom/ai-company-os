# Gemini 무료 모델 API 실연결 검증 — Codespaces Secret 반영 후 단일 호출

작성: 2026-11-04 KST

## 검증된 선행 사실
- 사용자가 GitHub Codespaces를 재시작한 후 `python -c "import os; print('Gemini 등록 성공' if os.getenv('GEMINI_API_KEY') else 'Gemini 키 없음')"`의 실행 결과 **Gemini 등록 성공**을 확인했다. 키 값/길이/일부/해시 출력 금지.
- 사용자가 Google AI Studio에서 해당 API 키 프로젝트의 **결제 등급이 무료 등급**임을 직접 확인했다. 별도 청구 또는 유료 모델 전환 승인 없음.
- 이전 보고서 `reports/v01_gemini_free_one_call_connection_20261104.md`는 키가 이전 세션에 없어 실제 요청 **0회**로 중단됨. 해당 보고서/기록 보존.
- 이 작업은 이전에 사용자가 요청한 Gemini **최소 연결 테스트 1회**를, 선행 조건 해결 후 재개하는 것이다. 외부 AI 호출은 이번 범위 내 정확히 최대 1회.

## 정책 및 작업 준비
`AI_COMPANY_OS_CORE_PRINCIPLES.md`, `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`, 기존 Gemini 단일 호출 지시서 `codex_tasks/v01_gemini_free_one_call_connection_20261104.md`, 보고서 `reports/v01_gemini_free_one_call_connection_20261104.md`부터 읽어라. 기존 Git worktree, 각종 백업·기존 Groq/OpenRouter failed 원장 및 활성 프로젝트·AI 직원/영상 코드·user 파일 보존. KST 표준.

## 순서와 경계
1. 환경변수 `GEMINI_API_KEY`가 현재 **실행될 실제 프로세스**에서 존재하는지 비밀 없는 bool만 검사. 없다면 즉시 중단. 재시작 전 사용자의 성공 확인만 믿고 누락 상태로 진행하지 말 것.
2. Free Tier 사용자 확인은 본 지시서의 선행 사실로 인정; Google Free Tier 요금이 명시된 모델 `gemini-2.5-flash-lite`만 고정하고 결제 등급 변경/다른 모델로 fallback/키 재생성/프로젝트 교체/구독 변경 금지. **Google API 웹측 현재 한도·무료 제공 여부가 사전 자료와 충돌한다고 확인되는 경우 요청 전 중단하여 보고**. 공식 문서 읽기는 가능, 인증 API preflight/다른 endpoint 네트워크 테스트 금지.
3. 외부 AI API 호출 **총 1회 이하**. 단일 `POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent`만 허용. 헤더 `x-goog-api-key`는 메모리에서만 참조. 키를 URL query 등에 넣지 않는다. HTTPS 인증서 검증 정상 유지, 리다이렉트/재시도 금지, 최대 timeout 30초, 최대 응답 8KiB. raw HTTP trace 또는 authorization/key 헤더 출력 절대 금지. 프록시·TLS 정책 변경/우회 금지.
4. 요청 본문은 아래 짧은 고정 안전 테스트 문구만 사용하며 실회사/개인정보·사업자료 입력 금지:
```json
{"contents":[{"role":"user","parts":[{"text":"안녕하세요. 한 문장으로 한국어 인사만 해 주세요."}]}],"generationConfig":{"maxOutputTokens":80,"temperature":0.2}}
```
5. 기존 독립 합성 Groq operation ledger와 기존 실패 프로젝트 재사용/수정/재시도 금지. **새 Gemini 전용 operation ID 및 O_EXCL 방식 1회 선예약 파일** 작성하여 호출 시도 전 소진 표시. 이 파일이 이미 존재하거나 이전 Gemini 시도 증거가 있다면 중단하고 상태만 보고. 테스트를 위해 실패 원장 초기화 금지.
6. 스크립트/fixture 개발과 **socket 차단한 fake 200/401/403/429/redirect/timeout 오프라인 테스트**를 먼저 하고 성공 시 단일 라이브 POST. 코드의 import로 네트워크 연결 안 되게 한다. 비용 추정·기존 예산 장치 우회 금지.
7. **결과 출력 최소화**: HTTP status 정수, 성공 여부, KST timestamp, 성공 시 무해한 한국어 인사 답변 최대 200자, 반환된 사용 토큰 수가 있다면 numeric, 실패 시 숫자 기반 고정 에러 분류만. response 전체/raw JSON/body/headers, request ID, 키/식별정보, URL query, 앱프로젝트 ID 출력/커밋 금지. 실제 호출이 성공해도 manager/workers 자동 실행은 하지 않는다.
8. `reports/v01_gemini_free_one_call_execute_after_secret_restart_20261104.md`에 키 존재 확인과 무료 등급 사용자 확인, 실제 호출 횟수(0/1), 정확한 결과 HTTP status, 토큰·답변의 안전 요약, 실패 분류, 재시도 0회, 기존 데이터 보존, 회귀 테스트, 다음 액션을 한국어·KST로 보고. 실패 시 결과를 정직하게 표시하고 원인 추측 반복/새 공급자 전환/자동 재시도 금지.
9. `git diff --check`, 필수 테스트 확인 후 비밀 없는 코드/테스트/보고서만 선택적으로 commit/push.

## 완료 기준
본 Gemini API 실제 짧은 응답이 성공하면 **공급자 인증/네트워크 최소 연결 성공**으로 기록하고, 기존 AI Company OS의 AI 관리자·직원 협업 작동까지 성공했다고 과장하지 않는다. 실패 시 상태를 정확히 기록하고 다음 해결 단계 1가지만 제안. 기존 어떤 프로젝트와 기록도 삭제하지 않는다.
