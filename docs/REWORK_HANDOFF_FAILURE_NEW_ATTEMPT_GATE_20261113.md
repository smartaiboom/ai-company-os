# 2026-11-13 — script_plan_handoff_required 이후 신규 승인 준비 게이트 최소 수정

사용자는 최신 코드 업데이트 완료. **실 API 재기획 HTTP200/json_parsed 후 script_plan_handoff_required로 중단된 실제 job** qualityprovider-0d3d8a4858f1422f8438f1eda5815aa9의 원인은 quality_workflow.py에서 재작업 동적 criteria ID와 일반 고정 criteria 검증 충돌이며, commit 1c024346으로 검사 분기가 이미 수정되었다. 이 변경은 외부 전송 스키마나 기존 PLAN_RULES를 변경하지 않았다.

**남은 정확한 장애**: companies/video/representative_rework.py::failed_plan_reference()는 reason_code를 ('invalid_dependencies','rework_plan_invalid','provider_unavailable')로 제한하여 새 실패 코드 script_plan_handoff_required를 허용하지 않음. studio_server.py::rework_view()는 failed_plan_reference 성공 시에만 new_attempt 버튼을 제공함. 그래서 코드 pull 후도 컷룸에서 새 작업 준비 버튼이 안 나옴.

이번에는 이 **한 가지 연결 문제만** 수정. AGENTS.md 확인. 기존 프로젝트/실패 job 읽기 전용 검증 후:
- script_plan_handoff_required는 **plan 단계, 완료된 HTTP200, JSON parsed, response_hash 있음, active_operation 종료 attempt id, no plan/assignments/final, sessions/attempts 1**, 이력 HMAC 유효, 기존 결과 불변 조건에서만 별도 신규 준비 가능.
- 새 job은 현재 변경된 내부 validator(quality_workflow.py commit 1c024346)로 재실행될 수 있고, 새 동의/서명/grant·대표의 명시적인 '새 재작업 준비→새 외부 전송 동의→AI 재작업 시작'이 있어야 함. 실패 job/grant/attempt 재실행/재사용 절대 금지. 같은 검증 버전의 무한 신규 준비는 차단하되 **기존 코드 규칙 때문에 발생한 오류를 코드 수정 이후 한 번만 복구 허용**하는 근거를 명확히 버전/코드 hash에 바인딩; 다른 오류로 gate 확대 금지.
- 기술적으로 기존 contract hash와 내부 validator 코드 버전 구별이 필요하면 최소 변경으로 구현하고 이유 기술. 재작업 prompt/검증/품질·동영상/음성/예산 변경 금지. 모든 중복 클릭 및 활성 operation guard 유지. 키/계정 재확인 요구 금지.
- **실 Gemini 호출0회**, 합성 fixtures로 기존 stopped HTTP200 handoff 오류 → 새 prepare → 새 consent → 모의 manager/writer/editor → 컷룸 v2 승인대기까지 표적 테스트 1개, 실패 원장 SHA 불변 확인. 길어진 종단이 부담되면 핵심 분기 표적 + 기존 검증된 종단 테스트 재사용.
- 보고서 reports/REWORK_HANDOFF_FAILURE_NEW_ATTEMPT_GATE_RESULT_20261113.md에 실제 적용 조건, UI 버튼 표시, 테스트 통과 여부, 실제 API0회, 대표 다음 단계 하나만 기록. main push/readback 종료.

KST. 기존 data/backups/artifacts/.env 및 미추적 파일, 과거 원장/동의/비디오/음성 전부 보존. API 전송/자동 retry/새 모델/유료 전환 금지. git clean/reset --hard/force push 금지.
