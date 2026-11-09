# AI Company OS — 첫 실제 무료 AI 응답 미완료 원인 진단·안전 복구 준비 (오프라인 작업)

## 배경 / 보고서 원문 확인
먼저 `AI_COMPANY_OS_CORE_PRINCIPLES.md`, `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`, `reports/v01_real_free_ai_video_one_cycle_20261104.md`, `reports/v01_real_free_autonomous_video_smoke_prepare_20261103.md` 및 실제 공급자 수신/검증/영속 원장/무료 AI 관리자 호출 경로를 전체적으로 읽는다.

2026-11-04 첫 승인된 프로젝트 `freecompany-ae4aa334511d470c8c517685e9902a53`에서 실제 `openrouter/free` 관리자 plan 요청 **정확히 1회** 송신, HTTP 응답 완료, `usage.cost=0` 검증, 그러나 `finish_reason == stop` 검증 불통과로 `incomplete_response`에서 stopped. 응답 원문/정확한 finish_reason은 저장되지 않아 **사후 확정 불가**. AI 직원 0회, MP4 0개, active_operation/원장에 completed-but-unvalidated 상태를 보존하고 있다. 기존 프로젝트 `cb44b605b498` 9/20 및 `c85d9853906a` reserved 1 등은 절대로 변경하지 않는다.

## 사용자 목표 / 이번 Codex 개발 위임
사용자는 실제 AI 회사가 최초 목표 한 번으로 관리자 계획→직원 업무→검토/수정→MP4 영상 최종 산출까지 가는 것을 원한다. 현재 걸림돌인 **실제 provider 응답 중단을 진단 가능하게 만들고, 정상 중단·복구가 중복/비용/개인정보 위험 없이 일관되도록 전체 관련 경로를 개선**하라. Codex가 구조 분석→개선→테스트→보고까지 한 번에 진행한다. 질문을 업무별 사용자 승인으로 돌리지 않는다.

**이번 지시에서는 추가 실제 OpenRouter 호출 0회, 기존 실패 프로젝트 승인 재사용하여 재실행 0회, 유료 API 0회.** 사용자의 앞선 명시 승인은 위 프로젝트의 최초 1회 run을 이미 허용한 것으로, **실패 operation에 대한 무제한 추가 전송/자동 재시도 권한을 새로 부여한 것이 아니다.** 실제 재송신은 별도 검토·명시된 복구 범위 후에만 할 것.

## 수행 요구
1. **응답 계약 진단:** 현재 `OpenRouterFreeAdapter`, transport, `request_json`, manager/worker role validation, JSON parsing, `finish_reason`, `usage.cost`, 공급자 오류 envelope/토큰 제한과 요청 `response_format` 및 가격 0 옵션을 코드로 추적. 최초 오류의 가능한 원인을 분류하되 실제 `finish_reason`을 알 수 없음을 인정. 실제 OpenRouter의 모든 모델/응답이 강제 JSON/stop 지원한다는 근거 없는 가정을 제거하거나 진단 가능하게 할 것. 안전한 가격0·fallback 금지·비밀키 보호 절대 완화 금지.
2. **개인정보 없는 bounded 진단 정보:** 앞으로 발생하는 응답에 한하여 `finish_reason`의 안전하게 허용된 문자열/분류, 제한된 토큰 사용량, content 유무/길이, 구조적 JSON 파싱 여부, provider request id 등 개인정보 없는 필드만 필요 최소한으로 기록. 응답 본문·헤더·비밀키·프롬프트 전체·직원 산출물 원문을 디버그 로그에 쓰지 않음. cost가 검증되지 않은 경우 재시도 금지. 현재 과거 첫 응답에 대해 실제 값을 복구한 것처럼 꾸미지 않음.
3. **길이·응답 조건:** 정상 모델이 작업을 수행할 현실적인 출력 토큰 길이/plan 복잡도/JSON schema 부담을 점검하고, 코드/요청 계약에 있는 명백한 불일치를 안전하게 보완. 모델이 길이 제한으로 중단됐을 경우 출력이 불완전함을 관리자 정상 계획으로 승격하지 말 것. 모델 출력이 중간에서 끊긴 경우를 자동 무제한 이어쓰기하거나 가격0 검증 없이 수락하지 말 것. 응답이 이미 완료됐으나 비검증인 이번 실제 원장의 모델 내용을 임의로 만들어 덮어쓰거나 업무 완료로 승격 금지.
4. **실패 복구의 설계와 검증:** reserved, sent, completed but unvalidated, failed, ambiguous, crash after receive의 상태 구분 및 동일 operation 중복 전송 방지. **기본은 재송신 없이 중단**, 실패 원인별로 회복 가능성을 판단하는 별도 명시 `recovery proposal` 또는 동등하게 안전한 절차를 제안/구현. 새 모델 호출이 필요하면 명확한 승인 범위와 최대 추가 시도/코스트0·프로바이더 쿼터·중복 방지가 필요. 신규 프로젝트 재생성을 자동 workaround로 쓰지 않는다. 실제 사람에게 품질 승인 반복을 요구하지 말고 운용 예외/재전송 승인만 분리하라. 정상 clean checkpoint resume은 completed-but-unvalidated 응답의 재전송 권한으로 해석하면 안 된다.
5. **오프라인 검증:** fake transport로 stop 정상, length/tool/unknown finish, 응답 누락, 거절/429/402, cost 0/누락/양수, JSON 불완전, 긴 응답, crash/재진입/중복 호출 방지, recovery 미승인 차단 등 핵심 경우를 검사. 초기에 성공했던 mock MP4 파이프라인/자율 무료 22건 시나리오와 legacy 2/20 모드는 보존. 가능하면 전체 회귀 실행. 무료 OpenRouter 환경의 실제 API 호출·외부 네트워크 진단 0회 유지.
6. **실패 원장 보존:** 위 실사용 프로젝트 상태 `stopped/plan`, `active_operation`, 원장 완료-but-unvalidated, 승인 기록, 원래 목표 hash/비용 0 확인 등 **전부 읽기만**. 다른 실사용 프로젝트/백업, 저장 데이터, `.env`, 키, 사용자 미추적 파일, 이전 MP4도 수정/삭제/초기화 금지. Git reset/clean/force push 금지.
7. **보고서:** `reports/v01_real_free_provider_response_recovery_20261104.md`에 (a) 진짜 확인된 원인 vs 미확정 원인 구분, (b) 수정 파일 및 요청/응답 계약의 보완, (c) 실제 재시도 없이 오프라인 테스트한 근거, (d) 기존 원장 보존 및 테스트 결과, (e) **다음 실제 테스트에 필요한 정확한 추가 승인 또는 새 실험 프로토콜**을 제시. 실패 원장의 불확실 상태를 안전하게 다룰 수 없는 경우 "불가능"이라고 명시. 원본 secret/raw payload/콘텐츠 출력 금지.
8. `git diff --check`, 필요한 파일만 선택적 커밋·푸시, 원격 보고서 확인. 대시보드 개발/영상 외부 유료 API 확장 금지. KST와 한국어 작업/보고.

## 완료 기준
실패 원인이 더 이상 `incomplete_response`라는 추상 코드 하나로만 남지 않고 **향후 응답의 종료/토큰/구조를 안전하게 구분**할 수 있어야 한다. **한 번의 불완전 응답에 대한 무단 자동 재전송 없이** 수정한 경로가 fake HTTPS로 검증되고, 현재 실사용 원장은 그대로여야 한다. 재시작/실사용 한 사이클 완료를 이번 오프라인 개발 작업에서 주장하지 않는다.
