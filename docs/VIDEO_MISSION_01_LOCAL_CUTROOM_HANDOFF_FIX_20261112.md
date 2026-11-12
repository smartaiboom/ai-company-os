# 미션 01 — AI 수락 완료 산출물의 기존 컷룸 인수 오류만 수정
2026-11-12 KST

## 확정 사실 / 대표 목표
이미 영상 생성 전체 한 사이클과 음성 개선은 과거 완료 경험이 있고, 현재 주제 선정·대본 AI의 품질 향상을 진행하고 있다. 실제 미션 01에서 이번에는 AI 직원 대본 자막 수정 → AI 관리자 대본 검토 accept → AI 편집 직원 실제 스토리보드 생성 → AI 관리자 편집 검토 accept까지 **네 단계 모두 실제 Gemini HTTP200/서버 검증 통과**. 최종 원장 `needs_user_review`의 실제 수락 대본/스토리보드가 있다. 하지만 같은 컷룸에 전달하는 후속 로컬 CLI `report_plan`에서 `mission_scope_mismatch`로 실패해 컷룸은 `research_planning`이다. **대본·스토리보드 재생성 및 외부 API 호출이 아니라, 이 로컬 인수 오류 한 가지를 해결하여 기획안/대본/스토리보드를 대표 승인 대기 화면에 보여주는 것이 목표**다.

Codex 주간 사용량 부족: 전체 감사·과도한 반복 테스트·장문 보고·무관 리팩터링/기능 추가 금지. 이미 승인받은 미션 인계 범위로 진행.

## 사실 확인
- 최신 main, `AGENTS.md`, `reports/VIDEO_MISSION_01_FIX_FIXTURE_USAGE_AND_EXECUTE_RESULT_20261112.md`, 실제 job `qualityprovider-57981d7b32e14a6cbed733eb1f316f61`, 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`, 관련 `representative_workflow.py`, `video_mission_one.py` 및 report_plan/mission_scope 관련 최소 함수만 읽기.
- writer versions3/reviews3 accepted_by_ai_manager, editor versions1/reviews1 accepted_by_ai_manager, research accepted, 실제 25초 연구/AI 관리자 선정/evidence 보존. 두 번째 beat 자막은 2줄 각 16폭/20폭으로 defects=[]. 원본 job status=`needs_user_review`; final.source=`accepted_review_handoff`, provider=system, final_evaluation=`not_performed_local_handoff`. 원 데이터의 서명·해시·attempt·grant/승인/원 시청자 제안 변경 금지.
- 기존 컷룸 research_planning과 새로운 독립 signed continuation job 사이의 **mission scope/anchor lineage 검증이 실제로 어떤 필드를 비교하는지** 식별. 모든 job/컷룸을 같은 scope로 강제로 바꾸거나 검사를 끄거나 히스토리를 덮어쓰지 않는다. 실패 원인을 프로그램/원장/연결 키를 대조해 정확히 확인하고, **새 업무가 원 미션에 합법적으로 속함을 증명하는 최소 reference/검사 경로**만 고친다. 잘못 연결된 데이터라면 외부 호출 없이 보고·중단. 이전 진단 없이 거친 우회 금지.
- **최소 표적 오프라인 테스트 1개**로 실제 original mission → signed successors → accepted writer/editor result → 동일 임시 컷룸 `awaiting_plan_approval` 을 확인, 다른 미션·서명 변조/중복 카드/미수락 job은 거부하도록 확인. 합성 검증 fixture와 실제 검증을 구분. 전체 테스트 반복 금지.
- 최소 수정·테스트 성공 시 **실제 이미 저장된 산출물의 report_plan/컷룸 인수만 정확히 1번** 실행. 작업 전체 `run` 재실행하지 않음. Gemini/YouTube 등 모든 외부 API **0회**, 신규 job/proposal/grant/consent 0건. **동일 기존 컷룸**의 `awaiting_plan_approval`와 화면/저장 데이터에 실제 기획·대본·스토리보드 카드가 모두 있는지 readback. 대표에게 실제 승인 버튼/클릭을 대신 하지 않는다. TTS·MP4/렌더·업로드·기존 영상/음성 자료 수정 금지.
- 실패 시 원본 보존하고 추가 수행 없이 간결 보고. 성공/실패 모두 `reports/VIDEO_MISSION_01_LOCAL_CUTROOM_HANDOFF_FIX_RESULT_20261112.md`에 원인·최소 수정 파일·표적 테스트·실제 컷룸 상태 및 사람 대표가 다음에 해야 할 일 1개를 짧게 기록해 GitHub main에 commit/push/readback 후 중단. 실제 원장과 컷룸 정보만 보고, 비밀/전체 대본/원시 응답 전문 포함 금지.
- Gemini 누적21회(과거 미수신 포함)·YouTube search2/videos2 보존, 이번 외부 호출0. 원 data/backups/artifacts/.env/미추적 파일·키·음성/미디어·stopped/paused 기록 모두 보존. KST, git clean/reset --hard/force push/데이터 삭제 및 가드 우회 금지.
