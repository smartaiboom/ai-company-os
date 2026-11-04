# AI Company OS v0.1 — Gemini Free API 연결 확인: 실제 요청 최대 1회

작성일: 2026-11-04 KST
목표: Gemini API 키가 GitHub Codespaces secret `GEMINI_API_KEY`에 등록된 현재 환경에서 **무료 모델 텍스트 응답을 단 한 번 검증**한다. 실전 AI 관리자/직원 엔진 연결은 이 작업 범위 밖이다.

## 필수 준수
- `AI_COMPANY_OS_CORE_PRINCIPLES.md`, `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`를 먼저 읽는다. 기존 Groq/OpenRouter 실패 원장·프로젝트·동의/토큰 예약·백업·기존 mock MP4·코드·환경설정 보존. KST.
- 사용자는 Google AI Studio에서 키 생성하고 GitHub Codespaces Secrets에 `GEMINI_API_KEY` 등록 완료를 확인했다. 키 값이나 일부, hash, masked suffix 등 어떤 식별 가능한 비밀도 터미널/보고서/로그/git에 출력하지 않는다. `GEMINI_API_KEY`의 **존재 여부만** 메모리에서 확인한다. 없으면 바로 중단하고 'Codespaces 재시작 또는 secret access 점검'이라고만 보고한다.
- 공식 요금표 https://ai.google.dev/gemini-api/docs/pricing 상 `gemini-2.5-flash-lite`의 **Free Tier Standard input/output=Free of charge**. 하지만 사용자의 Google 프로젝트가 실제 Free Tier인지 **미검증**. 사용자의 별도 결제 승인 없음. AI Studio 프로젝트가 유료 tier인지/본 키에 과금이 걸린 경우에는 요청 전 중단하고 사용자에게 확인 요청. 확인할 수 없다면 '무료 티어 여부 미확인'을 보고하고 호출하지 않는다. 모델 바꾸기/자동 fallback/유료 전환 금지. 사용자 실제 회사/개인 정보는 절대 프롬프트에 포함하지 않는다.
- **실제 외부 요청 총합 최대 1회**이며 허용된 요청은 `POST https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent` 1회만. 문서 조회/사전 모델 목록 GET/healthz/other API/Google 검색/통신 연습 호출 금지. GitHub git fetch/push는 예외. 재시도/리다이렉트/SDK 자동 retry/검증 목적 중복 요청 모두 금지. 429/403/401/404/400/timeout 등 실패하면 즉시 중단.
- 요청은 공식 `x-goog-api-key` 헤더 인증 방식으로, 키를 URL query string에 넣지 않는다. HTTPS 인증서 검증 정상 유지. stdlib/단일 HTTP transport 사용 시 redirects 끄고 기존 global network/proxy/TLS 정책 변경·우회하지 않는다. Body는 아래와 같은 고정 짧은 요청. 비밀없는 public fixture JSON은 기록 가능.
```json
{
  "contents": [
    {
      "role": "user",
      "parts": [{"text": "안녕하세요. 한 문장으로 한국어 인사만 해 주세요."}]
    }
  ],
  "generationConfig": {"maxOutputTokens": 80, "temperature": 0.2}
}
```
- 요청 전에 오프라인에서 payload, endpoint, header name, timeout(30초 이하), 응답 제한 최대 8KiB, 리다이렉트 금지, 실제 1회 선예약/실패 후 추가 실행 거부를 검증한다. **기존 synthetic Groq one-use ledger 재사용 금지.** 별도 Gemini 테스트용 진단/1회 선예약 파일을 O_EXCL 형식으로 작성한다. 하나라도 준비 못하면 실제 호출 중단.
- 인증 키, 요청 및 응답 전체 headers, request ID, raw response body, HTTP trace, Google project ID, URL query, 수신 IP, error message에 임의 반영된 원문 등을 로그하지 않는다. 허용 출력: 요청 여부, KST 시각, HTTP status integer, response type, 성공 시 한 문장 한국어 모델 텍스트 (비밀 없는 고정 테스트에 대한 답변이지만 합리적인 길이로 제한), 사용량 토큰 numeric(있을 때만), 실패 시 안전하게 고정 매핑한 에러 카테고리(401_auth/403_permission/429_limit/400_payload/404_model/5xx_server/network/other), raw 자유 문자열 배제.
- 이것은 **실제 API 키와 Codespaces 네트워크 경로의 최소 확인**일 뿐 AI Company OS 전체 시스템 성공이 아니다. 무료 모델 입력 데이터의 제품 개선 사용 정책에 따라 프롬프트는 인사만 쓴다.
- 한 번 이상 부주의하게 시도했다면 추가 호출하지 않고 시도 횟수와 원인만 보고. 실패시 Groq처럼 며칠간 추측 진단을 반복하지 말고 결과를 바탕으로 수정 방향 한 가지 제안.
- 성공 시에도 이번 작업에서는 Gemini provider 모듈을 AI Company OS 실행/manager/workers 경로에 자동 연결하지 않는다. 기존 미완료 프로젝트의 상태도 변경하지 않는다.

## 실행 절차
1. 저장소 정책과 기존 transport를 읽고, 환경의 `GEMINI_API_KEY` 존재 여부 확인. 외부 AI 요청 없음.
2. 현재 연결된 Google 프로젝트가 Free Tier임이 사용자/UI/기존 명시 기록에서 확인되는지 판단한다. 확인 안 되면 코드/오프라인 테스트와 보고서만 만들고 실전 호출은 보류(추측해 결제 위험 감수하지 말 것).
3. 필요한 최소 1회 실행 스크립트 및 격리된 단위 테스트를 추가한다. import 시 네트워크 연결 안 되게 한다. O_EXCL ledger가 실제 요청 전에 예약되도록 한다. 테스트 fixture 가짜 HTTP 200/403/429/redirect/timeout으로만 검증한다.
4. 위 모든 조건 충족 시 실제 generateContent POST를 **정확히 최대 1회** 실행. 성공/실패에 관계 없이 consumed 처리 유지. 오류를 숨기지 말고 적합한 종료 코드.
5. `reports/v01_gemini_free_one_call_connection_20261104.md`에 한국어로 '실제 호출 시행 여부', 호출 횟수, 모델, KST 시각, 결과 코드/텍스트(안전 범위), 무료 티어 확인 근거 또는 보류 사유, 재시도 여부(0), 테스트, 기존 데이터 보존, 다음 액션 명시. 새로운 키가 들어간 파일/출력은 커밋 금지. `git diff --check`, 필요한 범위 테스트, 변경된 비밀 없는 파일과 보고서만 commit/push.

## 완료 기준
- 무료 티어 확인이 가능한 경우: Gemini 실 API 1회와 결과 보고를 마친다. 성공하면 'Gemini 호출 연결 확인'이라고만 표현.
- 무료 티어 확인이 어려운 경우: 이유와 사용자에게 필요한 확인 위치를 한 가지로 좁힌다. 실제 호출 0회를 명시한다.
- 어느 경우든 기존 AI Company OS 실사용 자율 협업 구현을 초기화하거나 재구성하지 않는다.
