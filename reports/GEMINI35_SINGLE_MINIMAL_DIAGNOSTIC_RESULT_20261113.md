# Gemini 3.5 최소 진단 준비 결과
2026-11-13 KST · 기준 main `f0e000b`.

**실제 API 호출 0회. 실제 계정의 무료 등급을 독립 확인할 수 없어 전송 전에 중단했다.** 사용자 승인은 합성 문장 최대 1회에 한정되며, 무료 등급 확인 조건을 대체하지 않는다. HTTP 상태·새 응답은 없고 진단 승인 한도를 소진하지 않았다.

- 사전 점검: 기존 키 존재, 현재 업무 grant 서명·동일 키 binding 유효, 원장 모델/엔드포인트가 고정 Gemini 3.5 Flash-Lite와 일치함을 값 노출 없이 확인했다. 그러나 이는 실제 계정의 Free Tier/미청구 증거가 아니다. 현재 연결 도구에 Google 계정 티어·결제 조회 기능이 없고 `gcloud`도 없다. 공식 가격표의 Free Tier 제공이나 기존 소유자 서명만으로 무료 계정이라고 판단하지 않았다. 다른 자격증명/프로젝트로 바꾸거나 API 연결을 시험하지 않았다.
- 중복 조사: 로컬 코드·문서·보고서·JSON 기록에서 동일 합성 문장/진단 식별자를 검색했다. 승인 지침 외 기존 전송 증거는 발견하지 못했고, 지정 진단 원장 `reports/gemini35_single_diagnostic_20261113.json`도 없다. 외부/다른 프로세스의 미기록 실행까지 없다고 보증하지 않는다. 이번에는 무료 조건에서 차단되어 실제 예약·전송 원장을 만들지 않았다.
- 준비한 요청: 고정 POST `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`, `x-goog-api-key` 사용 계획. 아래 payload의 공백 없는 UTF-8 직렬화는 99바이트다. 실제 업무 목표·피드백, systemInstruction, schema, 도구, 캐시, temperature 없음.

```json
{"contents":[{"parts":[{"text":"Reply with OK only."}]}],"generationConfig":{"maxOutputTokens":16}}
```

합성 문장 SHA-256: `eaf01eb39aff46d47efaf2318b7a11d42e1e6ae27704e1ed74ba6886b57c9f03`.
요청 body SHA-256: `093198863b9f01957dbb4ae66f85864df5f0ac9eb87cf4e3a29c7d2de5980c60`.

- 코드 확인: `core/goal_dialogue_live.py:send_once`는 환경 프록시 배제·리다이렉트 거부·재시도 없는 전송 경로다. 과거 `gemini_connection_once.py`는 다른 모델/문장 및 기본 프록시 정책이므로 그대로 실행하지 않았다. 기존 실행 함수/run/approve는 호출하지 않았다.
- 가벼운 오프라인 시뮬레이션 1개 통과: 소켓/DNS 차단 아래 `/tmp` 임시 원장과 가짜 전송만 사용했다. 무료 미확인 시 가짜 전송도 0회·예약 없음; 확인을 가정한 경우 O_EXCL/O_NOFOLLOW로 KST·목적·고정 모델/엔드포인트·합성 문장 해시·max_attempts=1·업무 독립·reserved를 먼저 기록하고 파일/디렉터리 fsync 후 가짜 전송 1회; 합성 timeout 후 reserved 유지; 기존 reserved 원장을 발견한 재실행은 0회로 차단했다. 실제 네트워크 전송이나 실제 계정 무료 검증이 된 것으로 간주하지 않는다. 원장 저장 실패·결과 불명에도 재전송 금지가 필요하다.
- 보존 확인: 실제 studio 파일 56개의 검사 전후 SHA-256 목록이 동일했다. 11/12·11/13 HTTP503 작업, 기존 업무·동의·grant·호출 기록·산출물·키·미추적 파일을 변경하지 않았다. 공통 core/영상/음성/컷룸 코드 수정 및 회귀 테스트 없음. 실행 가능한 새 실제 호출 도구는 설치하지 않았고 준비 결과만 보고한다.

**다음 행동 하나:** Google AI Studio의 프로젝트 화면에서 **현재 키에 연결된 동일 프로젝트의 API Tier가 Free Tier인지** 직접 확인하고, 해당 프로젝트의 결제 설정도 함께 확인해 미청구 조건의 근거를 제공한다. 키 값은 공유하지 않는다. 이 확인 전에는 승인된 1회 진단도 실행하지 않는다.
