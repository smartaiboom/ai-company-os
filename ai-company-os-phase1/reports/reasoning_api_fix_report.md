# Reasoning API 오류 수정 보고서

작업일: 2026-10-29
오류: `Reasoning is mandatory for this endpoint and cannot be disabled.`

## 변경 사항

- `execution_engine.py`: 요청 본문에서 `reasoning: {"enabled": false, "exclude": true}`와 `chat_template_kwargs: {"enable_thinking": false}`를 제거했다. reasoning 설정을 강제로 비활성화하지 않아 모델 또는 라우트가 요구하는 reasoning을 허용한다.
- `tests/test_execution_engine.py`: 실제 HTTP 연결 없이 실행기 요청을 모의하고, payload가 기존 `openrouter/free` 모델을 유지하며 두 비활성화 파라미터를 보내지 않는지 확인하는 회귀 테스트를 추가했다.
- `validate_openrouter_free_model()` 및 요청 전 모델 검사는 변경하지 않았다. `openrouter/free` 외 모델은 기존과 같이 요청 전에 거부된다. 유료 모델 fallback이나 대체 경로를 추가하지 않았다.

## 검증

실행한 명령 및 결과:

1. `python -m unittest tests.test_execution_engine` — 첫 실행은 새 테스트 픽스처에 비 ASCII bytes literal이 있어 SyntaxError로 실패했다. 픽스처를 ASCII JSON으로 수정했다.
2. `python -m unittest tests.test_execution_engine` — **13개 테스트 통과 (OK)**.
3. `python -m unittest tests.test_company_workflow_e2e` — **1개 테스트 통과 (OK)**.
4. `git diff --check` — 오류 없음.

회귀 테스트는 `execution_engine.urlopen`을 mock 처리하며 외부 연결을 하지 않는다. 실제 AI API 호출은 없었다. 따라서 해당 API 제공자에서 오류가 해결됐는지는 이번 작업에서 실호출로 검증하지 않았다.

## 변경 파일 및 보존 사항

- 변경: `execution_engine.py`, `tests/test_execution_engine.py`, `reports/reasoning_api_fix_report.md`.
- 프로젝트 데이터, 기존 작업 결과, 백업 파일, 비밀값: 변경·열람하지 않았다.
- 커밋 및 푸시는 이 보고서 작성 시점 이후 별도로 진행한다.
