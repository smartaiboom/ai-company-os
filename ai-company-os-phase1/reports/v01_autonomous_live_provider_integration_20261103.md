# 자율 회사 실제 공급자 연결 경로 — 외부 송신 없는 통합 검증

2026-11-03 KST. `git pull --ff-only`로 main `4cb863c`를 반영한 뒤 작업했다. **기존 자율 업무 상태 기계에 별도 live 공급자·저장소·서명된 초기 운영 동의를 연결했고, fake HTTPS로 두 목표의 최종 JSON/Markdown 파일 생성을 검증했다. 실제 AI 한 사이클 실행은 아직 하지 않았다.** 실제 API/HTTP/DNS 송신 0회이며, Git 동기화는 이 통신 집계에서 제외한다. UI·대시보드 개발은 하지 않았다.

## 연결한 범위와 결정 주체

| 경로 | 이번 상태 |
|---|---|
| 기존 autonomous_mock | 기존 타입·marker·저장 규칙과 모의 동작 유지, 13개 기존 테스트 통과 |
| 새 autonomous_live | 생성 시 enabled=false, 동의 없음, 기존 프로젝트 자동 이전 없음 |
| live adapter + fake HTTPS | 기존 `ai_safety.request_json`과 `OpenRouterFreeAdapter`를 실제 통과, 외부 transport만 테스트에서 교체 |
| 실제 공급자 요청 | 코드 경로 구현, 이번 실제 동의·송신 없음. 공급자의 실제 응답 품질·가용성·완주 미검증 |

`autonomous_company.py:Company._run_workflow`가 계획→직원 수행→검토/수정→후속 직원→최종 통합을 공통 실행한다. Mock 공개 생성자는 여전히 정확한 mock 공급자와 mock Store만 받는다. Live 공개 생성자는 정확한 LiveStore/LiveManagerProvider/LiveEmployeeProvider/LiveConfig만 받는다. 저장소 marker도 `.autonomous-mock-store`와 `.autonomous-live-store`로 다르다.

`autonomous_live.py:LiveCompany._call`은 manager와 employee 역할을 나누어 실제 Chat Completions 요청을 구성한다. 목표에 맞는 계획·기준·배분, 직원 내용, accept/revise/stop, 최종 통합 본문은 모델 응답으로만 결정한다. 프로덕션 모듈에 도서관·창고 규칙이나 fixture를 복사하지 않았다. 도메인별 가짜 출력은 기존 `tests/support/autonomous_company_fixtures.py`에서만 제공한다. 실제 경로에 임의 콜백/transport를 받는 생성자나 fallback은 없다.

역할별 exact 필드·JSON 중복/NaN 금지·문자열 크기·의존 순서·기준 참조·검토 기준 전체 포함을 검사한다. 응답은 choice 1개, assistant, finish_reason=stop만 허용하고 tool/function 호출을 거부한다. 관리자 accept/deliver는 unknown/unmet 기준을 통과시킬 수 없다. 외부 확인 도구가 없고 모든 평가 근거는 model_claim이며, 최종 문서에도 독립 사실 검증 미실시를 표시한다. 실제 문장의 진실성을 코드가 보장한다는 뜻은 아니다.

직원은 수락된 최신 선행 버전만 받는다. 수정 시 직전 관리자 feedback을 받으며 버전/검토 이력을 보존한다. 최종 `task_refs`는 모델에게 SHA 계산을 맡기지 않고 프로그램이 최신 결과와 정확히 결합한다. 원장에는 role/phase/task/provider, 입력·선행·결과 hash, grant/session ID, KST와 검증 상태가 남는다. 업무 결정 이벤트에는 rationale·근거·불확실성과 직원 버전이 남는다.

## 최초 운영 동의와 취소

`LiveStore.prepare`는 검토 제안만 반환하며 서명 키·동의 레코드·활성화를 만들지 않는다. `approve`는 별도 명령으로 다음 전체 계약을 검증하고, 검토 hash 및 명시적 owner_confirmed=True를 요구한다.

| 계약 필드 | 범위/검증 |
|---|---|
| project_id, goal_hash, initial_state_hash | 새 프로젝트와 정확한 목표 및 승인 전 상태에 결합. 다른 목표/프로젝트·오래된 상태 거부 |
| scopes | goal, generated_plan, generated_criteria, assignments, employee_results, manager_reviews, final_integration의 정확한 목록 |
| provider/model/endpoint | openrouter / openrouter/free / https://openrouter.ai/api/v1 고정 |
| limits.max_calls | 프로젝트 최대 1~20회. 실패·timeout·예약도 소진 횟수에 포함 |
| per_start | 명시적 시작/재개당 1~2회, 기존 공통 요청 한도 2도 유지 |
| max_cost/free_only | 정수 0 / true, 유료 모델·비용 증가·fallback 금지 |
| 수정 한도 | 기본 업무당 1회·총 2회. 설정 가능 범위 업무당 0~2·총 0~4, 승인 후 확대 금지 |
| issued_at/expires_at | KST, 기본 24시간·최대 7일, 미래 발급·만료·잘못된 시간대 거부 |
| rules | 자동 재시도 false, 불확실 상태 정지 true, 실패 집계 true, 업무 결재 false, 외부 도구 없음 |

자료 범위는 해당 새 프로젝트 목표와 그로부터 생성한 계획/기준/배정/직원 결과/검토·수정 의견/통합 결과다. 요청의 고정 프로토콜에는 역할·단계·한도·출력 계약·검증 불가 안내도 포함한다. 기존 업무 데이터·다른 프로젝트·업로드·파일·웹 자료·키/인증 헤더는 역할 입력에 포함하지 않는다. 단계별 최상위 context 필드 허용 목록을 검사한다. 키가 입력/응답에 섞이면 차단하며 JSON unicode escape로 감춘 응답 키도 파싱 후 재검사한다.

동의는 별도 저장소 내부의 API 키와 무관한 로컬 32바이트 키로 HMAC 서명하고, 원자적 저장/fsync한다. 승인 이벤트는 grant ID와 계약 hash를 남긴다. 서명된 계약과 기존 `real_ai.consent`의 목표·자료 전송 동의를 연결한다. 기존 수동 업무 승인 레코드를 위조하거나 수동 API를 수정하지 않는다. 승인 재사용·다른 프로젝트 적용·서명 변조·범위 증가를 차단한다. 서명 키와 상태 파일의 보안은 로컬 OS 계정의 신뢰 경계에 속한다.

`revoke`는 명시적 소유자 확인과 독립 잠금 아래 서명된 revoked_at을 저장한다. 실행 중에도 취소 가능하며 매 요청 전 및 영속 예약 후 transport 직전에 재검사한다. 이미 송신 중인 요청은 취소/회수할 수 없고 완료 기록을 보존한다. 취소/만료/불확실 상태에 대한 자동 재활성화·동의 갱신·재시도 경로는 없다. 이번 동의/취소 검증은 모두 `/tmp`의 가상 프로젝트에서만 수행했다. 실제 운영 동의 레코드는 생성하지 않았다.

## 원장·한도·중단·재개

기존 `ai_safety.py`, `ai_provider_adapter.py`, 수동 live 보호 API는 변경하지 않았다. 기존 서버 활성화/엔진 설정, 정확한 AI_MODEL, 고정 HTTPS 주소와 키가 모두 필요하다. 실행기가 환경 설정을 자동으로 켜지 않는다. proxy/redirect 금지와 90초 timeout, 입력 131072바이트·응답 262144바이트·출력 4096토큰 상한을 재사용한다. 역할 JSON 본문은 추가 131072바이트/필드별 상한을 적용한다.

실제 요청 예약은 **real_ai.attempts 한 곳에만** 기록한다. 별도 mock attempts는 존재하지 않는다. 기존 요청 함수가 만드는 entry에 role/context/grant/session 메타데이터를 덧붙이고, 디스크 예약 후에만 transport를 호출한다. HTTP 처리 completed와 업무 JSON 검증 상태(unvalidated/json_parsed/validated)는 별도로 표시한다. HTTP 성공이어도 계약 오류/미완료 응답이면 업무는 stopped다.

한 번의 start/resume 전체가 단일 request_scope를 사용한다. 2회 도달 시 정상 체크포인트를 paused로 저장하며 자동 새 scope를 열지 않는다. 다음 실행은 사용자가 별도 resume 명령과 최신 state hash를 명시해야 한다. 이것은 업무 결과 승인과 다르며, 현재 2회/시작 제한 때문에 남아 있는 운영 개입이다. 전체 사이클을 무제한 자동 재개하는 기능은 넣지 않았다.

완료된 단계는 커밋된 phase/task state로 건너뛴다. 원장 failed/reserved, active_operation 잔류, 응답 수신 완료 후 상태 적용 전 강제 종료는 자동 재전송하지 않는다. 업무 체크포인트 적용 직후 프로세스 종료는 새 실행기에서 해당 단계 반복 없이 재개한다. 프로젝트 OS 잠금·낙관적 저장 hash·실행기 재진입 잠금·최신 실행 hash로 중복/동시 호출을 차단한다. 지원되지 않는 OS 잠금은 허용하지 않는다. stopped/needs_operational_permission/예산 소진은 최종 완료로 표시하지 않는다.

## 최소 명령 경로

아래는 사용법이며 이번에 실제 운영용 명령을 실행하거나 동의를 기록한 내역이 아니다. `NEW_STORE`는 기존 업무/백업과 분리된 새 경로, `PROJECT_ID`는 create 출력값이다. 키 값은 명령 인자·보고서에 쓰지 않고 보호된 프로세스 환경으로만 공급한다.

```bash
python -B -m autonomous_live_cli --store NEW_STORE create --goal '사용자가 맡길 목표'
python -B -m autonomous_live_cli --store NEW_STORE prepare PROJECT_ID --proposal-out /tmp/operating-proposal.json
```

출력된 목표·contract 전체와 review_hash를 소유자가 확인한다. proposal 파일은 기존 파일을 덮어쓰지 않고 생성한다. 그 뒤 **외부 전송과 운영 범위의 최초 동의**를 명시할 때만 다음 별도 명령을 사용한다.

```bash
python -B -m autonomous_live_cli --store NEW_STORE approve PROJECT_ID --proposal /tmp/operating-proposal.json --review-hash REVIEW_HASH --owner-confirmed
python -B -m autonomous_live_cli --store NEW_STORE status PROJECT_ID
python -B -m autonomous_live_cli --store NEW_STORE start PROJECT_ID --state-hash CURRENT_STATE_HASH
# paused 또는 정상 체크포인트 중단 후, 새 상태 해시로 별도 명시 실행
python -B -m autonomous_live_cli --store NEW_STORE resume PROJECT_ID --state-hash NEW_STATE_HASH
python -B -m autonomous_live_cli --store NEW_STORE revoke PROJECT_ID --owner-confirmed
```

환경에는 기존 안전 규칙대로 AI_REAL_REQUESTS_ENABLED=1, AI_ENGINE=openai_compatible, AI_MODEL=openrouter/free, AI_BASE_URL=https://openrouter.ai/api/v1 및 보호된 AI_API_KEY가 필요하다. 동의 명령은 이를 자동 설정하지 않으며 start/resume은 동의를 만들지 않는다. status는 원장 횟수·상태·최신 해시·최종 파일 경로/hash를 읽기만 한다. 최종 내용은 해당 로컬 final.json/final.md에서 확인한다. CLI 출력에는 역할 응답 원문이나 인증 정보를 출력하지 않는다.

## 오프라인 실행 증거

| 가상 목표 | fake HTTPS 요청 | 명시적 실행 구간 | 수정 | 업무 결재 | 결과 |
|---|---:|---|---:|---:|---|
| 도서관 초방문 안내 | 6 | 2→4→6 | 0 | 0 | delivered, final.json/final.md |
| 창고 재고 인수인계 | 8 | 2→4→6→8 | 1 | 0 | delivered, final.json/final.md |

`python -B /tmp/generate_live_integration_evidence.py`로 외부 socket/DNS를 차단하고 fake transport만 주입하여 생성했다. 테스트용 가상 키와 합성 운영 동의만 사용했으며, 각 구간은 새 실행기 객체와 최신 상태 hash로 시작/재개했다. **이는 실제 AI 요청 14회가 아니라 가짜 HTTPS 응답 14회다.** 프로덕션 모듈이 이 반복 실행 스크립트를 사용하거나 자동 재개하는 일은 없다.

증거는 커밋하지 않고 다음 임시 경로에만 남겼다.

- 요약: `/tmp/live_integration_evidence_manifest_20261103.json` (FAKE_HTTPS_ONLY_NOT_ACTUAL_AI 표기).
- 상태/산출물 루트: `/tmp/ai_company_os_fake_https_live_integration_20261103`.
- 도서관 ID: `livecompany-160837cf56e8410b8346caa71fb31dfd`.
- 창고 ID: `livecompany-637c195eeec54e5799bc66b10d7663d8`.
- 각 ID 아래 `artifacts/ID/final.json`, `final.md`. 별도 읽기 프로세스로 delivered·업무 결재 0·파일 4개의 SHA-256을 다시 확인했다.

## 검증 결과·보존

- `python -B -m unittest tests.test_autonomous_company`: 최초 공통 코드 분리 후 **13/13 통과**.
- `python -B -m unittest tests.test_autonomous_live tests.test_autonomous_company`: **36/36 통과** (신규 live 23 + 기존 mock 13).
- `python -B /tmp/run_live_integration_regression.py`: 최종 **354/354 통과**. 기존 수동 관리자/직원 승인·최종 보고·예산/불확실 예약·동시성·공급자 adapter·기존 자율 workflow 회귀 포함. 예산 서명 키는 임시 경로로 격리했다. 결과 로그 `/tmp/live-integration-regression-final.log`.
- 초기 미승인/명시 확인 누락/검토 해시/서명 변조/만료/범위·비용·모델·URL·횟수 위반은 무송신 차단. 취소 전·중·예약 직후 차단, timeout 소진과 무재시도, length/JSON 중복·불량/키 유출·escape/도구 호출/불량 envelope, unknown 품질·수정 상한·예산 소진·크기 상한을 검증했다.
- 강제 중단 테스트: 상태 적용 직후 종료는 완료 계획 재호출 없음, HTTP completed 저장 직후 종료는 불확실 active_operation 때문에 재송신 없음. 잠금 충돌·동일 실행기 동시 실행·오래된 resume hash도 차단했다.
- 개발 중 잘못된 소스 파일명 `ai_engine.py` 검색은 파일 없음으로 끝났고, 실제 `execution_engine.py`와 관련 소스를 확인했다. 최종 문서 점검 스크립트의 존재하지 않는 문구에 대한 literal assertion 1회 실패는 실제 원칙 문구로 수정해 재확인했다. 제품 테스트 실패나 미해결 충돌은 없었다. 추가 검토에서 JSON escape 키 유출 가능성과 불량 envelope 예외를 보완하고 검증했다.
- 시작 시 보존 SHA-256 35개(기존 data/backups 29개 + 기존 미추적 6개)를 종료 전에 다시 대조: **변경 0, data/backups 추가·삭제 0**. 기존 미추적 파일과 상위 디렉터리 업무 파일은 수정/스테이징하지 않았다.
- `cb44b605b498`는 **9/20, completed 9, failed/reserved 0**. TASK/승인 답변/원장 전체 파일 hash 동일. `c85d9853906a` 포함 다른 프로젝트·백업도 동일하여 기존 unresolved 차단이 유지된다.
- 실제 AI 호출 **0회**, 새 실사용 동의 **0건**, 비용 **0**. 실제 키·.env·사용자 JSON 원문을 출력하거나 커밋하지 않았다. 기존 안전 모듈·app.py·최상위 문서는 변경하지 않았다.
- 시작·핵심 구현 판단·완료 직전에 최상위 원칙/AGENTS/한국어 지침을 대조했다. 초기 운영 권한과 업무 판단을 분리하고, 화면 대신 실제 역할·원장·산출물 경로를 구현했다.

변경 파일은 `autonomous_company.py`(공통 상태 기계/저장 확장 지점), `autonomous_live.py`(격리 저장·동의·live 역할 요청), `autonomous_live_cli.py`(동의 준비/별도 승인/실행/조회/취소), `tests/test_autonomous_live.py`, 이 보고서다. Git diff 검사 후 이 파일만 선택 커밋/푸시한다. 실제 응답·동의 원문·키·증거 상태 파일은 커밋하지 않는다.

## 남은 실제 검증과 다음 사용자 행동 하나

**새 자율 프로젝트의 목표·ID에 결합된 초기 운영 범위를 한 번 명시 승인하는 것**이 다음 사용자 행동이다. 검토 범위는 위 7개 자료 유형, OpenRouter/free 고정 HTTPS, 총 최대 20회·명시적 시작/재개당 최대 2회, 비용 0/무료 전용, 업무당 수정 1회·총 2회, 24시간 유효, 실패/불확실 자동 재시도 없음·취소 가능이다. 실제 계약의 목표/ID/초기 상태 hash/기간을 확인한 후 승인해야 하며 기존 9/20 프로젝트 승인을 재사용하지 않는다. 업무 내용의 중간 승인은 요구하지 않는다.

그 승인과 보호된 서버/키 설정이 유효해진 이후에만 실제 공급자의 가용성·엄격 JSON 계약 준수·모델 판단 품질·실제 최종 산출물 완주를 검증할 수 있다. 현재 2회/시작 제한에 따른 명시 재개는 남아 있으며 자동 우회하지 않는다. **이번 완료는 안전한 실행 코드와 fake HTTPS 종단간 검증까지이며, 실제 AI 한 사이클 완주는 미완료다.**
