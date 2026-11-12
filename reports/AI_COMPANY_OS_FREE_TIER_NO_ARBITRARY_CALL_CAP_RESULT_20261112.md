# 무료 API 임의 호출 상한 폐지 — 미션 01 적용 결과

2026-11-12T09:13:59.714207+09:00 (KST). 최신 main `ca1510f`·AGENTS.md 및 지정 정책/직전 provenance 수정 결과를 확인했다. 20/8/8 확대 방식을 새 기본 정책으로 사용하지 않고, 과거 기록만 보존한다.

## 최소 적용 범위

미션 01의 향후 별도 독립 업무를 위한 `mission01_free_provider_limits_20261112_v1`, `create-free-writer-resume` CLI/`stage_mission_free_writer_resume`을 추가했다. 기본 `max_calls=None`, 새 총 호출 상한=None이며 큰 숫자로 우회하지 않는다. 원 소모7/2/2와 과거 서명 한도는 역사 참조로만 남긴다. 공급자 quota는 unknown, 청구 독립 검증은 unverified다.

공통 FreeStore는 이미 선택적 한도·사전 예약·중복 방지·무료 전용/서명·실패 소모를 지원했다. 품질 래퍼의 생성 시20회 검사와 미션 결과 인수의 숫자 상한 전제를 연결부에서 수정했다. `QualityProviderStore.create`는 자신의 기존 `_limits` 검증을 재사용하게 했고, MissionOneStore만 공통 선택적 한도 검증을 채택했다. 기존 미션 정책은 check_scope가 과거 정확한 한도를 계속 검증한다. 일반 품질 저장소의 기존 제한은 그대로다. 별도 예산 원장/승인 UI도 삭제·마이그레이션하지 않았다.

새 경로는 사용자가 명시한 선택적 `--explicit-max-calls`를 새 reference/proposal/grant에 서명한다. 명시한 제약은 엄격히 지키며 20보다 큰 명시적 값도 임의로 잘라내지 않는다. 기본 경로에서는 단순 사용량 카운터의 소진 때문에 추가 대표 승인을 요구하지 않는다. 새로운 업무/데이터 전송 동의와 실제 실행 승인은 별개다.

기존 네 번째 provenance 실패만 새 적격성 검증의 출발점으로 삼고, 원 실패4개·서명·계획·목표/입력·조사 기간·영수증/selection SHA·키/계정 바인딩을 그대로 검증한다. 다음 요청 목적은 정확한 서버 provenance 계약을 받은 새 대본 작성으로 명시한다. 구 실패를 run하거나 재전송하지 않는다. 새 업무는 빈 동의/시도/세션으로 시작해 별도 새 검토 해시/서명을 요구한다.

새 조사 한도를4/8 같은 수량으로 늘리지 않는다. 현재 선택된 조사 재사용 경로에는 **YouTube 신규 전송 권한0/0**을 둔다(임의 예산 소진이 아닌 작업 범위). 연구 재실행 차단과 원 자료 재사용을 유지한다. 고정 `gemini-3.5-flash-lite`·엔드포인트·계정 `gen-lang-client-0938732315`·Google 무료 데이터 정책·billing_disabled/free_only/max_cost0 가드는 유지한다. 이는 기존 소유자의 결제 미연결 진술/서명 및 키 바인딩이며 공급자 콘솔의 실시간 독립 검증은 아니다. 실제 무료 quota나 무과금을 확언하지 않는다. 설정/모델/계정/데이터 정책 불일치와 유료 전환은 새 정책으로 허용되지 않는다.

기존 사전 예약/시도·응답·토큰·HTTP·rate header 계측, 429/quota/billing 오류 중단, 불명/실패 소모, 동일 operation 거부, bounded revision/실행시간 가드는 재사용한다. 자동 retry·fallback·계정 순환·유료 전환은 없다. 오류 후 stopped/paused 업무를 재개하지 않고 새 목적/수정/검토 없는 후속 생성도 자동 수행하지 않는다. 수락된 대본/편집 검토를 대표 승인 대기로 묶는 local handoff는 별도 AI 최종 평가로 표시하지 않는다.

## 오프라인 검증

`PYTHONPATH=core:companies/video python -B -m unittest tests.test_video_mission_one tests.test_script_quality tests.test_quality_provider`: 최종 **49개 통과, 22.833초**. 임시 합성 fixture·mock native HTTP·외부 DNS/socket 차단. 초기 검증에서 래퍼의20회 제한, 최종 보고의 None 처리 누락 및 중복 검사 fixture의 context_hash 누락을 발견해 수정한 뒤 최종 통과했다. `git diff --check` 통과.

검증한 동작: 원 실패4개 보존→새 승인 전 전송 차단→검증된 조사/25초 선정 인계→대본/관리자 검토→편집/관리자 검토→동일 임시 컷룸 awaiting_plan_approval. 신규 mock 역할 요청4회·YouTube0회, fixture source=offline_http_fixture 유지. 원문 실패 응답 재현이나 실제 AI 성과로 주장하지 않는다.

10/20/25회는 메모리의 명시적 합성 계측 상태로 preflight 통과를 확인했으며 실제 호출/소모로 기록하지 않았다. 기본 무상한과 별도로 명시적3회 한도에서는3회 후 차단, 명시적30회에서는 정상 인수를 검증했다. 기존 일반 품질 저장소/역사적 한도는 그대로임도 확인했다. 동일 operation 재전송, reserved/불명 상태, 공급자 잔여0, HTTP429, quota/billing 오류, timeout 및 대본 검증 실패 후 자동 재호출을 모두 차단했다. 다른 모델/엔드포인트/계정·키, free_only/billing 설정 및 구 제안 재사용도 거부했다. 원4개 실패 파일/서명 바이트는 동일했다.

## 실제 보존·한계·다음 한 단계

**실제 Gemini/YouTube/provider API0회, 실사용 업무/승인/grant 생성0건, 기존 사용 원장 변경0건.** 실제 네 번째 업무에 대한 새 적격성 함수만 읽기 전용으로 확인했다. 기존4개 stopped 업무 및 컷룸 JSON/consent/lock14개 SHA-256 시작/종료 동일. 실제 누적 Gemini7·YouTube search2/videos2, 컷룸 research_planning 유지. 원 조사10건·관리자25초·evidence와 사용자 data/, backups/, artifacts/, .env·키·음성/영상·미추적7개 파일 보존. GitHub pull/commit/push는 요청된 저장 작업이다.

이번에는 핵심 미션 지연을 줄이기 위해 미션 01의 좁은 adapter와 공통 연결부만 완료했다. 다른 모든 provider/도메인의 기본 정책 일괄 변경·실시간 공급자 billing/quota 독립 조회·기존 프로젝트 이관은 하지 않았다. 과거 수량 정책 경로는 호환성을 위해 남지만 새 provider-limited 경로의 실행 한도로 사용하지 않는다. 실제 모델의 수정된 provenance 계약 준수·의미적 품질은 여전히 미검증이다.

**다음 별도 승인 요청1건:** 원 조사/25초 선정을 재사용하는 새 독립 대본 업무1건을 새 정책/제안/서명으로 생성·실행하여 동일 컷룸 대표 기획 승인 대기까지만 제출. 임의 내부 호출 상한 없이 동일 무료 모델/프로젝트/데이터 범위와 공급자 실제 무료 제한을 준수하고, YouTube 신규0회, quota/429·오류/불명 시 즉시 중단하며 자동 재시도·유료 전환·fallback 금지. 명시적으로 추가 지정된 제약은 서명/집행한다. 유료 전환은 반드시 별도 사전 대표 승인이 필요하다. 이번에는 실행하지 않고 소스3개·테스트1개·이 보고서만 commit/push 후 중단한다.
