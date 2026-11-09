# 승인된 Groq 합성 호환성 POST 1회 — HTTP 403

2026-11-04 KST. `git pull --ff-only` 성공, main `50083a9` 반영. 핵심 원칙·AGENTS.md·한국어 규칙·지정 진단/첫 실사용 보고서·Groq adapter/transport/무료 계정/원장 경로를 확인했다.

**사전 오프라인 검증 후 승인된 합성 Groq POST를 정확히 1회 수행했고 HTTP 403을 수신했다. 호환성 시험 실패다. 기존 실패 프로젝트는 변경하지 않았으며 추가 AI API 요청 0회, 기존 프로젝트 approve/run/continue 0회, 유료 업그레이드·fallback·재시도 0회다.** Git 통신·공식 공개 문서 조회는 AI API 호출과 별개다. AI 회사 관리자·직원 협업이나 MP4 생성은 수행하지 않았다.

## 승인·계정·요청 검증

실행 근거는 `codex_tasks/v01_groq_one_post_synthetic_compat_approved_20261104.md`의 특정 합성 진단 POST 최대 1회 승인과 이번 사용자 요청이다. 사용자가 앞서 대화에 붙여 넣은 ready JSON을 실제 API 성공 증거로 사용하지 않았다.

- 승인된 요청 canonical SHA256: `5886294a7a7e81271ebca9f67f25118cec3468b866b3c0eb5463f391a2c9367a`.
- 승인 문서 파일 SHA256: `7d93b11dd7d79c53fe1df9ea7bf28b1d491f8cca49643898911626383981f8f0`. 키 hash가 아닌 사용자 승인 문서의 식별자다.
- 고정 모델: `openai/gpt-oss-20b`, 공급자 Groq.
- 고정 POST URL: `https://api.groq.com/openai/v1/chat/completions`.
- 본문은 지시서에 명시된 합성 system/user messages와 작은 strict schema 그대로다. `max_completion_tokens=512`, `reasoning_effort=low`, nested anyOf·각 object required/additionalProperties=false를 유지했다.
- UTF-8 canonical JSON bytes의 SHA256을 고정 기대값과 비교하고 adapter Request.data가 해당 bytes와 같은지 확인했다. SDK의 추가 필드·프롬프트 변경·임의 payload 교체는 없다.
- 계정 확인 유효 종료 및 새 승인 만료: **2026-11-05T11:35:43+09:00 KST**.

개발 전 `2026-11-04T12:10:45+09:00` 및 실제 송신 전 preflight에서 지시서 hash/요청 hash/계정 유효기간/키 결합/고정 provider 설정을 확인했다. 오프라인 검증 완료 후 `12:14:21 KST`에도 모두 통과했고, 실제 실행 프로세스는 `12:40:06 KST`에 선예약 전·후 다시 검증했다. 모든 시각은 만료 전이었다.

무료 계정 근거는 사용자가 직접 확인한 Free $0 Current Plan·Developer 미활성·20B 모델 한도 및 기존 로컬 계정 확인 자료다. `/tmp/groq-account-reviewed-proposal-20261104.json`의 정확한 digest와 free_plan/billing_disabled/model_allowed, KST 확인 시각·24시간·cost policy·키 결합만 새 진단의 계정 증거로 검증했다. **과거 프로젝트 grant나 최초 실행 승인을 송신 권한으로 재사용하지 않았다.** 이번 별도 사용자 승인이 진단 권한이다.

GROQ_API_KEY 존재와 내부 binding을 확인했으며 키 값/접두어/길이/키 hash는 출력·보고서·Git에 남기지 않았다. 계정 조건 변경을 알리는 새 정보는 없었고 사용자 확인의 유효기간 내에서 실행했다. 서버에 로그인하거나 플랜을 실시간 조회했다고 주장하지 않는다. 응답 cost 필드 부재를 실제 0원 검증으로 취급하지 않았다. AI_API_KEY·.env·결제 설정은 변경하지 않았다.

## 일회성 실행기와 독립 원장

추가 코드: `synthetic_groq_compat_once.py`. 기존 회사 실행 엔진이나 실패 복구 경로는 변경하지 않았다. 이 도구는 이번 특정 승인에만 결합돼 있으며 프로젝트/store/endpoint/model/payload/timeout을 CLI 인자로 바꾸는 기능이 없다.

- 실제 Codespace의 고정 경로: `/workspaces/ai-company-os/ai-company-os-phase1/data/synthetic-groq-compat-once-20261104/operation.json`.
- operation fingerprint: `b804998ae18e33533a4c4c94fc281c4c4afda84512e8efec65c6031e0000db8d`. 승인 문서/요청 hash·provider/model/endpoint·만료·POST=1·512토큰·60초·무료 정책을 결합한다. 비밀키나 비밀 결합값은 포함하지 않는다.
- `O_CREAT|O_EXCL|O_NOFOLLOW` 선예약, 파일 flush/fsync 및 디렉터리 fsync 후에만 송신한다. 원장 파일 0600, 디렉터리 0700. 원장이 이미 있으면 동일 작업을 다시 소비할 수 없다. 검사와 예약 사이 경쟁은 O_EXCL로 차단했다.
- 원장은 reserved→transport_started→received 또는 failed/uncertain/succeeded로 KST 상태를 남긴다. 실패·timeout·예약 후 crash·수신 결과 불명확 상태에서도 한도를 환불하거나 표식을 초기화하지 않는다.
- 실제 HTTPS는 기존 `guarded_urlopen`을 재사용해 환경 proxy/HTTP redirect로 인증을 전달하지 않는다. 소켓 timeout=60과 SIGALRM wall-clock 60초를 함께 적용해 DNS/connect/read를 포함한 전체 송신 구간을 제한한다. 두 번째 요청이나 자동 fallback은 없다.
- 응답은 메모리에서만 검증하고 숫자 HTTP status·유한 오류 범주/허용 코드·숫자 quota·제한된 finish/token/schema/ready-stop 판정만 저장한다. 원문 error message/body/content·Authorization·임의 헤더·전체 query URL·키/키 hash는 저장하지 않는다.

정상 200이어도 finish!=stop, refusal/tools, strict schema 불일치, ready 외 stop, 비정상 비용·보고된 출력 토큰 초과는 성공으로 표시하지 않는다. 모델이 문장을 생성했다는 이유로 인증·호환성·업무 성공을 혼동하지 않는다.

## 오프라인 검증 후 실제 결과

새 테스트 `tests/test_synthetic_groq_compat_once.py`는 합성 키/계정 확인/승인 문서·임시 고정 원장·가짜 HTTPS를 사용하고 socket/DNS를 차단한다. 정확한 Request.data hash·모델/URL/512/60초, 사전 예약, 정상 200 strict JSON, HTTP 400/401/403/404/422/429/500/503, timeout/connection, refusal·finish·schema·secret·cost·token 오류, 만료/키/계정/승인/payload 불일치, 동시 선예약, 예약/송신 후 crash, 재실행 차단, 실제 SIGALRM 타이머 복원을 검증했다.

- 초기 `python -B -m unittest tests.test_synthetic_groq_compat_once`: 6개 통과 (0.114초). 이후 wall timeout 테스트 1개를 추가했다.
- **실제 호출 전 최종 검증 명령:**

```bash
python -B -m unittest tests.test_synthetic_groq_compat_once tests.test_groq_error_diagnostics tests.test_autonomous_groq
```

**22개 통과, 실패/오류 0, exit 0 (9.172초)**. 로그 `/tmp/groq-compat-offline-20261104.log`. 기존 가짜 Groq 협업→실제 로컬 MP4 테스트 포함이며 실제 AI 성공이 아니다. 기존 production 엔진 변경이 없어 전체 회귀는 반복하지 않았다.

그 후 외부 HTTPS 접근을 허용받은 실행 환경에서 아래 명령을 **한 번만** 수행했다.

```bash
python -B synthetic_groq_compat_once.py
```

| 항목 | 실제 관찰 |
|---|---|
| 예약/송신 시작/거절 수신/종료 | 모두 2026-11-04T12:40:06+09:00 KST (초 단위 정밀도) |
| POST 시도 / 기타 AI API 요청 | **1회 / 0회** |
| HTTP status | **403** |
| category / provider_code | **permission / other** |
| 원장 상태 / 종료 코드 | failed / exit 1 |
| quota 헤더 | 허용된 숫자 정보 없음 (`{}`) |
| finish_reason / 실제 토큰 / ready-stop | 정상 모델 응답이 없어 미확인 |
| strict schema 판정 | 미수행(null), 성공 아님 |
| 응답 비용 0 검증 | false, 실제 청구액을 응답으로 확정하지 못함 |

403 수신으로 이번 합성 요청이 권한 거절 범주에 해당한다는 사실은 확인했다. 공식 문서도 403을 permission restrictions로 설명한다. 그러나 인증키 유효성·어느 계층의 권한인지·20B 모델 접근·strict JSON 조합이 정상 수락됐는지는 **확인하지 못했다**. provider_code=other는 허용 목록에 일치하는 코드를 확보하지 못했다는 뜻이며, 임의 메시지로 빈칸을 채우지 않는다. [Groq 오류 문서](https://console.groq.com/docs/errors)

이 결과를 과거 첫 관리자 요청도 403이었다는 증거로 소급 적용하지 않는다. 과거 원인은 여전히 미확정이다. 403이므로 schema 400이 원인이라고 주장하지도 않는다. 기존 MP4 프로젝트 복구·관리자 계획 생성·직원 협업·영상 제작은 이번에 실행하지 않았다.

최종 읽기 전용 확인 `2026-11-04T12:40:54+09:00` KST: 원장 fingerprint·고정 operation·실패 상태·시도 1회·파일권한 일치. 실제 명령을 재실행해 차단을 시험하지는 않았다. 재실행/동시성/crash 차단은 사전 오프라인 테스트로 검증했고, 실제 선예약 원장은 그대로 보존한다.

## 기존 데이터 보존과 다음 최소 단계

개발 전후 기존 데이터/backup/프로젝트·grant·서명 키·설정·사용자 미추적 파일·기존 계정 제안 **79개 SHA256 모두 동일**. 원본 사용자 데이터 변경·삭제 0건. 추가된 로컬 자료는 위 독립 진단 원장 1개이며 Git에서 제외한다.

- 기존 Groq `groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e` 상태 hash `4fe0593cb0a1834a972fa42d31c54744ff5b64f619fbdfa57a4a9b514e01c0ca`, active_operation `5202abf79d95474091a7cb84fc84ecc3`, 기존 시도 1건 그대로다.
- OpenRouter `freecompany-ae4aa334511d470c8c517685e9902a53` 상태 hash `f28ebea41f84d1f08917acab1f6ae1e1c548a164e482710273828b7e5936e7b1` 유지. 수동 프로젝트·backup·기존 mock MP4·다른 사용자 파일도 보존했다.
- `git diff --check` 통과. 코드·테스트·이 보고서만 선택적으로 커밋/푸시한다. 원장 원본·API 키·계정 binding·contract·원문 응답·MP4는 Git 제외. 보고서 저장 후 다시 읽어 내용을 확인한다.

**다음 최소 단계는 추가 run이 아니라, 동일 키가 속한 Groq 조직/프로젝트의 모델 권한과 해당 KST 요청 로그를 Console에서 읽기 전용으로 확인하는 것이다.** 공식 문서상 모델 제한은 조직과 프로젝트 양쪽에 적용되고 제한 모델 요청은 403이 된다. 기존의 모델 한도 표시는 실제 키가 속한 프로젝트의 허용 여부까지 입증하지 않는다. 이는 이번 원인의 확정 진단이 아니라 우선 확인할 구체적 항목이다. 비밀키 값 대신 해당 403의 안전한 분류와 `openai/gpt-oss-20b` 허용 여부만 확인하면 된다. [Groq 모델 권한](https://console.groq.com/docs/model-permissions)

권한 원인을 확인한 뒤에도 이번 한도는 이미 소비됐다. 추가 호환성 요청이나 자율 MP4 실행은 정확한 새 범위와 별도 명시 동의가 필요하며, 기존 실패 원장·이번 예약을 지우거나 새 디렉터리/계정으로 반복하지 않는다. 현재는 API 수락 검증 자체가 실패해 전체 영상 사이클을 바로 재개할 근거가 없다.

이번 작업은 목표→AI 자율 협업→최종 산출물 앞의 연결 차단을 실제 HTTP 403까지 좁혔다. 실제 협업·MP4 완주는 아직 미완료이며 업무별 사용자 중간 결재는 추가하지 않았다. 기존 수동 승인 부채와 실패 복구는 남아 있다. 대시보드·영상 디자인 고도화는 하지 않았다.
