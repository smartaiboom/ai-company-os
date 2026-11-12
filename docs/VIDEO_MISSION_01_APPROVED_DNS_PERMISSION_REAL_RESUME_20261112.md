# 미션 01 — 네트워크 권한 확보 후 실제 주제·대본 능력 개선 미션 재개
작성일: 2026-11-12 KST

## 이 단계의 정확한 제품 맥락과 개발 우선순위
사용자가 명확하게 정정한 전체 이력: **AI Company OS는 이전에 영상 생성까지 전체 한 사이클을 실제로 완료한 경험이 있다. 다만 영상의 품질이 낮아 첫 번째로 음성 품질을 개선했고, 현재 두 번째로 AI의 주제 선정 및 대본 작성 능력을 향상하는 중이다.** 이번 Mission 01의 컷룸 실전 기획·대본·스토리보드 인수는 **품질 고도화 검증의 일부**이지, 제품 전체가 아직 영상 생성까지 한번도 못 해봤다는 의미가 아니다. 새 기능을 늘리는 것보다 AI가 선정한 주제의 매력도와 대본의 질, 실제 사용 가능한 결과물 확보에 집중할 것. 사용자는 **Codex 주간 사용량 절약을 요구**했으므로 꼭 필요한 코딩/실행 외 분석·반복 테스트·과도한 보고 금지.

사용자는 직전 DNS 보고 이후 **"응 진행해줘"**로 기존 무료 모델 조건 아래 네트워크 권한 확보 및 새 후속 업무 1건 실제 실행을 명시적으로 승인했으며, 이어 **"진행하자"**로 그 방향을 재확인했다.

## 재사용할 확정 상태
- 최신 main, `AGENTS.md`, `reports/VIDEO_MISSION_01_DNS_ENV_DIAGNOSIS_RESULT_20261112.md`, `reports/VIDEO_MISSION_01_V2_REAL_PRODUCTION_RESUME_RESULT_20261112.md`, `reports/VIDEO_MISSION_01_NATIVE_AUDIENCE_CONTRACT_FIX_RESULT_20261112.md`만 우선 확인.
- 원 컷룸 `company-aba553f29cfb454c8c05bad4abb49969` 현재 `research_planning`. 이 미션의 원 연구 YouTube metadata 10건, AI 관리자 롤토체스/모바일 퍼즐 관련 소재·25초 선정과 해당 evidence, signed chain을 변조하지 말고 인계. **기존 영상 생성/음성 개선 이력을 삭제하거나 '한 번도 영상 생성 성공 없음'으로 표시하지 말 것.** 이번 독립 미션에서 아직 대본/스토리보드 승인 대기까지 못 도달한 상태와 구분.
- 마지막 stopped `qualityprovider-d0bd0be8805b4d61938442acda4ef2cb`, `free_request_failed` `dns_error` at `transport_open`, HTTP 응답 없음, 실제 공급자 수신/토큰 소모 불명. 과거 **9개 stopped** 이력, 누적 Gemini **12회**(수신 불명 포함), YouTube search2/videos2를 보존.
- 이전 writer 계약 v1 sha `8d0ff0d818b0f7dfee18c13b506801b00ba588b14d9a45b173e497b6d540672f`; **현재 v2** sha `4b1f627165a8398e3e47549563f8588708bf9066bde6bfd14c980953906355ff`. 새 native schema/v2(미정 입력과 구체적 AI 시청자 제안 구분)를 사용. 원 선정값 그대로, 주제/제목 정확 복사, 25초 유지.
- DNS 확인: Codex 일반 제한 환경 `getent`/Python getaddrinfo 실패, `require_escalated` 범위에서 같은 hostname IPv4/IPv6 조회 성공. 다만 당시 transport 오류의 상세 OS 규칙은 불명. DNS 성공은 실제 HTTP/결제/쿼터 정상의 증거가 아님.
- 기존 고정 Google 무료 프로젝트 `gen-lang-client-0938732315`, `gemini-3.5-flash-lite`, 기존 endpoint·키 바인딩/Google 무료 데이터 정책(입출력 개선 이용 및 인적 검토 가능) 승인 범위. 신규 Gemini 내부 임의 호출 한도 `max_calls=None`(자동 무한 재시도 허가 아님), 새 YouTube API 0회, paid/fallback/다른 모델·키·계정/무료 공급자 quota 우회 금지. 무료 조건/비용 독립 확인 불가시 unknown/unverified로 보고하고 유료 위험이 나타나면 중단.

## 바로 실행할 것 — 불필요한 검증·개발 최소화
1. 기존 data/backups/artifacts/.env/미추적 파일·키·음성/완성된 과거 영상 자산을 보존하며 main fast-forward. 기존 서명·원본/미션 상태에 필수인 검사만 사용. 이미 완료된 네트워크 비교·오프라인 통합 테스트 반복 금지.
2. **네트워크 권한**: Gemini 전송을 실제 실행할 명령은 DNS 조회에 성공했던 **권한 확장 실행 환경**에서 실행하도록 Codex의 정식 승인/권한 상승 경로를 사용. 사용자의 이번 요청은 그 범위의 API 실행을 승인하지만, Codex가 실제로 OS/도구상 권한 승인을 요청한다면 이를 우회하지 말고 해당 정식 승인 절차를 거친다. 프록시/hosts/resolv.conf를 임의 변경하지 않으며 시스템 네트워크 보안 가드, 키 비공개, 허용된 endpoint·전송 검증을 유지. 실제 전송이 금지되거나 권한 확대가 불가하면 **무단 제한 해제·호스트 변조 없이 즉시 보고**. 이미 진단했으므로 별도의 반복 DNS/HTTP 연결 시도 금지.
3. 가장 최근 `dns_error` stopped 업무는 기존 `create-validated-successor`의 **HTTP200/json_parsed writer 계약 오류 전용** 조건에 맞지 않으므로 그대로 억지 재실행하거나 사유를 변경하지 말 것. 기존 공통 이력 검증·서명/중복방지/원본 보존을 재사용하여 **이번 실제 DNS 전송 불명 실패로부터 새 독립 업무 1건을 안전하게 만드는 가장 작은 경로**만 추가. 이전 요청의 재전송이 아니라 **새 목적·새 서명/동의·새 업무**여야 하며 전송 불명은 실제 시도 1회로 기록에 남긴다. 과거 9개 stopped 이력·실패 응답·attempt·grant/active_operation 변경 금지. 과도한 일반 후속 프레임워크/별도 CLI 증식 금지; 안전성상 필수 가드만 좁게 구현하고, 불가능하면 실행하지 말고 간결 보고.
4. 해당 최소 변경 부분만 **오프라인 표적 테스트 1묶음** (원본 이력 불변, DNS 실패 전송 불명 과거12회 기록, 새 운영 grant/계정·모델/서명/원선정/v2/중복 업무·새 YouTube0, network-free fixture 대본→관리자 검토→스토리보드→관리자 검토→원 컷룸 awaiting_plan_approval). 전체 테스트 재실행과 무관한 품질/예산 개발 금지.
5. 관련 검사 성공 후 **정확히 새 1개** successor 생성, 새 proposal prepare 및 사용자 승인 범위 검증, 신규 review SHA와 별도 operating grant approve. 앞선 grant는 역사 증명으로만 참조. 인수 내용은 원 수락 연구·원 AI 관리자 선정/evidence·25초·모델/무료 데이터 정책, writer/editor pending. 실패한 대본은 인계 금지. 기존 주제 선정 결과를 바꾸지 않는다.
6. **권한이 확보된 실제 실행 환경에서** 새 job run 단 1번 호출. 목적 다른 정상 단계에 따라 실제 Gemini writer **한국어 25초 대본** → AI 관리자 대본 검토 → 편집 AI 스토리보드 → 관리자 편집 검토 진행. AI는 구체적 대상 시청자를 제안하되 '사용자 미정'을 대상명으로 그대로 사용하지 않고 실제 추론/미확정 근거 기록. 주제 선정 동적 원문 정확 복사. `shot_type=demo|detail|card`, `source_status=pending`, `fact_status=illustrative|verification_pending`, provenance(mock=false·고정모델), 25초 타임라인/0-3초 후크·transcript·권리 불확실성·실제 출처 검증 유지. **검증을 통과한 실제 대본만** AI 관리자에게 넘긴다.
7. 작동 시 **동일 컷룸 `awaiting_plan_approval`** 기획안·대본·스토리보드 카드 인수 확인. 사용자 대표는 아직 승인하지 않음. `accepted_review_handoff`는 실제 수락된 employee/manager 결과에만 사용, `final_evaluation=not_performed_local_handoff` 유지. TTS/렌더/MP4/게시/과거 영상 자산 변경 금지.
8. 실패·DNS·429·쿼터·공급자 HTTP/검증/시간초과/불명 상태에서는 안전 원장에 status/진단/요청 hash를 보존하고 **그 즉시 중단**. 자동 retry/추가 successor 생성/유료 fallback/무음 응답 수정 금지. 테스트 fixture나 DNS 성공을 실제 제작 성공이라고 주장하지 말 것.
9. **결과는 성공·실패 상관없이 GitHub** `reports/VIDEO_MISSION_01_DNS_PERMISSION_REAL_PRODUCTION_RESULT_20261112.md` 한 개에 **짧고 명확하게** 작성. 변경한 코드 및 표적 테스트 수, 네트워크 권한 실행 여부, 신규 job/proposal/grant, 원9건 보존, 실제 단계별 Gemini API·사용량 누적 12+신규 시도/YouTube0, 실제 대본·관리자 검토·스토리보드/컷룸 phase, 중단 시 원인과 다음 행동 한 가지만 포함. 키/원시 응답/개인정보/완성된 과거 영상의 민감 정보 기록 금지. main commit/push 후 읽힘 확인하고 중단.

모든 시각 KST, git clean/reset --hard/force push 금지.
