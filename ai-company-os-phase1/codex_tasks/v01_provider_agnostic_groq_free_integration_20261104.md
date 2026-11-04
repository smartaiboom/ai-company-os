# AI Company OS — 공급자 교체 가능한 연결 구조 + Groq 무료 모델 첫 통합 (실전 테스트 준비)

작성: 2026-11-04 KST. 사용자의 결정: “OpenRouter에만 의존하지 말고 Groq를 먼저 연결하고, Gemini는 후속 대안으로 유지하자. 무료로 AI 회사 한 사이클을 완성하는 것이 우선.” **이번 요청은 연결 코드 개발과 오프라인 시험을 수행하라는 동의다. Groq 계정에 새로운 API 키 등록이나 외부로 목표/직원 작업을 실제 전송하는 데 대한 프로젝트 단위 운영 동의로 해석하지 말 것.** 따라서 이 지시서의 실제 Groq API 요청은 0회, 운영 approve/run 0회.

## 우선 읽을 문서
`AI_COMPANY_OS_CORE_PRINCIPLES.md`, `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`, `PROJECT_HANDOFF_20261103.md`, `reports/v01_real_free_ai_video_one_cycle_20261104.md`, `reports/v01_real_free_provider_response_recovery_20261104.md`, `reports/v01_real_free_autonomous_video_smoke_prepare_20261103.md`, `codex_tasks/v01_practical_second_video_trial_prepare_20261104.md` 및 관련 provider/role/consent/ledger/local_artifacts 코드를 충분히 검토한다. 마지막 지시서가 이미 사용자 Codex에서 실행되어 새 프로젝트를 만들었을 수도 있으니 먼저 상태 확인, 중복 작업 금지.

**불변 제품 목표:** 사용자는 목표를 한번 주고, 실제 AI 관리자가 계획/기준/업무 분배/직원 결과 검토·수정·전달/최종 통합하며 실제 직원들이 수행해 **MP4**를 결과로 제공한다. Codex는 개발자다. 사업 판단을 하드코딩하거나 사용자에게 업무 결재를 반복시키지 않는다. 현황판은 실제 AI 한 사이클 완주 후 개발.

## 이번 범위의 달성 목표
1. 기존 OpenRouter-only 결합을 최소한으로 분리해 **OpenAI-compatible provider 교체 계층**(또는 기존 코드에서 재사용 가능한 명확한 adapter API)을 구성한다. 처음에는 OpenRouter 기존 free-v2 경로를 완전히 보존하고, 신규 Groq free-v2 isolated 경로를 추가한다. Gemini는 추후 별도 adapter 장착할 수 있는 인터페이스만 확보하고 **Gemini API 구현·호출은 이번에 하지 않는다**. provider/model/endpoint/key와 consent, request payload, response normalization, cost/무료 정책, 오류 진단, request/operation hashes 모두 provider별로 명확히 분리한다. 한 프로젝트 승인 중에는 모델/공급자 전환 금지. 구 free-v2 승인/원장 보존. 최소 범위 변경 우선; 방대한 재설계 대신 첫 실전 경로 완성.
2. Groq 공식 API 호환 문서 기준: `https://api.groq.com/openai/v1/chat/completions` (고정 HTTPS), API 키 `GROQ_API_KEY` 등 별도 안전 저장, 모델 후보 `openai/gpt-oss-20b` 또는 `openai/gpt-oss-120b` **1개를 정확히 명시**. `openai/gpt-oss-20b`은 OpenAI 공식 유료 API가 아니라 Groq가 제공하는 GPT-OSS 모델. 토큰/요금/무료 한도는 계정/모델 정책에 따라 달라지니 계정의 실제 Free plan과 결제 연결/과금 설정을 확인하기 전 live 기능 활성화 금지.
3. Groq 공식 안내는 OpenAI API와 '대체로' 호환이며 1:1 동일하지 않다. 특히 기존 OpenRouter `provider.max_price`, `allow_fallbacks`, `usage.cost` 등 **Groq에서 지원하지 않거나 기본 제공을 보장하지 않는 필드를 그대로 전송하거나 0 비용 검증으로 잘못 적용하면 안 된다**. 무료 등급·계정·모델 이용 및 무결제 상태는 공급자별 별도 계약/사전 정책과 사용량/요금 기록으로 확인. 실제 API 응답이 cost 필드를 제공하지 않는다고 Groq를 '무료 보장'으로 임의 단정하지 말고, 실행 전 무료 계정/청구 상태가 불명확하면 송신 차단 및 요구사항을 보고한다. 유료 fallback, 결제, 비용 불확실한 자동 재시도 금지.
4. Groq 공식 문서는 `openai/gpt-oss-20b`/120b의 **Structured Outputs strict JSON Schema 지원**, `response_format=json_object` 지원을 안내한다. 현행 관리자 계획/직원 결과/검토/통합 역할 출력에 필요한 JSON 계약을 검사하고, 실제 지원되는 모델에만 strict schema(모든 필드 required / 각 object additionalProperties=false 등)를 사용하도록 구현·검증한다. 모델별 지원 차이가 있으면 공급자별 JSON mode를 선택; 자의적 파서 완화/불완전 결과 수락 금지. 모델 원문·비밀키/인증 헤더 로깅 금지. finish_reason/usage/응답 메타데이터 diagnostics는 유한 allowlist, KST, 실제 오류와 mock을 분리한다.
5. **공급자 본래 무료 쿼터/속도 제한 반영:** Free tier의 429 및 Retry-After 처리, 사용량·잔여 제한 헤더가 존재할 경우 개인정보 없는 숫자만 기록, 동의 유효기간·중복 호출/예약/불확실한 응답·30분 벽시계 보호. OpenRouter free-v2의 인위적 2/20 호출 상한 제거 정책은 새로운 Groq 무료에서도 합리적으로 유지하되 provider rate limits와 자원 상한 엄수. 현재 사용자 승인 없이 유료 API를 연결하지 않는다.
6. **새 자율 영상 시험 준비:** 기존 실제 실패 프로젝트 `freecompany-ae4aa334511d470c8c517685e9902a53`는 `completed_unvalidated_legacy / blocked_pending_audit`, 원래 승인/원장/active_operation을 그대로 보존. `cb44b605b498` 수동 프로젝트 9/20, `c85d9853906a` reserved 1, 다른 사용자 데이터/백업/미추적 파일 모두 불변. 기존 video mock MP4 보존. 신규 Groq 전용 store/프로젝트를 **정확히 하나** 만들거나, 현행 구조가 그 단계까지 안전히 구현되지 않았으면 그렇게 보고한다. 목표는 “ChatGPT 초보자를 위한 좋은 질문 작성법을 알려주는 한국어 20~30초 MP4 영상, 자막 포함, 로컬 한국어 음성 가능하면 포함, 최종 파일과 제작 보고서.” Groq용 첫 운영 동의안 prepare까지만 만든다. Groq project_id, goal/state hash, 운영 제안 review hash, 모델, 외부 송신 가능한 새 프로젝트 텍스트와 로컬 render 메타데이터, 승인된 로컬 도구 범위, grant 유효기간 등을 보고. 기존 OpenRouter consent/key로 Groq 프로젝트에 대한 암묵적 승인 금지.
7. **오프라인 종단간 검증:** fake Groq HTTPS에서 plan→실제와 동일 역할 메시지→AI worker 2명 이상의 선행 전달→관리자 검토·필요시 수정→로컬 ffmpeg 자막 MP4 생성/ffprobe→최종 파일/원장 기록까지 **CLI run 한 번**으로 검증. 모의 데이터인 점을 파일/보고에 분명히 표시. strict JSON/비정상 finish reason/거절/429/402·결제 필요/유효하지 않은 키·모델·schema/비용 조건 차단/크래시와 중복 방지/계약 범위 확대 거절 등 중요한 안전 케이스. 기존 OpenRouter 22 fake calls, 기존 mock MP4 및 legacy 2/20 회귀 유지. 실제 Groq/OpenRouter/Gemini AI API 요청 **0회**. 외부 API 검증이라며 ping 호출하거나 사용자 키를 요청 전체에 남기지 않는다. 로컬 장치/패키지 설치는 기존 사용자 승인 범위의 무료 오픈소스만.
8. **사용자 키 준비 절차:** 실사용은 Groq 계정/API 키(해당 Codespaces의 안전한 환경변수/Secrets로만), Free tier/과금 금지 확인과 최초 프로젝트 운영 동의가 필요하다. 현재 Groq 계정/키가 없으면 **Codex가 키를 생성하거나 사용자 대신 로그인할 수 없으므로**, 정확한 공식 URL과 최소한의 안전한 설정 방법을 보고한다. Git/.env 보고서에 키를 복사하지 않는다. 사용자에게 다른 provider의 계정 정보를 묻거나 OpenRouter 키를 Groq용으로 재사용하지 않는다.
9. **결과 보고서:** `reports/v01_provider_agnostic_groq_free_integration_20261104.md`에 (가) 변경 코드/공급자 인터페이스, (나) 선택 모델/공식 무료 정책과 구조화 JSON 적합성, (다) fake Groq 실제 MP4 생성 여부 및 기술 메타데이터, (라) 전체 회귀, (마) 새 store ID/해시/제안 만료/미승인 상태, (바) 키/실사용 전제 조건과 사용자에게 필요한 **단 한 번의 최초 Groq 운영 동의**, (사) 실제 요청 0회, 기존 원장/사용자 데이터 SHA 보존 기록, (아) 다음 실전 명령만 명확히 기록. `git diff --check` 후 코드/테스트/보고서만 선택적 commit/push. 모든 KST, 보고 한국어.

## 공식 개발 참고 (브라우징은 개발 중 필요할 때만)
- https://console.groq.com/docs/openai
- https://console.groq.com/docs/structured-outputs
- https://console.groq.com/docs/rate-limits
- https://console.groq.com/docs/api-reference
- https://console.groq.com/keys

## 금지 사항
이번 작업에서 **실제 AI 제공자 호출/유료 결제/데이터 전송 승인 생성/owner-confirmed/실사용 run 실행 금지**. 무료 오픈소스 설치 승인과 Groq 통합 개발 지시는 실제 Groq 외부 전송 동의가 아니다. 기존 파일 삭제·reset/clean/force push·기존 권한 계약 무단 변경 금지. 문제를 단순 코드/테스트 숫자로 포장하지 말고, 실제 한 사이클로 갈 수 있는 준비 경로를 완성하는 데 집중.

**완료 기준:** 기존 자율 엔진/실사용 프로젝트는 안전히 유지하고, Groq 무료 모델 고정 provider 교체와 구조화 응답 대응이 fake HTTPS/로컬 실물 MP4 통합으로 검증되며, Groq 신규 프로젝트의 **실사용 최초 운영 동의 직전 상태**까지 준비된다. 이번 작업의 영상/mock 성공을 실제 Groq 영상 제작 성공으로 표현하지 않는다.
