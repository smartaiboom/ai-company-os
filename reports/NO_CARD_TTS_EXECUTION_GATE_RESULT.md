# 무료 TTS 실제 실행 경계 결과 — 2026-11-10 KST

최신 main `3ed9a29`에서 **실제 HTTP 실행 코드와 CLI를 구현하고 mock HTTP로 검증**했다. 실제 TTS API0회, 미디어 업로드0, 비용$0, 계정/과금 변경0. 실제 음성 B·청취평가·자연스러움 개선 증거는 없다. `tts_execution.TTS_EXECUTION_ENABLED=False`를 유지했다. 기존 mock-only `TTSJob.run_mock()`/`execute()` 및 관리자 전송 게이트는 그대로다.

## 구현한 실행 경로

- `companies/video/tts_execution.py`: GeminiTTSAdapter와 독립 TTSExecution. 기존 job 검증·canonical bytes·LiveStore HMAC 서명·private_write의 exclusive/fsync 예약·직접 HTTP opener·로컬 미디어 명령 실행기를 재사용했다. 공통 회사 엔진/역할/기존 스토어/UI 재작성 없음.
- 서명 scope는 `video_tts_exact_once_v1`. 실제 프로젝트 ID, 원 job 해시, model/endpoint/voice, 정확 payload SHA, 1회/$0, 출력 절대경로, 무료 데이터정책, 1시간 이내 기한과 계정 증거 해시를 묶는다. 로컬 전용0700 폴더와 독립0600 서명키를 사용한다. 이전 관리자 서명·일반 채팅·환경변수로 활성화할 수 없다.
- 계정 기록에는 Free/Billing disabled/모델 제공/지역/잔여 요청·입출력 토큰/관찰 시각과 만료/증거 파일 SHA/관찰 내용·출처를 요구한다. 실행 키와 프로젝트 키를 로컬에서 비교하고 HMAC credential binding만 저장한다. **사용자 AI Studio 확인 진술이며 독립 원격 검증이 아니다.** 단순 boolean만으로 검증 완료를 주장하지 않는다. 현재 이 사용자에 대한 계정 기록/서명 승인 생성0.
- 발송 직전 `attempt.json`을 exclusive 생성하고 파일·디렉터리 fsync. 성공/오류/429/timeout/불확실 중단 모두 소모되며 동시중복/재시작 추가 요청을 차단한다. 예약 직후 전송 전 중단도 안전하게1회 소모한다. 재시도/fallback/추가 조회 없음.
- 고정 HTTPS endpoint와 POST, 헤더에만 키, TLS/소켓 timeout30초. 기존 `send_once()`로 proxy 환경·redirect·retry 차단. 응답 Content-Length와 실제 최대2,000,001bytes 읽기 후2MB 수락 상한, JSON/MIME/status/usage/base64/WAV 검사. 키/원시 응답/원시 exception은 원장·CLI에 출력하지 않는다.
- WAV는 별도 `B_gemini.wav`에 exclusive 저장. PCM16/mono24kHz/20초 이내·전체프레임, ffprobe·전체decode·SHA 기록. 권리 unverified, publish_ready=false, quality=unassessed. 부분/실패 파일이 남으면 예약은 소모된 상태이고 다시 호출하지 않는다. 실제 발화 일치/자연스러움은 사람 A/B 전 미검증이다.

## 공식 wire 교차 검증과 변경

조회일2026-11-10 KST. [공식 speech-generation](https://ai.google.dev/gemini-api/docs/speech-generation), [Interactions 개요/보관](https://ai.google.dev/gemini-api/docs/interactions-overview), [공식 API 참조](https://ai.google.dev/api/interactions-api), [가격](https://ai.google.dev/gemini-api/docs/pricing), [무료 데이터 약관](https://ai.google.dev/gemini-api/terms)을 읽었다. 공식 Markdown 사본은 로컬 보호 폴더에만 저장했다.

공식 TTS 예시의 `/v1beta/interactions`, `input[].content[].annotations[].speech_metadata.style`, `generation_config.speech_config`와 `response_format`을 사용한다. 기본 unary WAV는24kHz mono16bit이며 명시적으로 audio/wav·24000을 요청한다. 실제 응답은 interaction/completed, `steps[].type=model_output`의 단일 audio/base64 data와 MIME이다. 예전 mock의 `usage.mock/output_tokens/cost_usd`를 실제 provider 형식으로 재사용하지 않는다.

공식 API 참조의 `generation_config.max_output_tokens=1024`를 추가했고, 실제 `usage.total_input_tokens/total_output_tokens/total_tokens` 및 thought/tool 토큰0을 검사한다. TTS 모델에서 실제 상한을 지키는지는 **실 호출 전까지 미실측**이다. 미지원 파라미터/usage 누락/불완전 결과는 실패 소모로 종료한다. 일반 API 참조 지원이 현재 프로젝트의 모델 권한·TTS 성공을 보장하지 않는다.

Interactions는 기본 저장이 켜져 있으므로 새 요청에 공식 `store=false`를 명시했다. 이는 무료 입력/출력의 모델 개선·인적 검토 정책을 거부하는 기능이 아니다. 응답2MB/입력2048토큰/20초는 **로컬 수락 제한**이며 서비스 측 생성 중단/과금 상한이 아니다. 0원 요청 정책은 현재 Free Tier와 Billing 차단에 대한 사용자 확인에 의존한다. 공급자 과금·동시 쿼터 소비를 독립 보장하거나 응답 usage만으로 비용0을 증명하지 않는다. 실제 돈을 쓰는 Cloud Billing 경로는 도입하지 않았다.

## 사용자에게 제시할 좁은 전송 개요

|항목|고정 값/현재 상태|
|---|---|
|공급자/모델|Gemini Developer API / gemini-3.8-flash-tts|
|endpoint|POST https://generativelanguage.googleapis.com/v1beta/interactions|
|음성|Puck 사전제작 보이스. CapCut/성우 복제 없음|
|내용|기존 동일60자 가상 교육 안내문. 실제 회사자료·개인정보·원장·A 음성 전송 없음|
|스타일|친근한 한국어 직장인 쇼츠 안내, 또박또박·경쾌한 자연스러운 대화체, 과장/특정 성우 모사 금지|
|정확 payload SHA256|`9dde86070b2cb5be7263d654cd208a6ead743e7074a76c5162e10ff0edd5bd16`|
|시도/비용 정책|실패 포함 총1회, $0, 자동retry/fallback 없음|
|상한|wire 출력1024토큰; 로컬 입력2048토큰/응답2MB/20초|
|출력|계정 확인 후 새 서명 job 루트의 B_gemini.wav. 루트 절대경로까지 review에 고정|
|현재 계정/동의|프로젝트 ID·키 연결·모델권한·무료/Billing 차단·지역·잔여쿼터 미확인. 실제 실행 승인 없음|

새 로컬 검토자료: `/workspaces/ai-company-os/data/no_card_tts_execution/20261110T153342_KST/`. read-only `payload.json`, `source_job.json`, `transmission_review.json`, **미확인** `account_evidence_TEMPLATE_NOT_VERIFIED.json`, 공식문서/검증로그. 프로젝트는 null로 두었으며 가짜 계정 확인·실제 서명을 만들지 않았다. 기존 `data/no_card_tts/20261110T151021_KST/` 원본 job/payload/A는 불변. 새 원 payload/키/미디어/계정자료는 Git 제외.

## 언제/어떻게 실제1회가 가능해지는가

1. 사용자가 기존 AI Studio 프로젝트에서 실제 프로젝트 ID와 해당 모델의 Free Tier/모델 제공/지역/Billing 비활성·잔여 요청 및 입출력 쿼터를 확인한다. 관찰시각·쿼터 적용 시간창·로컬 증거 해시를 기록한다. 확인할 수 없는 항목은 추정하지 않고 멈춘다. 키를 GitHub/채팅에 보내지 않는다.
2. 터미널 CLI로 새 격리 루트를 준비하고 계정 증거·키를 로컬 대조한다. 아래 PROJECT_ID/NEW_PRIVATE_ROOT는 실제 확인값으로 바꿔야 한다. 루트는 아직 존재하지 않는 경로여야 하며 템플릿의 null은 실제 확인값으로 채운 별도 로컬 JSON을 사용한다.

```sh
export PYTHONPATH=core:companies/video
python -B companies/video/tts_cli.py --root NEW_PRIVATE_ROOT prepare --source-job data/no_card_tts/20261110T151021_KST/prepared/job.json --project PROJECT_ID
python -B companies/video/tts_cli.py --root NEW_PRIVATE_ROOT status
python -B companies/video/tts_cli.py --root NEW_PRIVATE_ROOT verify-key --evidence LOCAL_OWNER_EVIDENCE.json
python -B companies/video/tts_cli.py --root NEW_PRIVATE_ROOT review
```

3. 사용자가 로컬 `payload.json`, `scope.json`, 서명 `review.json`의 프로젝트/본문해시/voice/출력위치/1회/$0/기한과 무료 데이터 이용정책을 확인한 후 **그 review_hash에 대한 별도 명시 승인**을 한다. `approve REVIEW_HASH --owner-confirmed --accept-google-data-policy`는 secure TTY에서 키를 대조하고 로컬 서명 동의를 생성한다. 단순 채팅 확인만으로 CLI 승인이 자동 생성되지 않는다.
4. 이번에는 activation을 하지 않는다. 다음 별도1회 실행 지시서에서 계정 증거/검토·동의가 유효한 시간 내 모두 확인된 경우에만 **이 TTS 전용 코드 상수의 제한된 활성화**를 검토한다. `execute`가 동일 키·서명·기한·payload를 다시 검사한 뒤 실제 요청1회만 보낸다. 환경변수 옵션으로 상수를 변경할 수 없고 기존 관리자 활성화와 무관하다. 소비/불확실 중단이면 추가 execute 금지. 만료한 미사용 job은 재검토가 필요하며 기존 예약을 초기화하지 않는다.

CLI는 키를 secure getpass로 받고 non-TTY/fallback echo를 거절한다. 키 인수/URL/출력 지원 없음. 자동 원격 계정/키 확인 API는 구현·호출하지 않았으며 주인 확인을 요구한다. CLI 검증·서명 기록은 독립 공급자 인증서가 아니다.

## 실제 검증 결과

집중 mock HTTP7테스트 통과 후, 최종 통합 **70개 중67통과/3선택skip/실패0,16.714초**. 명령 `PYTHONPATH=core:companies/video python -B -m unittest discover -s tests -v`. 기존63테스트 유지, 새7개에 실제 Request 인코딩/키 헤더·exact bytes/공식 usage·WAV parsing, 서명·옛 scope·키 변경·만료·payload 변조·무료/쿼터 증거 누락·동의 누락, 기본 비활성·환경변수 무효, timeout/429/응답크기·usage·MIME 한도, 중단 후 재실행 차단·동시예약1회, non-TTY·proxy/redirect 차단을 포함한다. HTTP는 전부 mock, fixture 키는 가짜이며 계정 확인이 아니다. 실제 B로 표시한 테스트 미디어를 사용자 폴더에 만들지 않았다. 권리 미확인/publish_ready=false를 유지했다. `git diff --check` 통과.

기존 보호파일45,545개(data/ 및 존재하는 backups/artifacts/.env*)를 새 작업폴더 제외 사전/사후 SHA256으로 대조해 변경·삭제0. manifest/결과는 새 보호 폴더에만 저장했다. 기존 Gemini 관리자1/1·준비0/1·영상·WAV·승인/비용/시도 원장을 재실행하거나 초기화하지 않았다. 기존 미추적 보고서7개는 커밋 제외한다.

원 발화문 비공개를 위해 Git 테스트에는 별도의 가상 대본 fixture와 테스트 전용 해시 패치를 사용했다. 이 fixture 교체 후 새7테스트도 재확인해 모두 통과(1.190초)했으며 로그는 보호 폴더 `private_fixture.log`에 저장했다. 실제60자 원문 일치/새 wire 해시는 보호 폴더의 실제 준비자료에서 별도로 확인했다.
