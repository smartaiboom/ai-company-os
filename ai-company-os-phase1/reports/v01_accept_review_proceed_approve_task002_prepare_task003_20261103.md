# 관리자 검토 proceed 수락·TASK-002 사용자 승인·TASK-003 준비

2026-11-03 KST. `git pull --ff-only`로 main 5d94670을 반영했다. **관리자 검토 제안 수락 → TASK-002 사용자 결과 승인 순서로 저장했다. 실제 AI 호출·TASK-003/004 실행·품질 검토 실행·워크플로 자동 실행은 모두 0회다.** 품질 검토 완료나 대본 정확성 입증을 주장하지 않는다.

## 사용자 결정과 실제 적용

사용자 원문 “응 다음 품질검토 단계로 진행하자”를 이번 결과 승인 근거로 사용했다. 지시서에서 TASK-003 실제 호출은 미승인임을 확인했다.

사전 프로젝트 cb44b605b498는 **7/20, completed 7, failed/reserved 0**이었다. TASK-001 approved와 결과 SHA-256 `95e366272746a507f26f3776db5e6e5211126ae0f1f7d2b7712a718e5cff6802`, TASK-002 완료·pending 및 결과 SHA-256 `2276736d569a6e6cb34af05a4ac44e386d5a087ebd82f82dd59304c8bf0904ae`, TASK-003/004 대기·결과 없음을 확인했다. 기존 TASK-001 진행 제안 `2d62725cfe374852b916b5bd20af67ac`는 approved였다.

대상 검토 제안 `4a415f66a228440481806dd5cfc2818a`를 manager_decision_view로 재조회했다. real_openrouter_free, employee_result_review, proceed, TASK-003/TASK-004, pending_user_decision, stale=false를 확인하고 현재 expected_hash를 사용했다.

- **2026-11-03 13:34:47 KST**: 기존 respond_manager_decision으로 먼저 수락, **accepted_for_review**, decided_by=사용자.
- 같은 시각: 수락 상태를 다시 읽어 불변 필드를 비교한 뒤 기존 결과 승인 로직으로 TASK-002를 **approved**, reviewed_by=사용자, reviewed_at=KST로 저장.
- 승인 원문·프로젝트/업무/제안·대상 원문 SHA와 revision·pending 검토 binding·실제 호출 미승인을 별도 최소 감사 이벤트에 기록.
- 승인 후 TASK-002 원문·result_revision·완료 상태는 불변이다. 원문 SHA-256도 위 값 그대로다.

관리자 수락은 approved-result 진행 허가로 승격하지 않았다. 사용자 결과 승인 후 검토 제안은 **accepted_for_review를 유지하면서 stale=true**로 조회된다. 이는 원래 제안이 pending 검토 상태에 묶여 있기 때문에 생기는 정상적인 과거 기록이다. 수락을 재실행하거나 binding을 승인 상태로 고치지 않았다. 모델이 이전에 “승인된 대본”이라고 표현한 것은 이번 사용자 승인의 근거가 아니다.

실행 명령: `python -B /tmp/accept_review_approve_task002_20261103.py`. socket/DNS 및 AI transport opener를 차단한 로컬 프로세스로 실행했고 종료 코드 0을 확인했다. 실제 키를 사용하거나 AI runner를 실행하지 않았다.

## 변경 파일과 동시성 보호

- app.py: 기존 /task/review 처리 본문을 공통 review_task_result 함수로 옮겼다. HTTP route는 같은 함수를 호출하며 기존 모든 검증·상태 변경·감사·최종 확정본 처리를 유지한다. 호출자는 기존 프로젝트 lock을 소유해야 한다. 로컬 승인용 선택 인자로 최신 프로젝트 지문 비교와 승인 감사의 동일 저장을 지원한다.
- app.py의 respond_manager_decision에 선택적 expected_project_hash 검사를 추가했다. 기존 호출 방식과 상태 계약은 유지하며, 로컬 도구는 lock 내부 진입 시와 저장 직전에 프로젝트 지문을 확인한다.
- accept_review_task002_tool.py: 이번 프로젝트/TASK-002 검토 proceed 수락과 사용자 결과 승인만 수행하는 로컬 도구다. 사용자 원문·전체 프로젝트 지문·원문 SHA·pending 상태·실제 검토 제안 및 정확한 후속 대상을 검증한다. 기존 승인 함수로 수락 후 다시 mutation lock 안에서 수락 외 변경 여부를 확인하고 공통 결과 승인 함수를 호출한다. 이미 완료된 단계나 경합을 발견하면 재처리하지 않는다. AI 엔진·네트워크·실행 승인 기능은 없다.
- tests/test_accept_review_task002.py: 가상 프로젝트·가상 키·네트워크 차단으로 순서·지문·원문·사용자 원문 바인딩·중복·경합·실행 차단을 검증한다.
- 이 보고서.

결과 승인 시 기존 task_needs_approval, 완료·비어 있지 않은 성공 결과, task_has_successful_result, task_requires_review, 선행 승인, 현재 검토 상태, semantic/final 특수 검증을 그대로 사용했다. 이번 도구는 추가로 정확한 pending 상태를 요구한다. 수락 뒤 경합 등으로 두 번째 저장이 실패하면 수락 기록은 보존하고 결과 승인이나 같은 단계 재실행은 하지 않는다. 두 단계가 하나의 전체 트랜잭션인 것처럼 표현하지 않는다.

## 테스트

명령:

`python -B -m unittest tests.test_accept_review_task002 tests.test_task_result_approval_preparation tests.test_manager_pending_review tests.test_real_manager_review_once tests.test_manager_decision_loop tests.test_concurrent_execution_safety tests.test_semantic_review_integration`

1. 샌드박스 실행 `/tmp/accept-review-tests.log`: **117개 실행, 오류 9건**. 기존 semantic HTTP 통합 사례들이 로컬 socket 생성 PermissionError로 실행되지 못했다. assertion 실패는 없었으며 실사용 데이터는 적용 전이었다.
2. loopback 서버를 허용한 승인 환경에서 같은 명령을 `/tmp/accept-review-tests-unrestricted.log`로 재실행: **117개 모두 통과**, 실패·오류 0, 16.452초. 실제 적용 전에 확인했다. HTTP 테스트는 가상 프로젝트와 모의 AI를 사용한다. 오류는 환경 권한으로 해소됐고 미해결 테스트 실패는 없다.
3. `python -B -m py_compile app.py accept_review_task002_tool.py` 통과. `git diff --check` 통과.

unittest 수는 기반 테스트 상속/import에 따른 반복 사례를 포함한다. 전체 테스트는 실행하지 않았다. 승인 순서와 반대 순서의 stale, 잘못된 사용자 원문·원문 SHA·프로젝트 지문, 수락 직전/직후 경합·중복 처리 차단, 원문/revision·원장·기존 TASK-001 제안 보존, review 목적 accepted_for_review와 approved-result 실행 권한 분리, TASK-003 미실행을 확인했다. 기존 HTTP 승인·요청 수정·semantic·동시성 회귀도 포함한다. 실사용 JSON/실제 키는 fixture에 사용하지 않았다.

## TASK-003 준비 상태와 남은 차단조건

TASK-003의 역할은 “품질 검토 담당”이고 TASK-002를 선행 입력으로 가진다. TASK-002의 사용자 승인으로 선행 결과 조건은 충족됐고, **decision_input(project, TASK-002)의 승인 결과용 context 생성이 가능**함을 읽기 전용으로 확인했다. 새 관리자 판단이나 지침을 만들지는 않았다.

현재 semantic 설정은 **없다**. 따라서 TASK-003은 현재 저장 상태에서 semantic 전용 reviewer로 지정돼 있지 않다. 역할 이름만으로 의미 검토 전용 절차가 활성화되는 것은 아니다. 구조화된 의미 검토를 사용하려면 사용자가 명시적으로 성공 기준을 승인하고 configure_semantic에서 대상 TASK-002/검토 TASK-003을 연결해야 한다. 기존 기준 초안 success_criteria_draft.approved는 **false**이며 “초보자 기본 활용법”, “화면 녹화·자막·음성 설명에 맞춘 제작 자료”라는 선호 성격의 초안만 있다. 이를 승인된 의미 기준으로 확정하지 않았다. configure_semantic은 명시적으로 받은 기준을 별도 semantic.criteria에 저장하며 초안 플래그를 자동 승인하지 않는다.

현재 **require_proceed(project, TASK-003, [TASK-002])는 차단**된다. 수락한 review 제안은 미승인 결과 검토 목적이므로 후속 실행 허가로 사용할 수 없다. 승인된 TASK-002 결과 binding을 대상으로 하는 별도의 approved-result-manager proceed 판단과 그에 대한 사용자 승인이 필요하다. 이를 얻으려면 별도 관리자 실제 호출 승인·판단 생성 작업도 필요하며, 이번에는 호출하거나 모의 판단으로 대체하지 않았다.

TASK-003 실제 실행 전 필요한 것은 다음과 같다.

- 구조화된 의미 검토를 사용할 경우: 구체적인 품질 기준에 대한 사용자 승인과 semantic 대상/검토 업무 설정.
- 승인된 TASK-002에 대한 별도 후속 관리자 판단과 사용자 진행 승인. review 제안 수락이나 결과 승인을 재사용해서 이 조건을 우회할 수 없다.
- 실제 TASK-003 무료 AI 품질 검토 호출에 대한 별도 명시 승인과 안전한 단일 실행 준비. 기존 프로젝트 동의·잔여 예산이 있어도 이번 지시에는 실제 호출 권한이 없다.

7/20으로 잔여 13회이지만 예산 잔여량은 실행 승인이 아니다. run_semantic_review는 별도 semantic 설정·성공 기준·선행 승인 등을 요구하며, 내부 execute_project_task에서도 관리자 진행 승인이 검사된다. 현재 차단 상태에서 실행을 시험하거나 예약을 만들지 않았다. TASK-004 역시 실행하지 않았다.

## 보존과 종료

사전 data/backups 25개 및 기존 미추적 파일 6개, 총 **31개** 목록·SHA를 기록했다. 사후 대상 프로젝트 JSON 외 **30개 파일 SHA가 동일**하다. 다른 프로젝트 c85d9853906a의 기존 미확정 예약, 모든 백업, 기존 관리자·직원 guard와 관측 파일을 포함한다. 최종 data/backups 목록에는 새 파일이 없다. 테스트 중 생성된 부산물 처리 내용은 아래에 별도로 기록한다.

대상 JSON은 기존 7건 원장과 real_ai 전체, TASK-001 전체, TASK-003/004 전체, TASK-002 원문/revision/완료 상태, 기존 TASK-001 관리자 제안, 계획·목표·선호·성공 기준 초안·기존 history 접두부를 보존했다. 허용된 review 제안 결정 필드, TASK-002 승인 필드·갱신 시각, 세 감사 이벤트와 프로젝트 갱신 시각만 변경했다.

최종 **7/20, completed 7, failed/reserved 0**, 새 실제 AI 호출 **0회**. TASK-003/004 대기·결과 없음, semantic 기준 미승인 상태를 유지하고 종료한다. 코드·테스트·보고서만 선택적으로 커밋·푸시하며 실사용 JSON·전체 대본·키는 Git에 포함하지 않는다.

## 최종 보존 검사에서 발견한 테스트 부산물

기존 통합 테스트가 기본 project_budget.KEY_PATH를 사용해 사전 목록에 없던 data/.budget-approvals/local.key를 새로 생성했음을 발견했다. 내용이나 키 값은 출력·보고하지 않았다. 이 파일이 사전에 없었고 이번 테스트가 만든 파일임을 확인한 뒤 해당 새 파일과 비어 있는 새 디렉터리만 제거했다. 기존 파일은 삭제하지 않았다. 실사용 승인 적용에서 이 키를 사용하거나 AI 요청을 하지는 않았다.

신규 테스트 클래스는 서명키 경로를 자체 임시 프로젝트 디렉터리로 격리하도록 보완했다. 기존 통합 사례까지 포함한 전체 집중 실행도 임시 서명키 경로로 감싼 `/tmp/run_accept_review_tests_isolated.py`에서 재검증한다. 이는 제품 서명키 경로나 실사용 동의 설정을 변경하는 코드가 아니다.

최종 격리 실행 명령 `python -B /tmp/run_accept_review_tests_isolated.py > /tmp/accept-review-tests-isolated.log 2>&1`은 위와 같은 집중 모듈을 실행했다. **117개 모두 통과**, 실패·오류 0(16.929초). 격리 테스트 후 data/backups 25개 목록 및 대상 외 기존 30개 파일 SHA가 사전과 일치함을 재확인했다. `git diff --check` 통과, 보고서 저장·재읽기 검증 완료.
