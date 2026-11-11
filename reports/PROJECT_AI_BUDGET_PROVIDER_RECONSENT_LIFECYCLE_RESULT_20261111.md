# 공급자 동의 재준비·갱신 결과 — 부분 완료

2026-11-12T08:22:54.069355+09:00 (KST). GitHub 최신 `690b377`를 fast-forward로 반영하고 AGENTS.md 및 지정 작업 문서를 확인했다. 작업 문서 8항의 최소 기능 허용 범위로 미등록 프로젝트 재준비를 구현했다. **운영 중 프로젝트의 동의 갱신 목표는 미완료**다.

## 구현

- 기존 컷룸에 `budget-reprepare` HTTP 경로와 확인 버튼을 추가했다. 기존 workspace 토큰·교차 사이트 차단·프로젝트 잠금·strict body 검사·로컬 계정/무료 확인을 재사용한다. 현재 제안의 정확한 review_hash를 제출해야 하며, 미등록 새 60초 프로젝트의 만료 또는 거절 제안만 재준비할 수 있다.
- 이전 proposal과 거절/만료 상태는 `budget_setup_history`에 복사하고 원래 proposal 본문·provider job 파일은 유지한다. 새 provider job ID를 제안 식별자로 사용하며 새 유효기간·review_hash를 만든다. 동일 입력의 일반 준비/새로고침은 기존 제안과 원래 만료를 유지한다. 중복·경쟁 재준비는 새 pending 제안에서 거부한다.
- 조회는 저장된 상태와 현재 만료 상태·이력 개수를 구분한다. 새 제안의 모델/API·계정·목표·정책·전송 범위·입력·만료·해시를 기존 패널에서 검토한 뒤 별도로 승인한다. 구 해시는 승인할 수 없다. 승인 시 기존 계약/키/서명 검사를 재사용하고 초기 예산은 0이다. 비밀키·credential binding은 브라우저에 노출하지 않는다.
- 등록된 프로젝트에는 재준비를 허용하지 않는다. 기존 provider/서명·철회 가드, 예산 원장과 승인·사용량·실패/불명 시도, 자동 재시도 금지 정책은 변경하지 않았다.

## 실제 검증

`PYTHONPATH=core:companies/video python -B -m unittest tests.test_budget_cutroom tests.test_project_budget_ledger tests.test_studio_server`: **25개 통과, 7.509초**. 합성 임시 컷룸·mock 전송·loopback 외 DNS/socket 차단을 사용했다. 최초 샌드박스 실행은 localhost socket 생성 권한 때문에 실패했고, 권한을 받아 재실행했다. `node --check companies/video/studio/studio.js`, `git diff --check` 통과. 브라우저 시각/클릭 검증은 수행하지 않았다.

추가 표적 검증: 거절→명시적 새 제안→새 해시 승인, 만료→동시 재준비 한 건만 성공→승인, 동일 준비의 멱등성, 원래 job 바이트·제안/거절 기록 보존, 구 해시·중복·토큰 누락·교차 사이트·무료 미확인·새 제안 이후 키 변경 거부, 초기 예산 0. 기존 timeout 후 철회한 등록 프로젝트에서 재준비/재실행을 거부하고 grant·job·예산 원장 바이트가 그대로임을 확인했다. 기존 예산 부족·증액·동시 실행·불명 시도 및 provider 만료/키/서명 가드 회귀 테스트도 통과했다.

**실제 외부 AI/provider API 요청 0회, 실제 프로젝트 동의 갱신/등록/예산 승인 0건.** GitHub 동기화와 이 결과의 commit/push만 수행한다. 테스트의 모의 전송은 실제 API 요청이 아니다.

## 보존·미완료·다음 한 단계

실사용 data/, backups/, artifacts/, .env와 기존 미추적 파일 7개를 수정·삭제하지 않았다. 전체 데이터 해시 스냅샷은 서버 재시작으로 완료되지 않아 작업 전후 전체 동일성을 입증한다고 주장하지 않는다. 재시작 후 읽기 전용으로 수집한 studio JSON/lock 15개는 보고 직전 재확인하여 동일했다. 테스트는 TemporaryDirectory에서만 실행했다.

현재 미션 01의 세 provider 업무를 직접 읽어 stopped 상태와 각 attempts 1/3/2를 확인했다(free_request_failed / invalid_model_json / script_audience_mismatch). 컷룸은 research_planning이다. 직전 보존 보고의 Gemini 6/10, YouTube search 2/4 및 videos 2/4는 이번 호출·재개가 없어 유지되며, 이번 작업에서 공급자 서버에 사용량을 조회하지 않았다. 기존 조사·25초 선정·동의·실패·active_operation을 재작성하지 않았다.

운영 중 만료/철회 동의의 동일 scope 갱신은 미구현이다. 현재 grant/철회 구조와 consent ID/만료가 포함된 서명 예산 scope를 함께 갱신하려면, 과거 grant/철회 이력을 보존하는 새 grant 연결 및 장애/경쟁 시 원장과의 일관성 처리가 필요하다. 이 트랜잭션을 검증하지 않은 채 기존 grant나 원장을 교체하지 않았다. 따라서 사용량 보존 후 갱신된 동의로 업무 계속하는 시나리오와 그 scope/키 변경·동시 갱신 검증은 완료하지 못했다. 등록된 프로젝트는 만료/철회 시 계속 차단된다.

**다음 한 단계:** 기존 grant/철회 기록을 보존하는 버전별 grant 연결과 예산 원장의 동일 scope 갱신 이벤트를 함께 구현하고, 실패 복구·경쟁·불명 시도 보존을 오프라인 검증한다. 계정 RBAC·요금 독립 검증·다른 provider/도메인·미션 01 이관은 별개다. 이번 변경 3개 소스/테스트와 이 보고서만 commit/push 후 중단한다.
