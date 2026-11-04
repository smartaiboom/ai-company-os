# Gemini 실패 오프라인 분석 및 미래 예외 분류 개선

2026-11-04 KST. `git pull --ff-only`로 e319735 반영. 핵심 원칙, AGENTS.md, 한국어 규칙, 지정 지시서, 이전 Gemini 보고서/실행기/테스트, ai_safety.py 및 Groq 오프라인 진단 보고서를 확인했다.

**과거 실패 원인은 미확정이다.** 이전 코드가 예상 밖 로컬 예외까지 `network`로 축약했고 예외 타입·발생 단계를 남기지 않았다. 원장이 증명하는 것은 2026-11-04 13:30:59 KST에 시도 1회가 소진됐으며 HTTP status가 null이라는 사실이다. 서버 도달 여부, 인증 결과, DNS/방화벽/프록시/TLS 원인은 사후 복원할 수 없다. 이전 보고서의 `network`는 통신 오류 확정 증거가 아니라 당시 코드의 고정 분류다.

이번 실제 AI API 호출 **0회**, 재시도 0회, 외부 HTTPS/DNS/curl/ping/healthz/모델 목록 조회 0회. Git pull/push/원격 확인만 저장소 전달에 사용한다. live 실행기는 실행하지 않았다. 새 승인/operation/공급자/모델/키/결제 설정은 만들거나 변경하지 않았다.

## 단계별 기존 예외 귀속과 한계

| 단계 | 가능한 예외 예시 | 기존 처리 |
|---|---|---|
| 키 조회·timer 사전 검사 | ValueError, AttributeError, OSError | run_once 내부 try 밖. CLI는 ValueError/OSError만 고정 차단 안내 |
| Request 생성·JSON 인코딩 | ValueError, TypeError, UnicodeError | 내부 try 밖. 일부는 CLI 고정 차단, 나머지는 미포착 |
| 원장 mkdir/O_EXCL/쓰기/fsync | FileExistsError, PermissionError 등 OSError | 내부 try 밖. CLI 고정 차단. 선예약이 생긴 뒤 실패해도 소진 파일 보존 |
| signal handler 설치 | ValueError, OSError | 내부 try 밖. CLI 고정 차단 |
| 실시간 타이머 시작 | OSError, 예상 밖 Exception | OSError까지 `network`로 오분류 가능 |
| urllib 열기·DNS/socket/TLS | URLError, gaierror, SSLError, ConnectionError, RemoteDisconnected, HTTPError | HTTPError만 HTTP status/분류, 직접 TimeoutError는 timeout, 나머지는 network |
| 응답 상태·read·context 종료 | TimeoutError, OSError, HTTPException, AttributeError | 직접 timeout은 timeout, ValueError/TypeError는 other, 나머지는 network |
| JSON parse | JSONDecodeError, UnicodeDecodeError | ValueError 계열이므로 other |
| 답변·usage 검증 | ValueError/KeyError/IndexError/TypeError/AttributeError | 앞 네 가지는 other, AttributeError는 network로 오분류 |
| 타이머 해제·handler 복원 | OSError, ValueError | finally 예외가 앞 진단을 덮고 CLI로 전달될 수 있음 |
| 최종 원장 저장 | OSError, TypeError | 내부 try 밖. OSError는 CLI 고정 차단. 기존 예약은 여전히 소진 |

HTTPError는 URLError의 하위 클래스지만 실제 HTTP 상태를 갖는 별도 분기다. URLError.reason은 예외 객체 또는 자유 문자열일 수 있다. socket.timeout은 이 환경에서 TimeoutError의 별칭이다. SSLError는 OSError 계열, ConnectionError도 OSError 계열이며 RemoteDisconnected는 ConnectionResetError와 HTTPException 양쪽을 상속한다. 따라서 구체 타입을 먼저 검사해야 한다. HTTP 403 수신은 응답 상태 관찰이며 응답 생성자가 공급자 origin임을 증명하지 않는다. HTTP status 부재도 서버가 요청을 처리하지 않았다는 증거는 아니다.

## 최소 수정

변경 파일: `gemini_connection_once.py`, `tests/test_gemini_connection_once.py`, 이 보고서.

미래 실행의 기존 보호 try 범위에 고정 단계 `timer_setup/transport_open/response_read/json_parse/response_validate`를 추가하고 `error_stage`에 기록한다. 타입 기반 고정 분류는 dns_error/tls_error/connect_timeout/read_timeout/connection_reset/remote_disconnected/connection_error/transport_error/local_unexpected_error/parse_error/invalid_response/timeout 및 기존 숫자 HTTP 분류다. 타이머가 발생시킨 전체 제한은 WallTimeout으로 구별한다. connect_timeout은 open 단계에서 발생한 timeout이라는 의미이며 TCP 연결 이전인지 TLS/응답 대기 중인지는 구별하지 못한다.

문자열 URLError.reason은 읽어 해석하거나 저장하지 않는다. 예외 이름도 동적 기록하지 않으며 `str/repr`, 원문 errno 메시지, body/header, URL query, proxy host/IP/프로젝트 식별정보를 진단에 기록하지 않는다. HTTP status는 HTTPError 또는 실제 response 상태 관찰에서만 설정한다. HTTP 200 뒤 JSON 오류면 상태 200을 유지하며 실패 단계는 parse로 남긴다. 검증 중 뒤늦은 실패는 success를 false로 돌리고 부분 인사/토큰을 제거한다.

원장 예약·Request 생성 등 try 이전 실패와 최종 원장 저장 실패는 기존 CLI 차단 경계를 유지한다. 이들에 새 영속 진단을 기록하지 않으며 성공했다고 표현하지 않는다. timer cleanup은 해제가 실패해도 기존 signal handler 복원을 시도한다. ledger_save/timer_cleanup은 분류 함수에서 로컬 오류로만 허용하고 전송 오류로 분류하지 않는다. 원장 자체를 쓸 수 없는 경우 진단 저장도 보장할 수 없다. 명백한 통신 설정 버그나 과거 실패 원인을 재현한 것은 아니며, 이번 변경의 성과는 미래 진단 정확화다.

O_EXCL 1회 보호, endpoint/인사 payload, 인증 헤더, 30초 제한/8KiB 응답 상한, 기본 TLS/proxy, redirect/retry 차단은 유지한다. 과거 소진 원장에 새 분류를 소급 기록하지 않았다.

## 네트워크 없는 정적 환경 관찰

HTTP_PROXY/http_proxy/HTTPS_PROXY/https_proxy/ALL_PROXY/all_proxy/NO_PROXY/no_proxy/SSL_CERT_FILE/SSL_CERT_DIR 이름의 존재 여부는 모두 false였다. 값은 출력하지 않았다. `urllib.request.getproxies()`의 허용 scheme http/https/all/no 선택 목록은 비어 있었다. 기본 SSL context는 hostname 검증 true, CERT_REQUIRED였다. DNS·socket 접속 없이 로컬 설정만 읽었다.

Gemini는 `build_opener(NoRedirect())`로 기본 환경 proxy 탐지를 유지한다. Groq 기존 guard는 `ProxyHandler({})`로 환경 proxy 자동 탐지를 사용하지 않는다. 양쪽 모두 TLS 검증을 끄지 않고 redirect를 차단한다. 현재 명시적 proxy 변수가 없다는 사실이 과거 환경 동일성이나 투명 중계 부재를 증명하지 않는다. 이번 작업은 proxy/TLS 정책을 변경하지 않았다.

Groq에는 HTTP 403 관찰이 있지만 Gemini에는 HTTP 상태가 없다. 서로 실패 계층이 같다고 주장할 근거가 없으며 GitHub 통신 성공은 Gemini 접속 성공을 의미하지 않는다.

## 검증 및 보존

`python -B -m unittest tests.test_gemini_connection_once tests.test_synthetic_groq_compat_once tests.test_groq_response_source`

- 초기 18개 중 1개 실패: RemoteDisconnected의 다중 상속으로 connection_reset이 먼저 매칭됐다. 검사 순서를 수정했다.
- 최종 **18개 통과**, 실패/오류 0 (0.598초, exit 0).
- Gemini fixtures는 socket connect/create_connection 및 DNS getaddrinfo를 차단한다. fake 200/401/403/429/302/timeout과 DNS/SSL/연결 단절/일반 OSError/예상 밖 로컬 오류/JSON/답변 검증/읽기 timeout/타이머 설치 실패를 주입했다. 비밀을 포함한 예외 메시지가 반환값·임시 원장에 없고 중복 실행이 차단됨을 확인했다.
- `git diff --check` 통과. 전체 제품 회귀는 실행하지 않았다.
- 기존 data/backups/checkpoints에서 발견한 74개 파일의 전후 SHA256 모두 동일. Gemini 소진 1회·status null·network 기록, Groq/OpenRouter 실패 및 예약·백업을 보존했다. 기존 사용자 미추적 파일은 변경하지 않았다. 테스트는 임시 경로와 가짜 키만 사용한다.

## 다음 액션과 제품 개발 위치

사용자에게 제안하는 다음 액션은 **추후 단일 합성 연결 관찰이 필요할 때, 개선된 진단을 적용한 새 1회 범위를 명시적으로 승인하는 것** 한 가지다. 현재 소진 원장은 재사용하지 않으며 이번 작업으로 추가 호출을 허용하지 않는다.

자율 회사 경로에는 관리자 계획→직원 실행→내부 검토와 로컬 도구/MP4 산출물 확인 구조가 있지만 실제 공급자 성공이 검증되지 않아 실사용 한 사이클은 미완료다. Gemini 인사 실행기는 회사 adapter·동의·비용 정책·협업 원장과 연결되지 않은 독립 진단이다. Groq 실패 operation도 임의 해제할 수 없다. 실제 직원 출력의 도구 입력 계약과 MP4 렌더링·관리자 최종 검토까지 실제 AI로 검증해야 한다. 이번에는 외부 호출 없이 그 성공을 주장하지 않는다.

목표→AI 자율 협업→최종 산출물 앞의 잘못된 통신 분류를 줄여 다음 관찰의 정확도를 높였다. 업무별 계획/결과/품질 승인 등 기존 수동 흐름의 부채는 이 범위에서 변경하지 않았으며 새 중간 업무 결재는 추가하지 않았다. 새 호출 동의는 업무 판단 승인과 구별되는 외부 전송 안전 경계다.
