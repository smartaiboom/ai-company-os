# AI Company OS v0.1 — 개선된 모델 출력 계약으로 실제 AI 관리자 3차 개별 승인 호출 최대 1회

## 목적과 이번 사용자 승인
2026-11-03 사용자는 직전 모델 출력 계약 개선 오프라인 보고서를 확인하고 **“응 호출 승인할게 다음 진행해줘”**라고 명시적으로 **새 3차 관리자 호출 최대 1회**를 승인했다. 프로젝트 `cb44b605b498`의 사용자 승인 TASK-001 결과에 대해 범용 AI 관리자가 다음 행동을 자율 판단하고 유효한 제안을 `pending_user_decision`으로 영속 저장하는 것이 유일한 목적이다. 이번 승인은 1·2차 승인과 별개이며 재사용 불가. **외부 전송 허용 범위**는 프로젝트 목표, 관련 승인 계획·업무, 사용자 선호, TASK-001 승인 조사 결과 및 직접 후속 업무 요약에 한정한다. `openrouter/free` 단일 모델/고정 HTTPS OpenRouter만 사용, 실제 전송 최대 1회, **실패·계약 오류·타임아웃도 1회 소모, 재시도·대체 모델·추가 AI 호출 금지**. TASK-002~004 직원 실행·사용자 승인 대행·계획 변경·다른 프로젝트 AI 호출 **금지**.

`codex_tasks/README_KOREAN_LANGUAGE_RULE.md` 준수. 한국어 작업·보고, 시간은 KST(UTC+9), 기존 데이터/백업/미추적 파일/guard 보존. reset/clean/force push 금지, 불필요한 백업 생성 금지, 구조 전면 개편·UI·진단 화면·영상 전용 로직 개발 금지. `git pull --ff-only`로 최신 main을 반영하고 소스/관련 보고서를 검토한다.

## 시작 전 필수 확인 (모두 통과 전 실제 호출 금지)
- `reports/v01_real_manager_second_authorized_call_20261103.md`와 `reports/v01_manager_model_output_contract_offline_20261103.md` 및 `app.py`, `manager_decision.py`, `real_manager_second_tool.py`, `ai_safety.py`, 관련 테스트 읽기.
- 실사용 Git 제외 `data/video-real-plan-20261103/projects/cb44b605b498.json` 읽기 전용 확인: 총 **4/20**, attempts 4건 모두 completed, 관리자 attempts 정확히 2건 모두 TASK-001/openrouter/free, failed/reserved 0, manager_decisions.proposals=[] 및 answers=[], 원래 authorization 및 additional_authorizations 2차 1건, 1·2차 stopped 기록, TASK-001 완료·사용자 승인·결과 SHA-256 `95e366272746a507f26f3776db5e6e5211126ae0f1f7d2b7712a718e5cff6802`, TASK-002~004 대기·결과 없음, 관련 원본 계획/선호 불변. 첫 번째·두 번째 guard 및 관측 파일을 확인하고 보존. 다른 프로젝트 `c85d9853906a`의 불확정 예약은 절대 수정 금지.
- 현재 네트워크 호출/worker가 이미 실행 중인지 확인. 불확실하거나 예약이 있으면 **실제 전송 금지**, 읽기 전용 보고. data/backups 파일 목록·SHA-256 사전 기록. 모델·주소·키·무료-only 설정 확인(키 값 출력 금지).
- 최신 `manager_decision.py`에서 모델 출력이 정확히 **action/rationale/evidence/next_step/uncertainty/payload 여섯 필드**이며 프로그램이 `schema_version/binding/source`를 안전하게 결합하고 기존 내부 strict 검증/지문 비교를 통과시키는지 오프라인 점검. 지난 2회 실제 실패 원인을 임의로 단정하지 않는다.

## 새 3차 승인만 허용하는 최소 구현
기존 `propose_real_manager_decision_once`와 `propose_real_manager_second_authorized`의 재호출 금지 로직을 그대로 유지한다. 현재 2차 경로는 attempts=3, 추가 승인 없음일 때만 동작하므로 **기존 guard 삭제나 원장/승인 초기화로 우회하지 말 것**. 3차 개별 승인 전용 로컬 owner entrypoint(예: `propose_real_manager_third_authorized`와 단일 실행 도구)를 최소 추가하거나 기존 공통 내부 함수를 안전하게 일반화하되, 이전 두 경로의 허용 범위를 넓히지 말 것. **새 3차 승인 ID**, 사용자 승인 원문, KST 승인 시각, 프로젝트 ID, TASK-001 승인 결과·계획·입력 지문, 이전 2개 관리자 attempt ID, attempt_number=3, max_calls=1, 전송 허용 범위를 append-only `additional_authorizations` 및 history에 남긴다. 기존 1·2차 authorization/history/guard 보존. 기존 프로젝트의 새 승인 이전 상태/해시와 원장 4건을 정확히 비교해 이미 사용된 3차 승인 또는 다른 실행이 있으면 호출 전에 차단한다.

새 고유 O_EXCL guard와 Git 제외 관측 파일을 사용해 **전송 전** 최대 1회 독립 transport 카운트를 영속 기록. 기존 첫·두 번째 guard는 보존. 전송 직전 원장에 **정확히 다섯 번째 TASK-001 kind=manager_decision, model=openrouter/free, status=reserved**가 추가됐고 앞 4건이 불변인지 검증. guard만 지워도 원장·새 승인 ID·history로 중복 전송이 불가능해야 한다. 실제 호출은 기존 `request_scope`의 예약 선저장, 예산/timeout/고정 HTTPS/리다이렉트·프록시 차단/no retry 사용. worker가 timeout 후 살아 있거나 결과가 불확실하면 관측만 하고 재전송하지 않는다. 모델 action/내용을 코드에서 지정하거나 보정하지 말 것. 한국어 범용 관리자 판단만 요청. 저장 시 검증된 실제 모델 decision과 provider=`real_openrouter_free`, status=`pending_user_decision`, 새 attempt_id, 새 authorization_id, KST, 사용자 결정 대기 상태를 기존 `manager_decision_view`로 재조회. **직원 실행 및 제안 승인 금지**.

## 실제 전송 전에 반드시 오프라인 통합 테스트
임시 프로젝트/가상 키/fake transport/네트워크 차단으로 3차 신규 승인 정상 4 actions, 1·2차 원장/승인/guard 불변, 모델 여섯 필드 출력→프로그램 소유 지문 결합→기존 저장 검증→새 프로세스 조회, 3차 승인 누락/중복/guard 존재/경합/타 업무/잘못된 payload/finish_reason/예산 초과/타임아웃·실패·저장 실패, no retry, TASK-002 미실행, 다른 프로젝트 불변 검증. 기존 집중 회귀 테스트 포함. **안전성 테스트 실패나 실사용 사전조건 불일치 시 실제 호출을 수행하지 말고 보고**. 실사용 JSON/실제 키를 테스트 fixture에 사용하지 않는다. 오프라인 테스트 후 실제 호출 직전 다시 모든 사전조건을 확인한다.

## 실제 호출 1회와 결과 처리
오프라인 테스트 통과 후 새 소유자 확인 로컬 도구에서 **실제 요청 최대 1회**. 사용자 3차 승인은 이미 이 지시서에 명시되었으며 추가 승인을 임의 생성하지 말 것. API 응답을 그대로 의미 검증; 성공하면 제안 1개 영속 저장 및 `manager_decision_view` 조회, 판단 action/근거/다음 단계/불확실성을 보고서에 간략히 요약. 실패 시 원문·민감 데이터 없이 기존 `DecisionDiagnosticError`의 stage/code만 기록, 제안 0개 유지, 추가 호출 없이 중단. 완료 시 예상 **5/20, 잔여 15, attempts completed 5, reserved 0**이지만 네트워크 실패/미확정 예약/호출 전 차단은 실제 원장 기준으로 사실대로 보고. 이전 2차 4/20 기록을 절대 수정하지 말 것. Codex 세션이 중단되면 guard·원장·관측 파일을 먼저 읽기 전용 확인하고 재실행 금지.

## 결과·보존·보고
작업 후 data/backups 목록/SHA를 비교. 기존 19개 파일 중 대상 JSON만 허용된 승인/원장/제안/감사 변경, 다른 프로젝트·백업 불변. TASK-001 승인 결과/해시와 TASK-002~004 상태 불변. `reports/v01_real_manager_third_authorized_call_20261103.md` 한국어 작성: 변경 파일, 3차 승인 구별 방식, 오프라인 테스트 명령·수·결과, 실제 전송 0 또는 1회 및 KST 시작/종료, 4/20→실제 최종 예산, guard/원장/제안 조회 상태, 실제 AI가 선택한 action/근거/질문 또는 지침/불확실성의 비밀 없는 요약(성공한 경우만), 오류면 고정 stage/code, TASK-002 미실행, 보존 결과, 재시도 없음. 모델 원문 전체·API 키·실사용 JSON·비밀 로그는 Git 금지. `git diff --check` 및 집중 테스트 후 필요한 코드·테스트·보고서만 선택적 commit/push하고 원격 main 확인.

**완료 기준**: 새 사용자 승인에 따라 실제 모델 최대 1회 호출, 유효한 관리자 판단을 `pending_user_decision`으로 저장·조회하면 성공. 실패 시에도 1회 상한/예산/기존 데이터/업무 승인 경계를 지키고 안전하게 종료. 이 작업 후 진단 기능 개발로 확장하지 말고 AI 관리자→직원 협업이라는 본래 목표로 복귀.
