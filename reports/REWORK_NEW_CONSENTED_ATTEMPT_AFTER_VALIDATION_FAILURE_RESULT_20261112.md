# 실패 기획 이후 새 동의 기반 재작업 연결

2026-11-12 KST, 최신 main `1784014`·AGENTS.md·지정 지침 기준. **같은 컷룸의 새 준비→새 동의→명시적 실행→대본 v2 승인 대기 연결을 구현·오프라인 검증했다. 실제 새 대본은 미생성, API0회.**

- representative_rework.py: 이전 기획 검증 실패가 stopped/plan이며 시도1건 HTTP200/JSON parsed로 수신 완료된 경우만 허용. 완료 시도의 보존 active_operation 참조는 허용하지만 불명/예약/추가 시도·다른 오류는 거부한다. 기존 HMAC·원 목표/피드백·계정/키/모델·이전 기획 연결을 검증한다. 역사 동의 만료는 과거 서명 증명과 구분하며 새 전송 권한으로 재사용하지 않는다. 동일 강화 계약으로 실패한 업무는 반복 새 준비가 불가하다.
- 새 업무는 이전 실패 job/state/grant hash와 강화 PLAN_RULES 계약을 새 proposal에 묶고 빈 동의/시도/세션부터 시작한다. 이전 UI 상태는 rework_history에 보존하며 과거 파일은 수정하지 않는다. 프로젝트 잠금·previous_job 확인으로 동시/중복 클릭 차단, 이미 연결된 역사 업무만 orphan 충돌에서 제외한다. 미연결 orphan은 계속 차단한다.
- studio_server.py/studio.js: **수정 대본 다시 생성 준비** 버튼과 전용 준비 액션을 기존 consent/run 흐름에 연결했다. 이전/현재 job을 구분하고 새 무료 계정 확인·Google 개선/인적 검토 정책·전송 범위를 검토하게 한다. 새 동의 전 실행 불가, 기존 background/실패 후 no-retry 가드 유지. 일반 영상/음성/예산 기능 변경 없음.
- 종단 테스트 **1개 통과(7.842초)**: `tests.test_video_mission_one.MissionOneTests.test_new_consented_rework_after_failed_plan_to_v2_offline`. 합성 old stopped/invalid_dependencies/attempt1→새 준비→다른 job/grant·옛 동의 거부·중복 준비 차단→manager/writer/editor/의미 검토→같은 임시 컷룸 새 plan v2 승인 대기. 원 실패 job/동의/lock·원 기획 v1 불변 및 이후503 중단/중복 실행 차단 확인. DNS/socket 차단 fixture이며 실제 성과가 아니다. node --check·UI Node 렌더·git diff --check 통과, 전체 suite 미실행.

실제 컷룸은 plan_revision, 실제 job `qualityprovider-3cb52d1ab205460897e9f03fea21ca71`은 stopped 그대로. 읽기 조회에서 새 준비 가능/옛 run·recover 버튼 비노출 확인. 원장·동의/lock·컷룸4개 SHA 동일. 실제 신규 job/proposal/consent/grant0건, Gemini 추가0/누적22(과거 불명 포함), YouTube 추가0/search2/videos2. data/backups/artifacts/.env·키·과거 제작/음성·미추적 파일 보존. quota/청구 unknown/unverified 유지.

**대표 다음 순서:** 서버 재시작·컷룸 새로고침 → **수정 대본 다시 생성 준비 → 새 외부 전송 동의 → AI 재작업 시작**. 같은 피드백을 다시 입력할 필요 없다. 이후 새 대본/스토리보드는 대표가 이전 버전과 비교하고 승인/반려한다. 실제 모델 품질/공급자 성공은 아직 미검증이며, 실패 시 자동 재시도/새 준비 반복은 허용하지 않는다. 소스3개·종단 테스트1개·이 보고서 main commit/push/readback 후 종료한다.
