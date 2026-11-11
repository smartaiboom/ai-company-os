# 미션 01 — 실제 Google 프로젝트 ID 반영 및 실행 재개
작성일: 2026-11-11 KST

## 목적과 신규 확정 정보
대표가 Google Cloud Console의 프로젝트 링크를 제공했다.
- 표시 이름: `Default Gemini Project`
- URL에 지정된 **Gemini 프로젝트 ID**: `gen-lang-client-0938732315`
- 이 ID는 사용자 제공 Cloud Console URL의 `project=` 값이다. API 키 원문은 아님.
- 사용자는 이 Gemini 키 생성 프로젝트와 **결제 계정이 미등록인 것으로 확인한 프로젝트가 동일하다**고 별도로 확인했다.
- 단, YouTube API 키가 속한 Google Cloud 프로젝트까지 동일하다는 확인은 아직 없다. 서로 같은 것으로 가정하거나 허위 입력하지 말 것.

목표는 이미 승인한 첫 게임 쇼츠 미션의 실제 AI 조사→관리자 결정→대본 작성→내부 검토→컷룸 대표 기획 승인 대기까지 실행하는 것이다. 지난 차례에 없었던 프로젝트 ID 한 항목을 제공하는 후속 작업이다. 같은 감사/테스트/설계/중복 보고를 반복하지 않는다.

## 이미 완료한 기능과 승인 범위
읽을 문서: `AGENTS.md`, `reports/VIDEO_MISSION_01_QUOTA_GATE_FIX_AND_EXECUTION_RESULT_20261111.md`, `reports/VIDEO_MISSION_01_FINAL_REAL_RUN_RESULT_20261111.md`, `docs/VIDEO_MISSION_01_FINAL_REAL_RUN_20261111.md`.
- 최신 컷룸: `company-aba553f29cfb454c8c05bad4abb49969`
- 연결된 직원 업무: `qualityprovider-504d90900918450f98dd62b6f7704f1b`
- Gemini 고정 모델 `gemini-3.5-flash-lite`, 실제 텍스트 호출 실패 포함 최대 10회
- YouTube Data API 검색 `search.list` 최대 4회, 영상 정보 `videos.list` 최대 4회
- 무료 서비스만 허용, 유료 전환/자동 재시도/fallback/모델 변경 금지
- 대표는 이번 목표와 공개 자료·AI 직원 결과의 Google 무료 API 외부 전송 및 서비스 개선/인적 검토 가능성에 동의했다.
- 실제 대표 기획 승인 클릭, TTS/WAV/MP4/게시 금지. 이번에는 기획안·대본을 대표 승인 **대기**에 올리는 것까지만.

## 수행
1. 안전한 GitHub fast-forward와 기존 동의·시도 원장의 중복 실행 방지만 확인한다. 기존 미추적 파일·사용자 데이터·키를 보존한다.
2. 기존 `prepare`에 Gemini 프로젝트 식별자로 `gen-lang-client-0938732315`를 입력한다. 잔여량 미확인 항목은 이미 구현한 `unknown` 경로 사용. 실제 사용자 확인과 독립된 공급자 인증 검증을 혼동하지 않는다.
3. YouTube 키 프로젝트는 기존 설정/확인 가능한 로컬 자료에서 실제 프로젝트 식별자가 있는지 **관련 항목만** 살펴본다. 같은 프로젝트라는 증거가 있다면 검증된 ID를 사용한다. 확인이 안 되면 Gemini 프로젝트 ID를 YouTube 프로젝트에도 복사하지 말고, YouTube 키 생성 프로젝트 ID 하나만 사용자에게 요청한 뒤 중단한다. 이때 새 개발/전체 감사/반복 테스트 금지.
4. 두 프로젝트 ID 및 기존 무료 안전조건이 충족되면, 현재 코드의 `prepare → proposal/review hash 검토 → approve → run`을 기존 서명/사용량 가드에 따라 진행한다. 프로젝트 불일치, 제공자 유료 경로 노출, 무료 모델 사용 불가능 등 **실제 신규** 위험이 드러나면 호출하지 않고 정확한 사유만 보고한다.
5. 실제 호출은 기존 승인 상한에 포함한다. 직원은 인기 게임·쇼츠 길이를 자율 조사하고, 관리자 선정→한국어 전체 대본→검토/수정→대표 승인 대기 순으로 진행한다. Codex가 답안·후보·길이 등을 선제 주입하거나 mock을 실제 직원 작업으로 표시하지 않는다. 모든 로그 KST, 실패·불명 요청 자동 재시도 금지.
6. 결과를 `reports/VIDEO_MISSION_01_PROJECT_ID_RESUME_RESULT_20261111.md`에 기록해 안전하게 GitHub에 반영한다. 실제 호출 0회로 차단될 경우 보고서 중복 생성은 피하고 한 가지 차단 사유 및 필요한 정보를 Codex 대화에 간결히 출력한다.

## 금지
`git clean`, `git reset --hard`, 강제 push, 비밀키·헤더 출력/커밋, 기존 승인/시도/음성/영상/백업 수정·삭제, 미승인 유료 호출과 재시도 금지.
