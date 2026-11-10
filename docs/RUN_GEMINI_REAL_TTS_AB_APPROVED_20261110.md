# Gemini 3.8 Flash TTS 실제 한국어 B 음성 1회 생성 — 2026-11-10 KST

## 이번 사용자의 명시적 동의와 목표
사용자는 ChatGPT에서 다음 실험을 구체적으로 안내받은 후 **“응 진행해”라고 명시적으로 동의**했다:
- **기존 60자 가상 교육 대본** 1건을 Google Gemini Developer API Free Tier에 전송. 실제 회사 자료/개인정보/기존 A 녹음/원장 전송 금지.
- 모델 **gemini-3.8-flash-tts**, 보이스 **Puck**, 기존 준비된 한국어 직장인 쇼츠 음성 스타일.
- **실패 포함 외부 TTS 생성 요청 최대 1회**, 자동 재시도·fallback·여러 모델 비교 호출 없음.
- **무료 이용 가능 근거가 있을 때만 요청, 유료 과금/결제수단 등록/Cloud Billing 활성화 금지**.
- 사용자는 Google 무료 등급 데이터가 제품 개선 및 인적 검토 대상이 될 수 있다는 사전 안내를 받았다.
- 목적은 **B_gemini.wav 실제 파일**을 확보해 기존 **A_reference_melo.wav**와 듣고 비교하는 것. 음성 만족/상업적 게시 가능을 아직 주장하지 않는다.

이번 작업은 사용자의 위 *대화상 승인*을 실행 지시로 반영한다. 기존 `TTSExecution`의 **정확한 본문·계정·로컬 서명 승인 안전 게이트를 우회하지 말 것**. 사용자 동의를 Codex가 거짓으로 서명하거나 `--owner-confirmed`를 임의 지정해서는 안 된다. 로컬 사용자의 추가 직접 승인이 필요하다면 검토 내용을 **간결하게 표시하여 실제 사용자가 해당 CLI에서 승인**할 수 있게 하라. 반대로 대화상 동의로 이미 확인된 범위를 반복 확인하기 위해 새 설계·새 준비 문서를 만들지 말 것.

## 사실로 확인된 기존 상태 — 같은 조회 반복 금지
- **실제 기존 API 키 `GEMINI_API_KEY`로 `GET /v1beta/models?pageSize=100` 1회, HTTP200, 61개 모델**, `models/gemini-3.8-flash-tts` 및 Flash-Lite/2.5-preview TTS 반환. 보고서 `reports/GEMINI_TTS_MODEL_LIST_CHECK_RESULT.md`. **모델 조회 재실행 불필요**.
- 사용자 화면: **Default Gemini Project / 무료 등급 / 기존 API 키 한 개**, 사용량 상세에는 이전 사용 모델만 나왔음. 무료 모델 제공/현재 실제 합성 쿼터는 목록 GET만으로 증명 불가. **현재의 Free Tier/쿼터/Billing 상태를 실제로 확인할 수 있는 정보가 있으면 활용하되 미확인 항목을 허위 true로 기록하지 말라.**
- `companies/video/tts_execution.py`와 `companies/video/tts_cli.py` 실제 HTTP transport 및 로컬 승인 CLI 구현됨. `TTS_EXECUTION_ENABLED=False` 기본 차단. mock 기반 통합 70개 중 67통과/3skip. 이전 준비 payload `9dde86070b2cb5be7263d654cd208a6ead743e7074a76c5162e10ff0edd5bd16`.
- 관련 보고서 `reports/NO_CARD_TTS_EXECUTION_GATE_RESULT.md`, `reports/GEMINI_TTS_REAL_ONE_SHOT_RESULT.md`, `reports/NO_CARD_TTS_READINESS_RESULT.md`, `reports/CURRENT_PROGRESS.md`; 로컬 보호자료 `data/no_card_tts/20261110T151021_KST/` 및 `data/no_card_tts_execution/20261110T153342_KST/`. `AGENTS.md` 규칙 준수.
- 과거 Gemini 관리자 API 호출 1/1·준비 0/1은 이번 TTS와 별개. 기존 시도/금액/동의 원장 수정·초기화 금지. GitHub에 키/로컬 비공개 원문/미디어 업로드 금지.

## 이번에 실제 수행할 행동
1. 기존 CLI와 코드 경계를 **그대로 재사용**해 새 고립된 TTS 작업 루트 준비. 정확한 원문·payload hash·보이스·프로젝트 및 출력 경로·요청 1회/$0 범위를 검증. 새로운 provider-neutral 엔진이나 승인 준비 시스템, UI를 개발하지 않는다.
2. 기존 키가 로컬에 있는지와 키 바인딩을 비밀노출 없이 안전 확인. 모델 목록 1회 성공이라는 **실제 인증 근거**를 보고서에 인정. 필요하면 이용자 UI 또는 이미 확인 가능한 무료 계정/쿼터 근거로 TTS 1회 시도를 평가. 무료 이용 보장이 확인되지 않으면 **전송 전에 중단**. 단순 임의 계정 증거값 작성, 보안 서명 위조, 유료로 간주될 계정/서비스로 자동 전환 금지.
3. 로컬 CLI가 owner-confirmed HMAC review 확인을 요구하면, **정확한 SHA·전송 문장·Google 무료 데이터 처리·실행 1회/$0·A/B 파일 위치**를 사용자에게 간결하게 표시하고 로컬 직접 승인 작업이 필요하다고 안내. 사용자가 제공해야 하는 구체적 입력은 한 번에 보여줄 것. Codex가 사용자를 대신해 키 프롬프트나 서명 승인을 처리하지 않는다. 완료 전에 승인 없이 정지하면 그 이유와 **최소 단일 후속 행동** 보고.
4. 계정 근거와 실제 개인의 유효한 서명 승인이 모두 충족되면, TTS 전용 실행 상수의 최소한의 제한적 활성화로 **정확히 1회만** 전송. 기존 sign/attempt 영속 선예약을 이용해 전송 전 fsync 기록, timeout/4xx/5xx/비정상 응답도 전송 시도를 1회 소모; 절대 재시도·fallback 없음. 키는 HTTPS x-goog-api-key 헤더 전용; log/URL/파일/커밋에 노출 없음. 3.8 실제 wire/usage와 응답을 official specs로 재검증하고 부합하지 않을 경우 새로운 실요청 재개하지 말 것. store=false 유지.
5. 성공 시 `B_gemini.wav`와 기존 `A_reference_melo.wav` 실물 2개를 **Codespaces 로컬에 보존**, 같은 원문 SHA 검증/코덱·길이·전체 decode, 실제 생성 원장/실패 여부 및 output SHA 기록, 사용자에게 안전하게 파일 경로를 보여 주기. 품질은 사용자 청취 전 unassessed, 게시 권한 검증 전 publish_ready=false. 거짓 실물 mock 파일 출력 금지.
6. 현재 프로젝트 무료 모델 제공/지역/출력 쿼터 등을 **독립적으로 검증할 방법이 없으면 실행 중단**하되 이전까지 얻은 실제 증거와 남은 게이트를 정확히 구분. 더 이상 '어제와 동일한 준비만' 했다는 명목으로 새 코드를 추가하지 말 것.
7. 결과는 `reports/GEMINI_TTS_ACTUAL_AB_RESULT.md` 및 `reports/CURRENT_PROGRESS.md`에 기재. 실제 생성 요청 수 0/1, attempt 사용 수, 비용/무료 근거, 별도 승인 상태, 성공하면 WAV 파일 경로/크기/길이/해시 및 A/B 확인법, 실패면 확실한 중단 사유와 사용자의 **다음 작업 한 가지**를 기록. 수정한 코드/테스트/텍스트 보고서만 GitHub main 커밋·푸시. 모든 시간 KST. 기존 자산/원장/비밀을 보존하며 회귀 테스트 반복 금지.

## 종료 기준
가장 좋은 결과: **진짜 Gemini 3.8 Flash TTS 1회로 한국어 B WAV 생성 성공**. 불가피하게 근거/사용자 서명 미충족이면 전송 0회로 안전하게 멈추고 무엇이 필요한지만 구체적으로 기록한다. 절대 실행하지 않은 일을 실행했다고, 모의 WAV를 실음성이라고, 기술 테스트를 청취품질 합격이라고 보고하지 않는다.
