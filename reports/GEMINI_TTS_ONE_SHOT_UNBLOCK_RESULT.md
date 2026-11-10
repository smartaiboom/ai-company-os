# Gemini 한국어 TTS 실제1회 생성 결과 — 2026-11-10 KST

**실제 TTS POST1회·HTTP200·B_gemini.wav 생성 성공. 전송 전 영속 선예약1/1, 재시도0, fallback0.** 최신 main `213ee72`에서 실행 장애를 최소 수정하고 승인된 동일 본문으로 실제 수행했다. 정상 서명 흐름/관리자 게이트·전역 기본값은 유지했다. 자연스러움은 사용자 청취 전 unassessed, 권리는 unverified, publish_ready=false다.

## 최소 수정과 승인 provenance

`companies/video/tts_execution.py`의 발송·예약·응답검증 부분을 `_send_authorized`로 재사용하고, **execute_chat_trial 단일 작업 정책**만 추가했다. 일반 `execute`의 signed account/review/consent 검사와 `TTS_EXECUTION_ENABLED=False`, 기존 run_mock/관리자 게이트는 그대로다. 환경변수/일반적인 다른 프로젝트·대본·모델로 확대되지 않는다.

이번 정책은 `user_chat_approved_single_free_tts_trial`, 동의 출처는 **explicit_chat_user_approval_2026-11-10**이다. 이번 지시서의 exact SHA, 실제 프로젝트 SHA, 모델3.8/Puck/원문·A·payload SHA, 유일한 operation 루트, 기존 키의 과거 HMAC 바인딩, 실제 models.list GET200 증거를 검사한다. 다른 TTS 루트의 비모의 attempt와 유료 계정 반증이 있으면 차단한다. 모의 attempt만 구분해 제외한다. 독립 guard와 operation attempt를 각각 exclusive/fsync로 전송 전에 예약한다.

`chat_approval_receipt.json`은 **기계가 작성한 대화 승인 provenance 기록**이며 개인 HMAC 서명/owner-confirmed라고 가장하지 않는다. 이번 operation에 CLI consent.json/서명키를 만들거나 사용자 키 프롬프트를 대신 처리하지 않았다. 원래 정상 signed flow는 여전히 개인 서명을 요구한다. 한정 경로의 상수 기본 활성화는 없으며 승인된 고정 operation 내부에서만 실제 발송한다. 이미 소모한 guard/attempt는 유지한다.

계정 근거는 **owner_screenshot_free_tier**, independently_verified=false. 사용자가 전한 무료 등급/카드·Billing 미연결 상태와 기존 키의 실제 모델 제공 응답을 이번1회 무료 실험에 수용했다. 남은 quota=unknown, 지역 독립검증 없음으로 기록했다. 숫자/지역 true를 창작하지 않았다. quota 초과 시 실패할 위험을 허용하되 유료 fallback/설정 변경은 금지했다. 무료 프로젝트 근거로 예상 비용0원, 추가 결제/카드·Billing 활성화0. **공급자 청구액·과금0을 독립 측정/보증한 것은 아니며 청구 API는 호출하지 않았다.**

## 고정 요청과 실제 응답

- 요청: POST `https://generativelanguage.googleapis.com/v1beta/interactions`, gemini-3.8-flash-tts / Puck.
- payload SHA256: `9dde86070b2cb5be7263d654cd208a6ead743e7074a76c5162e10ff0edd5bd16` (기존 승인 본문과 동일, 수정 없음).
- 기존 가상60자 교육 안내문/스타일만 전송. A 음성·실제 회사자료·개인정보·원장 전송 없음.
- store=false, 출력1024토큰, 로컬 입력2048토큰·응답2MB·음성20초 수락 제한. 로컬 한도는 공급자 비용 보증이 아니다.
- 완료 시각: `2026-11-10T16:20:45.857780+09:00`. **HTTP200 / input33 tokens / output201 tokens / 8.04초**.
- 실제 외부 TTS 요청1/1, operation attempt1/1 및 독립 guard 소비, 오류 없음, 추가 models.list0회. 확인용 추론·다른 API 요청 없음.

공식 [TTS wire](https://ai.google.dev/gemini-api/docs/speech-generation), [Interactions 참조](https://ai.google.dev/api/interactions-api), [무료 데이터 약관](https://ai.google.dev/gemini-api/terms)을 읽기 전용으로 재확인했다(2026-11-10 KST). 기존 payload를 바꿀 필요가 없었다. 무료 입력/응답의 제품 개선·인적 검토 가능성과 store=false의 구분을 유지했다. 키는 x-goog-api-key 헤더만, proxy/redirect/retry 없는 기존 send_once를 사용했다. 키·원시 응답·header/오류 본문은 저장/출력하지 않았다.

## 실제 A/B 파일

보호 루트: `/workspaces/ai-company-os/data/gemini_tts_single_free_trial_v1/operation/`.

- **A_reference_melo.wav**: 기존 A의 정확 사본. 원본 `data/no_card_tts/20261110T151021_KST/A_reference_melo.wav` 보존.
- **B_gemini.wav**: 이번 실제 Gemini 응답의 WAV. 모의파일이 아니다.

두 파일을 Codespaces 탐색기의 위 폴더에서 재생하거나, 각각 우클릭 → Download로 내려받아 A 다음 B 순서로 듣는다. wav/원문/로컬 계정·승인 증거는 GitHub에 올리지 않는다.

전송 발화문 SHA256=`ec1e2906fd065530a2bbfc79bfab9d3769a9f72296897887f5b02d4efeeffa59`. 기존 A에 사용한 ab_script.txt와 정확 bytes가 일치함을 확인했다. **실제 B 발음·누락·톤·자연스러움/말한 내용의 일치도는 사용자 청취 전 미평가**다. 코덱 통과나 더 짧은 길이를 품질 개선 합격으로 해석하지 않는다. 속도 조정·자르기·재합성·후처리를 하지 않았다.

## 검증과 보존

한 묶음 검증: `PYTHONPATH=core:companies/video python -B -m unittest tests.test_tts_execution tests.test_tts_job tests.test_manager_plan_once -v` → **22통과/실패0,3.014초**. 기존 signed/mock/manager 게이트와 새 대화 승인 한정 경로, quota unknown의 정직한 기록, owner서명 미가장, 정확 scope/doc/key/payload/root, 유료 반증·기존attempt 차단, 400/429/timeout 실패소모와 재시도0을 mock HTTP로 검증한 뒤 실제 요청1회를 수행했다. 이후 실 API를 테스트로 반복 호출하지 않았다. `git diff --check` 통과.

로컬 파일: `source_job.json`, read-only `payload.json`, `scope.json`, `chat_approval_receipt.json`, `attempt.json`, `result.json`, `execution_receipt.json`, `AB_verification.json`, 사전/사후 보존 manifest·결과, 테스트로그·공식문서 사본. operation 바깥 독립 `trial_attempt.json`도 유지한다. 기존 관리자1/1·준비0/1·사용량/승인/비용 원장은 수정하지 않았다. 키/미디어/전체 응답/로컬 원문은 Git 제외하며 코드·테스트·보고서만 커밋한다.

**다음 할 일 하나:** A와 B를 직접 듣고 B의 발음·톤·자연스러움이 원하는 수준인지 평가하기. 추가 생성/확대/게시를 자동 진행하지 않는다.

실물 기술 검증(둘 다 ffprobe·전체 ffmpeg decode 통과):

|파일|크기 bytes|길이 초|코덱/샘플레이트/채널|
|---|---:|---:|---|
|A_reference_melo.wav|968666|10.982109|pcm_s16le / 44100Hz / mono|
|B_gemini.wav|392038|8.040000|pcm_s16le / 24000Hz / mono|

A SHA256=`a011f8bb6b83e5d3515171bcdf6fc9e9aa09d42844f8e14cfbb8955de18b25a5`。
B SHA256=`7674f8d8449f5011aff56efd6c4f52ba7d878c43541df6d7043442a4ba831419`。
기존 data/ 및 존재하는 backups/artifacts/.env*의 일반파일 **45,568개 사전/사후 SHA256 대조, 변경·삭제0**. 새 single-trial 작업 폴더만 비교에서 제외했다. 원본 A·기존 영상·원장·키를 재생성하거나 삭제하지 않았다.
