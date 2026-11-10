# 카드 없는 자연스러운 한국어 TTS — Gemini Developer API 우선 검증
작성: 2026-11-10 KST
**실제 실행형 개발 지시. 문서 열람만 하고 종료하지 말 것.**

## 사용자가 승인한 목표/금지사항
사용자는 현재 카드가 없어 **Google Cloud Billing 필수 Chirp3-HD**는 보류하고, 카드 없이 무료로 시작할 수 있으며 **영상제작 회사의 음성 AI 직원이 직접 API 호출**할 수 있는 고품질 한국어 TTS를 찾는 데 동의했다. 품질 기준은 이전에 사용한 CapCut의 자연스럽고 친근한 TTS 정도. CapCut 목소리/성우 복제 금지. 기존 MeloTTS는 실제 청취에서 어색하고 Qwen 0.6B는 Codespaces 가용 RAM 3.89GB로 실행 안전 게이트에 실패함. 동일 로컬 모델 재설치·사람이 직접 CapCut 음성 제작/업로드 방식 반복 금지.

**이 작업의 외부 TTS API 실제 호출은 아직 개별 승인되지 않았다.** 이번 묶음에서 정확한 무료 제공/키/모델/입력 payload 검토, transport 안전 코드 및 오프라인 mocked 테스트까지 수행한다. Google 계정/키/Free Tier 확인과 전송 검토 뒤 사용자가 1회 실행을 구체적으로 승인하기 전에는 **실제 요청 0회, 비용 0원, 계정 설정/과금 변경 0회**. 키 존재나 과거 Gemini plan 1/1 동의/서명이 TTS 실행 동의는 아니다.

## 핵심 발견: 서로 다른 Google 제품을 혼동하지 말 것
- **Google Cloud Text-to-Speech의 Chirp3-HD**: Cloud Billing 필수이므로 지금 보류. https://cloud.google.com/text-to-speech/pricing
- **Gemini Developer API / Google AI Studio TTS**: 공식 가격표에서 STANDARD **Free Tier 입력·출력 무료**로 표시된 TTS 모델이 있음. 기존 Gemini Developer API 키 사용 가능성과 모델별 현재 무료 쿼터/계정 권한은 별도 확인. 기존 사용자 Cloud Billing 카드 등록을 요구하지 말 것.
- 우선 모델: 공식 최신 문서상 **gemini-3.8-flash-tts**, 더 가벼운 **gemini-3.8-flash-lite-tts**. 둘 다 Free Tier 표시. 전자는 음성 충실도/연기 강조, 후자는 저지연/효율 강조. 한국어 자동 감지 지원. 실제 요청 전 현재 해당 모델이 프로젝트 Free Tier에 실제로 보이는지, quota 잔여/지원 지역/정확 endpoint와 SDK 입력 스키마/모델 정책 검증. 불가능하면 공식 Free Tier의 **gemini-2.5-flash-preview-tts**(품질은 샘플 청취 전 미검증)를 2순위로 검토하되 자동 fallback/재시도 금지.
- 공식 모델 가격 https://ai.google.dev/gemini-api/docs/pricing
- 공식 TTS 생성/voice/한국어 지원 https://ai.google.dev/gemini-api/docs/speech-generation
- 공식 모델 목록 https://ai.google.dev/gemini-api/docs/models
- 무료 서비스 데이터 입력/출력은 Google 모델 개선/인적 검토에 사용될 수 있으므로 **가상 테스트 대본만 전송**, 사용자 실제 원장/개인정보/회사 자료/기존 미디어 절대 전송 금지. https://ai.google.dev/gemini-api/terms
- 보조 후보: **Fish Audio API s2.1-pro-free** 공식 개발자 요금 0 USD/백만 UTF-8 바이트 및 별도 subscription 필요 없는 API라고 명시하지만, 웹 Free 요금표에서는 무료 사용자 **비상업적 사용만** 명시하며 상업 권리와 API 모델의 정책이 일치하는지 확인해야 함. API 이용에 카드/크레딧이 반드시 필요한지 명확하지 않으면 미확인으로 두고 게시용 1순위로 선정 금지. https://fish.audio/plan/ 및 https://github.com/fishaudio/docs/blob/main/developer-guide/models-pricing/pricing-and-rate-limits.mdx
- ElevenLabs 무료 API/한국어/상업권/카드 여부는 보조 후보로 비교, 무료 비상업 또는 앱 전용 기능과 회사가 직접 호출 가능한 API를 혼동하지 않는다. 유료 가입·카드·결제·크레딧 충전 안 함.

## 사전 확인
AGENTS.md, reports/VIDEO_COMPANY_QUALITY_AND_TOOL_DECISION.md, reports/QWEN_TTS_AB_RESULT.md, reports/CURRENT_PROGRESS.md, reports/USER_FEEDBACK_QUALITY_UPGRADE_RESULT.md, core/의 기존 Gemini35Adapter/goal_dialogue_live, manager_plan_once 및 영상 도메인의 quality_tool_adapters.py, audio/quality 비교 코드, tests를 읽는다. 기존 코드 재사용. 기존 실제 Gemini 인수1/1, 새 manager 0/1, 모든 사용량/승인/비용 원장, Flow 클립/기존 WAV/MP4/모델/.env/백업 보존. git clean/reset hard 금지. KST.

## 이번 실제 개발 업무
1. **카드 없는 API 선택 근거**: 3.8 Flash TTS/3.8 Flash-Lite TTS/2.5 Flash Preview TTS + Fish s2.1-pro-free + ElevenLabs의 무료·카드·상업권·자동 API·한국어 지원·품질 미평가를 비교하는 실제 출처/조회일 표. Gemini Developer API와 Google Cloud TTS의 결제 요구를 명확히 구분한다. 최신 모델의 실제 제공 여부는 계정/키 없이 확인 불가능하면 정확히 미확인 처리.
2. 기존 A_reference_melo.wav와 해당 정확 원문을 입력으로 하여 하나의 무료 TTS 샘플 B에 필요한 모델/보이스/음성 생성 style prompt(친근한 한국어 직장인 쇼츠 안내, 또박또박·경쾌한 자연스러운 대화체, 과장·성우 복제 없음), 동일 발화문, 출력형식/해시, 토큰/출력 길이 상한, 전송 본문을 준비. 기존 A 보존. 실제 사용자 자료는 보내지 않으며 예시가 가상인지 점검.
3. 영상회사의 기존 음성 직원 계약에 **provider-neutral TTS job** 최소 통합: 사전 승인 범위 검증, 명시된 provider/model/endpoint/voice/정확 payload 해시, API 요청 1회/실패 포함 소모, 영속 선예약 및 중단 후 재시도 차단, 무료 계정/잔여 할당량 증거 부족 시 fail-closed, 원시 응답/인증키 노출 차단, 결과 WAV 안전 저장/해시·ffprobe·전체 decode, 사용자 A/B 청취결과 수신 전 품질 unassessed. 현재 코드에 없는 실제 전송은 **별도 상수 비활성**에서만 구현하거나 테스트 전용 transport 주입으로 검증. 기존 Gemini 관리 전송/승인 게이트 약화 금지.
4. 새 테스트 전용 isolated project와 mock HTTP/TTS envelope를 이용해 요청 구성·응답 디코딩·과금/쿼터/한도·비활성 차단·중복/timeout/실패/재시도 없음·오디오 파일 해시/코덱 및 기존 A/B 텍스트 일치 검증. **실제 Gemini TTS 호출/미디어 업로드 0회**. 제품 기능 한 묶음 마지막 통합 회귀 한 번. 메모리 부족 Qwen을 재시도하지 말 것.
5. 새 로컬 보호 경로에 payload exact bytes/read-only 검토/해시/가상 테스트 대본, mock WAV 샘플이 있다면 mock 표시, 호출 전 요구 계정 증거 및 최종 좁은 실행 승인 필요 항목을 저장. TTS 사용권/생성물의 상업적 사용 조건이 명확하지 않으면 publish_ready=false 유지.
6. **reports/NO_CARD_TTS_READINESS_RESULT.md** 작성: 표준 Gemini Developer API Free TTS vs Cloud Billing 구분, 공식 출처, 우선 후보 1개와 보조 1개, 기존 Gemini 키로 가능한지/무료 할당량 잔여/현재 계정 상태의 미확인, 실제 구현된 코드·mock 테스트·잔여 단계, **사용자가 다음에 할 정확히 1가지 최소 확인** 및 완전히 분리된 음성 1회 실행 승인, 출처·권리·비용 0·외부호출0·기존 원장 보존, A/B 다운로드 경로(실재할 때만). reports/CURRENT_PROGRESS.md 갱신.
7. GitHub에 실제 코드·테스트·텍스트 보고서만 커밋/푸시. 원문 payload나 키/미디어/모델/기존 data는 푸시하지 말 것. GUI/화면 작업, 새 60초 영상 강제 렌더, Google Cloud Billing/card/유료 API 연결 금지.

## 완료 판정
목표는 **영상제작 회사 음성 AI 직원이 카드를 요구하지 않는 무료 API를 직접 선택·호출할 수 있도록 안전한 경로를 실질적으로 구축**하고, 다음 차례에 사용자에게 계정·1회 실행만 좁게 요청하는 것. 이번에는 무료 API의 실제 한국어 자연스러움이 개선됐다는 주장을 하지 않는다. 종전 모의 협업 전체 구조를 다시 만들지 말고 지금 부족한 경계에 투자. 코드 미구현이면 완료라 주장하지 않는다.
