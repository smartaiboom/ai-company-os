# AI 응답 중단 및 처리 중 UI 점검 보고서

작업일: 2026-10-29

## 1. AI 응답 중단 오류

### 확인된 사실

- `execution_engine.py`는 요청에 `max_tokens=4096`을 설정한다. 값은 `MAX_RESPONSE_TOKENS` 상수로 유지했다.
- 현재 오류 문구는 응답의 `choices[0].finish_reason`이 정확히 `length`일 때 발생한다. 이 분기에서 실행기는 예외를 내고 결과 문자열을 반환하지 않는다.
- 앱은 실행 함수가 정상 반환한 뒤에만 새 `task["result"]`를 저장한다. 예외 경로는 작업을 완료 상태로 두지 않으며, 다음 작업의 입력 매칭도 완료 상태와 결과가 있는 선행 작업만 선택한다. 따라서 잘린 새 응답은 정상 결과로 저장되거나 후속 작업에 전달되지 않는다.
- 저장소에서 최근 실제 실행 로그 파일은 찾지 못했다. 이전 안전성 응답 진단은 safety-only 및 빈 응답 분기에 있었고, `finish_reason=length` 분기에서는 토큰 진단을 기록하지 않았다.

### 판단할 수 없는 원인

`finish_reason=length`는 응답이 길이 제한으로 끝났다는 사실을 보여주지만, 이전 실패 응답에 대한 `usage.completion_tokens` 기록이 없어 다음을 구분할 수 없다:

- 요청의 `max_tokens=4096`에 도달했는지
- 라우팅된 모델/제공자의 더 낮은 출력 한도 또는 문맥 한도에 걸렸는지
- 응답에 사용량 메타데이터가 포함되어 있었는지

따라서 한도를 추측으로 높이지 않았다. 다음 빈 응답, 안전성 판정 또는 길이 중단 오류에서만 제한된 진단 로그를 남기도록 했다. 로그에는 종료 사유, 응답 필드 이름, 본문 문자 수/빈 여부, 요청 `max_tokens`, 응답이 제공하는 경우 prompt/completion/total token 수를 포함한다. 토큰 수가 없거나 유효하지 않으면 `missing`으로 남긴다. 응답 전문, 프롬프트, 입력 자료, 키와 인증 정보는 기록하지 않는다.

모의 회귀 테스트는 `finish_reason=length`, `request_max_tokens=4096`, `completion_tokens=4096`인 응답을 재현해 중단 오류와 제한된 진단값을 확인한다. 이는 테스트 픽스처에서의 동작 검증이며 실제 실패가 한도에 도달했다는 증거는 아니다.

## 2. 처리 중 UI

주요 POST 폼에 공통 처리 스크립트를 연결했다:

- 프로젝트 생성
- 프로젝트 정보/상태 저장
- 관리자 계획 작성 및 승인·수정 요청
- 작업 상태/결과 저장
- 작업 실행

전송을 시작하면 해당 버튼을 비활성화하고 폼별 안내(예: `저장 중...`, `실행 중...`)를 표시하며, 같은 폼의 중복 제출을 막는다. 서버가 정상 처리 후 이동 응답을 보내면 해당 화면으로 이동한다. 서버 오류 또는 네트워크 오류에서는 기존 버튼 문구와 활성 상태를 복구하고, 접근 가능한 오류 안내를 폼 아래에 표시한다. 기존 URL, POST 필드, 서버 저장 방식은 유지했다.

## 테스트 및 변경 기록

실행 명령:

```text
python -m unittest tests.test_execution_engine tests.test_project_ui tests.test_company_workflow_e2e tests.test_task_execution_persistence
```

결과: **22개 테스트 통과 (OK)**. 이 중 실행기 모의 응답은 길이 중단과 token usage 진단을 확인하며, UI 테스트는 주요 폼 표시·중복 제출 차단·오류 복구 경로의 렌더링 코드를 확인한다. 실제 AI API 호출은 없었다.

- `git diff --check` — 통과.
- 변경 파일: `app.py`, `execution_engine.py`, `tests/test_execution_engine.py`, `tests/test_project_ui.py`, `reports/ai_response_and_processing_ui_report.md`.
- `max_tokens` 수치와 `openrouter/free` 사전 검증은 변경하지 않았다. 유료 모델 또는 fallback 경로도 추가하지 않았다.
- 프로젝트 데이터, 기존 업무 결과, 백업 파일, 비밀값: 변경하지 않았다.
- 미확인 사항: 다음 실제 실행에서의 종료/사용량 메타데이터, 배포 브라우저에서의 실제 fetch 동작. 브라우저 실험과 외부 API 호출은 수행하지 않았다.
