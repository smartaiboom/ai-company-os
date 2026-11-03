# 무료 자율 실행: 인위적 호출 상한 없이 한 번의 run으로 완주

2026-11-03 KST. `git pull --ff-only`로 main `f979cbc`를 반영하고 최상위 원칙 4-1항을 적용했다. **새 무료 자율 정책에서는 기본 총 호출 수와 실행당 호출 상한을 없앴다. 초기 운영 동의 후 CLI run 한 번으로 관리자 계획→직원 수행→검토/수정→선행 전달→최종 JSON/Markdown까지 진행한다.** 세 목표에서 fake HTTPS로 검증했으며, 실제 AI 한 사이클 성공을 주장하지 않는다. UI·대시보드는 개발하지 않았다.

실제 AI/HTTP/DNS 송신 **0회**, 실제 운영 동의 생성 **0건**, 금전 비용 **0**. Git 동기화 통신은 이 AI 실행 통신 집계에서 제외한다. 새 테스트는 가짜 키·합성 운영 동의·격리된 `/tmp` 저장소·외부 socket/DNS 차단·fake transport만 사용했다. 새 무료 테스트에서 기존 `AI_REAL_REQUESTS_ENABLED`는 **0**이며 실제 환경/guard/.env를 수정하지 않았다.

## 변경 전 제한과 새 정책의 분리

| 계층 | 기존 정책 | 이번 처리 |
|---|---|---|
| `LiveStore.create/load/_check_contract` | max_calls 1~20, per_start 1~2를 저장·서명·검증 | 기존 코드와 승인 계약을 유지 |
| `LiveCompany._call` | 실행마다 used와 per_start 비교 | 기본 동작이 같은 보호 훅으로 추출; 기존 LiveCompany에서는 여전히 검사 |
| `ai_safety.request_json/request_scope` | scope당 최대 2회, 누적 입력과 프로젝트 예산 검사 | **변경 없음** |
| `project_budget.limit` | 기본 20, 추가 예산은 기존 서명 정책 | **변경 없음** |
| 새 `FreeStore/FreeCompany` | 별도 free_autonomous_v2 정책 | 총/실행당 비용성 상한 없음, 무료 전용 영속 원장 경로 |

`autonomous_free.py`의 새 모드는 `autonomous_live_free_v2`, marker는 `.autonomous-free-v2-store`, ID는 `freecompany-…`, policy_version은 2다. 기존 mock 및 bounded live namespace와 섞이지 않는다. 새 `real_ai`에는 legacy `limit` 필드가 없고, 기본 `limits.max_calls=null`, 서명 계약의 `call_policy.total/per_run=null`이다. 선택적 `--max-calls N`만 소유자가 지정한 기술 상한으로 집행한다. 정상 작업을 2회/20회에서 끊거나 공통 request_scope를 몰래 반복 생성하지 않는다.

기존 경로에 “무료면 검사 생략” 조건을 추가하지 않았다. `FreeCompany`는 정확한 FreeStore·live 역할 타입·설정만 받으며, legacy 저장소/동의는 거부한다. 기존 동의 재서명·자동 확장·마이그레이션은 없다. CLI는 기존 `.autonomous-live-store`를 발견하면 계속 기존 LiveStore/LiveCompany로 처리하며, 새 `run/continue` 명령으로 과거 계약을 확장하려는 시도도 거부한다. 새 경로는 **새 빈 저장소**로 만든다.

`autonomous_live.py`에는 세션 검사·요청 실행·payload·전송 전 점검의 보호 훅만 추가했다. 기존 타입 제한과 2회/20회 동작은 회귀 검증했다. `autonomous_company.py`의 mock 엔진과 공통 업무 상태 기계, 기존 수동 live API, `ai_safety.py`, `project_budget.py`, `ai_provider_adapter.py`, `app.py`는 수정하지 않았다.

## 단 한 번의 실행 증거

`python -B /tmp/generate_free_single_run_evidence.py`가 CLI의 실제 `main(... run ...)`을 목표마다 정확히 한 번 호출했다. 전송만 fake HTTPS로 교체하고 고정 OpenRouter adapter, Authorization 헤더 구성, 역할 JSON, 영속 예약/원장, 서명 계약, 공통 업무 상태 기계를 통과했다.

| 목표 | CLI run | fake 요청 | 수정 | 업무 결재 | 중간 resume | 최종 파일 |
|---|---:|---:|---:|---:|---:|---|
| 도서관 초방문 안내문 | 1 | 6 | 0 | 0 | 0 | final.json + final.md |
| 창고 재고 인수인계 안내문 | 1 | 8 | 1 | 0 | 0 | final.json + final.md |
| 지역 행사 운영 안내서 | 1 | **22** | 2 | 0 | 0 | final.json + final.md |

22회는 의미 없는 반복이 아니다. AI 응답 형식의 계획이 **요구사항→시간표→장소 동선→접근성→안전 대응→개인정보→자원봉사→안내 통합**의 8개 의존 업무를 배정한다. 요구사항/시간표의 비상 연락 확인 담당과 일정 변경 공지 절차 누락을 관리자가 지적하고 직원이 보완한다. 계획 1 + 직원/검토 16 + 재작성/재검토 4 + 통합 1 = **22회**다. 후속 직원은 수락된 최신 선행 버전을 받는다. 이 도메인별 업무/판단은 `tests/test_autonomous_free.py:EventGuideModels`에만 있는 가상 출력이며 프로덕션 로직에 복사하지 않았다.

증거는 실제 AI 결과와 혼동하지 않도록 `FAKE_HTTPS_ONLY_NOT_ACTUAL_AI`로 표시한 임시 manifest와 경로에 남겼다. 응답·동의 원문·상태 파일은 Git에 넣지 않는다.

- manifest: `/tmp/free_single_run_evidence_manifest_20261103.json`.
- 저장 루트: `/tmp/ai_company_os_free_single_run_fake_https_20261103`.
- 도서관 ID: `freecompany-9234b1a139be401a92f7fb48cc775d7d`.
- 창고 ID: `freecompany-6f8dcf6d9abe436da47d29b02ed234da`.
- 행사 ID: `freecompany-338b67370b34473cb0e9ce8224dd8be9`.
- 각 상태는 `ROOT/ID.json`, 최종 파일은 `ROOT/artifacts/ID/final.json`, `final.md`. 별도 읽기 프로세스에서 delivered·실행 session 1·업무 결재 0·산출물 6개의 SHA-256을 다시 확인했다.

세 사례의 요청 간 가상 대기 합계는 각각 10/14/42초다. 이는 테스트의 가상 시계가 검증한 스로틀링이며 실제 API 대기/호출 기록이 아니다. 총 36건은 **가짜 HTTPS 요청**이며 실제 API 요청은 0건이다.

## 계속 적용하는 안전 제어

- **최초 운영 동의**: prepare는 제안만 반환한다. 별도 approve에 owner_confirmed, 검토 hash, 최신 초기 상태 hash, 프로젝트/목표 결합을 요구한다. 서명은 해당 격리 저장소의 API 키와 무관한 로컬 HMAC 키로 만든다. 기존 grant 승인/취소·원자 저장 기능을 재사용하되, 새 정책 필드 검증은 FreeStore가 담당한다. 다른 목표·scope·정책·기간·무료 조건·수정 한도·서명 변조를 거부한다.
- **비용 0/모델**: AI_MODEL과 요청 모델 모두 정확히 openrouter/free, provider는 OpenRouter, endpoint는 고정 HTTPS다. 요청에 `provider.max_price.prompt=0`, `completion=0`, `allow_fallbacks=false`를 강제하고 변경을 거부한다. 공급자 응답 `usage.cost`는 숫자 0만 허용한다. 누락/양수/문자열/bool이면 완료로 처리하지 않고 정지한다. 모델 변경·유료 fallback·계정 전환·결제 기능은 없다.
- **실제 공급자 계약의 한계**: 고정 무료 모델과 가격 0 필터를 요청 전에 강제하지만, 실제 제공자가 이 요청 옵션을 지원하고 비용 정보를 정확히 반환하는지는 이번 외부 송신 금지 때문에 검증하지 않았다. 실제 응답에서 비용 0을 확인하지 못하면 첫 요청부터 정지한다. 제공자가 정책을 위반한 요금을 반환했을 때 되돌릴 수 있다는 뜻은 아니다. 실제 공급자 가용성·무료 조건·엄격 JSON/usage.cost 준수는 이후 승인된 실송신 검증 대상이다.
- **영속 예약/중복 방지**: `real_ai.attempts` 단일 원장에 reserved를 저장/fsync한 뒤에만 송신한다. 별도 mock 원장은 없다. role/phase/task/grant/session/context/dependency/result hash에 더해 request/가격 정책 hash·operation_hash를 기록한다. 같은 작업 입력의 operation_hash 재사용, active_operation, failed/reserved, 완료됐어도 업무 검증이 확정되지 않은 attempt는 재전송하지 않는다. completed는 HTTP 수신 상태이고 role_result_status=validated 및 cost_verified_zero는 별도로 기록한다.
- **공급자 제한/속도**: 프로젝트별 송신 간 최소 2초를 적용하고 다음 송신 가능 시점을 디스크에 보존한다. 이는 알려진 공급자 쿼터를 보장하는 수치가 아니라 보수적인 앱 pacing이다. 대기 중에도 취소·만료를 점검한다. HTTP/오류 envelope의 429는 provider_rate_limit, 402는 quota/요금 요구, 502/503/504는 공급자 장애로 pause한다. 안전한 Retry-After 숫자는 기록하되 자동 재시도하지 않는다. 다른 오류/timeout도 실패 원장과 중단 상태를 보존한다. 여러 계정/유료 fallback으로 우회하지 않는다.
- **수정/품질 정체**: 기본 업무당 수정 1회·총 2회, 허용 설정 범위 업무당 0~2회·총 0~4회다. 이전과 동일한 직원 본문은 근거 문구/공백만 바꿔도 진행으로 인정하지 않는다. 동일한 revise 지시와 기준 판정 반복도 quality_stagnation으로 정지한다. 업무/기준은 최대 8개, 계획은 한 번의 유한 DAG이며 새 업무를 무한 추가하지 않는다. 이 구조상 가능한 호출 수가 유한한 것은 품질/자원 제어이며 20회 비용 상한을 다른 숫자로 바꾼 것이 아니다.
- **기한/자원**: 최초 실행부터 30분의 벽시계 기한을 상태에 보존하여 continue로 초기화하지 않는다. 실행 중 monotonic 시간도 검사하며 비정상 시계/스로틀 정체를 차단한다. 동의 기본 유효기간은 24시간·최대 7일이다. 요청 timeout 최대 90초, 입력 131072바이트·응답 262144바이트·출력 4096토큰, 필드별 크기/저장 상태 크기 제한을 유지한다. 기한 도달 후 새 송신을 막으며 이미 진행 중인 요청은 즉시 회수할 수 없다.
- **권한/정보**: 7개 승인 scope와 단계별 context 필드, 목표/mode/limits 결합을 검사한다. 키는 payload/응답에 섞이지 못하며 오류 원문·응답 원문·헤더를 로그에 남기지 않는다. JSON escape 키 유출 차단과 stop-only/중복 JSON/tool 호출 거부는 기존 역할 검증을 재사용한다. 외부 확인 도구가 없고 근거는 model_claim이며 unknown을 accept/deliver로 바꾸지 않는다.
- **사고 후 재시작**: 정상 run에는 중간 start/resume이 없다. 상태 적용 직후 프로세스 종료처럼 완료가 확정된 clean checkpoint만 최신 상태 hash를 지정해 `continue`할 수 있다. 완료 단계는 재호출하지 않는다. 응답 수신 후 상태 적용 전 종료, timeout, 실패/불확실 예약, 공급자 pause에는 자동/묵시 재전송·복구 동의 생성이 없다. 해당 pause를 풀어 재시도하는 운영 복구 기능은 이번에 구현하지 않았다.

## 최소 실행 경로와 첫 실사용 동의에 보여줄 내용

아래는 사용법이며 이번 작업에서 실제 프로젝트/동의를 만든 명령이 아니다. 새 빈 `NEW_FREE_STORE`와 사용자 목표를 사용하고, 키를 명령 인자/파일·출력에 넣지 않는다.

```bash
python -B -m autonomous_live_cli --store NEW_FREE_STORE create --goal '맡길 목표'
python -B -m autonomous_live_cli --store NEW_FREE_STORE prepare PROJECT_ID --proposal-out /tmp/free-operating-proposal.json
# 목표·계약 전체·검토 hash를 확인한 소유자만 별도 승인
python -B -m autonomous_live_cli --store NEW_FREE_STORE approve PROJECT_ID --proposal /tmp/free-operating-proposal.json --review-hash REVIEW_HASH --owner-confirmed
python -B -m autonomous_live_cli --store NEW_FREE_STORE run PROJECT_ID --state-hash APPROVED_STATE_HASH
python -B -m autonomous_live_cli --store NEW_FREE_STORE status PROJECT_ID
python -B -m autonomous_live_cli --store NEW_FREE_STORE revoke PROJECT_ID --owner-confirmed
```

새 경로는 기본 비활성이다. 별도 서버 설정 `AI_AUTONOMOUS_FREE_ENABLED=1`, AI_ENGINE=openai_compatible, 정확한 AI_MODEL/AI_BASE_URL와 보호된 AI_API_KEY가 필요하며 CLI가 자동 설정하지 않는다. 기존 수동 요청 guard를 켜거나 우회하는 기능이 아니다. 새 테스트는 이 별도 flag만 테스트 프로세스 안에서 가상으로 설정하고 실제 transport를 차단했다. 기존 회귀 테스트의 합성 환경/가짜 요청은 그대로 유지했다.

실사용 전에 소유자에게 **한 번** 보여주고 받을 내용은 다음과 같다.

> 이 새 프로젝트 ID·목표·초기 상태 hash에 한하여, 목표와 생성 계획/기준·업무 배정·직원 결과·관리자 검토/수정 의견·통합 결과를 OpenRouter의 고정 HTTPS openrouter/free로 전송합니다. 앱의 기본 총/실행당 비용성 호출 상한은 없으며 업무상 필요한 요청을 한 run에서 이어갑니다. 공급자의 실제 무료 조건·쿼터·속도 제한은 준수하고 비용 0 필터를 강제하며, 비용 정보가 불명확하거나 요금을 요구하면 정지합니다. 유료 전환·fallback은 없습니다. 동의는 기본 24시간, 실행 기한은 최초 시작부터 30분입니다. 최대 업무/기준 8개, 업무당 수정 1회·총 2회, 최소 송신 간격 2초이며 실패/불확실/중복/정체에는 자동 재시도하지 않습니다. 언제든 취소할 수 있으나 이미 송신 중인 자료를 회수할 수 없습니다. 업무 내용에 대한 중간 결재·2회마다 재개는 요구하지 않습니다.

선택적 기술 상한을 설정했다면 해당 숫자도 실제 계약에 표시한다. 문서나 이번 개발 위임으로 이 운영 동의를 이미 얻었다고 간주하지 않는다. 프로덕션에 새 동의나 서버 flag를 생성/활성화하지 않았다. 실제 AI 한 사이클의 품질·제공자 계약 준수 확인은 이 초기 동의와 보호된 서버 설정 이후의 별도 실송신 검증으로 남아 있다.

## 미래 유료 확장 경계

이번에는 paid mode 자체가 없다. `FreeStore._check_contract`와 `FreeCompany._preflight/_prepare_payload/_request_json`은 무료 전용 계약/모델/가격 0을 강제하므로 유료 전환 지점으로 재사용해 몰래 완화하면 안 된다. 향후 유료 지원은 별도 정책·서명 동의/저장 namespace, 허용 모델·요율/최대 토큰·회당/총 금액 예산, 송신 전 최대 예상 비용 예약, 응답 후 실제 비용 정산/검증, 예산 부족 사전 정지·추가 승인·불확실 비용 보존을 먼저 설계/검증해야 한다. 기존 `project_budget`의 횟수 예산만으로 금전 예산을 대신할 수 없다.

## 테스트·보존·변경 파일

- `python -B -m unittest tests.test_autonomous_live`: 보호 훅 추출 후 **23/23 통과**.
- `python -B -m unittest tests.test_autonomous_free`: 초기 **18개 중 1개 실패**. 22번째 최종 응답을 처리하는 공용 FakeHTTPS 변환기가 기대한 task_refs를 행사 fixture가 누락했다. 올바른 테스트용 참조를 보완한 뒤 통과했다. 프로덕션에서는 기존처럼 프로그램이 최신 결과 hash를 결합한다. 이 실패에서도 엔진은 완료를 가장하지 않고 free_request_failed로 정지했다.
- `python -B -m unittest tests.test_autonomous_free tests.test_autonomous_live tests.test_autonomous_company`: 최종 **58/58 통과** (새 무료 22 + 기존 bounded live 23 + mock 13). 로그 `/tmp/free-all-focused-final.log`.
- `python -B /tmp/run_free_cycle_regression.py`: **376/376 통과**. 기존 자율 업무/manager·employee 승인·수동 live 보호·2회/20회·미확정 예약·프로젝트 예산·최종 보고·동시성 회귀 포함. 예산 서명 키는 테스트 전용 임시 경로로 격리했다. 로그 `/tmp/free-cycle-regression-final.log`.
- 무동의/소유자 미확인/검토·초기 상태 hash/서명·scope·목표·정책/무료 조건·URL·모델·기한/한도 확대/취소를 검사했다. 쿼터·요금·장애 pause와 무재시도, 비용 누락·양수, 가격 필터 완화, timeout·응답 크기/JSON/finish_reason/tool/키 유출, 선택적 상한, 품질 정체·수정 상한·unknown, 중복 operation/동시 잠금, clean crash continue·ambiguous 완료 무재전송을 검증했다.
- 테스트는 외부 socket connect/connect_ex/sendto·DNS 등의 호출을 차단하고 urllib transport를 fake로 교체했다. 스로틀링은 가상 시계로 검증했다. 실제 API 호출/요금·공급자 웹 조회는 하지 않았다.
- 시작 SHA-256 기준 **35개(기존 data/backups 29개 + 기존 미추적 6개)**를 재대조하여 변경 0. data/backups 추가·삭제 0. 기존 상위 디렉터리 업무/미추적 파일도 수정·스테이징하지 않는다. 삭제·초기화·reset/clean/force push 없음.
- `cb44b605b498`: **9/20, completed 9, reserved 0**. 기존 TASK-003/004 대기와 승인/원장 전체 파일 hash 동일. `c85d9853906a` 등 다른 프로젝트/백업도 hash 동일하여 기존 unresolved 보호를 유지한다.
- 시작·개발 중·완료 직전에 최상위 원칙 4-1항, AGENTS, 한국어 규칙을 재확인한다. 사용자 중간 업무 개입을 없애되 실제 운영 권한·보안은 별도로 집행했다.

변경 파일: `autonomous_free.py`, `autonomous_live.py`(기본 동작 유지하는 보호 훅), `autonomous_live_cli.py`(새 프로젝트 기본 무료 정책 및 단일 run/사고용 continue), `tests/test_autonomous_free.py`, 이 보고서. `git diff --check`와 선택적 커밋·푸시/원격 확인으로 마무리한다. 실제 데이터·동의·응답·키·guard는 Git 변경 대상이 아니다.
