# 무료 공급자 응답 진단 및 읽기 전용 복구 검토 — 오프라인 개발

2026-11-04 KST. `git pull --ff-only`로 main `aa2a88e` 반영 후 핵심 원칙·AGENTS.md·한국어 규칙·이전 실제 실행/영상 준비 보고서와 공급자/역할/무료 원장 코드를 확인했다. **이번 실제 AI/API 호출 0회, 공급자 외부 네트워크 진단 0회, 유료 사용 0회, 기존 실패 프로젝트 승인·재실행 0회.** Git 동기화 통신과 테스트 전용 loopback 통신만 별개로 수행했다.

## 확인된 사실과 미확정 원인

과거 실제 프로젝트 `freecompany-ae4aa334511d470c8c517685e9902a53`는 관리자 plan 요청 1회, 응답 수신 완료 및 비용 0 확인 후 `finish_reason == stop` 조건 불통과로 정지했다. 당시 응답 본문/종료 이유가 저장되지 않았으므로 **정확한 finish_reason·토큰 사용량·원인은 지금 복구할 수 없다.** 이번 변경이 과거 값을 복원했다고 주장하지 않는다.

가능한 원인은 length에 의한 출력 중단, 도구/함수 요청 종료, 필터·오류 종료, 공급자의 알 수 없는 종료 값 등이다. 정상 종료/JSON 지원을 모든 무료 라우팅 모델에서 보장할 근거가 없으며, 길이 제한에 걸렸다는 단정도 하지 않는다. 요청 출력 상한은 기존 4096토큰, 입력/응답 바이트 제한과 필드별 텍스트 제한은 별도다. 최대 8개 업무/기준을 장황하게 작성하면 한도 내에 못 들어갈 수 있지만 실제 첫 응답이 그러했는지는 미확정이다.

## 변경 파일과 계약

- `ai_provider_adapter.py`: 별도 `bounded_response_diagnostics` 추가. 고정 allowlist 종료 이유 `stop/length/tool_calls/function_call/content_filter/error`, 미지 값 `unknown`, 필드 부재 `missing`을 구분한다. 제한된 정수 토큰 수, choice 수(2는 2개 이상), 본문 유무/길이, 거절/도구 요청 존재 여부, 비용 분류만 반환한다. 임의 provider ID/문자열·헤더·본문은 저장하지 않는다. request ID는 개인정보 없는 값임을 증명할 수 없어 이번 최소 진단에서 제외했다. bool/문자열/과대 토큰 수는 null로 처리한다.
- `autonomous_free.py`: 향후 요청에 한해 응답 수신 시각/제한된 바이트 수를 먼저 저장하고, envelope 파싱 후 위 메타데이터를 비용 검사 전에 저장한다. JSON envelope 파싱과 모델 content JSON 파싱을 구분한다. 숫자 비용 0만 기존처럼 통과하며 미확인/양수 비용은 정지한다. 정상 수신→비용 확인→역할 검증→업무 적용이 각각 다르다는 원장 구조를 유지한다.
- `autonomous_live.py`: free-v2가 역할 검증 결과를 기록할 수 있는 기본 no-op 훅 추가. JSON 파싱 성공/실패, 비정상 종료, 구조 오류, 비승인 도구, 거절을 안전한 코드로 기록한다. 본문이 있어도 refusal이면 수락하지 않는다. 실제 도구 직접 접근 불가와 앱의 제한된 로컬 도구 capability를 구분하도록 프롬프트 설명을 보완했다. legacy 호출 한도/동의는 그대로다.
- `autonomous_free.py`의 요청 프롬프트에 4096토큰 내 간결한 JSON, 필수 필드/검사 유지, 불필요한 업무·별도 추론/Markdown 생략을 안내한다. `max_tokens`나 모델·가격 필터·fallback 정책은 바꾸지 않았다. 기존 요청은 `response_format`을 보내지 않는다. 무료 라우팅 대상의 해당 옵션 지원을 이번 외부 조회 금지 범위에서 확인할 수 없으므로 지원을 가정해 강제하거나 실패 시 옵션을 바꿔 자동 재송신하지 않는다. 프롬프트 안내는 강제 JSON 보장이 아니며 검증 실패는 계속 정지한다.
- `autonomous_recovery.py`: free-v2만 받는 **읽기 전용** `recovery_proposal`. store/프로젝트/목표/상태/마지막 시도/원래 운영 계약 hash에 결합한 검토안을 반환한다. 전체 원장을 검토하며 이전 미확정 시도가 있으면 후보에서 제외한다. 서명된 기존 계약의 유효성도 재확인한다. 마지막에 상태 hash를 재조회해 읽는 도중 변경을 감지한다. 파일·서명 키·승인·원장·상태를 쓰지 않는다.
- `autonomous_live_cli.py`: `recovery-proposal PROJECT_ID` 추가. 해당 명령은 실제 키나 실행 flag가 없어도 읽기만 수행하며, grant나 송신 권한을 만들지 않는다.
- `tests/test_provider_response_recovery.py`: 가짜 HTTPS/합성 키/합성 운영 동의/임시 저장소/외부 socket·DNS 차단으로 진단·거절·복구 검토·미승인 실행 차단·crash 보호를 검증한다.

모든 새 진단은 원장 `real_ai.attempts[].response_diagnostics`에 저장한다. 성공 직원 결과 등 정상 업무 저장과 별개로 디버그 진단에 응답 본문·프롬프트·키·직원 콘텐츠·provider 임의 문자열을 복사하지 않는다. 실패 시 raw payload를 남기지 않는 원칙은 유지한다.

## 상태별 복구 정책

| 상태 | 판단과 기본 동작 |
|---|---|
| reserved, 송신 표시 없음 | 송신 전 crash인지 저장 순서 사이 crash인지 증명 부족, 차단 |
| sent, 수신 기록 없음 | 공급자 처리 결과 미확정, 재송신 차단 |
| 수신 후 비용 commit 전 crash | `received_before_cost_commit`, 비용 0 미확정, 차단 |
| failed/HTTP 오류/timeout | 실패·불확실 결과를 보존, 자동 재시도 없음 |
| completed, 업무 미검증, 과거 진단 없음 | `completed_unvalidated_legacy`, 추가 시도 제안 0, 감사 필요 |
| completed, 비용 0, length 확인, plan 미적용 | 원본 시도와 원장을 보존한 **추가 요청 최대 1회 검토 후보**만 제안, 실행 권한 없음 |
| validated clean checkpoint | 기존 continue 정책만 적용 가능; 실패 응답 재전송 권한이 아님 |

후보 조건은 stopped/plan, 미채택 계획, 업무/산출물 없음, 마지막 active_operation 일치, 비용 0·length·incomplete_response 증거와 이전 모든 시도 업무 적용 확정이다. 이 조건을 충족해도 `execution_authorized=false`, `execution_implemented=false`, `automatic_retry=false`다. **복구 송신 실행기와 복구 승인 명령은 이번에 구현하지 않았다.** 검토안을 기존 approve/run/continue에 전달해 원장 보호를 우회할 수 없다. 사람에게 업무 품질을 승인받는 기능이 아니라 별도 운영 예외 검토 자료다.

읽기 전용 사용법:

```bash
python -B -m autonomous_live_cli --store data/free-video-smoke-20261104 recovery-proposal freecompany-ae4aa334511d470c8c517685e9902a53
```

현재 실사용 프로젝트에 이 조회만 실행한 결과 `completed_unvalidated_legacy / blocked_pending_audit`, `proposed_max_additional_attempts=0`이었다. 원본 상태 hash `f28ebea41f84d1f08917acab1f6ae1e1c548a164e482710273828b7e5936e7b1`, 원래 계약 hash `c36981e3e8e6d565e3a7566185869a5bf49fcddafdb36a73764d23ad6c0316c2`는 유지됐다. 조회 결과를 실사용 store에 쓰지 않았다.

**현재 첫 실패 원장을 안전하게 자동 복구하는 것은 불가능하다.** 과거 진단 누락과 completed-but-unvalidated 상태를 임의로 validated로 승격하거나 원장/active_operation을 지우지 않았다. 새 프로젝트 생성도 workaround로 쓰지 않는다.

## 다음 실제 시험 전 필요한 절차

1. 원본 미확정 업무 적용 상태를 감사하고, 원본 operation을 보존한 채 별도의 새 요청임을 명시하는 복구 실행기/서명 계약/영속 소비 예약을 먼저 오프라인 구현·검증한다. 복구 중 crash도 소비 상태를 초기화하거나 다시 전송하지 못해야 한다. 현재 검토안은 그 실행기를 대신하지 않는다.
2. 같은 프로젝트 ID·목표 hash·실패 시도 ID/hash·최신 상태 hash·기존 계약 hash에 결합한 **새 plan 요청 최대 1회**, `openrouter/free`/고정 HTTPS/비용 0/유료 fallback 없음/기존 데이터 범위 유지/중복 위험 인지/만료 시각을 별도로 명시 승인해야 한다. 이번 과거 응답의 정확한 원인은 미확정이라는 사실도 승인 자료에 포함한다.
3. 최초 run의 30분 기한은 원본대로 보존한다. 기한이 지나면 복구 요청의 별도 유효 기간과 벽시계 한도를 승인 계약에 명시해야 하며 기존 시간을 몰래 초기화하지 않는다. 이후 직원 협업까지 허용할지 역시 해당 복구 운영 범위에 명시해야 한다. 이번의 추가 plan 1회 검토만으로 전체 후속 실행 권한을 가정하지 않는다.
4. 새 요청도 비용 미확인·402/429·timeout·비정상 종료·잘린 JSON이면 즉시 정지하며 두 번째 복구 요청은 하지 않는다. 다음 실제 호출은 위 개발/검토/명시 승인 뒤 별도 작업이며 이번에 실행하지 않았다.

## 오프라인 검증과 보존

- stop 정상, length/tool/function/filter/error/unknown/missing 종료, choice/content 누락, refusal, JSON 불완전, 긴 응답, 토큰 메타데이터 오염, 비용 0/누락/양수, provider 오류 envelope, 수신 후 crash, 재진입과 미승인 복구 차단을 새 테스트로 검증했다.
- 기존 무료 테스트의 429/402/5xx/timeout/비용 미확인/원장 중복·crash·22회 자율 DAG 및 legacy 제한 테스트, 실제 로컬 mock MP4 파이프라인을 함께 실행했다. mock 영상이나 fake 응답을 실제 AI 성공으로 표현하지 않는다.
- `python -B -m unittest tests.test_provider_response_recovery tests.test_autonomous_free tests.test_autonomous_live tests.test_local_artifacts`: **60개 통과** (14.062초).
- 상태 분류를 세분화하는 후속 테스트 편집 중 들여쓰기 오류로 수집이 한 번 실패했다. 즉시 수정하고 `python -B -m unittest tests.test_provider_response_recovery`: **9개 통과** (0.943초).
- 최종 전체 회귀: **602개 실행, 601개 통과·1개 건너뜀, 실패/오류 0, exit 0** (75.656초). 명령: `python -B -m unittest discover -s tests`, 로그 `/tmp/provider-recovery-full.log`. 기존 loopback 테스트에 필요한 권한 확장으로 실행했으며 실제 provider 통신 테스트가 아니다.
- 기존 데이터/백업/프로젝트 파일 **47개**를 실행 전 SHA256과 비교해 변경 0건을 확인했다. 실제 실패 store의 상태·원장·승인·서명 키·요약, 기존 `cb44...` 9/20, `c85...` reserved 1, 기존 mock MP4 모두 보존 대상에 포함된다. `.env`·사용자 미추적 파일은 변경하지 않았다.
- `git diff --check` 통과. 새 코드/테스트/이 보고서만 선택적으로 커밋하며 실사용 데이터·진단 출력·계약·키는 제외한다.

이번 변경은 목표→자율 협업→최종 MP4 흐름의 실제 공급자 실패를 진단하고 안전하게 구분할 근거를 추가했다. 정상 경로의 업무별 승인/2회·20회 비용성 상한을 추가하지 않았다. 아직 실제 AI 한 사이클은 미완료이며, 실패 복구 송신 실행과 그 운영 예외 승인이 남았다. 기존 수동 프로젝트 승인 부채는 유지했고 UI/대시보드는 개발하지 않았다.
