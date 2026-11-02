# Codex 작업 이력

기록 기준: 2026-10-29. 아래 항목은 현재 확인한 GitHub `origin/main`의 커밋과 보고서에서 확인한 사실이다. 결과 본문·비밀 정보는 기록하지 않는다.

## 최근 완료 작업

### 2026-11-02 (KST) — mock 품질 형식 검토 저장·표시

- 명시적 업무 ID의 고정 제목 규칙을 순수 mock으로 평가하고 판정·근거·피드백·KST를 저장/표시한다. revision/입력/정책 지문으로 중복과 stale을 판정하며 사용자 승인·수정 의견·최종 스냅샷을 유지한다. 자동 수정·재실행 없음.
- 검증: 신규 15개 포함 전체 103개 중 102개 통과·브라우저 1개 skip. 검증 중 발견한 응답 직전 잠금 경합을 수정해 재검증했다. 임시 projects/artifacts와 mock 사용, 실제 AI API·비밀 설정 접근 없음.
- 보고서: [`mock_quality_review_implementation_20261102.md`](../reports/mock_quality_review_implementation_20261102.md). 구현 커밋은 이 항목을 추가한 커밋에서 확인할 수 있다.

### 2026-11-02 (KST) — 마지막 업무 최종 승인 및 버전 보관

- 마지막 업무에 승인·수정 요청·재실행 흐름을 적용하고, 사용자 최종 승인 시 새 JSON 스냅샷을 보관한다. 현재 성공·입력 맥락·승인·보관 파일·지문이 유효할 때만 확정으로 표시하며 변경·저장 오류 시 미확정으로 판정한다. 기존 파일 보존.
- 검증: 신규 11개 통과. 최종 전체 88개 수집 중 87개 통과, 브라우저 1개 skip. 임시 저장 경로·mock 실행·loopback HTTP만 사용, 실제 AI API 호출 없음. 개발 중 기대값·들여쓰기 오류는 수정 후 재검증했다.
- 보고서: [`final_report_approval_implementation_20261102.md`](../reports/final_report_approval_implementation_20261102.md). 구현 커밋은 이 항목을 추가한 커밋에서 확인할 수 있다.

### 2026-11-02 (KST) — mock 자동 진행 HTTP 통합 검증

- 격리된 loopback HTTP에서 승인·시작·중단·재개·선행 결과 전달·409 중복 차단 및 안전 조건을 검증했다. 운영 코드 변경 없음.
- 검증: 신규 HTTP 테스트 4개 통과. 전체 unittest 77개 중 76개 통과, 브라우저 1개는 Playwright 부재로 건너뜀. 최초 소켓 권한 오류는 승인된 동일 명령 재실행으로 해결했다. 실제 AI API 호출 없음.
- 브라우저 환경이 없어 지시서의 HTTP 대체 절차를 적용했다. 실제 화면 모달·버튼 클릭·409 표시의 브라우저 검증은 미완료다.
- 보고서: [`mock_workflow_http_browser_validation_20261102.md`](../reports/mock_workflow_http_browser_validation_20261102.md). 검증 커밋은 이 항목을 추가한 커밋에서 확인할 수 있다.

### 2026-11-02 (KST) — mock 업무 자동 진행과 승인 경계

- 명시적 시작·재개 POST로 최대 5개 업무를 진행하고 승인 대기·수정 요청·실패·입력 부족에서 정지하도록 구현했다. 단일 실행 로직과 프로젝트 잠금을 공유하며 실제 엔진 자동 진행은 거절한다.
- 검증: 신규 7개를 포함한 핵심 테스트 71개 통과, 실제 AI API 및 테스트 네트워크 호출 없음. 임시 프로젝트 경로로 격리했다.
- 보고서: [`mock_workflow_orchestration_20261102.md`](../reports/mock_workflow_orchestration_20261102.md). 구현 커밋은 이 항목을 추가한 커밋에서 확인할 수 있다.

### 2026-11-02 (KST) — 중복 업무 실행 및 동시 저장 보호

- 동시 POST 중복 실행을 임시 데이터로 재현한 뒤 동일 프로세스의 프로젝트별 비차단 잠금을 추가했다. 같은 프로젝트의 변경 경합은 HTTP 409로 안내하며 다른 프로젝트는 처리할 수 있다.
- 검증: 신규 동시성 테스트 5개를 포함한 핵심 회귀 64개 통과. 초기 재현 테스트 실패는 수정 후 해결했다. 실제 API 호출·테스트 네트워크 사용 없음.
- 보고서: [`concurrent_task_execution_safety_20261102.md`](../reports/concurrent_task_execution_safety_20261102.md). 구현 커밋은 이 항목을 추가한 커밋에서 확인할 수 있다.

### 2026-11-02 (KST) — 실행 모드 및 외부 전송 안내 정확화

- 프로젝트 상세 화면에서 mock/실제 엔진/호환 별칭/미지원 모드 안내를 구분하고 README를 갱신했다. 기존 무료 모델 제한과 실행 구조는 유지했다.
- 검증: UI·엔진·계획·저장 테스트 41개 및 업무 연결·승인 회귀 테스트 18개, 합계 59개 통과. 실제 API 호출 없음. 데이터 저장은 임시 경로로 격리했다.
- 보고서: [`execution_mode_notice_fix_20261102.md`](../reports/execution_mode_notice_fix_20261102.md). 구현 커밋은 이 항목을 추가한 커밋으로 추적할 수 있다.

### 2026-10-30 — 검토 승인 게이트 브라우저 UI 회귀 검증

- 작업: 임시 설치한 Playwright 1.64.1/Chromium으로 승인·수정 요청 UI를 실제 헤드리스 브라우저에서 검증했다.
- 검증: 브라우저 테스트 1개 및 전체 `unittest` 60개 통과, `git diff --check` 통과. 테스트 저장 경로는 임시 디렉터리이며 모의 실행기를 사용했다. 실제 AI API 호출 없음.
- 보고서: [`review_approval_browser_ui_report.md`](../reports/review_approval_browser_ui_report.md)
- 커밋: [`56ccf71`](https://github.com/smartaiboom/ai-company-os/commit/56ccf71)

### 2026-10-29 — 검토 승인 게이트 HTTP 통합 검증

- 작업: loopback HTTP 요청으로 검토 대기 차단, 실행 성공 이력 조건, 수정 의견 검증·저장, 실패·빈 결과 보존, 재승인 후 후속 전달과 HTML 검토 폼을 검증했다. 테스트 데이터는 임시 디렉터리를 사용했다.
- 검증: 전용 HTTP 통합 테스트 1개 및 전체 테스트 59개 통과, `git diff --check` 통과. 실제 AI API 호출 없음. 저장소 데이터를 참조하는 기존 `tests/test_smoke.py`는 격리가 보장되지 않아 실행하지 않았다.
- 보고서: [`review_approval_http_integration_report.md`](../reports/review_approval_http_integration_report.md)
- 구현 커밋: [`dc71244`](https://github.com/smartaiboom/ai-company-os/commit/dc71244c02e8e1f8f1a1fede7a19e4b92bc2845c)
- 다음 단계: 이 HTTP 통합 검증은 완료했다. 새 작업은 사용자 지시를 기다린다.

### 2026-10-29 — AI 직원 업무 검토 승인 게이트

- 작업: 연결된 선행 결과에 별도 검토 승인 상태를 두고 승인 전 후속 실행을 차단했다. 수정 요청 의견은 재실행 입력에 전달되며, 새 결과는 재승인 전까지 후속 업무에 전달되지 않는다. 실패·빈 결과는 기존 결과를 보존한다.
- 검증: 관련 테스트 58개 통과, `git diff --check` 통과. HTTP 스모크 테스트는 저장소 데이터 경로를 사용할 수 있어 실행하지 않았다. 실제 AI API 호출 없음.
- 보고서: [`review_approval_gate_report.md`](../reports/review_approval_gate_report.md)
- 구현 커밋: [`a67e6f8`](https://github.com/smartaiboom/ai-company-os/commit/a67e6f8dde0705dfa17736ca6c9575b2264a5129)
- 다음 단계: 사용자가 새 지시를 주기 전까지 추가 개발 작업은 시작하지 않는다.

### 2026-10-29 — 명시적 업무 연결

- 작업: 시장 조사 → 제품 기획 → 개발 결과를 `input_task_ids`로 연결하고, 필수 결과 누락 시 실행을 차단했다.
- 검증: 관련 테스트 51개 통과, `git diff --check` 통과. 실제 AI API 호출 없음.
- 보고서: [`explicit_workflow_links_report.md`](../reports/explicit_workflow_links_report.md)
- GitHub 커밋: [`33c00a2`](https://github.com/smartaiboom/ai-company-os/commit/33c00a2221f92f5548e83c9bc64b594047c8c5ef)

### 2026-10-29 — AI 직원 업무 연결 조사

- 작업: 선행 결과 전달, 실패·빈 결과 차단, 검토 및 재실행 흐름을 조사하고 개선 우선순위를 기록했다. 당시 보고서에서 검토 승인 게이트를 다음 개선으로 제안했다.
- 검증: 모의 테스트 10개 통과. 실제 AI API 호출 없음.
- 보고서: [`employee_workflow_connection_audit.md`](../reports/employee_workflow_connection_audit.md)
- GitHub 커밋: [`1e0eded`](https://github.com/smartaiboom/ai-company-os/commit/1e0eded509df869b79279fefdca75362bfb27b02)

### 2026-10-29 — 품질 검토·수정·재검토 흐름 테스트

- 작업: 선행 결과 변경으로 인한 후속 재검토, 재실행 및 최종 보고 경로를 모의 테스트로 확인했다. 품질 승인 게이트는 아직 구현되었다고 보고하지 않았다.
- 검증: 보고서 기준 집중 테스트 1개, 전체 유닛 테스트 33개, HTTP 스모크 테스트 통과. 실제 AI API 호출 없음.
- 보고서: [`quality_review_flow_20261029.md`](../reports/quality_review_flow_20261029.md)
- GitHub 커밋: [`576eeea`](https://github.com/smartaiboom/ai-company-os/commit/576eeeabf22baeb537f82c1b497b13d6653d7b6d)

## 다음 단계

- 검토 승인 게이트 구현과 격리된 HTTP 통합 검증을 완료했다. 다음 작업은 사용자가 새 지시를 주면 `next_step.md`를 갱신한 뒤 진행한다.

## 원격 확인

- 확인한 원격: `origin/main` (`https://github.com/smartaiboom/ai-company-os`).
- 조사 시점 원격 `main`과 로컬 기준 커밋: `33c00a2221f92f5548e83c9bc64b594047c8c5ef` — 일치.
- 보고서와 커밋은 `git fetch origin main`, `git show origin/main:<경로>`, `git log`로 확인했다. 기록한 테스트 결과는 각 원격 보고서에 적힌 값이다.
