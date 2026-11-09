# AI Company OS — Groq HTTP 403 발생 위치 확인 / Codespaces 네트워크 경로 오프라인 진단

기준: 2026-11-04 KST

## 사용자 요청과 제품 우선순위
사용자는 Groq Playground에서 '안녕하세요' 메시지에 정상 한국어 응답을 확인했고, Groq Free 플랜 / GPT OSS 20B 모델 목록 및 한도 / 조직·Default Project의 명시적 모델 차단 없음 / 키 목록의 Last Used=Never, Usage=0 API Calls / Organization Usage=No usage data / Dashboard Logs=No logs found를 화면으로 확인했다. 모델 웹 채팅 동작은 확인됐으나 **API 키 및 해당 Codespaces API 요청 경로의 정상 작동은 검증되지 않았다.**

첫 실제 Groq 프로젝트 `groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e` 관리자 plan 요청은 provider_rejected로 실패. 뒤이은 별도 승인된 합성 POST 1회는 **HTTP 403 / category=permission / provider_code=other**, 정상이 아닌 응답. **이 403이 Groq 자체, API key/project 제한, 프록시/보안 게이트웨이, DNS/전송 환경 중 어느 층에서 생성됐는지 아직 모른다.** 요청 로그 부재는 중간 차단 가능성을 제기할 뿐 확정 근거가 아니다. **실제 전송 추가 승인 없음. 이번 작업에서는 Groq/OpenRouter/Gemini 또는 다른 외부 AI API에 실제 요청 0회.**

최우선 목표는 개발 편의나 테스트 수가 아니라 '한 번 목표 입력→실제 AI 관리자 계획/직원 협업/검토/수정→최종 영상 MP4' 실사용 완주. 그 전제인 API 연결을 실제로 확인하기 위한 **최소 관찰 가능한 네트워크 진단**이 이번 작업 목표다.

## 필독
`AI_COMPANY_OS_CORE_PRINCIPLES.md`, `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`,
`reports/v01_groq_synthetic_compat_one_post_20261104.md`,
`reports/v01_groq_provider_rejected_diagnostics_20261104.md`,
`reports/v01_groq_real_autonomous_video_first_run_20261104.md`,
`groq_provider.py`, `synthetic_groq_compat_once.py`, `ai_provider_adapter.py`, 실제 HTTP transport / guarded_urlopen / request_json / HTTPError 래핑 코드를 분석.

## 이번에 수행할 작업 (실제 API 재송신 금지)
1. **기존 실제 기록 우선 읽기:** 기존 Groq 실패 store와 합성 진단 독립 원장의 status/category 및 HTTP 응답 source provenance 필드가 이미 있는지 확인. 없으면 불확실하다고 명시. HTTP 403 과거 응답의 raw headers/body/인증 경로는 저장되지 않았으므로 사후 복원이 불가능하면 그 한계를 인정. 과거 state, active_operation, 키·동의/원장/예약 표식을 변경하거나 재사용하지 않는다.
2. **Codespaces의 프록시/네트워크 환경에 대한 비밀 없는 정적 검사:** 실행 프로세스가 HTTPS_PROXY/HTTP_PROXY/ALL_PROXY/NO_PROXY 또는 SDK/urllib 프록시 설정을 어떤 우선순위로 읽는지 **환경변수 이름과 존재 여부만** 보고한다. 프록시 URL 전체, IP/host/port, 인증 정보, secret 값, 인증 헤더, 계정 ID 출력 금지. 환경변수/프록시를 임의로 해제하거나 우회해서 외부로 접속하지 말 것.
3. **전송 경로 코드 분석:** urllib opener/ProxyHandler/guarded_urlopen, 실제 DNS/TLS/HTTPS 연결, 환경 프록시, redirects, HTTPError 포착/변환, status 기록이 서로 어떻게 연결되는지 확인. 특히 첫 실전 요청과 독립 합성 진단이 동일한 proxy/guarded_urlopen 경로를 사용하는지, 요청이 프록시에서 반환될 경우 실제 origin 인증 서버의 응답인지 구분 불가능해지는지 추적.
4. **권한 거절의 발생 계층 가설을 분리:** (a) Groq 애플리케이션/모델 권한 (b) API key가 웹 UI와 다른 프로젝트/키인 경우 (c) 조직·프로젝트 정책 (d) Codespaces 프록시/환경 출구 정책 (e) 요청 schema/옵션. 403과 웹 UI Playground 정상의 조합만으로 특정 가설 확정하지 말 것. 특히 API 키의 표시된 masked suffix와 Codespaces secret을 **출력·비교·추측하지 말 것**. 정상 200이 아닌 403에 원인 없는 supplier_code=other이면 결론 유보.
5. **필요한 최소 코드/진단 개선:** 향후 *별도 승인된* 1회 API 시험에서 HTTP origin vs intermediary를 판단하도록, 메모리 내 HTTP status/리다이렉트 여부/표준 응답 헤더의 제한된 존재 여부만 allowlist로 진단할 수 있다면 코드 개선 및 fake transport 테스트. `server`, `via`, `www-authenticate`, `x-request-id`, `cf-ray` 등 자유 문자열 값을 **로그하지 않는다**. origin 응답임을 헤더만으로 확정하지도 않는다. 저장할 것은 제한된 boolean 존재/안전 분류뿐; 실제 응답 raw body/URL query/auth/키/프록시 호스트 절대 출력 금지. 새 진단이 판단에 도움이 거의 안 되면 **코드를 변경하지 않고** 기존 결과로 가능한 최소 진단만 보고.
6. **오프라인 단위 검증:** fake direct 403, fake proxy 403, fake 200 JSON, HTTPError, timeout, 환경 프록시 존재, 프록시 없는 경로 등은 **네트워크 차단된 합성 fixture**에서만 검증. 테스트에서 실제 Groq API/일반 인터넷 URL로 ping, curl, GET/HEAD/OPTIONS/POST, SDK 연결 진단 금지. 공식 공개 문서 검색은 필요할 때 가능하나 API 인증 경로에 실제 접속 금지.
7. **실무적 결과:** 검사 후 사용자가 웹에서 한번 더 확인할 정보가 있다면 **사용자에게 한 가지만** 구체적으로 제안하라. 예: 조직/프로젝트 API key 연결 상태, Groq 공식 서비스의 인증 거절 로그, Codespaces 네트워크 정책 등. 무조건 새 키 발급/결제/권한 개방/보안 해제 요구 금지. 필요시 별도의 **단 한 번 승인 범위**로 미래 실사용 API 호환성 검증을 제안하되 이번 명령으로 실제 POST 실행하지 않는다.
8. **기존 데이터 보존:** `groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e` 상태 hash `4fe0593cb0a1834a972fa42d31c54744ff5b64f619fbdfa57a4a9b514e01c0ca`와 active_operation `5202abf79d95474091a7cb84fc84ecc3` 유지. 독립 합성 403 원장 `data/synthetic-groq-compat-once-20261104/operation.json`의 예약/1회 소진 기록 그대로 유지. OpenRouter 실패 원장 및 수동 프로젝트·backup·mock MP4 유지. 어떤 실패 원장도 초기화·재전송·'성공' 전환·재생성하지 않는다. `.env`, Git secrets, provider config, 구동 환경변수/사용자 작업 파일 수정 금지. reset/clean/force push 금지.
9. 필요 최소한의 회귀 테스트와 `git diff --check`; 실제 API 호출/비용 0회. `reports/v01_groq_403_origin_codespaces_offline_diagnosis_20261104.md`에 한국어/KST로 사실, 불확실성, 정확한 HTTP 코드의 확인 범위, 프록시 변수 **존재 여부만**, 관련 전송 코드의 원인 경로, 테스트 결과, 변경 파일, 기존 원장 보존 및 다음 최소 액션을 남긴다. 비밀 정보 없는 코드/테스트/보고서만 선택적 commit/push한다.

## 수행하지 말 것
- 실제 외부 AI API 호출, Groq 인증 호출, 새 synthetic POST, 기존 operation 재실행, 다른 무료 모델/공급자로 자동 fallback, 계정 변경, 결제
- 프록시/방화벽/TLS 검증을 우회·비활성화하는 실험, 사용자가 승인하지 않은 외부 전송
- Codex가 임의로 실제 프로젝트 결과물을 만들어 실사용 AI 성공이라고 주장
- API 키·인증 헤더·프록시 URL 및 프록시 자격 증명·프로젝트 데이터 원본의 로그/커밋

## 완료 기준
HTTP 403의 **원인 확정 여부를 정직하게** 판별하고, 현재 정적 자료만으로 원인 미확정이면 추가 실전 호출 전 확인할 **가장 좁은 설정/관측 항목**을 도출한다. 수십 개의 테스트보다 사용자 문제 해결에 직접 연결되는 진단 결과를 우선한다.
