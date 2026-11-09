# 관리자 판단 실패 진단 및 오프라인 저장 경로 검증

2026-11-03 KST. git pull --ff-only로 main 674134e를 반영하고 지정 지시서를 실행했다. 실제 외부 AI 호출 0회, TASK-002 실행 0회, 기존 업무 데이터 변경 0회다. **이전 실제 실행은 응답 원문 미보존으로 historical_cause=unknown이며 실제 관리자 판단 성공을 주장하지 않는다.**

## 변경 파일과 동작

- manager_decision.py: validate_provider_response를 분리하고 고정 코드만 담는 DecisionDiagnosticError를 추가했다. 제공자 구조·finish_reason·content_type은 provider_response, 크기·JSON/중복 키/비표준 JSON은 decision_json, binding·strict 계약은 decision_contract로 구분한다. 원문·예외 메시지·키·프롬프트는 감사 기록에 포함하지 않는다.
- app.py: 단일 호출 경로의 transport, reservation_persist, ledger_persist, project_binding, decision_contract, proposal_persist 단계를 기록한다. 일반 오류는 고정 operation_failed 코드만 기록한다. 프로젝트 잠금을 유지한 채 디스크를 다시 읽어 중단 이력을 저장하며 원래 예외 메시지를 노출하지 않는다. 감사 저장까지 실패하면 한국어의 고정 오류로 정지한다. 저장 자체가 불가능하면 감사 기록을 남길 수 없는 한계가 있다. 재전송은 하지 않는다.
- tests/test_real_manager_decision.py: 네 action 각각 저장·새 프로세스 조회, 잘못된 응답 9종, 예약/원장/제안 저장 실패, 감사 저장 실패, 기존 stop_reason, 설정 없는 기존 관리자 attempt 중복 거절을 검증한다. 기존 stale·시간 초과 테스트에 단계 검증도 추가했다.
- 이 보고서.

## 저장 분기 분석

현재 코드에서는 기존 stop_reason이 요청 성공 시 삭제되지 않으며 전후 비교에 동일하게 남는다. updated_at은 기존 비교에서 정규화하고, 예산의 두 집계값은 입력 지문에서 제외하되 원장은 정확히 한 시도의 증가·예약 지문을 검사한다. 기존 stop_reason을 가진 정상 응답도 저장·조회되는 회귀 테스트가 통과했다. 이번에 구체적인 거짓 stale 저장 버그는 재현되지 않았으므로 지문 조건을 느슨하게 변경하지 않았다. 과거 실패를 이 분기의 버그로 단정할 근거도 없다.

정상 가짜 응답 네 행동은 기존 실제 제공자/handler 코드에서 원장 completed, provider=real_openrouter_free, status=pending_user_decision, attempt_id 및 KST 시각을 갖는 제안으로 원자 저장되고 각각 새 프로세스에서 조회된다. 사용자 결정 전 TASK-002 실행은 차단된다. 잘못된 응답은 completed 시도 하나만 남기고 제안 없이 단계 코드로 정지하며 재실행은 전송 전에 거절된다. 네트워크 실패는 failed, 예약 저장 실패는 전송 0회, 완료 원장 저장 실패는 기존 reserved를 보존한다. 프로젝트/승인/원장 변경 및 저장 실패 시 기존 업무 데이터를 보존한다. 테스트는 임시 fixture와 fake transport를 사용하고 실사용 JSON·키를 사용하지 않는다.

## 검증 명령과 결과

1. `python -B -m unittest tests.test_real_manager_decision tests.test_manager_decision_loop tests.test_project_budget tests.test_real_ai_safety_budget` 최초 55개 중 1개 오류: 저장 실패 주입 테스트가 과거 completed attempt에도 적용되어 승인 초기 저장부터 실패했다. 주입 조건을 새 attempt에 한정한 뒤 같은 55개 모두 통과했다. 제품에서 발견한 저장 버그가 아닌 테스트 주입 조건 오류였다.
2. `python -B -m unittest tests.test_real_manager_decision tests.test_manager_decision_loop tests.test_project_budget tests.test_real_ai_safety_budget tests.test_m4_runner_shutdown` 최종 61개 중 loopback 테스트 4개는 샌드박스 소켓 PermissionError로 실행 실패했다. 권한을 갖춘 동일 명령 재실행에서 **61개 모두 통과**했다. 외부 AI 대신 fake transport 및 로컬 loopback만 사용했다.
3. `git diff --check` 통과. 보고서 저장 후 재읽기 확인. 전체 테스트는 실행하지 않았다.

## 보존 확인과 다음 제안

작업 전후 data/backups 아래 17개 파일의 목록과 SHA-256이 모두 일치했다. 실제 영상 프로젝트는 사용 3/20, completed 3, failed/reserved 0, 잔여 17, 제안 0이다. TASK-001 사용자 승인과 원문 SHA-256 95e366272746a507f26f3776db5e6e5211126ae0f1f7d2b7712a718e5cff6802, TASK-002~004 대기·결과 없음, manager authorization·과거 stopped 이력·guard는 불변이다. 재고 프로젝트 c85d9853906a 및 미확정 예약을 포함한 기존 데이터·백업도 동일하다. 기존 미추적 파일은 수정·스테이징하지 않았다.

다음 핵심 개발 제안 하나: 새 실제 호출 없이, 저장된 단계 코드만 한국어 진단으로 보여 주는 읽기 전용 조회를 보완한다. 과거 원인 불명은 그대로 표시하고 재실행 기능은 추가하지 않는다.
