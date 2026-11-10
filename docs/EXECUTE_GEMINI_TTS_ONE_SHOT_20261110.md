# 실행 지시: 무료 Gemini 한국어 TTS 실음성 B 단 한 번 생성 (2026-11-10 KST)

## 이번 일은 '또 준비하기'가 아닌 실제 A/B 실험
사용자가 기존 AI Studio 무료 할당량이 충분히 남은 것 같다고 확인하고 “진행해”라고 명시했다. **이번 범위에서만** 기존 60자 가상 안내문을 Gemini Developer API `gemini-3.8-flash-tts`에 1회 전송해 실제 `B_gemini.wav`를 생성하는 작업을 진행하라. 다만 무료 모델 접근/쿼터/Billing 비활성/개별 정확 본문 승인 등 안전 게이트가 충족되지 않으면 **요청 없이 정지**, 문제와 최소 필요한 확인만 기록. 사용자는 카드가 없고 어떤 금전 과금도 승인하지 않았다. 일반적 “진행해”가 원 payload 해시·Google 무료 데이터정책의 확인을 대체하지는 않는다.

## 선행 문서
AGENTS.md, reports/NO_CARD_TTS_EXECUTION_GATE_RESULT.md, reports/NO_CARD_TTS_READINESS_RESULT.md, reports/CURRENT_PROGRESS.md, companies/video/tts_execution.py, companies/video/tts_job.py, companies/video/tts_cli.py. 기존 local 자료 `data/no_card_tts/20261110T151021_KST/`, `data/no_card_tts_execution/20261110T153342_KST/`. 현재 실행 코드는 구현되고 모의 HTTP 70개 테스트(67 pass/3 skip) 통과, `TTS_EXECUTION_ENABLED=False`; 실제 생성은 0회 상태. 중복 준비·엔진 재개발·UI/웹·새 60초 렌더 금지.

## 공급자와 요청 고정
- 공급자 Google **Gemini Developer API** (Cloud Chirp3-HD는 불가), 모델 `gemini-3.8-flash-tts`, endpoint `https://generativelanguage.googleapis.com/v1beta/interactions`, Puck 보이스, 기존 60자 가상 테스트 대본 및 친근한 한국어 쇼츠 안내 스타일.
- 정확 요청 SHA256(11/10 준비): `9dde86070b2cb5be7263d654cd208a6ead743e7074a76c5162e10ff0edd5bd16`. 단 실제 request review와 바이트가 동일한지 검증하고 코드 수정을 했다면 새 hash를 명시적으로 검토받아야 한다.
- `max_output_tokens=1024`, 요청 `store=false`, 단일 요청 실패 포함 1회; 절대 자동 재시도·fallback 없음; 신규 비용 $0, 유료 계정/Billing/카드 등록·크레딧 구매 없음; 사용자 동의를 얻은 가상 테스트 입력만 전송, 회사자료·실 개인정보·기존 음성 A/원장/API키 외부 전송 금지. Google Free Tier 입력은 서비스 개선/인적 검토 대상이 될 수 있다는 점 사용자에게 미리 표시.
- 공식 기준 https://ai.google.dev/gemini-api/docs/pricing 의 **Gemini 3.8 Flash TTS Standard Free Tier input/output free**, https://ai.google.dev/gemini-api/docs/speech-generation 및 https://ai.google.dev/gemini-api/terms. 공개 무료 가격표는 **현재 사용자 계정 무료 자격 증명이 아니다**.

## 이번에 실제로 할 일
1. **계정 상태/정확 승인**: 기존 프로젝트의 해당 TTS 모델 무료 접근/한국어/요청 및 출력 쿼터, 키-프로젝트 연결, Billing 비활성, 지역 지원을 확인. 진짜 확인할 수 있는 자료만 근거로 저장하고 불확실은 추정하지 마라. 기존 `tts_cli.py`의 `prepare/status/verify-key/review/approve` 사용. CLI에서 보안 프롬프트로 키 확인, 키를 로그/터미널 인수/파일/GitHub/대화에 절대 노출하지 마라. 사용자가 정확 job review 해시와 Google 무료 데이터 이용 조건 및 1회/$0 조건을 로컬에서 명시 승인했을 때만 proceed. 아직 승인 자료가 없다면 review 파일과 필요한 한 가지 확인을 보여주고 여기서 정지. 동의가 필요한 경우 Codex가 사용자를 대신해 `--owner-confirmed`를 지정하지 마라.
2. **실행 상수 활성화는 해당 조건이 모두 충족되었을 때에만** TTS 전용의 가장 작은 범위로 수행. 코드·테스트·권한 또는 기존 원장 우회 금지. 새 고립 root; `attempt.json`을 실제 전송 **전** fsync 예약. 전송 성공/실패/timeout/429 등 결과 불문 1회 소진. 기존 사용량 관리자 기록과 혼동하지 마라.
3. 실제 유료 전환이 필요한 증거가 나타나면 절대 호출하지 않고 정지. 무료 계정 확인에 필요한 공식 문서를 보되 확인용 API 요청도 외부 API 호출이며 승인 범위가 아니라면 임의로 실행 금지.
4. **성공 시** 실제 WAV(PCM mono24kHz, ffprobe·ffmpeg decode·해시·파일 크기·발화길이) 생성 및 기존 A Melo wav와 실제 동일 원문인지 검사. B는 *실제 Gemini가 생성한 경우에만* B_gemini.wav. 발음/톤/자연스러움 만족 판정은 사용자가 직접 듣기 전 '미평가'. 로컬 생성 폴더와 실제 A/B 파일의 확인 방법을 사용자에게 제공. 반환이 없으면 실생성 성공이라 표기 금지.
5. 사용자가 확인/승인할 수 없는 조건이 남았다면 **거기서 작업을 종료하고 실행 가능한 review·상태 보고**. 네 번의 비슷한 개발 준비 작업처럼 거듭 새 어댑터/게이트만 쌓지 말 것.
6. `reports/GEMINI_TTS_REAL_ONE_SHOT_RESULT.md`와 `reports/CURRENT_PROGRESS.md`에 구분: 실전송 0 또는 1, 선예약 0/1, 성공 B 실물 여부·파일 위치/해시, 무료/비용 증거, 승인 hash, 미확인/중단 사유, 다음 사용자 행동 딱 하나. 결과가 바뀌었다면 GitHub main에 **코드·테스트·보고서만** push. 기존 로컬 data/비밀키/미디어/예전 사용자 산출물 보존. 테스트는 이번 변경 부분 위주, 전체 회귀는 필요할 때 1회만.

## 성공
실제 무료 TTS 요청 1회가 사용자 서명·계정 무료 조건 충족 하에 이루어지고 **듣고 비교할 한국어 WAV가 생기는 것**. 또는 무료/동의 근거 부족일 때 무과금·0회 안전 중단하고 사용자에게 확인 가능한 다음 한 조치만 남기는 것. 실물이 없으면 품질 개선 성공이라 하지 않는다.
