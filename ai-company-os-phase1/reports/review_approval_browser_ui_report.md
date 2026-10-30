# 검토 승인 게이트 브라우저 UI 회귀 검증 보고서

작성일: 2026-10-30

## 결과 요약

Playwright 1.64.1과 Chromium을 준비해 검토 승인 UI를 실제 헤드리스 브라우저에서 확인했다. 브라우저 테스트 1개와 전체 `unittest` 60개가 통과했다. 처리 중 모달과 입력 차단, 중복 제출 방지, 리다이렉트 뒤 스크롤 복원, 승인/수정 요청 상태의 화면·저장 일치를 확인했다.

## 브라우저 환경 준비

- `requirements-browser-test.txt`에 선택형 브라우저 테스트 의존성 `playwright==1.64.1`을 고정했다. 기본 unittest 환경에서 Playwright가 없으면 브라우저 테스트는 skip되어 기존 테스트 실행을 막지 않는다.
- Playwright Python 패키지와 Chromium 156.0.8078.4 바이너리는 `/tmp/review_approval_browser_env` 아래에 설치했다. 저장소에는 브라우저 바이너리를 넣지 않았다.
- Chromium 실행에 필요한 OS 라이브러리는 승인된 `python -m playwright install-deps chromium`으로 설치했다. Ubuntu 패키지 설치 결과 67개 신규 패키지와 14개 패키지 업데이트, 추가 디스크 사용량 약 299 MB가 보고됐다.
- 실제 AI API는 호출하지 않았다.

실행한 환경 준비 명령:

```text
python -m pip install --target /tmp/review_approval_browser_env 'playwright==1.64.1'
env PYTHONPATH=/tmp/review_approval_browser_env PLAYWRIGHT_BROWSERS_PATH=/tmp/review_approval_browser_env/browsers python -m playwright install chromium
env PYTHONPATH=/tmp/review_approval_browser_env PLAYWRIGHT_BROWSERS_PATH=/tmp/review_approval_browser_env/browsers python -m playwright install-deps chromium
```

## 실제 브라우저에서 확인한 동작

`tests/test_review_approval_browser_ui.py`는 loopback HTTP 서버를 사용하고 프로젝트·아티팩트 디렉터리를 테스트별 임시 경로로 교체한다. 후속 업무 실행기는 오류를 내도록 모의 처리해 검토 POST가 실행 엔진을 호출하지 않음을 보장했다.

- 검토 대기 상태와 승인 폼에 표시된 대상 업무 ID가 `TASK-011`임을 확인했다.
- 느린 승인 응답 동안 모달과 진행 표시가 보이고, 배경 콘텐츠가 inert/aria-busy 상태이며, 페이지 스크롤이 잠기고, 제출 버튼이 비활성화되어 `승인 중...`으로 표시됨을 확인했다. 모달은 1200×720 뷰포트를 덮었다.
- 요청이 대기 중일 때 두 번째 submit 이벤트를 보내도 실제 서버 요청이 하나뿐임을 확인했다.
- 승인 완료 후 모달과 페이지 잠금이 해제되고 서버 저장 상태와 화면이 `검토 승인됨`으로 일치했다.
- 응답 뒤 해당 업무 행을 중심으로 스크롤이 복원되고 세션 복원 키가 소비됨을 확인했다.
- 수정 의견을 제출한 뒤 화면과 저장 JSON에 `수정 요청됨` 및 의견이 일치함을 확인했다.

## 실행한 테스트 및 결과

```text
env PYTHONPATH=/tmp/review_approval_browser_env PLAYWRIGHT_BROWSERS_PATH=/tmp/review_approval_browser_env/browsers python -B -m unittest tests.test_review_approval_browser_ui
```

결과: 실제 Chromium 브라우저 회귀 테스트 1개 통과.

```text
env PYTHONPATH=/tmp/review_approval_browser_env PLAYWRIGHT_BROWSERS_PATH=/tmp/review_approval_browser_env/browsers python -B -m unittest discover -s tests
```

결과: 전체 테스트 60개 통과(Chromium 브라우저 테스트 1개 포함). `tests/test_smoke.py`의 함수형 테스트는 `unittest discover` 대상이 아니며, 앱 기본 저장 경로를 격리하지 않아 별도 실행하지 않았다.

```text
git diff --check
```

결과: 통과.

초기 브라우저 시작 시 `libatk-1.0.so.0` 등 시스템 라이브러리가 없어 실행되지 않았다. Playwright 의존성을 설치한 후 브라우저 테스트를 실행했고, 테스트 코드의 동적 버튼 문구 locator를 안정적인 폼 locator로 수정한 최종 실행은 통과했다. 이 과정에서 운영 코드 변경은 없었다.

## 변경 파일

- `requirements-browser-test.txt`: 선택형 Playwright 테스트 의존성 고정.
- `tests/test_review_approval_browser_ui.py`: 임시 저장 데이터, 모의 실행기, loopback 서버를 사용하는 실제 Chromium UI 테스트.
- `reports/review_approval_browser_ui_report.md`: 환경, 검증 결과 및 제한 기록.
- `codex_tasks/next_step.md`: 브라우저 UI 회귀 작업 완료 상태.
- `codex_tasks/task_history.md`: 완료 사실, 테스트 결과, 보고서와 커밋 기록.

테스트는 임시 디렉터리만 사용했다. 기존 사용자 변경·미추적 파일·프로젝트 JSON·업무 결과·백업은 수정, 삭제 또는 스테이징하지 않았다. 실제 AI API 호출은 없었다.

## 미확인 사항

- 검증은 Ubuntu 24.04의 헤드리스 Chromium 한 종류에서 실행했다. 다른 브라우저 엔진, OS, headed 화면에서의 표시 차이는 확인하지 않았다.
- 테스트에는 실제 업무 데이터를 사용하지 않았다.

보고서를 저장한 뒤 다시 읽어 환경 준비, 브라우저 테스트, 전체 회귀 결과, 임시 데이터 격리 및 API 호출 여부를 확인했다.
