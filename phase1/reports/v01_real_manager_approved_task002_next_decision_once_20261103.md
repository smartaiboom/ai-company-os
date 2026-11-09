# 승인된 TASK-002의 실제 관리자 후속 판단 단일 호출 결과

2026-11-03 KST. `git pull --ff-only`로 main 33c8e75를 반영했다. **실제 openrouter/free 전송 1회 후 provider 응답 완료 사유 검증에서 중단됐다. 새 관리자 제안 저장은 0건이며 사용자 결정 대기 도달을 주장하지 않는다.** 재시도·직원 호출·사용자 승인 대행은 모두 0회다.

## 사전조건과 새 승인

실사용 cb44b605b498는 정확히 7/20, completed 7, failed/reserved 0이었다. 원장 종류/대상 순서는 plan/없음, task/TASK-001, manager_decision/TASK-001 세 건, task/TASK-002, manager_decision/TASK-002였다. TASK-001과 TASK-002 모두 완료·approved이며 각각 원문 SHA-256은 다음과 같았다.

- TASK-001: `95e366272746a507f26f3776db5e6e5211126ae0f1f7d2b7712a718e5cff6802`.
- TASK-002: `2276736d569a6e6cb34af05a4ac44e386d5a087ebd82f82dd59304c8bf0904ae`.

기존 TASK-001 진행 제안 `2d62725cfe374852b916b5bd20af67ac` approved·stale=false, TASK-002 검토 제안 `4a415f66a228440481806dd5cfc2818a` accepted_for_review·stale=true를 확인했다. 후자는 정상적인 과거 pending 검토 기록으로 보존했다. TASK-003/004 대기·결과 없음, approved-result binding의 기존 새 제안 없음, semantic 설정 없음과 성공 기준 초안 미승인을 확인했다. 실행 중 AI worker는 프로세스 목록에서 발견되지 않았다.

새 승인 ID는 `3c5eaa5ac06749d085e0aed63aa386fb`, 기록 시각은 **2026-11-03 13:43:31 KST**다. 사용자 이번 답변 “그래 진행해줘”를 원문 그대로 승인 근거에 기록했다. 감사 이벤트 real_manager_approved_next_once_authorized에 프로젝트/TASK-002, approved_result_next_decision 목적, 결과 hash/revision·approval/plan/input binding, 승인 전 프로젝트 해시, 이전 7개 attempt ID, model=openrouter/free, max_calls=1, 허용 전송 필드·범위를 저장했다. 이전 관리자·검토·직원 승인은 재사용하지 않았다.

전송은 기존 app._manager_decision_input과 decision_input의 **approved_result_data**를 사용했다. pending 결과용 employee_review_input으로 대상 입력을 구성하지 않았다. 허용 data는 goal, approved_stage, existing_task_ids, approved_result_data, preferences, next_tasks, user_answers, permission_summary, data_notice의 9개다. 실제 허용 JSON은 2754자, 관련 사용자 답변은 0개이며 선호는 focus/video_style만 포함한다. 미승인 success_criteria_draft, 전체 이력, 다른 프로젝트 내용, 프로그램 binding은 전송하지 않았다. 키·인증 헤더·이메일 패턴은 발견되지 않았다. 이 검사를 모든 개인정보가 없다는 보증으로 해석하지 않는다. 승인된 결과도 독립적인 품질 검증 완료 자료는 아니다.

## 변경 파일과 안전 경계

- real_manager_approved_task002_tool.py: 기존 review 도구의 lock·O_EXCL guard·fsync 관측·예약 gate·디스크 경합 비교 패턴을 복제한 별도 로컬 owner 경로다. 특정 프로젝트/TASK-002/approved-result 목적, 최신 전체 해시, 정확한 기존 7건 원장, 기존 두 제안 상태, 새 승인·실패 이력 없음 및 동일 binding 중복 없음을 요구한다. 제안 50개 제한도 유지한다. 승인·중단 이력과 원장으로 guard 삭제 후 재호출을 막는다.
- tests/test_real_manager_approved_task002.py: 임시 가상 프로젝트·가상 키·fake transport·socket/DNS 차단으로 새 경로를 검증한다. 서명키도 임시 디렉터리로 격리했다.
- 이 보고서.

기존 app.py, manager_decision.py, ai_safety.py, project_budget.py 및 이전 단일 호출 도구는 변경하지 않았다. HTTP/UI/스케줄/workflow/직원 실행 경로는 추가하지 않았다. RealManagerDecisionProvider.generate, request_scope와 선예약 원장 영속 저장, 모델 여섯 필드 계약·프로그램 schema_version/binding/source 결합·parse_and_validate를 그대로 사용한다. 정상 저장 시 목적 없는 기존 approved-result proposal 형식이 되도록 검증했다.

정확한 8번째 manager_decision/TASK-002/openrouter/free/reserved 항목이 저장되고 앞 7건이 불변이어야 전송한다. 전송 직전에 transport_calls=1을 fsync한다. 저장 때 프로젝트 snapshot·입력 binding·원장을 재비교하며 경합 시 과거 snapshot으로 덮어쓰지 않는다. 실패는 고정 stage/code로만 기록하고 원문 응답을 복원하거나 보정하지 않는다.

## 오프라인 테스트

1. `python -B -m unittest tests.test_real_manager_approved_task002 > /tmp/approved-next-initial-tests.log 2>&1` → **28개 통과**, 실패·오류 0, 8.405초.
2. 새 프로세스 재조회 및 lock 사례를 추가한 후 `python -B /tmp/run_approved_next_tests.py > /tmp/approved-next-focused-tests.log 2>&1` → **248개 통과**, 실패·오류 0, 23.731초. 실제 전송 전에 완료했다.
3. 호출 진행 중 별도 가상 데이터 프로세스로 같은 집중 모듈을 `/tmp/approved-next-post-tests.log`에 재실행 → **248개 통과**, 실패·오류 0, 22.431초. 실사용 runner와 데이터·환경을 공유하지 않았다.

/tmp/run_approved_next_tests.py는 임시 서명키 경로 아래 다음 unittest 모듈을 실행한다.

`tests.test_real_manager_approved_task002 tests.test_real_manager_review_once tests.test_manager_pending_review tests.test_manager_model_output_contract tests.test_manager_decision_loop tests.test_real_manager_decision tests.test_real_manager_second_authorized tests.test_real_manager_third_authorized tests.test_real_task002_once tests.test_accept_review_task002 tests.test_real_ai_safety_budget tests.test_project_budget`

수는 fixture import/상속에 따른 반복 사례를 포함한 실제 unittest 실행 수다. 전체 테스트 및 HTTP socket 통합 모듈은 이번에 실행하지 않았다. 집중 테스트에 환경 오류나 미해결 실패는 없었다. 실제 JSON·키를 fixture로 사용하지 않았다.

네 행동의 fake 응답 각각 정확한 8번째 예약·단일 전송·여섯 필드 검증·binding 결합·pending_user_decision 저장·새 프로세스 재조회를 확인했다. 승인 없음, 다른 프로젝트/TASK/목적, 중복/소모된 승인, guard 존재·삭제, 원장 불일치·예약·예산 초과, 결과·approval hash·계획·연계 업무·예약 경합, 응답 finish_reason/payload 오류, timeout/실패, 예약·제안 저장 실패 뒤 재시도 없음을 검증했다. 이전 검토 제안 accepted_for_review·stale 상태, TASK-002 승인 결과, 이전 guard·다른 가상 프로젝트 보존과 후속 직원 미실행도 확인했다. 기존 1~3차 관리자·pending review·직원 실행·결과 승인·무료 안전·예산 회귀를 포함한다.

## 실제 요청과 종료

실행: `python -B /tmp/run_approved_task002_next_once_20261103.py`. 네트워크 제한에 따른 승인된 외부 실행을 사용했다. 실제 실행 프로세스에만 AI_REAL_REQUESTS_ENABLED=1, AI_API_TIMEOUT=60을 적용했다. 키는 존재만 확인했고 값은 출력하지 않았다. 모델은 openrouter/free, 주소는 고정 https://openrouter.ai/api/v1이다. 프록시/리다이렉트 차단·무료-only·출력/응답 크기 한도·기존 시작당 최대 2회 규칙을 유지하고 이 도구에서는 최대 1회로 더 제한했다. 직전 전체 해시·사전조건을 다시 확인했다.

- 시작·승인 감사·transport 진입: **2026-11-03 13:43:31 KST**.
- 종료: **2026-11-03 13:45:53 KST**, 실행 세션 exit_code=0으로 관측/보존 검증까지 종료.
- 실제 전송 **1회**, 재시도 **0회**. 전체 처리 시간은 142초였다. timeout 인자 60을 전체 실행 시간 제한으로 보장했다고 표현하지 않는다. 이번 종료 진단은 timeout이 아니라 아래 완료 사유 검증 오류다. 기존 transport의 timeout 동작은 변경하지 않았다.
- 고정 진단: **stage=provider_response, error_code=finish_reason**.
- 예산: **7/20 → 8/20, 잔여 12**, completed 8, failed 0, reserved 0.
- guard: data/video-real-plan-20261103/real-manager-approved-task002-next-once-20261103.guard.
- 관측: 같은 경로 real-manager-approved-task002-next-once-20261103.observation.json. transport_calls=1, finished=true.
- 새 관리자 제안 **0개**. 기존 제안 2개만 유지하며 새 pending_user_decision 또는 action·근거·후속 지침을 보고하지 않는다.

원장의 completed는 provider 응답을 처리했다는 뜻이고 모델 판단 계약 성공을 뜻하지 않는다. finish_reason 검증을 통과하지 못했으므로 모델 선택 행동을 확정하지 않는다. 구체적인 완료 사유 값·응답 원문·내부 추론은 추가 분석/저장/공개하지 않았다. 응답을 임의 보정하거나 다시 요청하지 않았다. 실제 새 판단 생성·저장 성공 기준은 미충족이며 이번 호출 승인은 소모됐다.

## 보존 및 다음 결정

사전 data/backups 25개와 기존 미추적 파일 6개, 총 31개 목록·SHA를 기록했다. 사후 대상 JSON 외 **기존 30개 파일의 SHA가 동일**하다. 다른 프로젝트 c85d9853906a의 미확정 예약, 백업, 이전 모든 guard/관측을 포함한다. 새 파일은 이번 고유 guard와 관측 두 개뿐이며 다른 파일/백업을 생성·삭제하지 않았다.

대상 JSON은 앞 7 attempts, 업무 전체(승인된 TASK-002 원문·revision·승인 포함), 기존 두 관리자 제안 전체, 기존 관리자 authorization/additional_authorizations·기타 설정, history 접두부, 목표·계획·선호·미승인 성공 기준 초안 등 나머지 업무 필드를 보존했다. 허용된 새 승인 감사·8번째 원장·고정 중단 감사·갱신 시각만 변경됐다.

TASK-003/004는 대기·결과 없음, semantic 설정 없음·초안 미승인 그대로다. 직원 실행·semantic 평가·TASK-002 재실행/수정·사용자 대신 제안 승인·계획 변경·추가 관리자 호출은 모두 0회다. 새 후속 관리자 진행 제안은 없으므로 이전 차단조건은 해소되지 않았다. 새로운 실제 판단 요청을 하려면 별도 사용자 승인과 별도 안전한 작업이 필요하며 이번 승인을 재사용할 수 없다. 자동으로 추가 호출하거나 진단 기능 개발로 확장하지 않고 종료한다.

최종 `git diff --check` 통과 및 보고서 저장·재읽기 확인을 마쳤다. 원격 main 조회 후 이번 도구·테스트·보고서 세 파일만 선택적으로 커밋·푸시한다. 실사용 JSON·전체 대본·모델 원문·키·민감 로그는 포함하지 않는다.
