# 새 개별 승인에 따른 TASK-002 실제 관리자 후속 판단

2026-11-03 KST. `git pull --ff-only`로 main 1f65bbd를 반영했다. **새 승인으로 openrouter/free 실제 요청 1회가 성공했고, 모델이 선택한 ask_user 제안 1개를 pending_user_decision으로 저장·재조회했다.** 재시도·직원 실행·사용자 답변 대행·계획 변경은 모두 0회다.

## 사전조건과 새 승인 구별

실사용 cb44b605b498는 8/20, completed 8, failed/reserved 0이었다. 정확한 원장은 plan/없음, task/TASK-001, manager_decision/TASK-001 세 건, task/TASK-002, manager_decision/TASK-002 두 건이었다. TASK-001/002 완료·approved와 다음 원문 SHA-256을 확인했다.

- TASK-001: `95e366272746a507f26f3776db5e6e5211126ae0f1f7d2b7712a718e5cff6802`.
- TASK-002: `2276736d569a6e6cb34af05a4ac44e386d5a087ebd82f82dd59304c8bf0904ae`.

TASK-003/004 대기·결과 없음, semantic 미설정·성공 기준 초안 미승인을 확인했다. 기존 TASK-001 제안 `2d62725cfe374852b916b5bd20af67ac` approved·stale=false, TASK-002 검토 제안 `4a415f66a228440481806dd5cfc2818a` accepted_for_review·stale=true를 확인했다. 후자는 정상적인 과거 pending-result 검토 기록이다. TASK-002 approved-result binding의 유효 제안은 없었다. 실행 중 AI worker는 프로세스 목록에서 발견되지 않았다.

이전 8번째 승인 ID `3c5eaa5ac06749d085e0aed63aa386fb`, 승인·중단 감사와 guard·관측은 보존했다. 이전 진단 provider_response/finish_reason 이상으로 과거 원인이나 응답 내용을 추측하지 않았다. completed가 유효한 모델 판단을 뜻하지 않는다는 구분도 유지했다.

**이번 새 승인 ID: `56ffb603be0742888ae028c7f5d21129`**, 기록 시각 **2026-11-03 14:10:59 KST**. 사용자 새 원문 “응 다음단계 진행하자 승인할게”를 그대로 기록했다. 별도 real_manager_task002_new_once_authorized 감사에 프로젝트/TASK-002, approved_result_next_decision 목적, 결과 hash/revision·approval/plan/input binding, 최신 전체 프로젝트 해시, 정확한 이전 8개 attempt ID, kind=manager_decision, model=openrouter/free, max_calls=1, 허용 필드·범위를 저장했다. separate_from_authorization_id로 이전 소모된 승인을 명확히 구별했다. 같은 지시서·새 승인 이벤트·중단 이벤트가 이미 있거나 이전 승인 ID를 제시하면 차단한다.

전송 data는 기존 _manager_decision_input/decision_input의 approved_result_data를 사용한다. goal, approved_stage, existing_task_ids, approved_result_data, preferences, next_tasks, user_answers, permission_summary, data_notice의 **9개 필드**, 현재 2754자 JSON이다. 허용 선호는 focus/video_style이고 관련 답변은 0개다. 미승인 기준·전체 이력·다른 프로젝트·프로그램 binding을 보내지 않았다. 키·인증 헤더·이메일 패턴은 발견되지 않았다. 패턴 검사를 모든 민감정보 부재에 대한 보증으로 해석하지 않는다.

## 변경 파일과 안전 경계

- real_manager_task002_new_authorization_tool.py: 별도 로컬 owner 단일 호출 경로다. 기존 도구를 완화하지 않고 정확한 8건 완료 원장, 기존 제안, 이전 승인·finish_reason 중단 감사, 새 고유 승인과 최신 프로젝트 지문을 검증한다. O_EXCL guard, fsync 관측, 9번째 예약 gate, mutation lock·현재 디스크 snapshot·입력 binding 비교로 최대 1회 전송 및 저장 경합 차단을 수행한다.
- tests/test_real_manager_task002_new_authorization.py: 가상 프로젝트·가상 키·fake transport·socket/DNS 차단으로 새 승인만 한 번 허용되는 경계를 검증한다. 서명키는 임시 디렉터리로 격리한다.
- 이 보고서.

기존 real_manager_approved_task002_tool.py, ai_provider_adapter.py, ai_safety.py, manager_decision.py, app.py와 다른 owner 도구는 수정하지 않았다. HTTP/UI/자동 worker/workflow/스케줄 경로는 없다. 기존 require_live_adapter와 request_json 및 RealManagerDecisionProvider를 공유하므로 단일 free-only 모델·고정 HTTPS·키 필수·프록시/redirect 차단·기존 예산·크기 한도·선예약 저장·무재시도를 유지한다.

새 guard와 transport_calls=0 관측을 먼저 저장하고, 정확히 9번째 manager_decision/TASK-002/openrouter/free/reserved 항목 및 앞 8건 불변을 확인한 후 transport_calls=1을 전송 전에 fsync한다. 실패도 승인을 소모하고 추가 전송하지 않는다. guard만 삭제해도 원장·승인·중단·제안 기록으로 재사용이 차단된다. 정상 stop·모델 여섯 필드·한국어/타깃/payload·프로그램 schema_version/binding/source·strict 계약 검증을 그대로 통과한 판단만 저장한다. action과 내용을 보정하거나 특정 답을 강제하지 않았다.

## 선행 오프라인 테스트와 회귀

1. `python -B -m unittest tests.test_real_manager_task002_new_authorization > /tmp/new-auth-initial-tests.log 2>&1` → **30개 모두 통과**, 실패·오류 0(9.957초).
2. 엄격 JSON 사례 추가 후 `python -B /tmp/run_new_auth_tests.py > /tmp/new-auth-focused-tests.log 2>&1` → **344개 모두 통과**, 실패·오류 0(30.698초). 실제 전송 전에 완료했다.
3. 실제 요청 중 별도 가상 데이터 프로세스로 같은 집중 모듈을 `/tmp/new-auth-post-tests.log`에 재실행 → **344개 모두 통과**, 실패·오류 0(30.650초).

/tmp/run_new_auth_tests.py는 임시 서명키 경로 아래 다음 unittest 대상을 실행한다.

`tests.test_real_manager_task002_new_authorization tests.test_ai_provider_adapter tests.test_execution_engine tests.test_manager_plan tests.test_manager_model_output_contract tests.test_manager_pending_review tests.test_real_manager_decision tests.test_real_manager_second_authorized tests.test_real_manager_third_authorized tests.test_real_manager_review_once tests.test_real_manager_approved_task002 tests.test_real_task002_once tests.test_accept_review_task002 tests.test_real_ai_safety_budget tests.test_project_budget tests.test_semantic_review_integration.SemanticIntegrationTests`

기반 테스트 import/상속에 따른 반복 사례를 포함한 실제 unittest 실행 수다. 전체 테스트와 HTTP socket 통합 클래스는 실행하지 않았다. 실제 JSON·키는 fixture로 사용하지 않았으며 테스트 부산물은 임시 경로에만 저장했다. 초기/최종 미해결 테스트 실패는 없다.

네 행동의 fake 응답, 정확한 9번째 예약·단일 전송·여섯 필드→binding 결합→pending_user_decision 저장·새 프로세스 재조회, 기존 8건 원장/승인/중단 감사·대본·기존 guard·다른 가상 프로젝트 보존을 확인했다. 승인 누락·소모·과거 ID 재사용·이전 중단 기록 누락·guard 존재/삭제·lock·다른 프로젝트/TASK/목적·원장/예약/예산·바뀐 결과/approval/계획/연계 업무·저장 경합, 잘못된 JSON/중복 키/metadata/payload/non-stop·timeout·전송 실패·예약/제안 저장 실패를 재시도 없이 거절함을 검증했다. 기존 owner 도구·adapter free-only·무료 예산 회귀도 포함한다.

## 실제 요청과 검증된 판단

실행 명령: `python -B /tmp/run_task002_new_authorization_once_20261103.py`. 네트워크 제한에 따른 승인된 외부 실행으로 수행했다. 이 프로세스에만 AI_REAL_REQUESTS_ENABLED=1, AI_API_TIMEOUT=60을 적용했다. timeout 인자는 90초 이하이며 전체 처리 시간 보장으로 표현하지 않는다. 키는 존재 여부만 확인했고 출력하지 않았다. 호출 직전 전체 보존 해시와 사전조건을 다시 확인했다.

- 모델: **openrouter/free**, 고정 HTTPS OpenRouter. 실제 transport **1회**, 재시도 **0회**.
- 시작·승인·transport 진입: **2026-11-03 14:10:59 KST**.
- 종료: **2026-11-03 14:11:28 KST**. 원래 실행 세션 exit_code=0으로 종료 확인.
- 사용량: **8/20 → 9/20, 잔여 11**, completed 9, failed/reserved 0.
- guard: data/video-real-plan-20261103/real-manager-task002-new-auth-once-20261103.guard.
- 관측: 같은 경로 real-manager-task002-new-auth-once-20261103.observation.json. transport_calls=1, finished=true.
- 새 제안 ID: **`96b8ee2cc37c4aee830515255cc2af80`**.
- 재조회: provider=real_openrouter_free, status=**pending_user_decision**, stale=**false**, 새 authorization_id·9번째 attempt_id 결합. 기존 approved-result 형식이며 proposal/binding에 review purpose가 없다. 오류 stage/code는 없다.

실제 AI가 선택한 행동은 **ask_user**다. 모델은 대본의 형식·선호 부합을 판단하면서도 미확인 사실이 남아 있다고 보고, 다음 사용자 결정을 요청했다.

**저장된 질문:** “현재 대본을 그대로 두고 의미적 품질 검토로 진행할까요, 아니면 사실 확인이 필요한 항목에 대한 수정을 요청할까요?”

모델의 선택지는 대본 유지 후 검토, 사실 확인 항목 수정, 추가 사실 확인 기준 제시, 검증된 항목으로 재생성, 미확인 항목을 품질 검토에서 처리, 기타 사유 제시의 여섯 가지다. 어느 것도 대신 선택하거나 자동 답변하지 않았다. 직접 후속 단계로 TASK-003 품질 검토를 언급했지만 proceed 지침이나 직원 실행 허가를 만든 것은 아니다.

근거·불확실성은 모두 모델 주장이다. 특히 근거 문장에 나열한 미확인 구간은 다섯 개인 반면 다른 판단 문장은 네 개라고 적어 수량이 일치하지 않는다. 이 불일치를 코드로 보정하지 않았고 숫자나 “검증됨” 표시를 독립 검증 사실로 인정하지 않았다. 실제 낭독 시간·사실/기능 정확성도 이번 호출로 입증되지 않았다. 사용자 답변과 별도 진행 판단/실행 승인이 필요하며, 질문에 답했다고 직원 실행이나 semantic 기준이 자동 승인되는 것은 아니다.

## 보존과 종료

사전 data/backups **27개**와 기존 미추적 파일 6개, 총 33개 목록·SHA를 기록했다. 사후 대상 JSON 외 **기존 32개 파일의 SHA가 동일**하다. c85d9853906a의 미확정 예약, 백업, 모든 이전 guard·관측을 포함한다. 새 파일은 이번 guard·관측 두 개뿐이며 기존 파일 삭제나 백업 추가/삭제는 없다.

대상 JSON의 앞 8 attempts, TASK-001/002 원문·revision·승인 등 업무 전체, TASK-003/004 대기·결과 없음, 기존 두 제안 전체, 기존 authorization/additional_authorizations·관리자 설정, history 접두부, 목표·계획·선호·미승인 기준 초안은 불변이다. 새 승인 감사·9번째 원장·제안·감사·갱신 시각만 추가/변경했다. 이전 8번째 승인과 중단 기록을 수정하지 않았다.

TASK-003/004 직원 실행, semantic 평가/기준 승인, TASK-002 수정/재생성, 사용자 결정 대행, 계획 변경, workflow 및 추가 관리자 호출은 **모두 0회**다. 새 ask_user 제안에 대한 사용자 결정을 기다리며 추가 호출 없이 종료한다.

최종 `git diff --check` 통과, 보고서 저장·재읽기 및 보존 재검증을 완료했다. 원격 main 확인 후 이번 도구·테스트·보고서 세 파일만 선택적으로 커밋·푸시한다. 실사용 JSON·전체 대본·모델 응답 전문·키·민감 로그는 Git에 포함하지 않는다.
