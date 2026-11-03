# AI Company OS v0.1 — TASK-002 관리자 검토 proceed 수락, 대본 결과 승인, TASK-003 품질 검토 준비

## 사용자 결정과 이번 작업의 한계
2026-11-03 사용자: “응 다음 품질검토 단계로 진행하자”. 직전 대화에서 ‘AI 관리자의 proceed 제안 수락 + TASK-002 대본 사용자 승인 후 TASK-003 품질 검토 단계로 진행할지’를 물었고 **“아직 TASK-003 실제 AI 호출까지 승인하는 것은 아니야”**라고 명시했다. 그러므로 이번 작업에는 **기존 실제 AI 관리자 TASK-002 검토 제안 수락 및 TASK-002 결과 승인, TASK-003 준비·차단조건 확인**만 포함한다. TASK-003의 **실제 OpenRouter AI 호출 승인 없음**, 실제 AI 호출 **0회**. TASK-003 검토 자체나 TASK-004, workflow 자동실행, 다른 관리자 재호출 금지.

다른 기존 데이터·백업·guard·프로젝트를 보존하고 최소 변경. KST(+09:00), 한국어 지시 및 보고. `codex_tasks/README_KOREAN_LANGUAGE_RULE.md` 준수. `git pull --ff-only`, git reset/clean/force push 금지.

## 매우 중요한 승인 순서 및 제안 바인딩
검토용 AI 제안은 *TASK-002가 pending일 때의 결과 hash + pending review_status*에 바인딩되어 있다. **먼저 TASK-002 결과를 승인하면 검토 제안이 stale이 되어 기존 `respond_manager_decision`으로 수락할 수 없다. 따라서 반드시 아래 순서로 처리**한다.

1. 실사용 project=`cb44b605b498`의 최신 상태를 읽는다. expected: 7/20, completed 7, failed/reserved 0; TASK-001 approved SHA `95e366272746a507f26f3776db5e6e5211126ae0f1f7d2b7712a718e5cff6802`; TASK-002 status=완료, review_status=pending, 결과 SHA `2276736d569a6e6cb34af05a4ac44e386d5a087ebd82f82dd59304c8bf0904ae`; TASK-003/004 대기·결과 없음. 기존 TASK-001 관리자 proceed 제안 ID `2d62725cfe374852b916b5bd20af67ac`는 approved. TASK-002 review 제안 ID `4a415f66a228440481806dd5cfc2818a`의 provider=real_openrouter_free, purpose=employee_result_review, action=proceed, payload 다음 업무가 TASK-003/TASK-004임을 원문에서 확인, status=pending_user_decision, stale=false. 이 항목만 대상으로 최신 `manager_decision_view`에서 expected_hash 획득. 다른 제안/업무로 대체 금지.
2. 프로젝트 mutation lock/최신 지문 및 입력 불변 검증 후 기존 `app.respond_manager_decision(project_id, proposal_id, expected_hash, "approve")` 실행. 이 검토 목적 제안의 기록 상태는 설계상 `accepted_for_review`가 되며 `approved`가 아니라는 점에 유의. 이는 **관리자 판단 수락**을 뜻하며 TASK-002 결과 승인 또는 TASK-003 실행 허가는 아님. 모델의 ‘승인된 대본’ 같은 표현은 사실이 아니므로 감사에서 구분.
3. 관리자 검토 제안 수락 기록이 저장됐음을 다시 읽은 뒤, **사용자의 이번 TASK-002 결과 승인**을 기존 `/task/review`의 동일한 유효성 체크와 로직으로 적용. 프로젝트 lock 아래 원자 저장, 최초 성공 결과 지문 검증, 선행 승인 검증, `task_needs_approval`, `task_has_successful_result`, `task_requires_review` 및 current review_status pending 확인. `review_status=approved`, reviewed_by=사용자, reviewed_at=KST, 기존 결과 문자열/결과 revision 불변, history `task_review_approved`. **HTTP route 변경/우회보다 기존 코드의 승인 처리 재사용 선호.** 재사용할 로컬 승인 함수가 없다면 좁은 사용자 승인용 local owner handler를 만들고 기존 `/task/review`의 모든 검증을 동등하게 유지. 중복 처리/프로젝트 경합/오래된 제안/업무 지문 차단. 사용자 승인 원문·KST·대상/결과 hash 감사 이력 추가하되 기존 history/원장 불변.
4. TASK-003의 실질 실행 가능 조건을 **읽기 전용으로 점검**한다. TASK-003 품질 검토가 `semantic` 전용 reviewer인지, `configure_semantic`이 필요하고 현재 `success_criteria_draft`가 미승인인지, 후속 관리자 `require_proceed`가 승인된 TASK-002의 **별도 approved-result-manager decision**을 요구하는지 정확히 확인. **관리자 review 목적 proceed를 후속 실행 허가로 재해석·승격하지 말 것.** `manager_decision.decision_input(project, "TASK-002")`가 승인 후 가능한지는 확인하되 새 실제 AI 판단/모의 승인/가짜 지침 생성 금지. 프로젝트에 해당 기능의 기준이 미승인이라면 **승인 없이 semantic criteria 확정하지 말 것**. 이 모든 차단조건을 보고서에 사용자 친화적으로 적고 다음 실제 TASK-003 검토 실행 전에 무엇이 필요한지 명시.
5. TASK-003/004 결과 없음·대기 불변, 워크플로 자동 실행 0, 실제 AI API 요청 0. 7/20 원장 그대로. 다른 프로젝트 `c85d9853906a` 미확정 예약·기존 guard/관측·백업·미추적 파일 모두 불변. 실사용 JSON 전체/대본 전문/API 키 Git 추가 금지.

## 시험 및 실행
실사용 저장 전에 가상 프로젝트·가상 키·socket 차단으로 **검토 제안 수락→TASK-002 사용자 승인** 정확한 순서, 이전 순서에서 stale되는 사례, result hash 불일치/중복 승인/프로젝트 동시 변경/사용자 승인 원문 바인딩 차단, 결과 원본 보존, TASK-003/004 미실행, 실제 전송 0회, 기존 관리자 approved-result proceed와 review-purpose accepted_for_review 분리, 기존 승인된 TASK-001 제안 불변을 테스트. 관련 기존 테스트 집중 실행; 모의 프로젝트만 사용. 결과 오류 시 실사용 적용 금지. 실제 적용 시 최신 상태 재확인하고 이미 완료된 단계 발견하면 사용자 확인 없이 동일 단계 재실행 금지. 사전 data/backups·guard/미추적 SHA 기록, 사후 대상 JSON 이외 모두 동일 확인. 대상 프로젝트 JSON도 제안 status/decided_at/decided_by, TASK-002 승인 필드, 최소 감사/시각 외 불변.

## 보고 및 종료
`reports/v01_accept_review_proceed_approve_task002_prepare_task003_20261103.md` 한국어 보고. 현재 제안의 처리 결과 `accepted_for_review`, 사용자 TASK-002 결과 `approved`, 승인 시각 KST, TASK-002 원문 SHA 불변, 7/20, 새 AI 0회, 테스트 명령/수·결과, 이전 project/백업 보존, TASK-003 준비 및 남은 실제 차단조건(특히 semantic criteria, 별도 approved-result 관리자 판단·승인, 별도 실제 실행 동의 필요 여부), TASK-003/004 미실행을 명시. 품질 검토 완료/대본 내용 정확성 입증을 주장하지 말 것. 필요한 최소 코드/테스트/보고서만 선택적 commit/push, `git diff --check`, 원격 main 확인.

**완료 기준:** 사용자가 수락한 실제 관리자 review proceed 제안 기록 + TASK-002 원본 대본 사용자 승인, TASK-003 실행에 필요한 조건을 정확히 파악. 실제 호출·자동 품질 검토·다음 직원 실행 **전부 0회**.
