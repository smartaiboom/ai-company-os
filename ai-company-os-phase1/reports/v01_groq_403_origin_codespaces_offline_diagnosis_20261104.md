# Groq 403 발생 계층과 Codespaces 요청 경로 — 오프라인 분석

2026-11-04 KST. `git pull --ff-only` 성공, main `03828e4` 반영. 핵심 원칙·AGENTS.md·한국어 규칙·지정 3개 선행 보고서·Groq adapter/진단/일회성 실행기·공유 HTTP transport·로컬 Python 3.14 표준 라이브러리 구현을 확인했다.

**결론: 합성 진단에서 HTTP 403을 수신한 사실은 확정이지만, 응답을 생성한 계층은 미확정이다.** 현재 환경에 명시적 프록시 변수는 없고 두 실제 경로는 동일한 기존 proxy 비자동탐지 guard를 사용한다. 이것만으로 Groq 애플리케이션 응답 또는 중간 보안 계층 응답이라고 확정할 수 없다. **이번 실제 AI API 요청·ping·GET/HEAD/OPTIONS/POST·approve/run/continue 0회, 비용 발생 작업 0회.** Git 통신과 공식 공개 문서 조회만 별도로 수행했다.

## 기존 기록이 증명하는 범위

| 기록 | 확인된 사실 | 사후 확인 불가 |
|---|---|---|
| 기존 실제 영상 프로젝트 | stopped/plan, 관리자 시도 1회, provider_rejected, failed/unvalidated 및 active_operation 보존 | 정확한 HTTP status·응답 source·과거 raw headers/body |
| 독립 합성 진단 | 2026-11-04 12:40:06 KST, POST 시도 1회, HTTP 403, permission/other, failed | Groq 앱/edge/중간 계층 중 발생 위치·peer TLS·응답 헤더 존재/값·원문 body |

합성 원장의 rate_limits={}는 **허용된 숫자 quota를 확보하지 못했다**는 뜻이며 모든 응답 헤더가 없었다는 뜻이 아니다. provider_code=other도 허용 코드가 없거나 추출되지 않았다는 뜻이지 Groq 앱까지 도달했다는 증거가 아니다. 기존 원장에 provenance/source 필드는 없었고 과거 응답을 복원하거나 새 플래그를 소급 저장하지 않았다.

사용자의 Playground 한국어 응답·Free 모델 한도·조직/Default Project 명시적 차단 없음·Last Used=Never·0 API Calls·No usage data·No logs found는 지시서에 전달된 사용자 관찰이다. Codex가 계정에 로그인해 재검증한 사실은 없다. Playground 정상은 웹 UI 경로의 성공이며 Codespaces 키 인증과 같지 않다. 표시된 키/조직/프로젝트와 실행 환경의 동일성, 로그 조회 범위/반영 시점도 이 자료만으로 확정되지 않는다. **masked suffix·키 값·키 hash를 출력·비교·추측하지 않았다.** 로그 부재는 중간 차단 가설의 단서지만 증명은 아니다.

## 비밀 없는 환경 정적 점검

점검 시각 `2026-11-04T13:03:50+09:00` KST. 환경변수 **이름과 존재 여부만** 확인했다. 값·프록시 URL/host/port/IP/인증 정보·계정 ID는 출력하거나 보고서에 복사하지 않았다.

| 이름 | 현재 프로세스에 존재 |
|---|---|
| HTTPS_PROXY / https_proxy | 둘 다 false |
| HTTP_PROXY / http_proxy | 둘 다 false |
| ALL_PROXY / all_proxy | 둘 다 false |
| NO_PROXY / no_proxy | 둘 다 false |
| REQUEST_METHOD | false |
| SSL_CERT_FILE / SSL_CERT_DIR | 둘 다 false |
| REQUESTS_CA_BUNDLE / CURL_CA_BUNDLE | 둘 다 false |
| CODESPACES | true (이름의 존재만) |

이는 **현재 프로세스** 관찰이며 과거 자식 실행 환경을 통째로 저장한 기록은 아니다. 다만 과거 두 실행도 동일 guard를 사용한 코드/실행 기록이 남아 있어, 해당 guard가 환경 proxy를 자동 선택하지 않는다는 결론은 별도로 성립한다. 현재 변수 부재만으로 투명 중계·라우팅·출구 정책·공급자 edge를 배제하지 않는다. 환경변수를 수정/해제하거나 네트워크 우회를 시도하지 않았다. 테스트의 합성 환경은 해당 테스트 프로세스에서만 잠시 적용 후 복원했다.

기본 urllib ProxyHandler는 scheme별 환경 proxy를 탐지하며 로컬 구현은 소문자 변수를 나중에 적용해 우선한다. CGI REQUEST_METHOD가 있으면 대문자 HTTP_PROXY를 무시한다. 그러나 **이 프로젝트는 기존부터 `ProxyHandler({})`를 명시**해 자동 탐지를 사용하지 않는다. NO_PROXY도 이 경로에서는 환경 proxy 선택에 영향을 주지 않는다. SDK/requests/httpx/curl 경로는 두 실제 송신에 사용하지 않았다. [Python urllib 문서](https://docs.python.org/3.14/library/urllib.request.html)

## 실제 전송 경로 추적

1. 첫 영상 실행: 정상 CLI → GroqCompany/FreeCompany → LiveCompany._call → 원장 선예약/transport_started → `GroqFreeAdapter.build_request` → `autonomous_live.urlopen`.
2. 별도 합성 실행: 고정 payload/account preflight → 독립 O_EXCL 선예약 → `run_once` → `GroqFreeAdapter.build_request` → imported `guarded_urlopen`.
3. 두 마지막 함수는 **동일한 `ai_safety.guarded_urlopen` 객체**임을 현재 런타임 identity로도 확인했다. 이 함수는 `build_opener(ProxyHandler({}), NoRedirect()).open(...)`을 사용한다. 전역 urllib opener나 SDK proxy 설정을 참조하는 코드가 아니다.
4. 로컬 stdlib 소스: build_opener는 명시한 ProxyHandler/NoRedirect를 우선해 기본 proxy/redirect handler를 대체한다. HTTPSHandler → http.client.HTTPSConnection → socket 연결/DNS → TLS hostname wrapping → HTTP request/getresponse로 이어진다. DNS 조회나 peer 접속은 이번에 수행하지 않았다.
5. TLS를 끄는 context는 전달하지 않는다. 로컬 기본 SSL context의 check_hostname=true, verify_mode=CERT_REQUIRED를 네트워크 없이 확인했다. 실제 과거 peer 인증서/검증 체인/출구 경로는 저장되지 않았으므로 TLS 기본값만으로 운영 origin을 증명하지 않는다.
6. HTTPErrorProcessor는 수신한 비2xx 응답을 HTTPError로 올린다. 일반 연결/DNS/TLS 실패는 OSError/URLError 계열이며 코드가 이를 403으로 만들어내지는 않는다. **합성 403은 수신 HTTP 상태**라는 범위까지 확인된다. HTTP endpoint 또는 TLS 신뢰 경로상의 중간 계층이 403을 반환해도 HTTPError 인터페이스만으로 생성자를 구별할 수 없다.
7. 첫 영상 요청의 HTTPError는 포괄 provider_rejected로 축약됐다. 이후 합성 진단은 HTTPError.code=403을 보존하고 자유 문자열/원문을 버렸다. category=permission은 숫자 403의 로컬 분류이며 Groq 인증 서버가 직접 내린 판정이라고 인증한 값이 아니다.

NoRedirect는 자동 재송신을 허용하지 않는다. 과거 redirect 여부는 별도 저장되지 않았고 이번에도 이를 추측하지 않는다. 기존 `guarded_urlopen`·TLS·proxy 정책은 **변경하지 않았다**. 환경 프록시를 새로 비활성화해 접속한 실험도 없다.

GitHub 공식 문서는 Codespaces의 격리된 네트워크와 일반적인 인터넷 아웃바운드 허용을 설명한다. 포트 포워딩의 공개/비공개 설정은 들어오는 개발 서버 연결에 관한 것으로, 이번 outbound API 403의 해결책이라고 볼 근거가 없다. 문서의 일반 설명이 이 세션의 실제 egress/edge 추적을 대신하지는 않는다. [GitHub Codespaces 보안](https://docs.github.com/en/codespaces/reference/security-in-github-codespaces)

## 가설별 판단

| 가설 | 현재 판단 |
|---|---|
| Groq 앱/모델 권한 거절 | 403과 양립하지만 provider_code=other로 정확한 제한 미확정. 웹 UI 성공만으로 배제 불가 |
| API 키가 웹 UI와 다른 조직/프로젝트에 연결됨 | key Last Used=Never/0 usage와도 양립하나 키 연결 동일성 근거 없음. suffix 비교/새 키 발급하지 않음 |
| 조직·프로젝트 정책 | 사용자에게 명시적 차단 없음이 보고됐지만 실제 키의 프로젝트/추가 정책까지 입증되지 않음 |
| 명시적 환경 proxy | 현재 변수 없음, 기존 guard는 자동 탐지 안 함. 이 코드의 환경 proxy 선택이 원인이라는 근거 없음 |
| Codespaces 출구·투명 중계·Groq edge/WAF | 여전히 가능성이나 historical header/TLS/edge trace 없음. 403과 앱 로그 부재만으로 확정 불가 |
| 요청 schema/옵션 | 앞선 공식 계약 분석에서 명백한 불일치 없음. 이번 403은 schema 400 증거가 아니며 실제 schema 수락도 미검증 |

따라서 **403을 발생시킨 origin을 확정하지 못했다.** proxy 존재/부재나 한 종류의 응답 헤더만으로 확정하는 분류도 만들지 않았다.

## 향후 응답에만 적용하는 최소 진단 보완

기존에는 source 단서가 전혀 남지 않았다. 향후 별도 승인된 요청에서 HTTP 계층 단서를 잃지 않도록 `groq_provider.response_source_hints`를 추가했다. 저장하는 것은 아래 고정 키/boolean/null/enum뿐이다.

- `header_presence`: server/via/www-authenticate/x-request-id/cf-ray/location/content-type 각각 존재 여부만.
- `redirect_status_observed`: 301/302/303/307/308이면 true, 다른 유효 상태면 false, status 불명이면 null. 304는 redirect로 표시하지 않는다. 이는 상태 관찰이며 redirect를 따라갔다는 뜻이 아니다.
- `origin_classification`: 항상 `unverified`. 헤더가 있어도 origin 인증으로 승격하지 않는다.

헤더 **값은 읽어 저장하지 않는다**. cf-ray/request-id 값·server/via/인증 문자열·Location URL·query·키·body는 출력/로그/Git에 포함하지 않는다. Via 존재는 중계 단서가 될 수 있고 request-id류 존재는 공급자 측 관측 가능성의 단서가 될 수 있지만, 둘 다 생성자 확정 증거는 아니다. timeout 등 응답을 받지 못한 경우 flags를 모두 false로 꾸며 쓰지 않고 source 필드를 생성하지 않는다.

변경 파일: `groq_provider.py`, `autonomous_groq.py`, `autonomous_free.py`, `synthetic_groq_compat_once.py`, `tests/test_groq_response_source.py`, 이 보고서. 공유 훅은 실제 HTTP status를 전달하고 Groq에만 새 metadata를 붙인다. OpenRouter 기본 훅은 no-op이며 기존 error_code·가격/계정/한도/중복/원장 보호는 유지한다. 소비된 일회성 실행기 원장이나 fingerprint/승인을 변경하지 않았고 그 실행기를 실행하지 않았다. 이 보완은 **미래 관찰 능력**이며 과거 origin을 밝혀냈다는 뜻이 아니다.

## 오프라인 검증과 보존

새 테스트는 모든 socket/DNS를 차단한다. 합성 프록시 환경 유무와 소문자 우선순위, getproxies 자동 탐지 미사용, fake HTTPSHandler의 has_proxy=false, NoRedirect, fake direct/proxy 403, 200 strict JSON, HTTPError, timeout, header 값/비밀정보 미저장 및 origin 미확정 유지가 핵심 검증이다. direct/proxy는 fixture 의도이며 코드가 이를 판별했다고 표현하지 않는다.

```bash
python -B -m unittest tests.test_groq_response_source tests.test_groq_error_diagnostics tests.test_synthetic_groq_compat_once tests.test_autonomous_groq tests.test_autonomous_free tests.test_autonomous_live
```

초기 집중 회귀 **71개 통과 (15.904초)**. redirect 판정에서 304를 명시적으로 제외한 뒤 동일 범위 **최종 71개 통과, 실패/오류 0, exit 0 (13.350초)**. 로그 `/tmp/groq-origin-focused-final-20261104.log`. 기존 fake Groq 협업→실제 로컬 mock MP4, OpenRouter free/legacy 경로도 포함한다. 합성 fixture를 실제 API 성공으로 취급하지 않는다. 최소 관련 회귀만 수행하고 전체 회귀는 반복하지 않았다.

실행 전 기존 데이터/backup/프로젝트·설정·서명 키·grant·mock MP4·사용자 미추적 파일·기존 계정 제안 **80개** SHA256 기준을 확보했다. 실행 후 80개 동일을 확인했다. 실제 원장/예약/실패/설정은 변경하지 않았다.

- Groq 프로젝트: 상태 hash `4fe0593cb0a1834a972fa42d31c54744ff5b64f619fbdfa57a4a9b514e01c0ca`, active_operation `5202abf79d95474091a7cb84fc84ecc3` 유지.
- `data/synthetic-groq-compat-once-20261104/operation.json`: 기존 failed/403/POST 1회 소진 기록 그대로. 새 response_source_hints 필드 없음, 소급 기록/표식 초기화/실행 없음.
- OpenRouter 실패 상태 hash `f28ebea41f84d1f08917acab1f6ae1e1c548a164e482710273828b7e5936e7b1` 유지. 수동 프로젝트·기존 백업/영상/사용자 자료도 보존.
- `git diff --check` 통과. 비밀정보 없는 코드·테스트·이 보고서만 선택적으로 Git에 반영한다. .env/Git secrets/provider 환경변수 변경 없음.

## 사용자에게 제안할 한 가지 확인

**Groq의 로그인된 지원 창에서 “2026-11-04 12:40:06 KST에 api.groq.com의 Chat Completions로 보낸 openai/gpt-oss-20b 합성 요청이 Groq edge/WAF에 도달해 403으로 차단됐는지”를 확인하는 것**이 가장 좁은 다음 관측 항목이다. 앱 로그/키 Last Used에 나타나지 않는다는 사실을 함께 전달할 수 있다. 비밀키·masked suffix·프록시 주소를 공유할 필요는 없다. Codex가 지원 메시지를 전송하거나 계정에 접근하지는 않았다.

이 확인은 계정/모델 차단과 edge/상위 경로를 구분할 근거를 얻기 위한 것이며, 새 키·결제·권한 전면 개방·보안 해제를 요구하는 것이 아니다. 이번에는 새 실전 계약이나 재송신 권한을 발행하지 않았다. 추후 추가 API 관찰이 필요하더라도 **새 명시 범위의 합성 POST 최대 1회**로 따로 승인하고 현재 소비된 원장/기존 실패 프로젝트는 그대로 보존해야 한다. 현재 작업으로 실제 전송을 허용하지 않는다.

이번 결과는 목표→AI 자율 협업→최종 산출물 앞의 403 차단을 어느 계층까지 확인했는지 구분하고 다음 관측을 좁혔다. 실제 관리자·직원 협업/MP4 완주는 아직 미완료다. 새 중간 업무 결재를 추가하지 않았고 기존 수동 승인 부채·실패 복구는 남아 있다. UI/대시보드·영상 디자인 작업은 하지 않았다.
