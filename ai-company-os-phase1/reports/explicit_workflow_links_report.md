# 명시적 업무 연결 개선 보고서

## 변경 내용

- 계획 승인 시 각 업무에 `input_task_ids`를 저장한다. 새 AI 관리자 계획은 이전 단계 ID를 `input_task_ids`로 명시해야 하며, 누락·잘못된 형식·현재/미래 단계 연결은 계획 검증에서 거부한다.
- 기본 모의 계획에도 단계별 ID 연결을 추가했다. 새로 승인한 기존 형식 계획은 승인 시 입력 설명과 앞선 작업 이름·산출물을 비교해 연결 ID를 만들어 저장한다.
- 업무 실행은 저장된 ID를 기준으로 선행 업무를 찾아 결과를 `previous_results`에 전달한다. 각 전달 항목에 출처 `task_id`도 포함한다. 저장된 ID가 없는 기존 업무는 예전 입력명 연결 규칙으로 읽어 호환하며, 기존 프로젝트 파일을 일괄 수정하지 않는다.
- 연결된 필수 선행 업무가 완료되지 않았거나 결과가 없거나 공백뿐이면 엔진을 실행하지 않고 한국어 오류로 안내한다.
- 프로젝트 결과와 저장 형식의 기존 필드는 유지했다. 이번 변경은 새 업무를 승인할 때 링크 필드를 추가하고 실행 경로에서 이를 읽는 방식이다.

## 테스트 및 확인

- 새 `tests/test_explicit_workflow_links.py`에서 시장 조사 → 제품 기획 → 개발의 모의 실행을 수행해 각 후속 실행에 올바른 작업 ID와 결과가 전달되는지 확인한다.
- 같은 테스트에서 필수 선행 결과 필드가 없거나 공백인 경우 후속 실행이 차단되고 오류가 표시되는지 확인한다.
- 계획 단계의 선행 ID 유효성, 계획 승인 시 링크 저장, 기존 실행 실패·빈 결과·재검토·UI·실행 엔진 동작도 회귀 테스트로 확인했다.
- 명령: `python -B -m unittest tests.test_execution_engine tests.test_project_ui tests.test_explicit_workflow_links tests.test_manager_plan tests.test_manager_plan_persistence tests.test_task_execution_persistence tests.test_company_workflow_e2e tests.test_quality_review_flow tests.test_downstream_review`
- 결과: 51개 테스트 통과 (`OK`).
- `git diff --check` 통과.
- 실제 AI API 호출은 없었다. 실행 엔진과 기존 통합 흐름은 모의 처리로 검증했다.
- `tests/test_smoke.py`는 애플리케이션 서버를 별도 실행하는 테스트여서 이번 데이터 보존 검증에서는 실행하지 않았다.

## 데이터 보존 및 변경 파일

- 기존 프로젝트 JSON, 업무 결과, 백업은 읽기·수정·삭제하지 않았다.
- 변경 파일: `app.py`, `manager_plan.py`, `tests/test_explicit_workflow_links.py`, `tests/test_manager_plan.py`, `tests/test_manager_plan_persistence.py`, `tests/test_task_execution_persistence.py`, `reports/explicit_workflow_links_report.md`.

## 한계

- 기존 업무 데이터에 `input_task_ids`가 없으면 실행 시 한 번 입력명 규칙으로 연결 대상을 계산한다. 기존 데이터 파일에는 링크를 자동 기록하지 않는다.
- 이미 저장된 구형 계획에서 ID가 빠진 경우 승인 단계에서 입력 설명을 이용해 링크를 만들어 호환한다. 새 AI 응답에서 ID를 빠뜨리면 계획 검증이 거부한다. 입력 설명과 실제 의도가 다르면 자동으로 의미를 알아낼 수 없으므로, 향후에는 계획 화면에서 연결을 검토할 수 있는 기능이 유용하다.
