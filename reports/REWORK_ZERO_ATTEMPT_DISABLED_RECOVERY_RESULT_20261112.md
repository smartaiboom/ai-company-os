# Gemini 비활성화·전송0 재작업 한정 복구

2026-11-12 KST, 최신 main `79bdfb1`·AGENTS.md·지정 지침 확인. **실제 데이터/환경을 변경하지 않고 한정 복구와 사전 안내를 구현했다. 실제 API0회.**

- 실제 확인: job `qualityprovider-3cb52d1ab205460897e9f03fea21ca71`, 컷룸 plan_revision, UI 재작업 stopped/gemini_execution_disabled이나 provider job은 ready/phase=plan. real_ai.attempts0, sessions0, active_operation 없음, providers/run_started_at/next_request_at/plan/assignments/artifacts/final 없음. 이벤트는 operating_scope_approved1건뿐이다. 별도 일반 attempts 기록도 없다. core/autonomous_free.py의 real_ai.attempts가 예약을 전송 전에 저장하는 유일한 provider 전송 원장이고, 환경 검사는 예약·세션 생성 이전에 실행됨을 확인했다. 원장 초기화는 필요하지 않다.
- 실제 동의서 28841B의 HMAC·원 피드백/계획 해시·계정/범위·유효시간 및 현재 키 바인딩을 기존 grant 경로로 읽기 검증했다. 현재 recovery.eligible=true. 환경은 enable/model/endpoint 미설정, 키는 존재(값 비공개). 현재는 실행 준비 불가이므로 재개 버튼을 숨긴다. 실제 원장/동의·lock/컷룸4개 SHA-256 전후 동일, 새 job/grant/승인·실행0건.
- 변경: representative_rework.py는 disabled 오류+엄격한 초기 상태+서명/키 유효성을 모두 요구한다. stopped/attempt0만으로 허용하지 않으며 세션/예약/불명·실제 시도·다른 오류/가짜 모드·서명/키/만료 문제를 거부한다. ReworkCompany.run의 no-restart 가드는 유지. studio_server.py는 일반 시작도 사전에 설정 확인하며 별도 rework-recover 액션을 프로젝트 잠금 아래 처리한다. 원 provider job은 되돌리지 않고 현재 승인 범위·원 job hash·이전 중단 사유를 새 recovery_events에 추가한 후 명시적1회 실행만 허용한다. 기존 error 기록은 보존, 동시/반복 클릭은 차단한다.
- UI(studio.js): 'Gemini 실행 설정 확인 필요'와 누락 설정/서버 재시작 안내, 검증과 설정이 모두 준비됐을 때만 **설정 확인 후 AI 재작업 재개** 표시. 만료 동의는 새 동의 검토가 필요하다고 안내하며 자동 재발급/재동의는 하지 않는다. 재개는 사용자 클릭 후에만 실행한다.
- 표적 통합 테스트1개 통과(8.194초): `tests.test_video_mission_one.MissionOneTests.test_disabled_zero_send_recovery_requires_explicit_click`. 비활성화 전송0·provider 원장 불변→legacy UI stopped→설정 준비 시 명시적 재개→모의 관리자/직원→동일 컷룸 v2 인수, 중복 송신 차단, reserved/uncertain/attempt/session·다른 오류·서명/키/만료 거부 및 기존28841B 동의 보존을 확인했다. 최초 fixture 키 길이 오류만 수정 후 동일 표적 재실행. DNS/socket 차단 합성 응답이며 실전 재작업은 미실행. JS 문법/Node UI 버튼 조건·git diff --check 통과, 전체 suite 미실행.

실제 Gemini 누적21·YouTube search2/videos2 불변. 기존 승인·시도·과거 영상/음성·data/backups/artifacts/.env·미추적 파일을 삭제/초기화하지 않았다. 시스템이 환경변수를 설정하거나 서버를 재시작하지 않았다.

사용자 다음 순서: 실행 중인 서버를 종료한 뒤 **기존 키가 등록된 같은 서버 셸**에서 다음을 설정하고 재시작한다(키를 출력/재입력하지 않음).

```bash
export GEMINI35_AUTONOMOUS_FREE_ENABLED=1
export GEMINI35_MODEL=gemini-3.5-flash-lite
export GEMINI35_ENDPOINT=https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent
PYTHONPATH=core:companies/video python -B -m studio_server --root data/video_representative_workflow/studio
```

컷룸을 새로고침해 준비 상태/기존 동의를 확인하고 **설정 확인 후 AI 재작업 재개**를 한 번만 누른다. 서버가 별도 네트워크 권한을 요구하면 정식 경로를 따른다. 동의가 그 사이 만료되거나 다른 검증에 실패하면 재개하지 말고 새 동의 범위를 검토해야 한다. 무료 quota/청구는 여전히 unknown/unverified. 수정/테스트/이 보고서 main commit/push·원격 확인 후 중단한다.
