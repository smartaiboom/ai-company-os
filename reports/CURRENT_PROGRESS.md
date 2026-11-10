# 현재 진행 현황 — 2026-11-11 KST

**승인된 148자 Gemini/Puck 실제 음성을 생성했다.** 1회 POST에서 HTTP 200을 받았고 원본 WAV는 21.520초다. [실행 결과](GEMINI_TTS_148_CHAR_REAL_ONE_SHOT_RESULT.md).

영상별 보이스 선택 기능을 구현·검증했다. 같은 대상의 실제 B7/10은 범위가 맞는 우선 후보 근거이며 전 채널 기본값이 아니다. [영상별 선택·다음 샘플 결과](VIDEO_VOICE_SELECTION_AND_NEXT_SAMPLE_RESULT.md).

|항목|현재 실제 상태|남은 조건|
|---|---|---|
|영상별 선택|채널/시리즈/영상ID·대상/언어·주제/장르/톤·대표 설정·예외·근거를 입력받아 후보/스타일/이유/결정자·버전·SHA 반환|선정은 제작 정책이며 실제 청취 적합성 검증 아님|
|일관성과 예외|같은 범위의 대표 보이스 우선,대상/톤 변경 재검토. 이유/검토 없는 예외 및 단일7점으로 대표확정 차단|실제 사용자 채널/시리즈 대표 설정을 자동 생성하지 않음|
|실행 예시|동일AI팁2편Puck,시리즈 대표Kore fixture 우선,다른 대상/장르None|Kore 설정은 가상 검증 입력,실제 사용자 지시/청취 아님|
|회사 인수|기존 manager→writer→voice→editor→QA,선택SHA·대상·톤·상위resultSHA 연결.10오프라인콜백/최종stop|codex-authored/mock,실제LLM 추론·신규 미디어 제작 아님|
|사용자 평가|원본 실제 B선호·7/10 및 저널experience-1 불변.그 점수는 이전8초B 한정|다른 보이스/새 영상 점수로 전파 안 함,후속8점은 목표|
|148자 샘플|Gemini/Puck 실제 WAV 21.520초, PCM16·24 kHz·mono, 전체 디코딩 통과|사용자 청취 및 실측 기준 장면·자막 정렬|
|실제 실행|정확 승인 payload 1회, 독립 guard·attempt 1/1 소모, 재시도·fallback 0|기존 60자 guard도 1/1 유지. 공급자 청구액 미확인|
|검증·보존|관련 오프라인 30개 통과, 새 WAV·승인·시도 기록 대조. 이전 A/B 해시 및 예약 연결 확인|WAV와 로컬 기록은 Codespaces에 보존|

선택/후속 자료: `/workspaces/ai-company-os/data/video_voice_selection/20261110_v1/`.
선택 저널: `company-cff0a76ec19e4b5c9cb51c48eb8671e7`(4개 codex-authored/hypothesis 결정,실 사용자 평가와 구분).
주요 파일: `selection_examples.json`, `decision_journal_refs.json`, `staff_context.json`, 역할별 handoff, `offline_company_result.json`, `before_draft_137_chars_NOT_AUDIO.txt`, `next_narration.txt`, `next_sample.json`, `comparison_review.json`, `next_payload_REVIEW_ONLY.json`, `next_transmission_REVIEW_ONLY.json`, 검증로그/보존결과.
새 내레이션 SHA: `dee1aef757a0c7edac0a6314fef7559591bab1e506ab59066dbb62a5fe3d243b`.
새 검토 payload SHA: `1216b0c8c575c37dbaba04e18d474bbee13c4aa67e33f12edc519466b05cf354`.
청취 파일은 위 루트의 `next_trial/B_next_gemini.wav`에 있다. Codespaces 파일 탐색기에서 내려받을 수 있다.

실제 사용자 평가 원본은 `data/video_voice_feedback/20261110_AB_Puck_7of10/`에,실제 기존 A/B는 `data/gemini_tts_single_free_trial_v1/operation/`에 보존됐다. 이전 영상 피드백(카드지루함/개선체감작음)도 해결됐다고 바꾸지 않았다.

다음 단계는 새 WAV의 전체 자연스러움(10점), 목소리·억양, 듣기 편함, 속도·쉼, 후크 전달력을 청취 평가하는 것이다. 새 샘플은 청취 전 미평가이며 게시 준비 상태는 false다.
