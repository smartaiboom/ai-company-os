# AI Company OS — 사용자가 승인한 Groq 합성 API 호환성 진단 1회

작성일: 2026-11-04 KST

## 명시적 사용자 승인 — 정확한 원문

> Groq 무료 API 호환성 진단 1회를 승인해. 모델은 openai/gpt-oss-20b, 요청은 보고서의 canonical SHA256 5886294a7a7e81271ebca9f67f25118cec3468b866b3c0eb5463f391a2c9367a에 해당하는 합성 메시지와 JSON Schema로 제한하고, 실제 POST 최대 1회, 출력 512토큰 이하, timeout 최대 60초로 해. Free 플랜과 계정 확인 유효기간을 검증하고 유료 전환·fallback·재시도·기존 프로젝트 재실행은 금지해. 안전한 일회성 실행기를 오프라인 검증한 뒤 Codex가 실제 진단을 수행하도록 GitHub 작업 지시서를 만들어 줘.

위 승인은 **이 합성 진단의 특정 HTTP POST 최대 1회**에 한정된다. 종전 실사용 Groq/ OpenRouter 프로젝트의 재실행·실패 operation 복구·새 AI 회사 프로젝트 run·다른 모델/공급자 호출·유료 API·추가 POST는 승인된 것이 아니다. 반드시 사전 오프라인 안전 검증 완료 후에만 실제 호출.

## 필독 및 근거

- `AI_COMPANY_OS_CORE_PRINCIPLES.md`, `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`
- `reports/v01_groq_provider_rejected_diagnostics_20261104.md`
- `reports/v01_groq_real_autonomous_video_first_run_20261104.md`
- 현재 Groq adapter/transport 및 무료 계정 계약·진단·원장 코드
- Groq 공식 오류/요청/구조화 출력 문서는 필요시 공개 문서 조회 가능하나, 개발 중 외부 API 실험은 금지.

## 승인된 고정 요청

- 고정 POST URL: `https://api.groq.com/openai/v1/chat/completions`
- 인증: Codespaces `GROQ_API_KEY`만 사용. 키 값·prefix·길이·원문 hash·인증 헤더를 출력/로그/Git에 남기지 않는다.
- 모델 `openai/gpt-oss-20b`; 다른 모델 전환 및 fallback 금지.
- 최대 실제 POST **1회**(timeout·HTTP 429·400·401·403 등 어떤 경우에도 두 번째 송신 없음).
- `max_completion_tokens=512`, `reasoning_effort=low`, 요청 전체 timeout 최대 **60초**.
- **정확한 synthetic JSON 본문**을 아래에 고정하고, UTF-8 canonical JSON (기존 보고서가 사용한 canonical 함수/정규화 규칙) SHA256이 `5886294a7a7e81271ebca9f67f25118cec3468b866b3c0eb5463f391a2c9367a`와 일치할 때만 실행한다. 조금이라도 다르면 임의 수정/해시 재계산으로 허가를 확장하지 말고 실제 호출 없이 보고한다. 차후 공식 SDK가 요청 필드를 덧붙이거나 변경하는 방식도 막고, 전송되는 JSON bytes와 승인된 canonical 내용이 일치하는지 확인한다.

```json
{
  "model": "openai/gpt-oss-20b",
  "messages": [
    {"role":"system","content":"Return only JSON matching the supplied schema."},
    {"role":"user","content":"Return result.status ready. This is a synthetic API compatibility check."}
  ],
  "max_completion_tokens": 512,
  "reasoning_effort": "low",
  "response_format": {
    "type":"json_schema",
    "json_schema": {
      "name":"groq_compat_v1", "strict":true,
      "schema": {
        "type":"object",
        "properties":{"result":{"anyOf":[
          {"type":"object","properties":{"status":{"type":"string","enum":["ready"]}},"required":["status"],"additionalProperties":false},
          {"type":"object","properties":{"status":{"type":"string","enum":["stop"]},"reason":{"type":"string"}},"required":["status","reason"],"additionalProperties":false}
        ]}},
        "required":["result"], "additionalProperties":false
      }
    }
  }
}
```

**주의:** 위 JSON의 키 순서/공백이 보고서 canonical digest와 다를 수 있다. 보고서 내 기대 hash를 실제 canonicalizer로 검증하고, 불일치시 실행 중단 후 그 원인을 보고하라. 사용자 승인 없이 다른 payload로 바꾸지 않는다.

## 계정/유효 기간/비용
- 사용자 화면 확인: Groq Free 플랜($0 Current Plan), Developer 미활성, 지정 모델 Free 계정 조직 한도 30 RPM/1000 RPD/8000 TPM/200000 TPD. 이는 실제 잔여량을 보장하지 않는다. **기존 계정 확인 유효 종료 `2026-11-05T11:35:43+09:00` KST**. 지금 확인 시각이 이보다 같거나 늦으면 송신 0회. Codespaces 실제 시간대가 불명확해도 송신 0회.
- 실행 직전에도 유효한 Free/유료 미활성 조건·GROQ_API_KEY 존재와 정당한 사용권한·계정 조건 변경 없음이 확인되어야 한다. 별도 결제/유료 전환/유료 자동 fallback/계정 대체는 허용되지 않는다.
- Groq free account를 실시간 서버에서 검증할 수 없으면 서버 검증했다고 주장하지 않는다. 비정상 비용 징후나 계정/모델 불일치는 fail closed. 응답의 cost 필드 부재를 0원 검증으로 둔갑시키지 않는다.

## 안전한 일회성 독립 진단 실행기 구현
1. Codex는 **기존 실패 Groq 프로젝트를 읽기만** 하고 해당 프로젝트의 CLI `approve`/`run`/`continue` 또는 과거 동의를 사용하지 않는다. `groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e`의 `stopped/plan`, 기존 failed attempt, active_operation `5202abf79d95474091a7cb84fc84ecc3` 및 상태 hash `4fe0593cb0a1834a972fa42d31c54744ff5b64f619fbdfa57a4a9b514e01c0ca` 보존. OpenRouter 실패 원장 및 다른 프로젝트/backup/mock MP4도 변경·삭제하지 않는다.
2. 최소한의 독립 `synthetic_groq_compat_once` 실행 도구를 새 파일로 구현해 **고정 요청 외 외부 요청을 절대 하지 못하게** 한다. 승인된 operation fingerprint(고정 endpoint/model/payload SHA/유효기간/POST=1/tokens/timeouts/사용자 승인 문구 식별)를 코드에 결합한다. 그 fingerprint는 새 로컬 진단 전용 원장 및 실행 전 **원자적 O_EXCL 선예약**으로 기록한다. 시도/송신 시작/수신 완료/정지/확정 결과 상태를 KST로 남긴다. 같은 명령을 또 실행해도 **POST 0회**로 차단. 예약 후 크래시, timeout, 불분명한 수신 결과에서도 자동 재송신·표식 초기화·새 프로젝트 우회 금지. 파일 존재 확인과 예약 사이의 경쟁을 막고, 실제 Codespaces/프로젝트 내 유일한 경로를 사용. 동일 지시서 재실행, 프로세스 충돌, 별도 계정·디렉터리 변형으로 재시도하지 않는다.
3. **오프라인 먼저:** mock HTTPS 또는 fake transport에 정확한 요청을 최대 1회 전송하며, 정상 200/finish_reason stop/JSON Schema 검증, 400/401/403/404/422/429/5xx, timeout, 성공 응답 거절, 토큰 한도와 중복 시도/크래시 선예약/외부 DNS 차단을 검사한다. 실사용 키가 아닌 합성 키로 테스트한다. 필요 없는 전체 architecture 재작성 금지.
4. 실제 송신 직전: 사용자 승인을 작업 지시서로 확인; 실시간 KST·계정 조건/Free status 유효·키 존재 확인; 요청 canonical digest·고정 POST URL/모델·payload bytes·토큰·timeout·**미실행/중복 표식 없음** 확인. 오류가 하나라도 있으면 실제 송신 없이 안전하게 보고.
5. 조건을 모두 만족할 경우 **실제 Groq POST 정확히 최대 1회**만 수행한다. 전송 내용은 위 합성 system/user messages + JSON schema뿐이다. 프로젝트 목표/기존 문서/대본·직원 결과/계정 개인정보를 API 모델 콘텐츠에 포함하면 안 된다. 인증키는 인증 헤더에만 사용.
6. 결과는 제한된 비밀정보 없는 진단만 남긴다: 수신 HTTP 숫자 status, 유한 category/허용된 provider code, 허용된 숫자 quota 헤더, 정상 응답의 finish_reason·usage token 정수·content JSON이 strict schema를 통과했는지, 결과 status ready/stop 등 **최소 구조적 판정**. raw error body/message/content/authorization/header 원문/키/전체 URL query 등을 저장·출력/Git 커밋 금지. 오류 status를 모르면 미확정이라고 정확히 기록. 정상 200 응답이라도 schema 실패/finish 비정상이면 성공 아님.
7. 이 진단은 무료 API 연결 적합성만 확인한다. **AI 관리자 계획 생성, 실제 직원 협업, 영상 MP4 성공을 주장하지 않는다.** 전체 실제 협업 다음 실행은 새 동의와 별도 운영 범위가 필요.
8. 개발 전후 기존 사용자 data/backup/설정/실사용 실패 원장 SHA를 대조. 신규 독립 진단 로그/선예약 원본, API 키/비밀 결합 값은 Git에 넣지 않음. 코드/테스트/검토된 결과 보고서만 선택적 commit/push. Git reset/clean/force push 금지.

## 한국어 보고
`reports/v01_groq_synthetic_compat_one_post_20261104.md`에 KST로 다음을 반드시 기록:
- 정확한 요청 SHA, 테스트 전에 승인 검증 여부, 계정 유효기간, 실제 POST 횟수(0 또는 1), 이외 API 요청 0회.
- 실제 HTTP status 및 안전한 error category/provider code 또는 미확정 사유, 200일 때 finish/strict-schema 판정, token/quotas가 관찰된 경우에만.
- auth/모델 접근/구조화 JSON 호환성에서 확정할 수 있는 점과 없는 점을 구분.
- 독립 원장 선예약과 재실행 차단 확인, 중복·timeout 위험 처리.
- 기존 사용자 데이터 0변경, Codex 실행 코드와 테스트 결과, 실제 무료 API 통신 성공/실패 판단.
- 뒤이어 자율 MP4 사이클을 위한 **실무적으로 최소한의 다음 단계** 제안. 대시보드·영상 디자인 고도화 금지.

## 최종 완료 기준
동일 사용자의 **정확한 합성 진단 요청 한 건**을 승인 조건·유효기간 충족 시 실제 Groq에 단 한 번 전송하여 원인을 식별하거나, 조건 불충족으로 **실제 송신 0회**를 기록한다. 어떠한 경우에도 기존 실패 원장 초기화/재전송 금지, 유료 사용·fallback 금지. 오프라인 테스트 통과 수를 실사용 성공으로 포장하지 않는다.
