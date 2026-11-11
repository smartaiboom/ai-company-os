# 프로젝트 예산 — 컷룸 단일 실행 경로 연동 결과

2026-11-11T16:22:42+09:00 (KST). 기준 GitHub `040b6ab`.

## 연결한 범위

신규 영상 대본 프로젝트에만 명시적으로 켜는 경로에서 **관리자 견적 → 컷룸 대표 예산 승인/거절 → 원장 예약 → 기존 provider 전송 → 부족 요청 한 건 → 추가 승인 → 같은 업무 단계 계속**을 종단 간 오프라인으로 검증했다. 실제 운영 API 호출이나 기존 미션 01 이관은 하지 않았다.

- `companies/video/budget_video_provider.py`: 독립 marker/mode의 BudgetVideoStore/Company. 기존 Gemini35/QualityProvider/VideoProviderQualityCompany를 재사용하며 새 모드에서만 프로젝트 예산을 주요 수량 가드로 사용한다. 임의 전역 호출 기본값을 복제하지 않는다. signed provider grant에 계정·무료 확인 진술·데이터 정책·컷룸·새 전용 키 바인딩을 포함한다. 기존 모델/엔드포인트/환경·key 검증, grant 서명·만료·철회, 데이터 정책, 컷룸과 업무의 동일 목표/연결 검사를 통과해야 전송한다. 동의 검증 자리에 무조건 True를 넣지 않았다. 무료 확인은 서명된 소유자 진술 수준이며 공급자 콘솔 독립 검증으로 가장하지 않는다.
- 기존 `_request_json`의 provider 예약/전송 **앞**에 BudgetedVideoTransport를 연결했다. 예산 부족 시 provider 시도 원장을 새로 만들지 않고 멈춘다. 부족 시 채택된 AI 작업계획의 pending/검토/최종검토 단계에서 필요한 잔여량을 계산해 한 요청으로 제안한다. 견적은 승인량이 아니며 추가 수정/실패는 여전히 소비한다. 예산 승인을 받아도 자동 실행하지 않는다.
- 같은 새 업무에서 오직 `budget_approval_required`로 전송 전에 중단됐고 active_operation이 없으며 과거 시도가 모두 completed/validated일 때만 명시적 계속 버튼으로 기존 단계에서 진행한다. 실패·불명 provider 요청이나 다른 stopped 상태를 초기화하지 않는다. 기존 실행 기한·provider 동의 만료도 연장하지 않는다.
- `companies/video/studio_server.py`: 신뢰된 로컬 서비스의 `enable_budget(pid, provider_job)`로 목표 접수 단계의 새 프로젝트만 별도 provider 동의 후 연결한다. 미션/기존 기획·보고서가 있는 프로젝트는 거부한다. `propose_budget`은 관리자 견적 입력 서비스이며 공개 대표 승인 endpoint와 분리했다. 예산 조회에 scope/자원별 승인·소모·잔여·불명/요청·검토 해시를 제공한다. `POST /api/project/workspace/<id>/budget-decide`가 실제 원장 approve/reject 이벤트를 저장하고, `budget-run`이 위 provider 경로를 실행한다.
- `companies/video/studio/studio.js`: 기존 프로젝트 화면에 예산 패널/승인·거절/명시적 시작·계속 버튼을 추가했다. 대시보드의 대표 검토 목록에도 예산 미결 프로젝트를 한 번 표시한다. 요청의 프로젝트·모델/계정·증액량·사유·완료 현황·작업계획 해시·실패 위험·무료/데이터 조건·만료를 보여 준다. 기획/영상의 역할 승인 버튼과 분리했다. 기존 화면 구조를 리디자인하지 않았다.

기존 core 예산 원장·서명·예약/소모/초과/불명/동시성 가드와 영상 어댑터는 복제하지 않고 재사용했다. 기존 미션 provider/원장/제안/서명/예산은 변경하지 않았다.

## 표적 검증

`tests/test_budget_cutroom.py`의 합성 fixture는 임시 저장소의 실제 Studio/ThreadingHTTPServer와 네이티브 Gemini 요청 생성·응답 검증·직원 인수 엔진을 사용하고, 외부 provider send만 모의한다. socket/DNS는 loopback 외 목적지를 거부한다. 실제 HTTP POST는 UI 버튼과 같은 route/body/token/해시를 사용한다. 테스트에 등장한 계획·대본은 **offline_http_fixture**이며 실제 프로젝트에 등록하지 않았다.

`PYTHONPATH=core:companies/video python -B -m unittest tests.test_budget_cutroom tests.test_project_budget_ledger tests.test_studio_server`: **18개 통과, 3.154초**. 테스트 환경의 localhost 소켓 권한이 기본 제한돼 해당 로컬 테스트만 권한 승인 후 실행했으며, 테스트 내부의 외부 네트워크 차단은 유지했다. `node --check companies/video/studio/studio.js`, `git diff --check` 통과.

확인 결과:
- 초기 관리자 견적 2회는 승인 전 전송 불가. 토큰 없는 HTTP 승인 403, 위조 해시/중복 제출 409, 정상 승인 200 및 실제 ledger 이벤트 저장.
- 계획·대본 실행 2회 후 검토 전 예산 부족: provider 시도는 2회 그대로이며 추가 4회 요청 한 건만 대표 검토에 표시. 예산 미승인 상태의 계속 실행은 409. 증액 승인 후 기존 writer 버전·plan을 유지하며 review→editor execute→review→finalize까지 진행. 전체 phase는 plan,execute,review,execute,review,finalize 각 한 번이며 기존 자료 재기획·재조사 없음. 두 원장 모두 모의 send 이전에 reserved 상태가 저장됨을 확인.
- 기존 품질 가드를 유지해 합성 최종 결과는 `external_clip_pending`으로 종료한다. 실제 소스 미확보 상태를 대표 기획 승인 대기로 위장하거나 영상 제작을 하지 않는다. 이번 완료 목표는 예산 승인/차감의 단일 실행 경로이며 전체 영상 완료가 아니다.
- 거절은 증액/전송 없음. 기존 실제 provider grant 철회, 환경 API 키/고정 모델 불일치, 컷룸–provider 연결 변경은 전송 전 차단. 동일 프로젝트 동시 HTTP 실행은 409. 모의 timeout은 예산·provider 시도 각 1회 소비 후 stopped이며 다음 run은 거부한다.
- 기존 공통 예산 테스트에서 만료/서명 원장 변조/다른 프로젝트 연결/데이터·모델·계정 scope 변경/불명 예약·장애·중복 operation 재전송 차단도 통과. 새 경로는 provider 동의와 예산 승인을 서로 대체하지 않는다.

Chromium/Chrome·Playwright 및 설치된 브라우저 캐시를 확인했으나 없었다. 브라우저를 새로 설치하지 않았고 시각/헤드리스 브라우저 검증은 수행하지 않았다. HTTP 승인 경로와 JavaScript 문법 검증으로 범위를 한정했다. 기존 인증은 로컬 컷룸의 workspace 토큰/동일 출처 경계이며 별도 계정별 RBAC를 추가했다고 주장하지 않는다.

## 보존 및 미완료

실제 Gemini/YouTube API 호출 **0회**, 실제 프로젝트 신규 provider/예산/서명/실행 **0건**. 기존 세 stopped 업무와 컷룸 관련 JSON/consent/lock **10개 SHA-256 동일** 확인. 미션 01 Gemini 누적 **6/10**, YouTube search **2/4**, videos **2/4**, 컷룸 **research_planning** 유지. 기존 대상·선정·25초·조사·실패 시도/active_operation·동의/비용 원장·키·음성/영상·백업·미추적 파일 7개 보존.

이번 경로는 새 프로젝트를 로컬 서비스로 명시적으로 준비한 경우에만 연결된다. 새 opt-in/provider 동의를 만드는 일반 사용자 provisioning UI, 최초 견적을 생성하는 별도 AI 호출, 전 업종/다른 API 적용, 토큰/실제 금액 계측, 불명 예약 수동 정산, 기존 미션 이관은 미구현이다. 최초 견적은 관리자 서비스 입력으로 받으며 이후 부족량은 이미 채택된 AI 계획으로 산정한다. 기본 provider 경로나 실제 운영 배포/모델 실행까지 완료됐다고 표시하지 않는다. 기존 provider 동의 만료·실행 시간 가드를 우회하지 않으므로 긴 승인 대기 후 계속하려면 별도 유효 동의/기한 절차가 필요하다.

**다음 한 단계:** 새 opt-in 프로젝트의 provisioning·독립 provider 동의 준비를 기존 컷룸 사용자 동선에 연결하고, 같은 네트워크 차단 통합 사례로 확인한다. 실제 API와 미션 01 재개/이관은 별도 대표 승인 전 금지한다. 위 코드·관련 테스트·이 보고서를 GitHub에 저장하고 중단한다.
