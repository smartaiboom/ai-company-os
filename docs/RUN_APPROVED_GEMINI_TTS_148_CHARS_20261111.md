# 승인된 Gemini 한국어 148자 음성 — 실제 1회 생성 및 검증
작성: 2026-11-11 KST
실행 대상: `smartaiboom/ai-company-os` / `companies/video`

## 이번 사용자의 명시적 승인 — 정확히 이 범위
사용자는 2026-11-11 다음과 같이 명시 동의했다.

> 어제 준비한 148자 가상 회의 대본을 Gemini 3.8 Flash TTS/Puck으로 실제 1회 생성하는 데 동의해. 기존 무료 계정만 사용하고 유료 전환·자동 재시도 없이, 무료 API 데이터 이용 정책도 이해했어. Codex 실행 지시서를 만들어줘.

**목적은 모의 응답이 아니라 실제 음성 파일 한 개를 생성하고 사용자 청취를 받는 것이다.** 영상제작 전문 AI 회사의 품질 개선 2단계 작업이며, 앞서 제작된 품질 낮은 60초 영상을 처음부터 다시 만드는 일이 아니다. 무료 API 입력/출력은 Google의 서비스 개선 및 인적 검토에 이용될 수 있다는 점을 사용자가 이해했다. `store=false`는 그 정책의 옵트아웃이 아니다.

### 정확한 전송 원문 (줄바꿈 없이 한 문단)
금요일 세 시. 회의가 확정된 걸까요? 이건 가상 회의 메모예요. 금요일 세 시는 제안일 뿐, 아직 확정이 아닙니다. 반면, 목요일까지 고객에게 확인하고 다시 알려주겠다는 말은 확인 업무의 기한이죠. 회의 시간은 미정, 확인 기한은 목요일. 두 칸으로 나눠 보세요.

- 원문 SHA256: `dee1aef757a0c7edac0a6314fef7559591bab1e506ab59066dbb62a5fe3d243b`
- 스타일 정확 문자열: `친근하고 또렷한 한국어 대화체. 질문 뒤 짧게 쉬고 의미 단위로 나눠 말하기. 과장·성우 모사 없음.`
- Gemini Developer API / `gemini-3.8-flash-tts` / 보이스 `Puck`.
- 엔드포인트: `POST https://generativelanguage.googleapis.com/v1beta/interactions`
- 어제 생성한 검토 전용 원래 wire: `data/video_voice_selection/20261110_v1/next_payload_REVIEW_ONLY.json`. canonical payload SHA256: `1216b0c8c575c37dbaba04e18d474bbee13c4aa67e33f12edc519466b05cf354`. **그 파일의 실제 바이트를 먼저 읽고 SHA·원문·스타일·모델·voice와 구조가 일치하는지 독립적으로 재검사한 후 사용한다. 바이트/해시가 다르면 전송하지 않는다.**
- `store=false`, 출력 최대 1024토큰, 오디오 WAV PCM16 24kHz mono, 로컬 응답 최대 2MB.
- 새 실물 생성 결과의 목표 수락 시간 15~35초. 실제 15초 미만일 경우 기술적으로 정상이라도 사용자 품질을 임의로 낮게 단정하지 말고 원본 파일 보존과 실측 길이를 보고하되, 기존 코드의 20초 상한으로 21~35초를 잘못 거부하지 않도록 **이번 단일 실행 범위에 한해서** 최대35초 수락을 지원. 허용 상한을 초과할 경우 결과 실패·재시도 없음. 실제 낭독이 20초라는 보장은 없으며 장면별 3/5/7/5초는 실측 전 추정이다.
- 예정 출력: `/workspaces/ai-company-os/data/video_voice_selection/20261110_v1/next_trial/B_next_gemini.wav`. 해당 경로가 이미 존재하거나 이번 작업 실호출 시도가 확인되면 **절대 덮어쓰거나 재시도하지 않는다**.

## 반드시 읽고 준수할 기반
`AGENTS.md`; `reports/GEMINI_TTS_ONE_SHOT_UNBLOCK_RESULT.md`; `reports/VIDEO_VOICE_USER_AB_FEEDBACK_RESULT.md`; `reports/VIDEO_VOICE_SELECTION_AND_NEXT_SAMPLE_RESULT.md`; `reports/CURRENT_PROGRESS.md`; `companies/video/tts_execution.py`; `companies/video/tts_job.py`; `companies/video/voice_quality.py`; 관련 테스트; 실제 로컬 검토 payload / scope / 현존 attempt들.

**옛 60자 실호출/guard 1/1은 이미 소모됨**. 절대 초기화·변조·재사용 금지. 신규 scope/작업마다 유일한 선예약 기록을 `O_EXCL + fsync` 방식으로 영속화하고, 중단/시간초과/HTTP 오류도 실패 포함 **1회 소모**. 기존 서명·승인 경계를 일반 모드에서 무력화하지 않는다. 대화상 승인 기록은 `explicit_chat_user_approval_2026-11-11`로 출처 구분; 실제 사용자가 터미널에서 개인 HMAC 승인했다고 **가장하지 않는다**.

## 실제 실행 순서 (불필요한 준비 루프 금지)
1. 현재 repo/main과 자료를 확인. 이 신규 payload가 이미 한번 전송되었는지 `next_trial`·기존 voice trial guard/attempt/receipt·해시를 검사. 기존 성공 WAV가 있다면 중복 요청 없이 검증만 보고한다.
2. 기존 `tts_execution.py`의 `_send_authorized`·안전 예약·decode/ffprobe/ffmpeg를 **재사용**하여 이번 148자/35초 이내/정확 SHA와 프로젝트에 한정한 1회 통로를 최소 변경 구현. 새 전역 TTS 허용 상수 True 금지. API 스펙을 읽기만 하고 기존 검토 wire를 변경하지 말 것. 만약 검토 wire로 실요청 불가능할 정도의 스키마 불일치가 확인되면 조용히 본문/스타일/요청 구조 변경 후 호출하지 말고 장애물 보고. 다른 유료/비인가 모델로 대체 금지.
3. 사용자의 이전 AI Studio 무료 등급 화면, 기존 API 키로 실제 `models.list` 200/3.8 TTS 제공 증거, 지난번 같은 무료 프로젝트의 실제 60자 POST 성공 및 과금 설정 변경 없음 기록을 재사용. **무료 프로젝트에서만** 수행하고, 유료 청구/Billing 활성화/유료 전환의 현재 증거가 있거나 project/key 불일치면 요청 전 정지. 정확한 잔여 quota 수치·지역 지원을 증명할 수 없는 경우 임의로 값을 작성하지 마라. 무료 모델 목록 및 지난번 성공은 이번 호출의 잔여 quota/비용 0원 보증이 아님을 기록. 카드 등록/유료 결제설정/유료 fallback/자동 재시도는 절대 금지.
4. 실제 외부 호출 이전에 변경 코드의 범위 제한·중복 attempt·응답 한도·해시/승인·유료반증 차단 및 기존 signed/manager 경계를 최소 한 묶음 **오프라인 mock 테스트**. **테스트에 실 API 포함 금지**.
5. 모든 조건 충족 시 정확 payload 하나로 실제 외부 Gemini TTS POST **최대 1회**. preflight 직후 영속 attempt와 독립 guard를 먼저 예약. 비밀 키는 헤더로만, 파일/로그/보고서/커밋에는 절대 저장 금지. redirect/proxy/retry/fallback 금지. 서버 응답은 비밀을 포함하지 않은 상태코드·토큰사용량·응답포맷만 기록. 400/429/timeout 포함 실패도 재호출 금지.
6. 성공 시 신규 WAV 실제 존재/크기/sha256/ffprobe/ffmpeg 전체 디코딩/실제 길이 측정. 수정한 음성 파일을 '더 자연스럽다'고 미리 평가하지 말 것. 기존 60자 B8.04초 자연스러움7/10은 사용자 원본 점수로 보존, 새 음성의 점수/억양·듣기 편함·속도/쉼·후크 전달력은 사용자 청취 전 **미평가**. 원음원과 원 데이터 보존, 게시/상업권 판정 없음.
7. 다음 보고서와 CURRENT_PROGRESS 갱신 후 GitHub main에 코드·테스트·보고서만 push. WAV·키·로컬 payload/승인/attempt·기존 사용자 data는 GitHub에 올리지 않는다. `git reset --hard`/`git clean`/기존 원장 리셋 금지.

## 산출 보고서
`reports/GEMINI_TTS_148_CHAR_REAL_ONE_SHOT_RESULT.md` 반드시 작성:
- 기존 실물60자 B7점과 **새 148자 실제 음성 생성 여부**를 구분. 호출 전 실패면 실제 POST 0회, 실패 후면 1회 소모라고 정확히 명시.
- 서버 HTTP 코드/토큰/상태, 요청 횟수·reserved attempt·재시도/fallback·비용 설정 변경 여부, 독립 과금 확인되지 않음.
- 새 파일 절대경로 `.../next_trial/B_next_gemini.wav`, 파일 SHA/크기/시간/코덱/디코드 통과 여부.
- 새 사용자 청취용 평가 항목(전체 자연스러움 10점, 목소리·억양, 듣기 편함, 속도·쉼, 후크 전달력). 이전 7점과 다른 대본·길이로 인한 비교 한계.
- 소스코드 변경점/관련 테스트, 기존 사용자 자산·guard·원장 보존 여부, 실제 호출과 모의 테스트 명확 구분.
- 실패했다면 **실제 중단 이유 1개와 그 위치·실행 가능한 조치 1개**를 제시. 의미 없는 재승인/장부/보안장치 구축 준비 문서 반복 금지.

## 개발 목표
이번 성과 기준은 Gemini 음성 설정/모의 오디오가 아니라 **실제 장문 한국어 WAV 생성 및 사용자가 들을 수 있는 파일**이다. 그러나 사용자 승인과 무료 조건이 충족되지 않으면 무리하게 호출하지 않는 것이 우선이다. 원래 만들어 둔 품질 낮은 60초 영상의 **음성 품질을 개선하는 2단계**임을 잊지 말고, 성과가 확인되면 후속 대본·영상 퀄리티 작업으로 연결한다.
