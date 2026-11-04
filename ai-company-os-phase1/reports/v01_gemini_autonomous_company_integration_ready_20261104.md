# Gemini 기존 자율 회사 연동 및 첫 실제 프로젝트 준비

2026-11-04 KST. `git pull --ff-only`로 ec2e5bd 반영. 핵심 원칙·AGENTS.md·한국어 규칙·지정 지시서·이전 Gemini 2개 보고서와 Groq 첫 실제 실행 보고서, 기존 회사 엔진/CLI/어댑터/원장/동의/로컬 도구/테스트를 확인했다.

**기존 자율 협업 엔진에 Gemini를 통합했고 최초 실행 전까지 준비했다. 실제 AI API 요청 0회, 재시도 0회다.** 사용자 직접 curl에서 얻은 3.1 Flash-Lite HTTP 200은 지시서의 선행 사실이며 응답 본문 계약이나 협업 완주를 이번에 실제 검증한 것은 아니다. 이전 2.5 소진 실패 원장도 그대로다.

## 구현과 재사용

변경 파일:

- `gemini_provider.py`: 네이티브 generateContent 요청 및 응답 어댑터. `gemini-3.1-flash-lite`와 `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent`만 허용한다. x-goog-api-key 헤더 인증, 키는 메모리에서만 사용하며 URL query에 넣지 않는다.
- `autonomous_gemini.py`: GeminiStore/GeminiConfig/GeminiCompany. 기존 FreeStore/FreeCompany/LiveManagerProvider/LiveEmployeeProvider를 재사용한다. 별도 marker·프로젝트 prefix·서명 운영 동의·공급자 원장 정책을 사용한다.
- `autonomous_free.py`: JSON envelope 정규화 훅 1개 추가. 기존 OpenRouter/Groq 기본 훅은 입력을 그대로 반환하며 기존 모델/비용 제한은 변경하지 않는다.
- `autonomous_live_cli.py`: `--provider gemini` 및 `--confirm-gemini-free-account` 추가. 기존 저장소를 다른 공급자로 열면 차단한다. 새 API/UI 엔진은 만들지 않았다.
- `gemini_first_project.py`: 네트워크 없는 prepare와 별도 명시 execute 명령. 최초 동의·실행을 한 명령으로 연결하되 업무별 결재는 만들지 않는다. O_EXCL 시작 소진 파일과 기존 서명 동의/상태 검사로 중복 실행을 차단한다.
- `tests/test_autonomous_gemini.py`, 이 보고서.

기존 manager→계획/품질 기준→employee→의존 결과 인계→manager review→필요시 revision→로컬 artifact→최종 검토/보고 상태 기계를 그대로 사용한다. JSON 내용·업무 배분·품질 판단은 미래 Gemini 응답에서만 채운다. 첫 합성 목표 문구 외에 실제 계획/직원 결과/품질 기준을 사전 작성하지 않았다. 일반 목표도 기존 CLI로 생성할 수 있다. 테스트의 가상 결정은 테스트 파일에서만 사용한다.

Gemini 요청은 systemInstruction/contents/generationConfig이며 기존 역할 schema를 responseJsonSchema와 JSON MIME으로 전달한다. candidates가 정확히 하나이고 finishReason=STOP인 최종 text만 변환한다. thought 블록은 저장/전달하지 않으며 tool/code/inline-data, safety/prompt block, refusal, 빈 응답, 불완전 finish, JSON/schema 오류는 실패로 처리한다. 실제 업무 JSON도 기존 strict schema 및 도메인 독립 상태 검사로 다시 검증한다.

입력 128KiB, 응답 256KiB, 역할 텍스트 128KiB, 출력 4096 tokens 제한을 유지한다. 필수 prompt/candidate/total 사용량은 정수만 허용하고 unknown/missing은 정지한다. 반환된 thought tokens가 있으면 후보 출력과 합산해 상한을 검사한다. 토큰은 사용량 관측이지 금액 증명이 아니다. 원장에는 고정 예외 category/stage와 숫자 HTTP 상태만 기록하며 원문 오류/헤더/body/키 식별정보를 기록하지 않는다. 과거 오류 분류를 소급 변경하지 않는다.

## 무료 정책과 운영 안전

[공식 가격표](https://aistudio.google.com/docs/pricing#gemini-3.1-flash-lite)의 Standard Free Tier 입력·출력 무료 조건을 2026-11-04에 다시 확인했다. 해당 키 프로젝트 Free tier는 지시서의 사용자 확인을 근거로 한다. 이 실행 프로세스의 GEMINI_API_KEY 존재 bool=true만 확인했다. 키 값·길이·일부·해시는 저장/출력하지 않았다.

[공식 한도 문서](https://aistudio.google.com/docs/rate-limits)는 RPM/TPM/RPD 등 프로젝트별 제한을 설명하며 실제 활성 한도는 AI Studio에서 확인하도록 안내한다. 해당 계정의 현재 숫자·잔여량을 조회한 것은 아니다. 보장 쿼터를 임의 작성하지 않는다. 기존 최소 2초 간격, 1800초 업무 실행 경계, 유한 task/revision·정체 차단을 적용한다. 429/503은 정지/paused 원장으로 남기고 자동 재시도·계정 교체·fallback하지 않는다. 알려진 remaining=0도 다음 요청 전 차단한다. [generateContent 계약](https://aistudio.google.com/api-reference/generate-content)과 [구조화 응답 문서](https://aistudio.google.com/docs/structured-output)를 확인했다.

비용 0 근거는 모델 공식 무료 조건과 프로젝트 최초 서명 Free tier 확인이다. Gemini 응답에 금액 필드가 없으므로 응답으로 청구액 0을 확인했다고 표시하지 않는다. 응답에 뜻밖의 양수 cost가 나오면 차단한다. 유료 경로/결제 변경/자동 모델 대체는 없다. 최초 확인과 실제 요청 시점 사이의 Google 계정 결제 등급 변경을 이 프로그램이 계정 API로 감시하는 것은 아니므로 실행자는 해당 프로젝트가 여전히 무료임을 확인해야 한다.

기존 durable 사전 예약, request/context/operation 식별, active_operation·failed/unvalidated 보존, 서명 동의/유효기간/목표·공급자·모델·endpoint·전송 범위·도구 권한 검사 및 저장소 잠금을 재사용한다. 기존 공유 guarded transport의 redirect 차단·TLS 검증·proxy 정책은 변경하지 않았다. 독립 인사 실행기의 기본 proxy 경로와 회사의 공유 guard는 서로 다르며, curl 성공이 이 회사 경로의 성공을 보장하지 않는다. 미확정/실패를 새 공급자에 재송신하지 않는다.

## 준비한 독립 프로젝트와 단일 최초 동의

저장소: `data/gemini-first-autonomous-20261104` (Git 제외).

- 프로젝트: `geminicompany-db22e41adcc4446d9904e44c363df5fc`.
- 상태 ready, enabled=false, attempts=0, grant 없음, 서명 키 없음, 시작 소진 표식 없음. 계획·직원·최종 산출물은 아직 없다.
- 합성 목표: 초보자의 좋은 AI 질문 작성법을 한국어 자막/로컬 음성의 20~30초 MP4 및 최종 보고서로 제작. 개인/회사 비밀 없음. 계획/담당/품질 기준/수정 여부는 실제 관리자에게 맡긴다.
- 외부 전송 범위: 목표, 생성 계획·품질 기준·배정, 직원 결과, 관리자 검토, 최종 통합. 실제 회사 자료·비밀키·업로드·외부 검색은 포함하지 않는다.
- 로컬 권한: 기존 `caption_video_v1`만. FFmpeg/ffprobe/espeak-ng와 한국어 폰트 존재를 로컬 확인했다. 네트워크·임의 shell·외부 파일 접근 권한은 제공하지 않는다.
- 호출 정책: 총/시작당 자의적 비용성 상한 없음(max_calls=null), 재시도 없음. 8개 이하 task, task당 수정 1회/총 수정 2회, 품질 정체·시간·공급자 제한을 적용한다. 업무 중간 승인 0회를 목표로 한다.
- 동의안: `operating-proposal.json`, 대상/검토 hash: `launch-manifest.json`. 이들은 승인 제안일 뿐 운영 동의가 아니다.
- 발행 2026-11-04T14:06:54+09:00, 만료 2026-11-05T14:06:54+09:00. Free tier 확인의 24시간 조건도 적용한다. 만료 후 아래 명령은 안전하게 차단되며 과거 파일을 지우거나 새로 승인한 척하지 않는다.

최초 실행자는 로컬 동의안에서 목표·범위·무료 등급·모델·endpoint·시간/품질/쿼터 정지 조건을 검토한다. 아래 명령의 owner-confirmed와 confirm-free-tier는 해당 프로젝트 최초 외부 전송 및 자율 실행에 대한 명시 동의다. 승인 후 기존 AI 관리자/직원이 내부 판단으로 진행하며 매 업무 승인 질문을 만들지 않는다. 이번 개발 작업에서는 해당 명령을 실행하지 않았다.

## 테스트와 데이터 보존

실행 명령:

```bash
python -B -m unittest tests.test_autonomous_gemini tests.test_autonomous_groq tests.test_autonomous_free tests.test_autonomous_live tests.test_gemini_connection_once
```

관련 회귀 **69개 통과**, 실패/오류 0 (20.501초, exit 0). Gemini fake 네이티브 응답으로 관리자 계획→두 직원→선행 인계→수정 1회→기존 실제 로컬 음성 MP4→최종 보고 E2E를 검증했다. 업무 승인 요청 0, fake 호출 8회, 중복 run 후 추가 호출 0. 이것은 **오프라인 fixture 성공이며 실제 AI 결과가 아니다**. 가상 모델이 만든 MP4의 기술 검사·디코딩은 확인했으나 미적 품질·실제 Gemini 판단 품질을 입증하지 않는다.

HTTP 400/401/403/404/429/503, timeout/DNS, 빈 응답·truncated JSON·invalid schema·안전 차단·refusal·thought만 존재·tool 요청·unknown usage·비정상 token·비용·키 반사, 동의 부재/만료/범위 변경/공급자 전환, crash 예약/상한/중복 실행 거부를 확인했다. 테스트는 socket/DNS 차단·가짜 키·임시 store를 사용한다. 실제 data의 operation은 실행하지 않았다.

후속으로 응답 읽기/JSON 파싱 단계 분류를 보완하고 아래 집중 검사 **3개 통과**를 확인했다.

```bash
python -B -m unittest tests.test_autonomous_gemini.GeminiTests.test_response_read_timeout_and_broken_envelope_diagnostics tests.test_autonomous_gemini.GeminiTests.test_http_and_timeout_stop_without_retry_or_free_text tests.test_autonomous_gemini.GeminiTests.test_malformed_refused_incomplete_unknown_usage_and_secret
```

`git diff --check` 통과. 기존 data/backups/checkpoints 74개 파일 전후 SHA256 모두 동일. 기존 Gemini 소진 1회 원장과 Groq/OpenRouter 실패·예약·프로젝트·백업을 변경하지 않았다. 새 파일은 위 독립 Gemini 준비 store에만 만들었으며 Git에는 비밀 없는 코드·테스트·이 보고서만 저장한다. 기존 사용자 미추적 파일은 변경하지 않았다.

## 남은 검증과 후속 명령 하나

이번 결과는 목표→AI 자율 협업→최종 산출물의 기존 흐름에 Gemini를 사용할 수 있는 경로와 최초 동의 절차를 추가했다. 실제 Gemini 역할 JSON 수락·서비스 안정성·공유 transport 연결·직원 협업·최종 MP4 완주는 아직 미검증이다. 실제 성공을 막는 남은 단계는 이 신규 프로젝트의 명시적 최초 운영 동의와 실제 실행 검증이다. 기존 수동 프로젝트의 업무별 승인 부채는 보존되며 신규 경로에는 추가하지 않았다. UI/대시보드는 변경하지 않았다.

무료 등급과 준비된 전송 범위를 검토·동의한 뒤 유효기간 안에 실행할 **후속 명령 하나**는 다음과 같다. 이 명령은 단건 인사 테스트가 아니라 한 프로젝트의 자율 협업을 시작한다.

```bash
python -B gemini_first_project.py execute --review-hash 7c0e9a998660e6595bc6b34007b705a78456724b2c0c65131671c7f9c9f2ab60 --owner-confirmed --confirm-free-tier
```
