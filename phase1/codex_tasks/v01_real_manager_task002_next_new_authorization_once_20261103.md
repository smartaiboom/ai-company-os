# AI Company OS v0.1 — 이전 응답 중단 이후 새 승인으로 TASK-002 후속 관리자 판단 실제 1회

## 사용자 승인과 이번 목표
2026-11-03 사용자: “응 다음단계 진행하자 승인할게”. 이는 바로 앞에 안내한 **“실제 AI 관리자 호출 최대 1회를 새로 승인할까? 승인하면 기존 무료 모델과 보안 원칙을 지키고, 관리자 판단 결과만 저장”**에 대한 명시적 새 승인이다. 과거 8번째 호출의 재시도 허용이나 유료 모델 동의가 아니다.

**프로젝트 `cb44b605b498`, 승인 완료 TASK-002 대본을 대상으로 `openrouter/free` 실제 AI 관리자 후속 판단을 새로 최대 1회 호출하고 검증된 제안 1건을 `pending_user_decision`에 저장하는 것만 허용.** TASK-003/004 실제 AI 직원 호출, semantic 검토/기준 승인, TASK-002 수정/재실행, 사용자 대신 관리자 판단 승인, 전체 워크플로·추가 관리자 호출·계획 변경 적용은 금지. 실제 AI 관리자 스스로 proceed/ask_user/request_revision/propose_plan_change 중 판단. 코드로 proceed나 품질검토 진행을 강제하지 않는다.

`codex_tasks/README_KOREAN_LANGUAGE_RULE.md` 준수, KST(UTC+9), 한국어 지시·보고. git pull --ff-only 후 작업. git reset/clean/force push 및 기존 코드·데이터·백업·guard·미추적 삭제 금지. 필요한 작은 수정·집중 테스트·한 번의 실사용 호출·보고서만. 무리한 재설계/오래된 실패 진단 반복/새 공급자 활성화 금지.

## 반드시 확인할 현재 상태
`reports/v01_real_manager_approved_task002_next_decision_once_20261103.md`, `reports/v01_ai_provider_adapter_free_only_offline_20261103.md`, `real_manager_approved_task002_tool.py`, `ai_provider_adapter.py`, `ai_safety.py`, `manager_decision.py`, `app.py`, 관련 테스트 읽기.

실사용 제외 JSON `data/video-real-plan-20261103/projects/cb44b605b498.json` 최신 읽기:
- 원장 **8/20**, 8개 시도 모두 completed, failed/reserved=0, 잔여 12. 정확한 시도 kind/task_id는 `plan/-`, `task/TASK-001`, `manager_decision/TASK-001` 3회, `task/TASK-002`, `manager_decision/TASK-002` 2회. 과거 8번째는 provider 응답의 `stage=provider_response, error_code=finish_reason`, **검증된 제안 0개**, 승인/중단 감사 이력과 guard·관측 존재. **8번째 completed가 유효한 관리자 판단을 뜻하지 않음**.
- TASK-001 완료·approved SHA-256 `95e366272746a507f26f3776db5e6e5211126ae0f1f7d2b7712a718e5cff6802`. TASK-002 완료·approved, 결과 SHA-256 `2276736d569a6e6cb34af05a4ac44e386d5a087ebd82f82dd59304c8bf0904ae`. 기존 계획/goal/선호/업무 정의 불변, TASK-003/004 대기·결과 없음, semantic 기준 여전히 미설정·초안 미승인.
- 기존 TASK-001 후속 관리자 proceed 제안 `2d62725cfe374852b916b5bd20af67ac` approved 유효, TASK-002 pending-result 검토 제안 `4a415f66a228440481806dd5cfc2818a` accepted_for_review 및 승인 뒤 stale=true 정상. **TASK-002 approved-result 목적의 유효한 제안은 아직 없어야 함**.
- 현재 `app._manager_decision_input(project,"TASK-002")`가 성공하며 **approved_result_data** 목적(미승인 employee_result_review 아님) 사용, binding에는 result/approval/plan/input hash. 기존 해당 binding의 제안 중복/완료 있으면 중단.
- 다른 프로젝트 `c85d9853906a`의 미확정 예약·모든 data/backups·기존 1~8회 원장·승인 이력·guard 보존. 전체 사전 목록/SHA, 활성 worker/lock/새 예약 확인. 실제 API 키 존재만 확인, 값이나 전체 프롬프트/대본 출력 금지.

## 이번에 새로 부여된 동의만 1회 소비
프로젝트와 TASK-002, **새 승인 원문**, KST, 새 고유 authorization ID, 승인된 결과와 계획/binding·latest 전체 project hash, 정확한 앞 8개 attempt IDs, `kind=manager_decision`, `model=openrouter/free`, max_calls=1, 승인 전송 범위(현재 승인 목표·TASK-002 승인 결과·해당 승인 계획/업무·허용 선호·직접 후속 업무·답변·예산 요약), 과거 8번째 실패와 **이번 승인 별도**임을 감사에 영속 기록. 이전 8번째 승인 ID `3c5eaa5ac06749d085e0aed63aa386fb` 또는 기존 승인 원문을 재사용하지 말 것. 이 지시서의 재실행이나 guard 삭제만으로 추가 호출이 가능하면 안 된다. 동일 새 승인 이벤트나 호출/중단 이벤트가 있으면 차단.

## 최소 구현 및 안전한 실행
1. 새 로컬 owner-only 단일 호출 경로를 기존 `real_manager_approved_task002_tool.py`의 O_EXCL guard·관측 fsync·원장 예약·lock/낙관적 지문 검증 패턴으로 좁게 구현. 과거 도구의 `len(attempts)==7` 같은 단일승인 사전조건을 무력화하거나 재활성화하지 말 것. HTTP/UI/스케줄/자동 workflow 경로 추가 금지.
2. 기존 `ai_provider_adapter.require_live_adapter`, `ai_safety.request_json`, `manager_decision.RealManagerDecisionProvider.generate`를 사용. **오직 `openrouter/free` + 고정 `https://openrouter.ai/api/v1`**, 키 필수, 프록시/redirect 차단, 유료/대체 provider 금지, 20회 프로젝트 한도·2회/시작(여기선 1회)·입력/응답 크기·90초 이내 요청 timeout·미확정 예약 차단·자동 재시도 0회. 실제 전송 전에 **정확한 9번째 `manager_decision/TASK-002/openrouter/free` 원장 reserved 영속 저장** 및 별도 guard/observation 생성. transport 실행 전에 `transport_calls=1`을 fsync. 예약/경합/전송 오류가 났다면 일단 정지; 하나의 승인으로 2회 호출 절대 금지. timeout 이후 요청이 계속 처리되는 가능성을 무시한 재전송 금지.
3. 모델 출력을 strict 6필드 action/rationale/evidence/next_step/uncertainty/payload 그대로 검증; 프로그램 소유 binding/schema_version/source 합성. 정상 종료 `stop`만 통과, non-stop이면 실패와 고정 진단 기록만 남기고 **부분 응답을 판단 제안으로 위조하지 말 것**. 과거 실패 이유를 추측 보정하지 않는다. 공통 `classify_finish_reason`을 사용하되 필요하다면 이번 한 건에 대한 *제한된 분류값만* 유출 방지 확인 후 보고할 수 있다. 원문, 추론, 비밀, 프롬프트 전체 저장 금지. 같은 모델을 그대로 호출하므로 성공 보장은 없으며 실패하면 추가 호출 없이 중단.
4. 정상 판단만 `provider=real_openrouter_free`, 기존 approved-result 목적의 새 proposal (review-purpose가 아님), `status=pending_user_decision`, `stale=false`로 저장. 이후 **TASK-003·TASK-004 실행 0회, 사용자 결정 대행 0회**. 기존 제안 상태·대본/승인·사용자 성공 기준 초안 불변.
5. 새 호출이 1회 완료 시 예상 **8/20→9/20, 잔여 11**, 실패/예약도 기존 안전 규칙에 따라 기록. 경우에 따라 8/20일 수 있으니 실제 원장 보고. 모든 상태·시간은 KST.

## 실제 호출 이전 테스트 필수
가상 프로젝트/가상 키/fake transport/네트워크 차단으로 새 9번째 호출만 허용, 기존 승인과 마지막 `finish_reason` 중단 기록 보존, 중복·승인 재사용 불가, guard 삭제 후 우회 불가, 원장/프로젝트 경합/기존 예약/다른 프로젝트 및 task/결과·승인 hash 변경, 응답 정상/비정상 종료, 네 행동·엄격 JSON/finish_reason 처리, 재시도 0회, provider adapter free-only 및 고정 HTTPS, TASK-003/004 미실행을 검증. `ai_provider_adapter`, `real_manager_approved_task002`, `manager_model_output_contract`, `real_ai_safety_budget`, `project_budget` 등 집중 테스트 선행. 실사용 JSON/API 키를 fixture에 쓰지 말 것. 서명키 테스트 부산물은 임시 디렉터리로. 실패가 남으면 실제 호출 금지.

## 검증 보고
`reports/v01_real_manager_task002_new_authorization_once_20261103.md` 한국어 보고서 작성. 모델 호출 정확히 0/1, 재시도 0, KST 시각, 사용량 8→실제, 원장/guard/관측, 새 승인 ID, 테스트 명령·실제 통과 수, 유효 관리자 제안 ID/status/stale/행동·근거·직접 후속(성공 시), 아니면 **정확한 실패 stage/code와 원인 확인 한계**, TASK-003/004 미실행, 과거 원장·승인·대본·백업·다른 프로젝트 SHA 불변을 명시. 전체 모델 응답·키·민감 로그·실사용 프로젝트 JSON Git 금지. `git diff --check`, 최소 변경 파일만 선택적 commit/push, 원격 main 확인.

**완료기준**: 실제 AI 관리자 호출이 **최대 1회** 이루어지고, 유효한 판단을 받으면 사용자 결정 대기로 저장. 실패하면 실패 기록 보존, 추가 호출 없이 정지. TASK-003 실제 품질 검토는 별도 사용자 승인 전까지 수행하지 않는다.
