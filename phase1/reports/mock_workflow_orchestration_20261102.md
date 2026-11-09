# 승인 경계를 지키는 mock 업무 자동 진행

작성 시점: 2026-11-02 11:13 KST
기준 커밋: `d88c162` (fast-forward pull 후 main/origin/main 일치)

## 구현 범위

- `app.py`: 기존 `/task/execute` 본문을 `execute_project_task`로 옮겨 수동 실행과 자동 진행이 선행 ID·결과·승인 검사, 수정 의견 전달, 실패/빈 결과 보존, 성공 이력 저장을 공유하도록 했다. 실패 예외는 `TaskExecutionFailure`로 표시하여 기존 수동 실행 오류 화면의 실패 상태 표시도 유지했다.
- `run_mock_workflow`와 `/workflow/run` POST를 추가했다. 시작 전 엔진이 정확히 mock인지 확인하고 실제 엔진·호환 별칭·불명확한 모드는 HTTP 400으로 거절한다. 자동 경로는 설정 기반 실제 엔진 선택 함수 대신 `execute_task_mock`을 명시적으로 사용하므로 실제 AI 호출 경로를 선택하지 않는다.
- 승인된 계획에서 순서대로 다음 업무를 선택한다. 매 단계 저장값을 다시 읽으며 완료·결과·검토 상태를 확인한다. 검토 대기, 수정 요청, 실패, 빈 선행 결과, 누락/잘못된 연결, 진행 중 상태, 실행할 업무 없음에서 멈추고 한국어 이유를 저장한다. 실패·수정 요청의 자동 재시도는 하지 않으며 개별 업무 확인·수정 후 별도 재개 요청이 필요하다.
- 한 요청은 최대 5개 업무를 실행하며 실행한 ID를 기억해 같은 요청 내 중복을 막는다. 새 결과가 승인 대기가 되면 즉시 정지한다. 사용자 승인 후 새로운 POST로 재개한다. 마지막 결과처럼 후속 의존성이 없는 업무는 기존 정책대로 별도 승인이 필요하지 않다.
- `/workflow/run`에도 기존 프로젝트별 비차단 잠금을 적용했다. 전체 진행 요청 동안 같은 프로젝트의 수동·자동·검토 변경 요청은 409로 거절하고, 다른 프로젝트 요청은 처리할 수 있다.
- 프로젝트 상세 UI에 mock 전용 시작·재개 버튼, 상한·승인 경계 설명, 마지막 중단 이유를 추가했다. 기존 처리 모달과 오류 안내를 재사용한다.
- 기존 JSON 필드를 보존하면서 선택적 `workflow` 필드(reason, executed_task_ids, stopped_at)와 `workflow_stopped` 이력을 추가한다. 기존 데이터의 일괄 변경이나 마이그레이션은 없다. 시각은 기존 `now()`의 KST를 사용한다.

변경 파일: `app.py`, `tests/test_mock_workflow_orchestration.py`, `codex_tasks/task_history.md`, 이 보고서. 실행 엔진 코드·무료 모델 검사·기존 업무 데이터·백업·미추적 기존 파일은 변경하지 않았다. 외부 의존성 설치 없음.

## 검증 명령과 실제 결과

공통 함수 추출 후:

```text
python -B -m unittest tests.test_concurrent_execution_safety tests.test_task_execution_persistence tests.test_review_approval_gate
```

17개 통과.

신규 테스트 초안:

```text
python -B -m unittest tests.test_mock_workflow_orchestration
```

당시 12개 통과. 초안에서 기존 TestCase 클래스를 직접 import하여 기존 5개도 함께 수집된 값이다. 이후 모듈 import로 바꿔 중복 수집을 제거했다. 신규 테스트는 7개이다.

최종 검증:

```text
python -B -m unittest tests.test_mock_workflow_orchestration tests.test_concurrent_execution_safety tests.test_execution_engine tests.test_project_ui tests.test_explicit_workflow_links tests.test_manager_plan tests.test_manager_plan_persistence tests.test_task_execution_persistence tests.test_company_workflow_e2e tests.test_quality_review_flow tests.test_downstream_review tests.test_review_approval_gate
```

**71개 통과 (OK): 기존 64개 + 신규 7개.** `git diff --check` 통과. 미해결 테스트 실패 없음.

신규 테스트는 계획 승인→첫 업무→승인 대기 정지→재요청만으로는 실행 안 됨→사용자 승인→재개→선행 결과 전달, 실제/별칭/불명확한 모드의 저장 변경 없는 거절, 미승인 계획·누락 연결·빈 선행 결과·수정 요청 정지, 실패/빈 결과 보존 및 자동 재시도 금지, 상한 및 완료 업무 재실행 방지, 중복 자동/수동 요청 거절과 다른 프로젝트 동시 진행을 확인했다. 렌더링된 HTML의 버튼과 중단 이유도 검사했다.

저장은 TemporaryDirectory, 실행은 mock이며 실행·계획 네트워크 함수를 금지 mock으로 바꿨다. 소켓이나 테스트 네트워크 접근은 없다. 실제 AI API 호출 없음. 실제 인증 값·비밀 설정 파일 조회·출력 없음. 사용자 업무 경로를 사용하는 smoke 테스트, HTTP·브라우저 회귀는 이번에 실행하지 않았다. Git 원격 동기화·푸시는 요청대로 수행한다.

## 제한과 다음 단계

- 동기식 mock 전용 요청이다. 실제 모델 자동 호출, 품질 자동 판정, 수정 루프, 외부 조사·코드 실행 도구, 장시간 백그라운드 작업은 구현하지 않았다.
- 잠금은 동일 프로세스의 앱 POST 경로만 보호한다. 다중 프로세스, 재시작 후 복구, 영속 요청 ID 기반 멱등성은 제공하지 않는다. 같은 프로젝트의 변경은 진행 중 거절되며 사용자 재시도가 필요하다.
- 구형 데이터는 기존 입력명 연결 호환 규칙을 유지한다. 연결 의미의 완전성이나 결과 품질을 보장하지 않는다. 업무는 기존 순서 게이트를 따라 직렬 처리한다.
- 중단 이유는 마지막 진행 요청 시점의 기록이다. 사용자 승인 후에도 자동 갱신하지 않으며 새 재개 요청이 최신 상태를 판정한다. 실제 엔진 거절은 저장하지 않고 오류 화면으로 안내한다.
- 브라우저에서 버튼을 직접 클릭하는 검증은 하지 않았다. 다음 단계는 mock 흐름의 격리된 HTTP/브라우저 확인 및 최종 산출물 확정 절차 검토다. 실제 모델 확대는 별도 명시적 승인 작업이다.

동일 경로 보고서가 없음을 확인한 뒤 작성했으며 저장 후 재독했다. 관련 파일만 커밋·푸시하고 원격 SHA와 보고서 일치를 확인한다. 최종 커밋은 완료 응답으로 제공한다.
