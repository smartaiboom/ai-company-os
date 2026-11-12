# 미션 01 — 구조화 writer 계약 기반 공통 후속 업무 실제 실행
작성일: 2026-11-12 KST

## 대표의 신규 실제 실행 승인과 가장 중요한 결과
직전 `reports/VIDEO_MISSION_01_WRITER_SCHEMA_RELIABILITY_FIX_RESULT_20261112.md`를 확인한 대표가 "**진행하자**"라고 답했다. 이는 **일곱 번째 `invalid_script_shot` 실패를 보존하면서 안전한 후속 업무 1건을 생성하고 기존 무료 Gemini에서 실제 대본→AI 관리자 검토→스토리보드→AI 관리자 검토→동일 컷룸 대표 승인 대기까지 연속 실행**하도록 승인한 것이다. 단순 코드 작성/오프라인 테스트만 하고 종료하지 말 것. **성공 시 컷룸 `awaiting_plan_approval`에 실제 카드가 있어야 한다.**

이번 지시의 우선순위:
1. **실제 AI 대본과 스토리보드 생성** — 기존 원 연구/선정 인계, 새로운 native structured JSON writer schema의 공급자 수용 확인
2. 원본 7개 실패 업무, 서명, API 실제 소모 보존 및 안전한 후속 업무 1건만 생성
3. 불필요한 Codex 개발·테스트/추가 외부 호출 없이 실제 결과에 도달
**예산 관리/UI/새 YouTube 조사·게임 재선정/다른 영상 기능 개발 금지.**

## 고정된 실전 상태
- 필독: `AGENTS.md`, `reports/VIDEO_MISSION_01_WRITER_SCHEMA_RELIABILITY_FIX_RESULT_20261112.md`, `reports/VIDEO_MISSION_01_APPROVED_TOPIC_SUCCESSOR_REAL_RUN_RESULT_20261112.md`. 이전 프로젝트의 모든 소스/보고서를 전수 조사하지 말고 필요한 연관 경로만 참고.
- 현재 컷룸 `company-aba553f29cfb454c8c05bad4abb49969` 상태 `research_planning`; 마지막 stopped `qualityprovider-95e2b74978f24b4690368a8bf10ae72a`, reason `invalid_script_shot`, 실제 Gemini writer 1회 HTTP200/json_parsed/active_operation. 과거 **7개 stopped** 업무 및 그 시점의 consent/grant/attempt/원장·응답 해시·실패 기록 불변.
- 기존 실제 누적 Gemini **10회**(DNS 수신 불명 포함), YouTube search.list **2회**, videos.list **2회**. 무료 API 임의 내부 호출 상한은 없음(max_calls=None). 누적 사용량 관측은 계속 한다.
- 원본 계획 SHA `23ee4a8e9e2ab0079a5cf881be852c4f823eac0422f33fde1f357289f48b5c74`; YouTube 조사 receipt SHA `651b936fb9542aa188a3bf3a0a3ab803e914b8285f26a9e043fd041a9aeeb04b`; 관리자 선정 SHA `e4296e6a276d6462599d3c3bdb1a86bc5fb3ba2472bfd53eb78d98e6a8d47587`. 실측 메타데이터 10건 및 evidence `q0:TAidk7sXHk4`, `q0:0FVBz6iWhOY`, `q1:9YjDIwCAnsw`. 선정 소재 전략적 팀 전투/롤토체스 및 모바일 퍼즐 관련, 쇼츠 길이 **25초**. 기존 원본의 서명/해시/시점/유효기간·권한을 검증 후 재사용하고, 미확정인 Shorts 형식·소스 이용권·시청 성과는 확정 주장 금지.
- 고정 Google 무료 Gemini 계정 프로젝트 `gen-lang-client-0938732315`, 모델 `gemini-3.5-flash-lite`, 기존 엔드포인트/키 바인딩. 과거 대표가 동의한 무료 서비스 데이터 정책(사용자 목표/공개 조사/AI 출력이 Google 개선 및 인적 검토에 사용될 수 있음)과 동일 범위만. 실제 청구 연결/무료 잔여 quota 독립 확인 불가 시 `unknown/unverified` 유지. **유료 모델/과금 경로/계정/키 교체·fallback·쿼터 우회 금지**; 무료 사용 조건이 검증되지 않거나 유료 위험이 보이면 provider 전송 전 중단. 유료 전환은 별도 대표 승인 필수.
- 새 YouTube API 검색/조회 **0회**. 실패한 대본 원문 미보존; 이를 재구성해 AI 결과로 표시하거나 과거 중단 업무에 붙이지 말 것. 실패 업무의 `run` 재실행·동일 요청 자동 재송신 금지.

## Codex가 **이 한 번의 실행**에서 해야 할 것
1. GitHub main 최신 커밋 fast-forward, 기존 data/backups/artifacts/.env/미추적/사용자 미디어·비밀키 보호. 위 실전 보고와 관련 코드만 신속히 확인.
2. **안전한 범용 후속 업무 최소 진입점**을 새 실전 path에 적용. 이미 있는 7번째 실패별 reference가 없으므로 구 `create-topic-successor` 등 오래된 CLI를 무리하게 실행하거나 기존 status/reason 가드를 약화하지 않는다. 최신 `script_quality.py`, `video_mission_one.py`, `quality_workflow.py`, `representative_workflow.py`, 관련 테스트만 사용. 새로운 successor는 오직 **검증된 최신 stopped 업무**에서만 생성할 수 있도록 원 7개 서명 체인/목표·입력/원 컷룸/selected_topic/25초/원 research receipt/원 consent·키/계정/무료 정책/실제 10회 소모/마지막 HTTP200-json_parsed-active_operation을 확인. 각 원본 읽기 전용, 서명/attempt 재작성 금지.
3. 목적이 동일한 successor 여러 개를 생성하지 않도록 컷룸 잠금과 `(previous_job_id, new_purpose, writer_contract_hash)` 중복 방지 키를 활용한다. **새 독립 업무 정확히 1개** 및 별도 consent/proposal/grant를 사용하며 원 accepted research·관리자 selection·실측 web만 인계, writer/editor는 pending·versions0. 기존 업무에 유효 대본이 없으므로 인계하지 않는다. 이 최소 진입점은 향후 오류 코드별 별도 CLI가 반복해서 늘지 않도록 설계하되, **과도한 범용 프레임워크 개발/이전7개 이력 마이그레이션 금지**. 새 코드가 지나치게 복잡해지면 scope에 필요한 좁은 구현을 우선하고 실제 실행 진입에 집중한다.
4. **실제 네트워크 없는 오프라인 표적 테스트 1묶음**: 과거7개 stopped 원본 불변, 정확한 선정/계정/모델/서명/receipt/누적 소모/중복 생성 가드, `max_calls=None`, YouTube 신규0, 새 native writer object `responseJsonSchema` → 문자열 보존 변환→기존 inspector→관리자 검토→editor→관리자 검토→임시 같은 컷룸 `awaiting_plan_approval`. 외부 DNS/socket 차단 합성 fixture가 실제 성과 아님을 분명히. 무관한 전체 테스트나 사전 API 진단 반복 금지. **오프라인 실패하면 실제 호출하지 않고 오류 보고 후 중단.**
5. 오프라인 통과하면 실제 후속 업무를 1건 생성하고 **새 제안 prepare → 서명/검토 해시/무료 정책/계정·모델/선정/기존 조사 재사용/10회 기록/임의 내부 상한 None/YouTube 신규0을 승인 범위와 대조 → 새 운영 approve**. 이미 만료되거나 종료된 과거 grant는 history proof로만 검증. 새로운 목적은 "구조화 writer schema에 맞는 새 대본 작성", 이전 응답 재전송 아님.
6. 새 운영 허가 아래 **run을 딱 한 번 호출**해 Gemini writer 실제 한국어 25초 전체 대본 → AI manager writer 검토 → editor 스토리보드 → AI manager editor 검토를 수행한다. native writer schema의 모델 수용/실제 응답 인수를 기록하고 이후 직원 단계는 각기 다른 목적의 정상 흐름에서만 요청. user target_segment=미정이면 AI가 구체적으로 제안하되 사용자 미확정/근거를 반드시 남긴다. manager selected_topic을 topic.title에 정확 복사, 재미있는 문구는 hook/promise에 작성. 장면 shot_type은 demo/detail/card, source_status=pending, fact_status=illustrative/verification_pending, 0~3초 첫 후크, 연속 장면과 25초 길이, 실제 출처 mock=false/model 일치, 실제 미검증 시각 소스/사실표시와 transcript 검증 유지. 잘못된 응답을 자동 수정·원문 덮어쓰기/검사 우회하지 않는다.
7. 두 직원의 AI 관리자 review가 수락됐다면 검증된 `accepted_review_handoff`, `final_evaluation=not_performed_local_handoff`를 **별도 최종 AI 평가를 수행한 것처럼 표시하지 않고**, 원 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`를 `awaiting_plan_approval`로 올리고 실제 기획안/대본/편집 카드 조회까지 검증한다. **대표 승인/반려 클릭, TTS/미디어 생성/렌더/업로드/게시 절대 금지.**
8. 실제 요청 중 429/공급자 무료 quota·billing 차단, schema 수용 실패, 검증/출처 오류, HTTP 실패·타임아웃·불명 전송 등이 있으면 **즉시 stopped 처리**. 새 후속 자동 생성·run 재호출·모델/엔드포인트 변경·유료 fallback·계정 순환/유사 요청 재전송 전부 금지. 정확한 stage/error_code/가능한 안전 진단/response SHA·attempt·사용량을 원장에 기록. 새 API 요청 없이 원인과 제일 좁은 다음 행동 보고.
9. **성공/실패/중단 무조건** `reports/VIDEO_MISSION_01_APPROVED_UNIFIED_SUCCESSOR_REAL_RUN_RESULT_20261112.md` 생성 후 GitHub commit/push. main에서 파일 읽힘 검증 후 중단. 보고서에는 코드 변경/표적 검증·신규 업무 ID/새 제안 review SHA/새 grant, 원7개 원본 보존, 단계별 실제 Gemini 전송/HTTP/토큰(가능한 범위)/신규·누적 횟수와 YouTube 신규0, 실전 native schema 수용 여부, 컷룸 실제 phase·기획/대본/스토리보드 저장 여부/카드 위치, 비용/실제 quota의 독립 미검증 범위, 실패시 구체 원인과 다음 한 단계만 기록. 비밀값과 응답 전문·개인정보·미검증 성과 공개 금지.

시간은 모두 KST(UTC+9). `git clean`, `git reset --hard`, force push, 이전 signed ledger/data/키/미디어 삭제 금지.
