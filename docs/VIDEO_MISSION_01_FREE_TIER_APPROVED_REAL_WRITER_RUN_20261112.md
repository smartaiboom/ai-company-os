# 미션 01 — 대표 승인된 무료 API 실제 대본·스토리보드 실행
작성일: 2026-11-12 KST

## 사용자가 방금 명시적으로 승인한 범위
사용자는 앞선 "무료 API 임의 호출 상한 폐지" 작업 결과를 확인한 뒤 "**응 승인할게 제발좀 진행하자**"라고 승인했다. 현재 승인한 실제 작업은 **기존 조사 및 AI 관리자 선정 결과를 재사용해 동일 미션 01 컷룸에 실제 한국어 전체 대본·스토리보드를 제출하고 대표 기획 승인 대기까지만 진행하는 새 독립 후속 업무 1건**이다.

**무료 전용·임의 내부 횟수 상한 없음.** 이전 10/20/4/8 숫자는 공급자 무료 한도가 아니므로 새 실행의 차단 조건으로 사용하지 않는다. 그러나 자동 재시도·동일 작업의 불필요한 반복 요청은 금지한다. 성공 산출물과 이미 검증된 조사·선정을 재사용한다. 공급자 429/실제 무료 할당량 제한·결제 요구·응답 불명·실패 중단 조건을 존중한다. 유료 모델/계정·결제 연결·유료 fallback은 별도 대표 명시 승인 없이는 절대 금지한다. **예산 관리 기능 추가 개발 금지**.

Google 무료 프로젝트 `gen-lang-client-0938732315`, 모델 `gemini-3.5-flash-lite`, 고정 엔드포인트 `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`. 이전에 명시적으로 동의한 무료 API 데이터 정책(사용 입력/출력이 Google 서비스 개선 및 인적 검토에 사용될 수 있음)과 동일 목표·전송 범위 내에서만 진행한다. YouTube Data API는 **기존 자료 재사용 경로에서 신규 검색/조회 0회**, 계정/모델/키/범위 변경 금지. 무료 상태에 대한 로컬 소유자 진술을 공급자 청구 독립 검증으로 표현하지 않는다.

## 기존 확인된 코드·기록
- `AGENTS.md`, `reports/AI_COMPANY_OS_FREE_TIER_NO_ARBITRARY_CALL_CAP_RESULT_20261112.md`, `reports/VIDEO_MISSION_01_WRITER_PROVENANCE_CONTRACT_FIX_RESULT_20261112.md`를 읽고 기존 구현을 그대로 사용.
- 최신 코드의 `create-free-writer-resume` 및 `stage_mission_free_writer_resume`가 새 경로. `mission01_free_provider_limits_20261112_v1`, 기본 `max_calls=None`, 별도 신규 제안/검토 해시/grant 서명 요구. 임의 `--explicit-max-calls`를 지정하지 말 것. 기존 create-budget-writer-resume(20/8/8) 경로는 사용하지 않는다.
- 원 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`, 시작 상태 `research_planning`. 4개 과거 stopped 업무: DNS 실패 `qualityprovider-504d90900918450f98dd62b6f7704f1b`; 연구 review JSON 실패 `qualityprovider-299a51b38e6d4d50b651b9fbb39dabad`; 대본 audience 실패 `qualityprovider-4cbe762cbf554e40af5e7d990ceaf46b`; 대본 provenance 실패 `qualityprovider-bb394ad486014277998d8a64b62e8199`.
- 과거 실제 사용 Gemini 7회(실패·불명 포함), YouTube search.list 2회, videos.list 2회. 모두 **히스토리 원장 보존/집계**; 새 경로 소모와 합쳐 관측, 단 새 free-tier 정책의 임의 승인 상한으로 취급하지 않는다.
- 원 조사 YouTube 실제 메타데이터10건과 AI 관리자 실제 선정: 전략적 팀 전투/롤토체스 및 모바일 퍼즐류, 25초, evidence IDs `q0:TAidk7sXHk4`, `q0:0FVBz6iWhOY`, `q1:9YjDIwCAnsw`. 원 계획 SHA `23ee4a8e9e2ab0079a5cf881be852c4f823eac0422f33fde1f357289f48b5c74`, 조사 receipt SHA `651b936fb9542aa188a3bf3a0a3ab803e914b8285f26a9e043fd041a9aeeb04b`, 관리자 선정 SHA `e4296e6a276d6462599d3c3bdb1a86bc5fb3ba2472bfd53eb78d98e6a8d47587`. 기존 조사 유효기간 및 원본해시·과거 서명 검증 필수. 소재/길이 재선정·임의 자료 생성 금지.
- 최신 `quality_workflow.py`의 **대본 provenance.mock=false, provenance.model=실제 bound model** 시스템 지시 개선을 실제 실행에 사용. `target_segment=미정`은 기존 AI 추론·근거 표식 검증을 적용.

## Codex 지시: 이번에는 실제 제작을 수행
1. GitHub 최신 main을 기존 파일 보존한 채 안전하게 fast-forward 반영. 범위 내 파일과 저장된 원본 자료만 확인한다. **유료/예산/키/계정 재개발, DNS 시험 호출·무관한 코드 분석/테스트 반복 금지**.
2. 기존 네 업무, 동일 컷룸, 보존된 조사/선정의 서명·해시·사용량·원본 유효기간·키/계정 바인딩을 **읽기 전용** 검증. 만료·변조·불일치면 외부 요청 전에 중단하고 정확한 차단 원인만 보고.
3. 새 분리 업무가 아직 없다면 `create-free-writer-resume` 경로로 **정확히 한 건** 생성. 과거 stopped 업무를 직접 run/재시도 금지. 새 업무에 원 계획·연구 accepted 결과·선정·YouTube receipt를 원 provenance로 인계하고 writer pending부터 시작. 새 consent/attempt/session은 새 업무에서 빈 상태로 시작. 사용자 실제 실행 승인을 벗어난 다른 목표/프로젝트로 전송 금지.
4. 기존 CLI에서 신규 제안 `prepare`→정확한 review_hash/무료 서비스/고정 모델/계정/데이터 정책/선정25초·원 해시/YouTube 신규0·내부 임의상한 None을 검토→새 `approve` 서명. 이 대화의 사용자가 현재 승인한 범위만 전송 grant에 반영하며 이전 서명 또는 만료 동의를 재사용하지 않는다. 제안·승인 내용 불일치면 외부 전송 전에 중단. **실제 무료 모델인지 확정하지 못하거나 청구 위험 설정이면 중단**; 기존 사용자 확인과 서명 근거 범위를 분명히 할 것.
5. 새 업무를 **단 한 번** run하여 실제 Gemini를 호출한다. 성공 시 writer 실제 한국어 대본 → manager writer review → editor 스토리보드 → manager editor review. AI가 필요하다고 검토한 정상 revision이 지원되는 경우에도 기계적 자동 retry나 stopped 재실행, 같은 요청 무한 반복 금지. 한도가 없다는 뜻은 무제한 자동 요청 허가가 아니다. 매 요청은 목적·작업 단계가 달라야 하고 사용량/토큰/응답 상태를 기록한다. HTTP429/quota/billing 제한, 오류, 응답 불명, provenance/대본 검증 실패 시 기존 stopped 정책을 지키고 자동 우회/수선/새 successor 생성 없이 보고.
6. 정상 두 검토 수락 후 별도 AI 최종 평가를 생성하지 않았다는 점을 `accepted_review_handoff` / `final_evaluation=not_performed_local_handoff`로 표시하며 **동일 컷룸 `awaiting_plan_approval`** 등록까지만 진행. 대표 승인/반려 버튼 누르지 않음. 실제 음성·영상 제작, TTS/MP4/렌더/게시/업로드 금지. Shorts 여부·영상 소스 권리·조회 성과의 검증되지 않은 주장 금지.
7. 성공/실패/차단 어느 경우라도 `reports/VIDEO_MISSION_01_FREE_TIER_APPROVED_REAL_WRITER_RUN_RESULT_20261112.md` 파일을 **반드시** 작성해 GitHub commit/push 후 중단. 보고서에는 새 업무 ID와 승인/제안 SHA, Gemini 단계별 실제 HTTP·검증 상태·신규 시도/누적 횟수 및 토큰(가용한 경우), YouTube 신규 0, 컷룸 실제 phase, 원 조사/선정 재사용 해시, 실제 대본/스토리보드 카드 위치와 출처(있으면), 실패시 정확한 검증 코드/근거·다음 한 단계, 비용은 확인된 것만 기록. 종료 전 보고서 파일이 GitHub main에서 읽히는지 확인한다.

## 절대 금지
네 stopped 업무의 signed consent/attempt/active_operation·실패/unknown 사용량을 수정/삭제/재생성하지 않는다. data/, backups/, artifacts/, .env, 미추적 파일, 사용자 키·음성/영상은 보존. git clean/reset --hard/force push, 임의 fallback/유료 전환, 쿼터 우회·계정 순환, 실패 자동 재전송, fixture를 실제 결과로 가장하기 금지. KST 고정.
