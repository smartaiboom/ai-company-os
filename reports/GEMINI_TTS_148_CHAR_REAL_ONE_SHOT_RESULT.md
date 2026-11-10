# Gemini 한국어 148자 실제 음성 생성 결과 — 2026-11-11 KST

Gemini Developer API의 `gemini-3.8-flash-tts` / Puck으로 승인된 148자 대본을 합성했다. 실제 POST 1회, HTTP 200, 입력 82토큰·출력 538토큰, 응답 검증 상태 `audio_validated`. 중단 후 재개한 작업에서는 기존 결과를 로컬에서 검증했으며 Gemini API 요청은 0회였다.

## 실제 WAV

|항목|실측 결과|
|---|---|
|파일|`/workspaces/ai-company-os/data/video_voice_selection/20261110_v1/next_trial/B_next_gemini.wav`|
|크기|1,039,076 bytes|
|SHA-256|`6ef2673b6f977981a789d27b132c8233090e049e299cda6f11e946936ccb149f`|
|길이|21.520초, 목표 범위 15–35초|
|포맷|WAV, PCM signed 16-bit little-endian, 24 kHz, mono|
|검증|`ffprobe` 스트림·길이 확인 및 `ffmpeg -xerror` 전체 디코딩 통과. 파일 크기·해시가 실행 결과 기록과 일치|

Codespaces 파일 탐색기에서 WAV를 내려받아 청취할 수 있다. 발화 일치와 청취 품질은 미평가다. 전체 자연스러움(10점), 목소리·억양, 듣기 편함, 속도·쉼, 후크 전달력을 청취 후 평가한다. 이전 60자 B는 실물 8.04초이며 사용자가 자연스러움 7/10을 부여했다. 대본과 길이가 달라 점수 차이를 목소리나 스타일의 효과로 단독 해석할 수 없다.

## 승인·시도·비용

- 08:35:12 KST에 작업 attempt와 독립 guard를 각각 영속 예약했다. 두 기록의 payload SHA-256은 검토 원본 `1216b0c8c575c37dbaba04e18d474bbee13c4aa67e33f12edc519466b05cf354`와 일치하며, attempt의 scope·consent 해시도 로컬 기록과 일치한다. 대화 승인 출처는 `explicit_chat_user_approval_2026-11-11`로 기록했다. 개인 HMAC 서명 여부는 false다.
- 기존 무료 프로젝트의 사용자 등급 확인, 같은 키의 모델 목록 HTTP 200 및 이전 실제 60자 POST 성공 기록을 사용했다. 재시도·fallback·유료 전환·결제 설정 변경은 각각 0회다. 현재 잔여 쿼터·지역 지원·공급자 청구액은 독립 확인하지 않았다.
- 검토 wire 그대로 `store=false` 및 출력 최대 1,024토큰을 적용했다. 로컬 JSON 응답 한도는 2 MB다. Google 무료 API의 입력·출력 데이터 이용 정책은 승인 문서에 기록되어 있다. [Google 공식 TTS 문서](https://ai.google.dev/gemini-api/docs/speech-generation)
- 이전 60자 guard·attempt의 소모 상태와 승인·scope 해시 연결, 기존 A/B 파일 해시를 확인했다. 기존 사용자 자료와 원장에 쓰지 않았다. WAV·키·로컬 payload·승인·시도 원장은 로컬에 보존했다.

## 코드와 테스트

`companies/video/tts_execution.py`의 기존 전송·예약·오디오 검증을 재사용했다. 승인 문서와 검토 wire의 고정 해시, 모델·보이스·무료 프로젝트·키 연결을 검사하는 단일 경로를 추가했다. 이 경로의 WAV 상한은 35초이며 기존 60자 및 일반 실행의 기본 상한은 20초다. 일반 서명 흐름과 관리자 실행 기본값을 유지했다.

`tests.test_tts_execution`, `tests.test_tts_job`, `tests.test_voice_quality`, `tests.test_manager_plan_once` 오프라인 30개 통과. 신규 경로의 정확한 전송 바이트, 선예약·중복 차단, 21초 WAV 수락, 해시·키·유료 반증 차단, 응답 한도와 기존 서명·관리자 경계를 검증했다.
