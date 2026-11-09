# 구현 현황 — 2026-11-09 KST

- Gemini 관리자 연결: `core/goal_dialogue_live.py`에 별도 live mode/저장소, 기존 HMAC 서명·Gemini35 wire 어댑터 재사용, 현재 상태/입력/정확한 payload 해시에 묶인 1시간·1회 전송 동의, 누적 호출 한도, 디스크 선예약, 불확실 호출 재전송 차단 구현. 이전 승인·시도 이력 보존. 기존 오프라인 저장소를 자동 승격하지 않음.
- 공통 문답 검증 재사용 및 사용자 자연어 수정/근거 추적 추가. CLI에 `--live`, `prepare-consent`, `approve-consent`, `ask-ai`, 질문별 대화 입력, 자연어 `revise --text`, 명세 표시 후 최종 확인 추가. 기존 JSON 방식과 영상 회사 handoff 유지. README/ARCHITECTURE에 실제 명령·운영 제한 기록.
- 통합 명령: `PYTHONPATH=core:companies/video python -B -m unittest discover -s tests -p 'test_*.py' -v` — **14개 통과**(기존 7개 + Gemini 경로 7개). 모의 native HTTP 요청/응답, 입력·상태·서명·만료 바인딩, 승인 누락, 고정 모델/endpoint, 답변/수정의 다음 요청 반영, 준비 완료 명세, CLI, 확정 후 영상 Store 초안 연결, 중복/예산/잠금/중단/타임아웃/잘못된 응답/비용/비밀키 차단 검증. 기존 실제 Company 계획 루프 오프라인 검증도 유지.
- 실제 AI API 호출 **0회**. 기능/테스트 외부 네트워크 **0회**(소켓/DNS 차단, HTTP는 모의 응답). 개발 중 공식 모델·가격·한도 문서 조회와 Git 동기화만 별도 수행. 테스트 저장소는 임시 디렉터리만 사용했으며 기존 프로젝트·원장·백업·별도 보관본을 변경하거나 재실행하지 않음. 영상 실행 동의 및 기존 회사 실행 엔진 계약 변경 없음.
- 공식 확인: [모델](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [가격](https://ai.google.dev/gemini-api/docs/pricing), [한도](https://ai.google.dev/gemini-api/docs/rate-limits). 문서의 모델/구조화 출력 및 무료·유료 티어 구분을 확인했지만 계정별 실제 무료 쿼터나 실시간 API 이용 가능성을 검증한 것은 아님.
- 남은 운영 검증: 계정/키의 무료 프로젝트 연결과 쿼터를 독립 검증하는 경로. 그 전까지 **실제 전송 정책 게이트는 비활성**이며 키·env·사용자 확인 플래그만으로 활성화되지 않는다. 모의 HTTP 테스트에서만 게이트를 대체했다. 실 Gemini 대화·실 영상 제작 성공을 주장하지 않는다. 기존 4,000자 handoff 입력 한도와 불확실 호출의 수동 확인 제한은 유지.
