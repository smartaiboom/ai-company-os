# AI Company OS v0.1 — 실제 관리자 proceed 승인 기록 및 TASK-002 실제 AI 직원 최대 1회 실행

## 사용자 명시 승인 및 작업 범위
2026-11-03 사용자는 다음과 같이 직접 승인했다.
> “프로젝트 cb44b605b498의 실제 AI 관리자 proceed 제안은 승인합니다. TASK-002 실제 AI 직원 호출 최대 1회는 승인. 승인된 경우 기존 예산과 보안 원칙을 지키고 TASK-003 이후는 실행하지 않도록 Codex 작업 지시서를 GitHub에 작성해 줘.”

**이 승인으로 허용된 동작은 정확히 두 가지**다.
(1) 이미 실제 AI가 생성·저장한 TASK-001 → TASK-002 proceed 제안 1건을 기존 `respond_manager_decision(..., response="approve")`로 승인 기록.
(2) 기존 프로젝트 `cb44b605b498`의 **TASK-002 한국어 1분 영상 대본 작성**을 `openrouter/free` 실제 AI 직원으로 **최대 1회만** 실행하여 결과를 프로젝트에 저장. 외부 전송 허용 데이터는 승인된 프로젝트 목표, TASK-002 업무 정의, 사용자 선호, TASK-001 승인 조사 결과, 사용자가 승인한 AI 관리자 판단·지침 등 이 작업 수행에 필요한 최소 범위. 사용자 질문/승인/실행을 다른 작업으로 확대하지 않는다.

**절대 금지**: TASK-003 품질 검토, TASK-004 제작 패키지, 추가 AI 관리자 호출, TASK-001 재실행, 자동 재개/전체 workflow run, 사용자 대신 TASK-002 결과 승인, 추가 실제 호출, 자동 재시도, 유료 모델/대체 모델/다른 프로젝트 실행. 이번에는 TASK-002 대본 결과를 **사용자 검토 대기**로 남긴다. 외부 모델의 주장·기능 정보는 미검증으로 취급하고 확인되지 않은 기능·출처를 사실처럼 확정하지 않는다.

`codex_tasks/README_KOREAN_LANGUAGE_RULE.md` 준수, 지시·보고서는 한국어, KST(+09:00), 데이터/백업/기존 guard/미추적 파일 보존. reset/clean/force push 금지. `git pull --ff-only` 후 관련 소스·테스트·`reports/v01_real_manager_third_authorized_call_20261103.md` 먼저 확인. 최소 구현·테스트·실제 1회·보고서로 종료하고 전체 구조 개편/추가 진단 UI/영상 전용 로직 개발 금지.

## 필수 사전조건 — 불일치 시 실제 AI 호출 금지
- 실사용 Git 제외 `data/video-real-plan-20261103/projects/cb44b605b498.json`: 현재 `real_ai.attempts` 정확히 5건 모두 completed, failed/reserved 0, 20회 상한·잔여 15회, 마지막은 TASK-001 실제 관리자 3차 호출. 기존 1~3차 관리자 승인·guard·이력 모두 보존. 사용자 승인 TASK-001 결과 SHA256 `95e366272746a507f26f3776db5e6e5211126ae0f1f7d2b7712a718e5cff6802`, 승인 계획·선호 동일, TASK-002~004 대기·결과 없음.
- `manager_decision_view(project_id)`에서 **실제 모델 제안 정확히 1개**, provider=`real_openrouter_free`, action=`proceed`, payload.next_task_ids에 **TASK-002**, status=`pending_user_decision`, stale=false, 관련 binding이 현재 승인 TASK-001 결과/계획과 일치. proposal_id와 `expected_hash`를 **현재 실사용 상태에서 읽어** 기존 `respond_manager_decision`에 전달. 값 추측·하드코딩 금지. 제안 내용과 관리자 guidance는 변경하지 않는다.
- 사용자 승인과 별개로 **실제 TASK-002 직원 호출에 대한 단일 사용 승인 감사 기록**을 남기되, 같은 사용자 문장을 재실행에 재사용하지 못하게 고유 authorization ID, KST, 프로젝트/업무/관리자 proposal_id·승인 결과 지문, 최대 1회, 모델, 전송 범위, 사용자 원문을 기록. 기존 3차 관리자 추가 승인과 혼동하지 말 것. 기존 프로젝트 저장 방식·lock·atomic save·감사 형식 준수.
- `app.execute_project_task`, `manager_decision.require_proceed`, `execute_task` 실제 엔진, `ai_safety.request_json`, `check_project_permission`, `request_scope`, 기존 단일 실제 직원 실행 경로를 먼저 확인. TASK-002가 관리자 승인된 TASK-001 결과와 실제 관리자 guidance를 `previous_results`로 전달하는지 확인. 직원 실행 경로가 안전하지 않다면 최소한의 프로젝트 전용 로컬 owner runner를 만들되, 기존 프로젝트의 모든 직원 실행 권한을 넓히지 말 것.
- data/backups/guard/관측 파일 사전 목록·SHA 확인, 실행 중인 worker 및 미확정 예약 여부 확인. 다른 프로젝트 `c85d9853906a`의 기존 미확정 예약 불변. 키 값/실사용 JSON/전체 프롬프트 출력 금지. `AI_MODEL=openrouter/free`, 고정 `https://openrouter.ai/api/v1`, 무료-only/프록시·리다이렉트 차단/요청당 1회/기본 20회 및 시작당 최대 2회 규칙 유지.

## 안전한 실행 순서
1. **오프라인 검증**: 임시 프로젝트·fake transport·가상 키·네트워크 차단으로 실제 관리자 proceed 승인 저장, TASK-002 1회 단독 실행/결과 저장/사용자 검토 대기, TASK-003·004 미실행, 5→6/20 예산 fixture, 입력에 승인된 TASK-001과 관리자 guidance가 전달됨, guard·중복 승인·중복 호출·원장 경합·프로젝트 변경·미확정 예약·timeout/실패/예산 초과 시 무재시도·다른 프로젝트 불변 검증. 기존 관련 집중 회귀 테스트 포함. 안전성 테스트 실패 시 실제 호출하지 말 것.
2. **실사용 관리자 제안 승인 기록**: 최신 제안/지문을 다시 읽고 `respond_manager_decision(..., "approve")` 호출. 실제 AI 요청 **0회**. 승인 기록을 다시 읽어 proposal.status=`approved`, decided_by=`사용자`, guidance binding 유효 확인. 이미 승인 상태인 경우 중복 승인 시도하지 말고 읽기 전용으로 정지/보고; 이 지시서 자체를 재실행하여 직원 호출을 재허용하지 말 것.
3. **실사용 TASK-002 1회**: 별도 고유 O_EXCL guard와 Git 제외 관측 파일, 전송 횟수 기록을 **실제 전송 전에 영속화**. 승인된 단일 프로젝트/업무/제안과 원장 정확히 5건 확인 후, `manager_decision.require_proceed` 통과한 실제 TASK-002를 **기존 검증된 직원 executor**로만 호출. 선예약 원장 6번째 항목이 TASK-002, model=openrouter/free, status=reserved인 경우에만 transport 1회 허용. 요청 타임아웃 뒤 worker가 살아 있을 수 있으면 중복 실행 금지, 원장/guard/관측만 확인. **모델의 응답이 한국어 1분 영상 대본인지 결과를 의미적으로 관찰하되, 모델이 제시한 내용·분량을 코드로 강제 수정하지 말 것**. 성공 시 TASK-002 결과 저장 및 검토 대기 상태를 재조회. TASK-003/004는 실행하지 않는다. 자동 workflow 실행·재개 금지.
4. **안전한 실패 처리**: 승인 기록은 완료됐으나 TASK-002 실제 호출 전 사전조건 실패 시 호출 0회, 예산 5/20 불변, 상태를 보고. 전송 후 실패/타임아웃은 예약/원장 상태를 그대로 보존하고 추가 호출 금지. 요청 실패를 성공으로 표시하지 말 것. 기존 5건 attempts/기존 관리자 승인·제안·TASK-001 결과를 절대 삭제/수정하지 않는다.
5. **보존 검증**: 기존 data/backups/guard/미추적 파일 사전·사후 SHA 비교. 대상 JSON에서 승인 기록, 단일 TASK-002 시도/결과·감사·갱신 시각 등 허용된 변경 외 모두 불변. 다른 프로젝트/백업/기존 guard 전부 불변. 추가 승인 기록을 만들기 위한 전면 schema 개편 금지.

## 보고·완료 기준
`reports/v01_manager_proceed_approved_task002_real_once_20261103.md` 작성. 한국어로 사전조건/승인 proposal ID·상태(민감값 제외)/승인 시각 KST, 코드 변경과 테스트 명령·수·결과, TASK-002 실제 transport 0/1회·시작/종료 KST·재시도 0, 예산 5/20→실제 최종, 원장 상태/guard, TASK-002 상태/검토 상태 및 **생성 대본의 실질적 내용 요약 또는 안전한 발췌**(성공한 경우), TASK-003/004 미실행, 사용자 검토 필요사항, 데이터/백업 보존을 명시. 실사용 프로젝트 JSON 전체, API 키, 모델 원문 전체, 민감 프롬프트/로그 Git 금지. `git diff --check`, 집중 테스트 후 필요한 코드/테스트/보고서만 선택적으로 commit/push, 원격 main 확인.

**성공 기준**: 실제 AI 관리자 proceed 제안 1건을 사용자 승인으로 기록, **TASK-002 실제 AI 직원 요청 1회 이하**로 한국어 1분 대본을 생성·영속 저장, 사용자 검토 대기, TASK-003/004 및 추가 관리자/직원 호출 0회. 사용량은 전송이 실제 1회 완료되면 예상 **6/20, 잔여 14**. 실패/미확정은 실제 원장 그대로 보고하고 재시도 금지.
