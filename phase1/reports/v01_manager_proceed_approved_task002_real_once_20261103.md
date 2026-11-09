# 실제 관리자 proceed 승인 및 TASK-002 실제 직원 1회 실행

2026-11-03 KST. `git pull --ff-only`로 main f40f3ee를 반영하고 지정 작업을 수행했다.

**성공: 실제 관리자 제안 1건을 사용자 승인으로 기록하고, openrouter/free 직원 요청 1회로 TASK-002 한국어 대본을 생성·저장했다. 결과는 사용자 검토 대기이며 승인하지 않았다.** TASK-003/004, 추가 관리자 호출, TASK-001 재실행, workflow 실행은 모두 0회다.

## 사전조건 및 승인

실사용 프로젝트 cb44b605b498의 원장은 5/20, completed 5, failed/reserved 0이었다. TASK-001 완료·사용자 승인과 결과 SHA-256 `95e366272746a507f26f3776db5e6e5211126ae0f1f7d2b7712a718e5cff6802`, TASK-002~004 대기·결과 없음을 확인했다. 기존 1~3차 관리자 승인 및 guard/관측을 보존했다. 실행 중인 AI worker는 프로세스 목록에서 발견되지 않았다. 환경의 무료 모델·고정 OpenRouter 주소·키 존재를 확인했으며 키는 출력하지 않았다.

manager_decision_view로 실제 제안 1개, real_openrouter_free, proceed, TASK-002 직접 후속, pending_user_decision, stale=false를 확인했다. 현재 조회에서 얻은 proposal_id 및 expected_hash를 기존 respond_manager_decision에 전달했다.

- 제안 ID: `2d62725cfe374852b916b5bd20af67ac`.
- 승인 시각: **2026-11-03 13:05:17 KST**.
- 재조회: proposal.status=approved, decided_by=사용자, guidance binding 유효.
- 제안 승인 자체의 실제 AI 호출: **0회**.
- 직원 단일 사용 승인 ID: `81322c812a0d44e08c70d16b461542ce`.

직원 승인은 기존 관리자 추가 승인 목록을 수정하지 않고 history의 task002_once_authorized 이벤트에 별도로 추가했다. 고유 ID, KST, 프로젝트/업무/제안 ID, TASK-001 승인 결과·계획·입력 binding, 승인 전 프로젝트 지문, max_calls=1, 모델, 전송 범위, 지시서의 사용자 승인 원문을 기록했다. 제안 승인·원장·감사 기록으로 지시서 재실행과 guard 삭제 후 재호출을 차단한다.

## 변경 파일

- real_task002_once_tool.py: 로컬 소유자 전용 단일 실행 도구. 최신 프로젝트와 제안을 검증하고 기존 승인 함수로 승인한 뒤 mutation lock 안에서 TASK-002만 기존 직원 executor로 실행한다. 별도 O_EXCL guard 및 전송 전 fsync한 관측 파일, 정확한 6번째 예약/앞 5건 불변 검사, 저장 시 최신 디스크 비교를 적용했다. HTTP·시작 훅·자동 재개 경로는 추가하지 않았다.
- app.py: execute_project_task에 내부 선택 인자 _persist를 추가해 이 도구가 성공/실패 저장 시에도 경합을 검사하게 했다. 기본 호출은 기존 save_project를 계속 사용한다. 실제 직원의 프롬프트·모델·응답·권한은 변경하지 않았다.
- tests/test_real_task002_once.py: 임시 가상 프로젝트·가상 키·fake transport·네트워크 차단으로 단일 직원 실행을 검증한다.
- 이 보고서.

기존 previous_results는 승인된 TASK-001 결과와 manager_decision.require_proceed가 반환한 실제 승인 관리자 guidance를 함께 전달한다. fake transport에서 이 두 입력을 확인했다. 실제 요청은 기존 ai_safety의 선예약 저장, 무료-only, 예산, timeout, 고정 HTTPS, 프록시/리다이렉트 차단, 무재시도 경로를 사용했다. 기존 시작당 최대 2회 규칙을 유지하면서 이 도구는 원장 및 transport 계측으로 최대 1회만 허용한다.

## 오프라인 테스트

집중 명령:

`python -B -m unittest tests.test_real_task002_once tests.test_approved_employee_context tests.test_execution_engine tests.test_task_execution_persistence tests.test_concurrent_execution_safety tests.test_real_ai_safety_budget tests.test_manager_decision_loop`

- 최초 `/tmp/task002-offline.log`: 89개 실행, 실패 4건·오류 1건. 가상 제안 지문을 real provider 설정 전에 생성한 fixture 오류로 모든 신규 실제 경로가 전송 전에 차단됐다. 실사용 데이터 변경·실제 전송은 없었다.
- fixture 지문 생성 순서 수정 후 `/tmp/task002-offline-final.log`: **89개 모두 통과**.
- 승인 직후 프로젝트 변경 사례 추가 후 `/tmp/task002-offline-final2.log`: **90개 모두 통과**, 실패·오류 0, 4.120초. 실제 요청 전에 완료했다. 기반 테스트 클래스 상속·발견으로 기존 사례가 반복 실행된 수를 포함한다.

검증 범위: 관리자 승인 저장·실제 직원 결과 저장·사용자 검토 대기, 5→6/20 원장, 승인된 선행 결과와 관리자 지침 입력, 기존 업무·계획·선호·guard 및 다른 가상 프로젝트 불변, 중복 승인·호출·guard·오래된 지문 차단, 원장/프로젝트 경합 보존, 미확정 예약·예산 초과·timeout·실패 시 재시도 없음, 승인 직후 변경 시 0회 전송 및 승인 상태 보존. 기존 실행기·영속성·동시성·무료 모델·관리자 승인 경계 회귀를 포함한다. 실사용 JSON·실제 키는 fixture에 사용하지 않았다. 전체 테스트는 실행하지 않았다.

## 실제 1회 실행과 결과

실행 명령: `python -B /tmp/run_task002_once_20261103.py`. 네트워크 제한에 따른 승인된 외부 실행을 사용했고 세션 종료 코드 0을 확인했다. 호출 직전 data/backups 전체 해시와 사전조건을 다시 확인했다.

- 시작 및 transport 진입: **2026-11-03 13:05:17 KST**.
- 종료: **2026-11-03 13:05:31 KST**.
- 모델: **openrouter/free**. 실제 transport **1회**, 재시도 **0회**.
- 예산: **5/20 → 6/20, 잔여 14**. completed 6, failed/reserved 0.
- guard: data/video-real-plan-20261103/task002-once-20261103.guard.
- 관측: 같은 경로 task002-once-20261103.observation.json. transport_calls=1, finished=true.
- TASK-002 재조회: status=완료, review_status=pending, 결과 1263자(기존 실행기 메타데이터 포함). 사용자 결과 승인 없음.

생성물은 ChatGPT 초보자용 활용 팁 10개를 각각 6초 자막 항목으로 구성했다. 질문 구체화, 예시 제공, 대화 이어가기, 한계와 사실 확인, 새 대화, 모바일 사용, 개인정보, 고급 기능, 피드백을 다룬다. 글자 수만으로 1분을 보장하지 않으며 실제 낭독 시간을 측정해야 한다고 적었다. 모델이 만든 항목 수·시간·문장을 코드로 변경하거나 추가 생성하지 않았다.

**사용자 검토 필요사항:** 여러 항목이 구체적 링크나 독립 검증 없이 OpenAI 공식 문서 등을 언급하며 “검증됨”이라고 표시한다. 이는 모델의 미검증 주장으로, 검증 완료 사실로 인정하지 않는다. 개인정보·모델 개선·모바일·고급 기능 등 기능/정책 설명도 확인이 필요하다. 별도 웹 조사나 사실 검증은 수행하지 않았다. 자막과 실제 음성 대사의 구분, 화면 녹화 구성, 중복되는 팁, 실제 60초 낭독 적합성을 검토해야 한다. 결과는 그대로 보존하고 사용자 검토 대기로 남겼다.

## 데이터 보존과 종료 경계

사전 data/backups 목록·SHA-256 **21개 파일**을 기록했다. 사후 기존 파일 중 대상 프로젝트 JSON만 변경됐고 **나머지 20개 파일은 해시 동일**하다. c85d9853906a의 기존 미확정 예약, 모든 백업, 1~3차 관리자 guard·관측 파일을 포함한다. 새 파일은 TASK-002 guard와 관측 두 개뿐이며 백업은 생성·삭제하지 않았다.

대상 JSON의 앞 5 attempts, TASK-001 전체(결과·승인 포함), TASK-003/004 전체, 기존 history 접두부, 기존 관리자 authorization 및 additional_authorizations, 제안 decision 전체, 계획·선호와 나머지 업무 필드는 불변임을 검증했다. 허용된 변경은 관리자 사용자 승인 필드, 새 직원 승인 감사, TASK-002 단일 시도·결과·검토 상태·감사 및 갱신 시각이다. TASK-003/004는 대기·결과 없음이며 실행하지 않았다. 기존 미추적 파일은 수정·삭제·스테이징하지 않는다.

실사용 JSON·키·전체 프롬프트·모델 응답 전문·비밀 로그는 Git에 포함하지 않는다. 추가 요청이나 결과 승인을 수행하지 않고 이 작업을 종료한다.

## 최종 검증

실제 실행 후 같은 집중 명령을 `/tmp/task002-post-tests.log`로 다시 실행해 **90개 모두 통과**, 실패·오류 0(2.981초)을 확인했다. `git diff --check` 통과. 보고서 저장 후 재읽기로 내용과 파일 생성을 검증했다. 원격 조회 첫 시도는 샌드박스 DNS 제한으로 실패해 외부 읽기 실행으로 재확인했다. 이는 AI 재호출이 아니다. 검증된 코드·테스트·보고서 네 파일만 선택적으로 커밋·푸시한다.
