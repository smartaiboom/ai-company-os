# 미션 01 — 대상 시청자 '미정' 계약 정합성 수정 (오프라인만)
작성일: 2026-11-11 KST

## 배경
- 현재 보고서: `reports/VIDEO_MISSION_01_APPROVED_REVIEW_FAILURE_SUCCESSOR_RESULT_20261111.md`.
- 실제 관리자 선정: 롤토체스 및 모바일 퍼즐류 / 영상 25초, 실제 YouTube 관측 근거 3개 ID. 이는 모델 선정이며 Shorts 여부와 인기·권리는 검증되지 않았다.
- 세 번째 실제 후속 업무 `qualityprovider-4cbe762cbf554e40af5e7d990ceaf46b`는 대본 생성 응답 HTTP 200 이후 `script_audience_mismatch`로 stopped. 이전 두 stopped 업무 및 원장 보존.
- 총 Gemini 6/10, YouTube search 2/4, videos 2/4 소모. 기존 실패 기록·서명·active_operation 보존.
- 코드의 `companies/video/script_quality.py` `inspect_script`는 `value['target_audience'] == audience`를 엄격하게 요구한다. 게임 미션 원본 입력의 `target_segment`는 **'미정'**. `video_mission_one.py`의 게임 미션 프롬프트는 동시에 'exact target_segment'를 요구하지만 다른 분기에는 'if 미정, describe the audience inference in planning'이라고 되어 있다. 이 불일치가 실전 중단과 관련 있다. **실제 두 번째 모델 응답 원문은 보존되지 않았으므로 출력한 대상값을 추정하지 말 것**.

## 이 작업에 대한 허용 범위
**제품 코드 최소 수정, 관련 오프라인 테스트, GitHub 보고서 저장만 승인. 실제 Gemini/YouTube API 요청 0회, 실제 stopped 업무 재실행 0회, 새로운 실제 successor 생성·서명 0회.**

1. `AGENTS.md`, 본문 보고서와 `companies/video/script_quality.py`, `companies/video/video_mission_one.py`의 실제 스크립트 품질 검사·역할 프롬프트·최종 컷룸 인수 경로를 중심으로 확인. 현재 입력이 '미정'일 때의 의미(사용자가 시청자 조건을 지정하지 않음)와, 지정한 경우 정확히 일치해야 하는 의미를 명확히 구분한다.
2. **'미정'을 실존하는 시청자 타깃이나 문자 그대로의 대상 이름으로 처리하지 말 것.** 사용자 입력이 미정이라면 AI가 게임·주제·표본에 근거해 합리적인 대상 설명을 제안할 수 있게 하되, 이를 사용자의 실제 사전 확정 입력으로 위장하지 않는다. 선정 근거/추론 여부가 텍스트 산출물에 남도록 기존 필드·unknowns·계획 또는 프롬프트를 적절히 활용한다. 실제로 지정된 구체적 audience 값이 있으면 `inspect_script`의 엄격한 일치 검증을 **그대로 유지**한다. 의미 없는 문자열 대체, 대본의 audience 임의 재작성, '미정'을 특정 시청자로 강제 저장, 전역 검증 해제는 금지.
3. 최소 범위 변경을 택한다: 미션 입력·프롬프트·대본 검사 사이의 정합성을 함께 맞추고, 재사용되는 `inspect_script` 공통 검사에 영향이 있다면 해당 조건부만 제한적으로 수정한다. 선정 게임·25초/YouTube 근거와 영상 계약의 topic, duration, provenance, narration beats, captions, 권리/팩트 불확실성 및 기존 다른 모든 검증은 유지한다.
4. 실제 응답 원문 저장 부재를 인정하되, 다음 유사 실패가 났을 때 민감정보 없이 대상 미지정 여부, 실패 검사 필드 및 stage/category를 기록해 구체적 원인 추적이 가능하도록 검토한다. 응답 원문/키/개인 데이터 저장이나 실패를 성공으로 바꿔치기하는 진단 완화는 금지한다.
5. **명시적 합성 오프라인 fixture**로 (a) 미정 타깃에서 AI의 추론 대상 서술이 허용되며 provenance/unknowns 구분이 유지되는 성공 흐름, (b) 사용자에게서 실제 타깃이 확정된 경우 불일치 거부, (c) 대본 비관련 필드·선정 주제·길이·근거 변조 거부, (d) 실패 시 중단/재시도 금지, (e) 임시 컷룸 대표 승인 대기 종단 인수를 확인한다. 실제 업무 데이터를 fixture로 덮지 않는다. 관련 테스트만 한 번 수행한다.
6. 실제 성공 여부는 **검증 전**이므로 과장하지 않는다. 두 이전 실패 업무 및 새 stopped 업무의 상태·서명·사용량·attempt/active_operation·컷룸 원장 관련 파일을 읽기 전용으로 보존한다. 소모 Gemini 6/10, YouTube 각 2/4 유지. 추가 실 API/후속 업무는 사용자 새 승인 전 금지.
7. **성공·실패·중단 모두** `reports/VIDEO_MISSION_01_UNSPECIFIED_AUDIENCE_CONTRACT_FIX_RESULT_20261111.md` 작성 후 GitHub에 안전하게 commit/push. 변경 코드, 근거, 표적 테스트 개수·실제 결과, 호출 0회·원장 보존, 실제 응답 원문 부재, 다음 한 단계를 간결히 기록하고 중단.

## 금지
`git clean`, `git reset --hard`, 강제 push, 기존 원장/사용자 정보/키/미디어/백업·미추적 파일 삭제·수정, 비용 발생 API, 자동 retry/fallback, 임의 시청자/게임명/조회수 주입. KST 고정.
