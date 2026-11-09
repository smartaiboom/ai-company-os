# AI Company OS — Groq 키 등록 후 실사용 직전 점검 (실제 API 호출 금지)

기준: 2026-11-04 KST

## 사용자 확인 사항
사용자는 GitHub Codespaces 터미널에서 `GROQ_API_KEY` 환경변수가 존재한다는 확인 메시지 **“Groq 등록 성공”**을 받았다. 기존 OpenRouter용 `AI_API_KEY` 역시 등록됨을 확인했다. **이는 키 존재 확인일 뿐, Groq 계정의 무료 플랜·청구 비활성화·모델 허용·API 연결 성공을 증명하지 않는다.**

## 작업 목표
기존 AI Company OS의 실제 데이터 및 현재 개발 결과를 보존하면서 **Groq 실사용을 위한 준비 상태와 차단 요인을 확인**하고, Groq 전용 신규 영상 프로젝트의 동의안을 적절히 준비한다. 이번에는 실제 Groq/OpenRouter/Gemini API 요청을 **0회** 유지한다. 사용자가 승인하기 전 실제 approve/run 및 외부 AI 전송 금지.

## 먼저 확인할 자료
- `AI_COMPANY_OS_CORE_PRINCIPLES.md` (특히 실제 자율 협업 한 사이클, 4-2 다중 무료 공급자 전략)
- `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`
- `reports/v01_provider_agnostic_groq_free_integration_20261104.md`
- `reports/v01_real_free_ai_video_one_cycle_20261104.md`
- `reports/v01_real_free_provider_response_recovery_20261104.md`
- `autonomous_groq.py`, `groq_provider.py`, `autonomous_live_cli.py`, 운영 제안/동의·ledger/비용 보호 경로

## 절차
1. `git pull --ff-only` 후 관련 코드를 확인한다. 재개 중인 Codex 작업, 원격 변경 또는 사용자 파일과 충돌이 있으면 멈추고 상태를 보고한다. 무분별한 reset/clean/force push 금지.
2. 키 **값을 출력·기록·로그·보고서·Git에 남기지 않고** `GROQ_API_KEY` 존재 여부만 점검한다. `AI_API_KEY`나 기존 설정 파일을 변경하지 않는다. 키가 없으면 동의안 갱신 없이 안전하게 멈추고 안내한다.
3. 현재 Groq 전용 store `data/groq-video-smoke-20261104`, 프로젝트 `groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e`의 존재 여부, 목표/state hash, ready/plan, attempted 0, grant 없음, 이전 draft의 구조와 현재 계약·코드 일치 여부를 **읽기 전용** 점검한다. 기존에 예기치 않은 실사용 승인·송신 흔적이 있으면 덮어쓰거나 새로운 프로젝트로 우회하지 말고 즉시 보고한다.
4. 공급자·모델은 `groq` / `openai/gpt-oss-20b` / 고정 `https://api.groq.com/openai/v1/chat/completions`. 무료 계정과 청구 비활성화는 **API 키만으로 확인할 수 없다**. `https://console.groq.com/`에서 사용자가 Free plan / 결제·과금 비활성 / 선택 모델 사용 가능 여부를 직접 확인했다는 사실이 **명시적으로 전달되지 않았다면**, `--confirm-groq-free-account`를 임의로 사용하지 말고 해당 확인이 미완료라고 보고한다. 개발자가 계정 상태를 확인했다고 거짓 주장하지 않는다. 실제 공급자 호출을 통한 조회/진단도 하지 않는다.
5. 사용자 확인이 없어 account attestation이 불가능하면 현재 미승인 draft만 보존하고, **정확히 어느 계정 확인과 어떤 명령이 필요한지** 최소 단계로 한국어 보고한다. 이미 적법하게 확인된 계정 정보가 있으면 정상 CLI `prepare`만 사용하여 동일 신규 프로젝트의 계정 검증 포함 동의안을 별도 안전 위치에 만들고 프로젝트 ID, 최신 goal/state hash, review hash, model, provider, 외부 송신 텍스트 범위, 로컬 도구 범위, 만료 KST 및 미승인 상태를 보고한다. 생성 전 기존 draft/파일은 백업·보존하고 임의 삭제·교체 금지. **approve --owner-confirmed, run, continue 등 실제 실행/전송 관련 명령은 전부 금지**한다.
6. 실사용 전 차단 요인과 사용자의 다음 실제 동의가 무엇인지 간결히 정리하되, 실전 승인 요청에 필요한 계약 hash는 실제 새 제안을 발행한 경우에만 근거를 붙인다. 사용자 업무 내용에 대한 반복 중간 승인 요구 금지. **다른 공급자 키/운영 동의를 Groq에 재사용하거나 유료 fallback 사용 금지**.
7. 기존 OpenRouter 실패 원장(특히 `freecompany-ae4aa334511d470c8c517685e9902a53`), `cb44b605b498`, `c85d9853906a`, 기타 data/backup/mock MP4, 실제 프로젝트 시도·서명 키 모두 불변을 확인한다. 현재 Groq 프로젝트도 최초 송신 전 상태 그대로. KST 사용.
8. 불필요한 설계 변경/테스트 확장 없이 필수 읽기 전용 점검과 필요 최소한의 오프라인 검증을 수행한다. 결과는 `reports/v01_groq_live_readiness_check_20261104.md`에 작성해 코드/보고서 중 변경된 것만 선택적으로 commit/push. 실제 비밀키/원본 proposal/계정 정보/사용자 로컬 데이터는 Git 제외. 실제 AI API 호출 **0회**를 명시한다.

## 기대 결과
- Groq 키가 환경에 존재한다는 것과 **Groq 무료 계정 상태가 별도로 확인됐는지**를 정확히 구분한다.
- 실사용 이전 프로젝트/계약/안전 상태를 검증해 다음 단계의 조건을 확인한다.
- 계정 확인이 없다면 무리하게 새 계약을 발행/승인하지 않고 **한 가지 필요한 사용자 확인**을 제시한다.
- 이미 확인돼 있다면 동일 프로젝트의 승인 가능한 최신 제안을 prepare까지만 진행한다.
- 실제 AI 회사 관리자→직원→MP4 작업은 이번에 실행하지 않는다.
