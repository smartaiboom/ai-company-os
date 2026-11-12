# 미션 01 — v2 시청자 계약 기반 실제 대본·스토리보드 제작 재개
작성일: 2026-11-12 KST

## 이번 승인과 목표
사용자가 Codex 5시간 사용량 초기화 이후 "**이제 초기화 됐어 다시 시작하자**"라고 명시했다. 직전 결과 보고에서 예고한 **구조화 writer v2 계약을 사용하는 새 독립 후속 업무 1건의 실제 Gemini 제작 실행**을 승인한 것으로 취급한다. 기존 범위 그대로 **대본 작성 → AI 관리자 대본 검토 → 편집 직원 스토리보드 작성 → AI 관리자 편집 검토 → 같은 컷룸에 대표 기획 승인 대기**까지 진행한다. 성공은 실제 직원/관리자 수락 산출물과 컷룸 `awaiting_plan_approval` 확인이다. 사람의 승인 클릭, TTS/렌더/MP4/게시/업로드는 하지 않는다.

**추가 개발보다 실제 제작이 목적이다.** 기존 검증된 공통 후속 업무 진입점 `create-validated-successor` 및 stage, v2 계약을 그대로 사용한다. 새로운 사유별 successor CLI, 예산/UI/쿼터 관리 기능 추가, 새 조사·주제 재선정, 무관한 리팩터링 금지.

## 확인된 기준 상태
- 필독 `AGENTS.md`, `reports/VIDEO_MISSION_01_NATIVE_AUDIENCE_CONTRACT_FIX_RESULT_20261112.md`, `reports/VIDEO_MISSION_01_APPROVED_UNIFIED_SUCCESSOR_REAL_RUN_RESULT_20261112.md`. 최신 원격 main 확인, 기존 data/미추적 파일 보존.
- 마지막 stopped: `qualityprovider-3cfbbaec56d746799703489fe889a727`, 오류 `script_audience_inference_required`, 진단 `literal_unspecified_audience`; native Gemini writer HTTP200, 객체 응답 수용, role JSON parsed, writer accepted 아님.
- 과거 stopped **8건**, 누적 Gemini **11회**(수신 불명 포함), YouTube search.list **2회**, videos.list **2회**. 원본 grant/consent/attempt/active_operation/응답 해시 및 결제/무료 정책 상태는 수정 불가.
- 원 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`, 상태 `research_planning`. 원 실제 조사 YouTube metadata10건과 관리자 롤토체스/모바일 퍼즐 관련 소재 선정, **25초**, 원본 계획/조사/선정/receipt·자료 기간·서명·evidence 그대로 재사용.
- 계획 SHA `23ee4a8e9e2ab0079a5cf881be852c4f823eac0422f33fde1f357289f48b5c74`, research receipt SHA `651b936fb9542aa188a3bf3a0a3ab803e914b8285f26a9e043fd041a9aeeb04b`, selection SHA `e4296e6a276d6462599d3c3bdb1a86bc5fb3ba2472bfd53eb78d98e6a8d47587`, evidence `q0:TAidk7sXHk4` / `q0:0FVBz6iWhOY` / `q1:9YjDIwCAnsw`.
- 역사적 writer_contract v1 해시 `8d0ff0d818b0f7dfee18c13b506801b00ba588b14d9a45b173e497b6d540672f`; **현재 v2 해시 `4b1f627165a8398e3e47549563f8588708bf9066bde6bfd14c980953906355ff`**. 이전 실제8번째 v1 서명과 새 v2 서명은 별개이며, 과거 이력 증명에는 역사 버전 해시를 사용하고 신규 writer에게는 v2 사용.
- 고정 무료 서비스 Google 프로젝트 `gen-lang-client-0938732315`, 모델 `gemini-3.5-flash-lite`, 기존 고정 endpoint/키 바인딩/동의된 Google 무료 데이터 처리 정책(입출력 Google 개선 및 인적 검토 가능)만 사용. quota 실시간 독립 검증 불가 시 unknown, billing independent verification unverified로 명시. 결제 유도나 유료 전환/새 키·모델·계정·fallback·계정 순환 금지.
- **새 Gemini 임의 내부 횟수 상한 없음(`max_calls=None`)**이지만 목적 다른 정상 파이프라인 단계만 사용; 자동 재시도/실패한 request 재전송/새 successor 자동 생성 금지. 신규 YouTube API 호출 **0회**. 무료 공급자 429·quota·billing·timeout·전송 불명 시 즉시 중단.

## Codex 이번 한 번의 실행
1. main 최신 상태, AGENTS.md, 상기 보고, 실제 8번째 stopped 원장·서명/selected_topic/원본/키 바인딩과 v2 계약 해시 검증. 같은 목적의 기존 후속 업무가 없는지 컷룸 duplicate key 확인. **불필요한 전체 테스트/사전 API 테스트 반복 금지**. 지난 오프라인 v2 테스트2개 통과를 증거로 사용; 현재 코드/데이터 변화로 새 문제가 나타난 경우에만 관련 최소 오프라인 검사.
2. **기존 공통 `create-validated-successor` 경로**에서 마지막 미정 대상 실패와 계약 hash 변경 v1→v2를 검증해 새 독립 업무 **정확히 1건** 생성. 과거 8건과 원본 바이트 불변. accepted research/manager 25초 selection/observations 인계. 실패 대본은 절대 인계하지 않음. writer/editor pending, 신규 빈 consent/attempt/session, 명시적인 신규 목적 `write_new_script_with_concrete_ai_audience_proposal_under_native_v2_contract`. 현재 CLI 옵션은 소스를 보고 실제 지원 구문만 사용하고 추정하지 않는다.
3. 새 proposal prepare → 사용자 승인 범위(정확한 컷룸·무료 Google account·model·data policy/원본·누적11·None cap·YouTube 신규0·contract hash v2)를 검증한 **새 review SHA와 신규 operating grant 서명** → run **1회**. 과거 grant는 역사 검증만, 과거 stopped run 금지.
4. 실제 Gemini writer는 **새 native v2 schema**에 따라 한국어 25초 전체 대본을 작성. `quality_inputs.target_segment=미정`은 '사용자 미지정' 상태이며 output `target_audience`는 주제/관측 근거로 AI가 제안한 구체적 시청자여야 한다. `unknowns` 항목에 AI 제안·사용자 미확정/제안 대상·실제 근거를 함께 표기. `미정`을 output에 그대로 복사 금지. topic.title = quality.manager_selection.selected_topic 정확 복사. 출처 provenance.mock=false/실제 bound model. shot_type enum demo/detail/card, source_status=pending, fact_status illustrative/verification_pending, 0–3초 hook, 연속 타임라인, 정확히25초, transcript/close 일치 및 권리/조회 결과 한계 표시. 모든 실제 서버 검사 유지; 무음 보정·검증 우회 불가.
5. writer 통과 시 manager writer review → editor storyboard 작성 → manager editor review를 정상 단계로 수행. 둘 다 수락돼야 기존 `accepted_review_handoff`에 의해 같은 컷룸의 기획·대본·편집 카드를 `awaiting_plan_approval`로 전송. `final_evaluation=not_performed_local_handoff`; 모델이 실제 별도 최종 평가를 수행했다고 위장 금지. 컷룸 실제 데이터/phase 읽기 검증.
6. 실패 시 정확한 step/error_code·안전한 detail_code/response hash·HTTP/호출/소모를 기록하고 **그 즉시 중단**, 자동 재시도/새 계약 없는 후속 업무 생성 금지. 지난 실패 원문을 복원했다고 주장하거나 fixture를 실제 대본이라 표시 금지. 단순 API HTTP200만으로 성공 표시 금지.
7. **성공/실패/중단 모두** `reports/VIDEO_MISSION_01_V2_REAL_PRODUCTION_RESUME_RESULT_20261112.md` 작성 후 GitHub main commit/push·원격 fetch 검증하고 중단. 보고: 생성 업무 ID/새 grant·review SHA·v2 계약 hash, 과거8건 불변/원본 이용, 실제 Gemini 단계별 HTTP·토큰/신규·누적 소모, YouTube 신규0, 실제 시청자 제안/대본·스토리보드·manager review의 성공 여부(필요 시 개인정보 없이 짧게), 컷룸 실제 phase·카드 위치, 실패 원인, 공급자 quota/과금 독립 확인 한계, 다음 행동 **하나**. API 키·원시 응답 전문·민감정보 보고 금지.

KST(UTC+9). 사용자 data/backups/artifacts/.env/미디어·미추적 파일 불변. git clean, reset --hard, force push 금지.
