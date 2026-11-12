# 미션 01 — 자막 폭 규칙의 정확한 전달 최소 수정
2026-11-12 KST

## 목표
기존 영상 전체 제작 사이클과 음성 개선은 이미 완료 경험이 있다. 현재 주제 선정/대본 AI 품질 고도화 중이다. 직전 실전 `reports/VIDEO_MISSION_01_PARTIAL_WRITER_REVISION_CONTINUATION_RESULT_20261112.md`에서 신규 업무 `qualityprovider-b96e442fd4104d8cb9da3179c5ce6bc9`는 실제 writer v2 수정 HTTP200 및 관리자 review HTTP200을 마쳤다. dense_narration은 해결됐으나 첫 비트의 자막 `caption_width` major 결함이 남아 관리자의 accept를 서버가 `known_script_defects`로 차단했다. 잘못된 모델 accept를 성공으로 승격하지 않는다. 대본·검토 부분 결과 보존, 컷룸 `research_planning`.

**Codex 주간 사용량 절약이 중요하다. 이번에는 관련 최소 코드 한두 곳·표적 테스트 최소 1묶음만 실행. 추가 API 호출 없이 수정 계약을 개선하고 보고 후 중단.** 전체 테스트/재설계/다른 기능/예산 코드 및 불필요한 진단 금지.

## 확인할 핵심 파일
`AGENTS.md`, 직전 위 보고서, `companies/video/script_quality.py`의 실제 자막 폭 판정 알고리즘, `companies/video/quality_workflow.py`, `companies/video/video_mission_one.py`의 writer의 실제 systemInstruction/schema/invariants 및 manager revision_feedback 전달 위치만 확인. 원본 대본·피드백 전문은 외부 보고서에 복제하지 않는다.

## 최소 작업
1. 자막 허용 기준을 **실제 서버의 폭 계산 규칙과 일치하게** writer 생성/수정 시점에 명확하게 전달한다. 기존 `2줄, 줄당 28폭 단위`를 단순 글자 수로 혼동하지 않게 해당 코드의 한글/영문 폭 계산 예시를 **짧은 형식 예시**로 주고, 줄별 실제 폭을 검사하며 28폭 이하로 만드는 요령을 명시한다. 허용 폭을 임의 증가시키거나 경고를 무시하지 않는다.
2. 사용자에게 설명한 것처럼 AI 관리자가 남은 major 결함을 수락해도 서버가 차단하는 안전장치는 그대로 유지한다. 품질 검사 기준이 이미 올바르면 불필요한 검사 수정 금지. 필요하다면 모델의 수정 피드백에 `caption_width` 및 구체적인 권장 수정 방법이 전달되는지만 고친다. 대본을 무음으로 재작성/수락시키지 않는다.
3. 이미 보존된 초도 대본·수정 대본·실제 관리자 검토를 원본 그대로 보존. 일곱 번을 넘긴 과거 실패/최근 paused·stopped/모든 sign/grant/attempt 및 누적 Gemini17, YouTube search2/videos2 수정 금지. 기존 영상/음성/미디어 불변.
4. 관련 **최소 오프라인 테스트**: 폭 기준을 벗어난 자막 거부, 올바른 두 줄 이하/각 줄 폭 내 자막 통과, 실제 writer 수정 지시/payload에서 정확한 폭 계약 확인, manager가 남은 major 결함 accept 시 서버가 계속 막는지 확인. 실제 API 0회, 새 후속 업무·새 동의·grant 0건. 전체 회귀 불필요.
5. 현재 공통 continuation 경로가 signed max_revisions_per_task=1 및 이미 사용한 원 수정 한도를 우회하지 않음을 유지한다. 다음 실전의 안전한 이어받기 가능 여부는 보고서에 **간단히 결론만** 남긴다. 이 작업으로 실전 새 업무를 생성하지 않는다.
6. 성공/실패 무관 `reports/VIDEO_MISSION_01_CAPTION_WIDTH_MINIMAL_CONTRACT_FIX_RESULT_20261112.md`에 변경 파일/표적 테스트/실 API0/원본 보존/다음 실제 제작 단계 1개를 **짧게** 작성해 GitHub commit/push 후 중단.

KST, git clean/reset --hard/force push/유료 전환/자동 retry/기존 원장 수정 금지.
