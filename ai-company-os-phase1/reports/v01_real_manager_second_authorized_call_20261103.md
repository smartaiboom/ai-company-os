# 실제 관리자 두 번째 개별 승인 호출 결과

2026-11-03 KST. `git pull --ff-only`로 main e6edd78을 반영하고 지정 지시서를 실행했다.

**결과: 실제 외부 전송 1회, 응답 strict 계약 거절로 유효한 제안 저장 실패.** 요청은 재전송하지 않았다. TASK-002 실행 0회다. 이번 승인 상한은 모두 사용됐다. 실제 관리자 판단 성공 또는 사용자 승인 대기 도달을 주장하지 않는다.

## 새 승인과 구현

새 사용자 승인 “ai관리자 호출 승인할게”는 이전 승인과 분리했다. 기존 manager_decisions.authorization을 그대로 두고 additional_authorizations에 고유 ID, KST 승인 시각, 시도 번호 2, 이전 관리자 attempt ID, 목표 지문, 승인 결과/계획/입력 binding, 외부 전송 범위, max_calls=1 및 새 승인 원문을 append-only로 기록한다. 기존 중단 이력도 변경하지 않는다.

변경 파일:

- app.py: 기존 1차 호출 차단을 유지하면서 별도 propose_real_manager_second_authorized 로컬 경로를 추가했다. 기존 시도 3건 completed·관리자 시도 정확히 1건·제안 없음·추가 승인 없음·명시 확인·최신 프로젝트 해시를 요구한다. 실제 요청/예약/지문/계약/원자 저장 코드는 기존 경로를 공유한다. 새 제안에는 승인 ID를 결속하도록 구현했다. HTTP endpoint는 추가하지 않았다.
- real_manager_second_tool.py: 새 O_EXCL guard 및 독립 transport 계측으로 최대 1회만 전송하는 로컬 도구다. 전송 직전 기존 원장 전체와 정확한 4번째 TASK-001 manager_decision 무료 모델 예약을 재확인한다. 재실행은 guard뿐 아니라 기존 원장·제안·추가 승인 기록으로 차단되므로 guard 삭제만으로 새 호출이 허용되지 않는다. 완료 여부와 전송 진입 횟수를 Git 제외 관측 파일에 남긴다.
- tests/test_real_manager_second_authorized.py: 임시 fixture, fake transport, 네트워크 차단으로 2차 정상 네 행동·새 프로세스 조회·기존 승인/원장/guard 보존·중복 실행·직접 확인 누락·기존 guard·실패/경합·무재시도·TASK-002 차단을 검증한다. 기반 테스트 클래스 상속/발견으로 기존 사례가 일부 반복 실행되며 아래 수는 unittest의 실제 실행 수다.
- 이 보고서.

기존 승인 결과의 binding을 모델 대신 바꾸거나 strict 검증을 완화하지 않았다. 모델 action이나 영상 팁 개수도 강제하지 않았다. 전체 구조·UI·모델 설정은 변경하지 않았다.

## 호출 전 오프라인 검증

`python -B -m unittest tests.test_real_manager_second_authorized tests.test_real_manager_decision tests.test_manager_decision_loop tests.test_project_budget tests.test_real_ai_safety_budget > /tmp/manager-second-tests.log 2>&1`

**84개 테스트 모두 통과**, 실패 0. 실제 외부 요청 전에 완료했다. 기존 무료 모델/20회 예산/mock 회귀, stop_reason·updated_at·예약 후 사용량 변화, 응답 계약과 실패 단계·저장 실패 검증도 포함된다. fake transport만 사용하며 실사용 키·프로젝트 JSON을 테스트 입력으로 사용하지 않았다. 전체 테스트는 실행하지 않았다. `git diff --check` 통과, 보고서 저장 후 재읽기로 생성과 내용을 확인했다.

## 실제 1회와 진단

실행 명령은 소유자 확인된 격리 로컬 도구 `python -B /tmp/real_manager_second_authorized_20261103.py`다. 실행 직전 읽기 전용 사전조건 및 기존 데이터 SHA 일치를 다시 확인했다. 프로세스 목록에서 기존 요청 worker가 없음을 확인했다. 환경 설정은 실행 프로세스에만 적용했다. API 키 값·응답 원문·전체 전송 데이터는 출력하거나 보고서/Git에 저장하지 않았다.

- 모델: openrouter/free, kind=manager_decision, task_id=TASK-001.
- 예약 및 실제 transport 진입: **2026-11-03 11:50:39 KST**.
- 원장 completed 및 중단: **2026-11-03 11:50:52 KST**.
- 고정 진단: **stage=decision_contract, error_code=strict_contract**.
- 예산: **3/20 → 4/20**, 최종 completed 4, failed 0, reserved/미확정 0, 잔여 16.
- 독립 관측: transport_calls=1, finished=true. 원래 실행 세션 exit_code=0으로 종료 확인.
- manager_decision_view 재읽기 제안 수 **0**. action·근거·질문·지침은 검증되지 않아 보고하지 않는다.

이는 제공자 구조·finish_reason·JSON 검사를 지난 뒤 strict 계약에서 거절됐다는 범위의 진단이다. binding 불일치 전용 코드는 기록되지 않았지만, 전체 계약 및 binding의 유효성을 확보한 것은 아니다. 구체적인 개별 필드 오류는 현재 strict_contract 코드로 구분하지 않으므로 확정할 수 없다. 원문을 사후 복원하거나 임의 보정하지 않았다. 과거 1차 실패는 여전히 **historical_cause=unknown**이다. 원장 completed는 제공자 응답 처리 완료이며 관리자 제안 계약 통과를 뜻하지 않는다. 재시도·대체 모델·다른 프로젝트 호출·후속 직원 호출은 없다.

## 보존 검증

작업 전 data/backups 파일 목록 및 SHA-256 17건을 기록하고 오프라인 테스트 후/실제 호출 직전 불변을 확인했다. 호출 후 기존 파일 중 변경된 것은 대상 영상 프로젝트 JSON 하나뿐이며 나머지 **16개 기존 파일은 SHA 동일**하다. 기존 재고 프로젝트 c85d9853906a의 미확정 예약·모든 백업·이전 guard/관측 파일도 포함한다.

대상 JSON에서는 기존 3 attempts 전체, 첫 authorization, 기존 history 전체 접두부, 목표·승인 계획·선호·TASK-001 원문/승인·TASK-002~004 등 나머지 업무 필드가 동일함을 확인했다. TASK-001 결과 SHA-256은 95e366272746a507f26f3776db5e6e5211126ae0f1f7d2b7712a718e5cff6802다. 기존 real_ai 설정·동의·한도도 그대로다. 허용된 추가 승인/감사 이력, 4번째 attempt, updated_at만 변경됐다. TASK-002~004는 모두 대기·결과 없음이다.

새 파일은 Git 제외 경로의 real-manager-task001-second-20261103.guard와 real-manager-task001-second-20261103.observation.json 두 개다. 이전 guard를 삭제·초기화하지 않았고 백업을 추가하거나 삭제하지 않았다. 기존 미추적 파일은 보존하고 이번 코드/테스트/보고서만 선택적으로 커밋·푸시한다.

이번 실제 제안 저장 성공 기준은 미충족이며 추가 호출 없이 정지한다. 다음 개발 제안은 **strict_contract의 개별 필드 오류를 고정 코드로만 구분하는 오프라인 진단 보완**이다. 이는 새 실제 호출 승인이나 TASK-002 실행을 요구하지 않는다.
