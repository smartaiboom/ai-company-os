# 카드 없는 TTS 준비 결과 — 2026-11-10 KST

최신 main `c3645de`에서 구현했다. 실제 TTS 요청0, 미디어 업로드0, 비용$0, 계정/과금 변경0. 공식 문서 읽기와 GitHub 통신만 수행했다. 실제 B 음성/자연스러움 개선/게시 합격은 없다.

## 공식 비교 (조회 2026-11-10 KST)

|API 모델|무료·카드|직접 API·한국어|상업 사용·현재 계정·품질|
|---|---|---|---|
|Gemini Developer 3.8 Flash TTS (우선)|Standard 입력/출력 Free of charge. 무료 사용을 위한 Cloud Billing 요구와 구분; 계정에서 카드 없이 가능한지는 미확인|공식 Interactions REST, 한국어 지원|약관/사용정책/입력권리 검토 필요. 계정 제공·쿼터·지역·기존 키 권한 미확인, 청취 미평가|
|Gemini Developer 3.8 Flash-Lite TTS (보조)|동일 Standard 무료 표시, 계정 조건 미확인|3.8과 동일 스키마, 한국어 지원|지연/효율 지향이라는 공식 설명; 품질 우열 미평가|
|Gemini Developer 2.5 Flash Preview TTS|Standard 무료 표시, 계정 조건 미확인|기존 generateContent 계열, 한국어 지원; 이번 adapter 대상 아님|3.8 불가 시 별도 검토만, 자동 fallback 없음. Preview 조건·계정·청취 미평가|
|Fish s2.1-pro-free|공식 개발자 표 $0/M UTF-8 bytes, 별도 subscription 없이 호출 가능 설명. 공식 API 공지에도 카드 불필요(무료 기간 2026-11-30까지, Fair Use); API 계정 확인 안 함|직접 API, 공식 한국어 포함83개 언어; 계정 제공/쿼터 미확인|웹 Free FAQ 비상업 조건과 API 권리 일치 미확인. 게시 후보 선정 보류, 청취 미평가|
|ElevenLabs 무료|무료 API 요금제 존재; 현재 카드/계정/선택 voice API 가능 여부 미확인|직접 TTS API·한국어 모델 있음; 무료 Voice Library 접근 별도 제한 확인 필요|공식 무료 상업권 없음. 회사 게시용 제외, 청취 미평가|
|Google Cloud Chirp3-HD|무료 문자 할당량과 별개로 Billing 활성화 필수 → 보류|Cloud API·ko-KR|현재 카드 없는 목표에서 제외|

공식 출처: [Gemini 가격](https://ai.google.dev/gemini-api/docs/pricing), [TTS 스키마/보이스/언어](https://ai.google.dev/gemini-api/docs/speech-generation), [모델 목록](https://ai.google.dev/gemini-api/docs/models), [약관](https://ai.google.dev/gemini-api/terms), [Cloud Billing 요구](https://cloud.google.com/text-to-speech/pricing), [Fish 가격/FAQ](https://fish.audio/plan/), [Fish API 요금](https://github.com/fishaudio/docs/blob/main/developer-guide/models-pricing/pricing-and-rate-limits.mdx), [Fish 무료 API 공지](https://fish.audio/ko/blog/s2-1-pro-free-api/?articleLocale=en), [Eleven API 가격](https://elevenlabs.io/pricing/api), [Eleven 상업권](https://elevenlabs.io/docs/ko/help-center/legal/can-i-publish-the-content-i-generate-on-the-platform), [Eleven 한국어](https://elevenlabs.io/docs/ko/overview/capabilities/text-to-speech).

Gemini 무료 입력/응답은 모델 개선·인적 검토에 사용될 수 있다. Google의 출력 소유권 비주장이 모든 권리 보증은 아니다. 실제 회사자료/원장/개인정보/A 음성은 전송 대상이 아니다. 위 표의 공개 무료 표시가 현재 계정 사용 가능의 증거는 아니다. 원문 공식 Markdown 사본은 로컬 보호 폴더에만 저장했다.

## 구현

`companies/video/tts_job.py`와 기존 영상회사 `prepare_staff_tts_job()`을 연결했다. provider/model/endpoint/voice, 원문·A·정확 payload 해시, 1요청/$0/출력 한도를 가진 voice job 계약이다. 공급자별 payload/envelope 처리는 Gemini 3.8만 지원하며 다른 공급자로 자동 교체하지 않는다. 공통 회사 엔진이나 관리자 승인/키/원장은 변경하지 않았다.

최신 공식 REST 예시에 맞춰 `/v1beta/interactions`, verbatim transcript와 `speech_metadata.style` 분리, Puck 사전제작 보이스, WAV/24kHz를 고정했다. CapCut/성우 복제·voice 생성 API 없음. 기존 정확60자 가상 교육문을 사용한다. 입력1000bytes, 출력20초/1024토큰/응답2MB의 로컬 수락 상한이다. **공식 wire에서 TTS 토큰 제한 강제와 실제 usage 스키마는 아직 미검증**이므로 문서에 없는 필드를 임의 전송하지 않았다. 실사용 활성화 전 확인해야 한다.

현재 실제 HTTP 전송 구현은 없다. `TTS_EXECUTION_ENABLED=False`이며 `execute()`는 항상 거절한다. 테스트 전용 `run_mock()`만 주입 transport를 받으며 실제 키 인수는 없다. simulation 증거/별도 mock 승인만 받는다. 기존 manager 동의를 사용할 수 없다. 무료/과금비활성/키바인딩/모델/지역/잔여쿼터/1시간 이내 증거 부족 시 선예약 전 거절한다. 이는 모의 경계 검증이며 실계정 인증 증명이 아니다.

개별 job 전용0700 폴더,0600 exclusive 파일·fsync/디렉터리 fsync 선예약으로 동시중복·중단·실패·타임아웃의 재시도를 차단한다. payload는0400 exact bytes. 원시 응답/키/exception 내용 저장 없음. base64/WAV PCM16 mono24kHz/길이/전체프레임·ffprobe·전체decode 후 SHA 기록. 품질 unassessed와 publish_ready=false 유지. 음성 내용 일치는 텍스트 해시와 별개로 청취가 필요하다.

## 다음 사용자 확인과 분리된 승인

**사용자가 다음에 할 정확히 1가지:** Google AI Studio에서 기존 키의 프로젝트에 `gemini-3.8-flash-tts`가 **Free Tier로 표시되고 남은 할당량이 있는지** 확인해 결과를 알려주기. 키 문자열을 채팅에 붙이지 않는다. 이 확인은 실행 동의가 아니다. 카드/결제 등록은 요구하지 않는다.

그 뒤 계정·키 바인딩/지역/잔여 입출력 쿼터·정확 usage 및 강제 상한을 확인하고, 별도로 **Gemini Developer / gemini-3.8-flash-tts / Interactions endpoint / Puck / 보호 폴더 payload SHA / 가상 대본과 무료 데이터정책 / 실패 포함 총1회 / $0 / 출력경로**에 대한 좁은 TTS 실행 승인을 받아야 한다. 기존 관리자1/1·새 manager0/1은 TTS 승인이 아니다. 실제 요청 전에 production transport 검증이 남아 있으며 지금 즉시 호출 가능하다고 주장하지 않는다.

## 실제 로컬 검토자료·검증

보호 폴더: `/workspaces/ai-company-os/data/no_card_tts/20261110T151021_KST/` (Git 제외). `prepared/payload.json`은 읽기전용 정확 UTF-8 bytes이며 SHA256=`cdfe8ddad259b3d1b5401216dbb344bb1a6f72be980c58df9d612e0bb490ea4d`. `prepared/job.json`, `review.json`, `ab_script.txt`, 공식 문서 사본을 저장했다. 가상 대본은 기존 원문 bytes와 동일하며 SHA256=`ec1e2906fd065530a2bbfc79bfab9d3769a9f72296897887f5b02d4efeeffa59`다. 원문 payload는 Git에 올리지 않는다.

실재 A 사본: `data/no_card_tts/20261110T151021_KST/A_reference_melo.wav` (원본 SHA256=`a011f8bb6b83e5d3515171bcdf6fc9e9aa09d42844f8e14cfbb8955de18b25a5`, ffprobe·전체decode 확인). B 실음성은 없어 A/B 완료·B 다운로드를 제시하지 않는다. `mock_project/B_MOCK_NOT_TTS.wav`는 1초 PCM fixture이며 TTS/한국어 발화가 아니다. `mock_project/result.json`의 파일해시·decode 통과는 품질 증거가 아니다.

마지막 통합: `PYTHONPATH=core:companies/video python -B -m unittest discover -s tests -v` → **63개 중60통과/3선택skip/실패0,114.378초**. 새 TTS4테스트에 exact wire·텍스트 해시/모의 WAV 해시·코덱·전체decode, 무료/쿼터/시각/별도승인 차단, 비활성 차단, 재시작 중복, timeout/응답실패/유료값/토큰·길이·응답크기 초과와 재시도0, 변조/가상입력 거절이 포함된다. 기존 엔진·관리자·피드백·영상 테스트도 포함했다. 통합로그는 위 보호 폴더의 `integration.log`. `git diff --check` 통과. 기존 미추적 보고서7개는 커밋 대상에서 제외했다.

보존 검증: 기존 data/ 및 존재하는 backups/artifacts/.env*의 일반 파일 **45,528개**를 이번 보호 폴더 생성 후 사전/사후 SHA256으로 대조해 **변경·삭제0**. 원문 manifest와 결과는 보호 폴더 `preservation_before.json`, `preservation_result.json`에만 저장했다. 새 보호 폴더는 비교에서 제외했다. 기존 실제 프로젝트·관리자 동의/시도/비용 원장을 재실행·수정하지 않았다.
