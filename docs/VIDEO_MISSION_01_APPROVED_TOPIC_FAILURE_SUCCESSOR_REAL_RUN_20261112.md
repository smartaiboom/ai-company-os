# 미션 01 — 제목 불일치 실패 이후 실제 대본·스토리보드 최종 진행
작성일: 2026-11-12 KST

## 대표의 실제 실행 승인
대표가 직전 결과를 확인하고 "**응 진행하자**"라고 명시적으로 승인했다. 범위는 **마지막 주제/제목 불일치 중단 이후 기존 자료를 이어받는 신규 독립 후속 업무 1건의 생성, 새 무료 제공자 제안 검토·서명, 실제 Gemini 작업 실행 1회, 대본·스토리보드의 AI 관리자 검토, 동일 컷룸 대표 기획 승인 대기까지**다.

예산/원장/UI/일반 기능 재개발 금지. 이전 작업들과 같이 다시 단계별 승인만 요청하며 중단하지 말고 **코드의 필요한 최소 후속 연결 및 표적 오프라인 검사 → 실제 실행**을 이 작업 안에서 연달아 수행한다. 다만 단계 실패·실제 무료 여부 불확실/결제 위험·서명 불일치·429/쿼터 오류·응답 불명에서는 즉시 중단하고 무단 재호출하지 않는다.

## 그대로 유지할 조건
- 사용자 이전 동의 범위 및 Google 무료 서비스 고정: 프로젝트 `gen-lang-client-0938732315`, 모델 `gemini-3.5-flash-lite`, 기존 고정 엔드포인트/키 바인딩. 요청된 목표/기존 공개 YouTube 조사/AI 출력이 Google 무료 서비스 개선 및 인적 검토에 사용될 수 있다는 기존 데이터 정책 확인. 실제 공급자 quota/청구 상태 독립 확인이 없다면 unknown/unverified 표기. 유료 모델/전환, 결제 계정 연결, fallback, 새 계정·키·모델 변경 금지.
- 신규 업무에 Gemini **임의 내부 호출 상한 없음**(`max_calls=None`). 이는 무제한 반복 호출을 뜻하지 않는다. writer 작성→manager writer 검토→editor 작성→manager editor 검토 등 **각각 목적이 다른 단계**만 진행. auto retry, stop 후 다시 run, 동일 요청 재송신, 불명 전송 재시도 금지. 공급자 무료 quota/rate/billing 실제 제한 준수.
- 기존 검증된 자료 재사용으로 신규 YouTube search.list/videos.list **0회**. 새 연구·게임/주제/길이 선정 금지.
- 최종 목표는 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`의 **`awaiting_plan_approval`** (사용자 실제 기획 승인 전 정지). 대표 승인 클릭, TTS/영상 렌더/MP4/게시/업로드 금지.

## 소스 및 현 상태
- 필독 `AGENTS.md`, `reports/VIDEO_MISSION_01_SELECTED_TOPIC_CONTRACT_FIX_RESULT_20261112.md`, `reports/VIDEO_MISSION_01_APPROVED_AUDIENCE_SUCCESSOR_REAL_RUN_RESULT_20261112.md`, `reports/AI_COMPANY_OS_FREE_TIER_NO_ARBITRARY_CALL_CAP_RESULT_20261112.md`. 전체 무관한 소스 감사 금지.
- 마지막 중단 `qualityprovider-4109f683a75b466ba326a45df3bb7012`의 `mission_selected_topic_mismatch`; Gemini writer 1회 HTTP200/json_parsed, 그 이전 provenance 및 미정 대상의 AI 제안·근거 검사를 통과한 것으로 관측. 당시 대본 원문/원 실제 제목은 저장되지 않았고 미검증 대본을 재사용하거나 승인했다고 주장 금지.
- 과거 **6개** stopped 업무와 원 서명·attempt·active_operation·실패/불명 응답 및 누적 **Gemini9, YouTube search2/videos2** 보존. 시작 컷룸 `research_planning`.
- 기존 실제 조사 YouTube 메타데이터10건; 계획 SHA `23ee4a8e9e2ab0079a5cf881be852c4f823eac0422f33fde1f357289f48b5c74`; 조사 receipt SHA `651b936fb9542aa188a3bf3a0a3ab803e914b8285f26a9e043fd041a9aeeb04b`; 관리자 selection SHA `e4296e6a276d6462599d3c3bdb1a86bc5fb3ba2472bfd53eb78d98e6a8d47587`; 원 관측 ID `q0:TAidk7sXHk4`, `q0:0FVBz6iWhOY`, `q1:9YjDIwCAnsw`. 관리자 선정 롤토체스/모바일 퍼즐 관련 소재, **25초**. 출처 유효 기간/서명 재검증 후 정확히 재사용. Shorts 분류/권리/성과 미확정 유지.
- 직전 오프라인 수정 `companies/video/video_mission_one.py`는 시스템 지시에 **`topic.title = quality.manager_selection.selected_topic`을 문자 그대로 복사**하도록 명시했다. viewer-facing 문구는 hook/promise/viewing_reason에 작성. 선정값 완전일치 검사는 유지되며 실전 모델 적용은 아직 미검증. 이번에는 이 최신 코드 사용.

## Codex 실행 순서 — 한 번에 완료
1. 최신 GitHub main을 기존 파일/미추적 데이터 안전 보존·fast-forward 확인. 이미 성공한 기존 체인/원 연구를 확인하고 최신 여섯 번째 실제 실패가 컷룸에 연결돼 있는지 확인. 과거6개 stopped job 및 consent/lock/실패 이력을 변경하지 말 것.
2. 기존 `audience_successor_reference` 및 `stage_mission_audience_successor` 등 가드를 느슨하게 만들거나 재활용하지 말고, **여섯 번째 실패(`mission_selected_topic_mismatch`)와 연결된 정확한 과거 체인만 검증하는 최소 새 reference/stage/CLI 후속 경로**를 기존 영상 미션 코드에만 추가. 업무는 한 건만 생성하고 중복 차단. 새 동의/승인/시도/세션은 빈 상태에서 시작. 기존 원 계획·원 accepted research·원 관리자 25초 선정·웹 관측만 인계하고 미검증 대본은 인계하지 말 것.
3. 아주 작은 **합성 오프라인 검증**: 올바른 여섯 번째 오류/HTTP200/JSON/active_operation/원 서명/원 input·plan·research·selection·receipt/자료 기간/키·계정 관계만 새 작업에 적격함, 원본 바이트 불변, 중복 생성/구 승인 재사용/다른 선정값·키/계정 거부, `max_calls=None`/YouTube 신규0, writer→manager review→editor→manager review→임시 동일 컷룸 `awaiting_plan_approval`. 기존 테스트 전부 반복 실행하지 말 것. 네트워크 차단한 fixture는 실제 결과로 표시 금지. 테스트 실패/가드 불명 시 실제 외부 호출 없이 오류 보고 후 중단.
4. 실제 원본 적격 검증 뒤 **신규 후속 업무 1건** 생성. 새 API 제안 `prepare`→검증된 목표/Google 무료 데이터 정책/모델·엔드포인트·계정/선정25초/과거 누적9/임의상한 None/YouTube 신규0 확인→새 검토 SHA 및 새 운영 consent/grant `approve` 서명. 과거 grant는 history 검증만 하고 신규 전송 권한으로 재활용 금지. 기존 키를 안전하게 실행 프로세스에만 설정.
5. **실제 run 한 번** 수행하여 Gemini writer 한국어 전체 25초 대본→AI manager writer 검토→editor 스토리보드→AI manager editor 검토. 실제 모델이 다른 주제를 재선정하거나 고정 topic.title을 바꾼 경우 검증 실패 처리; 미정 시청자의 AI 추론·미확정 근거, provenance.mock=false/고정 model, 권리/팩트 불확실성·자막·장면·대본 품질 검사도 유지. 각 단계별 실제 호출·토큰/HTTP/response hash 기록. 정상 revision이 이미 지원돼 있더라도 목적 없는 반복/자동 retry 금지.
6. 직원·관리자 검토가 실제 모두 수락되면 기존 `accepted_review_handoff` (별도 AI 최종평가 수행 안 함을 `final_evaluation=not_performed_local_handoff`로 표시)로 **동일 컷룸 `awaiting_plan_approval`** 기획안/대본/편집 카드 등록 및 읽기 확인. 보고에 실제 카드/위치와 구별 가능한 근거 포함. 사람의 승인 버튼/미디어 생성 금지.
7. 실패시 해당 실패 코드와 안전 진단·새 attempt 보존 후 즉시 중단; **새 successor 자동 추가 생성/재호출 금지**. 실전 오류가 나면 별도의 반복 개발을 시작하지 말고 바로 실패 보고에 최선의 좁은 다음 행동 한 가지만 제시.

## 필수 결과 및 중단
성공·실패·실행 전 중단 어느 경우든 `reports/VIDEO_MISSION_01_APPROVED_TOPIC_SUCCESSOR_REAL_RUN_RESULT_20261112.md`를 **GitHub main에 commit/push**하고 결과가 실제 읽히는지 확인 후 중단. 보고서: 신규 ID/제안 SHA/새 grant, 과거6개 보존, 실제 호출 단계별 상태/토큰/현재 누적, YouTube 신규0, 무료 정책/독립 quota 검증 한계, 실제 대본/스토리보드와 Cutroom phase 여부, 미수행 단계 및 원인, 다음 한 단계. 비밀키·원 모델 응답 전문/민감정보 공개 금지. 모든 시각 KST. data/, backups/, artifacts/, .env·키·미추적/사용자 미디어 보존, git clean/reset --hard/force push 금지.
