# 미션 01 — 대본 시청자 추론 오류 최소 수정 및 재발 방지
작성일: 2026-11-12 KST

## 이번 작업의 유일한 목표
**대본 완성 지연을 끝내기 위해** 마지막 실제 Gemini writer HTTP 200 대본이 `script_audience_inference_required`로 중단되는 **모델 응답/검증 계약 정합성만** 바로잡고 오프라인 확인한다. 코드/검증 완료 후 실제 실전 대본→검토→스토리보드 재개가 다음 단계다. 예산 관리·무료 등급 재설계·대규모 구조 변경·새 조사/관리자 선정·반복 진단 작업 금지.

## 실제 근거
`AGENTS.md`, `reports/VIDEO_MISSION_01_FREE_TIER_APPROVED_REAL_WRITER_RUN_RESULT_20261112.md`, `companies/video/script_quality.py`, `companies/video/quality_workflow.py`, `companies/video/video_mission_one.py` 중 해당 부분만 확인한다.
- 2026-11-12 실제 업무 `qualityprovider-a084021162134b20b0972f9b5aec343b`에서 Gemini writer **1회 HTTP200**, JSON 파싱 성공 후 `script_audience_inference_required`로 stopped. 전체 실패 원문 미보존; 어떤 세부 조건이 실패했는지 **확정할 수 없다**.
- 기존 `inspect_script`는 사용자 target_segment=`미정`일 때 `target_audience != '미정'`, unknowns 문자열의 **정확한 한글 접두사 `AI 추론(사용자 미확정):`**, 대상 문자열의 **완전한 문자 그대로 포함**, `근거:`의 문자 그대로 포함을 동시에 강제한다. 문자열 형식이 의미 검증과 결합돼 있다. 프롬프트 역시 그 구조를 지시하지만 실제 모델에선 어긋났을 가능성.
- 실제 출처 `provenance.mock/model` 계약은 이전 작업에서 시스템 지시에 고정 값으로 전달되며, 관련 검증은 보존.
- 컷룸 `company-aba553f29cfb454c8c05bad4abb49969` = research_planning. 과거 실패5개, Gemini 누적 **8**, YouTube search **2**/videos **2**, 원 조사 관측10건과 AI 관리자 선정 **25초**, evidence IDs `q0:TAidk7sXHk4`, `q0:0FVBz6iWhOY`, `q1:9YjDIwCAnsw`. 기존 실패된 대본은 재사용·성공 승격 불가.

## 수정 원칙
1. 모델에게 사용자가 시청자를 지정하지 않았다는 사실을 명확히 전달하고, 하나의 `target_audience`를 **구체적으로 제안**하면서 해당 추론의 이유/불확실성을 `unknowns`에 기록하도록 한국어/간결한 예시를 제공한다. **사용자가 이미 지정한 시청자 입력은 정확 일치 검증 유지**.
2. 현행 언어 표현의 **글자 단위 완전 일치** 때문에 충분히 명시된 타당한 추론을 거절하지 않도록, `target_audience`가 비어있거나 `미정`이 아닌지를 엄격히 검사하고, unknowns에 **사용자 미확정 AI 제안임을 분명히 알리는 표현 + 비어 있지 않은 실제 이유**가 있는지를 의미 보존형으로 최소 검증한다. 지나치게 폭넓은 무조건 통과·unknowns 비어 있음 허용·근거 없이 추론 처리 금지. 기존 고정 접두사 사례도 통과해야 한다. 모델이 정확한 스키마를 지키도록 유도하는 것이 우선이며 필요하다면 계약 변경 범위를 더 좁게 선택한다.
3. 검증 실패 시 안전한 **세부 실패 항목**(예: literal_unspecified_audience, inference_marker_missing, audience_reference_mismatch, reason_missing)만 식별해서 기존 attempt의 진단 구조에 저장하도록 한다. 이는 사용자 개인 정보/응답 원문/대상 문자열/비밀키를 남기지 않는 boolean·enum 중심 진단이며 실제 응답을 대신 생성하거나 정정하지 않는다. 모든 실패는 이전과 같이 stopped 처리하고 자동 재시도 없음.
4. 관리자 선정 주제·25초, 고정 모델/실제 mock provenance, narrated beats/transcript, 근거·권리 검증, 보고서 출처/승인·실패 원장, 실제 제공자 응답과 offline fixture 구분은 유지. 대본 자체를 검증 없이 통과시키거나 모델 응답을 무음으로 수정 금지.
5. **오프라인만**: 한국어 형태가 다른 타당한 시청자 추론/근거 통과, literal `미정`, AI 미확정 표기 누락, 이유 누락, 사용자 지정 시청자 불일치, 잘못된 출처/25초 주제 변조 거부, 실패 시 진단 세부 코드/원문 미노출, 자동 재호출0, 임시 컷룸 대표 승인 대기 연결의 명시적 합성 fixture를 검증. 한 번의 관련 테스트 묶음으로 제한. 네트워크/DNS 차단, 실제 Gemini/YouTube/API 0회.
6. **실사용 새 successor 생성/실제 grant·실행 0건**. 기존 5개 stopped 업무 및 원 서명·사용량·active_operation, data/, backups/, artifacts/, .env, 키·음성/영상·미추적 파일 보존. 새 실전 실행은 별도 명시 승인으로만 진행.
7. 성패와 관계없이 `reports/VIDEO_MISSION_01_AUDIENCE_CONTRACT_MINIMAL_FIX_RESULT_20261112.md` GitHub 저장·commit/push. 정확한 변경·테스트·실제 호출0·과거 기록 보존·남은 실행 필요 절차만 간략 보고. 최소 코드 수정 외 다른 업무 금지.

KST(UTC+9). git clean/reset --hard/force push 금지. **프로젝트의 최종 목표인 실제 대본과 스토리보드, 대표 승인 대기를 지연시키는 다른 개발을 시작하지 말 것.**
