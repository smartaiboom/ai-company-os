# 영상회사 음성 품질 실험: 승인된 무료 Gemini TTS 1회 실제 생성 — 실행 막힘 해소
작성: 2026-11-10 KST

## 이 문서의 성격
**코드 수정·실제 실행·결과 보고 지시서다. 조사/준비/승인 요구서만 작성하고 끝내지 마라.**
사용자는 동일한 가상 60자 한국어 대본을 기존 Google AI Studio API 키로 **Gemini 3.8 Flash TTS/Puck 1회 무료 시험**하도록 여러 차례 분명하게 동의했으며, 최근에도 진행을 명시 지시했다. 카드가 없으며 유료 전환, Billing 활성화, 비용 지출은 허용하지 않았다. 무료 Gemini API의 데이터 개선/인적 검토 가능성을 안내받았다. 본 문서는 사용자의 해당 범위에 대한 *대화상 승인*을 실행 근거로 삼는다. **Codex가 허위 사용자 서명이나 계정 증거를 작성하는 것은 금지**한다.

## 확인된 실제 근거 (다시 확인한 셈 치지 말고 재사용)
- 화면 확인: Default Gemini Project, 무료 등급, 기존 API 키. Google Cloud 결제 카드 없음.
- `reports/GEMINI_TTS_MODEL_LIST_CHECK_RESULT.md`: 현 GEMINI_API_KEY로 `GET /v1beta/models` **실제 HTTP 200**, 전체 61개 모델 중 `models/gemini-3.8-flash-tts` 포함. 이 모델 목록은 **가용 잔여 TTS 쿼터 증명 아님**. 재조회 필요 없음.
- `reports/GEMINI_TTS_ACTUAL_AB_RESULT.md`: 새 로컬 프로젝트 바인딩 준비됨, payload SHA256 `9dde86070b2cb5be7263d654cd208a6ead743e7074a76c5162e10ff0edd5bd16`; 실 TTS 호출/예약0, B파일 없음. 루트 `/workspaces/ai-company-os/data/gemini_tts_actual_ab/20261110T160649_KST/`.
- `companies/video/tts_execution.py`, `companies/video/tts_cli.py` 실제 HTTPS transport·사용량 decode·WAV 검증 및 attempt exclusive fsync 기능 구현됨. `TTS_EXECUTION_ENABLED=False`가 현재 실행을 차단. `verify_key`의 `remaining_requests/input/output_tokens` 구체 숫자/지역 등은 AI Studio 화면에서 **직접 관찰할 수 없는 경우가 있음**. 사용자가 볼 수 없는 값을 추측/창작하는 건 금지.
- AGENTS.md, 위 보고서, reports/CURRENT_PROGRESS.md, 기 존재한 단위 테스트 읽고 존중. 기존 관리자 API 1/1 및 ledger, 원 사용자 미디어/코드/키/백업 보존.

## 핵심 수정 방침 — 확인 불가 증거를 무리하게 요구한 게이트의 문제 해결
- 기존 운영 일반 승인·서명 체계를 전역적으로 해제하지 말 것. 그 대신 **오직 이번 TTS 가상60자/특정 hash/특정 프로젝트/특정 모델/단일1회/무료 비과금**에만 유효한 좁은 *user_chat_approved_single_free_tts_trial* 실행 정책을 구현하거나 기존 경계를 최소로 확장하라.
- 실물 실행 조건: 현재 환경의 기존 API 키, 모델 목록 조회 성공 증거, 사용자 화면에서 무료 계정, 결제 Billing 연결되지 않은 상태와 무과금 정책; 정확 payload sha와 모델·보이스 매칭; 독립된 one-shot attempt 선예약; 실제 사용자 대화 승인 범위를 `consent_source='explicit_chat_user_approval_2026-11-10'`로 진실하게 기록. **`consent.json`에 owner-confirmed/HMAC 직접 서명했다고 가장하지 말라.** 대화상 승인과 CLI 서명은 별개의 유형으로 관리하고 scope를 제한.
- TTS 잔여 요청/토큰의 실숫자가 UI에서 제공되지 않는 경우 **정확 수치 없이 사용자 Free Tier 관찰 + 제공모델 GET200만으로 '1회 제한의 무료 실험 조건이 수용 가능한지' 정책 결정**할 수 있게 하라. 이를 '공급자가 잔여 쿼터를 보장한다'로 표기하지 마라. 초과하면 HTTP429 등의 실패가 날 수 있다. 어떠한 경우에도 결제계정 설정/자동유료전환/새 유료 API를 사용하지 않는다.
- 무료 결제 상태를 공개 UI로만 확인했다면 그 근거는 `owner_screenshot_free_tier`로 기재하고 **independently_verified=false** 명시. 결제계정이 활성화되었다는 증거가 있으면 **절대 요청하지 말 것**. 사용자 카드가 없으므로 무료 프로젝트에서 1회 시도하는 것이 목표이나 실제 공급자 측 과금0을 독립 보증하지 못한다는 점도 정직히 남겨라.
- 실행 정책을 별도로 변경하는 경우 기존 `run_mock`, 정상적인 signed flow, manager gates, 비용원장, 다른 모델/스크립트/프로젝트로 확장되지 않도록 단위 테스트. 테스트 확인을 핑계로 실제 API를 여러 번 호출하지 않는다. 최종 생성을 위한 API **딱 1회**, 실패도 소모, 재시도/fallback 금지. 모델 목록 추가 호출 불필요.
- Codex가 실제로 키를 갖고 있고 사용자가 chat으로 해당 scoped 요청에 명시 동의한 이상 **사용자에게 동일한 것만 또 승인하라고 되풀이하는 지시를 쓰지 말 것**. 범위/출력/원문이 바뀌어 새 승인 필요할 때만 중지. 단 기존 보안정책/AGENTS.md가 기술적으로 로컬 실제 개인 서명을 **필수 불변**으로 규정하면 그 정책을 우회하지 말고 정확한 사용자 로컬 명령 1개로 마무리하도록 하라. 허위 승인·키노출·근거창작 금지.
- 실사용 전에 정확 요청의 API endpoint/공식 wire 확인. 공식 스키마가 달라졌다 해도 payload를 변경하면 원 사용 승인 범위를 벗어나므로 조용히 변경해 호출하지 말고 필요한 새 승인사항을 보고하라. 응답을 받을 때에는 raw response 공개/키 저장 금지. 별도 보호폴더에서 `B_gemini.wav` 실제 생성, WAV 길이/코덱/해시/전체 디코딩 검증. 음성 기술상 검증과 사용자 자연스러움 평가는 별개.
- 실행 중 네트워크/호스트 인증·quota·permission 오류가 나면 **1회 사용 소진 후 정지**. 400 API 스키마 오류도 재호출 금지. 결과 보고서에 정제된 HTTP 상태/에러 범주만.
- 실행 코드 게이트 활성화는 이번 한정 runnable operation 경로 내부에서만. `TTS_EXECUTION_ENABLED=True`를 저장소 전역의 기본값으로 배포하지 말고 기본 False 유지. key·비밀·유료정보 로그 금지.

## 실제로 반드시 수행할 일
1. 기존 스펙과 CLI/실행코드/결제·동의 정책을 확인하고, **불필요한 수치 강제·대화 동의 반복 문제를 최소 수정**. 이미 존재하는 코드 재사용. 사용자에게 또 명령과 긴 계정증거 JSON 작성을 맡기지 않는다.
2. 새 one-shot 로컬 승인/시도 작업을 유일한 isolated root에 생성하고, 정확 payload SHA `9dde86070b2cb5be7263d654cd208a6ead743e7074a76c5162e10ff0edd5bd16` 및 기존 A 경로 SHA 검증. 한 요청 영속 예약 전에 모든 키/무료상태/승인증거를 점검. 다른 기존 root의 실음성 attempt가 있는지 확인하고 **전체 TTS 작업에 대한 중복 실호출 위험**이 있으면 차단.
3. 코드/테스트 수정→mock HTTP로 회귀 확인 **한 묶음**; 사용자 승인 범위와 계정 무료 증거가 충족되면 **실제 TTS 1회** 호출. 다른 유료/개인 입력은 전송 금지. 호출 전 약관·정확 payload가 승인 범위와 동일한지 확인.
4. 실성공 시 `B_gemini.wav` 및 기존 `A_reference_melo.wav` 실경로, 길이·SHA·파일 크기·ffprobe/ffmpeg 검사, 음성을 듣는 방법을 보고. 물리적으로 ChatGPT에 WAV를 첨부하지 못한다면 Codespaces 파일 경로를 사용자에게 알려라.
5. `reports/GEMINI_TTS_ONE_SHOT_UNBLOCK_RESULT.md`와 `reports/CURRENT_PROGRESS.md` 갱신: 실제 호출 0/1, 사전예약 상태, 사용자 승인 **provenance(채팅 승인 vs CLI 서명)**, 계정 증거 수준, 결과 WAV 여부, 한도/비용/에러 분류, 다음 할 일 하나. 코드/테스트/보고서만 GitHub main push. 기존 미디어·개인 키·로컬 증거·원장 보존.
6. **결과가 또 0회일 경우**, 기술적으로 또는 정책상 더는 자동 진행할 수 없는 *정확히 하나의 마지막 장애물*을 제시하고, 그 장애물이 해소되지 않는 한 유사한 준비 문서나 반복 게이트를 생성하지 않는다고 명시. 중단했다면 어느 if/조건/코드 지점인지와 구체적 해결방법 기록.

## 금지 사항
실사용 전 결제 카드 요청/활성화/유료전환, 무단 무료계정 추정 기록, 허위 quota숫자/인적서명, API 자동 retry/fallback, 실제 Gemini TTS 요청 2회 이상, 다른 계정/키/모델로 우회, 기존 코드·미디어 삭제/원장 reset, 수동 CapCut 음성 제작을 사용자에게 전가, manager/직원 일반 구조 재개발, UI/60초 영상 렌더, 품질 향상 확정 주장.

## 최종 검증
이번 사용자 요구는 **결과물 품질 개선**이다. 본 지시서는 마지막 안전한 실행 장애를 해결해 **실제 한국어 B 음성을 듣는 것**이 목적이다. 실패하면 기술/서비스 측 한계를 하나로 정확히 압축해 보고하고 더 이상 같은 준비 사이클을 반복하지 않는다.
