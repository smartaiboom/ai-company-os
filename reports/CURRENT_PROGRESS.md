# 현재 진행 현황 — 2026-11-10 KST

**실제 사용자 A/B 평가 반영: Gemini/Puck B가 훨씬 자연스럽고7/10.** 이 선호·점수만 verified로 보존하고, 같은 대상의 음성 추천·관리자 기준·후속 인수 검증을 구현했다. [피드백 반영 결과](VIDEO_VOICE_USER_AB_FEEDBACK_RESULT.md).

|항목|현재 실제 상태|남은 조건|
|---|---|---|
|실제 사용자 평가|동일60자 A/B에서 B선호·B7/10,provenance=user_structured,verification=verified|특정 발음/억양/속도 결함·일반 모델 우열·게시 합격 증거는 아님|
|경험 보존·범위|별도 ExperienceJournal experience-1. 동일 평가 재기록 중복0. video/한국어 직장인 AI 초보자만 선택|다른 한국어 대상/분야에 자동 일반화 안 함|
|음성 직원·관리자|같은 대상은 Gemini3.8 Flash TTS/Puck 우선 추천. baseline7,후속 목표8점은hypothesis|추천은 추가 생성 권한 아님. 새 품질은 청취 전unassessed|
|인수 기능|기존 회사엔진 writer→voice→editor→QA 실행. 본문·result hash/revision·장면시간·자막·권한·점수 의미 검증|codex-authored 오프라인 callbacks,실제LLM 자율판단/새 영상 제작은 아님|
|다음 샘플|가상 회의의 제안 시각/확인 기한 구분. 정확137자/327bytes·20초 목표·4장면·발음/방향 인수파일|새 exact-payload/실행 바인딩·별도1회 동의 후 생성 가능.20초 발화·8점 달성 미검증|
|이번 실행|외부 실API0·비용0·신규 실WAV/영상0. 관련33테스트 통과/실패0,4.818초|추가 합성/모델목록·쿼터조회/실행승인 생성 없음|
|기존 실물|이전 Gemini B8.04초·PCM16/24kHz/mono,이전 A10.982109초·44.1kHz,둘 다SHA/probe/decode 확인|소모된 실제 생성1/1 guard/attempt 유지,재실행 금지|
|보존·게시|기존45585파일 SHA 변경·삭제0.저널/키/영상/원장 보존,publish_ready=false,rights=unverified|실제 새 음성·영상/권리/사용자 재평가 필요|

피드백/다음 인수자료: `/workspaces/ai-company-os/data/video_voice_feedback/20261110_AB_Puck_7of10/`.
핵심 파일: `feedback_receipt.json`, `staff_context.json`, `writer_handoff.json`, `voice_handoff.json`, `editor_handoff.json`, `qa_handoff.json`, `next_narration.txt`, `next_sample.json`, `offline_workflow_result.json`, `execution_receipt.json`, `scope_checks.json`, `tests.log`, `preservation_result.json`.
저널 ID: `company-f99810729a2a42a48b45c8f28f057035` / feedback ID: `experience-1`.
평가 SHA: `8c4f6a2a7bcd6dbfaf23ea3868bef5f92429146e5bfc644a5f81550ec5da0bab`.

실제 A/B 파일은 `/workspaces/ai-company-os/data/gemini_tts_single_free_trial_v1/operation/`의 `A_reference_melo.wav`, `B_gemini.wav`이며 이번에 재합성하지 않았다. 이전 실제1회 결과는 [실행 보고서](GEMINI_TTS_ONE_SHOT_UNBLOCK_RESULT.md)에 보존한다. 전체 영상에 대한 기존 사용자 피드백(카드 지루함/개선체감 작음)은 해결됐다고 바꾸지 않았다. Qwen 재시험/새60초 렌더/GUI 개발도 하지 않았다.

다음 할 일은 **보고서의20초 후보 한 건을 검토해 새 exact-payload1회 테스트 승인 여부 결정**. 아직 호출하지 않았으며 실제 사용자 평가가 있어야8점 목표 달성을 판단할 수 있다.
