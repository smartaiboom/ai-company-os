# 프로젝트별 AI 사용 예산·추가 승인 구현 결과

2026-11-11T15:54:32+09:00 (KST). 기준 GitHub `ff0978d`.

## 완료 범위: 새 프로젝트용 안전한 최소 예산 실행 경계

기존 `core/project_budget.py`에는 단일 호출 예산·추가 승인/거절·서명·부족 요청이 있지만 기존 기본값과 단일 real_ai 원장을 전제로 한다. 기존 동작을 변경하거나 미션 01을 이관하지 않고 **별도 opt-in 다중 자원 원장**을 추가했다. 전역 10/4/4 또는 기본 20회를 새 프로젝트 정책으로 복제하지 않았다. 새 원장의 최초 승인량은 각 자원 0이며 관리자 견적만으로 호출할 수 없다.

수정/추가 파일:
- `core/project_budget_ledger.py`: 신규 공통 영속 원장과 request/decide/execute/view 경계.
- `companies/video/video_budget.py`: 새 영상 프로젝트가 명시적으로 연결하는 얇은 `BudgetedVideoTransport` 어댑터와 budget_status 조회. 기존 미션 실행 경로는 변경하지 않았다.
- `tests/test_project_budget_ledger.py`: 합성 오프라인 테스트.
- 이 보고서. 기존 core 예산·provider·UI·미션 소스는 변경하지 않았다.

기존 기능 재사용: `project_budget.digest/now`의 canonical hash·KST, `LiveStore._sign`의 로컬 HMAC/키 생성, `Store.atomic`의 atomic replace·fsync, 기존 ID/path 검증·오류/strict JSON 유틸리티·fcntl 잠금. 새 원장은 전용 marker/폴더를 요구해 기존 사용자 원장에 자동 혼합하지 않는다. 기존 서명 키나 승인 파일을 옮기지 않는다.

## 모델·승인·차감·차단

프로젝트 ID와 purpose/data_policy/free_only/consent 참조·만료 및 자원별 provider/model/account_project/operation/unit을 고정 scope로 묶는다. 자원은 예를 들어 텍스트 모델 요청, search.list, videos.list로 나누며 현재 지원 단위는 **request_attempt**뿐이다. 토큰·YouTube quota units·통화 비용을 호출 횟수와 섞지 않는다.

관리자는 실제 작업계획 해시와 수량·사유·완료 현황·비용/무료 영향·실패 위험을 request로 제안한다. 이는 승인 예산이 아니다. 미결 요청은 한 건으로 합쳐 반환하며, 승인/거절에는 명시적 사용자 결정과 검토한 요청 해시·유효기간·승인 이력 바인딩을 요구한다. 승인 시 기존 승인/사용량을 덮어쓰지 않고 추가 승인 이벤트를 append한다. 거절은 증액 없이 남고, 동일 작업의 자동 부족 요청이 거절되면 같은 요청을 반복 생성하지 않는다. 자동 추가 요청은 당장 필요한 1회만 제안하며 관리자는 별도 request에서 계획에 따른 수량을 제시할 수 있다.

execute는 전체 원장 서명·프로젝트/scope·만료·중복 operation_id·불명 요청·별도 공급자 동의를 검사한다. 예산 부족 시 전송 없이 추가 요청을 남기고 `budget_approval_required`로 멈춘다. 예산이 있으면 호출마다 대표 재승인을 요구하지 않는다. 외부 send 콜백 **전에** 소비 예약을 서명·영속화하며, 실패도 소비하고 동일 operation_id는 다시 보낼 수 없다. 타임아웃/연결 오류는 uncertain, 중간 시스템 장애는 reserved로 남아 새 전송도 막는다. 이 불명 상태의 자동 복구/재발송 경로는 없다. 같은 프로젝트의 동시 실행은 OS 잠금으로 차단한다.

예산 승인 자체는 데이터 전송 동의가 아니다. scope 변경(공급자·모델·계정·작업·목적·데이터 정책·동의 ID 포함)을 기존 원장으로 허용하지 않는다. 기존 provider grant/취소/키 바인딩/실제 전송 범위를 검사하는 verify_consent 콜백을 전송 전과 예약 후에 다시 호출하도록 설계했다. 이 콜백은 **운영 연결 측에서 반드시 기존 공급자 가드를 호출해야 하며**, 단순 True 콜백은 독립적인 실제 동의 증거가 아니다. 테스트에서는 기존 Gemini35Store의 실제 서명 구조를 임시 저장소에서 생성·철회하여 예산 승인과 별개로 전송이 차단됨을 검증했다. 유료 scope 생성은 거부하고 결제/카드 연결 기능은 없다.

실제 통화 비용은 이번에 계측하지 않았다. summary는 amount/currency=null, status=unknown이며 요청의 cost_impact는 계획 설명일 뿐 실측 비용이 아니다. 공급자 청구·토큰·쿼터 단위 계측은 구현하지 않았다.

## 검증 결과

모든 fixture는 합성이며 임시 저장소와 모의 전송을 사용했다. DNS와 socket.connect를 차단했다.

- `PYTHONPATH=core:companies/video python -B -m unittest tests.test_project_budget_ledger tests.test_video_mission_one`: **31개 통과, 7.487초** (당시 예산 8개 + 기존 미션 23개).
- 공급자 동의 철회·타임아웃 구분·프로젝트 바인딩 보강 후 관련 예산 테스트만 실행: `PYTHONPATH=core:companies/video python -B -m unittest tests.test_project_budget_ledger`: **10개 통과, 0.219초**. 전체 회귀 반복 없음.
- `git diff --check` 통과.

초기 견적→사용자 승인→여러 직원의 예약/소모→부족 전송 차단·단일 추가 요청→추가 승인 후 기존 이력 보존형 계속 진행을 검증했다. 거절/중복 결정, 만료/검토 해시 불일치, 서명 원장 변조·다른 프로젝트로 복사, 동시 전송, 실패/타임아웃/장애 소모, 중복 operation 재전송 금지, 미승인 예산 초과, 새 scope/유료 경로, 별도 동의 부재·철회 차단을 확인했다. 모의 전송 내부에서 예약 원장을 다시 읽어 서명된 reserved 상태가 실제 send 전에 영속화됐음을 확인했다. 실제 기획·대본·비용으로 등록하지 않았다.

## 보존·미완료·다음 단계

이번 실제 외부 API 요청 **0회**, 실제 미션 재시작/후속 업무/제안/서명 발급 **0건**. 미션 01의 세 stopped 업무와 컷룸 관련 JSON/consent/lock 10개 SHA-256이 직전 보존 기록과 동일하다. Gemini 누적 **6/10**, YouTube search **2/4**, videos **2/4**, 컷룸 **research_planning** 유지. 기존 failed attempt·active_operation·동의/비용 원장·키·데이터·백업·음성/영상 및 미추적 파일 7개 보존.

**부분 완료:** 공통 ledger/approval과 실제 send를 감싸는 실행 경계 및 영상 어댑터는 구현·오프라인 검증했다. 기존 모든 provider/직원 실행 진입점에 이 예산 모드를 설치한 것은 아니다. 컷룸의 실제 승인 UI/권한 있는 사용자 이벤트 연결, AI 관리자의 자동 견적 생성, 불명 예약의 수동 정산 절차, 토큰·quota units·통화 계측, 모델/계정 변경용 새 동의 연결, 기존 미션 01 이관은 미구현이다. 표시만으로 기존 운영에 예산 집행이 적용됐다고 주장하지 않는다. 기존 provider grant 자체의 고정 호출 제한도 자동 증액하거나 우회하지 않는다.

**다음 한 단계:** 새 프로젝트 한 경로에서 기존 provider 동의 검증을 유지한 채 이 어댑터와 컷룸 추가 승인 UI를 연결하고 격리 오프라인 통합 검증한다. 미션 01 이관/실제 API는 별도 검증·대표 승인 전까지 금지한다. GitHub 저장 후 중단한다.
