# 범용 AI 관리자 모델 출력 계약 개선 — 오프라인 검증

2026-11-03 KST. `git pull --ff-only`로 main bcaa9fd를 반영하고 지정 지시서를 실행했다. **실제 AI API 호출 0회, TASK-002 실행 0회, 실사용 데이터 변경 0회**다. 지난 두 번의 실제 응답 원문이 없어 개별 필드 실패 원인은 여전히 불명이다. 이번 테스트를 실제 AI 관리자 판단 성공으로 표현하지 않는다.

## 변경 파일과 계약

- manager_decision.py: 모델 출력은 정확히 action, rationale, evidence, next_step, uncertainty, payload 여섯 필드만 허용한다. schema_version·binding·source는 모델 소유 필드가 아니다. user 메시지는 기존 허용 data만 전송하도록 구성하고 프로그램의 project_id/결과/승인/계획/input 지문 전체를 보내거나 복사하도록 요구하지 않는다. 관련 TASK ID는 판단 자료와 payload 검증에 계속 사용한다. system 프롬프트에는 네 행동의 payload 형식을 같은 비중으로 제시하며 특정 행동·콘텐츠 개수·영상 규칙은 강제하지 않는다.
- 모델 응답의 구조·완료 사유·JSON 검사 후, 의미 내용은 기존 저장 계약과 공유하는 validate_decision_content에서 먼저 검증한다. 유효한 판단에만 프로그램이 context의 binding 복사본, schema_version=1, source=model_claim을 붙이고 기존 parse_and_validate를 다시 통과시킨다. action·payload·문장을 보정하거나 누락 내용을 만들어 채우지 않는다.
- 기존 모델 형식의 binding이나 metadata는 값이 정확해도 unexpected_field로 거절한다. 과거 전체 저장 JSON을 모델 응답으로 허용하지 않는다. 반면 기존 저장 JSON과 모의 공급자의 계약은 그대로 유효하다. parse_and_validate의 schema/metadata 검사 및 의미 조건은 유지하고 의미 검사만 공유 함수로 추출했다. 공유 검사의 ValueError 하위 오류에는 고정 세부 코드를 부여했다.
- tests/test_real_manager_decision.py 및 tests/test_real_manager_second_authorized.py: 실제 provider의 가짜 응답만 여섯 필드 형식으로 변경했다. 기존 mock/내부 저장 fixture와 그 테스트는 변경하지 않았다. 전송 data에 binding/프로그램 지문이 없는지도 검증한다.
- tests/test_manager_model_output_contract.py: 최소 모델 JSON, 신뢰 binding 복사, 의미 보존, 과거 형식·metadata·승인 표시 거절, 세부 오류와 안전 중단을 검증한다.
- 이 보고서.

행동별 payload는 기존과 같다. proceed는 직접 후속 next_task_ids와 한국어 guidance, ask_user는 question/why_needed/options, request_revision은 승인 결과의 task_id 및 reason/scope, propose_plan_change는 changes를 요구한다. 기존 ID를 대상으로 한 modify/reorder와 새 ID에 대한 add만 허용한다. 계획 변경안은 사용자 결정 대기 제안이며 실제 계획을 바꾸지 않는다. 모든 설명의 한국어·빈 문자열·1500자 상한 및 JSON 32768바이트 상한도 유지한다.

## 진단과 안전 경계

기존 provider_response 및 decision_json stage/code를 유지한다. decision_contract에는 invalid_object, unexpected_field, missing_field, invalid_action, invalid_payload, invalid_target, invalid_text를 추가했다. 최종 내부 저장 계약 검사 실패는 기존 strict_contract다. 코드에는 응답 필드 값이나 동적 예외 메시지를 넣지 않는다. 응답 전문·키·프롬프트·사용자 자료를 새 감사 로그나 Git에 남기지 않는다.

app.py, ai_safety.py, real_manager_second_tool.py의 승인/예약/예산/guard/동시 변경 비교 로직은 수정하지 않았다. 입력 binding은 계속 프로그램이 승인된 스냅샷에서 계산하고, 모델 응답 이후 최신 프로젝트 지문 및 정확한 단일 원장 증가를 검사한다. 승인된 결과/계획/사용자 승인·원장 변경은 계속 차단된다. 실제 모델 자동 활성화나 3차 호출 경로는 추가하지 않았다. 직원/사용자 자료의 명령 격리 및 미검증 주장 안내도 유지한다.

## 테스트와 결과

테스트 우선으로 새 경계 테스트를 작성한 뒤 다음을 실행했다.

1. `python -B -m unittest tests.test_manager_model_output_contract > /tmp/manager-model-contract-red.log 2>&1` → 구현 전 3개 테스트에서 실패 23건·오류 4건. 기존 전체 binding 응답 계약이 최소 모델 JSON을 거절하고 세부 코드가 없는 것을 의도대로 확인한 초기 실패다.
2. 같은 테스트를 구현 후 `/tmp/manager-model-contract-first.log`로 실행 → **3개 통과**.
3. `python -B -m unittest tests.test_manager_model_output_contract tests.test_real_manager_second_authorized tests.test_real_manager_decision tests.test_manager_decision_loop tests.test_project_budget tests.test_real_ai_safety_budget > /tmp/manager-model-contract-focused.log 2>&1` → **87개 통과**.
4. 과거 형식의 정확한 binding도 거절하는 사례 및 비객체/JSON 외부 텍스트/비표준 숫자 등을 추가한 후 같은 집중 명령을 `/tmp/manager-model-contract-final.log`로 실행 → **88개 모두 통과**, 실패·오류 0. 기존 테스트 상속/발견에 따른 반복 사례가 포함된 unittest 실제 실행 수다.
5. `git diff --check` 통과. 보고서 저장 후 재읽기 확인. 전체 테스트는 실행하지 않았다.

정상 네 행동 각각 fake transport → 모델 내용 검증 → 프로그램 metadata 조립 → 기존 strict 저장 계약 → completed 원장 → pending_user_decision 영속 저장 → 새 프로세스 조회를 기존 실제 handler에서 확인했다. 1차 및 2차 승인 경로, 3→4/20 fixture 예산·guard·승인 보존, 사용자 결정 전 TASK-002 차단, mock 및 기본 20회 예산 회귀도 통과했다.

오류 사례는 알 수 없는/숫자 action, 잘못된 payload·타 TASK, 한국어 아닌/빈/숫자/과도한 텍스트, 누락/추가 필드, 옛 metadata, 중복 키, 크기 초과, JSON 외 텍스트, 잘못된 finish_reason, 지문·원장 경합 등을 포함한다. 가짜 응답은 한 시도만 소모하고 제안 없이 정지하며 중복 실행 시 추가 전송하지 않는다. 새 테스트는 임시 프로젝트와 가상 키 및 fake transport를 사용하며 socket/DNS가 차단된 fixture에서 실행했다. 실사용 프로젝트 JSON이나 실제 키는 테스트에 사용하지 않았다.

## 실제 상태와 보존

작업 전후 data/backups **19개 파일 목록과 SHA-256이 전부 일치**한다. 영상 프로젝트 cb44b605b498는 **4/20, completed 4, failed 0, reserved 0, 잔여 16, 제안 0** 그대로다. TASK-001 사용자 승인과 결과 SHA-256 95e366272746a507f26f3776db5e6e5211126ae0f1f7d2b7712a718e5cff6802 및 TASK-002~004 대기·결과 없음도 다시 확인했다. 두 manager attempts, 기존 authorization/additional_authorizations·guard·관측/중단 이력이 불변이다. 재고 프로젝트 c85d9853906a의 미확정 예약 및 모든 기존 백업도 포함한다. 새 백업은 만들지 않았으며 기존 미추적 파일을 수정·삭제·스테이징하지 않는다.

한계: 오프라인 검증만 완료했으므로 실제 무료 모델의 응답 준수나 실제 제안 저장 성공은 아직 확인하지 못했다. 지난 두 실패가 binding 복사 때문이었다고 단정하지 않는다. **다음 실제 관리자 호출에는 새 사용자 승인이 필요하며, 기존 승인·guard를 재사용하거나 원장을 초기화해 실행할 수 없다.**
