# 실제 관리자 TASK-001 단일 판단 연결 및 실행 관측

작성: 2026-11-03 KST(UTC+9). `git pull --ff-only`로 main `3216737` 반영 후 수행했다.

**판정: 실제 관리자 판단 검증 미완료.** 실제 transport 진입은 **1회**, 제공자 응답·판단 제안은 확보하지 못했다. 클라이언트 시간 초과 및 요청 worker 종료 미확인으로 완료 불명이며, 예약과 실행 프로세스를 보존했다. 재시도·다른 모델·TASK-002 실행은 없다.

## 실제 실행과 현재 예산

대상 프로젝트 cb44b605b498, 사용자 승인된 TASK-001 조사 결과에 대한 관리자 판단 요청이다. 모델 `openrouter/free`, kind=`manager_decision`, task_id=`TASK-001`로 1건을 **2026-11-03 10:13:26 KST**에 요청 전 영속 예약했다. 전송 경로 진입은 1회이며 실제 제공자 수신·처리·완료 여부는 확인할 수 없다.

로컬 클라이언트 timeout=55초 뒤 응답 미확보, 추가 worker 관측 5초 뒤인 **10:14:26 KST**에 requests_finished=false를 기록했다. 이후 **10:15:16 KST** 읽기 전용 확인에서도 예산은 **3/20회 소모**, completed **2**, failed **0**, reserved **1**, 미확정 **1**이고 제안은 0개다. 이 값은 해당 시각 관측이며 살아 있는 worker가 이후 완료하면 바뀔 수 있다. 실제 응답 확보·action 선택·판정 성공으로 보고하지 않는다.

클라이언트 timeout만으로 제공자 실패나 작업 종료를 추정하지 않았다. 프로세스/worker를 kill하거나 reserved를 failed/completed로 강제 변경하지 않았다. 실행 도구 세션은 종료되지 않은 상태로 유지했다. 전체 wall-clock 취소 보장은 여전히 없으며 중복 전송하지 않는다. HTTP 200/409 결과도 클라이언트에서 확보하지 못했다.

TASK-001의 조사 원문·사용자 승인 및 TASK-002/003/004 대기 상태는 그대로다. 실제 관리자 질문·지침·근거는 아직 없으므로 요약할 수 없다. 사용자 제안 자동 승인·직원 실행·의미 검토·재계획·MP4 제작/업로드는 수행하지 않았다.

## 구현 파일과 실제 경로

- `manager_decision.py`: 명시적 RealManagerDecisionProvider, 한국어 strict JSON 요청, 네 action 자율 선택, 직원/사용자 자료의 명령 격리 안내, 고정 무료 모델·주소·키 존재 검사, finish_reason=stop 및 응답 content/계약 검증. 기존 모의 공급자는 유지한다.
- `app.py`: 소유자 확인된 로컬 `propose_real_manager_decision_once(project_id, task_id, expected_project_hash, user_confirmed=True, reason=...)` handler. 공개 HTTP 관리자 실행/승인 endpoint는 추가하지 않았다. 기존 모의 상태를 실제로 자동 전환하지 않는다. 실제 설정에서는 모의 제안 공급자 연결도 거절한다.
- `ai_safety.py`: 제공자 외부 JSON 객체의 중복 키도 거절하도록 강화. 기존 무료/HTTPS/프록시·리다이렉트 차단·예약 선저장·시작당 2회·20회 예산 안전 경계는 유지한다.
- `tests/test_real_manager_decision.py`: 실제 provider 코드를 fake transport로만 검증하는 7개 집중 테스트.
- 이 보고서. 실사용 JSON·서명 키·제공자 원문·관측 로그는 Git 제외.

실제 로컬 handler는 최신 프로젝트 해시와 직접 사용자 확인·근거를 요구한다. 기존 관리자 설정이나 manager_decision 시도가 있으면 거절한다. 서버/엔진/동의·정확한 모델·고정 주소·키 존재를 확인한 뒤에만 해당 대상 binding·범위·max_calls=1·KST 승인 감사 이력과 실제 관리자 opt-in을 저장한다. 실제 요청은 공통 request_json과 request_scope를 사용한다. 원본 프로젝트에는 관리자 설정이 없었으며 이번 명시 승인 대상에만 opt-in했다.

기존 consent의 goal_hash는 동일한 영상 목표에 결속되고 data_scope는 목표·업무 입력·선행 결과·피드백 전송을 허용한다. 이번 전송은 같은 목표와 사용자 승인된 대상 결과, 관련 승인 단계/후속 업무 및 허용된 선호라는 업무 맥락에 한정한다. 이를 보완하는 이번 관리자 단일 요청 승인·전송 범위는 별도 감사 이력/authorization에 기록했으며 기존 consent를 바꾸거나 TASK-002/후속 호출 허가로 확대하지 않았다.

## 판단 계약 및 지문/예약 충돌 해결

모델에게 proceed/ask_user/request_revision/propose_plan_change 중 하나를 고르게 하며 영상 항목 수·선택 팁·행동은 하드코딩하지 않는다. 최상위 schema_version/binding/action/rationale/evidence/next_step/uncertainty/source=model_claim/payload와 action별 필드·TASK ID·크기 상한은 기존 strict 계약을 재사용한다. 직원 결과의 ‘검증됨’ 표현도 독립 검증 사실로 취급하지 않으며 웹·도구 사용을 주장하지 않도록 system 안내와 user 자료를 분리했다. 실제 모델이 이 안내를 준수했는지는 이번 미확정 응답으로 검증하지 못했다.

기존 input_hash에서 **permission_summary의 used_calls와 unresolved_reservations 두 집계값만 제외**했다. 모델에게 보내는 자료에서는 실제 당시 값이 그대로 보이고 감사/원장도 보존한다. 목표·결과 원문/버전/사용자 승인 시각·계획·선호·후속 업무·사용자 답변·limit·권한 요약의 나머지는 계속 지문에 결속된다. 반환한 binding을 새 값으로 덮어쓰지 않는다.

사용량 제외로 생길 수 있는 느슨함은 실제 handler의 **정확한 단일 원장 증가 검증**으로 보완한다. 전송 전 프로젝트 스냅샷을 보존하고, 예약 및 완료 저장 직전에 디스크를 다시 읽어 불변 프로젝트 내용과 과거 attempts 전체를 검사한다. 이번에 생성된 같은 예약 ID의 reserved→completed/failed 전이만 허용한다. 마지막 보강에서는 예약 항목 전체를 지문 대조해 ID/상태 외 필드 변경도 거절한다. 응답 후에는 과거 시도 완전 일치+동일 TASK/kind/model의 completed 1건만 추가됐는지, 현재 의미 binding이 입력 binding과 같은지 확인한다. 실제 결과·계획·승인·원장 변경을 덮어쓰지 않는다.

검증된 응답만 provider=real_openrouter_free, pending_user_decision, attempt_id·KST·감사 이력과 함께 저장한다. 모의/실제 provider 표시는 조회에서 구별되고, 나중에 사용자가 proceed를 승인하면 후속 guidance도 ‘실제 AI 관리자’로 구별된다. 승인 후에도 기존 직원 호출 동의·서버 활성화·무료 모델/예산 조건은 별도로 필요하며 관리자 승인만으로 직원을 실행하지 않는다. 이번에는 제안 자체가 없어 사용자 결정 단계에 도달하지 못했다.

## 오프라인 테스트와 오류 수정

최초 명령:
`python -B -m unittest tests.test_real_manager_decision tests.test_manager_decision_loop tests.test_project_budget tests.test_real_ai_safety_budget`

첫 실행 **51개 중 1개 실패**. 전송 중 디스크 결과/계획이 바뀌었을 때 응답 후 검사 전에 기존 request_json의 완료 저장이 그 변경을 덮어쓸 수 있음을 테스트가 발견했다. 실제 요청 전에 저장 callback을 매번 비교·검증하는 persist_single_attempt로 보완했다. 재실행 **51개 통과**했다.

timeout 소모·무재시도 및 변경 보존 확인 추가 후 같은 명령은 **52개 통과**했다. 실제 요청 시작 전 완료된 최종 집중 검증이다.

추가 명령 `python -B -m unittest tests.test_m4_runner_shutdown` → **4개 통과**. 별도 fake transport/loopback만 사용해 클라이언트 우선 timeout, worker 종료 관측, 미완료 예약 보존을 검증했다. 실제 시작 전에 합계 **56개 테스트 통과**를 확인했다.

실제 실행 이후에는 기존 예약 항목의 세부 필드 변조 검사와 해당 가상 사례를 더 보강했고, 위 집중 명령을 다시 실행해 **52개 모두 통과**했다. 실제 요청을 다시 보내지 않았다. 미해결 테스트 실패는 없다. 전체 테스트·브라우저 설치는 하지 않았다.

확인한 오프라인 시나리오는 네 행동, 허용 입력만 포함/직원 명령의 system 승격 방지, 예약 선저장 및 count 변화 후 정상 binding/조회/새 프로세스 복원, source 결과/계획/승인/추가 원장/예약 지문 변경 시 거절과 변경 보존, malformed/truncated/중복 키/다른 프로젝트 binding의 1회 소모·무재시도, 동일 실제 요청 재실행 거절, mock 자동 전환 거절, 미승인 결과·사용자 미확인·다른 모델/호스트 무전송, 사용자 결정 전 다음 실행 차단 및 결정 후에도 서버 미활성화 시 직원 transport 0, 기본 20/사용자 증액/기존 mock·일반 경로 회귀다. 모든 테스트는 임시 fixture와 fake transport이며 실제 네트워크는 차단했다.

## 실제 실행 도구와 보존

실행 명령: `python -B /tmp/real_manager_task001_once_20261103.py` (허용된 격리 로컬 실행). 일반 앱에는 endpoint를 추가하지 않고 도구 내부 loopback 전용 서버에서 명시적 로컬 handler를 1회 호출했다. ObservedServer의 non-daemon worker 및 stop_and_observe를 사용했다. 로컬 요청 1회와 실제 transport 진입 1회 가드를 각각 두고, 배타 guard 파일·기존 관리자 시도/상태 검사로 재실행을 차단한다. 모델 요청 직전 디스크의 정확한 kind/task/reserved·기존 두 attempts·계획/업무 불변·무료 주소/모델을 검사했다. 영구 환경은 바꾸지 않고 실행 프로세스에만 실제 활성화 및 45초 소켓 timeout을 설정했다.

실제 프로젝트 위치는 `data/video-real-plan-20261103/projects/cb44b605b498.json`이다. 새 manager_decisions.authorization에는 이번 승인 범위와 대상 binding이 있고 proposals는 현재 비어 있다. 원장 마지막 항목이 관리자 reserved다. 기존 두 시도·동의·계획·조사 원문·TASK-002~004·사용자 선호는 변경 전후 동일함을 실행 도구에서 확인했다.

실행 도구는 `real-manager-task001-once.guard`와 `real-manager-task001-observation.json`을 동일 Git 제외 격리 경로에 보존했다. worker 종료 미관측 상태가 저장돼 있다. 실행 도구를 다시 호출하거나 guard를 지워 재실행하면 안 된다. 살아 있는 기존 worker는 이후 결과를 저장할 수 있으므로 재개 판단 전 원장·제안을 읽기 전용으로 재확인해야 한다.

기존 data/backups 15개 파일의 시작 전 SHA를 기록했다. 대상 영상 JSON 이외 **14개 기존 파일 SHA 불변**을 확인했다. 새 파일은 위 도구 guard/관측 자료뿐이다. 기존 재고 프로젝트 c85d9853906a와 그 미확정 예약·보존본·판단 원장, 다른 프로젝트·백업·미추적 파일을 수정/복사/삭제/초기화하지 않았다. 새 일일 백업도 생성하지 않았다.

보고서 저장 후 재읽기·git diff --check, 검증한 코드/테스트/보고서만 선택적으로 커밋·푸시하고 원격 main 일치를 확인한다. 실제 응답 전문·프로젝트 JSON·로그·키는 Git에 포함하지 않는다.

## 다음 한 단계

**기존 관리자 요청 worker와 예약의 종료/완료 상태를 추가 전송 없이 읽기 전용으로 관측**하는 것이 다음 단계다. 완료 증거가 없으면 reserved를 유지하며 실제 요청 재시도·TASK-002 대체 실행·제안 자동 승인 없이 멈춘다. 실제 관리자 action과 사용자 제안 확인 대기에 도달해야 하는 이번 성공 기준은 아직 충족하지 못했다.
