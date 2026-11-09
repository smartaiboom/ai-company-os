# 안전성 판정 응답 오류 조사 보고서

작업일: 2026-10-29

## 조사 요약

`execution_engine.py`는 API 응답을 JSON으로 해석한 뒤 `choices[0].message.content`를 우선 확인한다. 본문이 비어 있으면 `reasoning_content`, `reasoning`, `output_text`를 순서대로 대체 응답으로 확인한다(`execution_engine.py:308-323`).

내용이 문자열이면 앞뒤 공백을 제거하고 소문자로 바꾼 전체 응답이 다음 중 하나와 정확히 같을 때 실행기가 `RuntimeError`를 발생시킨다(`execution_engine.py:369-374`):

- `user safety: safe`
- `safe`
- `user safety: unsafe`

따라서 앱이 표시한 오류는 HTTP 상태 오류를 직접 의미하는 것이 아니라, JSON 응답 내용이 이 세 문구 중 하나와 일치해 실행기가 결과로 사용하지 않고 거부했다는 뜻이다. 수정 전에는 이 오류에 `AI_MODEL을 다른 지원 모델로 변경`하라는 안내가 포함되어 있었지만, 프로젝트의 `openrouter/free` 보호 규칙과 양립하지 않는 안내였다.

## 재현 및 최소 수정

모의 HTTP 응답의 `content`를 `User Safety: Safe`로 설정해 오류 조건을 재현했다. 요청은 테스트에서만 `urlopen`을 모의했으며 실제 네트워크나 AI API를 사용하지 않았다. 회귀 테스트에서 다음을 확인한다:

- 이 응답이 안전성 판정 전용 응답으로 거부된다.
- 오류 안내가 응답 내용과 라우팅된 모델의 동작을 확인하라고 알린다.
- 유료 모델 또는 다른 모델로 바꾸라는 안내가 나오지 않는다.

최소 수정으로 `execution_engine.py`의 오류 안내 문구만 중립적으로 변경했다. 판별 조건은 그대로 두어 안전성 문구가 업무 결과로 잘못 저장되지 않게 했다. `openrouter/free` 보호 검사와 요청 전 모델 검증은 변경하지 않았고 유료 모델 경로/fallback도 추가하지 않았다.

## 확인된 사실과 미확인 사항

**확인된 사실**

- 안전성 오류는 응답 내용이 정해진 세 문구 중 하나와 정확히 일치할 때 발생한다(대소문자와 앞뒤 공백은 정규화된다).
- 모의 응답 `User Safety: Safe`에서 해당 예외가 발생하는 것을 재현했다.
- 오류 안내에서 모델 변경 권고를 제거하고 미확정 원인을 조사하도록 바꿨다.
- 테스트는 `openrouter/free` 설정을 사용했고 API 요청 함수는 모의 처리했다.

**미확인 사항**

- 실제 모델/제공자가 왜 안전성 판정 문구만 반환했는지. 이는 모델 응답 내용과 라우팅된 모델의 동작에 관한 사항으로, 코드만으로 근본 원인을 확정할 수 없다.
- 실제 실패에서 원문 응답이 위 세 문자열 중 어느 것인지. 이번 조사는 사용자가 제공한 오류 설명 및 재현 가능한 코드 경로를 바탕으로 했으며 실제 실패 응답을 다시 호출하거나 로그에서 가져오지 않았다.
- 이번 문구 변경으로 외부 제공자의 응답 자체가 달라지는지. 외부 API 호출을 하지 않았으므로 제공자 수준의 해결 여부는 확인하지 않았다.

## 변경 및 검증 기록

- 변경 파일: `execution_engine.py`, `tests/test_execution_engine.py`, `reports/safety_response_error_audit.md`.
- `python -m unittest tests.test_execution_engine` — **14개 테스트 통과 (OK)**.
- `python -m unittest tests.test_company_workflow_e2e` — **1개 테스트 통과 (OK)**.
- `git diff --check` — 통과.
- 실제 AI API 호출: 없음.
- 프로젝트 데이터, 기존 작업 결과, 백업 파일, 비밀값: 변경하지 않음.
