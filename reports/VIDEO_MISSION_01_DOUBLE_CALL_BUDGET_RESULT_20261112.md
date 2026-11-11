# 미션 01 — 호출 예산 2배 증액 준비 결과

2026-11-12T08:55:18.280700+09:00 (KST). 최신 main `dfabb28`·AGENTS.md·지정 지시서와 직전 실전/출처 수정/대본 복귀 준비 결과를 확인했다.

## 적용 범위

미션 01의 **향후 독립 후속 업무 1건** 전용 정책 `mission01_double_budget_20261112_v1`을 추가했다. 기존 MAX_CALLS=10 및 과거 10/4/4 서명·실패 업무를 변경하지 않았다. 이번에는 실제 새 업무/제안/서명/승인 이벤트를 만들지 않았다.

| 구분 | 기존 내부 총 한도 | 새 정책 총 한도 | 보존된 실제 소모 | 새 업무 할당 상한 |
|---|---:|---:|---:|---:|
| Gemini 요청 시도 | 10 | 20 | 7 | 13 |
| YouTube search.list | 4 | 8 | 2 | 6 |
| YouTube videos.list | 4 | 8 | 2 | 6 |

새 정책의 YouTube 잔여6/6은 추가 조사를 허가하지 않는다. 선택된 조사 재사용 실행 범위는 **신규 YouTube0/0**으로 새 제안에 명시하며, research 재실행을 provider 호출 전에 차단한다. 내부 승인량은 공급자 무료 quota와 별개다. 공급자 quota=unknown, 청구 검증=unverified를 유지한다.

## 변경한 안전 경로

- `video_mission_one.py`: 네 번째 provenance 실패에만 해당하는 `budget_writer_reference` 및 `create-budget-writer-resume` CLI를 추가했다. 기존 세 가지 실패 전용 가드는 그대로다. 기존 네 실패 업무의 서명 진위·해시/연결·각 시도/active_operation·원 목표/입력·조사 유효기간/영수증·관리자 selection을 검증하고, 모든 실패/불명 소모7회와 원 web2/2를 새 reference에 포함한다. 과거 만료 동의는 역사 증명일 뿐 새 실행 승인이 아니다.
- 새 제안은 정책 버전·총20/8/8·과거7/2/2·신규13/6/6·web 실행0/0·고정 모델/엔드포인트·계정 `gen-lang-client-0938732315`·동일 데이터 정책·원 자료 해시를 구분한다. 기존 prepare/approve의 새 검토 해시와 별도 grant가 필수다. 원본 체인·grant·키/계정/고정 모델·자료 기간을 매 전송 전 검증한다. 신규13회 전송 가드와 과거7회 고정 검증으로 합계20회를 제한한다. 실패/불명 요청도 소모하며 자동 retry/fallback/유료 전환은 없다.
- `representative_workflow.py`: 컷룸/원업무 잠금 아래 새 경로로만 독립 업무를 만들고, plan·수락 연구·selection·원 web 자료를 그대로 인계한다. 빈 consent/attempt/session에서 writer pending부터 시작한다. 중복 생성은 거부한다. 원 서명·실패 대본을 복제/승격하지 않는다. 대본/편집 관리자 수락 후 기존 accepted_review_handoff로 동일 컷룸 대표 승인 대기까지만 제출한다(별도 AI 최종 평가 아님).
- 기존 프로젝트별 예산 원장/어댑터는 새 프로젝트 opt-in 전용으로 미션 이관을 하지 않도록 설계돼 있다. 이번에는 마이그레이션·예산 UI·동의 갱신 개발 없이 기존 미션의 서명/전송 한도 경로를 재사용했다. 다른 제품/기존 프로젝트 정책은 증액하지 않았다.

## 오프라인 검증과 실제 보존

`PYTHONPATH=core:companies/video python -B -m unittest tests.test_video_mission_one tests.test_script_quality tests.test_quality_provider`: **41개 통과, 12.975초**. 임시 합성 저장소·mock native HTTP·DNS/socket 차단에서 실행했다. `git diff --check` 통과.

합성 실패4개를 만든 뒤 새 경로에서 원 가상 선정/25초·원 evidence를 인계해 writer 작성→검토→editor 작성→검토의 신규4회로 같은 임시 컷룸 `awaiting_plan_approval`에 도달했다. 최상위 provenance는 offline_http_fixture이며 실제 대본으로 가장하지 않는다. 새 provider 전송 승인 전 차단, 구 proposal/서명 재사용·정책 총량/소모/신규량·YouTube8/8 초과 제안·키/모델/조사/선정/입력 변조 및 중복 생성 거부를 확인했다. 누적20 경계는 명시적 합성 메모리 상태에서 신규12회 허용/13회 소모 후 추가 전송 거부로 검증했으며, 실제13회 호출이나 실제 소모로 기록하지 않았다. 원4개 실패 파일 바이트/서명 불변, 신규 mock timeout1회 소모 후 재호출 금지도 확인했다.

**실제 provider API0회, 실제 사용 원장/승인 변경0건, 신규 실제 업무/서명0건.** 원4개 stopped 업무와 컷룸 관련14개 JSON/consent/lock의 시작/종료 SHA-256 동일. 네 번째 업무에 대한 새 적격성 함수만 읽기 전용으로 호출해 검증했다. 실제 누적 Gemini7·YouTube2/2, 컷룸 research_planning, 원 조사10건 및 관리자25초 선정은 그대로다. 원 영수증 SHA `651b936fb9542aa188a3bf3a0a3ab803e914b8285f26a9e043fd041a9aeeb04b`, 선정 SHA `e4296e6a276d6462599d3c3bdb1a86bc5fb3ba2472bfd53eb78d98e6a8d47587` 유지. 기존 data/, backups/, artifacts/, .env·키·음성/영상·미추적7개 파일을 수정/삭제하지 않았다. GitHub 저장을 위한 통신만 수행했다.

## 다음 실행 승인 요청 1건

**이 새 정책의 독립 대본 후속 업무1건 생성→새 제안 검토/서명→Gemini 신규 최대13회(과거7회 포함 총20회), 신규 YouTube0회, 동일 무료 프로젝트/고정 모델·데이터 정책, 자동 재시도·fallback·유료 전환 없이 대표 컷룸 기획 승인 대기까지만 실행**하는 별도 대표 승인이 필요하다. 기존 stopped 재실행/만료 동의 재사용/대표 승인 클릭·TTS/렌더/게시를 포함하지 않는다. 공급자 quota와 실제 모델 계약 준수는 미검증이다. 이번 소스2개·테스트1개·이 보고서만 commit/push 후 중단한다.
