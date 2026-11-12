# 미션 01 — 승인된 5차 실패 후속 업무 및 실제 대본·스토리보드 실행
작성일: 2026-11-12 KST

## 이번 사용자의 명시적 승인
사용자는 "응 승인할게 진행하자"라고 답했다. 이는 직전 안내한 **다섯 번째 시청자 추론 검증 실패 이후의 새 독립 후속 업무 1건을 준비하고, 기존 실제 조사/AI 관리자 25초 선정 자료를 재사용해 무료 Gemini로 한국어 대본·스토리보드를 실제 작성·검토하고, 동일 컷룸에서 대표 기획 승인 대기까지 제출하는 실행**을 승인한 것이다.

**핵심 미션 수행이 최우선. 이번 작업에서 추가 예산 기능 개발·반복적인 사전 점검/전체 코드 감사/새 YouTube 조사/계획·게임 재선정 금지.** 다만 실제 검증·동의·서명 가드를 우회하지 않는다.

## 변경 불가능한 승인 범위
- 사용 서비스: 기존 Google Cloud 프로젝트 `gen-lang-client-0938732315`의 고정 무료 `gemini-3.5-flash-lite`, 기존 검증된 모델 엔드포인트와 키 바인딩. 무료 계정/결제 미연결에 관한 기존 사용자 진술 및 기존 Google 무료 데이터 정책 동의(사용자 목표·공개 조사·AI 생성 입력/출력이 Google 개선과 인적 검토에 사용될 수 있음) 유지. **공급자 실제 무료 할당량/비용 상태를 검증하지 못하면 unknown/unverified로 표기**하고 유료 가능성/결제 요구가 나타나면 차단.
- **새 실행의 임의 내부 Gemini 호출 횟수 상한 없음**(max_calls=None). 이는 무한 루프/자동 재시도를 승인한 게 아님. 이미 확정된 계획과 연구 재사용, 업무 단계별 꼭 필요한 서로 다른 요청만 허용하고 실제 provider 무료 한도·429·quota 오류를 준수. 새 **YouTube search.list/videos.list 호출 0회**.
- 자동 재시도·실패 중복 전송·fallback·모델/공급자/계정 변경·유료 전환·청구 연결·쿼터 우회·동의 없는 다른 데이터 전송 금지.
- 결과 범위: 검증된 직원 대본 + 관리자 대본 검토 → 편집 AI 스토리보드 + 관리자 편집 검토 → 동일 컷룸 `awaiting_plan_approval`. **대표 승인/반려 동작은 하지 않는다.** 음성/TTS·영상/MP4·렌더/업로드/게시 금지.

## 실물 상태 및 출처
- 필독 `AGENTS.md`, `reports/VIDEO_MISSION_01_AUDIENCE_CONTRACT_MINIMAL_FIX_RESULT_20261112.md`, `reports/VIDEO_MISSION_01_FREE_TIER_APPROVED_REAL_WRITER_RUN_RESULT_20261112.md`, `reports/AI_COMPANY_OS_FREE_TIER_NO_ARBITRARY_CALL_CAP_RESULT_20261112.md`. 해당 실행 경로 외 불필요한 자료 탐색 금지.
- 컷룸: `company-aba553f29cfb454c8c05bad4abb49969`; 현재 `research_planning`.
- 과거 5개 stopped 업무는 **읽기 전용으로 그대로 보존**:
  1. `qualityprovider-504d90900918450f98dd62b6f7704f1b` (DNS 실패)
  2. `qualityprovider-299a51b38e6d4d50b651b9fbb39dabad` (연구 검토 JSON 실패)
  3. `qualityprovider-4cbe762cbf554e40af5e7d990ceaf46b` (대본 대상 일치 실패)
  4. `qualityprovider-bb394ad486014277998d8a64b62e8199` (대본 출처 정보 실패)
  5. `qualityprovider-a084021162134b20b0972f9b5aec343b` (대본 시청자 추론 상세 조건 실패)
- 기존 실제 누적 **Gemini 8회**, **YouTube search 2회, videos 2회**(실패/불명 건 포함). 이 기록과 각각의 그 당시 승인된 상한/서명/attempt/active_operation/타임스탬프/응답 SHA를 수정하거나 초기화하지 않는다.
- 검증된 기존 조사: YouTube 메타데이터 10건, 원 계획 SHA `23ee4a8e9e2ab0079a5cf881be852c4f823eac0422f33fde1f357289f48b5c74`, 조사 영수증 SHA `651b936fb9542aa188a3bf3a0a3ab803e914b8285f26a9e043fd041a9aeeb04b`; 관리자 선정 SHA `e4296e6a276d6462599d3c3bdb1a86bc5fb3ba2472bfd53eb78d98e6a8d47587`. 선정 소재 전략적 팀 전투/롤토체스 및 모바일 퍼즐류, **25초**, evidence `q0:TAidk7sXHk4`, `q0:0FVBz6iWhOY`, `q1:9YjDIwCAnsw`. 자료 유효 기간·선정 계약·원본 출처를 기존 가드로 검사. 실물 조회로 Shorts 여부나 권리 확정 금지.
- 이전 실패 대본 응답 원문은 원장에 보존되지 않았고 검증도 못 통과했다. 이 내용을 복원했다고 주장하거나 새 업무에 수락된 버전으로 이식하지 않는다.
- 최근 오프라인 코드 수정으로 시청자 `미정`일 때 AI의 구체적 대상 제안과 미확정 표기·근거를 여러 표현으로 검증하도록 개선했으며 **53개 표적 테스트 통과**. 실제 Gemini 준수는 이번이 첫 확인.

## Codex가 이번 **한 번의 작업**에서 수행할 순서
1. main 최신 버전을 기존 파일 보존하며 fast-forward. 이미 구현된 `create-free-writer-resume`는 **네 번째 provenance 실패 전용**이므로 다섯 번째 audience 실패에 억지 적용/가드 약화 금지. 기존 네 가지 체인 적격성/서명 가드를 재사용하는 **다섯 번째 stopped만의 최소 새 successor 적격성 함수와 stage/CLI**를 추가할 필요가 있다면 해당 코드에만 한정해 구현한다. 별도 예산/UI/서비스 모듈 신설 금지. 미션 전반의 변경보다 새 경로 연결만 수행.
2. 새 경로는 과거 네 단계 체인/서명·status·reason_code·attempt(다섯 번째 실제 Gemini writer 1회, HTTP200/json_parsed)/active_operation·누적8회/YouTube2+2·목표/원 입력·계획/연구/선정/receipt SHA·원 자료 기간·key/model/account/data scope를 **검증한 경우에만** 같은 컷룸에서 후속 업무 한 건 생성 가능하게 한다. 이전 다섯 stopped 파일 수정 금지. 원 연구 accepted/관리자 25초 selection과 기존 web 관측을 그대로 인계하고 writer pending부터 실행. 이 실패 응답의 잘못된 대본은 인계하지 않는다.
3. 필요한 최소 합성 **오프라인 경로 검증 한 묶음**: 새로운 다섯 번째 적격성·원본 해시 보존·예산 max_calls=None/YouTube0·다른 사람 프로젝트 바인딩 및 중복 successor 차단·writer 작성/관리자 수락/편집 작성·수락→임시 컷룸 awaiting_plan_approval. 이미 통과한 53개 전체를 불필요하게 반복하지 않는다. fixture는 실제 모델 결과가 아님. **소스·가드 점검과 테스트가 완료된 경우에만 실제 실행**, 개발/테스트가 실패하면 외부 요청 없이 보고 후 중단.
4. 기존 데이터에 새 successor가 있는지 먼저 확인하고 **정확히 한 건만** 생성. 새로운 독립 제안 `prepare`→scope/해시/계정·무료·모델/선정25초·원소모8·새 Gemini 임의한도 None·YouTube 신규0/원본 보존을 사용자 승인과 대조→**새 review_hash와 새 운영 grant 서명 `approve`**→새 업무 `run` 최대 1번. 과거 stopped 직접 run 금지. 과거 서명이나 만료된 동의를 전송 권한으로 재사용 금지.
5. 실제 실행은 **writer 한국어 대본 작성 → manager writer review → editor 25초 스토리보드 인수 → manager editor review**, 필요 시 기존 제한된 revision/수정 흐름을 따르되 단계별 목적 없는 재호출 금지. `provenance.mock=false` 및 고정 model, 명시적 시청자 `미정`의 제안/근거·원래 target_segment 불변, 선정 소재/주제/25초·원 조사 evidence, transcript/자막/권리/팩트 검증 유지. HTTP200이어도 산출물 검증 실패일 수 있음을 기록. 검증 실패가 나면 별도 자동 successor/재시도 없이 구체적 detail_code/응답 해시/단계만 기록하여 즉시 중단.
6. 성공 시 별도 최종 AI 평가를 수행한 것으로 위장하지 말고 기존 검증된 `accepted_review_handoff` 경로로 **같은 컷룸 `awaiting_plan_approval`** 등록 및 실제 데이터/카드 인수 여부 읽기 확인. 대표 승인 버튼은 누르지 않는다.
7. **성공·중단·실패 모두** `reports/VIDEO_MISSION_01_APPROVED_AUDIENCE_SUCCESSOR_REAL_RUN_RESULT_20261112.md` GitHub에 commit/push하고, 가능하면 main에서 다시 fetch 확인 후 중단. 보고에는 신규 업무 ID, 새 제안 SHA/승인 ID, 원5개 상태·원본 보존 확인, 단계별 실제 전송(HTTP/status/response hash/토큰 등 가능한 근거), Gemini 누적8+이번 실제 건수/YouTube 신규0, 실제 대본·스토리보드 저장 여부 및 컷룸 실제 phase, 실패 시 blocker+detail_code, 공급자 quota/비용 독립 검증 한계, 다음 행동 하나를 간결히 남긴다. 보고서에 API 키·원시 응답·시청자 개인정보를 기록하지 않는다.

## 절대 금지
`git clean`, `git reset --hard`, 강제 push, 기존 data/backups/artifacts/.env/미디어/키/미추적 파일 삭제·초기화, 기존 다섯 stopped 업무 재실행·시도 원장 수정, 새 무료 모델 추정/유료 전환, 자동 네트워크 시험 반복, 중복 업무 생성, fixture를 실제 영상으로 표시. 모든 시각 KST.
