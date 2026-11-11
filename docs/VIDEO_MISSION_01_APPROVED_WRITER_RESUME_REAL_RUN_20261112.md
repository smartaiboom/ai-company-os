# 미션 01 — 대표 승인: 실제 대본 단계 분리 업무 실행
작성일: 2026-11-12 KST

## 현재 사용자 명시적 승인 (이번 신규 분리 업무 1건)
대표가 아래 내용을 명시적으로 승인했다.
> 미션 01의 실제 대본 단계 재개를 승인해. 기존 세 실패 업무와 누적 Gemini 6회·YouTube 각 2회 사용량을 보존하고, Gemini 3.5 Flash-Lite 신규 최대 4회(총 10회), YouTube search.list 및 videos.list 각각 신규 최대 2회(총 각 4회)를 허용해. 기존 조사 자료 재사용 경로에서는 YouTube를 재호출하지 마. 프로젝트 gen-lang-client-0938732315의 무료 서비스와 기존 Google 데이터 처리 동의를 유지하고 자동 재시도·유료 전환·대체 모델은 금지해. 새 독립 업무의 제안·서명·실행 후 실제 대본과 스토리보드를 동일 컷룸의 대표 승인 대기까지만 제출해.

이 승인에는 **동일 미션의 새 분리 업무 1건의 실제 외부 전송과 아래 상한**이 포함되며, 다른 미션/유료 작업/자동 추가 승인에는 확대 적용되지 않는다. 기존 Google 무료 API에 목표·공개 YouTube 메타데이터·직원 작업 결과를 전송하고 서비스 개선·인적 검토가 가능하다는 데이터 정책 동의를 유지한다.

## 대상 및 현재 실사용 상태
- `AGENTS.md`, `reports/VIDEO_MISSION_01_WRITER_STAGE_RESUME_PREPARATION_RESULT_20261112.md`, `reports/VIDEO_MISSION_01_UNSPECIFIED_AUDIENCE_CONTRACT_FIX_RESULT_20261111.md`를 기준으로 한다.
- 컷룸: `company-aba553f29cfb454c8c05bad4abb49969`, 현재 `research_planning`.
- 과거 3개 stopped 업무:
  1. DNS 실패: `qualityprovider-504d90900918450f98dd62b6f7704f1b`.
  2. 연구 검토 JSON 실패: `qualityprovider-299a51b38e6d4d50b651b9fbb39dabad`.
  3. 대본 audience 검증 실패: `qualityprovider-4cbe762cbf554e40af5e7d990ceaf46b`.
- 기존 실제 관리자 선정: 롤토체스(전략적 팀 전투 및 모바일 퍼즐류) 관련 소재, **25초**, evidence IDs `q0:TAidk7sXHk4`, `q0:0FVBz6iWhOY`, `q1:9YjDIwCAnsw`. 조사 직원의 YouTube 메타데이터 10건 원 자료·출처/시간/영수증/선정 SHA를 그대로 참조한다. Codex가 신규 게임명·영상 길이·소재를 독단적으로 재선정하지 않는다.
- 과거 대본 응답은 검증 실패했고 원문이 남지 않았다. 재사용·승격 금지. 현재 대본/편집/대표 승인 대기는 아직 실물 미완료.
- 누적 호출 Gemini **6/10**, YouTube search **2/4**, videos **2/4**. 과거 DNS 실패 1회를 포함해 모든 실패/불명 시도 소모 유지.

## 이번 실행 지시 — 추가 개발보다 실제 업무 완료 우선
1. 최신 main을 안전하게 fast-forward 후 `AGENTS.md`와 이번 문서·직전 결과 보고서를 읽는다. 기존 개발을 재점검·재설계하지 않는다. 로컬 사용자 자료/미추적 파일을 보존한다.
2. 실사용 컷룸과 3개 과거 업무의 서명·시도·active_operation·결과 해시·연결/유효기간을 읽기 전용으로 확인한다. 이전 결과 보고서에서 구현·오프라인 검증 완료한 `video_mission_one create-writer-resume`와 `stage_mission_writer_resume`만 사용한다. 새 분리 업무가 없으면 **한 번만 생성**하며 중복 실행/새 분리 업무 남발 금지. 이전 stopped 업무에 `run` 금지.
3. 새 업무의 계획·연구/selection·YouTube 영수증과 원본 SHA를 검증해 **writer pending 단계부터** 이어간다. 이미 완료된 원 조사·관리자 선정 결과를 새 작업으로 허위 생성하지 않는다. 동일 원 자료 유효기간이 만료·변조됐으면 호출하지 않고 차단 사유를 보고한다. **이번 실행에서는 YouTube search.list와 videos.list 요청을 각각 0회**로 유지한다. 사용자 허용 상한 2+2는 이미 검증된 조사 재사용 경로에서 전송 면허가 아니다.
4. 기존 CLI `prepare`로 새 검토 제안/해시를 생성한다. Gemini 프로젝트 ID 및 YouTube 프로젝트 ID 모두 `gen-lang-client-0938732315` 고정, 무료 계정 사용자 확인 진술을 공급자 독립 검증으로 표시하지 않는다. 남은 공급자 쿼터 수치가 보이지 않으면 `unknown` 유지. 현재 사용자 승인과 일치하는 **과거 소모 6, 새 Gemini 최대 4, 합계 10, YouTube 각 과거2/새 최대2/합계4** 및 고정 모델/엔드포인트·외부 전송 범위·무료 데이터 정책/새 research-review 계약·새 audience 규칙을 검토한 뒤 새로운 검토 해시로 `approve` 서명한다. 과거 제안/서명 재사용·유효기간 우회 금지.
5. 안전가드가 모두 충족되면 고정 `gemini-3.5-flash-lite` 및 `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`를 기존 승인된 방식으로 프로세스 범위에서만 설정하고, **새 업무 `run`을 최대 한 번 실행**한다. Gemini 신규 최대 4회(실패·타임아웃 포함). 호출 전 사용량 예약, 예상치 못한 응답·전송 오류 시 소비 기록 후 중단. 자동 retry/fallback/유료 전환/새 모델/명시적 추가 동의 없는 증액 금지. API 연결 시험 호출·중복 네트워크 진단 금지.
6. 실행이 순조로우면 **AI 대본 직원 작성 → AI 관리자 대본 검토 → 편집 직원 스토리보드 작성 → AI 관리자 편집 검토**를 기존 검증 규칙으로 처리한다. 사용자 target_segment=`미정`은 AI 제안/근거를 `unknowns`에 명시하는 현행 계약을 적용한다. 관리자 선정 25초, 주제, evidence ID/Shorts 분류·권리 미확인 상태 및 한국어 전체 대본·장면 인수 규칙 유지. 안전장치 불일치에 따른 데이터 자동 수정/비검증 수락 금지.
7. 4회 안에서 두 검토가 모두 수락되면 오프라인으로 검증한 `accepted_review_handoff`를 사용해 동일 컷룸에 **`awaiting_plan_approval` 카드**를 제출한다. 별도 AI 최종 평가 호출은 수행하지 않았다고 `final_evaluation=not_performed_local_handoff`로 정확히 표시한다. 대표 승인/반려 클릭과 TTS/WAV·MP4·렌더·게시/업로드는 실행하지 않는다.
8. 실제 모델이 수정 요구를 하거나 4회 내 검증이 끝나지 않으면 조용히 넘어가지 않는다. 현재 상태·소모·실제 결과를 보존하고 자동 재시도/추가 새 업무 없이 중단한다. 승인 범위 변경이나 새 실제 호출 필요 시 보고 후 사용자에게 한 번만 요청한다.

## 결과 보고서는 반드시 GitHub에 저장
성공/실패/차단/부분 완료 **모두** `reports/VIDEO_MISSION_01_APPROVED_WRITER_RESUME_REAL_RUN_RESULT_20261112.md`를 작성, 안전하게 commit/push하고 중단한다.
최소 기록:
- 실제 생성한 새 분리 업무 ID, 이전 3개 stopped 업무 보존, 검토 제안 SHA와 승인 ID/프로젝트·모델
- Gemini 및 YouTube 신규 시도/HTTP/검증 결과, 누적 사용량 및 미확정 응답 포함, 무료 비용 계측의 확인 한계
- 실제 AI 대본/스토리보드/대표 승인 대기 카드의 경로와 provenance(있는 경우); 없는 경우 정확한 실패 단계·코드
- 관리자 선정·원 조사 인계의 출처/해시/25초, AI 검토 성공 여부와 최종 평가 미수행 표시
- 사용자 데이터/키·사용량·승인/실패 이력 보존, 자동 retry·fallback·유료 전환 0회, 다음 한 행동

KST 고정. `git clean`, `git reset --hard`, 강제 push, key/원문 비밀 출력, 사용자 자료·기존 시도·원장·미디어 삭제/수정 금지. 결과가 실패해도 보고서를 생략하지 않는다.
