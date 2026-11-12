# 미션 01 — 테스트 fixture 수정 후 자막 실전 수정 이어가기
2026-11-12 KST

## 승인 및 목표
대표는 기존 실제 대본의 **두 번째 장면 자막(beat index 1, 한 줄 39폭)**을 폭 28 이하로 수정하고 AI 관리자 재검토→편집 스토리보드→관리자 검토→동일 컷룸 대표 승인 대기까지 실행하도록 이미 승인했다. 최근 오프라인 테스트가 실패해 실제 API 호출이 전혀 없었으며, 대표가 다시 **"진행하자"**라고 지시했다. 별도 무관 개발·테스트·예산 기능 추가 없이 이 승인 범위 안에서 실제 제작을 완료한다. 기존 영상 생성 전체 사이클 및 음성 개선 경험은 보존하고 이번 업무는 AI의 주제/대본 품질 향상 미션으로 취급한다.

## 시작 상태
- `AGENTS.md`, `reports/VIDEO_MISSION_01_CAPTION_REVISION_REAL_COMPLETION_RESULT_20261112.md`, `reports/VIDEO_MISSION_01_CAPTION_WIDTH_MINIMAL_CONTRACT_FIX_RESULT_20261112.md`, 이전 승인서 `docs/VIDEO_MISSION_01_APPROVED_CAPTION_REVISION_TO_CUTROOM_20261112.md`만 우선 읽기.
- `qualityprovider-b96e442fd4104d8cb9da3179c5ce6bc9` stopped/`known_script_defects`에 원 writer versions2/reviews2/revisions1, editor pending. 최신 대본 SHA `31c453ca16749713dd5e21af23bd1084a21840c88bee57f08f0ea198cd64649a`, 최신 manager review SHA `ef16051251dd8d395054499fc78d4e67eb215b0c5f02732dab53571d098519d3`. 최신 리뷰 모델의 accept는 서버 수락이 아님. 남은 실제 결함은 beat index1 caption_width: 한 줄39폭, 허용 각 줄28폭/최대2줄. 과거 원본 수정 금지.
- 컷룸 `company-aba553f29cfb454c8c05bad4abb49969` 현재 `research_planning`, 원 연구10건/AI 관리자 선정 주제·25초/evidence 재사용. 누적 Gemini17회, YouTube search2/videos2.
- 고정 무료 Google `gen-lang-client-0938732315` / `gemini-3.5-flash-lite`, 원 endpoint/키/무료 데이터 정책, 새로운 Gemini 임의 호출 상한 없음(`max_calls=None`, 무한 재호출 허가 아님), YouTube 신규0. 청구/공급자 quota 독립 미확인: unknown/unverified. 유료 전환/모델·계정·키/fallback·자동 retry 금지. 실제 요청은 기존에 DNS 성공이 확인된 **Codex 정식 권한 확장 실행 경로**를 사용하되 해당 도구가 별도 허가를 요청하면 정식 절차를 따른다.

## Codex 최소 실행 순서
1. 이전 실패 원인을 **표적 fixture에서 먼저** 수정한다. 직전 시도는 합성 anchor를 생성할 때 관리자 accept의 **서버 `known_script_defects` 차단**을 재현하지 못하고 `revision_limit`에 먼저 걸렸다. 합성 writer revisions1의 제한·review 피드백/actual defect를 올바른 순서와 상태로 재현한다. 단순히 revision_limit 방어를 삭제하거나 과거 signed revision 한도를 늘려 테스트를 통과시키지 말 것. 이전 시도에서 남긴 `/tmp/caption_revision_unvalidated.patch`와 `/tmp/caption_revision_test.log`가 동일 작업 환경에 존재하고 유효하면 필요한 부분만 참고; 없거나 불일치하면 없다고 보고 직접 최소 수정. 불필요한 재탐색 금지.
2. 합성 anchor가 **실전과 동일하게** writer versions2/reviews2/revisions1 + manager accept 주장/서버 known_script_defects 차단 + beat index1 폭39를 가지도록 한다. 여기까지 통과하면 원 approved scope 내 **새 독립 signed continuation 1건**의 최소 연결 코드를 작성/검증한다. 원 `b96e...` 직접 run 금지; 구 grant/원 history/원 revisions/attempt 수정 금지. 원 두 대본·두 review SHA 및 마지막 상태/서명/계정·키/무료 모델·컷룸/원 관리자 선정·자료 receipt 확인; 최신 v2와 최신 관리자 결함 피드백을 이어받고 **새로운 수정 1회 승인 범위**를 새 proposal/review SHA/독립 grant에 명시. 과거1회를 지운 것처럼 보이지 않도록 lineage 보존. 이 수정 경로가 엔진 내부 한도를 충돌 없이 적용하도록 새 업무에만 승인된 한도 설정. 중복 successor 차단. 기존 API 요청 replay 금지.
3. **관련 표적 테스트 단 하나만** 실행: 실제 anchor 생성, 새 서명/한도·중복/변조 거부·원본 불변, 기존 대본2·review2 인계→새 writer 수정1회→manager accept→editor→manager accept→임시 같은 컷룸 `awaiting_plan_approval`. 합성 모델 및 DNS 차단. 테스트가 실패하면 **원인에 직접 관련된 수정 후 같은 표적 테스트를 한 번 더 실행할 수 있음**; 계속 실패하면 외부 요청0회로 간결하게 보고 중단. 이미 통과한 전체 회귀·장시간 진단 반복 금지.
4. 오프라인 성공 시 **실제 신규 job 1건** 생성→prepare→새 review SHA/운영 grant approve→**run 정확히 1회**. Gemini 첫 호출은 **새 대본 생성이 아닌 실제 최신 대본 v2의 두 번째 장면 자막 수정**이 목적. AI가 한국어 2줄 이하, 각 줄 화면폭28 이하(Unicode east_asian_width W/F=2)로 수정하고 자막만 억지로 바꾸느라 기존 선정 주제/25초/시청자 제안 및 근거/내레이션/transcript/사실·권리 불확실성/모델 출처를 훼손하지 않도록 한다. 모델 응답 자동 조작/서버 검사 우회/manager 잘못된 accept 수락 금지.
5. 실제 관리자 재검토가 서버 조건을 통과해 accept되면 **실제 editor storyboard 및 AI 관리자 editor review**까지 정상 실행. 두 직원의 검증된 수락 후에만 기존 `accepted_review_handoff`/ `final_evaluation=not_performed_local_handoff`로 같은 컷룸 `awaiting_plan_approval`에서 기획·대본·스토리보드 카드 읽기 확인. 사람 대표 승인·TTS·MP4·음성/기존 미디어 수정·렌더·게시 금지.
6. HTTP 503/429/DNS·quota·billing/형식·품질/타임아웃·전송 불명 실패가 나오면 그 즉시 보존·중단. 자동 retry/새 successor 재생성·유료 fallback 금지. 원본 파일·서명·attempt 보존과 KST 시간 처리. GitHub에 짧은 결과 보고서 `reports/VIDEO_MISSION_01_CAPTION_FIXTURE_AND_REAL_RESUME_RESULT_20261112.md`를 **성공·실패 어느 경우든** commit/push하고 원격 확인 후 중단. 내용: fixture 수정/표적 테스트, 수정 파일, 실제 새 job/grant/검토 SHA, 실제 Gemini 단계별 성공·실패/누적17+new/YouTube0, 원본 보존, 서버 caption_width 해소 여부, 컷룸 phase 및 남은 작업 단 하나. 키·원시 응답·개인정보·실제 대본 전문은 보고서에 복제 금지.

Codex 주간 사용량 절약. Git clean, reset --hard, force push, 이전 data/backups/artifacts/.env·키·사용자 영상·음성·미추적 파일 삭제/초기화 금지.
