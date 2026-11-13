# 2026-11-13: HTTP200 이후 script_plan_handoff_required 단일 장애 수정

## 절대 우선
사용자는 실제 AI 회사의 관리자→대본직원→편집직원 협업을 완성하고 싶다. 11/13 10:08:31~36 KST의 재기획 호출은 **HTTP200/completed/json_parsed**였다. 따라서 503/키/모델/API 연결 오류가 아니다. API가 정상 결과를 반환했지만 내부 기획 채택 또는 대본 직원 인계에서 `script_plan_handoff_required`로 중단했다. **이번 개발에서 실제 Gemini 호출0회**, 기존 실패 job 재실행·기존 consent 재사용 금지. UI/예산/신규 복구 흐름 개발 금지. 한 번에 코드상 문제 확인 후 정확히 고쳐라.

## 실제 원장
- 현재 컷룸 프로젝트 `company-aba553f29cfb454c8c05bad4abb49969`, data/video_representative_workflow/studio/의 실제 프로젝트·representative_rework 원장.
- 현재 사용자가 제공한 attempt: phase=plan, task_id=null, status=completed, HTTP200, role_result_status=json_parsed, reserved_at=2026-11-13T10:08:31+09:00, finished_at=10:08:36+09:00, response_hash=499d626e743a93e9e04859c0e18daf388d387ab213c63bb329d9dd379499cdaf, request_hash=9d489264a93012f16a97dee9edea510d4ac3180042d664af10327364268450f1. error=script_plan_handoff_required. 이전 11/12·13 HTTP503, 11/12 HTTP200 invalid_dependencies와는 다른 원인.
- 확인된 코드 흐름: core/autonomous_company.py::_run_workflow의 plan branch는 `proposed=self._call(...plan...)` → `validate_plan(proposed)` → assignments writer/editor 생성 및 phase='work'. `companies/video/representative_rework.py`는 재기획 result에서 `replan` 추출 및 validate_rework_plan, writer/editor 역할 검증. 현재 main 코드에 error 이름의 문자열 검색이 되지 않을 수 있으니 **실행 중 local code/AGENTS.md 및 인계 계약 전후를 직접 찾고 오류 유발 함수를 반드시 확인**, 복구 불가능한 raw provider response는 복구했다고 주장하지 말 것.

## Codex의 필수 작업
1. 먼저 **실제 실행 중인 로컬 코드에서 `script_plan_handoff_required` 문자열을 grep/rg**하고 발생 함수/조건/stack을 확인; 같은 이름이 없으면 local git SHA와 실제 서버 프로세스 구동 코드·환경·module path 비교. 첫 성공 응답이 schema와 의미 검증 후 계획으로 채택되었는지 확인하고, 오류가 원래 v1 script와 새 v2 인계 경로 혼용/미션 전용 precondition/plan reference 바인딩 문제인지 판별. 기술적 추측을 원인 확정이라고 보고하지 말 것.
2. 실제 job과 관련 참조를 **읽기 전용** 조사: plan null/assignments 비어 있는지, completed attempt만 남았는지, role_result_status=json_parsed 이후 어떤 서버 조건에서 raise됐는지, model output 보존여부와 hash. 필요하면 기존 synthetic response fixture를 사용해 오류를 오프라인 재현. raw response 전문이 기록되지 않았으면 '복구 불가'라고 보고. **이미 호출을 소비했으니 동일 job 다시 실행/자동 재시도 금지**.
3. 정확한 원인이 `script_plan_handoff_required`일 때 **해당 module/기획→직원 인계 조건만 최소 수정**: 현재 재작업 plan은 동의된 replan + writer→editor 두 역할 계약이며 원 목표/대표 피드백과 이전 버전 v1 참조를 갖는다. 기존 production script plan 계약의 잘못된 재사용이나 인계 전제 때문에 새 plan을 막는다면 동일 project의 rework 경로에 맞춰 안전하게 수정. 정상 유효 조건은 통과시키되 미승인/무결성 오류/부족한 참고자료는 거부, 무조건 true/validation 삭제/기획 생성 위조 금지. source 제약/결과물 품질 검증 유지. plan 응답에서 검증 실패를 구체적으로 기록하되 raw goal/키/피드백 유출 금지.
4. 변경이 승인된 전송 계약/서명에 영향을 주는지 점검. 영향 있으면 신규 서명 동의 필요, 구 동의 재사용 금지. 영향 없더라도 **현재 실패 job은 절대 재실행하지 않음**. 다음 실제 호출 필요하면 사용자에게 새 승인된 job만 허용하고 반복 승인용 UI 기능 증설 금지.
5. **관련 오프라인 표적 단일 테스트**: 실제와 동등하게 valid plan JSON 수신 → manager plan 채택/assignments writer/editor 생성 → writer 결과/manager review → editor/manager review → 같은 컷룸 v2 대표 승인 대기. 같은 인계 조건의 비정상 plan도 거부하고 원본/동의/attempt 불변. 외부 AI0, mock/fixture는 실전 성과로 표시하지 말 것. 기존 합성 성공 API 응답 실 데이터를 찾아내지 못하면 내용을 조작해 실전 성공으로 가장하지 말 것.
6. reports/FIX_SCRIPT_PLAN_HANDOFF_AFTER_HTTP200_RESULT_20261113.md 짧게 기록: **정확한 오류 발생 파일/조건**, 왜 HTTP200인데 중단했는지, 수정 파일/수정 내용, 표적 테스트 결과, 실제 API0회, 사용자에게 가장 적은 단계의 다음 행동 하나. commit/push/readback 후 종료.

## 엄격 금지
기존 회사 데이터, 실패 job, HMAC/grants/attempts, 서명, 기존 영상·음성/대본, data/backups/artifacts/.env 및 미추적 파일 모두 보존. git clean, reset --hard, force push 금지. 무료 조건 반복 확인/다른 모델 전환/유료 전환/재시도/대용량 추가 시스템 만들기 금지. KST. AGENTS.md 우선.
