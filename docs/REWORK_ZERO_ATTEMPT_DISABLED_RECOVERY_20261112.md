# 컷룸 미션01 — gemini_execution_disabled, 외부 호출 0회인 재작업만 안전하게 재시작
작성일: 2026-11-12 KST

## 확정 상태
사용자가 이미 대표 피드백을 제공하고 새 전송 동의를 승인함. 컷룸 'AI 재작업 시작' 클릭 후 화면은 `gemini_execution_disabled`, `시도 0`, 현재 프로젝트 상단은 `기획 수정 요청`, 별도 rework 상태는 `stopped`(예상). 동의서 `qualityprovider-3cb52d1ab205460897e9f03fea21ca71.consent.json` 크기 28841바이트였으며 64KiB 한도 수정 완료. **실 Gemini에 실제로 송신한 요청이 없었음(시도0)**. 그래도 사용자가 클릭을 반복하지 않도록 안내한 상태.

코드 근거:
- `core/autonomous_gemini.py` `GeminiCompany._check_provider_config`: `os.getenv(self.enabled_env)=='1'` 아니면 `gemini_execution_disabled`.
- `core/autonomous_gemini35.py`: `enabled_env='GEMINI35_AUTONOMOUS_FREE_ENABLED'`.
- `companies/video/studio_server.py` `Studio.rework_action`의 background worker가 실패 시 `flow['rework']['status']='stopped'`; `rework-run`은 `approved`만 허용.
- `companies/video/representative_rework.py` `ReworkCompany.run`은 `job['status']=='ready' and not job['sessions'] and not job['real_ai']['attempts']`만 허용. 기회가 시작되기 전 오프라인 환경 검사 실패라도 `sessions` 등이 발생할 수 있으므로 실제 상태를 읽어 판단해야 함.
- 이전 코드는 재시도/복구를 무조건 차단함. **절대로 레코드를 임의 초기화하거나 가짜 0회로 바꿔서는 안 됨**.

## 목표
사용자에게 쉽게 이해되는 **실행 가능 여부/활성화 설정 안내**를 보여주고, **실제 provider 송신 전 단순 설정차단에 한해서만** 기존 승인·동의·원본 데이터를 보존하면서 대표가 명시적으로 실행할 안전한 재개 경로를 제공한다.

1. 현존 **실제 job / 저장 상태 / 서명 / provider journal / sessions / active_operation / attempts / API request ledger**를 정확히 검사하고 이번 사건이 송신 전 환경 검사에서 막힌 게 맞는지 판단. 저장 상태를 `ready`로 무작정 되돌리는 방식 금지. 0 attempts라고 해서 활성/미확정 네트워크 시도가 없다는 뜻은 아니므로 반드시 **모든** 송신·예약·실행 원장 및 안전한 코드 경로로 확증. 애매하거나 송신 가능성이 있으면 계속 차단.
2. 서버 실행 전에 `GEMINI35_AUTONOMOUS_FREE_ENABLED=1` 플래그, `GEMINI35_MODEL=gemini-3.5-flash-lite`, `GEMINI35_ENDPOINT=https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`, `GEMINI_API_KEY` 존재를 안전하게 점검(키값 노출 금지); disabled일 때는 더 이상 **'AI 재작업 시작' 버튼을 누른 뒤에야 실패하는 UX**를 반복하지 않도록 사전 안내/차단.
3. **이번 'gemini_execution_disabled' + 송신0 건만** 명시적인 재개/재실행 상태로 제공. 수정 구현은 기존 원장 이벤트를 불변 보존하고 새 재개 이벤트·사유·현재 승인 범위를 기록, **중복 실행/이중 송신 방지**, HMAC 동의·원본 피드백·만료·사용자 새 동의 적정성 재검증. 이미 유효 동의면 재동의 강제하지 말고, 만료되었다면 새 동의를 요구. 일반적인 실패, 실제 요청1회 이상, 예약/불확실 요청 존재, 가짜 fixtures, 서명 문제, 키 변경에는 재개 금지. 기존 `ReworkCompany.run`의 no-restart 방식을 무차별 해제하지 말고 엄격한 한정 복구.
4. 경로는 컷룸의 현재 미션01 프로젝트 그대로 유지. UI에 **'Gemini 실행 설정 확인 필요'** 같은 유용한 메시지와 실제 수동 재개 버튼(준비 완료 때만) 표시. 활성화 플래그는 사용자가 서버 환경에서 명시적으로 설정(시스템이 몰래 수정하지 않음). 기존 '재작업 중단' 기록과 시도0 보존. 새 project/job/grant 생성·기존 승인 변조 불가. 환경변수 설정은 현재 서버 프로세스가 보는 값에 적용해야 함(재시작 필요). 실제 비용/전송은 **사용자가 재개를 명시적으로 클릭한 다음에만**.
5. **오프라인 표적 테스트** 1개 또는 최소: disabled 상태 실제 provider calls0 → stopped + 확인 → 활성화 설정 시에만 명시적 클릭으로 1회 실행 개시 → 모의 Gemini 통합 대본 생성/기획 버전 인수. 완료 혹은 차단 후 동일 API 반복 클릭 시 중복 송신 없음. reserved/uncertain/attempt>0 상태 재개 금지. 실제 호출 차단하는 fixture 사용. 기존 과거 동의서 28,841B HMAC+만료·계정/범위 계약 재검증은 유지. HTTP 실제 요청0회.
6. 범위 밖의 프롬프트/모델/조사/영상/음성/예산 수정, 전체 test suite 반복 금지. `reports/REWORK_ZERO_ATTEMPT_DISABLED_RECOVERY_RESULT_20261112.md` 짧은 보고: 원인/각 상태·회복 가능 여부/수정 파일/검증/실 API0회/사용자에게 다음 순서와 서버 환경 명령. 커밋/push 원격 확인.

## 중요
기존 시스템의 원 목적은 AI 관리자 재기획 → writer/editor 재작업 → 관리자 의미 검토 → 컷룸 대표 승인대기. 기존 승인·서명키·이전 대본/스토리보드·기록을 일절 덮거나 삭제하지 말 것. data/backups/artifacts/.env·미추적 파일 보존, git clean/reset --hard/force push 금지. KST. **활성화 상태 확인과 오프라인 코드 구현만** Codex가 수행하고 실제 Gemini API는 호출하지 말 것. 처리 완료 뒤 실제 사용자는 Codespaces에서 플래그 설정·서버 재시작·UI 명시 클릭 후 진행.
