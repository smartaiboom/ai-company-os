# 미션 01 무료 API 실행 준비 점검

- 점검일: 2026-11-11 KST, 12:06 이후 로컬 읽기 전용 점검.
- 기준: `main`, HEAD와 `origin/main` 모두 `495ba1ee1b78e23f9f1768d08e6730d8f357430d`. fast-forward 동기화 완료. 기존 미추적 로그/프로브 7개 보존.
- 결론: **승인 보류.** 키 등록은 현재 환경에서 확인했지만, 정확한 모델의 무료 접근·키 소속 프로젝트·잔여 할당량·데이터 정책 동의가 미확인이다. 결제 미등록만으로 $0 실행을 보장할 수 없다.

## 근거와 현재 상태

읽은 문서: `AGENTS.md`, 이번 `docs/VIDEO_MISSION_01_FREE_API_EXECUTION_READINESS_20261111.md`, `reports/CURRENT_PROGRESS.md`, `reports/VIDEO_FIRST_REAL_AI_PLAN_SCRIPT_MISSION_RESULT.md`, `reports/VIDEO_MISSION_01_EMPLOYEE_WEB_RESEARCH_RESULT.md`, 관련 `docs/VIDEO_MISSION_01_AI_EMPLOYEE_WEB_RESEARCH_CONNECTION_20261111.md`, `docs/VIDEO_MISSION_01_REAL_AI_PLAN_SCRIPT_TO_CEO_REVIEW_20261111.md`.

읽은 코드: `companies/video/video_mission_one.py`, `employee_web_research.py`, `representative_workflow.py`, `core/quality_provider.py`, `autonomous_gemini35.py`, `autonomous_gemini.py`, `autonomous_free.py`, `autonomous_live.py`, `goal_dialogue_live.py` 및 관련 호출/예산 가드 정의.

대상 컷룸은 `company-aba553f29cfb454c8c05bad4abb49969`, 연결 업무는 `qualityprovider-504d90900918450f98dd62b6f7704f1b`다. 컷룸 단계는 `research_planning`, 업무 상태는 `ready`이며 `youtube_public_research_v1` 연결이 있다. 서명 동의·consent 파일·텍스트 시도·세션·배정 업무·활성 실행·웹 예약/시도는 없다. 실제 기획·대본 및 대표 검토 결과는 생성되지 않았다.

이전 업무 `qualityprovider-3132c9fab6aa47bf8bdd3588ae8d6c0b`도 승인/시도 없이 이력에 보존됐다. 동일 목표의 이전 컷룸 `company-3866df23fc9f4d50a7600bcde3ecf504`와 업무 `qualityprovider-e7a1e19b419748b88fd67feb35351c6c`가 별도로 있으나 해당 업무 역시 승인·시도·세션이 없다. 이번 확인 범위인 studio/mission_one_provider에서 중복 실행 증거는 없다. 후속 실행 대상은 위 최신 연결 업무 하나로 제한해야 한다.

기존 Puck TTS의 `data/gemini_tts_single_free_trial_v1/operation/attempt.json`과 `data/video_voice_selection/20261110_v1/next_trial/attempt.json`은 각각 `reserved_consumed`를 유지한다. 이들은 별도 경로·승인·시도 원장이며 이번 텍스트/YouTube 승인을 대체하지 않는다. 과거 음성 호출이 현재 텍스트 모델의 무료 접근이나 남은 요청을 증명하지도 않는다.

## 무료 조건 확인 수준

|항목|현재 확인|남은 확인|
|---|---|---|
|Gemini 키|현재 프로세스 `GEMINI_API_KEY` 존재|유효성·소속 프로젝트·모델 접근은 미검증|
|YouTube 키|현재 프로세스 `YOUTUBE_DATA_API_KEY` 존재. 과거 보고서의 키 없음은 이전 시점 정보|유효성·API 활성화·키 제한 및 소속 프로젝트 미검증|
|Google Cloud 결제 미등록|사용자 보고|공급자 콘솔 독립 접근 없음. 실제 키 프로젝트의 Billing/AI Studio 요금제와 일치하는지 확인 필요|
|YouTube 할당량 확인|사용자 보고|정확한 프로젝트·버킷·잔여 수치·확인 시각·리셋 시각·분당 제한 자료 없음|
|Gemini 무료 모델/쿼터|코드가 `gemini-3.5-flash-lite`로 고정|해당 모델이 현재 계정 무료 요금제에서 제공되는지, 일일 잔여 ≥10, RPM/TPM 및 실제 입력 크기 수용 여부 확인 필요|
|실행 설정|`GEMINI35_MODEL`, `GEMINI35_ENDPOINT`, `GEMINI35_AUTONOMOUS_FREE_ENABLED` 모두 부재|승인 후에만 고정값 설정 가능. 이번에는 설정하지 않음|
|데이터 조건|코드에 무료 AI 데이터 이용 고지 및 YouTube 30일 기한 존재|현재 적용 약관·지역/계정별 조건 확인과 명시 동의 필요|

키 값·일부 글자·키 해시·인증 헤더는 출력하거나 기록하지 않았다. `.env`를 로드하거나 변경하지 않았다. 콘솔 접속·웹 검색·CLI 인증·API 프로브는 수행하지 않았다. 아래 정책/쿼터 숫자는 **기존 코드와 로컬 문서에 있는 가정**이며 최신 공식 문서나 계정 조건을 이번에 독립 검증한 결과가 아니다.

## 승인 범위 한 건의 초안 — 현재 승인 보류

대표 원문 목표: “요즘 인기있는 게임에 대한 흥미있는 쇼츠 영상을 만들어봐. 기본적으로 인기있는 쇼츠는 몇초인지도 확인해보고.” 한국어 9:16 YouTube Shorts 기획·조사·대본·편집 인수까지만 허용하는 한 건이다. 조사 직원이 질의/비교 후보/기간을 만들고 관리자가 근거와 길이를 결정한다. 특정 게임·순위·초 수를 사전 지정하지 않는다.

|서비스|고정 모델/엔드포인트|실패 포함 상한|확인 필요한 무료 조건|
|---|---|---|---|
|Gemini 텍스트|`gemini-3.5-flash-lite`, `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`|최대 10회, 회당 출력 최대 4,096토큰. 기본 8회 + 내부 수정/재검토 최대 2회|정확 모델의 무료 접근·잔여 요청·RPM/TPM·키 프로젝트/Billing|
|YouTube 검색|GET `https://www.googleapis.com/youtube/v3/search` (`search.list`)|최대 4회|로컬 구현은 search 전용 버킷 호출당 1, 잔여 ≥4를 전제. 기존 문서의 일 100회 주장 및 실제 계정 버킷 체계 재확인|
|YouTube 메타데이터|GET `https://www.googleapis.com/youtube/v3/videos` (`videos.list`)|최대 4회, 웹 합계 최대 8회|로컬 구현은 일반 버킷 호출당 1, 잔여 ≥4를 전제. 기존 문서의 일 10,000단위 및 실제 계정 조건 재확인|

호출 수 상한은 현재 코드와 호환된다. 직원 질의 최대 4개에 각각 search 1회와 결과가 있을 때 videos 1회다. **할당량 계산의 계정 호환성은 미확인**이다. 콘솔에서 다른 비용/버킷 체계를 표시하면 현재 ≥4 가드를 무료 충분성의 증거로 쓰지 말고 중단해야 한다. 다른 앱의 동시 사용·리셋·분당/토큰 제한 때문에 일일 잔여만으로 연속 10회가 가능하다고 단정할 수 없다. 코드에는 공급자 계정 조회나 능동적인 RPM/TPM 간격 조절이 없으며 429를 성공까지 재시도하지 않는다.

외부 전송은 YouTube에 직원 질의·기간·지역/언어 힌트·공개 영상 ID, Gemini에 목표·제약·역할 지시·공개 검색 메타데이터·이번 실행의 선행 결과/수정 피드백이다. 인증키는 공급자 인증에만 사용한다. 기존 보류 후보·개인/회사 자료·음성 입력은 이번 업무 입력에 넣지 않는다. 입력 계약에는 경험/피드백 필드가 있으므로 승인 직전 비어 있는지도 재확인한다.

로컬에는 입력 컨텍스트·검증된 역할 결과·요청/응답 해시·시각/HTTP/토큰 진단·공개 URL/제목/길이/조회수/게시일 및 도구 영수증이 저장된다. 무료 Gemini 입력/출력의 제품 개선·인적 검토 가능성을 확인하고 동의해야 한다. YouTube 데이터에는 30일 기한이 있으나 자동 정리 기능은 없다. 실제 수집 시 사본 및 모델 결과에 전달된 데이터까지 운영자가 기한 내 갱신/정리할 책임을 확인해야 한다. Shorts 분류·세로 형식·시청자 국가·인기 일반화·사용권은 미확인으로 남는다. API 조사 승인은 영상 다운로드/이용권 승인이 아니다.

승인의 비용 조건은 무료 이용만 허용하고 유료 결제 연결·요금제 변경·자동 유료 대체·추가 쿼터 구매를 금지하는 것이다. 코드의 `max_cost=0`, `cost_usd=0`, `billing_disabled=True`는 승인 조건/자기 확인 기록이며 공급자 청구 측정이나 $0 보증이 아니다.

## CLI 및 중단 가드 검토

- `connect-web`: 최초에는 새 업무와 연결 이력을 저장하는 변경 작업이다. 현재 이미 연결됐으므로 재실행할 필요 없다.
- `prepare`: 상속 경로를 포함해 읽기와 제안 본문 반환이며 서명/예약 저장은 없다. 무료 계정 인수를 코드가 사실 조회하는 것은 아니다. 이번에는 이 명령도 실행하지 않았다.
- `approve`: 명시 동의·제안 해시·초기 상태·만료·키 연결·범위를 검사한 뒤 서명 파일과 승인 상태를 저장한다. 이미 있는 consent 파일/시도는 재승인을 차단한다. 제안 유효기간은 1시간이다. 이번에는 생성하지 않았다.
- `run`: 서명·정확 모델/엔드포인트·실행 플래그·키 연결을 검사한다. 시작 시 기존 세션/시도가 있으면 재시작을 차단한다. 웹은 배치를 먼저 예약하고 각 GET을 송신 전에 원장에 기록한다. 실패/불명 배치를 다시 보내지 않는다. Gemini도 송신 전 시도를 소모한다. 대표 검토 결과가 이미 있으면 외부 재호출 없이 제출만 처리하는 경로가 있다.

중단 기준: 키/프로젝트 불일치, 무료 모델 부재, Billing/요금제·쿼터·정책 미확인, 서명 만료/변경, 기존 시도/불명 예약/세션, HTTP 오류·429·시간 초과, 상한 도달, 근거 누락/만료 또는 계약 불일치. 실패·불명 호출을 자동 재시도하거나 다른 모델/서비스로 전환하지 않는다. 기획 대표 검토에서 멈추며 TTS/WAV·MP4·업로드·게시·대표 기획 승인 자체는 범위 밖이다.

확인과 별도 대표 승인이 모두 끝난 뒤에만 사용할 명령 형식은 다음과 같다. 아래는 실행 기록이 아니며 자리표시자를 실제 검증값으로 채워야 한다.

```bash
PYTHONPATH=core:companies/video python -B -m video_mission_one prepare company-aba553f29cfb454c8c05bad4abb49969 --confirm-free-account --account-project <Gemini키프로젝트> --remaining-requests <검증한잔여요청> --quota-note <모델별무료접근과RPM_TPM확인근거> --youtube-project <YouTube키프로젝트> --youtube-searches-remaining <검증한검색잔여> --youtube-units-remaining <검증한일반잔여> --confirm-youtube-policy
PYTHONPATH=core:companies/video python -B -m video_mission_one approve company-aba553f29cfb454c8c05bad4abb49969 --proposal <검토한로컬제안JSON> --review-hash <제안검토해시> --confirm-free-data-policy
PYTHONPATH=core:companies/video GEMINI35_MODEL=gemini-3.5-flash-lite GEMINI35_ENDPOINT=https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent GEMINI35_AUTONOMOUS_FREE_ENABLED=1 python -B -m video_mission_one run company-aba553f29cfb454c8c05bad4abb49969
```

`prepare`의 출력 JSON을 검토 가능한 로컬 제안 파일로 보관하고 그 `review_hash`를 승인에 사용해야 한다. 이 준비/승인/실행은 이번 작업에서 모두 수행하지 않았으며 현 보고서는 실행 권한을 부여하지 않는다.

## 실제 수행 결과와 다음 한 단계

실외부 AI·YouTube·검증용 API·웹 검색 0회, 소스 수정 0건, 테스트 실행 없음. 기존 24개 통과는 과거 오프라인 결과로만 취급했다. 프로젝트·원장 상태 전환 없음. 기존 studio 및 관련 두 음성 자료 루트 59개 파일의 점검 전후 바이트 해시 비교 결과 변경/누락 0건이다(키 해시는 생성하지 않음). 보고서의 실제 키 값 미포함 검사와 diff 공백 검사를 통과했다. 이번 변경은 이 신규 보고서 하나이며 기존 미추적 파일은 추가하지 않는다. GitHub 동기화/보고서 push만 요청된 저장 작업으로 수행한다.

**다음 행동 한 단계:** 사용자가 두 키의 실제 프로젝트 콘솔/AI Studio에서 Billing 미연결·무료 요금제, 고정 텍스트 모델 제공 여부, Gemini 잔여 ≥10 및 RPM/TPM, YouTube 실제 검색/일반 버킷 비용·잔여·분당 제한을 확인한 시각과 함께 제공하고 무료 AI 데이터 처리 및 YouTube 보존 조건을 수락한다. 그 증거로 위 단일 범위를 확정한 뒤 별도 대표 승인을 받아야 한다. 현재는 확인 및 승인 보류 상태에서 중단한다.
