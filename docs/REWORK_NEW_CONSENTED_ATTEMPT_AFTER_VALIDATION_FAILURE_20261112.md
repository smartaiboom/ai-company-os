# 컷룸 재작업 — 실패 기획 이후 신규 실행 준비/동의/대본 생성까지 연결
2026-11-12 KST

## 가장 중요한 목표
사용자는 대본·영상·음성 품질 개선에 빨리 집중하고 싶다. 지난 개발로 rework 계획의 writer→editor, criteria ID 계약 강화 및 오프라인 종단 테스트까지 완료됐지만 실제 실행은 **옛 실패 job 재실행 금지 / 새 job 승인 경로가 UI에 없어** 막혀 있다. 이번 일회성 개발은 **현재 같은 컷룸에서 새 재작업 시도 제안 준비 → 사용자 동의 → 명시적 실행 → manager/writer/editor → 새 대본 v2 대표 승인 대기**를 실제로 연결하는 것만 목표. API 호출은 Codex 작업에서 금지.

## 근거
실패 rework job qualityprovider-3cb52d1ab205460897e9f03fea21ca71: stopped/invalid_dependencies, attempts1 HTTP200, model JSON parsed but server not validated, old plan=null. 이전 대표 feedback 및 v1, consent/grant/attempt는 역사적 불변. main 최신 커밋 1942800d. `companies/video/representative_rework.py` `prepare(workflow,pid,key,account)`는 동일 decision_hash 발견 시 그냥 return하여 새 준비가 불가능하며, 과거 orphan 동일 decision을 거부한다. `studio_server.py`는 old stopped 상태 뒤 신규 prepare 분기 없음. `studio.js`는 failed state에 신규 승인 버튼 없음.

## 구현할 내용
1. **새 실행 작업 생성 API/화면 최소 연결**: 기존 flow.stage=plan_revision, 최근 대표 feedback 동일, 이전 job이 stopped이며 실제 시도 완료/중단 원장 확인하고 활성 요청/불명 예약 없다면 사용자가 명시적으로 '수정 대본 다시 생성 준비'를 클릭하게 한다. 새 independent job ID, 새 고정 계약 hash(PLAN_RULES), 새 서명된 proposal, 새 owner consent 필요. **기존 실패 job/grant/attempt/서명 및 대표 피드백은 그대로 immutable history에 보관**, 화면에서 이전/신규 job 구분. 같은 feedback의 history가 있어도 유효한 신규 범위를 독립적으로 시작할 수 있게 하되 중복 클릭·동시 요청/새로운 grant 무한 발급 방지(진행 중/보류 상태에서 재발급 금지). 기존 파일 scanning orphan 검사는 활성 미연결 orphan만 막고 정상적으로 history에 보존된 이전 stop을 새 흐름에서 거짓 충돌로 취급하지 않도록 안전하게 한정 조정. 기존 원장 내역을 수정하거나 job hash를 재작성하지 않는다.
2. 기존 `rework-prepare`/consent/run + 실제 manager/writer/editor pipeline 재사용. 최초 승인 범위·무료 모델 GEMINI35_MODEL & ENDPOINT 고정·기존 키만 사용(키값 출력 금지), quota/청구 미확인. **옛 consent는 새 job 승인에 사용하지 않는다.** Google 개선/인적 검토 정책, 목표·피드백·이전 스크립트 전송 범위 그대로 UI에 고지. 실패 여부/원장 상태는 한국어로 안내. 새 job 생성/서명/동의까지는 외부 요청0회. 서버에서 긴 요청 background run 중복 차단 유지.
3. 새 실행이 중단되면 자동 재시도/무단 model fallback/반복 실행 금지. 이번 이후 실제 실패가 발생한 경우 다음 소유자 검토와 승인 없이 계속 시도하게 만들지 않는다. 현재 강화된 rework plan 계약(2 task writer→editor, proper deps/criteria)을 유지, 기존 AI manager 의미/품질 검증과 v1→v2 비교 유지. 모델의 콘텐츠/스토리보드를 조작해 가짜 성공 금지.
4. 유일 목표는 새 대표 제출 흐름. UI 미화/대규모 리팩터링/비용관리/새 API 공급자/음성·영상 기능 개선은 이번에 추가하지 않음. 오프라인 통합 테스트 단 1개: 실제와 동등한 old stopped attempts1 → 명시적 새 prepare → 서로 다른 new job/consent, 원본 old 파일 불변 → 새 승인/시작 → 모의 manager writer editor → 동일 컷룸 새 plan v2 승인 대기; 중복 클릭 차단, old consent 재사용 거부. 실제 Gemini/YouTube 전송0. 네트워크 없는 fixture. 전체 테스트 suite 금지.
5. 보고서 `reports/REWORK_NEW_CONSENTED_ATTEMPT_AFTER_VALIDATION_FAILURE_RESULT_20261112.md`에 수정 파일, 기존 history 보존 확인, 새 UI 버튼 이름/사용자 절차, 핵심 표적 테스트, **실 호출0 및 실제 대본 미생성** 사실, 남은 문제를 간결히 작성. main commit/push/readback 후 중단.

AGENTS.md 준수, KST. data/backups/artifacts/.env/실 job/old approvals/grants/logs/과거 제작 영상 음성/미추적 파일 삭제/덮어쓰기 금지. git clean/reset --hard/force push 금지.
