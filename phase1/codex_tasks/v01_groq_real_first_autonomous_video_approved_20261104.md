# AI Company OS — 사용자 명시 승인된 Groq 첫 실제 무료 AI 영상 자율 운영 1회

작성일: 2026-11-04 KST. **이 지시서는 아래 사용자의 특정 프로젝트·계약에 대한 명시 운영 승인을 기록해 Codex가 정상 CLI approve 1회와 run 1회를 수행하도록 한다.** 다른 프로젝트/모델/시도에는 동의가 확장되지 않는다.

## 사용자의 명시 승인 (원문)

> Groq 신규 프로젝트 groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e의 최초 무료 AI 자율 운영을 승인해. 승인 대상 동의안 해시는 e77a83d47b73176faad55fdfee563c357407fef3bcbd8046c11a73d8da9c305a이고, 만료 전 유효성을 검증해 줘. Groq openai/gpt-oss-20b 고정, 위에서 설명한 프로젝트 생성 텍스트와 로컬 렌더 메타데이터만 외부 전송하고 기존 파일·영상/음성 원본·계정 정보는 전송하지 마. 로컬 FFmpeg/eSpeak 허용, 유료 전환 금지, 무료 한도와 최대 30분·오류·중복 보호를 지켜. 최초 approve 1회와 run 1회를 Codex가 실행하도록 작업 지시서를 만들어 줘.

**이 명시 승인을 기존 일반 API 연결/개발 승인과 혼동하지 말 것. 사용자는 이 정확한 한 건에 대해 approve 및 실제 최초 run을 허용했다.** 업무 계획, 직원 결과, 관리자 검토 등 내부 업무 내용에 관해서는 중간 사용자 승인을 추가로 요구하지 않는다. 실행 권한이 유효하지 않을 때 임의로 다른 계약·프로젝트로 옮기지도 않는다.

## 작업 시작 전 확인 문서와 운영 근거
1. `AI_COMPANY_OS_CORE_PRINCIPLES.md`, `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md` 및 멀티 무료 API 전략.
2. `reports/v01_provider_agnostic_groq_free_integration_20261104.md`, `reports/v01_groq_live_readiness_check_20261104.md`, `reports/v01_groq_first_live_consent_prepared_20261104.md`의 실제 보고.
3. 현행 `autonomous_live_cli.py`, `autonomous_groq.py`, `groq_provider.py`, provider wire/schema, local renderer, 계약 서명/원장 보호 코드. 미리 실패한 OpenRouter 실사용 프로젝트는 다른 store와 승인 체계임.

## 승인된 불변 식별 정보
- Store: `data/groq-video-smoke-20261104` (사용자의 Codespaces에서 `ai-company-os-phase1` 하위).
- 프로젝트: **`groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e`**.
- 목표 hash: `3cf69cc191d65718ef1571671a3f85940676d3c8da7992f7d1760eec45bbb5c9`.
- 승인 전 state hash: `25d3e5d7c3666acac578d278aab63f00848716f904a4cb1dbe7f22dcc495db5f`.
- 준비된 proposal (Codex 로컬): **`/tmp/groq-account-reviewed-proposal-20261104.json`**.
- 사용자가 승인한 **canonical review hash: `e77a83d47b73176faad55fdfee563c357407fef3bcbd8046c11a73d8da9c305a`**.
- 계정 확인 및 제안 발행: `2026-11-04T11:35:43+09:00`.
- **만료: `2026-11-05T11:35:43+09:00` (KST)**. 키/계정 확인 유효성 24시간도 엄수한다.
- 모델/공급자: `groq` / **`openai/gpt-oss-20b`** 만 허용; 정해진 URL `https://api.groq.com/openai/v1/chat/completions`. `GROQ_API_KEY`만 인증에 사용한다.
- 목적: ChatGPT 초보자에게 좋은 질문을 작성하는 방법을 설명하는 **한국어 20~30초 MP4** (자막 포함, 가능하면 로컬 한국어 음성), 실제 파일과 제작 보고서. 실제 콘텐츠는 Codex가 임의로 작성해 성공처럼 꾸미지 않고 **실제 Groq AI 관리자/직원이 생성·검토**한다.

## 외부 전송과 실행 권한의 정확한 범위
- 사용자 승인 데이터: **이 새 프로젝트의 목표**, 새로 생성되는 관리자 계획/성공 기준/직원 배정, 대본·자막·장면 계획, 직원 결과/선행 전달, 관리자 검토/수정/최종 통합 텍스트 및 **로컬 FFmpeg/TTS 렌더 결과의 제한된 메타데이터**.
- **외부 전송 금지:** 기존 파일·코드 본문·백업·개인 정보·원본 MP4/WAV/음성 파일·비밀키·계정 정보·시스템 환경변수. API 키는 고정 Groq HTTPS의 Authorization 헤더에만 사용하고 모델 메시지·로그로 보내지 않는다.
- 로컬 도구만 `caption_video_v1` 허용: FFmpeg/ffprobe, 선택적 eSpeak NG 한국어 음성, 한국어 자막 MP4 생성/검사. 로컬 도구의 외부 업로드/임의 네트워크 접근은 허가하지 않는다.
- 계정 Free $0 플랜 (사용자가 Groq Billing/Plans 화면에서 Current Plan Free 직접 확인), Developer 플랜 활성화 금지. `openai/gpt-oss-20b` 사용 한도 화면: 조직 기본 **30 RPM, 1000 RPD, 8000 TPM, 200000 TPD** (프로젝트별/잔여치·실제 공급자 제한 우선). 무료 정책 `max_cost=0`, billing_enabled=false, paid_fallback=false. 공급자와 모델 변경/다른 무료 계정·키 전환/결제 설정 변경 금지. Groq의 cost 필드 누락을 0 비용 확정이라고 거짓 주장하지 말고 무료 계정·서명된 계약 근거와 비용 검증 정책을 따른다.
- 첫 실행 최대 **1800초(30분)**, 최대 업무 8개, 업무당 수정 1회/총 2회 등 기존 안전 상한, 2초 pacing/쿼터/중복/비정상 종료·미확정 operation 보호. 정상 무료 업무 진행을 예전 2/20 인위적 상한으로 끊지 않는다. **추가 반복 run, continue, 새로운 복구 송신은 이번 동의에 포함되지 않는다.**

## 실행 프로토콜 (반드시 이 순서)
1. `git pull --ff-only`로 최신 코드/문서 확인. 원본 proposal, state, ledger/consent, 파일들은 **읽기 전용으로 먼저 검증**한다. 다른 작업 변경/미추적 파일과 충돌 시 멈춘다. 무단 reset/clean/force push 절대 금지.
2. **유효기간을 현재 KST 시계로 검증.** 만료되었거나 시간이 불명확하면 **approve/run 둘 다 수행하지 말 것**. 새로운 제안을 다시 prepare해서 이번 과거 해시 승인으로 실행하지 말 것. 그 경우 새로운 해시와 별도 재승인을 요청하는 결과 보고만 남긴다.
3. `/tmp/groq-account-reviewed-proposal-20261104.json` 존재, JSON canonical review digest 일치, 프로젝트 ID/goal hash/state hash/계정 무료 확인·key binding/발행·만료·모델·URL·전송 scope/로컬 도구/기한 일치, `GroqStore._check_contract` 및 현행 CLI가 요구하는 모든 사전조건 통과 확인. **/tmp 파일이 Codespaces 재시작으로 사라졌다면 원본 계약을 임의 재발행·이전 승인 해시로 위장하지 말고 정지/보고.**
4. 새 Groq store가 정확히 초기 `ready/plan`, attempted=0, enabled=false, grant 없음, active_operation 없음, session/event=0, 서명 키 없음인지 확인. **이미 approve·run했거나 실패 원장이 있다면 이 지시서를 재실행해서 호출을 복제하지 말 것**. 실행 중 타 프로세스가 같은 프로젝트를 조작하지 못하도록 현재 코드의 배타/원장 보호 사용.
5. `GROQ_API_KEY` 환경변수의 **존재와 정상 계약 결합만 확인**; 키 값/접두어/길이/원문 hash를 출력하거나 리포트/커밋에 남기지 않는다. `AI_API_KEY`·기존 .env·OpenRouter 실사용 데이터는 불변. Free 계정·유료 미활성 확인이 현재 계약 유효 기간 동안 유지돼야 하며, 조건 변경·불확실하면 정지.
6. 위 조건이 모두 통과하면, 사용자 원문 승인을 근거로 **정상 CLI의 `approve --owner-confirmed`를 정확히 한 번 실행**:
```bash
python -B -m autonomous_live_cli --store data/groq-video-smoke-20261104 approve groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e --proposal /tmp/groq-account-reviewed-proposal-20261104.json --review-hash e77a83d47b73176faad55fdfee563c357407fef3bcbd8046c11a73d8da9c305a --owner-confirmed
```
   출력된 **승인 후 새 storage_hash**를 구조적으로 파싱한다. 공개 보고서에는 불필요한 서명/키/민감 필드 포함 금지. 승인 실패, 해시 미확인 또는 상태 중복이면 **run 금지**.
7. 승인 후 상태와 서명 grant 재검증. 그 최신 **APPROVED_STATE_HASH**를 `--state-hash`에 넣어 **정상 CLI run 정확히 1회** 실행. 해당 프로세스에만 `GROQ_MODEL=openai/gpt-oss-20b`, `GROQ_BASE_URL=https://api.groq.com/openai/v1`, `GROQ_AUTONOMOUS_FREE_ENABLED=1`을 설정한다. `run`은 호출 1회가 아니라 AI 회사 업무 사이클 1회이며 **그 안의 정상 승인된 여러 AI 호출은 허용**한다. 별도 글로벌 설정/키/가격 정책을 변경하지 말 것.
```bash
GROQ_MODEL=openai/gpt-oss-20b GROQ_BASE_URL=https://api.groq.com/openai/v1 GROQ_AUTONOMOUS_FREE_ENABLED=1 python -B -m autonomous_live_cli --store data/groq-video-smoke-20261104 run groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e --state-hash "$APPROVED_STATE_HASH"
```
8. 사용자로부터 업무 계획/대본·장면/품질/직원 수정 등 **중간 업무 승인 요구 없이**, 실제 Groq 관리자가 계획/기준·검토/수정을 결정하고 실제 Groq 직원들이 앞선 결과를 전달해 MP4까지 만드는지 검증한다. 가짜 HTTPS/mock/fixture/개발자가 작성한 대본을 실제 결과로 대체하지 않는다. 실패하면 안전 정지/원장 보존, **중복 run, continue, 새 프로젝트 생성, 다른 provider fallback, auto retry 및 신설 비용 정책 우회 전부 금지**.
9. 결과를 `reports/v01_groq_real_autonomous_video_first_run_20261104.md`에 저장하고 사실/한계 분리:
   - 첫 approve/run의 정확한 실행 횟수, KST 타임라인, Groq 모델, 실제 호출 수·완료/실패/미확정·토큰·제한 진단·무료 확인 근거(비밀값 제외).
   - 실제 **AI 관리자 계획 채택 여부, 직원 수/업무 전달, 관리자 검토/수정, 최종 결과**.
   - 성공 시 **실제 AI 실행으로 생성된 MP4 정확한 로컬 절대 경로**, preview/download 복사본 경로(같은 신규 store 내, 외부 업로드 금지), ffprobe/디코딩·길이·해상도·한국어 자막/오디오 검증, 정확한 SHA. **기술적 MP4 성공과 영상 미적 품질/자연스러운 목소리 차이** 명시.
   - 실패 시 **정확한 phase/finish reason/진단 및 blocked operation**을 구분. 완료 아닌데 프로세스 exit 0만 보고 성공이라 하지 말 것. 수신 실패/비정상 출력/유료 조건/모호 응답은 보존하고 추가 호출 없이 멈춘다.
   - 승인 범위·동의안 해시·새 프로젝트 외 기존 자료/파일/백업 변화 여부와 재실행 금지 사유.
10. 해당 작업에 필요한 **보고서만**(필요하면 별도 사용자 동의 없이 허용된 안전한 최소 코드 버그 수정 및 오프라인 테스트 결과를 명시) 선택적 commit/push. 기존 실사용 데이터/비밀키/contract/로그/MP4 원본은 Git 제외. Codex가 수행한 실제 호출을 숨기거나 fixture를 실사용으로 주장하지 않는다.

## 완료 기준
**승인된 유효 프로젝트에 한해 정확히 최초 approve 1회 + run 1회** 수행하고 실제 모델이 AI 관리자→직원→관리자 검토→로컬 MP4 결과까지 도달했는지 근거로 판단한다. 계약 만료·불일치·계정/키 조건 미충족 시 **0회 송신으로 안전 정지**하고 이유를 보고한다. 첫 실제 시험이 실패하더라도 기존 시도·승인 원장을 고쳐 재전송하지 않는 것이 우선이다.
