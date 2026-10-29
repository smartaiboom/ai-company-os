# AI 직원 업무 검토 승인 게이트 구현 보고서

작성일: 2026-10-29

## 변경 목적

시장 조사·제품 기획처럼 다른 업무의 입력이 되는 결과를 사용자가 검토하고 승인하기 전에는 후속 업무가 실행되지 않도록 했다. 검토 대기·승인·수정 요청은 기존 업무 상태와 별도 필드로 저장한다.

## 변경 파일

- `app.py`: 검토 상태 판정, 연결된 선행 결과의 완료·내용·승인 확인, 승인/수정 요청 처리, 수정 의견의 재실행 입력 전달, 검토 폼과 표시를 추가했다. 완료된 결과가 바뀌면 승인과 기존 후속 결과를 무효화한다. 단순히 상태를 완료로 바꾸는 것만으로는 승인할 수 없으며, 최신 결과의 실행 성공 기록이 있어야 검토할 수 있다.
- `tests/test_review_approval_gate.py`: 승인 전 차단, 구형 검토 상태 처리, 승인 후 입력 전달, 수정 요청과 의견 전달, 수정 실행 후 재승인, 실패·빈 결과 보존, 선행 결과 변경, 수동 결과의 재실행을 검증한다.
- `tests/test_company_workflow_e2e.py`, `tests/test_explicit_workflow_links.py`, `tests/test_quality_review_flow.py`: 기존 업무 연결과 종단 간 흐름에 승인·재검토 단계를 반영했다.
- `tests/test_project_ui.py`: 구형 연결 결과에 검토 상태 및 승인/수정 요청 수단이 표시되는지 확인한다.
- `codex_tasks/next_step.md`: 이 지시의 상태를 완료로 갱신했다.
- `codex_tasks/task_history.md`: 완료 사실, 검증 결과, 보고서와 구현 커밋을 작업 이력에 추가했다.
- `reports/review_approval_gate_report.md`: 변경·검증 내역을 기록하고 생성 후 다시 읽어 확인했다.

기존 프로젝트 JSON은 일괄 변경하지 않았다. 모든 신규 기능 테스트는 임시 프로젝트 폴더와 모의 실행기를 사용했다. 실제 AI API는 호출하지 않았다.

## 검증 결과

실행 명령:

```text
python -B -m unittest tests.test_execution_engine tests.test_project_ui tests.test_explicit_workflow_links tests.test_manager_plan tests.test_manager_plan_persistence tests.test_task_execution_persistence tests.test_company_workflow_e2e tests.test_quality_review_flow tests.test_downstream_review tests.test_review_approval_gate
```

결과: 58개 테스트 통과.

```text
git diff --check
```

결과: 통과.

`tests/test_smoke.py`는 실행하지 않았다. 이 테스트는 저장소 안의 실제 `app.py`를 직접 실행하며 테스트 파일 주석도 격리된 복사본에서 실행하라고 명시한다. 현재 테스트 명령은 프로젝트 루트의 저장 위치를 격리하지 않으므로 기존 데이터를 건드리지 않기 위해 제외했다. 별도 격리 실행은 하지 않았다.

보고서는 파일 생성 후 다시 읽어 변경 파일·테스트 결과·API 호출 여부를 확인했다.

## 미확인 사항 및 제한

- 실제 브라우저에서 폼 배치와 사용성은 수동으로 확인하지 않았다. UI 테스트는 생성 HTML의 검토 상태와 폼을 확인했다.
- 이전 저장 데이터에 업무별 실행 성공 이력이 없으면 그 결과는 즉시 승인할 수 없다. 결과를 보존하며 업무를 다시 실행하면 성공 이력이 생긴 뒤 검토할 수 있다.
- 실제 AI API의 동작은 이번 작업에서 확인하지 않았다.
