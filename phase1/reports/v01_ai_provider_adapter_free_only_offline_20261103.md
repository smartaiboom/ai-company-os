# AI 공급자 어댑터 경계 준비 — 오프라인·free-only 유지

2026-11-03 KST. `git pull --ff-only`로 main f479c98을 반영했다. **실제 AI API 호출 0회, 새 모델 연결 0회, 업무 실행·승인 0회**다. 실사용 사용량은 8/20 그대로다. 다중 공급자나 유료 모델의 실사용 지원을 구현·활성화한 작업이 아니다.

## 기존 호출 지점과 새 연결

| 업무 | 기존 호출 지점 | 공통 안전 경계 및 이번 연결 |
|---|---|---|
| 관리자 계획 | manager_plan._request_ai_plan → request_json(kind=plan) | 기존 계획 프롬프트·3000 토큰·응답 파싱을 유지하고 공통 경계의 어댑터를 경유 |
| 관리자 판단 | RealManagerDecisionProvider.generate → request_json(kind=manager_decision) | 4096 토큰·모델 여섯 필드·binding 결합·strict 검증 유지 |
| 직원 실행 | OpenAICompatibleExecutionEngine.execute → request_json(kind=task) | 기존 입력·previous_results·4096 토큰·결과 문자열/메타데이터 계약 유지 |
| 의미 품질 검토 | semantic_review.evaluate → request_json(kind=semantic_review) | 기존 3000 토큰·판정 계약 유지, 공통 경계만 경유 |

새 흐름은 **업무별 기존 payload → ai_safety의 정책/동의/예산/예약 → OpenRouterFreeAdapter의 Request 구성 → 기존 guarded transport → 기존 업무별 응답 검증**이다. 어댑터 자체에는 네트워크 호출·재시도·예산·동의·원장 쓰기 기능이 없다. manager_plan과 semantic_review는 직접 수정하지 않았으며 호출 지점과 공통 경유만 확인했다.

## 변경 파일

- ai_provider_adapter.py: frozen ProviderSpec, ProviderAdapter Protocol, OpenRouterFreeAdapter, 실제용 require_live_adapter, 고정 finish/transport 오류 분류 및 제한된 ResponseMetadata를 추가했다.
- ai_safety.py: 기존 모델/고정 HTTPS 검사를 그대로 두고 require_live_adapter로 무료 모델·주소·키를 추가 확인한다. 예약 이후 기존 HTTP Request 구성 부분만 어댑터로 옮겼다. 동의·원장·예산·선예약 저장·timeout·응답 크기·고정 전송·중복 키·오류 처리 및 무재시도는 기존 코드에 남겼다.
- manager_decision.py: 기존 finish != stop 검사를 공통 classify_finish_reason/FinishClass.STOP 비교로 연결했다. 모든 non-stop 응답은 기존 stage=provider_response, code=finish_reason으로 계속 거절한다. 모델 여섯 필드·strict 저장 검증을 바꾸지 않았다.
- tests/test_ai_provider_adapter.py: 실제 소비자 연결, 안전 정책 유지, 비활성 미래 metadata/mock 치환, 비민감 분류·프록시/리다이렉트 방어를 가상 데이터로 검증한다.
- tests/test_execution_engine.py: 기존 fake 응답 테스트 네 곳에 가상 키를 명시했다.
- tests/test_manager_plan.py: 기존 fake 계획 테스트 한 곳에 가상 키를 명시했다.
- 이 보고서.

현재 사용자는 실제 키 없이 호출하는 경로를 허용하지 않았다. 기존 request_json의 선택적 Authorization 구성은 키 부재를 사전에 거절하지 않았으나, 이번에는 **키가 없거나 공백이면 예약/전송 전에 거절**한다. 유효 키가 제공된 기존 요청의 URL·POST·Content-Type·Authorization·body는 동일하다. 실제 키는 테스트 fixture나 보고서에 사용하지 않았다.

## 선언과 실행 권한의 분리

ProviderSpec은 식별자, 모델, API 형식, 기본 주소, 인증 방식, 최대 출력 토큰, 비용 정책, 프로젝트 승인 필요 여부와 enabled를 담는 선언적 타입이다. 기본 enabled는 false다. 실제 제공 구현은 OpenRouterFreeAdapter 하나이고, model=openrouter/free, chat_completions, 고정 HTTPS OpenRouter, bearer, 4096 토큰, free_only를 선언한다.

**LIVE_PROVIDER_IDS는 openrouter_free 한 개뿐이며, 실제 선택 함수는 mutable registry나 환경변수의 provider metadata를 조회하지 않는다.** 임의의 ProviderSpec에 enabled=true나 유료 모델/큰 토큰 한도를 써도 실제 정책이 열리지 않는다. 실제 selector와 기존 ai_safety의 모델/주소/본문 모델 검사는 모두 단일 무료 모델만 허용한다. AI_MODEL 또는 주소를 바꿔 다른 공급자/모델로 전송할 수 없다. fallback, 재시도, 새 키·provider 연결 설정은 없다.

오프라인 mock은 같은 인터페이스의 metadata·Request 구성·응답 메타데이터 규격을 사용할 수 있다. 테스트에서 mock과 실제용 어댑터를 동일한 소비 함수에 전달해 이 작은 교체 경계를 검증했다. 그러나 mock이나 테스트 registry를 실제 selector에 등록/활성화하는 API는 없다. 다른 ID/model/주소는 not configured/disabled에 해당하는 고정 오류로 중단된다. 향후 새 어댑터 구현과 정책·승인 작업은 별도 범위다.

## 정상화·진단과 기존 실패의 의미

classify_finish_reason은 stop/length/content_filter/error/unknown으로만 분류한다. 알 수 없는 문자열·타입·제공자 원문을 결과에 반영하지 않는다. 관리자 응답 검증은 stop만 정상 후보로 받고 나머지를 계속 거절하며, 그 후 기존 JSON/한국어/payload/타깃/binding 검증을 수행한다. 중단된 응답을 정상으로 보정하지 않는다.

ResponseMetadata는 구조 추출 여부, 고정 완료 분류, 최대 262144로 제한한 content 문자 수 또는 None만 담는다. 원문·추론·임의 metadata·제공자 모델명·키를 보관하지 않고 로그도 자동 생성하지 않는다. classify_transport_error도 예외 메시지를 읽거나 반환하지 않고 TimeoutError는 timeout, 그 외는 transport로만 분류하는 최소 규격이다. 기존 업무 응답 문자열을 공통 포맷으로 재작성하지 않는다. 새 metadata 전체를 실사용 로그/이력에 추가하는 변경도 없다.

과거 8번째 관리자 호출에서 확정된 것은 **provider_response / finish_reason 검사 중단**, 실제 전송 1회·새 제안 0개라는 사실뿐이다. 당시 구체적인 finish_reason 값이나 원문은 이번 작업에 없다. 출력 길이, 필터, 모델 문제 등 특정 원인을 추측해 확정하지 않았고 과거 응답을 복원하지 않았다. 이번 분류기를 과거 실패의 구체 원인이 밝혀진 것으로 표현하지 않는다.

## 테스트 명령과 실제 결과

1. `python -B -m unittest tests.test_ai_provider_adapter tests.test_execution_engine tests.test_manager_model_output_contract tests.test_real_ai_safety_budget tests.test_manager_plan > /tmp/provider-adapter-first-tests.log 2>&1` → **77개 실행, 오류 5건**. 새 키 필수 조건에 맞지 않는 기존 가짜 응답 fixture 다섯 곳을 확인했다.
2. 해당 fixture에 가상 키를 명시하고 관리자/직원 공통 어댑터 소비 테스트를 추가한 뒤 같은 명령을 `/tmp/provider-adapter-second-tests.log`로 실행 → **90개 통과**, 실패·오류 0(2.953초).
3. 확장 집중 명령 `python -B /tmp/run_provider_adapter_tests.py > /tmp/provider-adapter-focused-tests.log 2>&1` → **313개 실행, 실패 1건**. 새 프록시 테스트가 기존 fixture의 guarded_urlopen 차단 mock을 호출한 테스트 구성 오류였다. 실제 네트워크는 열리지 않았다. 테스트용 원래 함수 참조를 명시하고 build_opener를 가짜 객체로 교체해 검증하도록 수정했다.
4. 같은 확장 집중 실행을 `/tmp/provider-adapter-final-tests.log`로 재실행 → **313개 모두 통과**, 실패·오류 0(23.953초).

/tmp/run_provider_adapter_tests.py는 임시 서명키 경로 아래 다음 unittest 대상을 실행한다.

`tests.test_ai_provider_adapter tests.test_execution_engine tests.test_manager_plan tests.test_manager_model_output_contract tests.test_manager_pending_review tests.test_real_manager_decision tests.test_real_manager_second_authorized tests.test_real_manager_third_authorized tests.test_real_manager_review_once tests.test_real_manager_approved_task002 tests.test_real_task002_once tests.test_accept_review_task002 tests.test_real_ai_safety_budget tests.test_project_budget tests.test_semantic_review_integration.SemanticIntegrationTests`

수는 fixture import/상속에 따른 반복 사례를 포함한 unittest 실제 실행 수다. 전체 테스트와 HTTP socket 통합 클래스는 실행하지 않았다. 가상 프로젝트·가상 키·fake transport 및 네트워크 차단을 사용하며, 테스트의 서명키는 임시 경로로 격리했다. 실제 AI 호출이나 실사용 JSON fixture 사용은 없다. 최종 미해결 실패는 없다.

다음 경계를 확인했다.

- 관리자 모델과 직원 모델이 같은 require_live_adapter를 실제로 사용하는 최소 연결, 기존 요청 URL/헤더/body/토큰 상한과 KST 예약·완료 원장 유지.
- 현재 어댑터와 오프라인 mock 치환 가능성, 미래 enabled=true 선언 및 mock registry에 유료 모델을 넣어도 실제 selector/request_json이 전송·사용량·예약 쓰기 전에 거절.
- 유료/알 수 없는/누락 모델, HTTP/다른 HTTPS endpoint, 키 누락, 잘못된 JSON/schema/본문 모델, 출력 한도 초과 시 무전송·원장/프로젝트 불변.
- 프록시 환경변수 무시·빈 ProxyHandler·리다이렉트 차단, 기존 timeout·전송 실패·응답 크기·JSON·선예약·무재시도·예산 보호.
- 관리자 six-field 계약과 모든 non-stop 완료 분류 거절, 비민감 진단에 임의 문자열/원문이 섞이지 않음.
- 기존 1~3차 관리자·pending review·승인 결과 후속 판단·직원 단일 호출·사용자 결과 승인·의미 검토·예산 관련 회귀.

## 실사용 데이터 보존

사전 data/backups **27개** 및 기존 미추적 파일 6개, 총 **33개** 목록과 SHA-256을 기록했다. 사후 목록·SHA가 모두 일치한다. 다른 프로젝트 c85d9853906a의 미확정 예약, 모든 기존 guard·관측·백업도 포함한다. 이번에는 data/backup/guard/서명키 파일을 생성하거나 삭제하지 않았다.

프로젝트 cb44b605b498는 **8/20, completed 8, failed/reserved 0, 잔여 12** 그대로다. TASK-001/002 완료·approved, TASK-003/004 대기·결과 없음, 기존 제안 2개와 마지막 finish_reason 중단 기록 및 승인 원문·원장·동의·미승인 기준 초안은 불변이다. 기존 실패 승인을 재사용하지 않았다. 과거 호출의 completed 원장은 관리자 계약 성공을 뜻하지 않는다.

## 향후 다른 모델 활성화 전에 필요한 별도 작업

다음은 이번에 구현하거나 활성화한 기능이 아니라, 향후 사용자 명시 승인과 정책 변경 전에 확인할 항목이다.

- 공급자·모델·endpoint·프로젝트별 허용 목록과 전송 가능한 자료 범위에 대한 명시 승인. 현재 free-only 지침을 유지한 채 metadata만 바꿔 활성화할 수 없다.
- 유료 사용이라면 과금 동의, 단가 확인, 요청/프로젝트/기간 비용 상한 및 초과 차단 설계. 현재 20회 예산은 호출 횟수이며 금액 상한이 아니다.
- 공급자별 API 형식·인증·모델별 프롬프트/JSON/finish_reason/도구 응답 계약·출력 한도·한국어/행동 의미·문서 문자열 호환성 검증.
- 새 키의 안전한 저장·권한·회수·로그 비노출, 데이터 보존/외부 전송 조건, 고정 HTTPS와 redirect/proxy 정책 검토.
- timeout의 적용 단위와 전체 처리 시간 한계, 불확실 예약 처리, 재시도/중복 청구 방지, 감사·원장 단위와 실패 시 안전 중단 검증.
- 가짜 transport로 선행 회귀를 통과한 뒤 별도 사용자 승인에 한해서만 제한된 실제 연결 검증. 새로운 모델의 품질/안정성을 이번 오프라인 테스트로 보장하지 않는다.

현재 실제 사용 가능한 공급자는 여전히 OpenRouter의 openrouter/free 하나다. **다음 실사용 재호출도 새 사용자 승인이 필요하다.** TASK-003을 실행하거나 다른 AI/유료 모델 연결로 확장하지 않고 종료한다.

최종 `git diff --check` 통과, 보고서 저장·재읽기 검증 및 실사용 전체 해시 비교를 완료했다. 원격 main을 확인하고 이번 코드·테스트·보고서 7개만 선택적으로 커밋·푸시한다. 실사용 JSON·대본·키·모델 원문·민감 로그는 포함하지 않는다.
