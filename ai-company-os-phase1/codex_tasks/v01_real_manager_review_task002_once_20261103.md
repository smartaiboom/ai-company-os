# AI Company OS v0.1 — TASK-002 미승인 결과 실제 AI 관리자 검토 최대 1회

## 사용자 개별 승인과 정확한 범위
2026-11-03 사용자 명시 원문:
> “프로젝트 cb44b605b498의 TASK-002 대본에 대한 실제 AI 관리자 검토 호출 최대 1회를 승인합니다. 기존 보안·예산 원칙을 지키고 관리자 판단만 저장하며 직원 수정이나 TASK-003/004는 실행하지 않도록 Codex 지시서를 GitHub에 작성해 줘.”

이번 동의는 **프로젝트 cb44b605b498의 TASK-002 결과에 대해 실제 AI 관리자(openrouter/free) 검토 요청 최대 1회**만 허용한다. 사용자가 승인한 계획·목표, TASK-002 실제 대본, 사용자 선호, 관련 승인 TASK-001 조사 결과, 사용자 승인된 기존 AI 관리자 지침, 직접 후속 업무, 호출 예산 요약을 검토에 필요한 최소 범위로 전송할 수 있다. 전송 전 정확한 필드/내용·민감정보 노출 가능성을 검토하고 승인 범위 외 필드는 보내지 않는다. 이 승인은 직원 결과 승인, 대본 수정/재생성, TASK-003/004 실행, 관리자 판단 수락, 추가 AI 호출, 예산 증액에 대한 승인이 **아니다**.

**절대 금지**: TASK-002 사용자 승인/검토 상태 변경/대본 변경/직원 재호출, TASK-003/004 실행, 추가 관리자 호출, TASK-001 재호출, 전체 workflow 자동 시작/재개, 실제 호출 재시도, 타 프로젝트 호출, 유료·대체 모델, 검토 행동 `request_revision` 강제. 모델이 어떤 행동을 선택할지는 전적으로 모델 판단에 맡긴다. 유효한 관리자 제안 1개만 `pending_user_decision`으로 저장하고 종료. 실패/미확정 시 재전송 금지.

`git pull --ff-only` 후 `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`, `reports/v01_manager_review_pending_employee_result_offline_20261103.md`, `reports/v01_manager_proceed_approved_task002_real_once_20261103.md`, `manager_decision.py`, `app.py`, `ai_safety.py`, `real_manager_third_tool.py`, `real_task002_once_tool.py`와 관련 tests를 먼저 읽는다. 한국어 지시/보고, KST(+09:00), 최소 수정·집중 테스트, 원본 코드/실사용 데이터/백업/미추적 파일 보존, git reset/clean/force push 금지. 불필요한 재설계·영상 전용 규칙/고정 판단 금지.

## 필수 사전조건: 하나라도 불일치하면 실제 호출하지 말 것
- 실사용 Git 제외 `data/video-real-plan-20261103/projects/cb44b605b498.json` 현재 원장 **6/20**, attempts 6건 모두 completed, failed/reserved 0, 잔여 14. 기존 TASK-001 실제 관리자 3회(앞의 실패 2건 포함), TASK-002 실제 직원 1회 및 이전 원장·동의·guard·관측 모두 보존. 다른 프로젝트 `c85d9853906a`의 미확정 예약에 접근하거나 변경하지 말 것.
- 승인 계획·목표·선호 불변, TASK-001 완료·approved 및 SHA-256 `95e366272746a507f26f3776db5e6e5211126ae0f1f7d2b7712a718e5cff6802`; TASK-002 **완료·review_status=pending**, 결과 SHA-256 `2276736d569a6e6cb34af05a4ac44e386d5a087ebd82f82dd59304c8bf0904ae`, 기존 결과 원문은 실사용 JSON에서만 읽고 Git/보고서에 전체 복사 금지. TASK-003/004 대기·결과 없음.
- 기존 실제 관리자 TASK-001 proceed 제안 ID `2d62725cfe374852b916b5bd20af67ac` 사용자 승인됨, TASK-002 후속 입력에 연결된 실제 관리자 guidance 보존. TASK-002에 대한 **기존 review 목적 제안이 없어야** 한다. `_manager_review_input(project, "TASK-002")`가 `purpose=employee_result_review`로 정상 생성되고 현재 지문이 승인 계획·대본·pending 상태에 결합되어야 한다. 대상 결과가 이미 승인/수정됐거나 중복 제안이 있다면 중단.
- 현재 사용자의 이번 승인 문장과 전송 범위를 별도 **고유 단일 사용 승인 ID**, KST, 프로젝트/TASK-002, review 목적, 결과·계획·선행 결과 binding, 프로젝트 최신 지문, model=`openrouter/free`, max_calls=1, 허용 전송 필드, 이전 6건 attempt ID와 함께 영속 감사 기록. 이전 관리자 1~3차 승인이나 직원 승인 재사용 금지. 사용자 원문을 동의 근거로만 기록하고 재실행 시 사용한 승인은 다시 사용할 수 없게 한다.
- 실행 중 worker/기존 미확정 예약/동시 mutation 검사, data/backups·기존 guard·미추적 파일 사전 SHA·목록 확보. `AI_MODEL=openrouter/free`, 고정 HTTPS `https://openrouter.ai/api/v1`, 키 존재만 확인하고 값 비출력. `AI_REAL_REQUESTS_ENABLED=1`은 승인된 **실제 실행 프로세스**에서만 사용. 기존 무료-only, 기본 예산 20, 시작당 최대 2, 요청당 한 번, 90초 이하 제한/기존 설정, 예약 선저장, 무재시도, 프록시/리다이렉트 차단, 응답 크기·모델 계약 유지.

## 구현 — 기존 범용 오프라인 review 경로를 최소한으로 실제 모델에 연결
1. `app._manager_review_input` / `manager_decision.employee_review_input` / `RealManagerDecisionProvider.generate` / `validate_provider_response` / `_proposal_context` / `manager_decision_view`의 기존 로직을 **그대로 최대한 재사용**한다. 기존 `propose_employee_result_review_offline`은 mock-only 유지하고 실사용 mock 저장/가짜 응답 주입 금지. 새로운 **로컬 owner 전용** 단일 실행 진입점/도구를 마련하되 HTTP, UI 자동 호출, worker 후속 실행, 반복 스케줄, 일반적인 무제한 실사용 관리자 호출 허용 금지.
2. 새 승인·실사용 현재 지문 검증, 정확히 6건 이전 원장 불변 확인, 독립 O_EXCL guard와 Git 제외 관측 파일 생성, transport 카운트 **실제 전송 전에 fsync**, `request_json` 내부 원장 **정확한 7번째** TASK-002/`manager_decision`/`openrouter/free` 예약 선저장 확인 후 전송 1회. 가능한 경우 기존 real_manager 단일 실행 도구의 안전한 패턴을 복제하되 승인 조건은 TASK-002 review 전용으로 독립. guard 삭제해도 사용된 승인/원장/제안 이력 때문에 재사용 불가능해야 함.
3. 기존 model-only 6필드 `action,rationale,evidence,next_step,uncertainty,payload` 출력 계약을 유지하고, 프로그램 소유 목적·binding·metadata를 붙여 strict 검증. `proceed`, `ask_user`, `request_revision`, `propose_plan_change` 중 모델이 실제 선택한 1개를 원문 의미 보존하여 `purpose=employee_result_review`, `provider=real_openrouter_free`, `status=pending_user_decision`으로 저장. **수정 지시를 실제로 수행하거나 결과 승인/계획 변경을 적용하지 말 것.** 모델이 품질 문제를 발견하지 못해도 강제로 request_revision으로 바꾸지 말 것. JSON/finish_reason/contract 오류는 고정 단계·코드로만 보고하고 응답 원문/키/프롬프트 전체 저장 금지.
4. 동시 저장 경쟁을 검증하고 변경된 프로젝트에 오래된 검토 제안을 덮어쓰지 않는다. 기존 approved TASK-001→TASK-002 proceed는 불변, TASK-002 pending 유지, `require_proceed`가 review 제안만으로 TASK-003을 열지 못하는 기존 보안 경계 유지. timeout 이후 원격 요청이 살아 있거나 원장 예약이 남았으면 확인 없이 재시도하지 말 것. 실패/미확정도 호출 시도 횟수에 포함.
5. 새 호출 1회 성공 시 예상 원장 **6/20→7/20, 잔여 13**, completed 7/failed 0/reserved 0. 호출하지 못했으면 6/20 유지, 전송 실패/미확정 시 실제 ledger 상태 그대로 보고. 사용자 승인/관리자 판단은 혼동하지 않는다.

## 오프라인 선행 테스트 (실제 전송 전에 모두 통과)
- 임시 가상 프로젝트, 가상 키, fake transport, socket 차단. **새 승인 한 번만**, 승인 없는 요청/다른 프로젝트/다른 TASK/목적 불일치/중복 승인/guard/중복 전송/이전 6건 원장 불일치/미확정 예약/예산 초과/결과 지문·계획·선행 결과·검토 상태 변경/제안 저장 경쟁/응답 오류/timeout에 대해 재호출 없이 차단. 최초 승인 기록 후 전송 전 실패도 재사용 불가.
- 실제 관리자 모델의 여섯 필드 계약과 네 행동 모두 fake 응답으로 검증, 새 프로그램 binding·목적·결과 hash가 재조회에서 일치, `manager_decision_view`에서 새 제안 stale=false 및 pending_user_decision. 기존 관리자 proceed 승인 유지, TASK-002 결과·pending 그대로, TASK-003/004 실행 차단, 결과 수정·자동 승인 0회, 기존 guard/백업/다른 프로젝트 불변.
- 기존 관리자 1~3차 실제 단일 호출 경계, TASK-002 실제 직원 단일 호출 경계, pending review offline, budget/ai_safety 집중 회귀 테스트. 테스트는 **실사용 JSON·실제 키를 fixture로 사용하지 말 것**. 실제 호출 전에 테스트 완료, 실패하면 호출하지 말 것.

## 보고와 완료
`reports/v01_real_manager_review_task002_once_20261103.md`에 한국어로 사전조건, 승인 ID/시각 KST, 전송 허용 범위(비밀값 없이), 테스트 명령·통과 수·실패, 실제 전송 0/1회·시간·재시도, 예산 6→실제 상태, guard/관측/원장, **실제 AI 관리자 행동 및 판단 근거·구체적인 수정 의견/질문/다음 단계(있으면)**, 제안 ID·pending_user_decision·stale, TASK-002 원문/검토 상태 보존 및 TASK-003/004 미실행, 다른 프로젝트·백업 SHA 불변을 기재. 모델 주장과 독립 검증 사실 구별. 보고서에는 API 키·전체 대본·실사용 JSON·모델 원문 전체·민감 로그를 포함하지 않는다.

`git diff --check` 및 집중 테스트 완료 후 필요한 코드/테스트/보고서만 선택적으로 commit/push, 원격 main 확인. 기존 파일 삭제/백업 추가·삭제 금지. 성공 후에도 추가 AI 호출/직원 수정/사용자 승인 대행 없이 중단.

**완료 기준**: 사용자 이번 개별 승인에 따라 **실제 무료 AI 관리자 1회 이하**가 TASK-002 미승인 대본을 읽고 자율 검토 판단 1건을 생성, 프로그램 검증 후 사용자 결정 대기로 안전하게 저장. 그 외 실제 실행/수정/승인은 0회.
