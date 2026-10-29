# AI Company OS 웹 화면 점검

## 기준 커밋과 도구

- GitHub `main` fetch 결과, 로컬 `main` 및 `origin/main` 기준 커밋은 `e51803cda20fc2ac6b556a1cb88e42979afed582`로 같았다.
- 사용 가능한 도구 목록에서 브라우저 자동화 도구를 확인하지 못했다. 따라서 브라우저의 실제 시각적 레이아웃과 사용자 클릭 동작은 미확인이다.
- 실제 AI API와 외부 유료 API는 호출하지 않았다.

## HTTP 화면 검증

임시 디렉터리에만 모의 프로젝트 두 개를 저장하고, 테스트 전용 loopback HTTP 서버에 GET 요청을 보냈다. 실제 업무 데이터 폴더는 테스트 저장 대상으로 사용하지 않았다.

- `GET /` — 두 프로젝트가 목록에 보임: 통과.
- 승인 대기 프로젝트의 `GET /project/pending-ui-check` — 계획 승인 대기 상태, 단계와 승인 버튼 표시: 통과. 승인 버튼 클릭 자체는 이번 HTTP GET 점검에서 실행하지 않았다.
- 승인된 프로젝트의 `GET /project/workflow-ui-check` — 승인 상태, 대기·재검토·완료 건수, 재검토 사유, 저장 결과 표시: 통과.
- `GET /report/workflow-ui-check` — 최종 보고서, 업무별 결과 및 재검토 상태·사유 표시: 통과.

## 테스트 결과

- `PYTHONDONTWRITEBYTECODE=1 python -B -m unittest tests.test_project_ui tests.test_company_workflow_e2e -v` — 통과, 3건.
- `PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -v` — 통과, 36건.
- `git diff --check` — 통과.
- 기존 `tests/test_smoke.py`는 unittest 자동 검색 대상이 아닌 별도 함수다. 이번 점검은 임시 HTTP 서버에 대해 화면 경로 4개를 직접 GET해 확인했다.

## 코드 변경 및 데이터 보존

기존 코드 변경은 필요하지 않았다. 이번 점검에서 추가하는 파일은 본 보고서뿐이다. 테스트 fixture는 임시 디렉터리에 저장했고, 기존 프로젝트 데이터는 삭제·초기화·수정하지 않았다.

## 미확인 사항

- 실제 브라우저에서의 CSS 레이아웃, 화면 크기별 표시, 키보드·마우스 상호작용은 브라우저 도구가 없어 확인하지 못했다.
- 이번 HTTP 요청은 GET 전용이어서 화면의 승인 버튼을 실제로 누르지는 않았다. 승인 POST 경로는 전체 테스트의 모의 검증에서 확인됐다.

실제 API 호출 여부: 없음.
