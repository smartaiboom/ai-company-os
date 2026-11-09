# 미승인 직원 결과에 대한 범용 관리자 검토 경로 — 오프라인 준비

2026-11-03 KST. `git pull --ff-only`로 main 46525e9를 반영하고 지정 작업을 수행했다. **실제 AI 호출·실사용 예약·직원 실행·결과 승인·결과 수정은 모두 0회**다. 실제 AI 관리자 검토 판단은 아직 생성하지 않았다.

사용자 검토 대기 중인 완료 결과에 대해 네 가지 관리자 행동을 검증·저장·재조회할 수 있는 오프라인 경로를 추가했다. 검토 제안 수락은 직원 결과 승인과 별개이며, 후속 실행 허가를 만들지 않는다. 영상 분량·팁 개수·문제 목록을 코드에 지정하지 않았다.

## 설계와 변경 파일

- manager_decision.py: 기존 decision_input은 approved 결과만 계속 허용한다. 별도 employee_review_input은 승인 계획과 일치하는 완료·pending 결과, 승인된 선행 결과 연결, 해당 선행 업무의 사용자 승인 관리자 지침을 요구한다. 공통 입력 생성·의미 검증을 공유한다.
- app.py: _manager_review_input, 목적별 _proposal_context, 엄격한 모의 공급자만 받는 propose_employee_result_review_offline을 추가했다. 기존 mutation lock·원자 저장·전체 프로젝트 지문 비교를 사용한다. 모의 제안은 mock 설정의 임시/모의 프로젝트에서만 저장 가능하며 real_openrouter_free 실사용 설정에 모의 제안을 섞지 않는다. 실제 공급자 객체를 이 오프라인 진입점에 전달하면 거절한다. HTTP 경로·실제 실행 runner는 추가하지 않았다.
- tests/test_manager_pending_review.py: 가상 고객 안내문과 가상 키·fake provider/transport·socket/DNS 차단을 사용한다. 실사용 JSON이나 실제 키는 fixture에 사용하지 않는다.
- 이 보고서.

입력 data의 purpose는 employee_result_review이고 대상은 employee_result_data로 표시한다. 기존 approved_result_data와 구별하여 pending 결과를 승인된 결과로 부르지 않는다. 승인 목표·관련 업무 정의·허용된 선호(focus/video_style)·대상 결과·승인 선행 결과·사용자가 승인한 관리자 지침·직접 후속 업무·예산 요약·목적별 사용자 답변만 포함한다. 관계없는 프로젝트 필드, 임의 메타데이터와 비밀용 fixture 필드는 제외한다. 허용된 본문 안의 개인정보를 자동 익명화하는 기능은 추가하지 않았다. 향후 실제 전송에는 별도 범위 확인이 필요하다.

대상 결과는 최대 16000자, 전체 data는 최대 32768바이트이며, 선행 결과도 기존 길이·승인 계획 검증을 거친다. 자료에 포함된 명령과 “검증됨” 주장을 신뢰하지 않는다는 안내를 제공한다. 모델에는 특정 판단을 요구하지 않는다. 미승인 결과라는 검토 목적 및 사용자 결과 승인이 별도로 필요함을 프롬프트에 명시한다.

프로그램 소유 binding에는 프로젝트/업무, 대상 결과 hash/revision, 승인 계획 hash, pending review_status, 검토 상태 hash, 선행 결과 binding hash, 전체 허용 입력 hash를 결합한다. 선행 자료의 프로그램 지문은 모델 data에 복사하도록 요구하지 않는다. 최상위 저장 목적과 binding 목적이 일치해야 하며 다른 프로젝트·업무·목적의 지문을 그대로 사용할 수 없다.

모델 출력은 기존 action/rationale/evidence/next_step/uncertainty/payload 여섯 필드다. 기존 validate_provider_response → 프로그램 metadata 결합 → parse_and_validate를 공유하며, 네 행동·정확한 payload·한국어·길이·중복 키·추가 필드·대상 ID 검증을 유지한다. request_revision은 검토 대상 업무만 지정할 수 있다. action이나 모델 문장을 보정하지 않는다.

## 저장·사용자 결정·실행 경계

검토 제안은 purpose=employee_result_review, status=pending_user_decision으로 기존 제안 목록에 추가하며 기존 제안을 덮어쓰지 않는다. manager_decision_view는 목적별 최신 context로 stale 여부를 계산한다. 같은 binding의 중복 제안, 프로젝트 경합, 결과·revision·검토 상태·계획·선행 결과·승인 지침 변경을 거절한다.

respond_manager_decision은 검토 목적의 approve를 모든 action에 대해 accepted_for_review로 기록한다. request_revision 수락은 수정·재실행을 하지 않으며 proceed 수락도 직원 결과를 approved로 바꾸지 않는다. reject는 rejected, ask_user에 대한 실제 사용자 answer는 answered로 기록한다. 검토 답변·감사 이력에는 목적을 표시하고, 기존 승인 후속 판단용 답변과 분리한다. 자동 답변은 없다.

require_proceed는 검토 목적의 제안을 명시적으로 제외하고 기존 approved 결과 binding의 승인된 후속 제안만 인정한다. TASK-002가 pending이면 TASK-003 실행은 계속 차단된다. 나중에 사용자가 기존 결과 승인 절차로 TASK-002를 승인하더라도 검토 제안만으로 후속 실행은 허용되지 않는다. 별도의 기존 승인 결과용 관리자 proceed 제안 및 사용자 승인이 있어야 한다. 이 과정을 가상 프로젝트에서 검증했으며 실사용 TASK-002에는 적용하지 않았다.

## 테스트 명령과 결과

1. `python -B -m unittest tests.test_manager_pending_review > /tmp/pending-review-first.log 2>&1` → **25개 통과**, 실패·오류 0. 초기 신규 사례와 import된 기반 fixture 클래스의 테스트를 포함한다.
2. 아래 집중 명령을 `/tmp/pending-review-focused.log`로 실행 → **172개 통과**, 실패·오류 0, 13.374초.

`python -B -m unittest tests.test_manager_pending_review tests.test_manager_model_output_contract tests.test_manager_decision_loop tests.test_real_manager_decision tests.test_real_manager_second_authorized tests.test_real_manager_third_authorized tests.test_real_task002_once tests.test_real_ai_safety_budget tests.test_project_budget`

기반 fixture import/상속에 따른 반복 사례를 포함한 unittest 실제 실행 수다. 전체 테스트는 실행하지 않았다. 기존 무료 모델·예산·1~3차 관리자 승인 및 guard 재사용 방지·TASK-002 직원 단일 실행 회귀를 포함한다.

신규 검증은 다음을 포함한다.

- TASK-001 approved → TASK-002 pending의 네 행동, 여섯 필드 모델 내용 검증, 프로그램 metadata 결합, pending_user_decision 저장 및 새 프로세스 조회.
- 사용자 수락/거절/질문 답변 저장, 중복 승인·제안 차단, TASK-003 실행 차단, 직원 결과·기존 TASK-001 제안·원장·계획·선호·기존 guard·다른 가상 프로젝트 보존.
- 결과/revision/검토 상태/계획/선행 결과/관리자 지침 변경 stale, 다른 프로젝트 binding·목적 혼동·다른 대상 payload·metadata 삽입·영어 설명·크기 초과·중복 키 거절.
- 가상 데이터의 명령 삽입을 자료로 격리하는 프롬프트/허용 필드 검증, 실사용 설정에 mock 저장 및 실제 공급자의 오프라인 진입 거절. 모델의 실제 프롬프트 인젝션 저항성이나 사실 검증을 증명하는 테스트는 아니다.
- lock 경합과 공급자 실행 중 프로젝트 변경 시 제안 저장 거절 및 경합 내용 보존.
- fake transport를 통한 기존 실제 provider의 review 프롬프트·여섯 필드 응답 검증. 가상 키와 별도 복사 fixture에만 가짜 원장을 만들고 실사용 원장과 저장 fixture는 변경하지 않았다.
- 사용자 결과 승인이 별도로 이뤄진 뒤 기존 승인 결과용 관리자 판단 경로가 정상 동작함을 가상 프로젝트에서 검증.

## 실사용 읽기 검증 및 보존

실사용 JSON의 실제 TASK-002 결과를 읽고 그 내용·지문을 직접 확인했다. 원문이나 전체 JSON을 보고서·Git에 복사하지 않았다. TASK-002는 완료·pending, 결과 1263자이며 “검증됨”이라는 표현이 포함돼 있다. 그 표현은 독립 검증 사실이 아니다. 원문 SHA-256은 `2276736d569a6e6cb34af05a4ac44e386d5a087ebd82f82dd59304c8bf0904ae`다. 읽기 전용 _manager_review_input이 이 실제 상태에서 검토 context를 생성하는 것까지 확인했으며 제안은 저장하지 않았다.

실사용은 **6/20, completed 6, failed/reserved 0, 잔여 14**다. TASK-001 승인 결과 SHA-256 `95e366272746a507f26f3776db5e6e5211126ae0f1f7d2b7712a718e5cff6802`, TASK-002 결과/pending, TASK-003/004 대기·결과 없음, 기존 TASK-001 관리자 proceed 승인 모두 그대로다.

사전 data/backups 파일 목록·SHA-256 **23개** 및 기존 미추적 파일 6개(합계 29개)를 기록했다. 사후 동일 목록·SHA를 비교해 전부 일치함을 확인했다. c85d9853906a의 미확정 예약, 백업, 기존 관리자·직원 guard와 관측 파일을 포함한다. 실제 데이터·동의·승인·원장 변경, guard 생성/삭제, 백업 추가/삭제는 없다.

## 남은 제한과 다음 승인

이번에 실제 AI 판단은 생성하지 않았고 오프라인 기능만 검증했다. 모의 검토 결과를 실제 AI의 평가로 표현하지 않는다. TASK-002는 여전히 사용자 미승인 결과다.

**다음 실제 무료 AI 관리자 검토 호출 최대 1회에는 사용자에게 별도 명시 승인을 요청해야 한다.** 새 승인에서 목적·프로젝트·TASK-002 현재 지문과 전송 범위를 확인하고, 이전 관리자 1~3차 승인이나 TASK-002 직원 승인을 재사용하지 않아야 한다. 이번에는 실제용 owner runner를 실행하거나 새 승인을 만들지 않았다.

후속 별도 승인 작업에서는 이 읽기 전용 context와 공유된 모델 계약을 이용하되, 새 단일 사용 승인 ID·정확한 6건 원장 비교·요청 전 1회 예약 저장·고유 O_EXCL guard·전송 전 영속 관측·무재시도·경합 검사와 저장을 별도로 연결해야 한다. 기존 실제 공급자는 여전히 무료-only/명시 request_scope/동의/예산 검사를 요구하며 이번 변경으로 과거 단일 호출 진입점의 재사용 범위를 넓히지 않았다.

## 최종 검증

오류 문구·목적별 감사 기록을 정리한 뒤 같은 집중 명령을 `/tmp/pending-review-final.log`로 재실행해 **172개 모두 통과**, 실패·오류 0(15.264초)을 확인했다. `git diff --check` 통과. 보고서 저장 후 다시 읽어 파일 생성과 내용을 확인했다. 코드 두 파일·테스트·보고서만 선택적으로 커밋·푸시한다.
