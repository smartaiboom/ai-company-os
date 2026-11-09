# 최종 결과 승인 및 불변 JSON 버전 보관 구현

작성: 2026-11-02 12:03 KST
기준 커밋: `53766d38eaa8da38e2fceb888adc5373f9612101` (fast-forward pull 후 main/origin/main 일치)

## 실제 구현

- `app.py:task_needs_approval`은 기존 후속 연결 또는 tasks 배열 마지막 업무를 승인 대상으로 판정한다. 업무명은 사용하지 않는다. 기존 연결 판정 함수의 의미는 유지했다.
- 단일 수동 실행, 후속 재검토, 결과 편집, 검토 폼과 POST, mock 자동 진행에 공통 판정을 적용했다. 마지막 결과도 성공 후 pending이며 승인·수정 요청 폼이 생긴다. 자동 진행은 최종 승인 대기에 정지한다. 수정 의견 전달, 실패·빈 결과의 기존 결과 보존, 승인 전 후속 차단은 기존 경로를 재사용한다.
- `validate_final_result`는 업무 ID 유일성, 계획 승인(계획이 있는 경우), 전체 완료·비공백 결과·재검토 해제, 기존 필수 입력의 승인, 최종 업무의 최신 성공 이력 및 실행 당시 입력 맥락을 확인한다. 마지막 업무 실행에 execution_context 지문을 저장해 성공 후 목표·계획·선행 결과·마지막 업무 지시가 달라졌으면 승인 전에 재실행을 요구한다. 구형 데이터는 읽기 가능하지만 실행 맥락이 없으면 재실행 후 최종 승인해야 한다.
- `archive_final_report`는 사용자 최종 승인 후 프로젝트별 `data/artifacts/{id}/final_reports/v000001.json` 형태의 새 파일을 배타적 생성(x 모드)한다. 번호는 기존 파일과 현재 참조 버전의 최대값 다음이다. 과거·미참조·실패 파일을 삭제하거나 덮어쓰지 않는다.
- 스냅샷은 당시 목표·관리자 목표·계획 단계·업무 순서/ID/지시/결과/승인 상태·최신 실행 근거, 최종 업무 ID, 버전, 사용자 승인, KST 확정 시각, 상태 지문을 담는다. 프로젝트의 final_report 참조에는 버전·최종 업무·시각·상태 지문·스냅샷 해시를 저장한다. 임의 환경 변수나 추가 데이터 키는 복사하지 않는다.
- 스냅샷 쓰기 및 JSON 재독·동일성 검증 뒤 프로젝트 승인/참조를 저장한다. 앞 단계 실패 시 저장된 프로젝트는 그대로 미확정이다. 프로젝트 저장 실패 시 파일은 미참조 상태로 남고, 재시도는 새 번호를 사용한다.
- `final_report_state`는 현재 유효한 실행·승인 상태, 스냅샷 파일, 참조 메타데이터, 파일 해시와 현재 근거 지문이 모두 맞는 경우에만 확정을 표시한다. 승인 필드만 있거나 파일이 없고 손상되면 미확정이다. GET은 판정만 하며 JSON이나 파일을 쓰지 않는다.
- `save_project`의 변경 지문 검사 및 명시적 재실행 무효화는 목표·계획·업무 결과/상태/승인 근거가 바뀌면 활성 참조를 무효화하고 필요시 마지막 업무를 재검토 대상으로 만든다. 기존 확정 파일은 보존한다. 확정된 마지막 결과에 대한 수정 요청 상태와 의견을 보존해 재실행·재승인할 수 있다. 프로젝트 표시용 status, updated_at, 무관한 history/workflow 기록은 지문에 포함하지 않는다.
- 상세 화면은 최종 확정 여부와 대상 ID·이름을 표시한다. HTML 보고서 제목은 미확정/확정 버전·KST 시각을 구분하고 진행률은 '업무 실행 완료율'로 표시한다. 실행 완료만으로 확정이라고 표시하지 않는다.

## 변경 파일

1. `app.py`: 공통 승인 판정, 마지막 업무 실행 맥락, 보관·검증·무효화, 화면 표시.
2. `tests/test_final_report_approval.py`: 신규 격리 테스트 11개.
3. `tests/test_explicit_workflow_links.py`: 마지막 업무의 기대 상태를 not_required에서 pending으로 변경.
4. `tests/test_mock_workflow_orchestration.py`: 마지막 업무 실행 후 승인 대기로 정지하는 기대값 반영.
5. `codex_tasks/task_history.md`: 구현 결과 기록.
6. `reports/final_report_approval_implementation_20261102.md`: 이 보고서.

AI 실행 엔진/무료 모델 제한/의존성/데이터 경로 구조는 변경하지 않았다. 기존 프로젝트 JSON·업무 결과·과거 스냅샷·백업·무관한 미추적 파일은 수정·삭제·스테이징하지 않았다. 기존 데이터의 자동 변환은 없다.

## 검증 방법과 결과

신규 테스트는 TemporaryDirectory의 PROJECTS_DIR와 ARTIFACTS_DIR를 모두 패치한다. 실행기는 mock이며 계획/실행 네트워크 함수는 호출 시 실패하도록 차단했다. 소켓 없이 핸들러를 호출하고, 동시 요청은 ThreadPoolExecutor와 Event로 재현한다. 테스트 키는 임의 상수이며 실제 인증 값은 읽지 않았다. 스냅샷에 이 테스트 환경 키가 포함되지 않음도 확인했다.

```text
python -B -m unittest tests.test_final_report_approval
```

최종 집중 실행: **11개 통과**. 최종 pending→수정 요청→실패/빈 결과 보존→수정 재실행→승인, KST v1, 중복 승인 거절, 선행 변경 후 v2 및 v1 바이트 보존, 목표·계획·승인·상태·순서 변경 무효화, 표시용 변경 유지, 파일 누락/손상/변조, 스냅샷 쓰기·재독 실패, 프로젝트 저장 실패와 미참조 파일 보존, 구형 결과/GET 무쓰기, 마지막 자동 진행 정지, 승인 중복/수동 실행 경합 409, 오래된 실행 맥락·중복 ID 거절, 확정 후 수정 의견 보존을 확인했다.

```text
python -B -m unittest tests.test_final_report_approval tests.test_mock_workflow_orchestration tests.test_concurrent_execution_safety tests.test_execution_engine tests.test_project_ui tests.test_explicit_workflow_links tests.test_manager_plan tests.test_manager_plan_persistence tests.test_task_execution_persistence tests.test_company_workflow_e2e tests.test_quality_review_flow tests.test_downstream_review tests.test_review_approval_gate
```

중간 핵심 실행: 신규 테스트 10개 시점에 **81개 통과**. 이후 확정 후 수정 요청 회귀 1개를 추가하고 전체 명령으로 재검증했다.

```text
python -B -m unittest discover -s tests
```

최종 결과: **Ran 88 tests, OK (skipped=1)** → 실제 통과 **87개**, Playwright 부재로 기존 브라우저 테스트 **1개 건너뜀**. 승인된 loopback 환경에서 기존 HTTP 통합 5개(기존 승인 HTTP 1개 및 mock 자동 진행 HTTP 4개)도 포함해 통과했다. 실제 업무 저장 경로를 격리하지 않은 함수형 `tests/test_smoke.py`는 별도 실행하지 않았다.

개발 중 기록: 초기 `tests.test_task_execution_persistence tests.test_review_approval_gate tests.test_mock_workflow_orchestration` 19개 실행은 마지막 업무의 예전 기대값 1개 실패였다. 신규 7개 포함 핵심 실행 78개에서도 같은 종류의 예전 not_required 기대값 1개가 실패했다. 기대값 수정 과정에서 테스트 들여쓰기 오류로 수집이 한 번 중단되어 바로 교정했다. 이후 핵심 81개 통과, 전체 87개 수집 중 86개 통과/1개 skip, 최종 신규 11개 및 전체 88개 결과로 재검증했다. 미해결 테스트 실패는 없다.

`git diff --check` 통과. 보고서와 작업 이력을 저장 후 다시 읽어 확인하고 staged diff도 점검한다. 실제 AI API 호출: **없음**. 유료 모델·외부 의존성 설치·외부 AI 네트워크 사용 없음. 전체 테스트의 네트워크는 임시 loopback HTTP뿐이다.

## 구현 한계와 남은 위험

- JSON 스냅샷 하나를 최소 보관 형식으로 사용하며 Markdown 내보내기·다중 최종 산출물·사용자 임의 최종 대상 선택은 구현하지 않았다. 마지막 업무가 의미상 전체 목표를 대표하는지는 자동 판단하지 않는다.
- 스냅샷 생성과 프로젝트 JSON 저장은 두 파일을 묶는 원자적 트랜잭션이 아니다. 프로세스 중단 시 부분 파일·미참조 파일이 남을 수 있으며 자동 삭제/복구하지 않는다. 파일 생성 성공과 프로젝트 참조 검증을 구분해 거짓 확정을 막지만 전원 장애 내구성이나 fsync 보장은 제공하지 않는다.
- 잠금은 동일 프로세스의 앱 POST만 보호한다. 여러 프로세스나 외부 파일 편집의 원자적 동시성은 보장하지 않는다. 버전 충돌은 x 모드 오류로 중단하며 덮어쓰지 않는다. 실제 다중 프로세스·전원 장애는 테스트하지 않았다.
- 내용 해시와 성공 이력은 동일 상태 추적 근거이며 사실성·AI 품질·암호학적 작성자 인증을 증명하지 않는다. 사용자 승인자는 기존 시스템과 동일하게 '사용자' 표기이며 새 인증 시스템을 추가하지 않았다.
- 목표/계획 변경은 지문·실행 맥락으로 재실행을 요구하지만 새로운 계획을 기존 tasks에 자동 재배치하지 않는다. 계획과 기존 업무의 의미적 일치 및 재계획 적용은 별도 작업이다. 기본 mock 계획·무료 모델 보호와 실제 엔진 자동 진행 금지는 유지했다.
- 보관 파일이 없거나 손상된 구형 approved 결과는 확정으로 승격하지 않는다. 상태를 변경해 개별 업무를 재실행하고 새 검토를 받아야 한다. 보관 원문 자체의 장기 보존/삭제 정책은 별도 사용자 지시가 필요하다.
- 이번에는 브라우저에서 실제 폼 클릭·모달·확정 화면 배치를 검증하지 않았다. HTML/핸들러/기존 loopback 경로만 확인했다. 실제 API 연결도 검증하지 않았다.

보고서 동일 경로가 없음을 확인한 뒤 신규 작성했다. 관련 파일만 선택적으로 커밋·푸시하고 원격 커밋 및 보고서 존재를 확인한다. 업무 데이터나 테스트가 만든 스냅샷은 Git에 포함하지 않는다.
