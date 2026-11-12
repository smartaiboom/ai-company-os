# 미션 01 — 잔여 자막 결함 수정 후 실제 컷룸 대표 승인 대기까지
2026-11-12 KST

## 사용자의 명시적 승인 / 업무 목표
대표가 최신 자막 폭 계약 수정 결과를 보고 "응 진행하자"라고 승인했다. **기존 실전 대본 v1/v2와 AI 관리자 검토/피드백을 그대로 보존**하면서, 새 독립 후속 업무와 새 제안·서명 아래 **남은 caption_width 문제의 대본 수정 1건 → 관리자 재검토 → 편집 AI 스토리보드 작성 → 관리자 편집 검토 → 동일 컷룸 대표 기획 승인 대기**까지 실제 무료 Gemini로 실행한다.

이것은 영상 생성 경험이 전무한 제품 개발이 아니라, 이미 영상 생성 전체 사이클을 한 차례 완료하고 음성 품질 보완 후 수행 중인 **주제 선정·대본 품질 고도화**다. 대표는 Codex 주간 사용량을 아끼기 위해 **실제 개발/실행 중심, 불필요한 테스트·검증·장문 보고 최소화**를 요구했다.

## 현재 사실과 보존 범위
- 최신 main 및 `AGENTS.md`, `reports/VIDEO_MISSION_01_PARTIAL_WRITER_REVISION_CONTINUATION_RESULT_20261112.md`, `reports/VIDEO_MISSION_01_CAPTION_WIDTH_MINIMAL_CONTRACT_FIX_RESULT_20261112.md` 우선 확인. 무관한 대량 코드 감사 금지.
- 마지막 stopped: `qualityprovider-b96e442fd4104d8cb9da3179c5ce6bc9`, reason=`known_script_defects`; `assignments[writer]`의 실제 대본 `versions2`, 실제 관리자 `reviews2`, 원 `revisions1`, editor pending. writer 수정 HTTP200/validated, 관리자 HTTP200 모델 accept였지만 서버의 major `caption_width` 잔존으로 수락 차단. **관리자 모델의 accept를 실제 서버 acceptance로 승격 금지**. 기존 accepted research10건·선정 주제 25초/evidence 및 대본 v1/v2·reviews·시도/서명 불변.
- 원 writer v1 SHA `7e6c41bb9264b6681410c718f9225ff7bf62e1cf31cdcf8b6cf89038be1e8b8d`, 이전 관리자 revise SHA `e0eff1c2cabb6b2f054c9447eb6ed67a82c9e7e61713b7bd72e42f484b8cfa74`; 최신 버전2와 최신 manager review의 진짜 hash는 원장으로 계산/검증하여 새 consent에 함께 묶는다.
- 원 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`, phase=`research_planning`. Gemini 누적 **17회**(실패/불명 포함), YouTube search2/videos2. 새 YouTube 전송0회. 원 9 stopped + 이후 paused + 최신 stopped 및 모든 원장/키/데이터/음성/기존 완성 영상 보존.
- 최근 수정: `script_quality.py`는 자막 폭 `east_asian_width` W/F=2 나머지1, **최대 2줄, 줄당28폭**, 실제 줄바꿈과 JSON newline escape를 writer systemInstruction/관리자에게 전달한다. 서식 기준/known_script_defects 경고를 완화하지 않는다.
- Gemini: 무료 Google `gen-lang-client-0938732315`, `gemini-3.5-flash-lite`, 기존 고정 endpoint/키, 기존 Google 무료 서비스 데이터 개선·인적 검토 가능 정책 동의만 유지. 실제 quota unknown, billing independent verification unverified. 신규 Gemini에 임의 내부 횟수 상한 없음(`max_calls=None`)은 자동 재시도/호출 남발 허가가 아님. 유료 전환/모델·계정·키 교체/fallback/쿼터 우회 금지. 실제 실행은 DNS 진단에서 성공한 Codex의 **정식 `require_escalated` 네트워크 권한 경로**로 수행; 필요시 권한 정식 승인 절차를 준수하고 우회하지 않음.

## Codex가 이번 한 번의 작업에서 해야 할 일
1. 원 job 및 원 grant/signature/attempt/writer v1,v2/manager reviews/revision 한도/기존 accepted research·선정25초/컷룸 연결을 확인한다. 실제 마지막 major 결함의 beat index/width는 원장과 inspector로 검증하되 원문을 공개 보고서에 복사 금지. 최신 상태를 기준으로 신규 목적 `revise_preserved_writer_v2_caption_width_under_new_signed_revision_grant`의 **신규 독립 continuation 단 한 건**만 만들고 중복 방지. 기존 stopped job 직접 run, 원본 revisions/grant 한도 재작성, 모델 accept를 실제 accept로 기록 금지.
2. `video_mission_one.py`, `representative_workflow.py` 및 필요한 engine 부분만 최소 수정해 **현재 stopped known_script_defects의 정상적으로 검증된 v1/v2와 모든 관리자 피드백을 독립 새 작업에 안전하게 인계**한다. 서명된 과거 revision 1회 소진은 역사로 불변이고, 이번 사용자가 별도로 승인한 **새 작업의 자막 수정 1회**를 새로운 proposal/operating grant에 독립적으로 명시한다. 새 revision budget/guard는 이 새 승인 범위 안에서만 검증하고, 누적 과거 revision을 삭제·숫자 초기화/감사 우회로 숨기지 않는다. v2 최신 대본과 마지막 manager major 결함 검토를 실제 수정 입력에 전달해야 하며, 업무 버전 chain·원본 hash/기존 출처를 명시. 일반 기능/예산 프레임워크/전용 CLI 무분별 추가 금지.
3. 필요한 **표적 오프라인 테스트 단 1묶음**: known_script_defects anchor와 v1/v2·review hash, 과거 grant/attempt/revisions 보존, 중복/계정·키·model/자료 서명 변조 거부, 새 한도1회, 실제 수정 요청에 최신 v2·자막 width 피드백 전달, 수정 후 manager accept→editor→manager accept→같은 임시 컷룸 awaiting_plan_approval. 합성 fixture는 진짜 결과가 아니며 전체 테스트/성능 분석/연속 사전 API 확인 금지. 테스트가 실패하면 외부 호출 없이 간결하게 보고하고 중단.
4. 안전 검증을 통과하면 신규 후속 1개·proposal prepare·원본+수정목적+무료 데이터 조건·새 독립 수정 한도1회 검토 SHA·grant approve를 연결한다. 기수락 연구와 AI 관리자 원 선정/evidence/25초는 그대로, 이전 실전 대본과 피드백을 새 작업에 계보를 유지해 인계하고 manager accept 미완료를 명시한다.
5. **실제 run 딱 한 번**, 정상 연결 권한 환경에서 먼저 **writer caption_width 수정**: 가급적 첫 장면의 자막만 간결하게 재작성하되 대본 품질/주제·시청자·내레이션 타임라인·hook·transcript/close·provenance·미검증 사실·권리 한계도 유지. Unicode 폭 합계를 각 줄 ≤28, 줄 수≤2, 실제 줄바꿈. AI가 원문 없이 대본 전체를 처음부터 생성하지 말고 최신 실전 v2/manager feedback을 인수한다. 새 revision의 모델 출력/서버 계약 통과 → AI 관리자 실제 재검토(모델 accept만으로 서버 known defects 수락 우회 금지). 두 직원의 실전 검토가 받아들여지면 editor storyboard 작성과 manager editor 검토를 진행.
6. 실제 결과가 모두 수락됐을 경우만 **동일 컷룸 `awaiting_plan_approval`**에 기획·대본·스토리보드 카드 인수 및 readback 확인. `accepted_review_handoff`, `final_evaluation=not_performed_local_handoff`; 최종 AI 평가 했다고 위장하지 말 것. 대표의 승인/반려 누르지 말고 TTS/음성·영상 렌더/MP4·게시/업로드·과거 영상 파일 수정 금지.
7. HTTP503/429·DNS·공급자 quota/billing/timeout·미수신·형식/품질 검증 오류 즉시 stopped/paused로 보존하고 **재실행·추가 successor·자동 retry·유료 fallback 금지**. 새 승인 한도 위반/보존 연결 불명 시 외부 호출 금지. 실제 provider 성공/모델 accept와 서버의 최종 acceptance 구분.
8. **성공/실패 모두** `reports/VIDEO_MISSION_01_CAPTION_REVISION_REAL_COMPLETION_RESULT_20261112.md`를 GitHub main에 commit/push하고 원격에서 읽힘 확인 후 중단. 보고는 **짧게**: 변경 파일, 최소 테스트 수, 신규 job/grant/review SHA, 원본 v2/review hash 불변, 실제 실행 단계와 HTTP/신규 Gemini 소모·누적17+new/YouTube0, server major defects 해소 여부, 대본·스토리보드 및 컷룸 `awaiting_plan_approval` 여부, 실패 원인과 다음 한 행동. 키/실제 대본 전체/원시 모델 응답/사용자 개인정보 공개 보고 금지.

KST(UTC+9). `git clean`, `git reset --hard`, force push, 데이터/원장/서명/음성·영상 파일 삭제·초기화 금지.
