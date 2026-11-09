# AI Company OS Phase1: 도구 실패를 실제 AI 관리자 검토·직원 수정 루프로 연결 (첫 한 사이클 완주용 최소 기능)

기준일: 2026-11-04 KST. **이것은 Codex의 개발/오프라인 검증 지시서**이며, 실사용 Gemini POST나 기존 실패 프로젝트 재실행의 허가는 아니다.

## 절대 우선: 사용자 목표와 이미 저장된 원칙
읽기 우선:
1. `AI_COMPANY_OS_CORE_PRINCIPLES.md` 전체.
2. `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`.
3. 최근 보고서 `reports/v01_gemini_second_live_local_tool_failure_20261104.md`, `reports/v01_gemini_caption_overflow_first_live_recovery_20261104.md`, `reports/v01_gemini_autonomous_company_integration_ready_20261104.md`.
4. 실제 소스 `autonomous_company.py`, `autonomous_live.py`, `autonomous_free.py`, `autonomous_gemini.py`, `local_artifacts.py`, `gemini_first_project.py`, 테스트/원장/동의 구현.

사용자는 **최종 목표를 한 번 제시**한다. 실제 Gemini AI 관리자가 계획·업무 기준·검토·수정 판단을 하고 AI 직원이 실제 업무를 한다. 시스템/개발자/고정 조건이 영상의 자막 길이·줄 수·구성·미적 판단 등을 대신 결정하지 않는다. 미디어 인코더, 실제 화면 크기, 메모리·파일·보안 등 **기술적으로 반드시 필요한 기계적 검증**은 유지하되 이를 AI의 업무 판단으로 오해하지 말 것. 기술 제약을 AI에 안전하게 전달하고, 충돌 시 가능한 해결책은 **AI 관리자에게 결정하게** 할 것. 신규 사용자 업무 중간 결재 추가 금지.

**범위 최소화:** UI/대시보드/기타 공급자/전면적인 자기복구 프레임워크는 만들지 않는다. 단 하나의 첫 실사용 완주에 필요한 **local tool 실패 → 실제 AI 관리자 검토 → 직원 수정 → local tool 재시도 → 최종 MP4**만 기존 상태 기계에 연결한다.

## 현재 확인된 사실
첫 실사용 `data/gemini-first-autonomous-20261104`, `geminicompany-db22e41adcc4446d9904e44c363df5fc`: 관리자 plan과 직원 execute 각각 HTTP200, `caption_overflow`, stopped.
둘째 `data/gemini-caption-recovery-20261104`, `geminicompany-df65908337b04143b576e5cbfc076abb`: 관리자 plan과 직원 execute 각각 HTTP200, `local_tool_failed`, stopped. 두 프로젝트 모두 실제 employee 완결/manager review/MP4 없음. 기존 원장은 **불변 보존**. 두 번째 로컬 오류는 과거 명령 단계가 유실되어 미확정; 최근 수정으로 `LocalToolError` stage/category/exit_code를 미래 안전 이벤트에 기록한다. 합성 로컬 렌더 4조합 성공. `Gemini-3.1-flash-lite` 연결 자체가 실패한 것으로 추측하지 말 것.

코드에서 `autonomous_free.FreeCompany._call(phase='execute')`는 모델 역할 JSON을 이미 받고 난 뒤 spec의 `local_artifacts.execute`를 **manager review 이전에** 수행. local tool 예외가 `autonomous_company.Company._run_workflow`의 outer except에 도달하여 `stopped`가 되며 이미 completed된 API attempt와 active_operation은 남는다. 이 경계를 신규 안전한 내부 수정보류 상태로 바꾸는 것이 목표.

## 필수 개발
1. 최소 설계: 로컬 tool 자체의 **안전하게 분류 가능한** 실패(caption_overflow, narration_exceeds_scene, LocalToolError 고정 stage/category/exit_code 등)에 대해서만, 실패한 employee 응답/도구 요청의 업무상 의미와 validation 단계/분류 정보를 실제 Gemini manager review 입력으로 전달하는 경로를 추가. manager가 accept(그 경우 물리적 MP4가 없으므로 허용되지 않음)/revise/stop/operational permission을 **스스로 판단**. 성공하지 않은 tool을 성공했다고 증명·저장하지 말 것. 실패한 직원 산출물의 상태는 '실패한 시도/검토 자료'로 정직하게 저장하고, accepted employee result/MP4로 오인하지 않도록 설계. 기록에는 원래 모델 응답 body/비밀키 등을 과도하게 넣지 않되, 원본이 기존 저장 정책에서 합법적으로 남아야 하는 경우 기존 무결성·외부 전송 동의 범위 안에 유지. 기술 오류 정보는 fixed enum과 숫자 코드만, stderr/exception 메시지/경로/환경/헤더/키를 기록·전송하지 않는다.
2. 기존 `Company._run_workflow`의 `awaiting_ai_review` / `revision_requested` 상태, `validate_review`, task당/전체 revision 상한을 **재사용**. 만약 `review` 컨텍스트의 result 스키마/근거에 실패 메타데이터를 추가해야 한다면, Gemini 전용 최소 확장 또는 안전한 evidence envelope로 연결하고 정확한 `_call` 허용 키/JSON 스키마/서명된 동의 범위를 점검. 사용자 승인 범위에 없는 외부 데이터로 확대하지 말 것. 실패 정보가 다회 Gemini 호출 동의에서 허용된 기존 generated employee results/reviews에 속한다고 확인될 때만 차후 실제 사용.
3. 성공/실패 API attempt와 role_result_status 전이, `active_operation` 해제는 신중하게. **응답 수신·role JSON 검증 완료와 local tool 실패를 분리**하여, 이미 완료된 API 요청은 중복 전송하지 않고 도구 오류 후에도 정상적으로 manager review를 호출할 수 있어야 한다. 기존 미확정·실패 API 응답, 토큰 비용/쿼터·rate limit, 중복 실행·hash·권한/동의는 절대 느슨하게 하지 않는다. local tool 복구는 API 네트워크 재전송/자동 fallback으로 간주해 무제한 retry하지 않는다. 과도한 원장 schema 변경이나 기존 프로젝트 마이그레이션 금지; 새로운 독립 프로젝트에만 적용.
4. 직원 수정은 manager의 구체적 피드백을 받아서 이루어져야 함. Python에서 임의로 내용/자막/영상 품질 기준을 결정하거나 자막을 단순 잘라내서 통과시키지 않는다. 시스템은 작업 실패의 기술적 조건만 알려줌. 현재 caption reflow 등 기존 기술 처리 로직을 무작정 제거/변경하지 말되 사용자 기본 원칙과 충돌을 분석해 보고서에 명시. AI가 물리적 렌더 검사를 완전히 무시하는 것도 금지.
5. 내부 복구가 아닌 종류: API 401/403/429/503/timeout/비용/쿼터 부족/불확실한 전송·동의 만료/운영 권한 문제, 파일 안전 경계 위반 등은 기존대로 안전 중단·보류. 전 직원 완료 없이 최종 전달 금지. 도구 재시도나 AI 검토가 quota/stagnation/revision/time limit를 넘으면 정지하고 상황 보존.
6. MP4 존재·디코딩/메타데이터/원장 receipt와 manager 최종 판단은 분리해 검증. 사전 제작된 테스트 결과/fixture를 진짜 AI 결과물로 둔갑시키지 않음.
7. 가짜 manager→employee가 첫 tool 요청에서 실패(caption_overflow, local_tool_failed)→manager review에서 수정 요청→employee 수정→실제 로컬 renderer MP4→manager accept→다른 직원에 선행 결과 전달→finalize 하는 **오프라인** end-to-end를 최소한의 테스트로 검증. 수정 한도 초과, 관리자 stop, hard safety failure, manager review API 실패 시 원장 불변 및 보호 동작도 핵심 회귀. 테스트 fixture의 manager 선택은 AI 실사용에서 강제되는 정책이 아님을 보장.
8. 기존 Groq/OpenRouter 및 다른 Gemini 계약 회귀 영향을 확인. 보존 파일 SHA 비교, `git diff --check`, 필요한 범위 tests. 실제 AI API 요청 **0회**, 기존 실패 프로젝트 execute/run/continue/approve 0회. Git 소스/테스트/보고서 중 비밀 없는 파일만 선택적 commit/push. reset/clean/force push 금지.

## 최초 완주를 위한 후속 준비
- 위 오프라인 작업/테스트가 통과하면 `gemini_first_project.py --store <NEW_PATH> prepare` 등 **기존 기능으로 새 독립 프로젝트의 동의안 준비만** 할 수 있다. 새 프로젝트의 목표는 기존과 동일한 *비밀 없는 AI 질문 작성법 영상*, 실제 모델은 `gemini-3.1-flash-lite`, 사용자 Google AI Studio 무료 등급 조건 재검토. 새 계약에 대한 실제 사용자의 별도 실행 동의를 기다린다. 과거 해시·소진 표식을 재사용하거나 consent 승인한 척하지 말 것.
- 사용자에게 **정확히 필요한 후속 절차 하나**를 명시하고 가능하다면 신규 프로젝트의 만료 시각(KST), review hash, 실행 명령을 결과 보고서에 담되, 이번 Codex 지시로 실제 AI 협업을 실행하지 않는다. 최초 계획→직원→review→최종 MP4/보고서의 실제 완주는 다음 사용자 승인 실행으로 검증한다.
- `reports/v01_gemini_internal_tool_failure_manager_revision_20261104.md`에 한국어/KST로 변경점, 상태 전이, 고정 기준과 AI 결정의 구분, API 실제 0회, 오프라인 fake scenario 결과, 실제 기존 프로젝트/데이터 보존, 다음 1회 실사용 준비 상태 및 blocker를 보고.
- 성공하지 않은 테스트 또는 풀리지 않는 구조/보안 충돌을 숨기지 말고, 어디까지 구현했는지 구체적으로 적는다. 추가 추상 프레임워크나 과도한 범위의 개발로 첫 완주 목표를 미루지 않는다.

## 최종 완료 정의
이번 코드 구현 완료 = **기존 AI 엔진 안에서 '도구 실패'를 직원-관리자 내부 의사결정/수정 사이클로 처리할 수 있고, 오프라인 엔드투엔드가 통과하며, 실제 새 프로젝트 동의/실행 전 단계까지 준비된 상태**. 실제 Gemini 전체 사이클 성공은 별도 실행 후 확인한다.
