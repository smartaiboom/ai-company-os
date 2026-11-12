# 미션 01 — 합성 Gemini usageMetadata 보완 후 실제 자막 수정 실행
작성: 2026-11-12 KST

## 우선 목표
대표는 첫 영상 생성 사이클/음성 개선 이후 진행하는 **주제·대본 품질 고도화**의 기존 업무를 끝까지 잇도록 승인했다. Codex 주간 사용량이 부족하므로 이제 새로운 사전 감사/길고 반복적인 보고서/무관한 테스트로 시간을 쓰지 않는다. 현재 목표는 기존 실전 대본의 0-based beat index1, 자막 한 줄39폭을 28폭 이하/최대2줄로 개선 → 실제 AI 관리자 검토 → 실전 스토리보드 작성 및 관리자 검토 → 기존 컷룸 대표 승인 대기.

## 입력
최신 `AGENTS.md`, `reports/VIDEO_MISSION_01_CAPTION_FIXTURE_AND_REAL_RESUME_RESULT_20261112.md`, `docs/VIDEO_MISSION_01_APPROVED_CAPTION_REVISION_TO_CUTROOM_20261112.md` 및 연관 코드만 확인. 직전에는 `/tmp/caption_fixture_resume_unvalidated.patch`와 `/tmp/caption_fixture_resume_test.log`를 저장하고 미검증 소스2개/테스트1개를 원복했다. **이 패치가 현재 HEAD에 깨끗하게 적용 가능하면 재사용하고**, 아니면 연관 최소 부분만 재구성. 기존 프로덕션 파일/권한/원장에 무관한 변경 불가.

지난 표적 테스트 `tests.test_video_mission_one.MissionOneTests.test_caption_revision_new_signed_budget_and_cutroom`는: (1) 합성 manager를 accept로 재현한 후 서버 known_script_defects + 수정1회 소진 + beat1 폭39의 anchor까지 통과, (2) 새 합성 writer 응답 envelope `role=model`을 수정한 후, (3) `usageMetadata`가 없는 **fixture** 문제로 `gemini_usage_unverified`에서 막힘. 이는 실제 provider 문제 아님. 프로그램의 실전 사용량 검증을 완화하면 안 됨.

## 수행
1. 패치/테스트의 **합성 Gemini 응답 fixture에만** 이미 정상 통과한 기존 테스트와 동일한 `usageMetadata` 형식을 넣는다. 역할 및 content wrapping도 정상 fixture와 비교해 필수 항목을 한 번에 확인하라. 실제 transport/회계/검증 가드에 예외 허용을 추가하지 말 것. fixture가 정당한 별도 writer revision response인지 확인.
2. **위 표적 테스트 1개만 실행**해 새 signed continuation이 실제 원 job `qualityprovider-b96e442fd4104d8cb9da3179c5ce6bc9`의 검증된 latest version/review를 물려받되, 기존 stopped/이전 grant/revisions=1과 모든 history가 불변임을 확인. 실패가 여전히 **테스트 응답의 누락/연결 오류**라면 바로 그 fixture만 고치고 동일 테스트를 재실행해 **이런 사소한 오류마다 또 다른 별도 승인/대화로 중단하지 마라**. 단, 실제 안전 가드 실패/불명확한 승인/원본 변조 또는 회계 문제면 외부 API 호출 전 중단. 전체 suite/반복 리팩터링/무관 감사 금지.
3. 기존 `known_script_defects` 과거 job 재실행/기존 approved grant 변조/과거 failed API replay 금지. 다음 새 목적의 독립 signed continuation **정확히 하나**를 원 승인서에 따라 생성, 새 proposal/review SHA/독립 grant, 역사 속 대본 v1/v2·AI 관리자 feedback 원문 및 해시 재사용. **과거 signed 수정 1회는 사용 완료 상태 그대로 두고**, 별도 대표가 승인한 새 자막 수정 1회의 범위만 새 작업에 기록한다. 최신 writer v2 SHA `31c453ca16749713dd5e21af23bd1084a21840c88bee57f08f0ea198cd64649a`, latest review SHA `ef16051251dd8d395054499fc78d4e67eb215b0c5f02732dab53571d098519d3`.
4. DNS 연결 성공 기록이 있는 정식 권한 확장 실행 환경에서 **실제 새 job run 1회**. 무료 `gen-lang-client-0938732315`/`gemini-3.5-flash-lite`/기존 키·endpoint·입출력 서비스 개선/인적 검토 정책 조건 유지, 유료 전환/모델 교체/auto retry 금지. 신규 YouTube 검색 0. Gemini 누적17회부터 카운트; `max_calls=None`은 임의 횟수 상한 없다는 의미이며 반복 재호출 허가가 아님. provider quota/청구 독립 확인 안 되었으면 `unknown/unverified` 유지.
5. 첫 실전 writer는 **완전히 새로운 대본 생성이 아니라 최신 실제 v2 대본의 beat1 자막 수정**. Unicode W/F=2, 나머지1로 실제 각 줄 폭≤28, 최대 두 줄, 줄바꿈 정확하게 적용; 선정 주제·25초·시청자 제안·내레이션/해시·provenance/검증을 훼손하지 말 것. 모델의 주제/성과 추정을 사실처럼 수락하지 말 것. AI 관리자 검토가 **서버 검증까지** 수락한 경우에만 editor 실전 스토리보드 및 AI 관리자 편집 검토→기존 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`의 `awaiting_plan_approval` 카드 실물 인계 확인.
6. 실패하면 실제 기록 보존 후 자동 재시도/추가 successor/유료 fallback 없이 중단. 성공해도 대표 대신 승인/게시/TTS/영상렌더 금지. 예전 전체 영상 제작·음성 개선 결과와 이번 고도화 미션 구분.
7. **짧은** 결과 보고서 `reports/VIDEO_MISSION_01_FIX_FIXTURE_USAGE_AND_EXECUTE_RESULT_20261112.md`만 추가해서 GitHub main에 commit/push 및 원격 확인. 테스트/코드 최소 변경점, 새 job/review/grant, Gemini 실제 단계/누적17+신규, editor/컷룸 실물 상태, 오류 시 다음 조치 하나만 기록. 기밀/원본 대본 전문 출력 금지.

KST, 과거 history·data/backups/artifacts/.env/사용자 키/기존 음성·영상/미추적 파일 손대지 말 것. git clean/reset --hard/force push 금지.
