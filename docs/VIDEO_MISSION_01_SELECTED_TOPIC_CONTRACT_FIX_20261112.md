# 미션 01 — 관리자 선정 주제와 writer 제목 계약 정합성 최소 수정
작성일: 2026-11-12 KST

## 가장 중요한 목표
실제 Gemini writer가 2026-11-12 **HTTP200/JSON 파싱**을 반환했으나 `mission_selected_topic_mismatch` 때문에 stopped된 원인을 기존 코드 계약에서 교정한다. **실제 대본→스토리보드→대표 컷룸 승인 대기라는 본래 목표가 더 지연되지 않게**, 오프라인에서 작은 수정만 하고 즉시 보고한다. 이번 지시는 외부 실제 API 재호출·새 실전 successor 생성 권한이 없다.

## 실전 기록
- 필독: `AGENTS.md`, `reports/VIDEO_MISSION_01_APPROVED_AUDIENCE_SUCCESSOR_REAL_RUN_RESULT_20261112.md`.
- 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`, 상태 `research_planning`. 총 **6개** stopped 업무, 최신 `qualityprovider-4109f683a75b466ba326a45df3bb7012`. 과거 실제 Gemini **9**, YouTube search **2** / videos **2**.
- 마지막 실패는 writer 출처/provenance·시청자 추론 검사를 통과한 후, `video_mission_one.py`의 `content['topic']['title'] == chosen['selected_topic']`에 실패. 원문 응답은 보존되지 않아 실제 title·의미상 주제 이탈 여부 불명. 성공한 대본 버전은 없음. 오류를 무시하거나 실패 결과를 승인된 대본으로 승격 금지.
- 관리자 실제 선정과 기존 조사 10건/25초/evidence 및 모든 연결 해시·기존 서명·원장·과거 실패는 변경 금지.

## 코드를 확인한 계약 불일치 가능성
- `video_mission_one.py` `_mission_call`은 `context['quality']['manager_selection']`에 고정된 정확한 selected_topic 문자열을 전달하면서, writer가 반환하는 `topic.title`의 완전 일치를 요구한다.
- `_tool_notice`는 간접적으로 selected_topic을 유지하라고만 안내하는 곳이 있다. AI가 '주제'와 '영상용 흥미로운 타이틀'을 혼동할 수 있다.
- **원 주제 선택 권한은 AI 관리자에게 있으므로 선정 주제를 writer가 바꾸면 안 된다.** 해결은 수용 조건을 전부 제거하는 게 아니라, **선정 주제 식별자와 쇼츠용 매력적인 제목(카피)을 분리**하거나 실제 selected_topic을 정확히 복사하도록 구조/프롬프트를 명확히 연결하는 최소 방법을 선택한다.

## 작업
1. 최신 main·상기 보고서·`video_mission_one.py`, `quality_workflow.py`, writer contract 및 관련 테스트만 확인한다. **오류 발생 원문을 보지 못했으므로 '제목만 살짝 달랐다'고 확정 금지**.
2. writer 실제 프롬프트(시스템·context 중 적합한 지점)에 모델이 읽을 수 있는 형태로 **`quality.manager_selection.selected_topic`을 `topic.title`에 문자 그대로 복사**해야 한다는 지시를 명확히 준다. 해당 정확한 동적 값은 승인된 selection/context에서 주입해야 하며 개발자가 게임/제목을 하드코딩하거나 새 선정하지 말 것. 적절한 별도 후킹 문구가 필요하다면 선정 주제와 'viewer-facing hook/title'을 혼동하지 않게 안내한다. 원 selected_topic 변경 금지.
3. `selected_topic` 완전 일치 검사를 무조건 삭제/우회하지 말 것. 의미상 주제가 동일해도 띄어쓰기 정도가 달라지는 사례를 허용할지 신중히 판단하고, 안전하게 고정값 복사 경로를 우선한다. 프로그램이 서버에서 무음으로 결과물을 교체하거나 topic을 덮어쓰기 금지. `topic.title`이 관리자 선정 주제와 다를 경우 AI 관리자 편집 승인 전에 명확한 검증 실패를 남겨야 한다.
4. 이후 실패를 효율적으로 고칠 수 있도록 모델 출력 전문/키/시청자 개인정보 없이 현재 attempt의 `script_validation_diagnostics`에 `mission_selected_topic_mismatch`, 선택 문자열과 대본 제목의 **일치 boolean, 정규화 비교 boolean, 안전한 길이/해시** 등 최소 정보만 담고 실패 유지. 이미 stopped된 6번째 원장은 수정하지 않는다. AI 실제 대본 결과를 생성·수선해서 성공으로 위장 금지.
5. 합성 fixture로 (a) manager selection을 writer 실제 시스템/컨텍스트에 정확히 전달·복사 시 pass, (b) writer가 다른 topic.title을 쓴 경우 여전히 reject, (c) 실제 주제/25초·시청자 미정 추론·provenance·출처·권리 등 기존 검사 유지, (d) 대상/제목 불일치 등진단 원문 미노출, (e) 수락한 합성 대본→manager review→editor→manager review→임시 컷룸 `awaiting_plan_approval`를 한 번의 관련 테스트 묶음으로 검증한다.
6. **실제 Google API 0회**, 실제 새 업무/동의/승인 0건. 현재 실패6건과 원 signed history/원본 data·backups·artifacts·.env·키·미디어·미추적 파일은 불변. 호출/유료 예산 정책과 다른 영상 기능 추가 개발 금지.
7. 성공/실패/중단 모두 `reports/VIDEO_MISSION_01_SELECTED_TOPIC_CONTRACT_FIX_RESULT_20261112.md`를 GitHub commit/push하고 중단. 변경 파일/표적 테스트 수, 실 API0·현재 Gemini9·YouTube2/2, 실제 컷룸 연구 단계 유지, 다음 최소 후속 경로(6번째 실패 후 별도 신규 업무 승인 필요)를 기록한다.

KST, git clean/reset --hard/force push 금지.
