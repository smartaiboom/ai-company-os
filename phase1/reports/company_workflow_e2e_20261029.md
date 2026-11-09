# 전체 관리자·직원 업무 흐름 통합 테스트

## 범위

기존 웹 POST 라우트와 계획·실행 mock 구현을 연결해 관리자 계획 생성, 사용자 승인, AI 직원 순차 실행, 결과 저장, 품질 검토, 선행 결과 수정에 따른 재검토, 최종 보고서 저장까지 확인했다. 테스트 목표는 `초보자를 위한 간단한 할 일 관리 프로그램 기획`이다.

## 변경 파일

- `tests/test_company_workflow_e2e.py` — 실제 API 네트워크 함수를 호출 금지 mock으로 대체하고, 프로젝트 JSON은 임시 디렉터리에 저장하는 종단 간 테스트.
- `reports/company_workflow_e2e_20261029.md` — 본 결과 보고서.

애플리케이션 코드는 변경하지 않았다. 통합 테스트는 `AI_ENGINE=mock`을 사용했으며, 실제 API 호출은 없었다. 기존 프로젝트 데이터는 테스트 저장 대상으로 사용하지 않았다.

## 검증 내용

- 계획이 `pending_approval` 상태로 저장되고 4개 단계가 생성됐다.
- 승인 시 단계가 순서와 이름을 유지해 4개 업무로 전환됐다.
- 4개 업무가 선행 작업 순서대로 실행되고 각 결과와 이력이 저장됐다.
- 품질 검토 결과에 검토 상태와 수정 제안이 포함됐고, 최종 보고서에 검토 결과와 미해결 확인 내용이 저장됐다.
- 완료된 초안 결과를 수정하자 검토 및 최종 보고 업무가 재검토 대상으로 표시됐다. 두 업무를 다시 실행한 뒤 모든 작업이 완료 및 재검토 해제 상태로 저장됐다.
- 관리자 계획 및 실행 엔진의 `urlopen`이 호출되지 않았음을 테스트에서 검증했다.

## 테스트 결과

- `PYTHONDONTWRITEBYTECODE=1 python -B -m unittest tests.test_company_workflow_e2e -v` — 통과, 1건.
- `PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -v` — 통과, 34건.
- 샌드박스에서 실행한 HTTP smoke 테스트는 loopback 서버에 연결되지 않아 실패했다. 권한 상승 loopback 실행으로 재확인했다: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests python -B -c 'from test_smoke import test_health_endpoint; test_health_endpoint(); print("HTTP health smoke test: PASS")'` — 통과.
- `git diff --check` — 통과.

## 오류 및 미해결 사항

첫 통합 테스트 실행에서 테스트가 모의 최종 보고서의 문구를 잘못 예상해 assertion이 실패했다. 실제 mock 출력에 맞춰 기대 문구를 수정한 뒤 통합 테스트와 전체 테스트를 다시 실행해 통과했다. 미해결 테스트 실패는 없다.

## Git 처리

테스트 통과 후 테스트 파일과 본 보고서만 스테이징·커밋·푸시한다. 기존의 다른 미추적 파일은 작업 범위에서 제외한다. 최종 커밋 ID와 원격 반영 여부는 완료 응답에 기록한다.
