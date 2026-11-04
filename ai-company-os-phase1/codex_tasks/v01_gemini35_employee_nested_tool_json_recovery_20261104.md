# AI Company OS v0.1 — Gemini 3.5 직원 content 내부 JSON 오류의 최소 복구

기준: 2026-11-04 KST. Codex **오프라인 개발 작업**. 실제 AI API 호출 금지.

## 최우선
`AI_COMPANY_OS_CORE_PRINCIPLES.md`, `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`를 먼저 읽고 기존 변경 및 전체 실행 흐름을 검토한다. **사용자는 목표만 제공**, AI 관리자가 계획/기준/검토/수정 판단, AI 직원이 작업. 앱은 시스템 안전·렌더 기능만 담당. UI나 별도 프레임워크/신규 공급자/부가 기능 개발 금지. **첫 실제 완주에 필요한 최소 변경만.**

## 실제 실패 근거
신규 3.5 최초 실사용 프로젝트:
- store: `data/gemini35-first-autonomous-20261104`
- id: `gemini35company-2b01639ee7284443b5c68dfdae206949`
- status stopped / phase work / reason invalid_model_json / artifacts 없음.
- 관리자 API attempt #1: HTTP200, completed, `role_result_status=validated`, response diagnostics JSON parsed.
- 직원 API attempt #2: HTTP200, completed, `role_result_status=json_parsed`, response diagnostics envelope parsed, finish stop, role JSON parsed, content_chars=703, tokens prompt1049/output324.
- 기존 3.1 실사용 및 Gemini 3.5 독립 진단 결과 보존.
- 따라서 외부 요청 자체가 실패한 게 아니라 **역할 JSON 검증 이후의 내부 content 처리 오류**. `autonomous_free.FreeCompany._call`의 `phase=='execute'`에서 `content.strip().startswith('{')`에 따라 `parse(content)`하는 코드가 가장 유력. 하지만 그 밖의 모든 `invalid_model_json` 발생 경로를 코드로 대조하고, 저장된 기록이 특정 코드 위치를 확정하는지 분명히 말할 것. raw employee content는 저장돼 있지 않아 구체적 문법 오류를 꾸며내지 말 것.

## 반드시 구현할 최소 수정
1. 현재 role JSON `{content,evidence,uncertainty}` 검증 성공과, 내부 content가 실제 `caption_video_v1` 도구 요청 JSON인지 여부를 구분. JSON으로 보이는 문자열을 모두 무조건 도구로 처리하는 구조가 왜 오류를 낳는지 확인. **정상적인 산문/예시 JSON과 실제 도구 요청을 구별**하되 악의적/잘못된 내용이 허용 도구 실행으로 넘어가지 않도록 엄격한 schema와 allowlist 유지.
2. 실패가 **직원의 도구 요청 형식 오류**라면, 앱이 임의로 JSON을 고쳐서 실행하거나 자막 길이/화면/품질 결정을 대신 하지 말 것. 직원의 실패한 결과를 기존 '도구 실패 → AI 관리자 review → 직원 revision' 루프로 보내 관리자가 수정/stop/operational permission 결정하게 할 것. 내부 파싱 실패는 정해진 안전 코드/단계로만 모델에 설명. API 결과 역할 JSON을 임의 성공으로 판정하지 말고 MP4 receipt/버전/검토 state를 정확히 기록. malformed content의 비밀이나 exception/raw response/key, 파일 경로를 로깅하지 말 것.
3. 기존 재검토 경로는 recoverable failure 분류가 제한돼 있음: `autonomous_free.py`, `autonomous_gemini.py`, `autonomous_gemini35.py`, `autonomous_company.py`, `local_artifacts.py`를 보고 최소 재사용 확장. 새 **Gemini35 신규 프로젝트**에만 추가 정책을 서명한 동의안으로 명시할 필요가 있다면 그렇게 하고 기존 프로젝트/동의/원장 소급 수정 금지. 일반 hard safety/data malformed errors와 API response 검증 실패는 기존 안전 차단. tool_request 구조가 불명확할 때 회사가 무조건 '성공한 산문'으로 취급해 버리는 누락도 방지.
4. 기존 도구 실패와 마찬가지로 API attempt를 재전송하지 않고 직원 결과가 관리자에게 영속적으로 전달되는 안전한 commit 경계, 중복 operation guard, manager review->employee revision, 최대 수정 수(task1,total2), 실패 기록 보존, 사용자 중간 결재0을 검증.
5. 오프라인 fixture: 정상 prose와 JSON 예시를 도구라고 오인하지 않는지, valid 도구 JSON은 렌더하는지, malformed nested tool spec이 안전 검토 자료로 전달되는지, manager revise→employee 새 올바른 도구 입력→실제 로컬 MP4→manager accept→인계→final report까지. 관리자 stop·수정 상한·일회성 원장·API 실패 보존·hard safety 회귀. 대규모 영상/프레임워크 변경 없음.
6. 실 Gemini API 호출 **0회**. 과거 store `data/gemini35-first-autonomous-20261104` 외 모든 기존 프로젝트/원장/백업 상태 **변경 0**; 실패한 3.5 프로젝트도 read-only. 잠겨 있거나 기존 active_operation이 있으면 초기화/재실행 금지.
7. 모든 타임스탬프 KST, `git diff --check`, 관련 unittest, 기존 기록 SHA256 전후 비교 및 변경 파일 선택적 커밋. 테스트 불완전하면 보고에 명시.

## 다음 실사용 준비
오프라인 한 사이클 성공 후 **신규 격리 Gemini 3.5 프로젝트를 prepare만** 진행 가능. 기존 비밀 없는 합성 목표 그대로, Google AI Studio Free Tier 조건/모델/구체적 동의 정책에 대해 새 리뷰 해시와 만료시간 보고. 이전 실패 프로젝트의 consent/used marker 복사 금지, 자동 retry 없음. **실제 execute는 사용자가 다시 명시적으로 승인한 뒤에만**.

## 결과 보고서
`reports/v01_gemini35_employee_nested_tool_json_recovery_20261104.md` (한국어): 실제 근거, 발생 코드 위치의 확정/추정 구분, 바뀐 내부 흐름, 최소 변경점, API 0회, offline E2E 및 안전 회귀, 기존 기록 보존, 새 프로젝트 준비 및 다음 필요한 단 한 행동. 사용자에게 신규 기능 개발 제안하지 않기.
