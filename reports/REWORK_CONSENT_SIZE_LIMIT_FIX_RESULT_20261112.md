# 재작업 동의서 크기 제한 수정 결과

2026-11-12 KST, 최신 main `573fa41`·AGENTS.md·지정 지침 확인. **16KiB 크기 오류만 수정했다.**

- `core/autonomous_live.py`: 기존 16384 미만 조건을 클래스 속성 `max_consent_bytes=16384`로 이동. `representative_rework.py`의 ReworkStore에서만 65536 미만으로 재정의했다. 일반 LiveStore/MissionOneStore는 기존16KiB 유지. HMAC·바인딩·범위·시간/상태 검사는 변경하지 않았다.
- 표적 테스트1개 통과(7.820초): `tests.test_video_mission_one.MissionOneTests.test_rework_consent_size_limit_and_approved_start`. 임시 승인 계약을 유효한 JSON 공백으로 28841B까지 늘려 서명 원문 유지/검증 성공, 65535B 허용·65536B 차단, 서명/내용 변조 차단, 일반 저장소의 큰 파일 거부, UI action의 approved→running 전이 및 오프라인 종단 흐름 확인. DNS/socket 차단 합성 응답만 사용. `git diff --check` 통과, 전체 suite 미실행.
- 실제 읽기 확인: job `qualityprovider-3cb52d1ab205460897e9f03fea21ca71`, 동의서 **28841B**, 컷룸 plan_revision, 재작업 상태 **approved**, attempts0/sessions0. 관련 원장/동의/lock·컷룸4개 파일 SHA 전후 동일. 실제 동의서의 서명키를 읽거나 재승인하지 않았으므로 현재 HMAC/만료까지 재검증한 것은 아니다. 코드상 기존 동의서는 새 크기 상한을 만족하고, 다음 정상 시작에서 나머지 기존 검증을 그대로 거친다.
- 실제 API 호출0회, 프로덕션 실행 시도0회, 신규 승인/grant/job0건. 기존 승인·서명키·원장·피드백·영상/음성·data/backups/artifacts/.env·미추적 파일 변경/삭제 없음. 무료 quota/청구 독립 미확인 상태 유지.

**다음 동작:** 서버 재시작 후 동일 컷룸의 기존 **AI 재작업 시작**을 한 번만 누른다. 이번 크기 수정 때문에 새 동의를 받을 필요는 없다. 실패하면 반복 클릭하지 않는다. 수정/표적 테스트/이 보고서 main commit/push·원격 확인 후 중단한다.
