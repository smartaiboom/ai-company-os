# Gemini 한국어 실제 A/B 실행 결과 — 2026-11-10 KST

**대화상 실행 승인은 인정했으나 현재 무료 조건 근거·로컬 개인 서명 미충족으로 전송 전에 중단했다. TTS 생성 요청0/1, attempt0/1, 비용$0, 실제 B 없음.** 최신 main `7c61aab` 및 AGENTS.md/실행 지시서를 확인했다. 모델 목록 재조회·새 어댑터·게이트 개발·영상 렌더·회귀 반복은 하지 않았다.

## 실제 진행과 중단 지점

기존 `tts_cli.py prepare`를 그대로 실행해 다음 격리 작업을 만들었다:
`/workspaces/ai-company-os/data/gemini_tts_actual_ab/20261110T160649_KST/`.
사용자 화면으로 전달된 실제 프로젝트 ID를 로컬 scope에 바인딩했고 Git 보고서에는 ID를 반복하지 않는다. payload.json과 scope.json을 재검증했다. 기존 원 job과 A는 변경하지 않았다.

- Gemini Developer API / gemini-3.8-flash-tts / Puck / 기존 동일60자 가상 교육문과 스타일.
- POST `https://generativelanguage.googleapis.com/v1beta/interactions`.
- payload SHA256: `9dde86070b2cb5be7263d654cd208a6ead743e7074a76c5162e10ff0edd5bd16` (기존과 동일).
- store=false, wire 출력1024토큰, 실패 포함 외부 요청1회/$0 정책, 재시도·fallback 없음.
- 예정 B 출력: 위 격리 루트 `B_gemini.wav` (**현재 파일 없음**).
- 실제 A: `data/no_card_tts/20261110T151021_KST/A_reference_melo.wav`. 원 job의 A SHA256 `a011f8bb6b83e5d3515171bcdf6fc9e9aa09d42844f8e14cfbb8955de18b25a5`와 재대조해 일치했다. B가 없으므로 B 코덱/크기/길이/해시·실제 발화 일치 검사는 하지 못했다.

기존 GEMINI_API_KEY가 있으며 과거 로컬 대조 기록의 유효한 HMAC 바인딩과 현재 키가 일치함을 비밀노출 없이 확인했다. 기존 실제 models.list GET1회/HTTP200/61모델과3.8 TTS 포함을 **인증·모델 목록 증거로 인정**하고 재조회하지 않았다. 사용자 화면의 무료 등급과 대화상1회 동의·무료 데이터정책 사전안내도 인정한다.

그러나 현재 합성 무료쿼터/Billing 비활성/지역 지원을 증명하는 최신 계정 자료가 없고 이 격리 작업의 account.json·signed review.json·consent.json도 없다. 과거 키 대조 증거는 만료됐으며 새 TTS 계정 확인/서명으로 승격하지 않았다. models.list는 무료잔량/합성 성공/0원 보장이 아니다. `TTS_EXECUTION_ENABLED=False` 유지, `execute`/사용자 대신 `verify-key`/`approve --owner-confirmed` 실행0. 키는 요청·파일·인수·로그에 넣지 않았다.

중단 근거: [이번 실행 지시서](../docs/RUN_GEMINI_REAL_TTS_AB_APPROVED_20261110.md) 3항은 로컬 개인 승인이 필요하면 사용자 직접 CLI 승인을 요구하며, “Codex가 사용자를 대신해 키 프롬프트나 서명 승인을 처리하지 않는다.” 6항은 무료 제공/지역/출력쿼터 독립 확인 방법이 없으면 전송 중단을 요구한다. 대화상 동의를 재요청하는 것이 아니라 기존 실행 경계의 개인 서명과 아직 확인되지 않은 무료 조건이 남았다.

## 사용자 다음 작업 하나: Codespaces에서 계정 확인·개인 서명 세션 완료

사용자가 직접 아래 세션을 진행한다. 키는 오직 secure prompt에 입력하며 채팅/파일/명령 인수로 보내지 않는다. 확인되지 않은 값은 채우지 않으며 확인할 수 없으면 중단한다. 유료 설정/카드 등록은 하지 않는다.

1. 기존 템플릿 `data/no_card_tts_execution/20261110T153342_KST/account_evidence_TEMPLATE_NOT_VERIFIED.json`을 새 작업 루트의 `owner_evidence.json`으로 복사해 **실제 확인한 값만** 입력한다. project는 새 scope.json의 실제 ID와 동일해야 한다. 필요한 항목을 한 번에 정리하면 다음과 같다.

|입력|필요한 실제 근거/값|
|---|---|
|project/model|scope.json의 실제 프로젝트/gemini-3.8-flash-tts|
|tier/billing|현재 Free / disabled 확인|
|model_access/region_supported|현재 available / 지원지역 true 확인; 추정 금지|
|remaining_requests/input/output_tokens|현재 남은 수치, 각각 최소1/2048/1024 필요. 모델의 최대 토큰 규격을 잔여값으로 사용 금지|
|checked_at/expires_at|실제 관찰 KST ISO 시각/1시간 이내 만료|
|evidence_sha256/observation|실제 로컬 확인 자료 SHA256/관찰 내용과 할당량 시간창. 키 포함 금지|
|source_url/method|https://aistudio.google.com/ / owner_aistudio_review_not_independent_verification|
|paid_fallback|false(유료 전환 금지 정책)|

이 로컬 진술은 독립 공급자 인증서가 아니다. 화면에서 값이 보이지 않거나 무료 이용을 보장할 근거가 없으면 임의 true/잔여수치를 작성하지 않는다.

2. 실제 근거를 확보한 경우에만 기존 CLI를 실행한다. 아래 명령은 **사용자용 안내이며 Codex가 대신 실행하지 않았다**.

```sh
export PYTHONPATH=core:companies/video
TTS_AB_ROOT=/workspaces/ai-company-os/data/gemini_tts_actual_ab/20261110T160649_KST
python -B companies/video/tts_cli.py --root "$TTS_AB_ROOT" verify-key --evidence "$TTS_AB_ROOT/owner_evidence.json"
python -B companies/video/tts_cli.py --root "$TTS_AB_ROOT" review
```

3. 위 review의 실제 해시·기한·프로젝트/출력위치와 읽기전용 payload를 확인한다. 전송은60자 가상 안내문만이며 A/실자료/원장은 보내지 않는다. 무료 입력/응답은 Google 제품 개선 및 인적 검토에 사용될 수 있고 store=false는 이 정책의 거부가 아니다. 해당 정확 본문·Puck·실패 포함1회/$0에 동의할 때만, 사용자가 반환된 REVIEW_HASH를 아래에 넣고 직접 secure 키 대조/서명을 한다.

```sh
python -B companies/video/tts_cli.py --root "$TTS_AB_ROOT" approve REVIEW_HASH --owner-confirmed --accept-google-data-policy
```

서명 기록이 생겨도 상수는 비활성이며 자동 전송하지 않는다. 무료 조건 근거와 개인 서명이 유효한지 확인된 뒤에만 이번 승인 범위의 제한 활성화·단1회 실행을 이어갈 수 있다. 새 음성 생성 동의나 모델 선택을 반복 요청하는 단계가 아니다. 확인 불가능한 조건은 그대로 중단 사유다.

## 검증·보존·실물 상태

prepare/status·원 job/payload/A 해시·현재 키의 과거 바인딩 확인은 socket/DNS 차단 패치 아래 수행했다. 선예약/전송을 만들지 않았다. 로컬 `preflight_result.json`은 대화상 승인 인정, 무료 조건 미확인, 개인 서명 없음, 실제 요청0/attempt0/비용0을 구분한다. 사용자의 기존 승인·비용·시도 원장/영상/대본/키/기존 WAV는 변경·재실행·초기화하지 않았다. 이번에는 전체45,000여 파일 해시/전체 회귀를 반복하지 않았다. 코드·테스트 변경 없음. 보고서2개만 Git에 반영하며 로컬 source/payload/프로젝트ID/키/미디어는 올리지 않는다.

실제 B WAV/다운로드 링크는 없다. 실제 A는 위 경로에서 들을 수 있으나 A/B 비교는 미완료다. quality=unassessed, publish_ready=false이며 자연스러움/상업권 합격을 주장하지 않는다.
