# 무료 Gemini Developer TTS — 실제 1회 실행 경계 마무리
기준: 2026-11-10 KST

## 실행 의도
사용자 지시: **카드 없이 기존 Google AI Studio 프로젝트를 이용해 AI 영상제작 회사의 음성 직원이 자연스러운 한국어 음성 B를 만들도록 계속 진행**. 이번 단계는 기존 `companies/video/tts_job.py`의 미구현 실제 transport/승인 검증을 안전하게 구현하고 *mock HTTP*로 검증한다. 사용자에게 실제 TTS 전송 내용과 모델/현재 무료 계정 및 쿼터 확인 결과를 제시하고 명시적으로 **정확히 1회 실행 승인**을 받기 전에는 **실제 Gemini TTS API를 호출하지 말 것**. 사용자의 일반적 “진행해줘”는 실행 구현 지시이며 전송/Google 무료 데이터 정책에 대한 개별 서명 승인이 아님. API 사용 가능한 본인 계정은 Codex가 자동 추정·확인했다고 주장 금지.

## 재사용 및 규칙
`AGENTS.md`, `reports/NO_CARD_TTS_READINESS_RESULT.md`, `reports/CURRENT_PROGRESS.md`, `companies/video/tts_job.py`, `companies/video/quality_tool_adapters.py`, `core/manager_plan_once.py`, `core/goal_dialogue_live.py`, 해당 tests와 `data/no_card_tts/20261110T151021_KST/` 실제 로컬 준비물을 확인. 기존 63 tests 중 60 pass/3 skip을 유지하며 이전 실 Gemini 관리자1/1, 준비된 관리자0/1, 영상/대본/오디오/비용·사용자 승인·시도 원장, 키·데이터·기존 WAV를 보존. 기존 시스템 구조 재작성/기존 역할·스토어 재개발/UI 개발 금지. git clean/reset hard 금지, KST 사용.

## 우선 실제 wire 교차 검증
- 공식 문서(2026-11-10 기준) https://ai.google.dev/gemini-api/docs/speech-generation 와 https://ai.google.dev/gemini-api/docs/interactions-overview , https://ai.google.dev/gemini-api/docs/pricing 및 무료 데이터 이용 정책 https://ai.google.dev/gemini-api/terms 를 확인.
- Gemini 3.8 Flash TTS `POST https://generativelanguage.googleapis.com/v1beta/interactions`; TTS 원문/지속적 스타일은 `speech_metadata.style`, `speech_config`에 실제 지원 음성 이름. 공식 스키마에서 `response_format` WAV, 기본 24kHz 단일 TTS 반환과 정확한 `steps[].content` / base64·MIME 응답 형식을 확인. **현재 mock envelope를 실제 provider 형식으로 오인하지 말 것.** 특히 실제 usage 필드·강제 토큰 상한, 응답 바이트 상한이 공식 문서에서 지원되지 않으면 임의 전송 필드 추가 금지. 보수적 로컬 제한이 유료 요청 후 뒤늦게 검증되는 경우 0원 보장이라고 주장 금지.
- 공식 문서와 현재 코드 wire가 다르면 실제 코드 수정, 테스트 fixture/검토 payload hash 재생성, 기존 준비 job 원본 불변. 미해결이면 실제 전송 비활성 유지.

## 이번에 구현할 정확한 범위
1. **독립 TTS production 경계**: 기존 mock-only `TTSJob.run_mock`은 그대로 보존. 새 별도 실제 TTS provider adapter/runner, `TTS_EXECUTION_ENABLED=False` 기본값 유지. 정상 실행에 필요한 무료 계정/실 모델 제공/현재 할당량/모델·키 프로젝트 연결/청구 차단 근거와 사용자의 정확한 scope 서명 동의(프로젝트 ID, model/endpoint, payload SHA, voice, 1회, 기한, 비용 상한 0, Google 무료 데이터 처리 확인, 출력 위치)가 하나라도 없다면 fail closed. 단순 환경변수·일반 채팅 동의·예전 Gemini 서명으로 정책 해제 금지. 계정 증거를 임의 boolean 체크만으로 실제 확인했다고 주장하지 말 것.
2. TTS 직무와 실행 UI를 분리해 **터미널 CLI**로 준비/상태/키 안전 대조/서명 승인/단일 execute를 구현할 수 있으면 기존 cli 경계를 재사용한다. 정확한 고정 wire와 기간 한정 signed review, non-TTY에서는 키 공개 금지. key는 secure prompt로 local verify만 하고 github/chat/log/URL/payload에 포함 금지. 무료 현재 상태의 원격 조회 권한이 없으면 사용자 확인 게이트로 남김.
3. 한 번의 실제 전송 시도는 **요청 전에 fsync 원자적으로 영속 예약**. 성공·오류·429·timeout·중단은 모두 1회 차감, 재시도/자동 fallback 없음. redirect/proxy 차단, 도메인·모델 whitelist, 네트워크/TLS timeout, 응답 크기 상한, 키 헤더만 사용, 별도 WAV 생성/검증. 중단/불확실 시 '재시도' 금지. 작업 경로는 기존 원장/영상과 별도 경로; 외부 전송 내용은 기존 60자 가상 테스트 대본뿐. 관리 API/Flow/CapCut API로 범위 확장 금지.
4. 먼저 mock HTTP로 실제 요청 인코딩과 공식 응답 parsing, 승인·만료·payload 변경·free evidence 누락·quota/이중실행·timeout/429/overlimit/불확실 중단/권리 미확인/publish_ready=false 테스트. **실제 TTS API 0회**. 테스트 전용 WAV를 실제 B음성으로 표시 금지.
5. `reports/NO_CARD_TTS_EXECUTION_GATE_RESULT.md`에 실제 코드 완성 상태·실 API 0회·정확한 계정 확인 필요 정보·사용자가 볼 수 있는 좁은 전송 개요와 키 비공개 payload SHA/모델/음성/한도, 현재 필요한 승인/실제 호출이 **언제/어떻게** 가능해지는지, unresolved wire·quota 한계를 명시. `reports/CURRENT_PROGRESS.md` 갱신. 원 payload/code/비밀키 제외. Codex가 품질 향상을 보증하지 않으며 사람이 A/B 샘플을 들을 때만 평가.
6. 기능 묶음 구현 후 **통합 검증 한 번** (실제 호출0), 기존 사용자 파일 해시 보존 확인, 코드/테스트/보고서만 GitHub main 커밋/푸시. 원본 data, WAV, 모델, payload, API 키 및 사용자 원장은 비공개 로컬.

## 다음 결정
이번 결과를 ChatGPT가 GitHub에서 읽은 뒤, 사용자가 기존 Google AI Studio에서 Free Tier 모델/쿼터를 확인할 수 있도록 최소한의 구체적 화면/절차를 알려준다. **한 번의 정확한 실제 TTS 음성 호출 최종 동의**를 받으면 별도 1회 실행 지시서를 작성한다. 다른 API 결제·카드·가입 요구, Qwen 메모리 시험 반복, 새로운 영상 렌더/UI는 하지 않는다.

성공은 '실제 API 전송 경로가 안전하게 마련되고 남은 확인/승인이 하나씩 명확한 것'이지 '좋은 음성을 이미 만들었다'가 아니다. 준비만 반복하지 않도록 이번에는 실제 실행 코드가 없으면 미완료라고 보고하라.
