# 업무 실행 결과 안내 문구 중복 수정 보고서

## 조사 결과

- `app.py`의 작업 실행 경로는 `execute_task(...)` 반환값이 비어 있지 않은지 검사한 뒤 `task["result"]`에 그대로 저장한다. 이 경로에서는 해당 안내 문구를 덧붙이지 않는다.
- `execution_engine.py`의 OpenAI 호환 엔진은 AI가 돌려준 `content` 뒤에 안내 문구를 추가한다.
- 따라서 AI 응답 본문 자체가 같은 안내 문구로 끝나는 경우, 본문에 있던 문구와 엔진이 추가한 문구가 연속해서 표시되는 것이 중복 원인이다.

## 수정 내용

- `execution_engine.py`에서 결과 본문 끝에 이미 붙은 동일 안내 문구를 제거한 뒤, 안내 문구를 마지막에 한 번만 추가하도록 최소 수정했다.
- 안내 문구 이외의 AI 생성 본문은 수정하거나 삭제하지 않는다.
- `app.py`, 프로젝트 데이터, 기존 업무 결과, 백업, API 설정, 모델 선택, 업무 상태 처리, 모달 및 화면 위치 복원 코드는 변경하지 않았다.

## 변경 파일

- `execution_engine.py`
- `tests/test_execution_engine.py`
- `reports/duplicate_result_notice_fix_report.md`

## 테스트 및 검증

- 명령: `python -m unittest tests.test_execution_engine tests.test_task_execution_persistence tests.test_company_workflow_e2e tests.test_quality_review_flow`
- 결과: 25개 테스트 통과 (`OK`).
- 새 모의 응답 테스트는 모델 본문에 안내 문구가 들어 있는 경우 본문이 보존되고 최종 결과의 안내 문구 개수가 1개인지 확인한다.
- `git diff --check` 통과.
- 실제 AI API 요청은 하지 않았다. 네트워크 요청은 모의 응답으로 대체했다.

## 미확인 사항

- 실제 제공자가 반환하는 응답 형식으로 API를 호출해 확인하지 않았다. 다만 실제 요청 없이 동일한 응답 본문 중복 상황을 모의 테스트로 재현하고 수정 동작을 확인했다.
