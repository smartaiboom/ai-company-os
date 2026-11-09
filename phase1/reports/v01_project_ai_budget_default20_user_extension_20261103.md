# 프로젝트 기본 AI 예산 20회와 사용자 추가 예산 승인

작성: 2026-11-03 KST(UTC+9). `git pull --ff-only`로 main `5bdbc2a` 반영 후 지정 작업을 수행했다. **실제 외부 AI API 호출 0회**, TASK-002 실행 없음.

## 정책과 실제 영상 프로젝트 반영

`DEFAULT_PROJECT_CALL_BUDGET=20`을 프로젝트별 영속 limit과 분리했다. 신규 `/create` 프로젝트는 enabled=false, limit=20, attempts=[]로 생성하며 외부 전송 동의나 실행 허가는 부여하지 않는다. 과거 limit 누락은 같은 기본 20으로 해석한다. 명시 저장된 과거 limit=7 등은 자동 변경하지 않는다. MAX_CALLS는 기존 코드 호환용 기본값 별칭이며 절대 상한이 아니다.

사용자가 지정한 실제 영상 프로젝트 `cb44b605b498`만 **7→20**으로 변경했다. 적용 시각 **2026-11-03 09:59:40 KST**. 저장 후 **completed 2/20, failed 0, reserved 0, 잔여 18**을 확인했다. TASK-001 완료·사용자 승인, TASK-002/003/004 대기 상태를 보존했다.

로컬 도구 `/tmp/migrate_video_budget20_20261103.py`가 기존 목표·승인 계획 해시·조사 결과 SHA·예산 2/7·후속 대기를 확인한 뒤 정식 `raise_project_budget_to_default` handler로 상향했다. 사용자 정책 문구·작업 문서 근거, 변경 전후 한도, 실행 권한 미부여를 KST history에 남겼다. 변경 전 객체와 비교해 **real_ai.limit, 추가 감사 이력 1개, save_project의 updated_at 이외 완전 일치**를 확인했다. 기존 attempts·동의·원장·승인된 조사 원문·계획/원본 이력·선호·기존 실행 허가는 불변이다.

이 상향은 예산만 변경하며 실제 호출·외부 전송·실행/재개에 대한 새 승인이 아니다. 다음 실제 대본 작성에는 별도 사용자 승인이 필요하다.

## 추가 예산 요청과 결정 계약

`project_budget.py`는 외부 모델 없이 추가 예산을 제안·검증한다. 요청은 project_id, goal_hash, 요청 당시 limit/used/reserved/remaining, 양의 추가 횟수, 사유, purpose/calls의 구조화된 예상 사용 계획, KST 생성 시각, 예산·계획·업무 지문, request ID 및 pending 상태를 갖는다. 요청 최대 50개, 사유 1,000자, 사용 계획 1~20개/항목 설명 500자, 한 요청 추가량 **1~50회**, 프로젝트 절대 한도 **200회**로 제한했다. 이 값은 비용 지출 한도가 아니라 무료 경로의 요청 개수 안전 상한이다.

사용자가 승인하면 **제안에 적힌 additional만** atomic save로 더하고 approved 및 변경 전후 한도·결정 근거·KST를 기록한다. 거절은 rejected와 감사 기록만 남기고 예산은 바꾸지 않는다. 제안이나 manager_claim 자체는 승인이 아니다. stale 증액 승인, 변조, 다른 프로젝트, 중복/동시 승인, 동시 미결 요청, 과도한 추가량은 거절한다. stale 요청도 현재 프로젝트/목표와 유효한 서명·사용자 토큰을 확인한 **명시적 거절**은 허용해 미결 요청을 정리할 수 있다. 거절은 증액을 하지 않는다.

요청과 20회 초과 증액 증명은 로컬 HMAC 서명으로 검증한다. 요청 내용을 임의 변경하거나 limit만 25로 바꾸는 것으로 증액할 수 없으며 서명 없는 20회 초과 limit은 실제 전송 전 거절한다. 신규 기본값/기존 작은 limit은 기존 데이터 호환을 유지한다. 로컬 파일·서명 키·Python 도구를 모두 통제하는 소유자의 악의적 임의 변경까지 막는 보안 저장소는 아니다.

서명 키는 Git 제외 data/.budget-approvals/local.key에 요청 생성 시 최초 생성되고 0600으로 보존한다. 서명 키 읽기/생성을 프로세스 내 잠금으로 보호한다. 테스트 키는 임시 경로에만 생성했으며 실제 영상 프로젝트의 기본 상향에는 서명 키 생성이 필요 없어 기존 실제 데이터 경로에 새 키·요청 파일을 만들지 않았다. 키·서명 토큰·프로젝트 JSON은 보고서나 Git에 포함하지 않는다.

## 소유자 확인된 로컬 인터페이스

기존 앱에 사용자 인증이 없는 공개 HTTP 승인 엔드포인트를 추가하지 않았다. 아래 명시적 로컬 도구를 소유자와 실제 사용자 결정을 확인할 수 있는 운영 도구에서 사용한다. user_confirmed는 호출 도구가 실제 사용자 의사를 확인했다는 값이며 사용자 인증 UI를 대체하지 않는다.

| 도구 | 용도 |
|---|---|
| request_project_budget(project_id, additional, reason, usage_plan) | 근거·사용 계획을 포함한 추가 요청 생성 |
| prepare_project_budget(project_id, usage_plan) | 예상 호출 합계와 잔여 비교. 부족분만 요청하고 충분하면 변경 없음 |
| project_budget_requests(project_id) | 사유·사용 계획·상태·stale·expected_hash를 읽기 전용 조회 |
| decide_project_budget(project_id, request_id, expected_hash, response, user_confirmed=True, reason=...) | 확인된 사용자의 approve/reject만 기록·반영 |
| raise_project_budget_to_default(project_id, expected_project_hash, user_confirmed=True, reason=...) | 이번처럼 사용자가 특정 기존 프로젝트의 기본값 상향을 명시한 경우만 사용 |

usage_plan 예시는 `[{"purpose":"추가 검토", "calls":5}]`다. 조회한 요청의 expected_hash를 그대로 결정 handler에 넘긴다. 모든 변경 handler는 기존 비차단 프로젝트 잠금과 save_project를 사용한다. 같은 요청 중복 승인/동시 승인 중 하나만 성공한다. 기존 앱의 단일 운영 프로세스 제약은 유지한다.

기존 실제 AI 화면에는 현재 limit·사용/예약·남은 횟수·추가 요청의 횟수와 상태, 로컬 승인 도구 안내를 표시한다. 상세 사유와 사용 계획은 로컬 조회 도구로 확인한다. 기본 20회는 **OpenRouter의 무료 할당량이나 비용을 보장하지 않음**, 실패/시간 초과/예약도 소모, 증액은 실행 허가가 아님을 UI와 README에 명시했다. 모델은 계속 정확히 openrouter/free이고 유료 전환은 없다.

## 관리자·업무 흐름 연결과 기존 안전 경계

공통 check_project_permission은 유효한 동의·엔진/서버·예약 상태를 확인하고 예산이 소진된 경우, request_scope가 있으면 **외부 전송 없이** ‘다음 승인된 AI 업무 실행 1회’의 추가 요청을 저장한 뒤 정지한다. 이 1회는 방금 차단된 단일 요청의 필요량이며 모든 미래 작업을 1회로 추정하는 규칙은 아니다. pending 요청이 있으면 중복 생성하지 않는다. scope가 없는 읽기 전용 검사에서는 쓰지 않고 예산 소진 오류로 정지한다.

예측 부족은 호출자가 제공한 목적별 예상 calls 합계에서 잔여를 뺀 부족분을 요청한다. 요청 생성은 잔여 0에서도 동작하며 모델 호출을 필요로 하지 않는다. manager_decision의 비밀 없는 permission_summary도 실제 프로젝트 limit과 pending 예산 요청 여부를 제공한다. 기존 네 관리자 action은 변경하지 않고 별도 좁은 예산 요청 계약을 사용했다. **이는 deterministic 산술과 안전 중단이며 실제 AI의 자율 필요량 추론이 아니다.** 자동 추정·실제 관리자 모델 연결·고급 승인 UI는 후속 범위다.

시작·재개당 최대 **2회**, 프로젝트 동의·무료 모델·고정 HTTPS·리다이렉트/프록시 차단·전송 전 영속 예약·무재시도는 유지했다. 성공/실패/reserved 모두 len(attempts)로 차감한다. 미확정 reserved 검사는 예산 소진 처리보다 먼저 수행하므로 증액으로 미확정 예약을 재전송할 수 없다. 증액해도 enabled·consent·실행 허가를 설정하지 않는다.

입력은 여전히 호출당 128KiB, 응답은 호출당 256KiB, 출력은 최대 4096토큰(계획 3000), timeout 상한 90초다. 누적 입력은 `min(project_limit * MAX_INPUT_BYTES, MAX_TOTAL_INPUT_BYTES)`로 제한하며 절대 누적 입력 상한은 200×128KiB=25MiB다. 정상 수용 응답 총량은 호출당 256KiB와 전체 요청 최대 200회의 결합으로 최대 50MiB까지 제한된다. 실제 출력 토큰 상한도 요청별로 유지한다. 실제 잔여 18회는 18회 연속 실행 허가나 제공자 성공 보장이 아니다.

## 변경 파일과 집중 테스트

변경 파일: `project_budget.py`, `ai_safety.py`, `app.py`, `manager_decision.py`, `README.md`, `tests/test_project_budget.py`, `tests/test_real_ai_safety_budget.py`, `tests/test_uncertain_reservations.py`, 이 보고서. 기존 두 안전 테스트의 변경은 새 로컬 서명 키가 실사용 data에 생성되지 않도록 임시 키 경로를 주입한 것뿐이다. 과거 7회 fixture/테스트는 명시 7회 한도의 회귀 검증으로 유지했다. 과거 보고서·사용자 동의 기록을 일괄 수정하지 않았다.

최초 집중 명령:
`python -B -m unittest tests.test_project_budget tests.test_real_ai_safety_budget tests.test_uncertain_reservations tests.test_manager_decision_loop`
결과: **61개 통과**.

누적 상한·stale 거절·표시/생성 경로를 보완한 최종 명령:
`python -B -m unittest tests.test_project_budget tests.test_real_ai_safety_budget tests.test_uncertain_reservations tests.test_manager_decision_loop tests.test_project_ui tests.test_manager_plan_persistence`
결과: **72개 통과**. 서명 키 프로세스 내 잠금을 보강한 동일 명령의 마지막 재실행도 **72개 통과**다. 신규 예산 테스트는 13개다. 실패한 테스트 실행·미해결 실패 없음. 전체 테스트·브라우저 설치·실제 AI 호출은 하지 않았다.

테스트는 신규 생성 기본 20/disabled, 누락 limit 기본 20·명시 7 유지, 20번째 허용/21번째 차단과 잔여 0 요청 저장, 20→25 사용자 승인과 25번째/26번째 경계, 사용 계획 부족분 산술, 실패/예약 소모, 예약 미확정 상태에서 증액 후 재전송 차단, 동의/활성화 없이 증액만으로 transport 0, stale/위조/다른 프로젝트/과도량/동시·중복 승인 거절, 원본 호출 보존·다른 프로젝트 불변, 누적 입력 상한 및 시작당 2회 유지, 기존 UI/관리자/미확정 예약/계획 경로를 검증했다. 외부 opener와 신규 테스트 네트워크는 차단했고 transport는 fake만 사용했다.

실제 적용 명령: `python -B /tmp/migrate_video_budget20_20261103.py` → **2/20·잔여18·예약0**, 변경 허용 필드 외 불변 검증 성공. 실제 API 호출 0회.

## 데이터 보존 및 다음 단계

작업 전 data/backups 파일 15개 경로·SHA를 기록했다. 적용 후 파일 목록은 같고 대상 영상 JSON 외 **14개 파일 SHA 불변**을 확인했다. 재고 프로젝트 c85d9853906a의 원본/보존본·reserved·판단 원장은 손대지 않았다. 기존 업무·미추적 파일·백업을 복사·삭제·초기화하지 않았다. 실사용 JSON·키·모델 응답 전문·로그·백업은 Git 제외다.

보고서 저장 후 재읽기·git diff --check, 필요한 파일만 선택적 커밋·푸시 및 원격 main 일치를 확인한다.

다음은 사용자가 실제 영상 프로젝트의 TASK-002 실행 또는 관리자 실제 연결 중 어느 작업을 별도로 승인할지 판단하는 것이다. 예산 20회 정책과 추가 예산 승인 경로는 완성했지만 실제 관리자 추론·자동 호출 추정·공개 사용자 인증/승인 UI는 구현하지 않았다. 이번에는 추가 실행 없이 종료한다.
