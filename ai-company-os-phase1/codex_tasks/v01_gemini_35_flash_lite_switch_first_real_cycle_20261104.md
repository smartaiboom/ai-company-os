# AI Company OS — 검증된 Gemini 3.5 Flash-Lite로 최소 전환 및 첫 실제 완주 준비

2026-11-04 KST. **Codex 개발 지시서**, 실제 유료 또는 무료 AI API 호출 허가가 아님.

## 최우선
- 사용자 최상위 원칙 파일 `AI_COMPANY_OS_CORE_PRINCIPLES.md`, `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md` 먼저 읽고 준수.
- 사용자는 **목표만 입력**; 실제 AI 관리자 계획/품질 기준/판단→실제 직원 업무/오류 시 관리자 검토·수정→인계→최종 산출물. 프로그램/개발자/Codex가 자막·영상 미적 기준을 임의로 결정하지 않는다.
- 지금 최우선은 **첫 실제 한 사이클 완주**. 범용 자동복구, UI, 다른 공급자, 대시보드, 추가 미디어 기능은 금지. 기존 기능 최대 보존, 변경은 공급자 모델의 최소 호환 전환만.
- 실제 Gemini API 호출 0회, 기존 프로젝트 실행/재실행/초기화/동의 재사용 0회, 백업/원장/키/이전 실패 프로젝트 원본 변경 0.

## 실사용 근거
과거 모델 `gemini-3.1-flash-lite`: 첫 두 실제 프로젝트에서 관리자·직원 각각 성공 HTTP200(총 4회), 뒤 로컬 caption_overflow/local_tool_failed로 정지. 세 번째 프로젝트는 관리자 계획 단계 HTTP503 UNAVAILABLE. 동일 모델의 독립 연결 진단에서도 152 bytes 인사, 4143 bytes 관리자 형식 둘 다 HTTP503 UNAVAILABLE/약1.5초.
**새 모델 `gemini-3.5-flash-lite`**: 동일 Codespaces/API 키 환경에서 별도 단건 검증 HTTP200/1.09초, 187 bytes, STOP; 관리자의 실제 구조와 유사한 schema JSON 진단 HTTP200/3.22초, 4274 bytes, 641 입력 토큰/852 출력 토큰, `manager_plan_structure=true`, STOP.
새 모델이 1회씩 성공했을 뿐 전체 프로젝트 완주/지속 안정성은 아직 미확인.

기존 관련 파일: `gemini_provider.py`의 MODEL/ENDPOINT/코스트 정책 및 GeminiFreeAdapter, `autonomous_gemini.py`의 GeminiStore/GeminiConfig/GeminiCompany와 서명된 공급자/도구 검토 정책, `gemini_first_project.py`의 별도 `--store` 준비/실행, `autonomous_live.py`, `autonomous_free.py`, `role_json_schema.py`, `local_artifacts.py`, `ai_safety.py`, `tests/test_internal_tool_review.py`, 기타 관련 tests.
진단 스크립트 `diagnostics/gemini_35_lite_connection_once_20261104.py`, `diagnostics/gemini_35_lite_manager_shape_once_20261104.py`는 소모성 증거로 보존.

## 해야 할 일
1. 현재 Gemini 3.1에 고정된 코드 경계/테스트/운영 동의 계약/모델 검증을 검토한 뒤 **새로 생성하는 프로젝트에만 Gemini 3.5 Flash-Lite가 적용**되도록 최소 패치. 기존 Gemini 3.1 프로젝트의 model/endpoint/consent/status/hash를 변경하거나 가짜로 호환시키지 말 것. Store 정책 버전·모델 binding이 기존 stopped 상태의 무결성 load를 깨면, 기존 binding은 그대로 두고 별도 v3.5 adapter/config/store/launcher 또는 버전 격리의 작은 호환 계층을 쓸 것. 과거 프로젝트에 대한 과도한 마이그레이션 금지.
2. Google 모델의 공식 정확한 ID, Free Tier 적용 조건, native generateContent의 structured JSON/schema 지원을 확인(이미 독립 진단 성공). 다른 서비스/유료 모델 fallback 없음. 무료 조건이 정확히 입증되지 않거나 문서/실제 정책이 충돌하면 **실행 준비만 하고 사용자에 사실관계 명시**, 실제 호출 금지.
3. 관리자/직원/검토/finalize 모두 동일 새 모델 binding, output strict schema, 기존 오류 진단, manager-directed local tool revision, tool receipt/MP4 provenance 보존. `Gemini 3.5`가 plan 결과를 반환한 단건 진단은 **가상 회사 실행은 아님**.
4. `python -B -m unittest ...`로 새 모델 계약/동의 hash/기존 Gemini 3.1 저장소 load·새 3.5 저장소 격리/role schema/fake manager→employee→tool failure→manager revision→employee fix→local real MP4→final report 검증. 실제 외부 AI 호출 0회. 기존 실패 저장소/원장 읽기만 하며 불변 SHA256 보존; active_operation이나 used markers 재설정 절대 금지.
5. Git diff --check 및 관련 회귀. 사용자의 미추적 데이터/기존 백업 삭제·초기화 금지. 소스+테스트+보고서만 선택적 commit/push.
6. 독립적인 새 3.5 프로젝트를 기존 **비밀 없는 합성 목표**로 `prepare`만 진행할 것(무료 등급 정책·새 서명 동의가 성립할 때). 기존 goal/plan/직원 결과를 복사하지 않음. API 실제 요청은 **절대 하지 말 것**. user confirmation 등 동의 flags를 사칭하여 execute 하지 말 것.
7. 한국어 보고서 `reports/v01_gemini_35_switch_first_real_cycle_ready_20261104.md` 작성. 변경 파일·기존 데이터 보존·테스트 결과·Free Tier 검증 범위·새 프로젝트 모델/endpoint/tool_failure_review 정책·goal/전송 범위·유효기간(KST)·review hash 및 **사용자가 새 프로젝트의 최초 실행에 동의한 뒤 Codespaces 터미널에서 실행할 정확한 명령**을 제시. 블로커가 있으면 이유를 숨기지 말 것.

## 완료 기준
기존 Gemini 3.1 관련 실행 상태를 보존하면서, **새 Gemini 3.5 Flash-Lite 프로젝트만** offline 검증된 manager↔employee workflow와 도구 자율 복구를 사용하여 새 사용자 동의 후 실사용할 준비가 된 상태. 실제 MP4 완주는 그 뒤 사용자 승인 단 한 번의 신규 실행에서 확인. 다른 기능 구현 금지.
