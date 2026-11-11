# 현재 진행 현황 — 2026-11-11 KST

**Stage B 대표 웹 UI를 연결하고 Chromium에서 검증했다.** 대시보드, 실제 키프레임, 기획·대본 승인·반려, 영상 재생·수정·최종 승인과 이력을 기존 프로젝트 상태에서 확인할 수 있다. Codespaces 비공개 포트 8000에서 실행한다. [대표 웹 UI 결과](VIDEO_REPRESENTATIVE_UI_RESULT.md).

**대표 협업 A단계의 로컬 업무 흐름을 연결했다.** 기획과 영상의 버전·SHA 승인, 피드백 반려와 재보고, 대본 변경 시 기획 재승인, 최종 MP4 검증·완료를 가상 사례에서 실행했다. [대표 승인 흐름 결과](VIDEO_REPRESENTATIVE_APPROVAL_FLOW_RESULT.md).

이전 쇼츠 후보 3개는 참고자료로 보존했고 주제 선정은 보류했다. 대표 승인과 대본·제작 권한은 모두 미부여다. [주제 조사 결과](VIDEO_TREND_TOPIC_SELECTION_RESULT.md).

기존 대본 반려·수정·편집 인수는 오프라인으로 검증했다. [대본 개선 결과](VIDEO_SCRIPT_QUALITY_IMPROVEMENT_RESULT.md).

영상별 보이스 선택 기능을 구현·검증했다. 같은 대상의 실제 B7/10은 범위가 맞는 우선 후보 근거이며 전 채널 기본값이 아니다. [영상별 선택·다음 샘플 결과](VIDEO_VOICE_SELECTION_AND_NEXT_SAMPLE_RESULT.md).

|항목|현재 실제 상태|남은 조건|
|---|---|---|
|영상별 선택|채널/시리즈/영상ID·대상/언어·주제/장르/톤·대표 설정·예외·근거를 입력받아 후보/스타일/이유/결정자·버전·SHA 반환|선정은 제작 정책이며 실제 청취 적합성 검증 아님|
|일관성과 예외|같은 범위의 대표 보이스 우선,대상/톤 변경 재검토. 이유/검토 없는 예외 및 단일7점으로 대표확정 차단|실제 사용자 채널/시리즈 대표 설정을 자동 생성하지 않음|
|실행 예시|동일AI팁2편Puck,시리즈 대표Kore fixture 우선,다른 대상/장르None|Kore 설정은 가상 검증 입력,실제 사용자 지시/청취 아님|
|회사 인수|기존 manager→writer→voice→editor→QA,선택SHA·대상·톤·상위resultSHA 연결.10오프라인콜백/최종stop|codex-authored/mock,실제LLM 추론·신규 미디어 제작 아님|
|실제 사용자 평가|기존 60자·8.04초 B 선호·7/10과 새 148자·21.52초 자연스러움 7/10을 별도 저널에 보존|새 샘플은 목소리·억양 좋음, 속도·쉼 적절함. 추가 음성 실험 보류|
|148자 샘플|Gemini/Puck 실제 WAV 21.520초, PCM16·24 kHz·mono, 전체 디코딩 통과|사용자 청취 완료. 새 대본에 대한 화면 및 낭독 미제작|
|실제 실행|정확 승인 payload 1회, 독립 guard·attempt 1/1 소모, 재시도·fallback 0|기존 60자 guard도 1/1 유지. 공급자 청구액 미확인|
|대본 검증·보존|오프라인 50개 통과. 실제 60초 원본과 기존 음성·저널·시도 기록 등 82개 전후 해시 일치|새 초안·수정본·편집 인수와 평가란은 Codespaces에 보존|

선택/후속 자료: `/workspaces/ai-company-os/data/video_voice_selection/20261110_v1/`.
선택 저널: `company-cff0a76ec19e4b5c9cb51c48eb8671e7`(4개 codex-authored/hypothesis 결정,실 사용자 평가와 구분).
주요 파일: `selection_examples.json`, `decision_journal_refs.json`, `staff_context.json`, 역할별 handoff, `offline_company_result.json`, `before_draft_137_chars_NOT_AUDIO.txt`, `next_narration.txt`, `next_sample.json`, `comparison_review.json`, `next_payload_REVIEW_ONLY.json`, `next_transmission_REVIEW_ONLY.json`, 검증로그/보존결과.
새 내레이션 SHA: `dee1aef757a0c7edac0a6314fef7559591bab1e506ab59066dbb62a5fe3d243b`.
새 검토 payload SHA: `1216b0c8c575c37dbaba04e18d474bbee13c4aa67e33f12edc519466b05cf354`.
청취 파일은 위 루트의 `next_trial/B_next_gemini.wav`에 있다. Codespaces 파일 탐색기에서 내려받을 수 있다.

실제 사용자 평가 원본은 `data/video_voice_feedback/20261110_AB_Puck_7of10/`에,실제 기존 A/B는 `data/gemini_tts_single_free_trial_v1/operation/`에 보존됐다. 이전 영상 피드백(카드지루함/개선체감작음)도 해결됐다고 바꾸지 않았다.

새 청취 저널과 대본 비교 자료는 `data/video_script_quality/20261111_v1/`에 있다. 후보 대본의 후크·유용성·시청 유지와 편집 화면은 사용자 검토 및 소스 확보를 기다린다. 이번 작업의 실 외부 API 요청, 비용, 신규 MP4·WAV는 0이다.
