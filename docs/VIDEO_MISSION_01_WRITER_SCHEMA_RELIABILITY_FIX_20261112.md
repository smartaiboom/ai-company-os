# 미션 01 — writer 전체 스키마 신뢰성 개선과 반복 중단 구조 해소
작성일: 2026-11-12 KST

## 이번 작업의 목표 — 더 이상 필드 하나씩 고치며 1회 호출 중단 반복하지 않기
실제 Gemini는 지난 수차례 HTTP200 및 JSON 파싱에 성공했지만 provenance, audience, topic.title, 이번에는 `invalid_script_shot` 등 **서로 다른 writer 계약 검증 하나씩** 실패하여 7개 업무가 stopped됐다. 목표는 임의의 검사 완화가 아닌, **AI에게 유효한 스키마를 일관되고 명확하게 전달하고, 실제 전송 전 계약 확인 및 실패 후 필드 단위 안전 진단을 갖추는 최소 구조 개선**이다. 다음 실전 제작을 위한 마지막 오프라인 준비를 우선하며, 더 많은 무관한 기능 개발 금지.

## 확인된 마지막 실전 사실
- `reports/VIDEO_MISSION_01_APPROVED_TOPIC_SUCCESSOR_REAL_RUN_RESULT_20261112.md`: 2026-11-12 10:08 KST 마지막 stopped `qualityprovider-95e2b74978f24b4690368a8bf10ae72a`, 실제 Gemini writer HTTP200/json_parsed 1회, `invalid_script_shot` 발생. `narrative_beats[*].shot_type`은 정확히 `demo|detail|card` 중 하나여야 한다. 원문 응답이 저장되지 않아 어떤 값인지 불명. 선정 주제 검사 통과 여부도 아직 모름.
- 과거 **7개 stopped** 전부 읽기 전용 불변, Gemini 누적 **10회**, YouTube search2/videos2. 컷룸 `company-aba553f29cfb454c8c05bad4abb49969` `research_planning`. 성공한 실제 대본/스토리보드 카드 없음.
- 실제 계획·수락된 조사10건과 AI 관리자 롤토체스/모바일 퍼즐 소재 선정·25초·원 해시·원 무료 Google 계정/모델 바인딩 그대로. 목표 재선정 불가.

## Codex 작업 (API 없이 한 번에)
1. `AGENTS.md`, 해당 실전 보고, `companies/video/script_quality.py`, `companies/video/quality_workflow.py`, `companies/video/video_mission_one.py`의 writer systemInstruction·context·role JSON/schema·검사 경로와 관련 테스트 **만** 확인. 실제 모델 응답 원문을 추정하지 말 것.
2. **구조화된 실제 writer 산출물의 스키마 요구를 명확하게 단일 원천화**: `shot_type: demo|detail|card`, `source_status: pending` (이 미션 영상 소스 미확인), `fact_status: illustrative|verification_pending`, topic.title=관리자 고정 selected_topic 정확 복사, 25초/0–3초/연속 장면/대본 transcript·hook 일치, 미정 audience의 구체적 AI 제안·미확정 근거, provenance.model/mock, 기타 기존 required 필드 등 **현재 inspect_script가 실제 검사하는 모든 하드 에러**를 전송 시스템 지시와 가능한 구조화 응답 schema가 모순 없이 강제하도록 한다. 이미 전달된 일반 SCRIPT_INSTRUCTIONS 문구만 중복 덧붙이는 것이 아니라, **실제 모델에 보내는 요청의 어느 필드에 지침이 있는지** 테스트로 확인.
3. **서버 사실과 모델 창작 분리**. provenance.model/mock 등 서버 고정 사실을 LLM에 정확하게 주고 원장과 비교하되 실제 호출을 mock으로 위장하거나 산출물 원문을 무음 변경 금지. 선정 topic.title, length, 원 evidence도 시스템적으로 인계하되 관리자 선정 권한 및 수락 조건 유지. '주제 제목'과 '시청자에게 보여줄 흥미로운 문구'는 분리.
4. 안전 진단을 writer 전반의 hard validation errors에 공통으로 제공: 최소한 `invalid_script_shot`에서 `stage`, `category`, 첫 실패 beat 인덱스, 허용 집합 매치 여부, 타입/길이(안전한 경우), 응답 hash 등만 기록. 다른 오류도 가능하면 공통 `error_code/field_path`를 통해 **어느 필드가 문제인지 최소 정보로** 알 수 있게 하되 원본 응답 전문/시청자 값/키/프롬프트 비밀정보를 기록하지 말 것. 현재 실패7번째는 소급 조작하지 말고 새 업무에서만 진단. 보안상 안전하면 수신 응답의 암호화/권한 제한된 별도 진단 보관 가능성은 설계 메모만; 범위 커지면 구현 금지.
5. 중요: **반복되는 신규 사유별 successor CLI 증가를 멈출 수 있는지** 현재 stopped/서명·source chain을 검증하는 범용 안전한 새 successor 설계의 최소 변경안을 작성한다. 이미 서명된 과거 업무/시도 변경·replay·계정 바인딩 우회 없이 새 후속을 만들어야 한다. 다만 이 작업에서 새 실제 successor 생성·새 실사용 운영 동의는 하지 않는다. 범용 코드 구현이 과도하면 **최소 제안만 결과 보고서에 기록**하고 영상 제작 자체를 지연시키지 말 것.
6. **필요한 표적 오프라인 테스트 한 묶음**: 유효하지 않은 shot_type(예: 허용하지 않은 단어)은 여전히 reject + 안전 진단, valid 허용 세 값 수락, 잘못된 source_status/fact_status/title/provenance/audience/장면 timeline 거부, 미정 audience·25초/선정 주제 정확 복사·원 검증된 web 보존, 합성 writer→manager review→editor→manager review→임시 컷룸 awaiting_plan_approval. 수정 범위를 넘어 다른 모든 테스트 반복하지 않는다. fixture는 실제 AI가 작성한 대본이 아니라고 명확히 표현.
7. **이번 작업에서는 실제 Gemini/YouTube/기타 provider 호출0회, 실제 새 successor/grant/승인 0건**. 과거7개 stopped 업무/서명/원장·누적 Gemini10, YouTube2/2·컷룸·data/backups/artifacts/.env/사용자 키·미디어·미추적 파일 보존. 무료 호출 임의 숫자 상한을 재도입하지 않고 유료 전환·fallback·자동 재시도·무의미한 재조사 금지.
8. **결과 무조건 GitHub**: `reports/VIDEO_MISSION_01_WRITER_SCHEMA_RELIABILITY_FIX_RESULT_20261112.md`에 변경·검증/test결과, 왜 이전 오류가 재발할 수 있었는지 확정가능 범위, 해당 단계 전송 계약 확인, 실 API0/누적10, 기존7개 불변, 다음 **실제 AI 제작**으로 넘어갈 최소 행동 1개만 기록. commit/push/원격 main 확인 후 중단.

KST. git clean/reset --hard/force push 금지.
