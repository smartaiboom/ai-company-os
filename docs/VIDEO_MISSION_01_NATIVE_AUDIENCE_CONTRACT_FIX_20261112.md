# 미션 01 — 실제 native writer 대상 시청자 미정 혼동 최소 해결
작성일: 2026-11-12 KST

## 최우선 목표
실제 `result.content` 객체형 구조화 응답은 Gemini에서 **HTTP200으로 수용**되었다. 그러나 마지막 8번째 stopped 업무 `qualityprovider-3cfbbaec56d746799703489fe889a727` writer가 `target_audience`에 실질적으로 `미정`을 반환하여 `script_audience_inference_required / literal_unspecified_audience`에서 중단됐다. 이 **하나의 계약 공백**만 보완해 실전 대본을 완성하는 길을 연다. **예산/UI/새 연구/일반 프레임워크/다른 오류 개발 금지.**

## 확인된 실전/코드 근거
- `AGENTS.md`, `reports/VIDEO_MISSION_01_APPROVED_UNIFIED_SUCCESSOR_REAL_RUN_RESULT_20261112.md` 확인.
- `companies/video/script_quality.py`: 현재 `writer_contract(audience='미정')`가 `target_audience`를 `minLength:1` 문자열로만 제한하고, 의미 검사 `audience_inference_issue`에서 `미정`을 거부한다. 기존 `AUDIENCE_INSTRUCTIONS`도 미정 복사 금지를 설명하지만 실제 모델은 이를 준수하지 않았다.
- 새 writer native schema는 `video_mission_one.py`의 `generationConfig.responseJsonSchema`, 요청 body `output_contract`, `data.quality.writer_contract`에 일치해서 전달되고 전송 전 해시 검증한다. 기존 서버 검증은 그대로 신뢰한다.
- 과거 **8개 stopped** 원장/동의/서명/active_operation/응답 해시 불변. 누적 Gemini **11**, YouTube search **2**, videos **2**. 원 컷룸 `company-aba553f29cfb454c8c05bad4abb49969` = `research_planning`; 원 조사10건·관리자 롤토체스/모바일 퍼즐 소재 선정25초와 연결 해시는 원본 그대로.

## 이번 Codex 작업
1. 시청자 입력 `target_segment='미정'`(사용자가 정의하지 않음)과 직원 출력 `target_audience`(AI가 구체적으로 제안해야 함)를 시스템 지시 및 native 스키마에서 **명확히 구별**. `target_audience`의 스키마가 literal `미정`을 허용하지 않도록 가능한 구조 제약을 **기존 Gemini가 실제 수용한 schema 문법 안에서** 넣는다. 지원이 확실치 않은 `not`, `pattern` 등 새로운 JSON Schema 키를 추측해 추가해서 실제 전송 실패를 만들지 말 것. 안전한 schema 문법으로 불가능하면 경로를 확장하지 말고 상세하고 짧은 description와 구조화된 예시, `unknowns`의 의도 명확화 및 서버 검사 유지로 해결한다. 특정 시청자를 개발자가 고정/하드코딩하지 않는다.
2. 프롬프트에 `미정`을 사용자 미입력 상태로만 보고, output `target_audience`에는 **관리자가 고른 주제와 관측에 근거해 구체적인 대상 하나를 제안**해야 하며 `unknowns` 한 항목에 `AI 제안(사용자 미확정)`, 해당 대상, 비어 있지 않은 이유를 쓰라는 짧은 한국어 지시를 명시. 예시는 형식/placeholder일 뿐 실제 대상/게임을 대신 고르지 않는다. 사용자 명시 target_segment의 정확 일치 검증 유지.
3. 기존 `writer_contract`의 version 또는 계약 객체/설명 변경이 **실제 writer_contract_hash**를 변경하게 해, 공통 `unified_successor_reference`의 '계약 변경이 없는 동일 후속 자동 재생성 금지' 규칙과 정합을 맞춘다. **중복 방지/서명·원장/검사 우회 금지**. 이전 실제 계약 hash `8d0ff0d818b0f7dfee18c13b506801b00ba588b14d9a45b173e497b6d540672f`는 과거 사실로 보존하고, 새 계약 hash는 실제 함수로 계산·검증할 것. 기존 역사 reference 검증과 충돌이 있으면 과거 contract version으로 history hash를 확인하되, 예전 서명/원장 바이트를 수정하지 않는다.
4. 검사 실패에 `literal_unspecified_audience` detail_code, 응답 hash 등은 기존 안전 진단 유지. 실제 Gemini가 또 `미정`을 반환해도 승인된 대본으로 자동 수정/수락하지 말 것. 모델 출처/제목 정확 복사, 25초·shot_type/source_status/fact_status/장면 연속성·transcript·권리/사실 불확실성·관리자 검토 모두 유지.
5. **최소 표적 오프라인 시험 한 번**: 실제 전송 payload의 schema/context/system 지시에서 input과 output audience 구분, 새 계약 hash 변경, 미정 반환 거부/타당한 AI 미확정 제안+근거 허용, 명시적 사용자 시청자 exact match, 과거 signed chain 및 원장 보존, 기존 common successor가 **변경된 계약 아래에서만** 안전한 미래 후속을 인정함, 합성 writer→manager→editor→manager→임시 컷룸 대표 승인 대기. Gemini API/YouTube/DNS 외부 네트워크 **0회**.
6. 실제 stopped 8개/컷룸/data/backups/artifacts/.env/키/미추적/미디어 불변. 실제 new job/grant/동의/전송 **0건**. 유료 전환/모델 변경/구 승인 재사용/자동 retry/사용량 초기화 금지.
7. 성공·실패 모두 `reports/VIDEO_MISSION_01_NATIVE_AUDIENCE_CONTRACT_FIX_RESULT_20261112.md` 작성 후 GitHub commit/push 및 main에서 읽힘 확인하고 중단. 실제 새 계약/요청 전송 위치/해시, 테스트 수·실 API0회/누적11, 실제 대본·스토리보드 미완료 상태, 다음 **실제 제작 재개**의 최소 한 단계만 기록. 원문/키/대상 개인정보 복제 금지.

이 작업은 실제 호출에 대한 기존 사용자 승인 범위를 넘겨 추정하지 않는다. **이번은 오프라인 수정만**, 이어지는 실전은 별도 대표 승인 아래 수행. 시간 KST. git clean/reset --hard/force push 금지.
