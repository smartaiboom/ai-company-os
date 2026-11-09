# AI Company OS 웹 화면 표시 점검

## 점검 범위와 결과

프로젝트 상세 화면과 최종 보고서 화면의 관리자 계획, 승인 상태, 업무 상태, 저장 결과 및 재검토 상태를 확인했다. 화면 테스트는 임시 디렉터리에 모의 프로젝트 데이터를 저장해 수행했다. 실제 AI API 호출은 없었고 기존 프로젝트 업무 데이터를 사용하거나 변경하지 않았다.

확인 중 발견한 오류: 재검토 대상으로 지정된 업무의 재실행이 실패하면 업무 상태는 `진행 중`이 되고 `review_required`는 유지된다. 상세·보고서 화면은 재검토 건수를 상태 문자열 `재검토 필요`만으로 계산해 이 업무가 재검토 건수에서 빠지고 진행 중으로만 표시될 수 있었다. 최종 보고서의 업무별 행에도 재검토 사유가 표시되지 않았다.

## 변경 파일

- `app.py` — 공통 재검토 판정 함수를 추가했다. 상세 화면의 업무 집계와 보고서 집계가 상태 문자열 또는 `review_required` 플래그를 반영하도록 수정했다. 재검토 플래그가 남은 업무는 재실행 중이어도 재검토로 집계하고 진행 중 건수에서는 제외한다. 최종 보고서의 업무 행에 재검토 표시와 사유를 추가했다.
- `tests/test_project_ui.py` — 승인 대기 계획 표시, 승인 후 상태, 업무 결과, 재실행 중 재검토 표시와 보고서 행을 검증한다.
- `reports/project_ui_audit_20261029.md` — 본 보고서.

## 테스트

- `PYTHONDONTWRITEBYTECODE=1 python -B -m unittest tests.test_project_ui tests.test_company_workflow_e2e tests.test_quality_review_flow tests.test_manager_plan_persistence tests.test_task_execution_persistence -v` — 통과, 10건.
- `PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -v` — 통과, 36건.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests python -B -c 'from test_smoke import test_health_endpoint; test_health_endpoint(); print("HTTP health smoke test: PASS")'` — 통과.
- `git diff --check` — 통과.

## 오류 및 미해결 사항

새 화면 테스트의 첫 실행에서 재검토 건수가 잘못 표시되는 현상을 재현했다. UI 집계 코드를 수정한 후 관련 테스트와 전체 테스트를 재실행해 통과했다. 해결되지 않은 테스트 실패는 없다.

## Git 및 API

실제 AI API는 호출하지 않았다. 작업 결과는 검증된 코드·테스트·보고서 파일만 스테이징해 현재 `main`에 커밋·푸시한다. 기존의 다른 미추적 파일과 데이터는 포함하지 않는다. 커밋 ID와 원격 반영 여부는 완료 응답에 기록한다.
