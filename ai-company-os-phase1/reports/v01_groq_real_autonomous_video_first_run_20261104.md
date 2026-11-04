# Groq 첫 실제 무료 AI 자율 운영 — 첫 관리자 요청 거절로 정지

2026-11-04 KST. **사용자가 명시 승인한 프로젝트의 정상 CLI approve 1회와 run 1회를 수행했다. 실제 Groq 요청 시도 1회 후 `stopped/plan`, `provider_rejected`로 안전 정지했다. 관리자 계획·직원 협업·최종 MP4는 생성되지 않았으며 실제 자율 한 사이클 성공이 아니다.** 재시도·continue·다른 공급자 전환·새 프로젝트 실행은 하지 않았다.

## 승인과 사전 검증

`git pull --ff-only` 성공, main `db09eca` 반영. 핵심 원칙·AGENTS.md·한국어 규칙·기존 Groq 통합/준비 점검/동의안 보고서 및 CLI·Groq wire/schema·로컬 렌더러·서명/원장 보호를 확인했다. 기존 사용자 미추적 파일과 작업 범위 충돌은 없었다.

사용자 원문 승인은 `codex_tasks/v01_groq_real_first_autonomous_video_approved_20261104.md`에 기록되어 있고 이번 대화에서도 해당 최초 운영 승인 및 approve/run 각 1회 실행을 명시했다. 다음 정확한 프로젝트/계약만 실행했다.

- Store: `/workspaces/ai-company-os/ai-company-os-phase1/data/groq-video-smoke-20261104`.
- ID: `groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e`.
- 목표: ChatGPT 초보자용 좋은 질문 작성법을 설명하는 한국어 20~30초 자막 MP4, 가능하면 로컬 한국어 음성 및 제작 보고서.
- 목표 hash: `3cf69cc191d65718ef1571671a3f85940676d3c8da7992f7d1760eec45bbb5c9`.
- 승인 전 state hash: `25d3e5d7c3666acac578d278aab63f00848716f904a4cb1dbe7f22dcc495db5f`.
- Proposal: `/tmp/groq-account-reviewed-proposal-20261104.json`.
- 승인된 canonical review hash: `e77a83d47b73176faad55fdfee563c357407fef3bcbd8046c11a73d8da9c305a`.
- 발행/계정 확인: `2026-11-04T11:35:43+09:00`, 만료: `2026-11-05T11:35:43+09:00` KST.

사전 점검 시각 `2026-11-04T11:44:51+09:00` KST. 제안 존재·canonical hash·프로젝트/목표/초기 상태·provider/model/endpoint·동의 scope·도구·비용/업무/시간 한도·계정 확인 24시간 유효성·키 결합 및 `GroqStore._check_contract` 전체 검증을 통과했다. 실행 직전에도 다시 검증했다. ready/plan, attempted=0, enabled=false, consent/session/event 비어 있음, grant/실사용 서명 키/plan/active_operation 없음 조건이 일치했다. ffmpeg/ffprobe/eSpeak NG와 Noto CJK 폰트 존재도 확인했다.

키는 존재 여부 및 내부 계약 결합만 검사했다. 비밀값·키 접두어/길이/키 hash·서명 원문을 출력하거나 Git에 포함하지 않았다. AI_API_KEY·.env·전역 설정은 변경하지 않았다. 기존 제안을 재발행하거나 이전 승인 범위를 확장하지 않았다.

허용된 공급자/모델은 `groq` / `openai/gpt-oss-20b`, 고정 POST URL은 `https://api.groq.com/openai/v1/chat/completions`다. 전송은 이 프로젝트의 목표와 생성 업무 텍스트/로컬 렌더 메타데이터 범위로 한정했다. 실제 첫 요청에는 목표·운영 한도·역할 계약·허용 로컬 capability 안내가 들어가며, 기존 파일/코드/백업/영상·음성 원본/계정 개인정보를 읽어 요청에 넣지 않았다. 키는 고정 HTTPS 인증에만 사용했다. 아직 생성 결과가 없어 대본/직원 결과/렌더 메타데이터 후속 송신은 없었다.

## 정확히 한 번의 승인과 실행

로컬 실행 도구 `/tmp/run_groq_first_authorized_once_20261104.py`는 사전 검증·보존 기준 확보 후 배타적 `O_EXCL` 실행 표식을 생성하고 정상 CLI를 호출했다. 제품의 요청/서명/비용/원장/잠금 보호는 변경하거나 monkeypatch하지 않았다. 외부 HTTPS 접근을 허용받은 실행 환경에서 수행했으며 실제 송신 후 도구 호출을 반복하지 않았다.

approve 명령 1회:

```bash
python -B -m autonomous_live_cli --store data/groq-video-smoke-20261104 approve groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e --proposal /tmp/groq-account-reviewed-proposal-20261104.json --review-hash e77a83d47b73176faad55fdfee563c357407fef3bcbd8046c11a73d8da9c305a --owner-confirmed
```

승인 성공 출력의 `storage_hash`를 구조적으로 파싱하고, 저장된 최신 상태와 signed grant를 재검증했다. 승인 후 state hash는 `8f6a38257f245d0dde9811852fd06586d27ef145f188a5ccb58fb355b011aac6`였다. 그 값을 사용한 run 명령 1회:

```bash
GROQ_MODEL=openai/gpt-oss-20b GROQ_BASE_URL=https://api.groq.com/openai/v1 GROQ_AUTONOMOUS_FREE_ENABLED=1 python -B -m autonomous_live_cli --store data/groq-video-smoke-20261104 run groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e --state-hash 8f6a38257f245d0dde9811852fd06586d27ef145f188a5ccb58fb355b011aac6
```

고정 모델/URL/실행 flag는 해당 자식 프로세스에만 설정했다. run은 AI 회사 사이클 1회이며 그 안의 여러 정상 요청은 승인됐지만, 이번에는 첫 요청에서 정지했다.

| KST 시각 | 사실 |
|---|---|
| 2026-11-04 11:47:01 | 최초 approve 성공, signed 운영 grant 및 전용 키 생성, run 호출 |
| 2026-11-04 11:47:02 | 단일 session 시작, 관리자 plan 원장 선예약·transport_started 기록 |
| 2026-11-04 11:47:02 | 단일 시도 failed/provider_rejected, system_safety_stop 기록 및 run 종료 |

approve exit=0, run exit=0, 실행 도구 exit=0이다. **run exit=0은 정지 상태의 저장/요약 반환 성공이며 업무 성공이 아니다.**

## 실제 결과와 진단 한계

- 실제 요청 모델: `openai/gpt-oss-20b`, provider_id=`groq`, 역할 `autonomous_manager`, phase=`plan`.
- 실제 Groq 요청 시도 **1회**, transport 시작 기록 **1회**, completed **0건**, failed **1건**, reserved로 남은 시도 **0건**. OpenRouter/Gemini 요청 0회.
- 첫 오류: **`provider_rejected`**. 현재 `_request_json`은 HTTP 거절을 제한된 error_code로 매핑하고 원문을 보존하지 않는다. `_provider_code`의 포괄 분류 때문에 **정확한 HTTP 상태 번호·공급자 오류 코드/본문·거절 이유는 이번 원장에서 확정할 수 없다.** 키 오류·요청 schema 오류·접근 차단 등 특정 원인으로 단정하지 않는다.
- 정상 모델 응답 envelope 수신/파싱 기록 없음. `finish_reason`·JSON 검증 결과·토큰 사용량·응답 지연 상세·rate limit 잔여치 **미확인**. rate_limits는 빈 object이며 정상 응답의 response_diagnostics/response_received_at도 없다. 토큰을 0으로 추정하지 않는다.
- 요청 입력 4,472 bytes, 출력 요청 한도 4,096 tokens. 실제 토큰 소비나 생성량을 뜻하지 않는다. 타임스탬프는 초 단위여서 subsecond 지연은 산출할 수 없다.
- 업무 결과 적용 상태 `unvalidated`, 보존된 blocked active_operation: `5202abf79d95474091a7cb84fc84ecc3`. failed 시도는 자동 재전송 가능한 clean checkpoint가 아니다. 공급자 내부 처리/사용량을 이 원장만으로 확정할 수 없다.
- 현재 `stopped/plan`, 계획 채택 0, 직원/배정 0, 직원 실행 0, 선행 결과 전달 0, 관리자 검토/수정 0, 로컬 렌더 0, 최종 통합 0. 사용자 중간 업무 승인 요청 0, run session 1개.
- 최종 상태 hash: `4fe0593cb0a1834a972fa42d31c54744ff5b64f619fbdfa57a4a9b514e01c0ca`.

무료 근거는 사용자 확인한 Current Plan=Free $0, 선택 모델 허용 및 서명된 계정 선언이다. cost_policy의 `max_cost=0`, billing_enabled=false, paid_fallback=false와 계정/키/만료 검증을 유지했다. 이번 요청은 실패해 **응답 cost/토큰 증거가 없으며 실제 청구액 0을 응답으로 검증했다고 주장하지 않는다.** 유료 업그레이드·유료 모델·결제 변경·fallback은 수행하지 않았다. 조직 기본 상한 30 RPM/1000 RPD/8000 TPM/200000 TPD는 보장 잔여량이 아니며 이번에 공급자 한도 진단을 추가 조회하지 않았다.

## MP4와 보존된 로컬 근거

**실제 Groq AI 프로젝트 MP4: 없음.** store 아래 MP4 0개, final.md 0개, artifacts 비어 있음, final=null. 따라서 실제 영상의 절대 경로/다운로드 복사본/SHA/ffprobe·디코딩·한국어 자막/오디오 검사 대상이 없다. preview를 만들거나 기존 mock MP4를 실사용 결과로 대체하지 않았다. 기술적 MP4 성공도 미달이며 미적 품질·자연스러운 목소리는 평가하지 않았다.

다음 근거는 같은 신규 store에 보존했다(Git 제외).

- `groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e.json`: 실패 원장·상태·단일 session·이벤트·active_operation.
- `groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e.consent.json` 및 전용 `.operating-consent.key`: 최초 운영 승인/서명 근거. 내용 공개 금지.
- `authorized-launch-20261104.json`: 동일 작업 재실행 방지 표식.
- `authorized-run-summary-20261104.json`: approve/run 각 1회 및 종료 상태의 비밀정보 없는 요약.
- 기존 `operating-proposal.json`, /tmp 승인 대상 제안은 원본 그대로 유지.

기존 데이터/백업/프로젝트·설정/사용자 미추적 파일 **73개**를 실행 전후 SHA256으로 비교했다. 승인된 Groq 프로젝트 상태 파일 1개만 의도대로 변경했고 나머지 **72개는 동일**하다(기존 data 계열 67개 중 대상 상태 1개 외 66개 동일). 신규 grant/전용 서명 키/잠금/실행 표식/요약은 승인 대상 store에서만 추가됐다. 기존 사용자 파일은 삭제·초기화하지 않았다.

OpenRouter `freecompany-ae4aa334511d470c8c517685e9902a53`의 stopped/plan·시도 1·active_operation 및 상태 hash `f28ebea41f84d1f08917acab1f6ae1e1c548a164e482710273828b7e5936e7b1` 유지. `cb44b605b498` 9/20·reserved 0, `c85d9853906a` 1/7·reserved 1, 기존 mock MP4·백업·승인·서명 키 모두 보존했다.

## 오프라인 검증과 후속 과제

실행 후 최소 안전 회귀 명령:

```bash
python -B -m unittest tests.test_autonomous_groq.GroqTests.test_429_402_401_and_retry_headers_are_safe_no_auto_retry tests.test_autonomous_groq.GroqTests.test_crash_receive_uncertain_and_continue_no_replay
```

**2개 통과, 실패/오류 0, exit 0 (0.138초).** 네트워크 차단·합성 키/동의·가짜 transport·임시 store 검사이며 실제 프로젝트를 재실행하지 않았다. 제품 코드 변경이 없어 전체 회귀는 반복하지 않았다. `git diff --check` 통과. 보고서 저장 후 다시 읽어 검증하며 이 보고서만 선택적으로 커밋/푸시한다. 실제 데이터·proposal·키·서명·로그·MP4는 Git에 포함하지 않는다.

목표→실제 AI 관리자 호출·서명 동의·선예약·실패 안전 정지까지의 근거를 확보했으나 실제 관리자→직원 협업→최종 산출물에는 도달하지 못했다. 새 중간 업무 승인 부채는 추가하지 않았다. 기존 수동 경로의 반복 승인 부채와 실패 복구는 남아 있다. UI/대시보드 작업은 하지 않았다.

이번 승인 범위는 최초 approve/run 각 1회로 소진됐다. 추가 실제 호출·ping·run·continue·재승인·새 프로젝트 우회는 하지 않는다. 먼저 제한된 HTTP 상태/허용된 오류 분류를 비밀정보 없이 남기는 진단을 오프라인에서 보완하고, 원본 실패 시도·active_operation·승인을 보존하는 복구 정책을 검증해야 한다. 실제 추가 송신은 그 후 별도 명시 운영 권한이 필요하다. 이번 실패의 원장이나 서명 계약을 수정해 원인을 추정하거나 재전송하지 않는다.
