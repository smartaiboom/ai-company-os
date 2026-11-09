# 구현 현황 — 2026-11-09 KST

- **실제 Gemini 요청 0회 / 예약 0 / 승인 서명 0**. 실제 전송 전에 중단. 모델 `gemini-3.5-flash-lite`, 상태 `draft`, 오류 없음(키 연결·실행 승인 미충족). 실제 질문/요약/토큰 사용량은 아직 없음. 환경의 GEMINI_API_KEY 존재만 확인했으며 값·공개 지문을 출력하지 않음.
- `goal_dialogue_live.py`에 OneCallAcceptanceStore 추가: 새 mode/표식의 단일 초안, 고정 가상 목표와 빈 첫 입력만 허용, 실제 호출 예산 1회, 일반 전역 차단 유지. 질문을 허용하기 위한 논리 라운드는 2지만 후속 API 호출/추가 초안/영상 handoff 차단. 기존 저장소·동의·예산·실행 원장은 변경하지 않음.
- 사용자 비표시 로컬 키 대조 + Free/Billing 비활성 확인을 초안·키 HMAC·서명·1시간 만료로 결합. 기존 상태/입력/payload 해시 승인 재사용, scope 해시와 Google 무료 데이터 이용 동의 추가. 키 변경·미확인·서명/해시 변경·만료는 전송 차단. 환경 플래그/스크린샷만으로 해제하지 않음. 실제 전송은 별도 사용자 승인 후 해당 인수 범위만 예외이며 일반 정책은 False 유지.
- CLI `--acceptance`, `verify-acceptance-key`와 전체 요청 검토 출력 추가. 검증된 응답의 usage를 기존 시도 원장에 보존하고 실패/타임아웃/429/중단은 소모된 예약으로 유지. 키·임의 오류·원문 민감정보 기록 금지. 유료 전환·fallback·재시도 없음. README/ARCHITECTURE에 명령과 제한 기록.
- 통합 검증: `PYTHONPATH=core:companies/video python -B -m unittest discover -s tests -p 'test_*.py' -v` — **19개 통과**(기존 14 + 인수 5). 전역 False에서 모의 native HTTP 단일 요청, 질문/명세 수용·usage, 보안 입력, 승인 누락·키/서명/해시/모델 변경·만료·예산·중단·429·재요청 차단 확인. 테스트는 임시 디렉터리와 모의 HTTP만 사용하고 소켓/DNS 차단. 실제 준비도 소켓/DNS를 차단한 상태로 수행.

## 준비된 전송과 미충족 조건

- 새 로컬 저장소: `data/gemini_one_call_acceptance` (gitignored, 기존 데이터/백업/별도 보관본 미접근·미변경).
- 초안: `dialogue-f4eb35fc53a3415093e37815964f51d7`. 목표: **AI 초보자를 대상으로 ChatGPT 활용법을 소개하는 1분짜리 영상을 제작하고 싶어.**
- 전송: 위 목표 + 빈 질문/답변/명세/사용자 수정 + 첫 라운드 메타데이터 + 관리자 시스템 지시/JSON 스키마. 본문 3,405 bytes, 출력 최대 4,096 tokens, 토큰 계수 요청 없음. 개인정보·기존 이력·원장·키·로컬 경로는 본문에 없음. 키는 향후 고정 Google endpoint의 인증 헤더에만 사용.
- endpoint: `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`.
- scope 해시: `a2f6f4d21dd2003ef784b7b767e64a3411c12ae3d236cb35abcd1b22b77c7879`.
- 현재 **미승인** 검토 해시: `26b054d2c8a1da94b599e28c1288949e640208c806b64778e759d5e9e8be0396`, 만료 `2026-11-09T13:51:15+09:00`. 키 대조 후 반드시 prepare-consent 재실행 및 **새 해시** 검토/승인 필요. 현재 해시로 실행 승인되었다고 간주하지 않음.
- 전체 본문/정책: 로컬 `data/gemini_one_call_acceptance/dialogue-f4eb35fc53a3415093e37815964f51d7.review.json`. 키 대조·서명 승인·ask-ai는 이번 작업에서 수행하지 않음.
- 다음 조건: 사용자가 AI Studio의 Default Gemini Project에서 Free 등급/Billing 비활성 및 해당 키를 로컬 터미널로 대조 → 전송 내용을 재검토 → 1회/무료 전용·Google 데이터 정책·새 승인 해시에 명시 동의 → 그 이후에만 ask-ai 1회. 불명확하면 계속 중단. 실패해도 재실행 금지.
- 공식 [모델](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [가격](https://ai.google.dev/gemini-api/docs/pricing), [키/프로젝트](https://ai.google.dev/gemini-api/docs/api-key), [한도](https://ai.google.dev/gemini-api/docs/rate-limits), [데이터 정책](https://ai.google.dev/gemini-api/terms) 확인. 사용자 스크린샷의 무료 등급·RPM 15/TPM 250K/RPD 500은 사용자 제공 근거이며 잔여 쿼터/무과금 보장이 아님. 코드의 로컬 키 대조도 원격 Cloud 계정/Billing 조회를 대신하지 않으며 현재는 아직 그 대조도 미수행. Google 무료 입력·응답은 제품 개선과 사람의 검토에 사용될 수 있음.
