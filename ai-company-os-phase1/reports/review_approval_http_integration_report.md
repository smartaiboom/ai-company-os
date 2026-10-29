# 검토 승인 게이트 HTTP 통합 검증 보고서

작성일: 2026-10-29

## 목표와 지시 확인

원격 `main`의 최신 `codex_tasks/next_step.md` 지시에 따라, 검토 승인 게이트를 실제 HTTP 요청·응답 경로에서 검증했다. 초기 로컬 `main`은 원격보다 2개 커밋 뒤에 있었으며, 최신 지시는 `49366af`, `a196ef5`를 fast-forward로 반영한 뒤 확인했다. 작업 중 기존 미추적 파일은 그대로 보존했다.

## 격리 및 실행 방식

- `tests/test_http_workflow_integration.py`가 `ThreadingHTTPServer`를 `127.0.0.1`의 임의 포트에서 실행하고 표준 HTTP 클라이언트로 GET/POST 요청을 보낸다.
- `PROJECTS_DIR`와 `ARTIFACTS_DIR`를 테스트별 임시 디렉터리로 지정해 저장 데이터가 저장소의 프로젝트 데이터와 분리되도록 했다.
- `execute_task`는 각 요청에서 모의 처리했다. `AI_ENGINE=mock`도 지정했다. 실제 AI API 호출은 없었다.
- 서버 소켓을 닫고 테스트 스레드 종료를 확인했다.

## 확인한 HTTP 동작

- `/health` 및 프로젝트 상세 화면이 HTTP 200을 반환한다.
- 승인 대기 선행 결과를 입력으로 쓰는 후속 업무 실행은 HTTP 400으로 차단되고 실행기는 호출되지 않는다.
- 실제 성공 실행 이력이 없는 완료 결과의 승인은 거절된다.
- 상세 HTML에 검토 상태와 `/task/review` 폼, 대상 작업 ID가 표시된다.
- 빈 수정 의견은 HTTP 400으로 거절되고, 유효한 의견은 저장된다.
- 수정 재실행 실패 및 빈 결과는 각각 HTTP 400으로 처리되며 기존 결과와 수정 요청 상태가 보존된다.
- 수정 재실행 성공 결과는 다시 검토 대기로 저장되고, 재승인 전 후속 업무는 계속 차단된다.
- 재승인 후 후속 실행은 HTTP 303으로 완료되며, 선행 업무 ID와 새 결과가 입력으로 전달된다.
- 상세 화면과 임시 JSON 저장 결과의 업무 상태·결과가 일치한다.

## 변경 파일

- `tests/test_http_workflow_integration.py`: 위 실제 loopback HTTP 흐름의 통합 회귀 테스트.
- `reports/review_approval_http_integration_report.md`: 이 검증 결과 보고서.
- `codex_tasks/next_step.md`: HTTP 통합 검증 지시의 상태를 완료로 갱신.
- `codex_tasks/task_history.md`: 완료 사실, 보고서 및 커밋을 이력에 기록.

운영 코드, 기존 프로젝트 JSON, 업무 결과와 백업은 변경하지 않았다. `tests/test_smoke.py`는 저장소의 실제 `app.py`를 subprocess로 실행하고 저장 위치를 격리하지 않으므로 실행하지 않았다. 새 통합 테스트는 같은 서버 핸들러를 임시 저장 경로로 격리해 HTTP 경로를 확인했다.

## 테스트 결과

```text
python -B -m unittest tests.test_http_workflow_integration
```

결과: HTTP 통합 테스트 1개 통과. 승인 전 차단·검증 거절은 HTTP 400, 처리 완료 리다이렉트는 HTTP 303, 조회는 HTTP 200을 반환했다.

```text
python -B -m unittest discover -s tests
```

결과: 59개 테스트 통과.

```text
git diff --check
```

결과: 통과.

격리 제한 안에서는 loopback 소켓 생성이 금지되어 서버 시작이 실패했다. 테스트는 임시 디렉터리만 사용함을 확인한 뒤, 승인된 격리 제한 밖 실행으로 동일 테스트를 통과시켰다. 이는 로컬 loopback 요청이며 외부 네트워크 호출이 아니다.

## 미확인 사항

- 브라우저에서 처리 모달, 중복 제출 방지, 스크롤 복원과 실제 화면 배치를 자동화해 확인하지 않았다. 이 검증은 서버 HTTP 경로와 HTML 응답을 대상으로 한다.
- 실제 AI 제공자 연결은 호출하지 않았고 검증 범위에도 포함하지 않았다.

보고서를 저장한 뒤 다시 읽어 변경 파일·격리 방법·실행 결과·API 호출 여부를 확인했다.
