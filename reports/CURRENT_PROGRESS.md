# 현재 진행 현황 — 2026-11-10 KST

**영상마다 같은 Puck을 강제하지 않는 선택 기능을 구현·검증했다.** 같은 대상의 실제 B7/10은 범위가 맞는 우선 후보 근거이며 전 채널 기본값이 아니다. [영상별 선택·다음 샘플 결과](VIDEO_VOICE_SELECTION_AND_NEXT_SAMPLE_RESULT.md).

|항목|현재 실제 상태|남은 조건|
|---|---|---|
|영상별 선택|채널/시리즈/영상ID·대상/언어·주제/장르/톤·대표 설정·예외·근거를 입력받아 후보/스타일/이유/결정자·버전·SHA 반환|선정은 제작 정책이며 실제 청취 적합성 검증 아님|
|일관성과 예외|같은 범위의 대표 보이스 우선,대상/톤 변경 재검토. 이유/검토 없는 예외 및 단일7점으로 대표확정 차단|실제 사용자 채널/시리즈 대표 설정을 자동 생성하지 않음|
|실행 예시|동일AI팁2편Puck,시리즈 대표Kore fixture 우선,다른 대상/장르None|Kore 설정은 가상 검증 입력,실제 사용자 지시/청취 아님|
|회사 인수|기존 manager→writer→voice→editor→QA,선택SHA·대상·톤·상위resultSHA 연결.10오프라인콜백/최종stop|codex-authored/mock,실제LLM 추론·신규 미디어 제작 아님|
|사용자 평가|원본 실제 B선호·7/10 및 저널experience-1 불변.그 점수는 이전8초B 한정|다른 보이스/새 영상 점수로 전파 안 함,후속8점은 목표|
|다음 후보|기존137자 원본 보존,148자/350bytes 수정본·정확 검토 payload·평가rubric 준비|20초 추정 미실측.실제15~35초 범위·실측 후 장면/자막 정렬|
|새 실행 정책|생성/게시 false,Free Tier만·1회/$0·retry0 제안|새 정확본문·스타일·출력·데이터정책 별도동의와 실행바인딩 필요.이전60자guard 소모1/1 유지|
|검증/보존|관련28통과,대상 대본검사 보강후6통과.기존45609파일SHA 변경·삭제0|실API/다운로드/키조회/결제/새음성0,비용0|

선택/후속 자료: `/workspaces/ai-company-os/data/video_voice_selection/20261110_v1/`.
선택 저널: `company-cff0a76ec19e4b5c9cb51c48eb8671e7`(4개 codex-authored/hypothesis 결정,실 사용자 평가와 구분).
주요 파일: `selection_examples.json`, `decision_journal_refs.json`, `staff_context.json`, 역할별 handoff, `offline_company_result.json`, `before_draft_137_chars_NOT_AUDIO.txt`, `next_narration.txt`, `next_sample.json`, `comparison_review.json`, `next_payload_REVIEW_ONLY.json`, `next_transmission_REVIEW_ONLY.json`, 검증로그/보존결과.
새 내레이션 SHA: `dee1aef757a0c7edac0a6314fef7559591bab1e506ab59066dbb62a5fe3d243b`.
새 검토 payload SHA: `1216b0c8c575c37dbaba04e18d474bbee13c4aa67e33f12edc519466b05cf354`.
예정 출력은 위 루트 `next_trial/B_next_gemini.wav`이며 **아직 파일이 없다**. 기존 실행 코드는60자 전용이므로 검토자료를 즉시 실행할 수 있다고 주장하지 않는다.

실제 사용자 평가 원본은 `data/video_voice_feedback/20261110_AB_Puck_7of10/`에,실제 기존 A/B는 `data/gemini_tts_single_free_trial_v1/operation/`에 보존됐다. 이전 영상 피드백(카드지루함/개선체감작음)도 해결됐다고 바꾸지 않았다.

다음 한 단계는 **보고서의 새148자·스타일·정확 payload 한 건을 검토해 별도 실제1회 테스트 승인 여부를 결정하는 것**. 목소리/억양·듣기편함·속도/쉼·후크전달력은 다음 실제 샘플 청취 때 평가한다. 현재 새 품질은 unassessed,publish_ready=false다.
