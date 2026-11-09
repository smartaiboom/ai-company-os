# AI Company OS v0.1 — AI 공급자 교체 가능한 연결 경계 준비 (오프라인, 기존 free-only 불변)

## 사용자 의도
2026-11-03 사용자: “또다시 개발이 멈췄는데 어쩔수 없지. 그리고 향후 ai는 openrouter/free 가 아닌 다른걸로 변경 가능하지? openrouter/free는 오류가 많은거 같아”, 이어 “그래 그렇게 하자 다음 진행해줘”. 사용자와 합의한 방향은 **기존 업무 흐름은 보존하고, 향후 다른 AI 공급자/모델을 쉽게 연결할 수 있도록 인터페이스를 먼저 마련**하되 **지금은 실사용 `openrouter/free`만 허용**, 새 모델/유료 사용은 향후 별도 명시 승인으로만 활성화하는 것이다.

**이번 작업은 코드 최소 개선과 오프라인 테스트만. 실제 AI API 호출 0회, 새로운 모델 호출 0회, TASK-003/004 실행·승인 0회, 기존 실패 승인 재사용 0회, 사용량 8/20 유지.** 실제 모델 선택이나 재호출, 유료 비용, API 키 생성/연결, 새 provider 사용은 사용자가 승인한 바 없다. 특히 현재 마지막 관리자 호출은 `stage=provider_response, error_code=finish_reason`이었고 8번째 시도가 소모되어 새 판단이 저장되지 않았다. 실패 원인과 원문은 확정하지 말고 출력 길이 등을 추측 사실로 설명하지 말 것.

`git pull --ff-only` 후 `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`, `reports/v01_real_manager_approved_task002_next_decision_once_20261103.md`, `ai_safety.py`, `execution_engine.py`, `manager_decision.py`, `manager_plan.py`, `app.py`, `project_budget.py`, 기존 관련 테스트를 먼저 점검. KST UTC+9, 한국어 보고·지시, 기존 파일·백업·미추적·실사용 데이터 보존. git reset/clean/force push 금지. 하루 백업 1개 이하 원칙 유지, 이번에 불필요한 백업 생성 금지.

## 설계 목표: 모델 연결과 안전 정책을 분리하되 잠금 해제하지 않는다
1. 실제 코드에는 `ai_safety.MODEL="openrouter/free"`, `BASE_URL="https://openrouter.ai/api/v1"` 고정 검증이 있고 `execution_engine.OpenAICompatibleExecutionEngine`, `manager_decision.RealManagerDecisionProvider` 등이 `ai_safety.request_json`을 공유한다. 이 안전 경계를 **완화·우회하지 말 것**. 먼저 실제 호출 지점과 `manager_plan` 호출 지점을 목록화해 보고서에 정리.
2. **좁은 공통 공급자 정의/adapter interface**를 구성한다. 미래 provider에 필요한 선언적 metadata(식별자, 모델명, API 형식, endpoint, 인증 방식, 출력 제한, 비용/승인 요구 등)와 응답 정규화/오류 분류 규격을 **비활성 계획/타입 또는 오프라인 mock 구현**으로 분리한다. 모든 작업 종류(관리자 계획·관리자 판단·직원 실행)가 미래에 같은 인터페이스를 활용할 수 있도록 방향을 잡되, 이번에는 위험한 전면 리팩터링을 하지 않는다. **정책 엔진에서 동의/원장/예산/선예약/재시도 금지/고정 HTTPS 검증을 수행**하도록 유지한다. 새 provider metadata를 선언했다고 자동 전송 가능하게 만들지 않는다. 허용 모델 선택 동작은 현재 반드시 단일 free-only 목록뿐, `AI_MODEL` 또는 환경변수 변경만으로 다른 모델 사용 불가.
3. 안전한 정상화/진단 함수(가능한 경우)에는 **finish_reason 분류**(stop=정상, length/content_filter/error/unknown=중단 등)와 제한된 비민감 메타데이터만 다루는 정책을 정리. 실제 `manager_decision.validate_provider_response`는 현재 stop이 아닐 때 strict 거부하므로 **기존 동작 유지**. 중단된 응답을 성공으로 보정·저장하거나 provider response 전체를 로그에 남기지 않는다. 특히 이전 실패의 구체 finish_reason은 추후 관측으로만 알 수 있고 **과거 원문을 복원한다고 주장 금지**. 안전한 진단 개선이 꼭 필요하고 기존 테스트가 있다면 내부 계약 호환 방식으로만 구현. 출력 토큰 한도 증가나 재시도 활성화 금지.
4. 적은 변경으로 기존 함수들이 공통 추상화를 실제 사용할 가치가 명확하다면 `openrouter/free` 어댑터 하나를 기존 `request_json` 아래/옆에 얇게 추출하고 적어도 **관리자 모델·직원 모델이 동일한 어댑터의 free-only 모델 정책을 확인**하도록 연결. `manager_plan`까지 넓게 바꾸면 위험하면 이번에는 호출 지점 문서화만 하고 실제 코드 리팩터링을 다음 단계로 분리. 방대한 코드 교체보다 **하나의 안전한 경계가 실제로 재사용되는 최소 수직 슬라이스**가 우선. mock 기반 교체 가능성 확인, 실사용 허용 provider는 하나만. 가능하면 provider-neutral 실패 유형/결과 규격은 외부 AI 호출 직전/후에만 적용하며 원장/기존 프롬프트/문서 생성 결과의 문자열·메타데이터 계약은 바꾸지 않는다.
5. 미래 제공자 지원은 별도 승인 없이는 `not configured/disabled`로 fail-closed. 향후 유료/추가 공급자를 지원할 때 필수인 프로젝트별 provider/model whitelist, 비용 상한 및 과금 동의, 모델별 프롬프트·응답 규격, 예산 단위(현재 20회는 호출 횟수이지 유료 비용 상한 아님), 데이터 전송 범위, 비밀 관리, timeout과 불확실 예약 처리 체크리스트를 **보고서에** 제시. 실제 지원 코드/키·설정을 이번에 활성화하지 말 것.

## 테스트/보존
- 임시 가상 프로젝트·fake transport·네트워크 차단. 기존 `openrouter/free` 요청 모양/고정 HTTPS/헤더·출력 토큰·예산·KST·선예약·무재시도·원장 저장 검증; 관리자 판단의 strict six-field / finish_reason non-stop rejection 유지; 직원 실행기 결과 계약 및 별도 관리자 업무 연결 보존.
- 미래 provider 또는 유료 모델 ID를 공급자 adapter/mock registry에 넣어도 실사용 `ai_safety.request_json`이 **외부 전송 전에 거부**해야 하며 프로젝트 사용량/키/원장이 변경되면 안 된다. endpoint redirect/proxy 우회·알 수 없는 모델·누락된 키/잘못된 schema·전송 실패/timeout에 fail-closed. API 키 값/실사용 JSON/모델 원문은 테스트 fixture/로그/보고서에 금지.
- 단순 디자인 문서만 만들고 끝내지 말 것: **작은 실제 코드 추출 또는 연결 + 이를 통과하는 집중 테스트**를 남길 것. 동시에 모델 다중 연결·유료 지원을 구현했다고 주장하지 말 것.
- 실사용 프로젝트 `cb44b605b498`: 8/20, completed 8, 실패·예약 0, 8번째 관리자 응답 finish_reason 검증 중단/제안 없음, TASK-001/002 approved, TASK-003/004 대기. 다른 프로젝트 `c85d9853906a` 미확정 예약 및 기존 승인·guard·관측·백업 불변. 사전/사후 data/backups 파일 목록·SHA 모두 같아야 함. 테스트가 서명키 등 파일을 생성하지 않도록 임시경로 격리. 사용자 동의 또는 원장 수정 불가.
- 기존 실행기/안전 예산/관리자 response 계약/real owner 호출 게이트 관련 집중 unittest 실행. HTTP socket 통합 테스트가 환경에서 거부되면 실패를 숨기지 않고 실제 호출과 관계 없는 테스트를 분리해 보고하거나 안전한 격리 환경에서 다시 실행. 전체 테스트 필요 없다면 생략 범위 보고.

## 보고서
`reports/v01_ai_provider_adapter_free_only_offline_20261103.md` 작성: 기존 호출 지점과 새 구조, 변경 파일·테스트 명령·수·결과, 기존 openrouter/free 호출이 여전히 안전하게 지원되는 방식, 미래 모델은 **차단**됨을 증명, finish_reason 기존 실패 원인에 대해 확인된 것/확인 안 된 것 구분, 향후 모델 활성화에 필요한 사용자 승인·비용/보안/호환성 체크리스트, 실사용 8/20 및 승인/업무/backup 불변 기록. `git diff --check`, 필요한 코드/테스트/보고서만 commit/push, 원격 main 확인. 외부 AI 호출/새 모델 연결/TASK-003 실행은 절대 하지 말 것.

**완료 기준**: AI Company OS의 기존 호출/업무 흐름을 망가뜨리지 않고 공급자 교체를 위한 작고 실제로 검증된 인터페이스가 생김. openrouter/free만 여전히 실제로 허용되며, 다음 실사용 재호출은 별도 사용자 승인이 있어야 함.
