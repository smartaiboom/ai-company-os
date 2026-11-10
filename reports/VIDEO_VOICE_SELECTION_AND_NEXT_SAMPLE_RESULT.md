# 영상별 음성 선택·다음 샘플 준비 결과 — 2026-11-10 KST

**모든 영상을 Puck으로 고정하지 않는다.** 기존 파일을 재사용해 채널/시리즈/영상의 맥락·대표 보이스·검토된 예외에 따른 선택과 인수 검증을 구현했다. 관련28테스트 통과 후 대상별 대본 누출 검사를 보강하고 해당6테스트를 재확인했다. 기존 회사 엔진 오프라인 실행10콜백도 완료했다. **이번 실 API·다운로드·키 조회·결제·새 음성 생성0,비용0**. 최신 main `aba35da`/AGENTS.md/지정 문서에서 작업했다.

## 실제7점 근거와 권한 경계

기존 실제 사용자 평가는 Gemini3.8 Flash TTS/Puck B가 Melo A보다 훨씬 자연스럽고 B7/10이라는 사실이다. 원본 저널 `company-f99810729a2a42a48b45c8f28f057035` / experience-1과 journal hash `e6bfa73e85d4529f7e061738bdc5019de4fdf32850bd0b2eaa43d4159bf79faf`를 읽어 그대로 재사용했다. 원본 평가/저널에 추가 기록하거나 바꾸지 않았다.

B SHA=`7674f8d8449f5011aff56efd6c4f52ba7d878c43541df6d7043442a4ba831419` /8.04초, A SHA=`a011f8bb6b83e5d3515171bcdf6fc9e9aa09d42844f8e14cfbb8955de18b25a5` /10.982109초. 실제 파일은 `data/gemini_tts_single_free_trial_v1/operation/`에 보존했다. 기존 실 TTS 허가/guard/attempt는1/1 소모 상태 그대로이며 이번 작업이 새 생성을 승인하지 않는다.

이7점은 **그때의 짧은 B 청취 기준선**이다. 모든 Puck 영상의 점수나 전 채널 대표 보이스 설정이 아니다. 후속8점은 목표/hypothesis이고 다른 보이스의 평가와 새 영상 품질은 unassessed다.

## 실제 구현한 선택 계약

기존 `voice_quality.py`에 `select_video_voice`, `voice_policy_for_brief`, `record_voice_selection`을 확장하고 `video_production_company.voice_staff_quality_context(...,video_brief=...)` 및 `quality_workflow.VideoQualityCompany`에 연결했다. 새 공통 엔진/권한·서명 시스템/전송 게이트는 만들지 않았다. 기존 대상 기반 helper도 호환 유지하며, 새 영상별 모드에서는 아래 전체 brief를 명시적으로 받는다.

- 관리자 입력: channel_id/series_id/video_id,대상·언어·주제·장르·톤,브랜드 일관성,기존 대표 보이스의 범위/지정 출처·근거,예외와 변경 이유·검토자·버전,생성/게시 false 및 비용0 제약.
- 직원 출력: provider/model/voice/style,선정 이유/status,실제 청취 연결/미검증 상태,결정 주체 deterministic_policy_for_voice_staff,decision_version=1,brief SHA/decision SHA,생성·게시 권한 false.
- 같은 채널/시리즈·대상/언어/톤의 지정 대표 보이스가 있으면 일관성 우선. 대상·톤 변경 또는 재검토 요청은 자동 교체하지 않고 reassessment_required. 다른 시리즈 설정 유입은 거절한다.
- 대표 설정이 없고 **한국어 직장인 AI 초보자/ko-KR/ai_tips/friendly_explainer**와 실제 근거가 맞는 경우만 Puck 우선 후보. 다른 대상/장르/톤에는 근거 없이 적용하지 않는다. 성별 고정 규칙이나 써보지 않은 목소리의 검증 점수는 없다.
- 예외는 video/series/channel 범위와 이유·검토자(user/manager)·검토 내용·버전을 요구한다. 이 검토 정보는 **제작 의사결정 metadata**이며 API 실행 서명이 아니다. 변경 설명이 비어 있거나 권한을 추가한 요청은 차단한다.
- 새 선택/예외 기록은 별도 기존 ExperienceJournal에 codex-authored/offline_fixture/hypothesis로 저장한다. 원본 사용자 평가와 구분하고 decision SHA로 재기록 중복을 막는다. 단일7점으로 대표 보이스를 자동 확정하지 않으며 현재 단일 근거만으로 evidence_based 대표 설정을 지정하는 것도 거절한다. 미청취 보이스의 user_designated 설정은 선택 가능하되 점수/청취는 unassessed다.

## 실행한 선택 예시와 인수 증거

다음 ID와 대표 설정은 모두 **codex-authored 가상 테스트 입력**이며 실제 사용자 채널/새 대표 보이스 지정을 만들어낸 것이 아니다.

|사례|실행 결과|근거/경계|
|---|---|---|
|demo-tip-1,직장인 AI 팁|Puck 우선|실제 B7/10은 원본 청취 기준선. 새 영상 점수 아님|
|demo-tip-2,동일 범위 두 번째 편|Puck 우선|영상ID/decision SHA는 다르며 전역 고정 없음|
|demo-series-setting,같은 시리즈 대표를Kore로 지정한 fixture|Kore 우선|user_designated 설정 우선 동작 검증. Kore 실청취 없음,점수 null/unassessed. 실제 적용 설정 아님|
|demo-children-story,다른 대상·장르|candidate=null/unassessed|강제 Puck/장르별 성별 추천 없이 별도 탐색 필요|

첫 선택 SHA=`5a69f07d07dccb95ee3d300a48622c1926647b8ab3d06a7e121b0b418c72130d`. 별도 선택 저널 `company-cff0a76ec19e4b5c9cb51c48eb8671e7`,4개 항목·같은 decision 재기록 중복0, journal hash=`e0c87a5baca1ed30c1fc13931dff2fa5c7230268a344df8305a11a36180a6077`. `selection_examples.json`, `decision_journal_refs.json`에 전체 입력·결과·SHA를 보존했다.

기존 엔진으로 새 격리 프로젝트의 manager→writer→voice→editor→QA→final stop을 실행했다.4역할/각1버전/10모의 콜백,각 인수물에 동일 영상별 decision SHA/대상·톤과 실제 상위 result SHA/revision을 연결했다. 영상별 policy로 검증하므로 선택 voice에 없는7점이 전파되거나 목표8점을 관측점수로 바꾸면 거절한다. 장르/대상이 바뀌면 기존 직장인 AI 대본을 자동 전달하지 못하도록 writer 범위도 검사한다.

이는 **실행 가능한 결정·검증 코드 + codex-authored/mock 콜백**이며 실제 LLM 관리자/직원의 추론이 아니다. simulation=true,artifacts={},manager_final_stopped. 새 음성·실제 자막 동기·게시 품질은 미검증이다.

## 다음 실제 테스트 후보 딱 하나

기존137자/327bytes 후보는 원본 그대로 보존하고 새148자/350bytes를 codex-authored로 편집했다. 질문 전 의미 쉼,제안/확정,목요일/금요일 대비를 명시했다. 주제의 시청자 매력·새 음질 개선이 검증된 것은 아니다.

> 금요일 세 시. 회의가 확정된 걸까요? 이건 가상 회의 메모예요. 금요일 세 시는 제안일 뿐, 아직 확정이 아닙니다. 반면, 목요일까지 고객에게 확인하고 다시 알려주겠다는 말은 확인 업무의 기한이죠. 회의 시간은 미정, 확인 기한은 목요일. 두 칸으로 나눠 보세요.

새 내레이션 SHA=`dee1aef757a0c7edac0a6314fef7559591bab1e506ab59066dbb62a5fe3d243b`.
모델/보이스=Gemini Developer API/gemini-3.8-flash-tts/Puck.
정확 스타일=“친근하고 또렷한 한국어 대화체. 질문 뒤 짧게 쉬고 의미 단위로 나눠 말하기. 과장·성우 모사 없음.”

기존 성공 wire를 복사해 위 새 본문·스타일만 반영한 **read-only 검토용** payload814bytes를 저장했다. POST `https://generativelanguage.googleapis.com/v1beta/interactions`, WAV/24000Hz,store=false,max_output_tokens1024,키/새 파라미터 없음. **새 payload SHA=`1216b0c8c575c37dbaba04e18d474bbee13c4aa67e33f12edc519466b05cf354`**. 실제로 전송하지 않았다.

예상20초는 미실측 추정일 뿐20초 이내를 보장하지 않는다. 다음 실험의 실제 발화 수락 범위는 **15~35초**이고 로컬 상한35초/응답2MB 제안이다. 장면3/5/7/5초는 임시 계획이며 합성 후 실제 발화·쉼 길이를 측정해 장면/자막을 맞춘다. 토큰/길이 제한을 벗어나면 입력을 조용히 줄이거나 재호출하지 않고 정확 입력 재검토·새 동의가 필요하다. 이번에는 기존60자 전용 실행 바인딩/20초 수락 코드를 일반화하지 않았다. 검토용 자료는 현재 executable_now=false이며 기존 guard를 재사용할 수 없다.

비교 자료는 (1) 실제60자 B8.04초/전체 자연스러움7/10,(2) 미합성137자 이전 draft,(3) 미합성148자 수정 draft를 구분한다. 후속 사용자 rubric은 **목소리/억양,듣기편함,속도/쉼,후크 전달력**을 각각 평가하도록 before/after를 빈 값으로 준비했고 전체8점 이상은 목표만 제시한다. 원래7점에서 개별 항목 점수를 추정하지 않는다. 기존8초와 긴 새 샘플은 발화·길이·문맥이 달라 점수 차이를 모델/스타일의 단일 효과로 확정할 수 없다.

## 다음1회에 필요한 별도 동의와 현재 상태

새 exact payload SHA/위 본문·스타일/3.8/Puck/출력경로에 대해 **실패 포함1회,Free Tier만·$0 상한,유료전환 금지,retry0/fallback0,Google 무료 입력·출력의 개선/인적 검토 가능성**을 별도로 동의해야 한다. store=false는 무료 데이터 이용정책 거부가 아니다. 실제 계정 잔여쿼터/상업권/해당 긴 발화의 성공은 이번에 조회·검증하지 않았고 publish_ready=false/rights=unverified다. 이전60자 허가는 새 입력 허가가 아니다.

새 예정 출력(현재 없음): `/workspaces/ai-company-os/data/video_voice_selection/20261110_v1/next_trial/B_next_gemini.wav`.
자료 보호 루트: `/workspaces/ai-company-os/data/video_voice_selection/20261110_v1/`.
핵심 파일: `staff_context.json`, `selection_examples.json`, `decision_journal_refs.json`, `writer_handoff.json`, `voice_handoff.json`, `editor_handoff.json`, `qa_handoff.json`, `offline_company_result.json`, `before_draft_137_chars_NOT_AUDIO.txt`, `next_narration.txt`, `next_sample.json`, `comparison_review.json`, `next_payload_REVIEW_ONLY.json`, `next_transmission_REVIEW_ONLY.json`, `execution_receipt.json`.

## 검증과 실제 한계

관련 테스트 한 묶음: `PYTHONPATH=core:companies/video python -B -m unittest tests.test_voice_quality tests.test_quality_feedback tests.test_quality_provider tests.test_tts_execution -v` → **28통과/실패0,6.724초**. 이후 대상이 달라졌는데 기존 대본이 따라갈 위험을 보강하고 `tests.test_voice_quality`만 **6통과/실패0,2.284초**로 재확인했다. 동일 대상 두 편·시리즈 우선·다른 대상 제외·대표 재평가·이유/검토 없는 예외 차단·7/8점 구분·권한 차단·SHA 인수·미실측 길이/비교점수와 기존 품질/서명 경계를 포함했다. 전체 회귀/실 API를 반복하지 않았다. 실제 로컬 적용도 socket/DNS 금지 아래 수행했다. `git diff --check` 통과.

이 검증은 실제 목소리를 새로 듣거나 실제 사용자 대표 설정/장르 적합성을 확인한 시험이 아니다. 대표 보이스 fixture 통과는 Kore 품질·제공 권한을 입증하지 않는다. 코드가 판단하는 것은 명시 맥락·근거·정책 우선순위이며 감각 적합성은 청취 전 미검증이다. 임시 장면표의 합이20초라는 검사만으로 실제 음성 길이를 보장하지 않는다. 이런 false positive를 피하도록 새 점수/실측/생성 허가는 비워 두었다.

보존 확인: 새 선택자료 폴더를 제외한 기존 data/ 및 존재하는 backups/artifacts/.env* **45,609파일 사전/사후 SHA256 변경·삭제0**. 기존 평가 저널/experience-1·A/B·소모된 TTS guard/승인·비용·관리자 원장·키·모델을 보존했다. 사전/사후 manifest는 새 보호 폴더에만 저장했다. GitHub에는 수정 코드·테스트·이 보고서/CURRENT_PROGRESS만 반영하고 로컬 payload/오디오/사용자 자료는 제외한다.
