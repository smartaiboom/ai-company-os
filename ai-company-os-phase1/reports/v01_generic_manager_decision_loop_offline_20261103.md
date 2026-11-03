# 범용 관리자 판단·사용자 결정 흐름 오프라인 구현

작성: 2026-11-03 09:47 KST(UTC+9). `git pull --ff-only`로 main `6801a6b` 반영 후 지정 작업을 수행했다.

## 결과와 범위

**실제 외부 AI API 호출 0회.** 임의 목표의 사용자 승인된 직원 결과를 입력으로 모의 관리자 제안을 생성·저장·조회하고, 사용자 질문/승인/거절/답변 및 후속 실행 게이트를 구현했다. 모의 callback이 JSON을 반환하는 테스트이며 실제 AI가 핵심 항목을 선택하거나 자율 판단한 증거가 아니다. 실제 OpenRouter 관리자 transport·자동 활성화·유료/fallback 경로는 추가하지 않았다.

실제 영상 프로젝트 cb44b605b498에는 기능을 설정하거나 제안을 만들지 않았다. TASK-001 완료·사용자 승인, TASK-002/003/004 대기, completed **2/7**, failed 0, reserved 0을 그대로 유지했다. 실제 직원 실행·질문 전송·계획 변경·결과 수정·새 승인은 없었다.

## 변경 파일과 구조

- `manager_decision.py`: 비밀 없는 입력 구성, 지문, strict JSON 검사, 주입형 MockDecisionProvider, 사용자 승인 진행 게이트와 진행 지침 구성.
- `app.py`: 명시적 모의 기능 설정·제안 생성·조회·사용자 응답 도구 handler, 프로젝트 잠금/atomic save 연결, 직원 실행 직전 게이트 및 승인된 모의 관리자 지침의 후속 입력 연결.
- `tests/test_manager_decision_loop.py`: 서로 다른 두 목표와 네 행동, 상태 전이·보존·경합·실행 차단의 오프라인 테스트 19개.
- 이 보고서. 실사용 JSON·키·제공자 원문·로그는 Git 제외.

기능이 없는 과거 프로젝트는 기존 동작을 유지한다. 기능은 `configure_mock_manager_decisions`를 명시적으로 호출한 프로젝트에서만 켜진다. 일반 직원 결과 승인으로 기능을 자동 설정하거나 판단 공급자를 자동 호출하지 않는다. 모의 제안 생성도 명시적 도구 호출이다. 설정된 프로젝트에서는 관리자 제안이 아직 없어도 다음 의존 업무 실행을 차단한다.

## 입력과 판단 계약

입력은 목표, 현재 업무의 승인 계획 단계, 성공 이력이 있는 사용자 승인 결과와 result_revision, 현재 업무/역할, 허용 선호 focus/video_style, 직접 후속 업무의 정의 요약, 기존 업무 ID, 해당 결과에 대한 사용자 답변, 비밀 없는 예산·권한 요약이다. 전체 계획/이력·다른 프로젝트 자료·미승인 결과·성공 기준 초안·키·개인 메타데이터를 일괄 포함하지 않는다. 전체 계획은 내용 대신 지문으로 결속한다. 결과·답변은 `approved_result_data`와 `user_answers`의 자료이며 내부 명령을 시스템 지시로 취급하지 않는다는 data_notice를 둔다. 실제 모델 프롬프트 계층은 미구현이므로 실제 모델의 프롬프트 주입 방어를 검증했다고 주장하지 않는다.

공통 JSON 필드는 정확히 schema_version=1, binding, action, rationale, evidence, next_step, uncertainty, source=model_claim, payload다. binding은 project_id, task_id, result_hash, result_revision, approval_hash, plan_hash, input_hash를 갖고 현재 입력과 완전히 일치해야 한다. 사용자 선호·답변·후속 정의·예산 요약이 바뀌어도 입력 지문이 달라진다. 승인 시각 변경이나 결과 버전 변경도 기존 제안을 무효화한다.

| action | payload 필수 필드 | 사용자 응답 후 처리 |
|---|---|---|
| proceed | next_task_ids, guidance | approve 이후 명시한 후속 업무의 관리자 게이트만 통과 |
| ask_user | question, why_needed, options | answer는 별도 답변 이벤트로 저장, 새 입력에 대한 제안 생성 가능 |
| request_revision | task_id, reason, scope | 제안 수락은 accepted_for_review, 원본 결과·승인 상태를 변경하지 않음 |
| propose_plan_change | changes 배열: operation(add/modify/reorder), task_id, description | 제안 수락은 accepted_for_review, 계획·업무에 적용하지 않음 |

승인된 proceed의 guidance/근거/불확실성은 후속 직원의 previous_results에 ‘사용자가 승인한 관리자 진행 제안’으로 붙고, 모의 관리자·model_claim으로 구분된다. 관리자 지침은 사실 보증이나 새 시스템 명령이 아니다. 답변과 계획 변경 제안은 직원 입력으로 자동 적용하지 않는다.

JSON 전체와 입력은 각각 32,768바이트 이하, 원본 결과는 16,000자 이하, 목표는 2,000자 이하, 설명 문자열은 항목당 1,500자 이하, 답변은 2,000자 이하, 질문 선택지는 최대 6개, 변경 제안은 1~10개, 프로젝트 제안은 최대 50개다. 설명에 한국어 포함을 검사하되 문장 품질을 보증하지 않는다. TASK ID는 TASK-숫자3자리다. 진행은 실제 직접 후속 업무만, 수정은 현재 승인 결과만, 변경/재배치는 기존 업무만, 추가 제안은 기존 ID와 충돌하지 않는 새 TASK ID만 허용한다. 변경 제안은 구조화된 설명이며 실행 가능한 새 계획으로 간주하지 않는다.

알 수 없는 action/필드·빈 필수 값·잘못된 타입/ID·중복 JSON 키·비표준 숫자·stale/다른 프로젝트 binding은 거절한다. 검증 실패 시 제안/결정은 저장하지 않는다. 실제 저장에는 원본 결과 대신 binding, 공급자 mock 표시, 제안 버전, KST 시각 및 감사 이력을 남기며 직원 원문을 바꾸지 않는다.

## 최소 사용자 결정 인터페이스

새 웹 화면/HTTP API는 추가하지 않았다. 명시적 로컬 도구 handler를 제공하며, 호출 도구는 실제 사용자 결정을 확인한 뒤 응답을 넘겨야 한다. 아래 함수는 자체적으로 프로젝트 잠금을 소유하므로 이미 잠근 HTTP handler 안에서 다시 호출하지 않는다.

| 함수 | 용도 |
|---|---|
| configure_mock_manager_decisions(project_id, expected_project_hash) | 승인된 계획을 가진 가상 프로젝트의 명시적 opt-in. 해시는 manager_decision.digest(project) |
| propose_manager_decision(project_id, task_id, MockDecisionProvider(callback)) | 사용자 승인된 성공 결과로 모의 제안 1개 생성. callback은 context를 받아 strict JSON 문자열 반환 |
| manager_decision_view(project_id) | 질문·이유·선택지·제안·상태·stale 및 expected_hash를 읽기 전용 반환 |
| respond_manager_decision(project_id, proposal_id, expected_hash, response, answer='') | 실제 사용자 approve/reject/answer 기록. 조회한 expected_hash로 동시/중복 결정을 차단 |

제안은 처음 pending_user_decision이다. proceed를 approve하면 approved, reject하면 rejected다. 질문 answer는 answered 및 별도 manager_question_answered 감사 이벤트/답변 배열을 저장한다. 답변만으로 후속 업무를 풀지 않는다. 새 답변으로 달라진 입력에 대해 명시적으로 재제안을 생성하고 사용자 판단을 다시 받아야 한다. 다른 행동을 approve하면 accepted_for_review이며 적용·실행 권한은 없다.

동일 binding의 제안 재생성은 거절 후에도 차단한다. source 결과/승인/계획/답변 등 입력이 바뀌면 새 binding·새 버전으로 제안할 수 있고 과거 이력은 남는다. stale 제안은 조회에 표시되지만 사용자 승인이나 실행 게이트에 사용할 수 없다.

## 실행 연결과 미구현 사항

기존 execute_project_task에서 선행 결과 검사 후 관리자 게이트를 검사하므로 기존 단일 직원 실행과 _run_workflow 자동 진행 모두 적용된다. 승인된 proceed가 있어도 직원 실행을 자동 시작하지 않는다. 기존 선행 결과 사용자 승인, semantic 전용 실행, 실제 요청 서버 활성화·동의·무료 모델·주소·request_scope·7회/2회 예산 검사는 그대로 필요하다. 관리자 제안 수락으로 real_ai나 외부 전송 권한을 설정하지 않는다.

수정 요청·승인 후 계획 변경의 실제 적용, 의존 관계 재검증을 포함한 변경 계획 승인 흐름, 고급 UI, 관리자 실제 모델 연결/외부 전송 승인/실제 호출 예산 설계는 **미구현**이다. 이 작업은 지시서 12항의 허용 범위인 계약·제안 영속화·질문/사용자 결정·후속 게이트까지 완성했다. 기존 완료/진행 업무 삭제·덮어쓰기 기능은 없다.

단일 운영 프로세스의 기존 잠금 구조를 사용한다. 비차단 잠금으로 동시 작업을 거절하고 판단 공급자 반환 후 디스크 상태를 재읽어 변경됐으면 저장을 거절한다. 사용자 응답은 제안 해시와 현재 binding을 재검사한다. 다중 서버 프로세스 간 잠금이나 사용자 인증 UI는 이번에 추가하지 않았다. 로컬 파일을 직접 수정할 수 있는 소유자에 대한 위변조 방지 저장소는 아니다.

## 집중 오프라인 검증

최초 신규 묶음: `python -B -m unittest tests.test_manager_decision_loop` → **15개 통과**.

승인 지침 전달과 기존 호환성 연결 후:
`python -B -m unittest tests.test_manager_decision_loop tests.test_mock_workflow_orchestration tests.test_task_result_approval_preparation tests.test_approved_employee_context tests.test_execution_engine` → **43개 통과**.

추가 경합·상한·사용자 토큰 검증과 최종 코드 수정 후 명령:
`python -B -m unittest tests.test_manager_decision_loop tests.test_mock_workflow_orchestration tests.test_task_result_approval_preparation tests.test_approved_employee_context tests.test_execution_engine tests.test_real_ai_safety_budget.RealAISafetyBudgetTests.test_no_activation_or_consent_no_transport_or_budget_write tests.test_real_ai_safety_budget.RealAISafetyBudgetTests.test_reserve_before_transport_and_two_per_request_seven_total`

최종 **49개 통과**(신규 19개 포함). 동일 집중 명령의 최종 재실행도 49개 통과했다. 목표·후속 업무와 승인 계획의 일치 검사를 보강한 뒤에도 집중 묶음 49개가 통과했고, 마지막 입력 타입/후속 정의 stale 사례 보완 후 신규 모듈 테스트 19개를 재실행해 모두 통과했다. 실패한 테스트 실행은 없고 미해결 실패도 없다. 전체 테스트·브라우저 설치·실제 AI 호출은 하지 않았다.

확인한 시나리오:

- 초보자 영상과 재고/운영 개선 가상 목표, 네 action 모두 저장·조회·사용자 결정 대기. 열 개 후보 우선순위 제안은 fixture 문장으로 모사하며 특정 개수 선택 규칙이 운영 코드에 없다.
- 승인 전 결과·알 수 없는 TASK·다른 프로젝트 binding·잘못된 JSON/중복 키/빈 값/잘못된 action·필드/상한 거절.
- 제안 없음/질문/수정/변경 제안 대기에서는 다음 직원/자동 workflow 실행 차단. 승인된 proceed 이후에만 모의 직원 실행 및 지침 전달.
- 사용자 진행 승인 후에도 실제 서버 활성화가 없으면 외부 transport 0회·예산 불변. 기존 safety 테스트에서 동의/서버 차단과 요청 전 예약·2회/7회 한도 확인.
- 결과/목표/계획/승인 시각 변동, stale 사용자 토큰 거절. 공급자 처리 중 상태 변경 시 덮어쓰기 거절.
- 질문 답변 이력·입력 지문 변경·새 사용자 결정 대기, 거절 상태·중복 제안/승인 차단, 동시 승인 1회만 성공, 동시 제안 공급자 1회만 호출.
- 새 Python 프로세스에서 질문·상태 복원, 원본/계획/예산 보존, 기존 일반 프로젝트와 모의 workflow 회귀.

신규 테스트는 가상 임시 경로만 사용한다. socket/DNS 및 외부 opener를 차단했고 주입된 모의 공급자·모의 직원만 사용했다. 기존 집중 회귀 테스트의 transport도 fake/차단이다.

## 실제 데이터 보존과 예산 상충

시작 전 data/backups의 기존 파일 15개 SHA-256과 경로 목록을 /tmp에 기록하고 구현·테스트 후 전부 동일함을 확인했다. 영상 프로젝트에 manager_decisions 필드가 없고 실제 제안 생성 0임도 확인했다. 재고 프로젝트 c85d9853906a의 미확정 예약·보존본·원장과 기존 데이터·백업은 불변이다. 기존 미추적 파일을 스테이징하거나 정리하지 않았다. 데이터/백업을 새로 복사·삭제·초기화하지 않았다.

영상 프로젝트는 현재 2/7회 사용·잔여 5회다. 대본 1 + 최초 의미 검토 1 + 최종 패키지 1 + 필요시 수정 1 + 재검토 1 = 남은 최대 5회이며 기존 전체 최대는 7회다. **관리자 실제 판단 1회를 추가하면 전체 최대 8회**로 상한과 충돌한다. 수정이 필요 없는 경로는 원래 총 5회이고 관리자 1회 추가 시 총 6회지만, 수정/재검토 여유를 동일하게 보장할 수 없다. 반복 관리자 판단/질문 재판단도 실제 연결 시 각 호출 예산 설계가 필요하다. 이번 모의 제안은 외부 요청이 아니므로 실제 예산을 소모하지 않았고 상한·예약을 늘리거나 초기화하지 않았다.

보고서 저장 후 재읽기와 git diff --check, 필요한 네 파일만 선택적 커밋·푸시 및 원격 main 일치 확인을 수행한다.

## 다음 한 단계

사용자가 모의 계약·질문/응답·실행 게이트를 검토한 뒤, 실제 프로젝트 적용 또는 실제 관리자 연결의 별도 범위와 7회 예산 안의 흐름을 판단하는 것이다. 이번에는 실제 영상 프로젝트 적용·TASK-002 실행·실제 관리자 호출 승인이나 그 호출을 수행하지 않았다.
