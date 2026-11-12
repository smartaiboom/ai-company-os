# 미션01 — 자막 폭 지시 최소 수정 결과

2026-11-12 KST. 최신 main `cbf3594`·AGENTS.md·지정 지시서·직전 결과를 확인했다. **실제 API 호출 없이 폭 계산 기준 전달만 수정, 표적 테스트2개 통과.** 과거 영상 전체 제작/음성 개선 이력과 이번 주제·대본 품질 고도화를 구분한다.

- 변경: `companies/video/script_quality.py`에 짧은 공통 caption_width 지시를 추가해 기존 SCRIPT_INSTRUCTIONS→실제 systemInstruction 경로로 생성·수정·관리자 검토에 전달한다. Unicode east_asian_width W/F=2, 나머지=1(ASCII 공백·문장부호 포함), 최대2줄·줄당28폭, 줄별 합산·축약/실제 줄바꿈·JSON newline escape를 명시했다. 예: 가나다 ABC=10폭, 한글14자=28폭/15자=30폭, ASCII28자=28폭. 슬래시/자동 화면 줄바꿈은 줄 분리가 아님을 알린다. 관리자에게 잔존 major 결함 accept 금지와 caption_width/구체 수정 피드백도 지시한다.
- 서버 units/inspect_script의 기준, known_script_defects 차단은 변경하지 않았다. native schema/invariants 및 역사 writer v1/v2 hash도 변경하지 않았다. 새 표현은 systemInstruction 지시 보강이며 native schema만으로 폭을 강제했다고 주장하지 않는다. 실제 모델 준수 여부는 미검증이다.
- 표적 검증: `PYTHONPATH=core:companies/video python -B -m unittest tests.test_script_quality.ScriptQualityTests.test_caption_width_boundaries_and_manager_accept_guard tests.test_video_mission_one.MissionOneTests.test_partial_writer_revision_continuation_preserves_feedback_and_hands_off` **2개 통과, 4.991초**. 한글/ASCII 경계, 올바른 두 줄, 한 줄 초과·3줄·슬래시 미분리, 잔존 결함 manager accept 차단/정상 자막 통과, 기존 대본·피드백을 전달하는 실제 writer 수정 wire의 systemInstruction 포함을 확인했다. 외부 DNS/socket 차단 합성 fixture이며 실전 성공이 아니다. `git diff --check` 통과. 전체 회귀는 하지 않았다.
- 보존: provider 원장37개+컷룸 JSON1개 **38개 SHA-256 전후 동일**. 초도/수정 대본·관리자 검토·실패/paused/stopped·모든 grant/attempt/서명 불변. Gemini 신규0/누적17, YouTube 신규0/search2/videos2. 실제 새 successor/consent/grant0건, 기존 업무 재실행0회. data/backups/artifacts/.env·키·미추적/음성/영상/미디어 삭제·초기화 없음.
- 이어받기 결론: 현재 stopped known_script_defects 업무는 기존 공통 continuation 적격이 아니며 signed 수정1회 한도도 소진했다. 이 수정만으로 안전 재개 가능해진 것이 아니고 기존 grant/한도를 우회하지 않는다. 컷룸 research_planning, 스토리보드·대표 승인 대기 미완료 상태 유지.

**다음 실제 제작 단계 하나:** 별도 승인에서 최신 대본/검토 보존 및 수정1건의 신규 서명 범위를 명시하고, 해당 stopped 상태를 안전하게 이어받는 최소 경로를 마련한 뒤 실제 자막 수정을 진행한다. 이번에는 실행하지 않는다. 소스1개·기존 테스트 파일2개·이 보고서만 GitHub main commit/push·원격 확인 후 중단한다.
