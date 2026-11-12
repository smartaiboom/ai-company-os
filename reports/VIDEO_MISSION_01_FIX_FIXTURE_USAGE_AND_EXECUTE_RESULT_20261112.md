# 미션01 — 실제 자막 수정·스토리보드 수락, 컷룸 인수 오류

2026-11-12 KST, 최신 main `0f60c43`·AGENTS.md·승인 지침 확인. **실제 writer 자막 수정→manager accept→editor storyboard→manager accept 모두 HTTP200/서버 validated. 이후 로컬 컷룸 인수에서 mission_scope_mismatch로 종료하여 대표 승인 대기는 미도달.** run1회 후 재실행/추가 호출 없이 중단했다.

- 변경: 기존 `/tmp/caption_fixture_resume_unvalidated.patch`를 재사용, 합성 Gemini writer 응답에 정상 fixture와 같은 usageMetadata(20/30/50)만 보완. 실제 사용량 검증은 유지했다. 소스2개(video_mission_one.py/representative_workflow.py)는 기존 공통 signed continuation에서 최신 대본·review2·서버 자막 결함을 인계하고, 과거 수정1회+신규 승인1회를 숨김없이 기록한다. 별도 CLI/일반 예산 기능 없음.
- 표적 테스트1개 **통과(5.964초)**: `tests.test_video_mission_one.MissionOneTests.test_caption_revision_new_signed_budget_and_cutroom`. DNS/socket 차단 합성9 stopped+paused+known defects anchor, 대본2/review2/beat1폭39, 원본·서명/한도·중복/변조·키 가드, caption revision→manager→editor→manager→같은 임시 컷룸 awaiting_plan_approval 확인. 실제 성공과 구분한다. 전체 suite 미실행, git diff --check 통과.
- 신규 job `qualityprovider-57981d7b32e14a6cbed733eb1f316f61`, proposal `/tmp/caption_usage_proposal.json`, review SHA `e1396b2c1d62d69f135abe64852c7718c6101daa784d1400d44f9d57e1843830`, grant `62e7c67884264b059ec00cbfc54510c3`. 신규 reference에 historical_revisions=1/new_signed_revisions=1, engine cumulative limit2 및 사전 예약 revisions2를 명시해 추가 수정은 허용하지 않는다. 구 grant/원 revisions는 불변.
- 원 writer v2 SHA `31c453ca16749713dd5e21af23bd1084a21840c88bee57f08f0ea198cd64649a`, manager review SHA `ef16051251dd8d395054499fc78d4e67eb215b0c5f02732dab53571d098519d3` 재검증/인계. provider 기존37개 파일 SHA-256 전후 동일. 과거 실패/불명/503·서명·대본 v1/v2·검토 및 이전 제작/음성 개선 이력 보존. 기존 사용자 data/backups/artifacts/.env·미디어·키·미추적 파일 삭제/초기화 없음.

| 실제 Gemini 단계 | HTTP / 서버 결과 | prompt/completion/total 토큰 |
|---|---|---|
| writer 자막 수정 | 200 / validated | 13338/987/14325 |
| manager writer | 200 / accept, validated | 13234/698/13932 |
| editor storyboard | 200 / validated | 4598/582/5180 |
| manager editor | 200 / accept, validated | 5991/825/6816 |

Gemini 신규4회, 누적 **17+4=21회**(과거 불명 포함), 신규 토큰37161/3092/40253. YouTube 신규0/search2/videos2. 정식 require_escalated 환경에서만 실제 run1회. 무료 Google gen-lang-client-0938732315/gemini-3.5-flash-lite·기존 키/endpoint/Google 개선·인적 검토 데이터 정책 유지. max_calls=None, quota unknown/billing independent verification unverified. paid/fallback/자동 retry0회.

읽기 확인: beat index1 자막은 **2줄, 각16/20폭**, 전체 대본 deterministic defects=[]; transcript 원 v2와 동일. writer versions3/reviews3·editor versions1/reviews1, 모두 accepted_by_ai_manager. 연구10건·관리자 원 선정25초/evidence 재사용. 실제 산출물은 신규 로컬 원장에 보존하며 모델의 주제·성과 주장이나 미확인 소스 권리를 실증된 성과로 승격하지 않는다.

job은 needs_user_review, final.source=accepted_review_handoff/provider=system. 별도 AI 최종 평가 없이 로컬 묶음 완료(final_evaluation=not_performed_local_handoff 정책). 그러나 CLI의 후속 report_plan 인수에서 **mission_scope_mismatch** 발생, 실제 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`는 **research_planning**으로 확인됐다. 승인 대기 카드 인수가 성공했다고 표시하지 않는다. HTTP/모델 실패가 아닌 로컬 인수 검증 오류이며 아직 상세 조건은 미확정이다. 대표 승인·TTS/렌더/MP4/게시0회.

**다음 행동 하나:** 추가 AI 호출 없이 수락된 산출물의 로컬 컷룸 인수에서 mission_scope_mismatch 원인을 수정·검증한다. 이번에는 실패 후 재실행하지 않고 소스2개·표적 테스트1개·이 보고서만 main commit/push·원격 확인 후 중단한다.
