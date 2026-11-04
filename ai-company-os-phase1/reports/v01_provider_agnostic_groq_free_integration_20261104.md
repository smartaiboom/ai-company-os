# 공급자 분리 및 Groq 무료 계정 경로 통합 — 오프라인 MP4 한 사이클

작성: 2026-11-04T10:36:53+09:00 KST. `git pull --ff-only`로 main `acf6b05` 반영. 핵심 원칙·AGENTS.md·한국어 규칙·인수인계·기존 실제 실행/응답 복구/영상 준비 보고서·두 번째 시험 준비 지시서·관련 코드와 데이터를 읽었다. 이전 두 번째 시험용 별도 store/보고서는 발견되지 않았으며, 기존 데이터 안의 프로젝트를 복제하거나 재실행하지 않았다.

**실제 Groq/OpenRouter/Gemini AI 호출 0회, 실사용 approve/run 0회, 실제 운영 서명 키 생성 0건, 유료 사용 0건.** 공식 개발 문서 조회와 Git 통신은 수행했다. 가짜 HTTPS·합성 키/동의·임시 저장소만으로 자율 협업과 실제 로컬 MP4 생성을 검증했다. 이를 실제 Groq 모델의 제작 성공으로 표현하지 않는다.

## 구현과 기존 경로 보존

- `autonomous_free.py`: 기존 FreeStore의 mode/policy/model/endpoint/rules를 기본값이 동일한 클래스 속성으로 분리했다. FreeCompany에는 adapter/요청 검증/비용 정책/원장 식별/응답 헤더 등의 작은 보호 훅을 추출했다. 업무 상태 기계·수정·선행 전달·품질 정체·중복·원장 선예약·기한·로컬 렌더러는 공유한다. 기존 OpenRouter 계약 형태와 기본 요청 가격 0 필터·cost 0 검증·operation hash 형식은 유지한다.
- `autonomous_live.py`: 역할 content 파싱의 기본값이 기존 `parse`인 훅만 추가했다. 기존 legacy/실제 `AI_ENGINE=openai_compatible`의 `openrouter/free` 보호를 Groq 때문에 우회하지 않는다.
- `groq_provider.py`: 기존 `ProviderSpec`/wire adapter 인터페이스를 재사용하는 별도 Groq adapter. 모델은 **`openai/gpt-oss-20b` 하나**, 고정 endpoint **`https://api.groq.com/openai/v1/chat/completions`**. request token 필드는 `max_completion_tokens=4096`, `reasoning_effort=low`, strict schema다. OpenRouter의 `provider.max_price`/`allow_fallbacks`를 Groq에 보내지 않는다. 예상 요청 필드/모델/schema가 다르면 송신 전 차단한다.
- `role_json_schema.py`: plan/execute/review/finalize의 기존 역할 계약을 strict JSON Schema로 표현했다. 모든 object 필드는 required, additionalProperties=false다. plan은 정상 계획 또는 운영상 stop 결정을 nested anyOf로 표현한다. 최상위 object `{"result":...}`에서 검증된 result만 기존 상태 기계에 전달한다. 서버의 strict 지원만 믿지 않고 로컬에서도 동일 schema 부분집합과 기존 업무 의미 검증을 적용한다. 불완전 JSON·비정상 finish·refusal·도구 호출은 수락하지 않는다.
- `autonomous_groq.py`: 별도 `GroqStore/GroqCompany/GroqConfig`. marker `.autonomous-groq-free-v2-store`, mode `autonomous_groq_free_v2`, policy `groq_free_v2`, ID `groqcompany-…`. API 키는 **GROQ_API_KEY만** 사용한다. 기존 OpenRouter 저장소/키/승인을 Groq로 바꾸거나 재서명하지 않는다. 공급자/모델/endpoint/비용 정책은 계약과 요청·operation hash/원장에 결합된다. 원장의 기존 역할명 provider와 실제 공급자 provider_id는 별도 필드다.
- `autonomous_live_cli.py`: 새 store 생성용 `--provider groq`; 기존 marker로 공급자를 고정 판별하고 공급자 변경·혼합 namespace를 거부한다. Groq prepare에 별도의 계정 확인 옵션을 추가했다. 준비만으로 서명/승인/송신하지 않는다.
- `tests/test_autonomous_groq.py`: 외부 socket/DNS를 차단하고 가짜 Groq 요청이 고정 URL·합성 Groq 키·strict schema·예약 원장을 통과하는지 검사한다. 영상 업무 판단/예시 콘텐츠는 테스트 fixture에만 있다.

Gemini 구현/키/호출/자동 fallback은 없다. 후속 공급자는 같은 adapter/보호 훅을 구현하고 별도 namespace·계약·정책·테스트를 갖춰야 한다. 무제한 동적 endpoint나 모델 registry는 추가하지 않았다.

## 공식 문서와 무료 계정 정책

Groq는 OpenAI 클라이언트와 대체로 호환되는 별도 API이며, Groq endpoint와 Groq 키를 사용한다. 여기의 GPT-OSS 모델 호출은 OpenAI 공식 유료 API 호출이 아니다. [Groq 호환 문서](https://console.groq.com/docs/openai)

공식 문서는 선택한 GPT-OSS 20B의 strict JSON Schema를 지원하며 모든 object의 required/additionalProperties 규칙을 요구한다. 이번에 모델별로 해당 schema mode만 선택하고, 지원하지 않는 모델/자의적 파서 완화/JSON mode fallback을 허용하지 않았다. GPT-OSS의 low reasoning effort와 max_completion_tokens도 공식 요청 계약을 확인했다. [구조화 출력](https://console.groq.com/docs/structured-outputs), [API reference](https://console.groq.com/docs/api-reference)

**Groq 응답에서 cost 누락을 비용 0 증거로 취급하지 않는다.** Groq의 Free tier와 Developer tier는 별개이며 Developer 전환에는 결제 수단이 필요하다. 공식 spend limit 기능도 유료 계정용이므로 이를 무료 보호로 착각해 결제를 연결하지 않는다. [Billing FAQ](https://console.groq.com/docs/billing-faqs), [Spend limits](https://console.groq.com/docs/spend-limits)

실행 전 소유자가 Console에서 **Free plan, 결제/과금 비활성, 선택 모델 사용 가능**을 확인해야 한다. `prepare --confirm-groq-free-account`는 그 사실을 직접 확인했다는 운영자의 주장으로만 사용한다. 키 문법을 로컬 검사하고 키의 SHA256 binding·KST 확인 시각을 계약에 넣는다. 이 확인은 24시간 이내여야 하며, 별도 최초 운영 승인 후 계약 서명으로 보호된다. 계정 미확인/다른 키/만료면 approve와 송신을 차단한다. 만료·키 변경 뒤에도 revoke는 가능하게 했다.

이것은 서버에서 계정 청구 상태를 조회한 증명이 아니다. 이번에는 Groq 키가 없고 계정에 로그인하지 않았으므로 **실제 무료 계정/청구 상태 미확인**이다. 현재 draft는 의도적으로 계정 확인값 false/null이며 승인 불가다. 이후 Console 확인 없이 확인 옵션을 사용해서는 안 된다. 원격 계정 상태 변경을 실시간 감시하는 기능도 없으므로 소유자의 최신 확인이 필수다. 응답 cost가 없을 때 원장에는 `free_account_policy_verified`/signed account attestation이라는 근거를 쓰며 `cost_verified_zero=true`를 꾸며 쓰지 않는다. 만약 cost가 명시되면 숫자 0만 허용하고 양수/비정상 값은 정지한다.

기관별 실제 무료 쿼터는 Console Limits에서 확인해야 하므로 고정 RPM/TPM을 무료 보장으로 하드코딩하지 않았다. 기존 2초 pacing·30분 기한·유한 업무/수정 한도는 유지하고, 429/402/401/5xx 등은 안전 정지한다. Retry-After와 남은 요청/토큰 등의 허용된 숫자 헤더만 기록하며 헤더 원문/계정 정보는 저장하지 않는다. 남은 요청 또는 토큰이 0이면 다음 송신 전에 정지한다. reset 후 자동 재송신·계정 전환·유료 전환은 없다. [Rate limits](https://console.groq.com/docs/rate-limits)

## 가짜 Groq → 실제 로컬 MP4 증거

최종 영상 업무 fixture는 관리자 계획→대본 담당 초안→관리자 수정→대본 보완/수락→선행 대본을 받은 영상 담당→장면 JSON 제출→FFmpeg/TTS→기술 검사→관리자 검토→최종 제작 보고서다. **CLI run 1회**, fake HTTPS **8회**, 직원 **2명**, 수정 **1회**, 사용자 중간 업무 결재 **0회**, delivered와 final.json/md를 확인했다. 최종 fixture의 대본·장면·판정은 개발용 가상 데이터다.

- 증거 label: `FAKE_GROQ_HTTPS_NOT_ACTUAL_AI`
- 최종 증거 store: `/workspaces/ai-company-os/ai-company-os-phase1/data/groq-offline-evidence-final-20261104`
- 모의 프로젝트: `groqcompany-f39b292a4a784c0fbaaeb9cae9496237`
- MP4 원본: `/workspaces/ai-company-os/ai-company-os-phase1/data/groq-offline-evidence-final-20261104/artifacts/groqcompany-f39b292a4a784c0fbaaeb9cae9496237/tool-ae22abe0ebb1eff3453dc0105e96d52a52603e83f5791464c31fe62df05f7375/video.mp4`
- 쉬운 다운로드용 복사본: `/workspaces/ai-company-os/ai-company-os-phase1/data/groq-offline-evidence-final-20261104/preview/video.mp4` (Codespaces 탐색기에서 이 파일을 내려받을 수 있음)
- 검증: **1280×720, 24.02322초, 24fps/576프레임, H.264/yuv420p, AAC 한국어 합성 음성, 한국어 자막**.
- SHA256: `8db61afd9bade347c1a6e37946dca05663be8f44b94d0c82d5409604c16e4574`. ffprobe 및 전체 ffmpeg 디코딩 성공. 8초 프레임을 추출해 한글 표시도 확인했다.
- 역할 입력/수정/선행 전달·관리자 검토·도구 receipt·KST·request/operation hash·서명된 합성 동의·최종 산출물은 해당 모의 store에 보존했다. 이 합성 테스트 승인은 실사용 운영 승인이 아니다.

이전 렌더러와 동일한 제한된 장면 fixture를 써서 MP4 SHA가 기존 mock 영상과 같을 수 있다. 이는 실제 FFmpeg 호출과 새 Groq 가짜 요청 원장으로 재생성된 파일이며, 기존 파일을 실사용 결과로 둔갑시키지 않았다. 텍스트·eSpeak 중심의 단순 영상이다. 미적 품질·음성 자연스러움이나 실제 Groq의 업무 품질은 검증하지 않았다. 초기 호환 fixture 증거 `data/groq-offline-evidence-20261104`도 삭제하지 않고 보존했으며 위 final 증거를 최종 기준으로 삼는다. Git에는 영상/모의 원장/서명 키도 넣지 않는다.

## 신규 실사용 대기 프로젝트 — 정확히 한 건

- store: `/workspaces/ai-company-os/ai-company-os-phase1/data/groq-video-smoke-20261104`
- ID: `groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e`
- 목표 hash: `3cf69cc191d65718ef1571671a3f85940676d3c8da7992f7d1760eec45bbb5c9`
- 초기 상태 hash: `25d3e5d7c3666acac578d278aab63f00848716f904a4cb1dbe7f22dcc495db5f`
- 동의 draft: `/workspaces/ai-company-os/ai-company-os-phase1/data/groq-video-smoke-20261104/operating-proposal.json`
- 현재 draft review hash: `51eccb7b6daf10bf6da723becb3a05ac704254662c5847362ced67411d326c23`
- draft 만료: `2026-11-11T10:32:43+09:00` KST.
- 모델: `openai/gpt-oss-20b`, provider groq, 고정 HTTPS.
- ready/plan, 실제 원장 0건, enabled=false, grant·실사용 서명 키 없음, 로컬 caption_video_v1 허용.

동일한 작업을 반복해도 이 store의 프로젝트를 재생성하지 않도록 존재 여부와 프로젝트 1건을 확인했다. 앞선 OpenRouter 실패 프로젝트의 복구/승인을 재사용하지 않는다. 이번 실제 데이터 생성은 이 신규 프로젝트와 미승인 draft뿐이며 기존 데이터는 읽기 전용이다.

현재 draft는 계정 검증 미완료라 **바로 approve할 수 없다**. 키와 계정 조건을 충족한 뒤 같은 프로젝트에서 새 파일명으로 계정 확인이 결합된 제안을 prepare해야 한다. 이때 review hash·발행/만료 시각은 달라지므로 **새 제안 전체를 검토한 후 최초 운영 동의를 한 번만** 받아야 한다. 목표/공급자/모델/도구/비용/전송 범위를 임의 확대하지 않는다.

동의할 외부 전송 범위는 이 목표 및 해당 새 프로젝트의 계획/품질 기준/배정/대본/자막/장면/직원 결과/관리자 검토·수정·최종 통합 텍스트와 로컬 render 메타데이터다. 기존 파일/코드 본문/MP4/WAV/계정 정보/키는 모델 메시지에 넣지 않는다. 키는 고정 Groq endpoint의 인증에만 쓴다. 로컬 FFmpeg/eSpeak 실행과 외부 전송 허가는 계약에서 구분한다. 비용 0/유료 fallback 금지, 공급자 제한·30분·오류/중복 보호, 만료와 데이터 범위를 최초 운영 동의에서 함께 확인한다.

## 키 준비와 다음 실전 명령 (이번에는 실행 안 함)

소유자가 [Groq Keys](https://console.groq.com/keys)에서 자신의 계정에 직접 로그인해 키를 준비해야 한다. Codex가 대신 로그인/키 발급/결제 설정을 수행하지 않았다. 키는 대화·보고서·Git·명령 인자·.env에 복사하지 말고 **GitHub Settings → Codespaces → Secrets → GROQ_API_KEY**, 해당 저장소 접근 허용으로 등록한다. 새 Secret은 Codespace 재시작 후 환경변수로 사용할 수 있다. [GitHub 공식 Secrets 안내](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-your-account-specific-secrets-for-github-codespaces)

현재 환경에서는 GROQ_API_KEY 존재 여부 false, Groq 실행 flag false만 확인했다. 다른 공급자의 키를 재사용하지 않는다. 실제 Free plan/무결제/모델 허용을 먼저 확인한 후 다음 순서를 사용한다. 아래 approve/run은 **향후 명시 승인 후에만 실행할 예시**이며 이번 작업에서는 실행하지 않았다.

```bash
# 키는 사전에 Codespaces Secret으로 준비. 아래는 비밀값이 아닌 고정 설정.
export GROQ_MODEL=openai/gpt-oss-20b
export GROQ_BASE_URL=https://api.groq.com/openai/v1
# Console에서 무료/무결제/모델 허용을 직접 확인한 뒤 새로운 동의안 준비
python -B -m autonomous_live_cli --store data/groq-video-smoke-20261104 prepare groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e --confirm-groq-free-account --proposal-out /tmp/groq-reviewed-account-proposal.json
# 새 계약과 출력 review hash를 소유자가 최초 1회 명시 승인한 뒤에만:
python -B -m autonomous_live_cli --store data/groq-video-smoke-20261104 approve groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e --proposal /tmp/groq-reviewed-account-proposal.json --review-hash REVIEW_HASH --owner-confirmed
# 승인된 실행 프로세스에서만 활성화하고 최신 승인 상태 hash 사용
GROQ_AUTONOMOUS_FREE_ENABLED=1 python -B -m autonomous_live_cli --store data/groq-video-smoke-20261104 run groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e --state-hash APPROVED_STATE_HASH
```

## 검증·보존·남은 한계

- 보호 훅 추출 후 기존 OpenRouter/진단/legacy 집중 회귀: **54개 통과** (7.466초).
- Groq 초기 테스트: 10개 중 2개 실패(provider 역할명과 공급자 ID 충돌). 별도 provider_id로 고쳐 원장 의미를 유지했다.
- `python -B -m unittest tests.test_autonomous_groq tests.test_autonomous_free tests.test_provider_response_recovery tests.test_autonomous_live tests.test_local_artifacts`: **70개 통과** (21.113초).
- 영상 목적에 맞춘 최종 fixture의 `python -B -m unittest tests.test_autonomous_groq`: **10개 통과** (11.259초). 해당 fixture로 증거도 별도로 생성했다.
- `python -B -m unittest discover -s tests`: **612개 실행, 611개 통과·1개 건너뜀, 실패/오류 0, exit 0** (98.221초). 기존 loopback 테스트 때문에 권한 확장으로 실행했다. OpenRouter 22 fake-call 자율 DAG, 기존 mock MP4, legacy 2/20·동의/중복·진단 회귀 포함. 로그 `/tmp/groq-full.log`.
- 핵심 Groq 안전 사례: 계정 미확인/변경 키·모델·endpoint/flag 차단, 계약 scope/비용/도구 변경 거부, strict schema 불일치·JSON 오류·refusal·비정상 finish, 비용 양수, 429/402/401, 숫자 헤더만 기록, 남은 쿼터 0, 수신 후 crash와 중복 재진입 차단, 계정 확인 만료 후 revoke, CLI 공급자 변경 거부.
- 실행 전 기존 데이터/백업/프로젝트 **47개** SHA256 기준 확보. 최종 비교에서 **47개 모두 동일, 변경 0건**을 확인했다. OpenRouter 실패 프로젝트의 stopped/plan·active_operation·completed-unvalidated와 승인, `cb44...` 9/20, `c85...` reserved 1, 기존 영상/백업/사용자 미추적 파일을 변경하지 않는다.
- `git diff --check` 통과. 코드/테스트/이 보고서만 선택적으로 커밋·푸시하며 모든 데이터·계약·영상·키는 제외한다.

이번 변경은 같은 자율 엔진에서 공급자별 기술 계약을 분리하고 **목표→관리자/직원 협업→로컬 MP4**의 두 번째 공급자 경로를 오프라인으로 완성했다. 업무별 사용자 승인 단계를 추가하지 않았다. **실제 Groq 모델 협업 성공, 실제 무료 청구 검증, 고품질 영상 제작은 아직 미검증**이며, 사용자 계정/키/무료 조건 확인과 한 번의 최초 프로젝트 운영 동의 후 실제 실행이 남았다. 기존 실패 원장의 무단 복구는 하지 않았다. 대시보드/화면 고도화는 개발하지 않았다.

## 작업 중 추가된 다중 공급자 정책 반영과 후속 확장 규칙

첫 push 시 원격 main에 정책 문서 커밋 `96d1bfa`가 추가되어 거절됐다. 원격 변경은 AGENTS.md·핵심 원칙 4-2·이번 지시서의 추가 정책뿐임을 확인하고, 내용을 읽은 뒤 충돌 없이 rebase했다. Groq 우선 한 사이클 검증, 공급자별 정당한 무료 할당량 활용, 다른 계정으로 쿼터 우회 금지, 별도 송신 동의, 추후 검증된 공급자만 명시 예산 승인 후 유료 전환이라는 정책과 이번 구현은 일치한다. Gemini나 유료 경로는 추가하지 않았다.

후속 무료 공급자의 공통 확장 규칙/검증 체크리스트는 다음과 같다.

1. `ProviderSpec`의 고정 모델·endpoint·wire format·capability를 공식 문서로 확인하고 별도 adapter를 구현한다. 요청 필드 allowlist와 모델별 strict schema 지원을 검사하며 미지원 공급자에 옵션을 그대로 복사하지 않는다.
2. FreeStore/FreeCompany의 보호 훅을 재사용하되 새 marker·policy·ID·전용 secret·계정 무료 정책을 둔다. schema/요청 정규화와 비용 증거를 공급자별로 정의하고, 기존 서명 계약이나 실패 operation을 재사용하지 않는다.
3. 최초 전송 scope/로컬 도구/모델/무료 근거/만료·원장 결합을 검증한다. API 키 존재만으로 무료 계정이나 송신 동의를 인정하지 않는다. 비용·무료 조건 불명이면 차단한다.
4. 동일한 가짜 HTTPS 협업·수정·선행 전달→실제 MP4→최종 보고를 CLI run 한 번으로 검증하고, 비정상 종료/거절/비용/429/402/schema/키/계약 변경·crash 중복 차단 및 다른 공급자 회귀를 실행한다.
5. 비교 지표는 원장의 provider_id/model/request hash, reserved_at/transport_started_at/response_received_at/finished_at(KST), response_diagnostics의 finish/validation/json_parse/tokens, rate_limits와 관리자 review/checks·최종 artifact를 근거로 계산한다. HTTP 완료율과 업무 검증 완료율을 분리하고, 지연은 송신→수신 시각 차이로 산출한다(현행 KST 초 단위 정밀도). 사용자 체감 영상 품질은 토큰 수나 technical decode 성공으로 대체하지 않는다. 이번 fake 지표는 실제 공급자 지연/품질 비교 근거가 아니다.
6. 여러 공급자의 실사용 비교와 유료 전환은 후속 작업이다. 사전 승인 없는 공급자 전환·실패 요청 자동 복제·유료 fallback을 만들지 않는다. 대시보드는 실제 한 사이클 완주 뒤에 저장된 지표로 개발한다.
