# 실제 영상 프로젝트 TASK-001 조사 1회 실행 결과

작성: 2026-11-03 09:19:30 KST(UTC+9). `git pull --ff-only`로 main `0d1a7e7` 반영 후 지정 작업을 실행했다.

## 실제 실행 및 승인 대기

프로젝트 `cb44b605b498`, TASK-001 ‘ChatGPT 활용법 조사’를 기존 `/task/execute` HTTP 경로로 실행했다. 실제 OpenRouter `openrouter/free` 요청 **1회**, 제공자 응답 수신 및 비어 있지 않은 한국어 결과 영속 저장 성공. HTTP 303, 요청 스레드 종료 확인 true다.

예약 시각: **2026-11-03 09:19:11 KST**, 응답 처리 완료: **09:19:30 KST**. TASK-001은 `status=완료`, **review_status=pending**으로 사용자 결과 검토/승인 대기다. 결과를 자동 승인하지 않았다. 업무 완료 상태는 생성·저장을 뜻하며 내용의 사실 검증이나 사용자 승인 완료를 뜻하지 않는다.

누적 예산 **2/7회** 사용, completed **2**, failed **0**, reserved **0**, 영상 프로젝트의 미확정 예약 **0**. 이번 시작 소모는 1/2회이고 이번 명시 승인 상한 1회를 모두 사용했다. 기존 관리자 계획 1회와 TASK-001 1회다. 재시도·fallback·다른 모델·추가 전송은 없다. TASK-002/003/004 모두 대기, 결과 없음. 품질 기준 승인·의미 검토·수정·최종 패키지·MP4 생성/업로드는 수행하지 않았다.

## 실제 조사 결과 요약과 검토 포인트

모델은 초보자용 기본 활용 팁 **10개**를 제시했다. 간단한 질문으로 시작하기, 구체적 요청과 출력 형식 지정, 대화 이어가기, 예시로 요청 설명하기, 한계와 사실 확인, 새 대화, 모바일 이용, 개인정보, 고급 기능, 피드백 등이 주제다. 쉬운 한국어 설명을 반환했고 초보자 기본 활용이라는 방향은 반영됐다.

**출처는 독립 확인되지 않았다.** 실제 요청에는 웹 검색·도구 실행이 없었다. 모델이 공식 설명서·지원 센터·정책 등을 출처라고 적고 일부 항목을 ‘검증됨’으로 표시했으나, 구체적인 URL이나 확인 증거가 없어 그 표시는 모델의 주장일 뿐이다. 결과의 최신성 확인 미수행 안내와 앱의 AI 결과 주의 문구도 함께 저장됐다. 이번에는 추가 외부 조회로 이를 검증하지 않았다.

사용자가 확인할 사항:

- ‘검증됨’ 표시를 검증 사실로 받아들이지 않고 출처·제품 동작을 확인하거나 미확인으로 다룰 것.
- 최신 정보 제공 여부·개인정보/데이터 사용·고급 기능 등 제품 동작의 단정적 설명은 최신 기능·설정에 맞는지 별도 확인할 것. 이 보고서는 해당 주장을 사실로 보증하지 않는다.
- 팁 10개는 1분 영상에 많다. 핵심 활용법 선택은 사용자 검토와 후속 대본 단계의 판단 대상이다.
- 구체적인 질문 예시, 화면 녹화 시연 흐름, 자막/음성 설명의 배치, 60초 구성은 충분히 제시되지 않았다. 영상 방식 선호가 요청에 들어갔다는 사실이 결과의 충실한 반영을 보장하지 않는다.

성공 판정 범위는 실제 요청 1회에서 유효한 비어 있지 않은 결과를 저장하고 사용자 검토 대기에 도달한 것이다. 내용 품질 통과, 조사 사실 검증 완료 또는 전체 영상/가상회사 완료를 의미하지 않는다. 결과 원문은 수정하지 않았다.

## 최소 코드 변경 및 입력 연결

`execution_engine.py`에 범용 `approved_task_context`를 추가했다. 승인된 계획에서 TASK ID에 해당하는 **현재 단계만** 선택해 name/role/inputs/input_task_ids/output/risk를 전달한다. 전체 계획·다른 단계·수정 이력·피드백·개인 메타데이터를 일괄 전송하지 않는다. 프로젝트 선호는 기존 `user_preferences`의 focus/video_style 문자열 값만 허용한다. 승인 전 계획 또는 일치하는 TASK ID가 없으면 추가 컨텍스트를 넣지 않는다. 영상 목표·ID·역할을 운영 코드에 하드코딩하지 않았다.

기존 목표·업무 정의·선행 결과 요청 구조와 무료 모델 안전 경계를 유지했다. 프롬프트에는 실제 검색/도구 실행을 주장하지 말고 최신 정보·출처가 미검증이면 명시하도록 안내를 보강했다. 이 안내에도 모델이 일부 검증 주장을 반환했으므로 사용자 검토가 필요하다.

오프라인 fake transport에서 요청 본문에 목표·현재 승인 단계·선호·업무 입력이 들어가며 다른 단계/프로젝트 정보·미승인 기준 초안·메타데이터가 제외됨을 검증했다. 실제 전송 원문·인증키·프로젝트 JSON은 Git에 포함하지 않는다.

## 사전 검사·종료 관측·데이터 보존

실제 격리 파일 존재, 정확한 목표, 승인 계획과 승인 전 해시 기록, 4개 대기 업무·역할/선행 관계·사용자 선호·원본 이력, completed 1/7·reserved 0·failed 0 및 TASK-001의 기존 예약/결과/실행 이력 부재를 확인했다. 키는 존재 여부만 확인했다. 모델·엔진·고정 OpenRouter HTTPS 주소 일치와 공통 동의·예산 검사를 확인했다.

실행 도구 `/tmp/video_research_task001_once_20261103.py`는 실제 격리 경로만 사용했다. 프로젝트의 execution_authorizations에 이번 TASK-001 최대 1회·전송 범위·모델·KST 승인 기록 시각·계획 해시·작업 문서 근거를 추가했다. 이전 승인 기록·동의·계획·선호를 덮어쓰지 않았다. 실행 활성화와 timeout 설정은 해당 프로세스에만 적용했다.

ObservedServer의 non-daemon 요청 스레드 및 stop_and_observe를 사용했다. 단일 허용 HTTP 경로·프로젝트·TASK만 받아 실행 직전 상태를 프로젝트 잠금 안에서 재검사했다. 공통 request_scope의 요청 전 영속 예약과 7회/시작당 2회 한도를 유지했다. 실제 transport 앞의 단일 호출 가드가 두 번째 전송을 차단하며, 실제 첫 전송 직전에 디스크의 TASK-001 reserved와 정확한 주소·모델·승인 맥락을 확인했다. 기본 guarded transport의 프록시·리다이렉트 차단을 유지했다. 배타적으로 생성하는 task001-once-20261103.guard와 기존 TASK 상태/예약 검사로 같은 도구의 중복 실행을 차단했다.

소켓 timeout은 전체 wall-clock 취소를 보장하지 않는다. 클라이언트 timeout이나 관측 기한 초과를 제공자 실패로 간주하지 않고 진행 중 프로세스·reserved를 보존하는 정책을 유지했다. 이번에는 응답 처리와 모든 요청 스레드 종료를 관측했으므로 미확정 상태가 없다. 실제 결과 대기는 한 번만 수행했고 강제 종료나 재전송은 없었다.

실제 저장 위치: `data/video-real-plan-20261103/projects/cb44b605b498.json`의 tasks[0].result. 관측 기록은 동일 격리 경로의 task001-observation.json이다. 기본 앱 화면에는 자동 표시되지 않으므로 위 요약 또는 해당 파일을 읽어 검토할 수 있다.

저장 후 계획 전체·원본 plan_revisions·사용자 선호·기존 동의·기존 관리자 시도 항목 불변을 확인했다. TASK-001만 결과가 있으며 후속 3개는 대기 상태임을 재읽기로 확인했다. 대상 이외 data/backups JSON **10개**는 변경 전후 SHA-256 동일하다. 기존 재고 프로젝트 c85d9853906a 및 보존본·미확정 예약·판단 원장을 수정/복사/초기화/재전송하지 않았다. 기존 미추적 파일도 보존했다.

## 집중 테스트와 Git 변경 파일

Git 변경 파일: `execution_engine.py`, `tests/test_approved_employee_context.py`, 이 보고서. 실사용 JSON·승인 기록·guard·관측 로그·키·외부 응답 원문은 제외한다.

실행 명령 및 실제 결과:

1. `python -B -m unittest tests.test_approved_employee_context tests.test_execution_engine tests.test_video_plan_approval_preparation tests.test_real_ai_safety_budget.RealAISafetyBudgetTests.test_pending_reservation_survives_reload_and_blocks_restart tests.test_real_ai_safety_budget.RealAISafetyBudgetTests.test_timeout_in_real_workflow_preserves_result_and_does_not_retry tests.test_real_ai_safety_budget.RealAISafetyBudgetTests.test_reservation_write_failure_never_calls_transport`: **25개 통과**. 모의 요청에서 예약 선저장·transport 1회·예산 +1·허용 입력 포함/미승인 필드 제외, 기존 엔진, 선행 미완료/미승인 차단, 재로드 후 reserved 보존 및 재시작 차단, timeout 실패 소모/재시도 없음, 예약 저장 실패 시 무전송을 확인했다.
2. `python -B -m unittest tests.test_real_ai_safety_budget.RealAISafetyBudgetTests.test_plan_and_two_roles_share_budget_and_approval_gates`: **1개 통과**. 모의 제공자로 실행 성공 후 review_status=pending, 승인 전 후속 전송 차단 및 공유 예산을 확인했다.
3. `python -B -m unittest tests.test_m4_runner_shutdown`: **4개 통과**. 별도 모의 loopback 테스트로 클라이언트 우선 timeout·worker 완료 관측·미완료 시 reserved 바이트 보존을 확인했다. 실제 공급자 호출 없음.
4. `python -B /tmp/video_research_task001_once_20261103.py`: 승인된 실제 실행 **1회**, HTTP 303, 실제 transport 진입 1회, 요청 스레드 종료 true. 비어 있지 않은 결과·사용자 검토 대기·예산 completed 2개·후속 대기를 재읽기로 확인했다.

모의 집중 테스트 합계 **30개 통과**, 미해결 실패 없음. 전체 테스트·브라우저 설치는 하지 않았다. 보고서 저장 후 재읽기와 git diff --check를 수행하고 필요한 세 파일만 커밋·푸시하며 원격 main 일치를 확인한다.

## 다음 한 단계

사용자가 TASK-001 결과와 위 검토 포인트를 읽고 **승인 또는 수정 요청을 판단**하는 것이다. 이번에는 그 결정을 대신하지 않았다. TASK-002 실행과 추가 외부 호출은 승인되지 않았으며 수행하지 않는다.
