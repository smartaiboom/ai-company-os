# Groq 전송 비교와 재개 조건

2026-11-25 KST · GitHub main `edc8986`에서 시작했다.

대표는 일반 WSL 터미널에서 동일 `.env`를 읽은 curl로 GPT-OSS-20B에 “Reply with OK”를 보내 HTTP 200을 받았다고 보고했다. 성공 보고는 최소 요청 1건에 해당한다. 당시 터미널의 실제 키 결합, 응답 내용 및 청구는 독립 확인하지 않았다. Codex의 이전 협업 원장은 16:24:42 첫 관리자 기획에서 HTTP 403, 미검증 응답, 중단 상태를 보존한다. 11월 4일 Codespaces 진단의 별도 HTTP 403도 발생 계층이 확정되지 않았다. [이전 협업 기록](20261125_alternative_live_workflow_result.md) · [Codespaces 진단](https://github.com/smartaiboom/ai-company-os/blob/703702e2b840211877d6b6c7ee66781e690314f1/ai-company-os-phase1/reports/v01_groq_403_origin_codespaces_offline_diagnosis_20261104.md)

## 격리 비교

가상 인증값을 사용한 127.0.0.1 캡처에서 curl, 현재 협업의 `send_once`, 기존 `guarded_urlopen`을 비교했다. 실제 Groq 목적지는 어댑터가 생성한 요청 객체에서만 확인했다. 기본 샌드박스의 localhost 소켓 생성은 `EPERM`이었으며 정식 실행 권한 승인 후 로컬 캡처가 성공했다. 이 관측은 이전 원격 HTTP 403의 발생 위치를 설명하지 않는다.

| 항목 | 최소 curl 재구성 | 현재 협업 요청 |
| --- | --- | --- |
| 메서드·경로 | POST `/openai/v1/chat/completions` | 동일, 외부 목적지가 어댑터에 고정됨 |
| 인증·본문 | 가상 Bearer 인증, `application/json` | 동일 |
| 공개 헤더 | `curl/8.18.0`, `Accept: */*` | `Python-urllib/3.14`, `Accept-Encoding: identity`, `Connection: close` |
| 모델 옵션 | 단일 가상 메시지, 완성 토큰 100, 스키마 없음 | 역할 계약과 엄격한 응답 스키마, `reasoning_effort: low`, 완성 토큰 4096 |
| 크기 | 로컬 재구성 113바이트 | 로컬 합성 계약 2,260바이트, 이전 실제 원장 14,065바이트 |

현재 Codex 프로세스에 사전 설정된 Groq 키는 없었고, dotenv 로더는 등록된 키를 읽었다. 유효 값은 파일에서 해석한 키와 일치했고 기존 서명의 키 결합도 유효했다. 값·접미사·키 해시는 기록하지 않았다. 검사한 HTTPS/ALL/NO 프록시 환경변수는 대·소문자 모두 없었다. 일반 WSL 셸의 환경은 독립 확인하지 못했다. 현재 프로그램의 두 전송 함수는 환경 프록시 자동 탐색을 사용하지 않는다. Python 기본 TLS 컨텍스트에서 호스트명·인증서 검증이 켜져 있고, localhost 307은 후속 경로 전송 없이 차단됐다. 이전 원격 연결의 TLS 상대와 경유 경로는 미확인이다.

## 진단 수정과 재개

Groq의 문서화된 조직·프로젝트 모델 차단 코드 두 개를 기존 허용 목록에 추가했다. 향후 HTTP 실패에는 제한된 헤더 존재 여부만 기록하며 응답 발생 계층은 미확인으로 남긴다. 관련 Python 테스트 24건이 통과했다. 로컬 테스트에서 두 코드가 구분되고 헤더 값과 응답 자유문이 원장에 저장되지 않으며 동일 403 작업 재실행이 차단되는 것을 검증했다. 과거 `other` 기록은 두 코드가 허용 목록 밖이던 시점의 결과여서 해당 원인을 배제할 수 없다. 요청 옵션이나 네트워크 경로를 원인으로 확정할 증거가 없어 전송 동작은 유지했다. [Groq 모델 권한](https://console.groq.com/docs/model-permissions)

기존 서명은 2026-11-26 16:24:42 KST까지이며 점검 당시 활성 상태였다. 그 서명은 기존 격리 프로젝트에 결합돼 있고 유효기간은 중단된 업무의 재개 권한을 부여하지 않는다. 이번 신규 외부 AI 요청, 서명, 실패 재전송은 모두 0건이다. 공급자 잔량과 청구는 미확인이다.

요청한 최소 재개 승인 범위는 독립된 신규 격리 기획 업무의 GroqCloud Personal / Default Project, `openai/gpt-oss-20b`, `https://api.groq.com/openai/v1/chat/completions`, 새 서명 후 24시간, Free 전용 USD 0이다. 가상 목표·대표 선택·승인된 공개 근거와 한계·기획·대본·장면표·가상 수정 의견 및 역할 검토만 보낸다. 정상 협업 엔진과 서명·예약 경로를 사용하며 공급자 오류·미확정에서 멈춘다. 실제 관리자·직원 산출물과 영상 인계는 이 새 업무의 첫 응답이 검증될 때부터 진행한다.
