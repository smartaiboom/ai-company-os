# 미션 01 — 시청자 추론 계약 최소 수정 결과

2026-11-12T09:43:39.559793+09:00 (KST). 최신 main `f529d70`·AGENTS.md·지정 지시서·직전 실제 실행 보고를 확인했다. 실제 실패 대본 원문은 없어 당시 실패 세부 조건은 여전히 확정할 수 없다. 이번 수정은 실전 실패의 소급 복구/성공 승격이 아니다.

## 변경

- `script_quality.py`: 사용자가 시청자를 정하지 않았다는 점을 한국어로 명시하고, unknowns에 제안 대상·AI 제안/사용자 미확정·추론 이유를 한 항목으로 쓰는 짧은 placeholder 예시를 제공했다. 특정 게임/시청자 답안을 주입하지 않는다.
- 정확한 고정 접두사·문자열 원문 포함·`근거:`만 허용하던 검사를, 제한된 명시 표현 검사로 바꿨다. 같은 unknowns 항목에서 AI 추론/제안/추천/가정 + 사용자 미확정/확인 전/미지정 등 명시 표현, 제안 대상 참조, 이유/근거 설명을 모두 요구한다. 공백·문장부호·유니코드 표기 차이는 정규화해 비교하되 산출물 자체를 수정하지 않는다. 기존 고정 접두사도 통과한다. 빈/미정 대상, 표기/대상 참조/이유 누락, 빈 문장부호·없음/미확인 등 이유 placeholder 및 대상 단순 반복은 거부한다. 확정된 사용자 시청자는 원래의 정확 일치 검사를 유지한다.
- `video_mission_one.py`: 신규 실패 attempt의 기존 script_validation_diagnostics에 안전한 detail_code만 추가한다: literal_unspecified_audience / inference_marker_missing / audience_reference_mismatch / reason_missing. 기존 category·응답 해시 등은 유지하고 대상값·unknowns·응답 원문·비밀키를 복제하지 않는다. 실패는 기존 코드 script_audience_inference_required와 stopped 정책을 유지하며 자동 재시도하지 않는다. 과거 실제 실패에는 새 진단을 소급 기록하지 않는다.

이 검사는 선언/참조/이유 존재를 확인하는 보수적 규칙이며, 자연어 이유의 사실성·시청자 타당성을 독립 입증하지 않는다. 모든 한국어 표현/동의어를 이해하는 의미 평가기로 확장하지 않았다. 대본의 주제·선정25초·transcript·장면·provenance·불확실성 및 관리자 검토는 그대로 필요하다.

## 오프라인 검증 — 관련 묶음 1회

`PYTHONPATH=core:companies/video python -B -m unittest tests.test_script_quality tests.test_video_mission_one tests.test_quality_provider`: **53개 통과, 24.905초**. 임시 합성 fixture·mock native HTTP·외부 DNS/socket 차단. `git diff --check` 통과.

추가 사례는 표현 순서/띄어쓰기/문장부호가 다른 타당한 선언 및 기존 접두사 통과, literal 미정·AI/미확정 표기 누락·다른 대상 참조·이유 누락/빈값/placeholder·별개 항목으로 이유 분리 거부, 확정 시청자 불일치 거부를 확인했다. 실제 전송 모의 흐름에서 literal/reason_missing 세부 진단과 원문/키 미노출·실패 후 자동 재호출0을 확인했다. 표현이 다른 미정 대상 제안의 합성25초 대본→관리자 검토→편집 인수→임시 컷룸 awaiting_plan_approval도 통과했다. 기존 주제/기간/transcript·잘못된 model/mock provenance·원본 해시/서명·불명/중복 가드 회귀도 통과했다. 합성 fixture는 실제 대본이나 실패 응답 재현이 아니다.

## 보존과 다음 단계

**실제 Gemini/YouTube/provider API0회, 실제 successor/새 업무/grant/승인/실행0건.** 기존5개 stopped 업무와 컷룸 관련 JSON/consent/lock **17개 파일 SHA-256 시작/종료 동일**. 실제 Gemini 누적8·YouTube search2/videos2, 컷룸 research_planning, 기존 조사10건/관리자25초 선정·서명·attempt·active_operation 그대로다. data/, backups/, artifacts/, .env·키·음성/영상·기존 미추적7개 파일을 수정/삭제하지 않았다.

**다음 한 단계:** 별도 대표 실행 승인 범위 아래, 다섯 번째 실패와 누적8회를 보존하는 새 독립 후속 실행 절차가 필요하다. 이번에는 기존 실패를 재실행하거나 새 적격성 경로를 추가하지 않았다. 기존 free-writer 경로는 네 번째 provenance 실패 전용이므로 다섯 번째 audience 실패에 그대로 적용/가드 우회하지 않는다. 실제 모델의 수정 계약 준수·실제 대본/스토리보드 완성은 미검증이다. 이번 소스2개·테스트2개·이 보고서만 GitHub commit/push 후 중단한다.
