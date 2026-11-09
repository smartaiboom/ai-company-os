# 사용자 답변 기록과 범용 품질 검토→최종 결과 흐름 연결

2026-11-03 KST. `git pull --ff-only`로 main 061c8c7을 반영했다. **지정된 실제 관리자 질문에 사용자 답변 1건을 저장했고, 품질 검토·수정·재검토·최종 결과물·사용자 확정의 전체 흐름을 가상 프로젝트에서 검증했다. 실제 AI 호출·실사용 TASK-003/004 실행은 0회다.**

## 실제 사용자 답변 저장

사전 프로젝트 cb44b605b498는 9/20, completed 9, failed/reserved 0이었다. TASK-001/002 완료·approved, TASK-002 원문 SHA-256 `2276736d569a6e6cb34af05a4ac44e386d5a087ebd82f82dd59304c8bf0904ae`, TASK-003/004 대기·결과 없음, semantic 미설정·성공 기준 초안 미승인을 확인했다. 마지막 제안 `96b8ee2cc37c4aee830515255cc2af80`은 real_openrouter_free, ask_user, approved-result 형식, pending_user_decision·stale=false였다.

답변 저장 테스트 2개가 통과한 뒤 **2026-11-03 14:24:52 KST**, manager_decision_view의 실시간 expected_hash와 전체 프로젝트 해시를 사용해 기존 respond_manager_decision(..., "answer", answer=...)를 정확히 1회 호출했다. 네트워크·DNS·AI transport를 차단한 `python -B /tmp/record_authorized_workflow_answer_20261103.py`로 실행했으며 종료 코드 0을 확인했다. 실제 키를 사용하거나 AI_REAL_REQUESTS_ENABLED=1을 외부 실행 프로세스에 설정하지 않았다.

상태는 **pending_user_decision → answered**이며, TASK-002의 approved-result 답변 목록에 1건이 추가됐다. 기록한 내용은 지시서의 지정 문장을 그대로 사용했다: 대본 유지, 품질 검토에서 사실 확인 필요 항목·의미 정확성·초보자 이해도·제작 가능성 검토, 수정 여부는 검토 후 결정, 이 답변은 실제 AI 호출 승인이 아니라는 뜻이다. 사용자 원래 승인 문장과 답변 digest를 같은 KST 감사 이벤트에 기록했다. 다른 제안·모델 판단 내용·업무·원장은 보존했다. 중복 답변은 기존 상태 검사로 거절한다.

답변 때문에 해당 질문의 입력 지문이 달라져 과거 answered 제안이 stale로 보이는 것은 정상이다. 이를 다시 답변하거나 proceed로 바꾸지 않았다. 새 관리자 입력에는 등록한 답변이 포함되지만, 실행 권한·성공 기준 승인을 만들지 않는다.

## 병목과 선택한 개발 범위

기존 실행기·관리자 판단·의미 검토·수정 1회·최종 보관은 이미 있었지만, 관리자 질문/제안의 사용자 결정 화면이 없고 품질 검토 예약이 관리자 진행 승인 확인보다 먼저 저장되는 문제가 있었다. 관련 사용자 답변을 후속 직원에게 직접 연결하고 최종 확정 근거에 남기는 연결도 필요했다.

제품을 다시 만들거나 자동 호출을 추가하지 않고 다음 수직 연결을 구현했다.

- **app.py**: 사용자 질문 답변 감사에 선택적 user_authorization/answer_hash를 지원한다. 새 `/manager/decision`은 현재 프로젝트/제안 해시로 기존 결정 함수를 호출하며 자체 mutation lock을 사용한다. 질문은 answer, 진행 제안은 명시적 approve, 검토/변경 제안은 accepted_for_review로 분리하고 AI를 호출하지 않는다.
- **workflow_guidance.py**: 프로젝트 화면에 업무별 선행 승인·기준·의미 검토 상태, 관리자 질문/선택지/답변·판단·수락/거절, 과거 고정 오류와 새 별도 호출 승인 필요성을 읽기 전용으로 표시한다. 질문 답변·제안 수락·결과 승인·기준 승인·실제 호출을 구별한다. HTML은 escape하고, 오래된 제안에는 결정 양식을 표시하지 않는다. 앱을 직접 실행하는 경우에도 같은 runtime을 사용한다.
- **app.py 의미 검토**: 선행 결과와 관리자 require_proceed를 확인한 후에만 의미 검토 슬롯을 예약한다. 관리자 승인이 없는 시도는 프로젝트/원장/의미 검토 예약을 변경하지 않는다. 관련 사용자 답변 hash를 의미 검토 binding에 포함해 답변이 바뀌면 과거 품질 판정이 stale이 되도록 했다.
- **manager_decision.py**: 관련 선행 업무의 등록된 approved-result 사용자 답변만 후속 입력에 연결한다. 답변은 호출/기준 승인이 아님을 명시하고 원 질문의 결과 revision을 함께 표시한다. 다른 프로젝트·업무·review 목적·미답변 제안·임의 메타데이터는 제외한다. 사용자 승인 기록이 있는 semantic.criteria만 해당 대상의 다음 관리자 입력에 포함하며 미승인 초안은 보내지 않는다.
- **품질 기준 준비**: 업무 연결과 기존 역할에서 대상/검토 ID를 제안하고 현재 초안을 화면에 보여주되 미승인임을 명시한다. 버튼을 통한 별도 사용자 승인 전에는 저장·확정하지 않는다. 실사용 configure_semantic은 실행하지 않았다.
- **최종 결과 연결**: 기존 TASK-004와 같은 최종 업무는 승인된 선행 산출물·관리자 지침·관련 사용자 답변을 받는다. 기존 최종 사용자 승인과 immutable snapshot·Markdown/JSON 확정본 흐름을 유지하고, JSON 확정 근거에 허용된 관리자 판단·사용자 답변만 추가한다. 사후 관리자 결정은 원래 직원 결과의 품질 입력 지문으로 취급하지 않아 순환적인 stale을 만들지 않는다.

일반 실행 로직에 TASK-003/004 ID, 1분, 팁 개수나 제작 규칙을 넣지 않았다. 품질 검토 담당 역할은 기존 semantic 계약을 재사용했다. 기존 owner 단일 호출 도구·무료 어댑터·동의·예산·예약·무재시도 조건은 완화하지 않았다. 새 범용 무승인 실제 호출/자동 재개 endpoint는 만들지 않았다.

## 오프라인 종단간 검증

가상 프로젝트에서 실제 Handler.do_POST와 새 결정 양식을 사용했다. 네트워크를 열지 않고 가짜 직원/의미 검토 transport와 가짜 모델 응답만 공급했다. 계획/결과/관리자 진행 제안/기준/수정 여부/최종 확정의 사용자 승인은 테스트 사용자가 실제 handler에 명시적으로 제출했다.

검증된 주요 흐름:

1. 승인된 결과 → 관리자 ask_user → 답변 → 답변을 포함한 새 관리자 proceed → 사용자 진행 승인 → 사용자 품질 기준 승인 → 의미 품질 검토 → 검토 결과 사용자 승인 → 검토 결과용 새 관리자 proceed 및 사용자 승인 → 승인 선행 자료를 종합한 최종 업무 → 사용자 최종 확정·보관 파일·Markdown 읽기.
2. changes_needed → 검토 결과 승인 차단 → 사용자 수정 요청 승인 → 대상 직원 수정 1회 → 사용자 결과 재승인 → 바뀐 결과에 대한 새 관리자 진행 판단·승인 → 의미 재검토 1회 → pass → 검토 결과 승인·최종 결과/확정. 최초 승인 결과는 수정 요청만으로 바뀌지 않는다.
3. inconclusive/unknown, timeout, 소모된 검토 재실행은 후속 업무를 차단한다. 근거를 외부에서 확인하지 못한 항목은 미확인/model_claim으로 남기며 사람 최종 승인이 필요하다. 모델 pass는 독립 사실 검증이 아니다.
4. 관리자 승인 누락 시 의미 검토 슬롯·원장을 예약하지 않음, 최신 프로젝트 토큰 누락/경합/중복 답변 거절, request_revision/계획 변경 수락만으로 실제 수정·계획 변경·직원 실행이 이뤄지지 않음, 사용자 답변 변경 시 과거 품질 판정/승인 차단, 화면 escape와 실제 프로젝트 페이지/양식 연결.

신입 직원 안내와 별도 도서관 안내 목표, `TASK-101/TASK-211/TASK-321/TASK-431` 같은 다른 ID 조합을 사용했다. 성공 사례의 기준은 절차의 구체성과 미확인 주장 표시를 확인하는 것이며, 가짜 모델에 실제 사실 검증 능력이 생겼다고 주장하지 않는다. 기존 승인된 결과용 관리자 판단과 pending-result 검토의 권한 분리는 유지했다.

## 테스트 명령·결과

- `python -B -m unittest tests.test_authorized_manager_answer.AuthorizedAnswerTests.test_authorized_answer_changes_only_question_answer_and_audit tests.test_authorized_manager_answer.AuthorizedAnswerTests.test_stale_project_or_question_rejects_without_writes > /tmp/autonomous-answer-tests.log 2>&1` → **2개 통과**, 실패·오류 0(0.099초). 실제 답변 저장 전에 완료했다.
- `python -B -m unittest tests.test_autonomous_workflow > /tmp/autonomous-e2e-first.log 2>&1` → **4개 중 오류 2건**. 가상 시나리오에서 품질 결과를 사용자 승인하기 전에 승인 결과용 관리자 판단을 생성한 테스트 순서 오류였다. 기존 승인 경계를 바꾸지 않고 순서를 수정했다.
- 같은 테스트 `/tmp/autonomous-e2e-second.log` → **4개 통과**(0.179초). 입력/확정 근거·실패 표시 사례 추가 후 `/tmp/autonomous-e2e-third.log` → **5개 통과**(1.091초).
- 주요 수직 사례와 답변 두 사례 `/tmp/autonomous-vertical-final.log` → **7개 통과**(0.481초). 이후 페이지·허용 입력·답변 stale 사례를 추가했다.
- `python -B /tmp/run_autonomous_workflow_tests.py > /tmp/autonomous-focused-first.log 2>&1` → **317개 통과**, 실패·오류 0(29.750초).
- 승인된 품질 기준 입력과 사용자 답변 지문 연결까지 포함한 최종 명령 `python -B /tmp/run_autonomous_workflow_tests.py > /tmp/autonomous-focused-final.log 2>&1` → **318개 모두 통과**, 실패·오류 0(28.375초).

집중 runner는 임시 서명키 경로에서 다음 대상을 실행했다.

`tests.test_autonomous_workflow` 및 위 답변 테스트 두 메서드, `tests.test_manager_decision_loop tests.test_manager_pending_review tests.test_ai_provider_adapter tests.test_real_manager_task002_new_authorization tests.test_real_manager_approved_task002 tests.test_real_manager_review_once tests.test_real_task002_once tests.test_accept_review_task002 tests.test_task_result_approval_preparation tests.test_final_report_approval tests.test_semantic_review_integration.SemanticIntegrationTests tests.test_execution_engine tests.test_manager_plan tests.test_real_ai_safety_budget tests.test_project_budget tests.test_concurrent_execution_safety`

실제 unittest 수에는 기존 fixture import/상속에 따른 반복이 포함된다. 새 종단간 사례 8개와 답변 저장 사례 2개로 핵심 성공·수정·실패·승인 경계를 증명했다. 전체 테스트·HTTP 소켓 서버·브라우저 검증은 실행하지 않았다. 동일 Handler의 GET/POST를 직접 호출해 화면과 양식을 확인했으며 HTTP 서버가 통과했다고 표현하지 않는다. 외부 socket/DNS/transport 차단과 가상 키를 사용했다. 테스트 안에서만 가짜 요청 검증 환경을 구성했고 실제 서버 활성화·실사용 키·JSON fixture는 사용하지 않았다. 최종 미해결 테스트 실패는 없다.

## 실사용 보존과 한계

사전 data/backups **29개**, 기존 미추적 파일 6개, 합계 35개 목록·SHA를 기록했다. 사후 data/backups 목록은 동일하고 대상 JSON 외 **기존 34개 파일 SHA가 동일**하다. c85d9853906a의 미확정 예약, 모든 과거 guard/관측과 백업을 포함한다. 새 data/backup/guard/서명키 파일은 없다.

대상은 지정 제안의 answered/decided 필드, 답변 1건, KST 감사 1건과 갱신 시각만 변경했다. 모든 TASK, TASK-002 원문/승인, 9개 원장·동의·한도, 기존 다른 제안, 8번째 실패·이전 승인/guard, 계획·선호·미승인 기준 초안은 보존했다. **실사용 9/20, completed 9, failed/reserved 0, 잔여 11**이다. 실제 TASK-003/004·semantic 평가·기준 확정·최종 확정은 수행하지 않았다.

독립 웹 조사/출처 검증, 실제 낭독·영상 제작 측정 기능을 추가하지 않았다. AI 검토는 제공 자료의 정합성과 불확실성을 평가하는 단계다. 확인할 수 없는 사실은 unknown/사람 검토로 분리하며 실제 사실 확인 완료로 표시하지 않는다. 새 실제 관리자 판단·실제 직원 실행은 기존 외부 전송 범위와 별도 사용자 승인을 받아야 한다. 가상 성공은 실사용 완료가 아니다.

## 다음 사용자 행동 — 최소 승인 단위

실제 프로젝트의 다음 병목은 사용자 답변을 반영한 **새 approved-result 관리자 판단**, 그리고 실제 의미 검토에 사용할 **사용자 품질 기준**이다. answered는 진행 허가가 아니고, 미승인 기준 초안은 여전히 미승인이다.

다음 한 번의 사용자 결정에서 아래 기준을 승인/수정하고 **답변과 확정 기준을 입력으로 하는 무료 관리자 판단 최대 1회**의 승인을 함께 명시할 수 있다. 이는 품질 검토 직원 호출 승인은 아니다. 별도 작은 개발 지시서를 계속 만들기보다, 이번 공통 화면/handler와 검증된 연결을 사용해 필요한 승인 시점마다 이어갈 수 있다.

실제 영상 사례에 대한 검토용 기준 제안이며, 아직 저장하거나 승인하지 않은 초안이다.

- 기능·수치·출처 주장의 근거를 구분하고 확인할 수 없는 내용은 미확인으로 표시한다.
- 초보자가 요청 방법과 사용 시 주의점을 이해할 수 있게 구체적으로 설명한다.
- 대본·자막·음성/화면 구성 사이의 누락·모순과 제작에 필요한 추가 자료를 식별한다.
- 제시한 분량은 추정과 실제 측정 근거를 구분하며, 낭독 확인이 없으면 시간 적합성을 미확인으로 남긴다.

그다음 실제 관리자 판단이 proceed라면 사용자가 그 제안을 확인·승인하고 **실제 품질 검토 호출**을 별도로 승인해야 한다. 수정 필요/판정 불가이면 수정 여부·근거 보완·재검토 승인이 필요하고, pass도 검토 결과 사용자 승인과 최종 업무 진행 판단/실행 승인을 대체하지 않는다. 최종 패키지 역시 결과 검토·사용자 확정을 거쳐야 한다. 현재는 이 모든 실제 호출·승인 지점 앞에서 정지했다.

최종 `git diff --check` 통과, 보고서 저장·재읽기 및 data/backups 전체 목록·대상 외 34개 파일 SHA 재검증을 마쳤다. 제품 코드 3개·테스트 2개·보고서 1개만 선택적으로 커밋·푸시하며 원격 main을 확인한다. 실사용 JSON·대본·키·guard/관측 원문은 Git에 포함하지 않는다.
