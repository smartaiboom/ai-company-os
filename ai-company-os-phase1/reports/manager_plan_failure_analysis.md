# 관리자 계획 생성 실패 분석 및 수정 결과

## 확인한 실패

`reports/manager_plan_test_20261029.md`에는 실제 관리자 계획 생성 API가 HTTP 200을 반환했지만 계획 단계 검증에서 `ValueError`가 났다고 기록되어 있다. 당시 예외 상세와 API 응답 본문은 보존되지 않았다. 따라서 실제 응답에서 어떤 필드 또는 단계 개수가 규격과 달랐는지는 확인할 수 없다.

코드를 확인한 결과 `_request_ai_plan()`은 응답 JSON을 해석한 뒤 최상위 `stages`만 `validate_stages()`에 전달한다. 응답이 중첩된 `plan.tasks` 형태이면 `parsed.get("stages")`는 `None`이 되고, 검증기는 이를 작업 수가 2~10개가 아닌 경우로 처리해 다음 오류를 낸다.

`AI 관리자 계획의 작업 수는 2개 이상 10개 이하여야 합니다.`

이 형식 차이를 재현하는 모의 API 응답 테스트를 수정 전에 실행했고, 위 `ValueError`로 실패하는 것을 확인했다. 이 재현 형식은 원래 API 응답의 원문이 아니므로 실제 응답도 같은 형태였다고 단정하지 않는다.

## 수정 내용

- `manager_plan.py`: 응답 정규화 단계를 추가했다. 중첩 `plan`, `tasks`/`steps` 별칭과 `task_name`/`title`, `input`, `deliverable`/`result`, `risk_note`/`risks` 같은 동등한 필드 표기를 기존 엄격한 검증 전에 정규화한다. 단수 입력 문자열은 입력 목록 하나로 바꾼다.
- 단계 수(2~10)와 정규화된 필수 필드 검증은 계속 적용한다.
- 실행기와 관리자 계획 생성기의 `openrouter/free` 제한 코드는 유지했다. 이 작업에서는 유료 모델 fallback을 추가하지 않았다.
- `tests/test_manager_plan.py`: 가짜 HTTP 응답으로 중첩된 `plan.tasks` 및 단수 `input` 응답을 재현하고, 계획 변환과 요청 1회 호출을 검증하는 모의 테스트를 추가했다.
- `execution_engine.py`, `tests/test_execution_engine.py`: 기존 미커밋 무료 모델 보호 변경도 함께 기록해 main에 통합할 때 보호 코드가 빠지지 않도록 한다.

## 테스트 및 결과

- 수정 전 재현: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests python -B -m unittest test_manager_plan.ManagerPlanTests.test_api_plan_accepts_nested_tasks_and_singular_input_response -v` — 실패 확인. `validate_stages(None)`에서 작업 수 조건 `ValueError`가 발생했다.
- 수정 후 같은 집중 테스트 — 통과.
- 전체 유닛 테스트: `PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -v` — 26개 통과.
- 실제 API 호출: 없음. 전체 응답 본문과 비밀 정보는 로그나 이 보고서에 기록하지 않았다.
- 기존 업무 데이터 변경: 없음.

## 변경 파일 및 통합

- `execution_engine.py`
- `manager_plan.py`
- `tests/test_execution_engine.py`
- `tests/test_manager_plan.py`
- `reports/manager_plan_failure_analysis.md`

검증이 통과해 위 관련 파일만 커밋·푸시하고 main에 통합한다. 다른 작업 트리 변경은 포함하지 않는다.
