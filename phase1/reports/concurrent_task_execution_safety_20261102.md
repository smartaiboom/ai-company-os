# 중복 업무 실행 및 동시 저장 안전성 개선

작성일: 2026-11-02 11:08 KST
기준: `97f8826` main/origin/main 동기화 후 작업. AGENTS, 작업 지침, 현황 분석 및 실행 모드 보고서, 관련 코드·테스트 확인.

## 재현과 변경

기존 `Handler.do_POST`는 요청마다 JSON을 읽고 상태를 판정한 후 실행·저장한다. ThreadingHTTPServer의 다른 스레드가 같은 저장 상태를 읽으면 실행기가 두 번 시작될 수 있고, 동일 `.json.tmp` 파일 및 오래된 프로젝트 객체 저장이 충돌할 수 있었다. 브라우저 JS의 중복 제출 방지만으로는 방어되지 않았다.

임시 프로젝트와 지연 mock 실행기로 첫 요청을 대기시키고 두 번째 POST 핸들러를 호출하는 테스트를 먼저 추가했다. 수정 전 명령:

```text
python -B -m unittest tests.test_concurrent_execution_safety.ConcurrentExecutionSafetyTests.test_duplicate_execution_is_rejected_before_second_engine_call
```

결과: 1개 실패. 두 번째 요청이 기대한 409 대신 303을 반환했다. 두 요청이 동일 업무의 실행기에 진입할 수 있는 경로를 재현했다. 아래 수정 후 같은 시나리오를 포함한 테스트가 통과했다. 초기 재현 실패는 해결됐으며 미해결 테스트 실패는 없다.

- `app.py`: `project_mutation_lock` 및 프로젝트별 비차단 잠금을 추가했다. `/task/execute`, `/task/review`, `/task/update`, `/update`, 관리자 계획·승인·수정 요청의 읽기→판정→실행→저장 구간을 요청 단위로 보호한다. 기존 POST 본문은 `_handle_post`로 분리해 동작을 유지했다.
- 같은 프로젝트의 변경 요청이 겹치면 로드·엔진 실행 전에 HTTP 409와 한국어 재시도 안내를 반환한다. 대기열에 쌓아 오래된 폼을 자동 적용하지 않는다. finally에서 잠금을 해제하므로 실패와 빈 응답 후에도 재시도가 가능하다.
- 잠금 등록부는 짧은 전역 잠금으로 생성만 동기화하고, 실제 처리는 프로젝트별 잠금에서 한다. WeakValueDictionary로 진행 중 요청이 사라진 프로젝트의 잠금 객체를 계속 쌓아두지 않는다. 각 요청이 잠금 객체를 참조하는 동안은 동일 객체가 유지된다.
- `tests/test_concurrent_execution_safety.py`: 소켓 없이 실제 POST 핸들러를 여러 스레드에서 호출하는 격리 테스트 5개를 추가했다.
- 이 보고서와 `codex_tasks/task_history.md`에 결과를 기록했다.

기존 JSON 구조, AI 엔진과 API 사용 방식, 무료 모델 제한, 실패 시 기존 결과 보존, 승인 전 후속 실행 차단은 변경하지 않았다. 사용자 데이터·백업·기존 미추적 파일을 수정·삭제·스테이징하지 않았다. 외부 의존성을 추가하지 않았다.

## 검증

```text
python -B -m unittest tests.test_concurrent_execution_safety
```

첫 수정 직후 당시 신규 테스트 4개 통과. 이후 반대 방향의 승인/실행 경쟁 테스트 1개를 추가해 아래 최종 명령에 포함했다.

```text
python -B -m unittest tests.test_concurrent_execution_safety tests.test_execution_engine tests.test_project_ui tests.test_explicit_workflow_links tests.test_manager_plan tests.test_manager_plan_persistence tests.test_task_execution_persistence tests.test_company_workflow_e2e tests.test_quality_review_flow tests.test_downstream_review tests.test_review_approval_gate
```

최종 결과: 64개 통과 (OK), 신규 5개 포함. `git diff --check` 통과.

신규 검증 항목:

1. 느린 실행 중 동일 업무 요청은 409, 실행기 호출·성공 이력은 1회.
2. 실행 중 승인·수정 요청·업무 결과 저장·프로젝트 정보 저장·계획 생성·다른 업무 실행이 409로 차단되고 기존 저장 결과는 보존됨. 실행 완료 후 승인은 정상 처리됨.
3. 다른 프로젝트의 업무는 첫 프로젝트 실행이 끝나기 전에 정상 완료됨.
4. 실행 오류와 빈 결과 뒤 기존 결과가 보존되고 재시도 가능함.
5. 승인 저장을 지연한 동안 후속 실행은 엔진 진입 전에 거절됨. 승인 완료 후 재시도하면 승인 상태를 보존하고 후속 실행 성공.

모든 신규 저장은 TemporaryDirectory, 실행은 mock이다. 테스트용 HTTP 소켓이나 외부 네트워크를 사용하지 않았다. 실제 AI API 호출: **없음**. 인증 정보·실제 비밀 설정은 조회·기록하지 않았다. HTTP·브라우저 회귀 및 실제 데이터 경로의 smoke 테스트는 실행하지 않았다. 기존 업무 상태/무료 모델 관련 테스트는 위 최종 명령에 포함된다.

## 보호 범위와 남은 위험

- 보호 범위는 **동일 Python 프로세스 안의 앱 POST 경로**다. 서버를 여러 프로세스로 띄우거나 외부 스크립트가 `save_project`를 직접 호출하는 경우의 잠금은 제공하지 않는다. 재시작 후 실행 식별자·멱등성·작업 복구를 제공하지 않는다.
- 같은 프로젝트의 서로 다른 업무도 저장 파일이 같으므로 동시에 변경하지 않고 409로 거절한다. 별도 프로젝트와 GET 조회는 잠금 대기 없이 처리한다. 조회는 실행 이전에 저장된 상태를 볼 수 있고 실시간 실행 진행을 보장하지 않는다.
- 작업 실행 동안 프로젝트 변경이 거절되므로 다른 탭에서도 처리 완료 후 재시도해야 한다. 기존 UI는 오류 응답의 한국어 문구를 표시한다. 이번에는 브라우저로 직접 확인하지 않았다.
- 잠금은 오래된 폼의 순차 제출이나 재시작을 넘는 요청 중복을 판별하지 않는다. 여러 프로세스·분산 실행에는 저장 계층의 동시성 제어와 지속적인 실행 ID가 별도로 필요하다.
- 성공 응답 손실 뒤 사용자의 재시도는 기존 완료 상태 검사에 의존한다. 영속적인 요청 ID 기반 exactly-once 보장은 아니다.

보고서를 작성한 뒤 재독하고 변경 범위·재현 실패 해결·최종 통과 수·제한을 확인했다. 관련 4개 파일만 커밋·푸시하며 원격 SHA 확인 결과는 완료 응답에 기록한다.
