# AI Studio 기존 키로 TTS 모델 제공 여부 1회 조회 — 2026-11-10 KST

## 이번 작업
사용자는 기존 무료 Google AI Studio 프로젝트의 모델 목록 조회를 명시 승인했다. **Codex가 기존 API 키를 로컬에서만 사용하여 읽기 전용 Gemini 모델 목록 API를 조회하고 결과를 기록하라.** 이번 동의는 모델 목록 조회에만 적용되며 **TTS 음성 생성, 모델 추론, 결제/카드/Billing 변경, 계정 설정 변경, API 키 신규 발급을 승인하지 않는다.** AGENTS.md를 준수하고 실제 수행·결과 보고·커밋까지 완료할 것. 또 다른 준비용 시스템/게이트를 개발하지 말 것.

## 이전 결과, 중복 금지
- 사용자가 AI Studio 화면으로 확인한 사항: `Default Gemini Project` / 프로젝트 ID `gen-lang-client-0938732315` / API 키 1개 / **무료 등급**. 기존 사용량 화면에는 Gemini 3.1·3.5 Flash Lite만 보였으며 이것은 모델 지원 목록이 아닌 **사용 기록**.
- `reports/GEMINI_TTS_REAL_ONE_SHOT_RESULT.md`: 실 음성 생성 0회, 준비 payload SHA `9dde86070b2cb5be7263d654cd208a6ead743e7074a76c5162e10ff0edd5bd16`, WAV B 없음, TTS 프로덕션 실행은 disabled. 기존 `reports/NO_CARD_TTS_EXECUTION_GATE_RESULT.md`, `reports/CURRENT_PROGRESS.md`, `companies/video/tts_execution.py`, `companies/video/tts_cli.py`와 관리자 Gemini 키 환경을 참고한다. 비밀키·모델·미디어·원장은 그대로 보존한다.
- 사용자의 화면에 키 전체가 나오지 않음. 실제 프로젝트 ID는 공개 지시서에 노출을 최소화하되 계정/키 바인딩 확인은 로컬에서 수행.

## 조회 방법
1. Google 공식 `models.list` 문서 https://ai.google.dev/api/models 및 공식 모델 문서 https://ai.google.dev/gemini-api/docs/models , 가격 https://ai.google.dev/gemini-api/docs/pricing 확인. 문서에서 지원하는 **GET** `https://generativelanguage.googleapis.com/v1beta/models?pageSize=100`를 기본으로 하고, `nextPageToken`이 있는 경우 필요한 최소 횟수만 동일 GET으로 페이징. API 키는 반드시 `x-goog-api-key` 헤더에서만 사용. URL 쿼리·CLI 인수·로그/GitHub/출력 파일에 키 포함 금지. 응답 크기·timeout 제한 및 redirect/proxy/retry 금지; 429/5xx/타임아웃이면 재시도 없이 중지. 모델 조회만, generateContent/interactions/TTS 전송 금지.
2. 기존 Codespaces의 키 이름을 안전하게 찾아 사용. 키 문자열을 echo/print/save 하지 않는다. 키가 없거나 프로젝트 소속 확인이 불가능하면 API 호출하지 말고 어떤 **환경변수 이름이나 설정 경로(키 값 제외)**를 확인하면 되는지 보고하라. 키-프로젝트 연결은 API listing만으로 증명하기 어려울 수 있으므로 미확인으로 둔다. 실제 계정 스크린샷의 프로젝트 정보와 로컬 키 증거를 구분.
3. 조회 성공 시 **모델 이름만** 필터해 `gemini-3.8-flash-tts`, `gemini-3.8-flash-lite-tts`, `gemini-2.5-flash-preview-tts` 등 TTS가 리스트에 포함되는지, `supportedGenerationMethods` 등 실제 반환된 모델 메타데이터가 무엇인지 표시. 공식 공개 모델 목록에 있다는 사실과 **현재 사용자 키의 list 응답에 나온 것**을 구분. '목록에 존재함'만으로 실제 TTS 호출 성공/잔여 무료 할당량/과금 0을 보장하지 않는다. 오히려 목록에 없어도 엔드포인트/버전 정책 차이일 수 있음을 기록.
4. 필요하면 로컬에 독립 1회성 조회 스크립트를 추가하거나 기존 HTTP helper 재사용. 프록시 우회 금지, API 키 관련 예외 내용·원시 headers/token 비저장. 시도 영수증(실제 GET 횟수, HTTP 응답 코드, 조회 시각 KST, 매칭 모델 목록, 정황상 확정/미확인), 실패시 이유를 로컬 안전 경로에. 개인 키/전체 응답을 GitHub 업로드 금지.
5. 보고서 `reports/GEMINI_TTS_MODEL_LIST_CHECK_RESULT.md`와 `reports/CURRENT_PROGRESS.md` 갱신. 실제 GET 모델 조회 여부와 횟수, 현재 키의 모델 이름 증거, 프로젝트/무료 등급/쿼터/결제 여부 중 **화면으로 확인된 것만** 구분, TTS 음성 생성0회/추가비용0원, **다음 최소 조치 한 가지** 기록. **실제 API 조회 시 비용이 발생하지 않는 모델 목록 조회만** 허용. 모델 목록도 확인 안 되면 그 이유만 보고하고 다른 결제/생성 API로 우회 금지.
6. 코드 수정 시 최소 단위 테스트만(모의 GET 등), GitHub main에 코드·테스트·보고서만 커밋·푸시. 기존 영상/대본/음성/토큰·원장/사용자 미추적 파일 불변. KST UTC+9.

## 범위 밖
음성합성 실제 호출, 사용자 대신 로컬 exact-review 서명, 새 모델에 자동 fallback, 동의/안전게이트 수정, 영상 제작/UI 개발, Google Cloud Billing/card 등록. 조회가 성공하면 ChatGPT가 보고서를 읽고 다음 실제 음성 1회 요청의 안전조건을 분명히 제안할 것이다.
