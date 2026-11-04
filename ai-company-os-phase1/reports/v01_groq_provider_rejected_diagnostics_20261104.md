# Groq 거절 원인 구분을 위한 최소 진단 보완

2026-11-04 KST. `git pull --ff-only`로 main `683eecf` 반영. 핵심 원칙·AGENTS.md·한국어 규칙·지정 실제 실행/통합/응답 복구 보고서 및 adapter·wire/schema·실제 transport·예외 변환 경로를 조사했다. **이번 실제 Groq/OpenRouter/Gemini API 요청·ping·호환성 호출 0회, 실제 approve/run/continue 0회, 유료 사용 0회다.** Git 통신과 공식 공개 문서 조회, 테스트 전용 loopback 통신은 별개로 수행했다.

## 확정 사실과 이번 변경의 범위

과거 Groq 첫 실사용은 관리자 plan 송신 시도 1회 후 `provider_rejected`로 정지했다. 당시 원장에는 정확한 HTTP 상태/공급자 오류 코드/본문이 없으므로 **과거의 원인을 지금 복원할 수 없다.** 스키마 400·인증 401·권한 403 등으로 단정하지 않는다. 원본 원장이나 상태에 새 진단을 소급 기록하지 않았다.

앞으로 발생하는 Groq 오류에 다음 제한된 필드를 실패 attempt의 `provider_error_diagnostics`로 추가한다.

```json
{"http_status":400,"category":"invalid_json_schema","provider_code":"invalid_json_schema"}
```

위 값은 오프라인 합성 예시이며 실제 과거 응답이 아니다. `http_status`는 실제 수신한 정수 100~599만 저장하고 bool/문자열/범위 밖 값은 null로 처리한다. HTTP 오류는 HTTPError.code, 정상 응답 안의 error envelope는 실제 response.status를 사용한다. status를 읽을 수 없으면 200을 가정하지 않는다.

| 상태/증거 | 안전 범주 |
|---|---|
| 400 | invalid_request |
| 401 / 403 | authentication / permission |
| 402 / 404 | quota_or_billing / model_or_resource_not_found |
| 413 / 422 | request_too_large / request_validation |
| 429 / 500~599 | rate_limit / server_error |
| 기타 유효 HTTP 상태 | http_error |
| timeout / URL 연결 실패 | timeout / connection_error (status=null) |
| 정상 응답의 error envelope | provider_error 또는 허용 코드 기반 세분화 |

정확히 일치하는 코드만 허용한다: `invalid_api_key`, `model_not_found`, `model_permission_blocked`, `invalid_json_schema`, `json_validate_failed`, `unsupported_parameter`, `context_length_exceeded`, `rate_limit_exceeded`. 그 밖의 값·누락·잘못된 타입은 `other`다. 이 목록은 제한된 앱 진단 vocabulary이며 Groq의 전체 코드 목록이나 모든 모델의 동일 코드 제공을 보장하지 않는다. 400/422 및 error envelope는 허용 코드로 JSON schema/지원 불가 parameter/token 제한 등을 세분화할 수 있다. 인증·서버 상태에 모순되는 코드가 있어도 해당 HTTP 상태 범주를 우선한다. 400에 허용 코드가 없고 message만 있으면 invalid_request/other까지만 구분하며 원문으로 원인을 추측하지 않는다.

## 실제 변경 파일과 보안/호환성

- `groq_provider.py`: 순수 진단 함수 추가. HTTP 오류 body에서 **최대 8,193 bytes를 메모리로만 읽고 8,192 bytes 이하일 때만** 중복 필드를 거부하는 JSON 파서로 error.code 하나를 추출한다. oversized/비JSON/중복 필드/읽기 예외면 code=other다. body/message/type/param/failed_generation/URL/headers 원문/키 또는 해시는 저장하거나 출력하지 않는다. 읽기/파싱 실패가 원래 요청 실패를 덮거나 재시도를 허용하지 않는다.
- `autonomous_free.py`: 기존 error envelope/예외 경로에 기본 no-op 진단 훅 및 실제 response.status 전달만 추가했다. 기존 failed error_code, 원장 선예약·active_operation·가격·동의·중복·실패 정지 인터페이스는 유지한다. OpenRouter의 동작과 과거 저장 형식은 바꾸지 않았다.
- `autonomous_groq.py`: Groq에만 새 진단 훅을 적용한다. 기존 `numeric_rate_headers`는 이미 수신된 헤더의 허용된 숫자 quota/Retry-After만 저장하며, 헤더를 얻기 위한 별도 요청은 없다. 키·계정 attestation·고정 모델/endpoint·무료 계약 보호는 그대로다.
- `tests/test_groq_error_diagnostics.py`: socket/DNS 차단·합성 키/동의·임시 store·가짜 HTTPS를 사용한 진단/비밀정보 미저장/재전송 차단 검증을 추가했다.
- 이 보고서. 다른 제품 코드·UI·공급자·복구 실행기는 추가하지 않았다.

HTTP 거절은 기존 error_code(`provider_rejected` 등)를 유지한다. 네트워크 실패도 기존 `free_request_failed` 인터페이스를 유지하면서 새 범주만 덧붙인다. HTTP 200 error envelope를 성공/무료 비용 확인으로 승격하지 않는다. 실패 원장은 여전히 failed/unvalidated이며 자동 retry/fallback/continue 경로를 열지 않는다. 기존 legacy OpenRouter 요청 함수 자체에는 변경이 없다.

## 공식 요청 계약 확인

공식 Groq API reference에서 고정 Chat Completions POST URL, `max_completion_tokens`, GPT-OSS 20B의 `reasoning_effort=low`를 확인했다. 현재 4,096 출력 토큰 한도와 필드 사용에서 명백한 불일치를 찾지 못했다. 지원하지 않는 reasoning 값은 400이 될 수 있으나 이번 값은 허용 범위다. [Groq API reference](https://console.groq.com/docs/api-reference)

Groq Structured Outputs 문서는 20B의 strict 지원, object의 모든 property required·additionalProperties=false, nullable union 및 중첩 anyOf를 설명한다. 현행 schema는 최상위 object/result, result 내부 anyOf 및 닫힌 object 구조로 이에 부합한다. stream/tool-use 옵션도 전송하지 않는다. 따라서 **근거 없이 strict를 끄거나 anyOf를 제거하거나 파서를 완화하지 않았다.** 문서상 적합은 과거 요청이 서버에 수락됐다는 증거가 아니며 실제 조합의 수락 여부는 별도 실전 호환성 시험이 필요하다. [Groq Structured Outputs](https://console.groq.com/docs/structured-outputs)

공식 오류 문서의 HTTP 상태별 의미와 error object의 message/type 구조를 확인했다. 문서가 모든 오류에 구체적 code를 보장하지 않으므로 코드 없는 응답은 status 범주만 남긴다. 임의 message를 로그로 복사하지 않는다. [Groq 오류 문서](https://console.groq.com/docs/errors)

요청 옵션·schema의 명백한 계약 오류를 입증하지 못했으므로 production 요청은 변경하지 않았다. 공식 문서 조회는 로그인/계정·키 확인이나 실제 AI 송신이 아니다.

## 오프라인 검증

새 테스트는 fake HTTP 400(schema/unsupported parameter), 401/403/404/413/422/429/500/502/503, timeout/URL 래핑 timeout/connection error, 200 error envelope, 비JSON·중복·과대 body·읽기 실패·잘못된 status·모순 코드를 검사한다. 합성 키와 private sentinel이 저장 파일에 남지 않고 실패 후 run/continue가 재송신하지 않는지 확인했다. 정상 200 strict JSON·abnormal finish·provider refusal·cost 오류·가짜 협업→실물 로컬 MP4는 기존 Groq 테스트와 함께 검증했다.

1. 첫 집중 회귀: 75개 중 새 error-envelope fixture의 반환값 누락으로 오류 1건. 제품 실패가 아닌 테스트 구성 오류였으며 return을 추가해 수정했다.
2. `python -B -m unittest tests.test_groq_error_diagnostics`: **5개 통과**, 오류 0, 1.970초.
3. 최종 집중 회귀 명령:

```bash
python -B -m unittest tests.test_groq_error_diagnostics tests.test_autonomous_groq tests.test_provider_response_recovery tests.test_autonomous_free tests.test_autonomous_live tests.test_local_artifacts
```

**75개 통과, 실패/오류 0, exit 0, 22.230초.** 로그 `/tmp/groq-diagnostics-focused-20261104.log`. 기존 fake Groq→실제 로컬 MP4와 OpenRouter free/legacy 회귀 포함. 모의 모델 콘텐츠/MP4를 실사용 성공으로 표현하지 않는다.

4. `python -B -m unittest discover -s tests`: **617개 실행, 616개 통과·1개 건너뜀, 실패/오류 0, exit 0, 91.494초**. 로그 `/tmp/groq-diagnostics-full-20261104.log`. 기존 테스트 전용 loopback 서버 권한을 허용받아 실행했으며 실제 공급자 API 테스트가 아니다. `git diff --check` 통과.

## 원본 데이터 보존

실행 전 데이터/프로젝트·백업·설정·사용자 미추적 작업 파일·/tmp 승인 대상 제안 **79개**의 SHA256 기준을 확보했다. 비교 결과 79개 모두 동일이며 기존 프로젝트·grant·active_operation·서명 키·영상·계정 설정에 변경이 없다. 테스트는 임시 store만 사용했다.

- Groq `groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e`: stopped/plan, 시도 1건, 상태 hash `4fe0593cb0a1834a972fa42d31c54744ff5b64f619fbdfa57a4a9b514e01c0ca`, active_operation `5202abf79d95474091a7cb84fc84ecc3` 유지. 과거 attempt에 새 provider_error_diagnostics 없음.
- OpenRouter `freecompany-ae4aa334511d470c8c517685e9902a53`: 상태 hash `f28ebea41f84d1f08917acab1f6ae1e1c548a164e482710273828b7e5936e7b1` 유지.
- 수동 `cb44b605b498`, `c85d9853906a`와 기존 승인·서명 키·backup·mock MP4·사용자 파일은 hash 기준으로 보존했다. .env/키 변경 없음. 실제 승인·재송신·신규 실사용 프로젝트 생성 없음.

## 다음 한 번의 실제 호환성 시험을 위한 승인 자료 (미실행)

풀 자율 run은 계획·업무 검증·로컬 도구까지 변수가 많다. 먼저 합성 텍스트의 작은 strict JSON 요청 하나로 인증/모델 접근/요청 옵션/중첩 anyOf 수락 여부를 확인하면 다음 수정 범위를 좁힐 수 있다. 이 시험은 전체 역할 schema나 AI 협업 품질을 입증하지는 않는다. 실패한 과거 요청의 재시도나 승인 재사용으로 처리하지 않는다.

제안 범위: **별도 합성 호환성 operation 한 건, 최대 실제 POST 1회**, 공급자 Groq·`openai/gpt-oss-20b`·고정 `https://api.groq.com/openai/v1/chat/completions`, 기존 GROQ_API_KEY만 인증에 사용. 현재 Free 플랜/유료 미활성/키 결합의 유효성을 먼저 확인하고 불확실하면 송신 0회로 정지한다. 기존 계정 확인 유효기한인 **2026-11-05T11:35:43+09:00 KST 이전**으로 제한하며, 이후에는 계정 조건을 다시 확인하고 승인 자료도 갱신한다. 유료 업그레이드/fallback·계정 변경 금지. 아래 고정 합성 messages/schema/옵션만 전송하며 기존 프로젝트 목표·파일·실패 원장·원본 영상·계정 개인정보는 전송하지 않는다.

정확한 JSON 요청안(아직 실행기가 아닌 검토 자료):

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

위 요청 JSON의 canonical SHA256: `5886294a7a7e81271ebca9f67f25118cec3468b866b3c0eb5463f391a2c9367a`. 이는 요청 내용 식별자이며 서명된 운영 계약이나 실행 허가가 아니다.

다음 한 번의 명시 승인에 사용할 문안:

> 위 canonical 요청 hash의 합성 Groq 무료 호환성 시험을 승인한다. 고정 openai/gpt-oss-20b·고정 HTTPS·제시된 합성 messages/schema만 전송하며 실제 추가 POST는 최대 1회, 출력 최대 512토큰, timeout 최대 60초로 제한한다. 현재 Free 플랜과 유료 과금 미활성 및 2026-11-05 11:35:43 KST 이전 유효성을 재검증하고, 실패/시간 불명확/계약 불일치면 정지한다. 유료·fallback·재시도·기존 실패 프로젝트 승인/run/continue 재사용은 금지한다. HTTP 상태와 제한된 오류 범주/허용 코드·숫자 quota·정상 응답의 finish/토큰/로컬 schema 검증 결과만 관찰한다.

이는 **향후 승인 검토 자료이며 이번 작업에서 승인받거나 실행하지 않았다.** 실제 수행 전에는 위 내용과 만료·요청 hash에 결합한 별도 operation/한도 소비 기록을 갖춘 일회성 실행 도구를 오프라인 검증해야 한다. 새 프로젝트로 기존 실패 업무를 복제하는 방식이 아닌 독립 합성 진단이다. body/키/임의 오류 메시지는 출력/로그로 남기지 않고, 기존 guarded HTTPS·무료 조건·선예약·중복 방지를 적용해 결과가 불확실해도 소비를 복구하거나 다시 보내지 않는다. 기존 프로젝트의 실패 원장/active_operation/승인은 그대로 둔다. 이 승인 하나가 영상 자율 운영 재개까지 허용하는 것은 아니다.

이번 변경은 목표→실제 AI 협업→최종 산출물 경로에서 첫 공급자 거절의 기술적 원인을 다음에 구분할 근거를 추가했다. 실제 협업·MP4 완주 자체는 아직 미완료다. 업무 계획/직원 결과/품질 판단의 반복 사용자 승인은 추가하지 않았고, 기존 수동 경로의 승인 부채와 별도 실패 복구는 남아 있다. 다음 합성 시험의 최초 전송 동의는 운영 안전 경계다. UI/대시보드 작업은 하지 않았다.
