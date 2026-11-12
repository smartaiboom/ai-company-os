# 대표 수정 요청 → AI 재작업 구현 결과

2026-11-12 KST, main `517fdc0`·AGENTS.md·지정 지침 기준. **세 기능 구현 및 오프라인 종단 검증 완료. 실제 AI 재작성은 아직 실행하지 않았다.** 실제 컷룸은 저장된 피드백 그대로 plan_revision/동의 준비 상태다.

- 구현: 새 `representative_rework.py`가 기존 MissionOne/VideoProviderQualityCompany 엔진의 native writer·품질 검사·서명/attempt 원장을 재사용한다. 원 목표·대표 피드백·이전 대본/스토리보드·공개 관측을 새 서명 범위에 묶고 관리자에게 주제/길이 재판단 및 피드백 반영 사유를 요구한다. 직원 대본→관리자→스토리보드→관리자를 실행하며 정상 수정은 새 업무의 서명된1회 한도 내에서만 가능하다. 웹/조사 API 도구는 제공하지 않아 관측이 부족하면 중단해야 한다.
- 의미 관문: goal_fit/feedback_applied/subject_story/concrete_hook/claims_supported를 명시 전달하고 accept에는 모두 충족 및 산출물 원문 인용을 요구한다. 기존 형식 검사와 함께 명백한 제작법 설명/골든타임 단정 패턴도 차단한다. 특정 게임/정답을 고정하지 않는다. 모델 의미 판단과 제한된 패턴 검사는 완전한 사실·흥미 검증이 아니므로 최종 대표 검토가 필요하다.
- 컷룸 인수: 검증 수락된 결과만 같은 프로젝트의 새 plan 버전으로 연결한다. 원 v1/대표 결정은 보존하고 새 버전에 재기획 사유·대표 피드백·대본/편집 결과·의미 검토를 기록한다. accepted_review_handoff이며 별도 최종 AI 평가는 하지 않는다. 기존 production/60초 budget 경로를 사용하지 않는다.
- 서버/UI: studio_server.py, studio/studio.js에 동의 준비→새 전송 동의→명시적 실행·상태 새로고침을 연결했다. 장시간 호출은 백그라운드 실행하며 중복 시작/실패 후 재시작/불명 상태 자동 재개를 차단한다. 이전/새 대본과 편집 직원 스토리보드·재기획/검토를 비교할 수 있다. 키 값은 UI로 전달하지 않는다. 고정 무료 프로젝트/모델, Google 개선 활용·인적 검토, quota unknown/billing unverified 및 전송 입력을 표시한다.

핵심 테스트 **1개 통과(7.309초)**: `tests.test_video_mission_one.MissionOneTests.test_representative_feedback_rework_end_to_end_offline`. 임시 원 기획 v1→대표 수정→동의 대기 전송0→서버 동의/비동기 실행→모의 manager 재기획→writer/editor 검토→같은 컷룸 v2 승인 대기, v1/원장 보존, 서명 범위 변조/동의 없는 시작/중복 클릭/재호출 거부, 명백한 목표 이탈 수락 차단, 다음 별도 수정의503 후1회에서 중단을 검증했다. 연결 문제 수정 후 같은 표적만 재실행했으며 전체 suite는 실행하지 않았다. DNS/socket 차단 fixture이며 실제 모델 성과가 아니다. node --check·git diff --check 통과. Node VM에서 실제 plan_revision 데이터의 동의 준비 버튼과 pending/approved/running/stopped/completed UI 문구 렌더 확인(브라우저 시각 검사는 미수행).

**실제 외부 API0회, 실제 신규 job/consent/grant0건.** Gemini 누적21·YouTube search2/videos2 불변. 기존 provider40개 파일은 이전 보존 SHA와 동일, 실제 컷룸 포함41개 파일은 readback 전후 동일. data/backups/artifacts/.env·기존 완성 영상/음성·미추적 파일 삭제/초기화 없음. 이번 작업은 현재 피드백 기반 기능 구현이며 과거 영상 전체 제작/음성 개선 이력을 부정하지 않는다. 새 조사·모델 비교·렌더/대표 승인·게시 없음.

다음 사용자 절차: 서버가 고정 GEMINI35_MODEL/GEMINI35_ENDPOINT·기존 GEMINI_API_KEY 및 기존 무료 실행 환경을 사용하도록 한 뒤, 동일 컷룸에서 **AI 재작업 동의 준비 → 새 외부 전송 동의 → AI 재작업 시작**. 기존 피드백 재입력은 필요 없다. 실행 실패/서버 종료로 상태 불명인 경우 자동 재실행하지 않으며 별도 검토가 필요하다. 실제 모델이 목표에 맞는 새 대본을 만드는지는 새 동의 후 확인할 미완료 항목이다. 소스/핵심 테스트 및 이 보고서 main commit/push·원격 확인 후 중단한다.
