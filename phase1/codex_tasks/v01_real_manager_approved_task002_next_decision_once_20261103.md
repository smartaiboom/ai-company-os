# AI Company OS v0.1 — 승인된 TASK-002 결과에 대한 실제 관리자 후속 업무 판단 1회

## 이번 사용자 직접 승인·범위
2026-11-03, 직전 제안 “다음은 AI 관리자에게 TASK-003 진행 여부를 판단시키는 단계야. 실제 무료 AI 관리자 호출 최대 1회를 승인하면 그 작업 지시서를 GitHub에 작성할게. 기존 예산을 지키고, 품질 검토 직원은 아직 호출하지 않을 거야.”에 사용자가 “그래 진행해줘”라고 답함.

**승인 범위는 오직 프로젝트 `cb44b605b498`의 이미 승인된 TASK-002 대본 결과를 읽어 실제 `openrouter/free` AI 관리자에게 후속 업무 의사결정을 최대 1회 요청하고, 나온 제안 1건만 `pending_user_decision`으로 검증·저장하는 것**이다. TASK-003·004 직원 호출, semantic 평가, TASK-002 재실행·결과 수정, 사용자 대신 제안 승인, 계획 변경 적용, 다른 AI 관리자 추가 호출은 금지. 모델이 proceed/ask_user/request_revision/propose_plan_change 중 스스로 선택하며 특정 답을 강제하지 않는다.

이번 승인으로 프로젝트 목표, 승인된 TASK-002 결과, 허용된 선호, 승인된 계획/해당 업무 정의, 직접 후속 업무, 사용자가 등록한 관련 답변, 안전 예산 요약을 최소 범위로 외부 전송 가능. 다른 프로젝트, API 키, 전체 이력, 불필요한 민감정보는 전송 금지. 구조화된 의미 검토 기준 `success_criteria_draft`는 아직 승인되지 않았으므로 승인된 기준인 것처럼 모델에 제공하거나 확정하지 말 것. 기존 사용자 승인 TASK-002 결과는 품질 검증 완료와 다름.

## 사전 확인 (불일치 시 전송 0회, 중단)
`git pull --ff-only`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`, `reports/v01_accept_review_proceed_approve_task002_prepare_task003_20261103.md`, `reports/v01_real_manager_review_task002_once_20261103.md`, `manager_decision.py`, `app.py`, `real_manager_review_tool.py`, `ai_safety.py`, `project_budget.py`, 관련 tests를 읽고 시작한다. KST(+09:00)·한국어, 기존 코드/데이터/백업/guard/미추적 파일 보존, git reset/clean/force push 금지.

- 실사용 Git 제외 `data/video-real-plan-20261103/projects/cb44b605b498.json`: 실제 호출 원장 **7/20**, 정확히 7건 모두 completed, failed/reserved 0, 기타 실행 중 worker 없음. 예상 원장 kind/task_id 순서: `plan/-`, `task/TASK-001`, `manager_decision/TASK-001` 3건, `task/TASK-002`, `manager_decision/TASK-002` 1건. 각 항목 기존 그대로. 다른 프로젝트 `c85d9853906a`의 미확정 예약은 그대로 유지.
- 승인 계획·goal·preferences 불변, TASK-001 완료·approved 및 결과 SHA-256 `95e366272746a507f26f3776db5e6e5211126ae0f1f7d2b7712a718e5cff6802`; TASK-002 **완료·approved** 및 원문 SHA-256 `2276736d569a6e6cb34af05a4ac44e386d5a087ebd82f82dd59304c8bf0904ae`; TASK-003/004 대기·결과 없음.
- 관리자 TASK-001의 approved proceed 제안 `2d62725cfe374852b916b5bd20af67ac`는 보존. TASK-002 검토 목적 기존 제안 `4a415f66a228440481806dd5cfc2818a`는 **accepted_for_review**이며 승인 상태 변화 때문에 `stale=true`가 정상이다. 이것을 오래된 오류로 취급해 임의 수정하거나 같은 제안을 이어서 재사용하지 말 것.
- `app._manager_decision_input(project, "TASK-002")`로 **approved-result 목적(검토 목적 아님)** 입력이 유효함을 확인. `manager_decision.decision_input`의 approved_result_data 및 새 binding/result_hash/approval_hash/plan_hash/input_hash를 활용, `employee_review_input`은 호출하지 말 것. TASK-002 approved-result binding에 대한 새 실제 manager proposal이 아직 없어야 한다. 관련 제안 50개 제한 및 동시 경합/미완료 예약 여부 검증.
- 사용자 현재 명시 승인, 새 고유 authorization ID, KST, 프로젝트/업무·approved-result 목적, 실제 result hash/revision·approval hash/plan/input binding·최신 전체 project hash, 모델·허용 필드/전송 범위, 정확한 이전 7건 attempt IDs, max_calls=1을 별도 사용 1회 감사 기록에 저장. **이전 1~3차 관리자 호출 승인, TASK-002 미승인 검토 승인, TASK-002 직원 승인 재활용 불가**. 승인 기록 또는 실패 기록이 있으면 같은 지시서 재실행/guard 삭제 후 재호출 불가.
- 프로젝트 mutations lock·현재 디스크 snapshot 비교·data/backups SHA 및 기존 guard/미추적 목록·활성 worker 검사. 실제 키는 존재 여부만, `AI_MODEL=openrouter/free`, 고정 `https://openrouter.ai/api/v1`; 기존 `ai_safety` free-only, 요청 선예약, 예산 20, 시작당 최대 2, 1회 호출, 90초 이하 timeout, 크기 한도, 프록시/리다이렉트 금지, 자동 재시도 금지.

## 최소 구현
1. 기존 `real_manager_review_tool.py`의 한 번만 사용할 수 있는 owner runner·O_EXCL guard·관측 파일 fsync·reservation/transport gate·프로젝트 lock·경합 방지 패턴을 참조하되, **새 전용 로컬 owner handler**로 새 승인/전송 범위/정확한 8번째 요청 `manager_decision/TASK-002/openrouter/free` 조건에 맞게 좁게 구현. 기존 단일 호출 도구의 사전조건을 완화·재사용 가능하게 만들지 말 것. HTTP/UI/자동 workflow/스케줄 추가 금지. 기존 실제 모델 계약을 임의 변경하지 않는다.
2. 실제 호출은 `manager_decision.RealManagerDecisionProvider().generate(project, context)` 및 `ai_safety.request_scope` / 내부 원장 영속 예약을 그대로 사용. 승인 원문은 Codex 지시서에 명시된 사용자 현재 답변으로만 감사 저장. 요청 전 새 고유 guard 및 transport_calls=0 관측 파일 영속 저장. 정확한 8번째 원장 항목이 `reserved`로 저장된 것을 확인한 뒤 **transport_calls=1을 실제 전송 전에 fsync**. 성공/실패/timeout 모두 최대 1회이며 재시도하지 말 것. 실패/미확정 원장을 성공으로 바꾸거나 사용량을 되돌리지 말 것.
3. 모델 JSON 정확히 여섯 필드 `action,rationale,evidence,next_step,uncertainty,payload`, 프로그램 결합 schema_version/binding/source, `parse_and_validate` 검증. action 내용/판단을 보정하거나 video-specific 규칙 강제 금지. 모델이 `proceed` 선택 시 payload 직접 후속 IDs에 따라 제안만 저장하며 **TASK-003/004는 실행하지 않음**. 목표/선호/선행 결과가 충분치 않다고 ask_user 등을 선택해도 있는 그대로 저장. `purpose` 없는 기존 approved-result proposal 형식, provider=real_openrouter_free, status=pending_user_decision, stale=false 확인; 기존 review-purpose 제안과 분리.
4. 작업 중 프로젝트 경합/실행 중 worker/원장 변경/입력 hash·TASK-002 승인 상태 변경 등이 일어나면 제안 저장을 차단하고 이미 시도한 호출은 재호출하지 않는다. 이전 7개 attempts/기존 제안·승인·결과·history 접두부, TASK-003/004 전체, 모든 백업·타 프로젝트·guard 불변.
5. 성공 시 예상 사용량 **7/20→8/20 (잔여 12)**; 전송하지 못했다면 7/20, 실패/예약이 남았다면 정확한 실제 원장 상태 보고. 승인된 프로젝트의 기본 예산 확장·추가 비용 발생 모델 금지.

## 호출 전 필수 오프라인 검증
임시 가상 프로젝트·가짜 키·fake transport·네트워크 차단 테스트를 먼저 작성·실행. 성공 시 정확한 8번째 승인된-result 관리자 시도 1회, 6필드 모델 계약→프로그램 binding→사용자 검토 대기 저장/재조회, 다른 목적 기존 review proposal 보존 및 stale 상태 허용, 후속 직원 실행 0회. proceed/ask_user/request_revision/propose_plan_change fake 모델 응답 각각 검증. 승인 없음/이미 소모·중복 실행/guard 존재·삭제/프로젝트·TASK 불일치/원장 7건 불일치/미확정 예약·예산 초과/바뀐 TASK-002 결과·approval hash/계획·연계 업무/지문/동시 저장 경합/응답 오류/timeout·실패에서 transport 0 또는 최대 1, 재시도 0 확인. 실사용 JSON·실제 키를 fixture로 절대 사용하지 말 것. 기존 real manager 단일·pending review·TASK-002 실행·result approval·무료 안전·예산 관련 집중 회귀. 환경에서 HTTP socket 통합 테스트 권한 거절 시 **테스트 미통과로 속이지 말고**, 사용 가능한 격리 loopback 허용 환경에서 가짜 데이터로만 재검증; 실제 호출 전 필수 테스트가 미해결이면 호출 중단.

## 최종 보고
`reports/v01_real_manager_approved_task002_next_decision_once_20261103.md` 작성. 한국어로 사전조건 및 새 승인 ID/KST, 실제 전송 0/1회·시각·재시도 0·예산 7→최종, 원장/guard/관측, **실제 관리자 선택 행동/근거/대상 업무/구체적 제안(있으면)**, 제안 ID/status/stale, 미확인 사실의 한계, 사용자 다음 승인 필요 사항, TASK-003/004 미실행/semantic 기준 미승인, 기존 직원 결과·관리자 검토 기록·타 프로젝트/백업 불변 및 테스트 명령·통과 수를 명시. 전체 모델 원문/전체 대본/키/실사용 JSON/개인정보는 보고서·Git에 넣지 않는다. `git diff --check`, 필요한 코드/테스트/보고서만 선택적 commit/push, 원격 main 확인.

**완료 조건:** 사용자 별도 승인으로 실제 무료 AI 관리자가 승인된 TASK-002 결과를 평가해 후속 업무에 관한 *새* 판단 최대 1개 생성·검증·저장; 사용자 승인 대기에서 정지. 실제 직원 호출/다른 단계 실행/사용자 대신 결정 전부 0회.
