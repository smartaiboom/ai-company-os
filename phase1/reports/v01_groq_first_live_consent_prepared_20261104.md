# Groq 최초 운영 동의안 준비 결과

작성: 2026-11-04T11:35:43+09:00 KST. `git pull --ff-only` 성공, main `1ae3df6` 반영. 핵심 원칙·AGENTS.md·한국어 규칙·Groq 통합/준비 점검 보고서 및 CLI·계약·adapter·원장 보호 코드를 확인했다.

**최신 최초 운영 동의안 prepare 성공, 로컬 계약 검증 통과. 실제 AI API 호출 0회, 실제 approve/run/continue 0회, 실사용 운영 서명 키 생성 0건, 유료 사용 0건. 프로젝트는 미승인 상태다.** 제품 코드 변경 없이 보고서만 Git에 반영한다.

## 계정 확인 근거와 한계

이번 작업 지시서 `codex_tasks/v01_groq_prepare_first_live_consent_20261104.md`가 명시한 사용자 직접 확인을 근거로 삼았다. Console의 Free $0 / Current Plan, Developer/Enterprise 미활성, 선택 모델의 조직 무료 한도 표시가 제공됐다. Codex가 로그인하거나 실제 공급자 API로 조회한 사실은 없다. 별도 결제수단 부재까지 확인했다고 주장하지 않는다.

현행 계약의 `free_plan=true`, `billing_disabled=true`, `model_allowed=true`는 현재 Free 플랜·유료 과금 플랜 미활성·해당 모델 허용에 관한 선언이며 별도의 카드 미보유 조건은 없다. 따라서 제공된 사용자 확인에 근거해 정상 `--confirm-groq-free-account`를 사용했고, 정책을 완화하거나 미확인 결제수단 정보를 채우지 않았다. 무료 조건과 키 결합 확인은 24시간 이내여야 한다. 유료 업그레이드·과금 활성화·유료 모델·유료 fallback은 허용하지 않는다.

GROQ_API_KEY는 현재 환경에 존재한다. 키 값/길이/접두어/키 hash는 공개 출력·보고서·Git에 남기지 않았다. 정상 계약 내부의 credential binding은 유지하고 CLI 전체 출력은 메모리에서 처리해 공개 출력에서 제외했다. AI_API_KEY·.env·전역 설정은 변경하지 않았다.

## 실제 제안 식별 정보

- Store: `data/groq-video-smoke-20261104`.
- 프로젝트: `groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e`.
- 목표: ChatGPT 초보자용 좋은 질문 작성법을 설명하는 한국어 20~30초 MP4, 자막과 가능하면 로컬 한국어 음성, 최종 재생 파일과 제작 보고서. 검증되지 않은 기능을 사실로 단정하지 않는다.
- 목표 hash: `3cf69cc191d65718ef1571671a3f85940676d3c8da7992f7d1760eec45bbb5c9`.
- 현재/초기 상태 hash: `25d3e5d7c3666acac578d278aab63f00848716f904a4cb1dbe7f22dcc495db5f`.
- **새 제안 canonical review hash:** `e77a83d47b73176faad55fdfee563c357407fef3bcbd8046c11a73d8da9c305a`.
- 새 제안: `/tmp/groq-account-reviewed-proposal-20261104.json` (권한 0600, Git 제외).
- 발행/계정 확인 선언: `2026-11-04T11:35:43+09:00` KST.
- **만료:** `2026-11-05T11:35:43+09:00` KST. 키 변경·계정 조건 변경·만료 시 그대로 승인/실행할 수 없다.
- 기존 `data/groq-video-smoke-20261104/operating-proposal.json` 원본 유지. 별도 보존본 `/tmp/groq-original-proposal-preserved-20261104.json` (0600)과 바이트 동일 확인.

정상 CLI main을 아래 인자로 한 번 호출했다. 외부 socket/DNS는 차단하고 stdout은 메모리에서 받아 비밀 결합 필드를 제외한 요약만 출력했다. 동의 검사·서명·원장 보호는 변경하거나 우회하지 않았다.

```bash
python -B -m autonomous_live_cli --store data/groq-video-smoke-20261104 prepare groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e --confirm-groq-free-account --proposal-out /tmp/groq-account-reviewed-proposal-20261104.json
```

기존 초안 canonical hash·목표/상태·현행 계약 구조와 유효기간을 먼저 확인했다. 새 제안을 다시 읽어 CLI review hash와 canonical digest 일치, `GroqStore._check_contract` 전체 검증 통과를 확인했다. 준비 후에도 ready/plan, attempted=0, enabled=false, consent/session/event 비어 있음, plan/active_operation/grant/실사용 서명 키 없음 상태를 확인했다.

## 동의 대상과 운영 제약

공급자 `groq`, 모델 `openai/gpt-oss-20b`, 계약 base URL `https://api.groq.com/openai/v1`, 실제 고정 POST URL `https://api.groq.com/openai/v1/chat/completions`다. 별도 Groq namespace·GROQ_API_KEY만 사용하며 OpenRouter 승인/실패 원장을 재사용하지 않는다.

외부 전송 예정 범위는 **오직 이 신규 프로젝트의 목표, 생성되는 관리자 계획/성공 기준/직원 배정/대본/자막/장면/직원 결과/선행 전달/관리자 검토·수정·최종 통합 텍스트 및 로컬 렌더 메타데이터**다. 계약 scopes는 goal/generated_plan/generated_criteria/assignments/employee_results/manager_reviews/final_integration이다. 기존 문서·코드 본문·음성/영상 원본·키·계정 개인정보는 모델 메시지로 보내지 않는다. API 키는 고정 공급자 endpoint 인증에만 사용한다.

로컬 허용 도구는 `caption_video_v1`: allowlist FFmpeg/ffprobe, 선택적 eSpeak NG 한국어 음성, 한국어 자막 MP4 생성·기술 검사. 네트워크/업로드 없음, 짝수 해상도 240~1920, 장면 1~16개·장면당 120자 이하·전체 120초 이하의 기술 한도를 유지한다. 실제 업무 목표는 20~30초다. 로컬 도구 허용과 모델 전송 동의는 구분한다.

비용 정책은 Free 계정 확인 기반 `max_cost=0`, billing_enabled=false, paid_fallback=false다. Groq 응답 cost 누락 자체를 비용 0 증명으로 사용하지 않으며 계정 확인 계약을 근거로 한다. 명시된 cost가 양수/비정상이거나 계정 근거가 무효이면 정지한다. 원격 계정 변경을 실시간 조회해 과금을 불가능하게 보장하는 기능은 없으므로 사용자 확인의 유효성과 유료 플랜 미활성 조건을 유지해야 한다.

사용자 화면의 조직 상한은 30 RPM / 1,000 RPD / 8,000 TPM / 200,000 TPD이며 보장된 프로젝트 예산이나 잔여치가 아니다. 공급자의 현재 응답/프로젝트별 더 엄격한 한도를 우선한다. 기존 2초 최소 간격은 TPM/RPD 전체를 사전 계산해 보장하는 장치가 아니다. 429/402/401/5xx·quota 0·계약 불일치·실패·미확정 송신에 안전 정지하며 자동 재시도/공급자 전환은 없다.

총/시작당 인위적 호출 상한 없음(`max_calls=null`). 최초 실행 최대 1,800초, 업무/기준 최대 8개, 업무당 수정 1회·총 수정 2회, 품질 정체/중복 operation/미확정 예약 차단을 유지한다. 업무 내용에 대한 사용자 중간 결재는 요구하지 않는다.

## 향후 명시 승인 후의 절차 — 이번에는 실행하지 않음

위 새 제안의 프로젝트·review hash·범위·만료에 대한 사용자 최초 운영 동의와 실제 실행 권한을 명시적으로 받은 뒤에만 진행한다. 실행 직전 동일 키·무료 계정 상태·미실행 상태·제안 hash·유효기간·로컬 도구를 다시 점검한다. 불일치/만료면 실행하지 않는다.

1. 아래 approve를 **한 번만** 실행한다. 이 명령은 로컬 운영 승인을 기록하며, 출력의 `storage_hash`는 승인 후 변경된 상태 hash다.

```bash
python -B -m autonomous_live_cli --store data/groq-video-smoke-20261104 approve groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e --proposal /tmp/groq-account-reviewed-proposal-20261104.json --review-hash e77a83d47b73176faad55fdfee563c357407fef3bcbd8046c11a73d8da9c305a --owner-confirmed
```

2. 승인 성공 출력의 `storage_hash`를 `APPROVED_STATE_HASH`에 넣고 아래 run을 **한 번만** 실행한다. 승인 전 상태 hash를 넣으면 안 된다. 이 미래 hash는 이번 준비 작업에서 생성하지 않았다. 모델/URL/실행 flag는 이 실행 프로세스에만 지정한다.

```bash
GROQ_MODEL=openai/gpt-oss-20b GROQ_BASE_URL=https://api.groq.com/openai/v1 GROQ_AUTONOMOUS_FREE_ENABLED=1 python -B -m autonomous_live_cli --store data/groq-video-smoke-20261104 run groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e --state-hash "$APPROVED_STATE_HASH"
```

승인 실패면 run을 실행하지 않는다. 실행이 정지하면 원장과 오류를 보존하고 임의 run/continue/재승인/다른 공급자 전송을 하지 않는다. 이번 계정 확인과 prepare는 위 실제 송신 권한을 대신하지 않는다.

## 검증·보존 및 남은 사항

실행한 오프라인 테스트:

```bash
python -B -m unittest tests.test_autonomous_groq.GroqTests.test_unverified_account_prepare_no_side_effects_and_no_send tests.test_autonomous_groq.GroqTests.test_contract_provider_model_scope_schema_cost_and_key_guards tests.test_autonomous_groq.GroqTests.test_cli_draft_dispatch_and_provider_switch_block
```

**3개 통과, 실패/오류 0, exit 0 (0.046초).** 외부 네트워크 차단·합성 키/동의·임시 store fixture다. 실제 Groq 성공으로 표현하지 않는다. 코드 변경이 없어 전체 회귀와 MP4 생성은 반복하지 않았다. `git diff --check`도 통과했다.

기존 데이터/백업/프로젝트 **67개** 파일의 전후 SHA256과 목록 동일, 변경/추가/삭제 0건. 새 제안과 초안 보존본은 /tmp에만 생성했다. 기존 사용자 미추적 파일은 수정하거나 스테이징하지 않았다.

- OpenRouter 실패 `freecompany-ae4aa334511d470c8c517685e9902a53`: stopped/plan, attempted 1·active_operation 보존, 상태 hash `f28ebea41f84d1f08917acab1f6ae1e1c548a164e482710273828b7e5936e7b1` 유지.
- `cb44b605b498`: 9/20, reserved 0. `c85d9853906a`: 1/7, reserved 1 유지.
- 기존 승인/서명 키·mock MP4·초안 원본 보존. 새 실제 운영 승인이나 서명 키 없음. 원본 proposal/credential binding/계정 자료/로컬 데이터는 Git 제외.

목표 입력→AI 자율 협업→최종 산출물의 실제 시험을 위한 최초 동의안을 준비했다. 실제 관리자·직원 협업과 MP4 완주는 아직 미실행이다. 새 중간 업무 승인 단계는 추가하지 않았다. 남은 최초 외부 전송·실행 동의는 운영 안전 경계이며, 기존 수동 경로의 반복 승인 부채와 OpenRouter 실패 복구는 이번 범위에서 변경하지 않았다. UI 고도화는 하지 않았다.
