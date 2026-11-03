# 실제 AI 관리자 3차 개별 승인 호출 결과

2026-11-03 KST. `git pull --ff-only`로 main 1dbaede를 반영하고 지정 작업을 실행했다.

**성공: openrouter/free 실제 전송 1회, 유효한 관리자 제안 1개를 pending_user_decision으로 저장·재조회했다.** 사용자 승인 대행, 계획 변경, TASK-002~004 실행은 하지 않았다. 재시도·추가 AI 호출·다른 프로젝트 호출은 없다.

## 변경 파일과 새 승인

- app.py: 로컬 소유자 전용 propose_real_manager_third_authorized와 3차 상태 검사를 추가했다. 4건 completed 원장, TASK-001 무료 관리자 시도 정확히 2건, 기존 승인 및 2차 추가 승인 1건, 중단 이력 2건, 제안·답변 없음, 최신 전체 프로젝트 해시와 직접 확인을 요구한다. 기존 1차·2차 진입점의 허용 조건은 유지했다. HTTP 경로는 추가하지 않았다.
- real_manager_third_tool.py: 별도 O_EXCL guard와 관측 파일을 사용하는 단일 실행 도구다. 기존 4건 원장이 불변이고 정확한 5번째 TASK-001/manager_decision/openrouter/free 예약이 저장된 경우에만 transport 카운트를 먼저 기록하고 최대 1회 전송한다. guard를 삭제해도 승인·이력·원장 검사로 재사용을 차단한다.
- tests/test_real_manager_third_authorized.py: 임시 프로젝트·가상 키·fake transport 및 네트워크 차단으로 3차 경로를 검증한다.
- 이 보고서.

새 승인 ID는 325de4d118e946c49bc9d0be24d781af다. 사용자 승인 원문 “응 호출 승인할게 다음 진행해줘”, 승인 시각 2026-11-03 12:48:45 KST, 프로젝트 ID, attempt_number=3, max_calls=1, 이전 관리자 attempt ID 2개, 승인 결과·계획·입력 binding 및 목표 지문·전송 범위를 additional_authorizations에 추가했다. history에도 새 승인 ID와 binding을 추가하고, 저장된 제안에 승인 ID와 새 attempt_id를 연결했다. 기존 authorization·2차 승인·이력 접두부는 불변이다.

모델 계약·action·payload를 보정하지 않고 기존 여섯 필드 출력 검증, 프로그램 소유 metadata 결합, 내부 strict 계약, 입력 지문 비교와 원자 저장을 그대로 공유한다. 기존 무료-only·예산·예약 선저장·고정 HTTPS·프록시/리다이렉트 차단·timeout·무재시도 경로를 사용했다.

## 사전조건과 오프라인 검증

호출 전 4/20, completed 4, failed/reserved 0, 관리자 시도 2건, 제안·답변 0, 추가 승인 1건과 중단 이력 2건을 확인했다. TASK-001 완료·사용자 승인·결과 SHA-256 95e366272746a507f26f3776db5e6e5211126ae0f1f7d2b7712a718e5cff6802 및 TASK-002~004 대기·결과 없음을 확인했다. 기존 guard와 관측 파일을 읽어 보존했다. 프로세스 목록에서 실행 중인 AI worker는 발견되지 않았다. 모델·주소·키 존재를 확인했으며 키 값은 출력하지 않았다. 실제 실행 프로세스에만 AI_REAL_REQUESTS_ENABLED=1을 적용했다.

실행 명령:

`python -B -m unittest tests.test_real_manager_third_authorized tests.test_manager_model_output_contract tests.test_real_manager_second_authorized tests.test_real_manager_decision tests.test_manager_decision_loop tests.test_project_budget tests.test_real_ai_safety_budget`

- 최초 기본 확장 실행은 정상 종료했다. 후속 실패 주입 테스트 확장 실행은 117개 중 fixture 재사용에 따른 오류 10건이었다. 기존 guard를 테스트 반복에서 재사용하고 이미 완료된 가상 업무를 재준비한 테스트 구성 오류를 수정했다. 실제 호출은 하지 않은 상태였다.
- 최종 로그 `/tmp/manager-third-tests-final2.log`: **118개 모두 통과, 실패·오류 0**, 8.964초. 기반 클래스 상속·발견으로 반복 실행된 사례가 포함된 unittest 실제 실행 수다.
- 네 행동 정상 저장 및 새 프로세스 조회, 모델 여섯 필드→프로그램 metadata→내부 저장 검증, 기존 승인·원장·guard·업무 보존, 누락/중복 승인·guard 존재·원장/결과 경합·타 업무·payload·finish_reason·예산 초과·timeout·예약/원장/제안 저장 실패, no retry, 기존 진입점 차단, 사용자 결정 전 TASK-002 실행 차단을 검증했다.
- 실사용 JSON·실제 키를 테스트 fixture로 사용하지 않았다. 전체 테스트는 실행하지 않았다. 실제 호출 직전 data/backups 전체 해시와 사전조건을 다시 확인했다.

## 실제 호출과 AI 판단

실행: `python -B /tmp/real_manager_third_authorized_20261103.py`. 환경의 네트워크 제한에 따라 승인된 격리 로컬 도구를 실행했다. 단일 실행 세션 종료 코드 0을 확인했다.

- 시작 및 transport 진입: **2026-11-03 12:48:45 KST**.
- 종료: **2026-11-03 12:49:23 KST**.
- 모델: **openrouter/free**, 실제 전송 **1회**, 재시도 **0회**.
- 예산: **4/20 → 5/20, 잔여 15**, completed 5, failed 0, reserved 0.
- 새 guard: data/video-real-plan-20261103/real-manager-task001-third-20261103.guard.
- 새 관측 파일: 같은 경로의 real-manager-task001-third-20261103.observation.json. transport_calls=1, finished=true.
- manager_decision_view 재조회: 제안 1개, provider=real_openrouter_free, status=pending_user_decision, stale=false. API 호출 실패나 계약 오류 없음.

AI가 선택한 행동은 **proceed**, 직접 후속 업무는 TASK-002다. 근거는 승인된 조사 결과가 목표·선호와 부합하고 대본 작성 입력을 충족한다는 판단이다. 다음 단계로 한국어 1분 대본 작성에 구간별 예상 낭독 시간, 화면 자막·음성 설명, 사실 확인 안내를 포함하도록 제안했다. 출처와 최신성은 독립 검증되지 않았으며 글자 수만으로 1분을 보장할 수 없다는 불확실성을 명시했다. 질문이나 계획 변경은 제안하지 않았다. 이는 실제 모델의 검증된 제안 요약이며 사용자 승인을 뜻하지 않는다.

## 보존과 제한

작업 전 data/backups 목록·SHA-256 19건을 기록했다. 호출 후 기존 파일 중 대상 프로젝트 JSON만 변경됐고 **나머지 18개 파일 SHA가 일치**했다. 다른 프로젝트 c85d9853906a의 미확정 예약, 모든 백업과 기존 guard/관측 파일을 포함한다. 새 파일은 3차 guard·관측 두 개뿐이며 백업 추가·삭제는 없다.

대상 JSON의 기존 4 attempts, 최초 authorization, 기존 additional_authorizations 접두부, history 접두부, 업무 전체, 목표·승인 계획·선호 및 기타 업무 필드는 동일하다. TASK-001 결과·승인과 해시는 불변이다. TASK-002~004 대기·결과 없음, 직원 실행 0회다. 실사용 변경은 허용된 새 승인·원장·제안·감사 이력 및 갱신 시각에 한정했다. 이전 2차 보고서는 변경하지 않았다. 이전 두 실패의 구체적인 원인은 여전히 단정하지 않는다.

실사용 JSON·키·모델 응답 전문·비밀 로그는 Git에 포함하지 않는다. 기존 미추적 파일은 보존한다. 추가 호출은 수행하지 않으며 다음 업무 진행은 저장된 제안에 대한 사용자 결정과 직원 호출 승인이 필요하다.

## 최종 검증

실제 호출 후 같은 집중 명령을 `/tmp/manager-third-post-tests.log`로 다시 실행해 **118개 모두 통과**, 실패·오류 0(8.041초)을 확인했다. `git diff --check` 통과. 보고서를 저장 후 다시 읽어 생성과 내용을 확인했다. 원격 조회의 첫 실행은 샌드박스 DNS 제한으로 실패하여 허용된 외부 실행으로 원격 main이 1dbaede임을 재확인했다. 이는 AI API 재전송이 아니다.
