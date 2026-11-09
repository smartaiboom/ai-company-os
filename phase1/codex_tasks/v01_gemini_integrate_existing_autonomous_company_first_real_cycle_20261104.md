# AI Company OS Phase 1 — 검증된 Gemini 연결을 기존 AI 관리자·직원 자율 업무 흐름에 통합

기준일: 2026-11-04 KST

## 상황 / 가장 중요한 목적
사용자 직접 실행으로 GitHub Codespaces에서 Gemini API 인증 모델 목록 `GET /v1beta/models?pageSize=1`은 HTTP 200, `gemini-3.1-flash-lite:generateContent` 짧은 인사 POST는 **HTTP 200 / first byte 약 0.642초 / total 약 0.642초**를 확인했다. curl은 `-o /dev/null`을 사용했으므로 **본문 구조와 텍스트가 검증된 것은 아니다.** 과거 Gemini 2.5 Flash-Lite POST 404, 3.1 Flash-Lite 과거 30초 timeout와 503을 거쳐 최근 200을 얻었다. 단건 성공은 안정성 보장이 아니다.

지금 최우선 과제는 진단기 추가나 공급자 바꾸기가 아니라, **기존 자율 회사의 실제 manager→employee→review→revision→artifact 경로에 Gemini 무료 모델을 통합하고 첫 완주 실행 준비를 마치는 것**이다. 이미 갖춘 워크플로를 보존한다. Codex와 mock이 실제 AI 관리자 역할을 대신해서는 안 된다.

## 시작 전 필독 및 분석
`AI_COMPANY_OS_CORE_PRINCIPLES.md` (특히 1~5절), `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`, 기존 보고서 `reports/v01_gemini_free_one_call_execute_after_secret_restart_20261104.md`, `reports/v01_gemini_network_failure_offline_root_cause_20261104.md`, `reports/v01_groq_real_autonomous_video_first_run_20261104.md`를 확인.
실제 코드 전반 `autonomous_live.py`, `autonomous_free.py`, `autonomous_groq.py`, `autonomous_company.py`, `ai_provider_adapter.py`, `ai_safety.py`, `local_artifacts.py`, `gemini_connection_once.py`, CLI/API 엔트리포인트, tests, persistence, approval/consent/budget ledger를 분석. 필요한 최소 변경을 선택.

## 작업 1: Gemini 공급자 adapter
- **새 격리된 Gemini adapter**를 사용 중인 provider abstraction에 맞춰 추가. 공식 Gemini `generateContent` API 형식; `GEMINI_API_KEY` 환경값 메모리 사용만. 키·일부·해시·쿼리값·raw Authorization/헤더 기록 금지.
- 모델은 성공한 `gemini-3.1-flash-lite`로 고정하며 실제 Google AI Studio 프로젝트의 **Free tier**라는 사용자 확인을 바탕으로 하되, 현재 공식 요금표에서 **이 모델 자체의 무료 요청/출력 제공 여부**, 무료 등급 정책·할당량을 다시 검증. 사이트 확인이 어렵거나 모델이 무료가 아니라면 **실전 송신 금지 및 이유 보고**. 모델을 임의 교체하지 말 것. 실제 유료 전환 또는 quota/가격 불확실성에 무단 fallback 금지.
- 기존 manager/employee JSON 요구 계약을 그대로 유지하되 Gemini 응답의 `candidates[].content.parts[].text`를 꺼내고, 종종 `thought` 등 별도 블록/빈 응답/finishReason/maxOutputTokens로 인해 JSON 누락이 발생할 때 정직하게 검증/중단. Gemini는 OpenAI `choices` 구조가 아니므로 단순한 URL/키 교체를 하지 말고 어댑터 계층에서 정확히 변환.
- 기존 free policy의 안전 경계를 유지: 요청의 안정 식별·지속 원장 사전 예약·중복 호출 방지, 불확실한 timeout/503/429 처리, 공급자 쿼터·속도 제한, 별도 명시 없는 fallback/자동 retry 차단, 비용 0 확인. 응답 입력/출력 바이트/토큰 상한과 JSON strict 검증, 예외 분류.
- 공유 Groq/OpenRouter adapter 및 기존 사용자 프로젝트에는 부작용 없는 분리 설계를 사용. model/base_url 확인 조건이 기존 OpenRouter 고정이어도 기존것을 헐겁게 해제하지 말고 새 Gemini 전용 버전 경로에서만 허용.

## 작업 2: 기존 회사 엔진 재사용 및 1회 목표 입력 흐름
- 최단 경로의 새로운 Gemini Free Company factory/store/CLI를 구성하되 Manager/Employee/Reviewer 등 **기존 코드 재사용** 우선. AI 업무 계획/품질 기준/수정 요청/최종 보고의 실제 판단을 실제 Gemini API 결과가 수행할 수 있게.
- 서로 다른 업무 단계가 선행 산출물을 인계받아야 하며 manager 검토·필요 시 수정→최종 MP4 생성·실재 파일 확인. 외부 인터넷/FFmpeg/espeak 등 **기존 로컬 도구만** 허용된 범위로 사용. 기존 로컬 툴/mock영상이 비주얼 품질을 보장하거나 AI 실사용 결과라고 과장하지 않는다.
- 영상 목표에만 맞춘 코드 하드코딩 금지. 범용 목표 흐름과 local artifact tool 계약 유지. 첫 사례는 **개인/회사 비밀 없는 합성 목표**를 사용할 수 있게 하되, AI 관리자 계획/실행 결과를 Codex가 사전 작성하지 말 것.
- 사용자 목표 입력 시 업무 내용의 중간승인·계획 수락·직원 결과 승인·매 호출마다 승인 질문을 만들지 않는다. 단, 최초 Gemini 공급자 데이터 전송 범위·모델/비용 한도·실제 사용 승인은 분명하게 분리. 최초 승인 후 범위 내 자율 운영을 목표로 하고 업무 중간 결재는 추가하지 않음.

## 작업 3: 보안/실사용 단계 게이트
- **이번 지시서 자체는 개발·오프라인 fixture 테스트를 승인하는 것이며 실제 Gemini 외부 API 요청을 승인하지 않는다.** 사전 단건 curl 인사 확인의 동의를 프로젝트 전체 호출 승인으로 확대하지 말 것.
- 일회성 테스트 파일 `data/gemini-connection-once-20261104.json`의 consumed 기록과 기존 Groq/OpenRouter 실패/예약 원장, 각 프로젝트 상태는 보존. 테스트 재실행/원장 초기화 금지. 미래에 실제 전송이 필요하다면 **신규 독립 첫 실사용 프로젝트**, Gemini 모델+endpoint+목표/데이터 전송 범위+무료 티어 검증+쿼터/호출 상한 정책을 명시한 단일 프로젝트 초기 동의/실행 절차를 준비하고 사용자에게 제시. 아직 실행하지 않는다.
- 사용자가 이미 확인한 Free tier 상태는 기록하고 실제 Google 모델 무료/제한 자료를 최신 검증하라. 알 수 없는 무료 조건으로 비용 발생 가능하다면 안전하게 멈춰라. 실제 API 요청 자동 시도 0회.
- 기존 파일/과거 백업/손상 여부·KST 시간·기존 Git 미추적 사용자 파일 보존. reset/clean/force push 금지.

## 작업 4: 완료 검증과 보고
- 오프라인 fake Gemini 200 응답(JSON text), 400/401/403/404/429/503, timeout, empty response, truncated JSON, invalid schema, safety blocks, refusal, malformed output, unknown usage를 대표적으로 검증. manager/employee 두 단계 이상→기존 로컬 도구→최종 보고 E2E fixture 검증. 기존 OpenRouter/Groq 회귀도 필요한 범위에서 수행.
- **오프라인 E2E는 실제 AI 실행 성공으로 표시하지 않음.** 성공 기준은 다음 사용자 승인과 실제 Gemini 응답을 통한 전체 협업/MP4 완주이고, 이번 작업은 그 경로의 준비 완료 및 안전한 실행 방법의 정리까지.
- `reports/v01_gemini_autonomous_company_integration_ready_20261104.md`에 변경 파일, 실제 API 호출 0회, 환경키 존재 여부만, 무료모델 확인 결과, 실제 실행 커맨드와 프로젝트 최초 승인에 필요한 구체적 단일 절차, 테스트 결과, 기존 원장 불변성, 남은 blocker를 한국어/KST로 보고. `git diff --check` 및 관련 검증 완료 후 비밀 없는 코드/테스트/보고서만 선택적 commit/push. 테스트 실패가 있으면 해결 전 push 금지.
- **기존 회사 협업 코드를 다시 만드는 대규모 리팩터링이나 장식 UI, 과도한 오프라인 진단을 자제하고 실제 AI 완주 가능성을 최우선으로 한다.**

## 수행 범위와 끝맺음
Gemini provider integration + offline workflow contract validation + **첫 실제 프로젝트 실행 전 단계까지**. 비용/데이터 외부 전송 승인 없는 live call은 하지 않는다. 완료 보고서에서 '지금 바로 무엇을 해야 1회 실제 완주하는가'를 단 한 개의 후속 명령으로 요약할 것.
