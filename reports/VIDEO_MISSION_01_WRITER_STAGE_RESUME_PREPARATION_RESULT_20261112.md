# 미션 01 — 대본 단계 복귀 오프라인 준비 결과

2026-11-12T08:30:05.858143+09:00 (KST). 최신 main `5af3ddc`와 AGENTS.md, 지정 지시서 및 직전 미션/미정 시청자 계약 수정 결과를 확인했다. 예산 개발·기존 프로젝트 예산 전환·환경/키/무료 등급 재점검은 하지 않았다.

## 최소 변경

기존 create-resume은 DNS 실패 전용이고 create-successor는 연구 관리자 검토 실패 전용이므로 세 번째 대본 실패에 사용할 수 없었다. 두 가드를 완화하지 않고 video 도메인에 `create-writer-resume` CLI와 `stage_mission_writer_resume`을 추가했다.

- 새 경로는 세 번째 업무의 대본 audience 검증 실패, 완료된 review/execute 시도 2건(역할 결과 validated/json_parsed), 원 active_operation, 연구 accepted 상태와 미작성 writer/editor를 검사한다. 첫 DNS→두 번째 연구 검토 실패→세 번째 대본 실패 체인을 기존 서명 진위·상태/입력·계획·조사·영수증·selection 해시로 검증한다. 만료된 과거 동의는 역사 증명에만 사용한다.
- 새 독립 업무는 원 목표/사용자 입력·계획·수락된 연구/선정 및 원 employee_web 자료를 출처 그대로 참조하고 대본 pending부터 시작한다. 원본 획득시각/보존기간 및 evidence ID는 기존 usable_observations/validate_selection으로 검사한다. 과거 실패 대본 응답은 복원·재사용·수락하지 않는다. 빈 신규 attempts/sessions/consent로 시작하며 별도 새 제안 해시·서명이 필수다.
- 소모 6/신규 최대4/총10과 YouTube 각각 소모2/신규 상한2/총4를 새 서명 검토 범위에 포함한다. 동일 원 계정·데이터 정책 및 원 키 바인딩을 새 승인/전송 경계에서 검사한다. 매 전송 전 원본 체인·자료·선정 해시와 새 grant를 검증한다. 이미 보존된 조사 배치는 재수집하지 않으며 연구 재실행도 차단한다. 잔여량은 실행 승인으로 취급하지 않는다.
- 기존 대본 이후 흐름은 writer 작성/검토, editor 작성/검토, 별도 finalize까지 최소5회가 필요했다. 새 경로는 4개 역할 호출의 관리자 수락 후, 원 수락 검토의 met checks와 결과 해시를 로컬에서 묶어 대표 검토 대기로 넘긴다. 별도 AI 최종 평가를 생성하거나 검사를 met로 승격하지 않는다. final.source=`accepted_review_handoff`, provider=`system`, 이벤트=`system_review_handoff`; 보고 카드에도 `final_evaluation=not_performed_local_handoff`를 남긴다. 기존 다른 경로의 finalize 호출은 유지한다. 수정 요구 등으로 4회를 소모하면 한도에서 중단하고 자동 재시도하지 않는다.

## 표적 검증 — 1회

`PYTHONPATH=core:companies/video python -B -m unittest tests.test_video_mission_one tests.test_script_quality`: **29개 통과, 7.780초**. 임시 저장소·합성 fixture와 mock native HTTP 응답만 사용하고 DNS/socket을 차단했다. `git diff --check` 통과. 합성 데이터는 실제 실패 응답 재현이나 실제 AI 산출물이 아니다.

추가 통합 fixture는 합성 DNS→연구 검토 실패→대본 audience 실패를 만든 뒤 새 분리 업무에서 **execute(writer)→review(writer)→execute(editor)→review(editor)** 정확히4회, 신규 YouTube0회로 동일 임시 컷룸 `awaiting_plan_approval`에 도달했다. 원 manager_selection·evidence/영수증·미정 입력과 한국어 대본의 명시적 AI 대상 추론/근거·길이·편집 인수를 유지하고 fixture provenance를 확인했다. fixture는 가상 게임/34초로 실제 25초 결과와 구분한다.

새 승인 전 전송 차단, 구 해시·만료된 새 제안·다른 계정·키 변경·소모/신규 상한/selection/원 입력/영수증 변조 거부, 중복 새 업무 생성 금지, 과거 가드 유지, 4회 소모 후 추가 호출 차단을 검증했다. 과거 합성 업무 파일 바이트 불변도 확인했다. 기존 미정/확정 audience 및 주제 변조·검토 계약 회귀도 함께 통과했다. 실제 provider 실행이나 브라우저 시각 검증은 하지 않았다.

## 실제 상태·보존

실제 외부 Gemini/YouTube API 요청 **0회**, 실제 미션 실행/신규 업무 생성/제안 승인 **0건**. GitHub pull/commit/push는 요청된 코드 저장 작업이다. 로컬 실제 업무에 대해서는 writer_reference만 읽기 전용으로 실행해 적격성을 확인했다. 실제 새 제안이나 서명을 만들지 않았다.

세 stopped 업무와 컷룸 관련 JSON/consent/lock 등 **11개 파일의 작업 시작/종료 SHA-256 동일**을 확인했다. 실제 세 번째 업무는 script_audience_mismatch, 기존 active_operation·실패/시도/동의 그대로다. 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`는 **research_planning**이다. Gemini 원 시도 합산 **6/10**, YouTube 원 배치 search **2/4**·videos **2/4** 유지(복제 캐시 중복 집계 없음).

실제 관리자 선정 게임·25초·증거 ID `q0:TAidk7sXHk4`, `q0:0FVBz6iWhOY`, `q1:9YjDIwCAnsw`를 변경하지 않았다. 원 조사 영수증 SHA `651b936fb9542aa188a3bf3a0a3ab803e914b8285f26a9e043fd041a9aeeb04b`, 선정 SHA `e4296e6a276d6462599d3c3bdb1a86bc5fb3ba2472bfd53eb78d98e6a8d47587`를 읽기 전용 참조 검증했다. 기존 사용자 data/, backups/, artifacts/, .env·키·음성/영상·미추적7개 파일을 수정/삭제하지 않았다.

## 다음 한 단계 — 별도 사용자 승인 1건 필요

승인 범위: **기존 조사·선정을 재사용하는 새 대본 단계 분리 업무 1건 생성→새 제안 검토/서명→실행, Gemini 신규 최대4회(과거6회 포함 총10회), YouTube 각 신규 최대2회(각 총4회), 동일 Google 무료 프로젝트 `gen-lang-client-0938732315`·동일 데이터 정책, 유료 전환·자동 재시도·fallback 금지, 대표 컷룸 기획 승인 대기까지만**. 보존된 조사 사용 경로에서는 신규 YouTube 호출을 하지 않는다. 이 범위를 아직 승인받거나 실행하지 않았다. 원 조사 유효기간과 출처는 미래 생성/전송 때 다시 로컬 검증하며 만료/변경 시 중단한다.

실제 모델의 새 audience 계약 준수·의미적 품질은 미검증이다. 4회 내 수정이 필요하면 성공을 보장하지 않으며 중단 상태를 보고한다. TTS/렌더/게시·대표 승인·기존 stopped 재전송은 범위 밖이다. 소스2개·관련 테스트1개·이 보고서만 GitHub에 commit/push 후 중단한다.
