# Gemini 503 오프라인 원인 진단
2026-11-13 KST · 기준 main `7612d0a` · 코드·실제 작업 데이터 수정 없음.

확정 범위는 **동일 업무 요청에 대한 HTTP503 두 번**이다. 응답 JSON/기획안 검증 실패와는 구별된다. 제공자 내부 장애와 요청 특성에 따른 실패를 가를 서버 오류 본문이 없어 근본 원인은 확정할 수 없다.

## 실제 원장 비교
컷룸 경로: `#project/workspace/company-aba553f29cfb454c8c05bad4abb49969`.
로컬 프로젝트: `data/video_representative_workflow/studio/company-aba553f29cfb454c8c05bad4abb49969.json`.
작업·동의 원장: 같은 디렉터리의 `representative_rework/`.

| 항목 | 11/12 | 11/13 |
|---|---|---|
| 작업 ID | qualityprovider-63f5d501fc34496292167736371b990c | qualityprovider-23bccf52ca0d4aa38ba6232c38294b82 |
| 전송~종료 KST | 16:41:21~16:41:23 | 09:17:59~09:18:01 |
| 요청 해시 | bc787bb74af99b6a97cce47f3c5d4bd20a66c94c41d7136d423ba2a89439512a | a4a6c6db05749ba2a81f6232d3bba7168b70a13d4a6cc4745c8f177479c2b749 |
| 전송 크기 / 출력 상한 | 36,671바이트 / 4,096토큰 | 36,671바이트 / 4,096토큰 |
| 상태 | plan / failed / HTTP503 / unvalidated | plan / failed / HTTP503 / unvalidated |
| 내부 작업 / 컷룸 | paused / 이력 stopped | paused / 현재 stopped |

각 작업은 전송 시작과 최종 실패가 기록된 attempt 1개뿐이다. active_operation은 각 종료 attempt ID를 가리키며 reserved attempt나 별도 미확정 전송은 없다. 응답 해시·response_received_at·응답 진단은 두 건 모두 저장되지 않았다(조회상 null/없음). `provider_error_diagnostics`는 두 건 모두 `5xx_server / transport_open`, rate_limits는 빈 객체이고 Retry-After 기록도 없다.

양쪽 작업 저장 해시·독립 grant 서명·현재 로컬 키 binding을 읽기 전용으로 검증했다. 동일 무료 프로젝트 binding, 모델 `gemini-3.5-flash-lite`, 고정 generateContent 엔드포인트이며 동의 만료는 각각 11/12 17:41:10, 11/13 10:17:50 KST이다. 전송은 각 동의 만료 전이다. 무료 quota/billing은 서명된 소유자 확인 수준이며 독립 검증되지 않았다.

별개 HTTP200 작업 `qualityprovider-3cb52d1ab205460897e9f03fea21ca71`은 11/12 16:06:16~22, 33,985바이트 요청에 정상 응답 후 `invalid_dependencies`로 중단됐다. 이때 실제 입력 토큰은 9,743이다. 두 503에는 유효 기획안·새 대본이 없으며 이 과거 검증 오류를 503 원인으로 합치지 않았다.

## 코드와 요청 재현 근거
- `core/autonomous_live.py`의 `_call` → `representative_rework.py`의 `_prepare_payload` → `core/autonomous_free.py`의 `_request_json` → `video_mission_one.py`의 `_open_transport` → `core/goal_dialogue_live.py`의 `send_once` 경로다. 실제 어댑터는 `core/autonomous_gemini35.py`의 Gemini35Adapter이며 `core/gemini_provider.py`를 상속한다. 공통 정의는 `core/ai_provider_adapter.py`다. 상속 파일의 3.1 상수가 실제 3.5 전송 모델을 덮어쓰는 경로는 아니다.
- POST, 고정 3.5 모델/엔드포인트, timeout=90초. `ProxyHandler({})`로 환경 프록시를 배제하고 리다이렉트·자동 재시도를 막는다. 기록된 약 2초 HTTP503은 90초 타임아웃이 아니다. 실행 플래그·모델/엔드포인트·키/동의 검사는 전송 전 수행하도록 구현되어 있다.
- HTTPError는 `core/autonomous_free.py`에서 503→`provider_unavailable`로 분류한다. Gemini 오류 기록은 HTTP 상태와 고정 분류만 남긴다. HTTPError 본문을 읽지 않고 닫으며, Google request ID·서버 오류 메시지·원본 헤더도 보존하지 않는다. 응답 JSON 정규화/역할 검증에 도달하지 않았으므로 로컬 JSON Schema 검증 실패로 진단할 수 없다. `transport_open`은 예외 발생 위치이지 네트워크 단절 증명이 아니다.
- 두 작업을 메모리 복사하고 승인/세션 검사를 진단용으로 우회한 뒤, 요청 생성 끝에서 가로채 전송·예약·저장 없이 비교했다. 현 코드로 **두 request_hash와 context_hash 및 36,671바이트를 모두 정확히 재현**했다. 원장 실행이나 run/approve는 호출하지 않았다. 양 요청의 contents·generationConfig는 동일하고 systemInstruction 속 작업 ID만 다르다. 해시 차이는 업무 입력 변경을 뜻하지 않는다.
- systemInstruction 10,056바이트(8,397자), 사용자 텍스트 18,834자. JSON Schema 2,611바이트(2,609자), result.anyOf 2개이며 `generationConfig.responseJsonSchema`와 사용자 메시지 `output_contract`에 동일 스키마가 중복된다. 별도 systemInstruction에는 역할/품질/재작업 지시가 들어간다. 전체 텍스트 합계 약 29,840자. 로컬 입력 상한 131,072바이트 이내다. 과거 HTTP200의 바이트/실측 토큰 비율을 단순 적용하면 약 10,500 입력 토큰 수준이나 이는 **추정**이며 실패 요청의 실측·공식 토큰 계산은 없다.

## 원인 구별
| 후보 | 판단 | 근거·한계 |
|---|---|---|
| 서비스 503 | HTTP503 관측 검증됨, 제공자 과부하/일시 장애 가능성 | 두 시점 동일 HTTP 오류. 서버 본문·요청 ID 부재로 Google 내부 원인 확정 불가 |
| 크거나 중복된 요청 | 중복 구조 검증됨, 503 인과 근거 부족 | 동일 스키마 2회, 약 36KB. 로컬 크기 제한 통과; 비슷한 34KB 요청은 과거 HTTP200. 단순화 전후 실측 없음 |
| 전송·프록시 | 환경 프록시·리다이렉트 배제는 코드 확인, 다른 중간 계층 문제 근거 부족 | HTTP 응답은 관측됐으나 응답 출처 헤더 미보존; 원 서버/중간 계층을 단정할 수 없음 |
| 모델·설정 | 고정 모델/엔드포인트·서명/binding 확인, 오설정이 원인이라는 근거 부족 | 작업 지침에 제공된 Google 공식 모델 문서상 ID는 유효하고 structured outputs 지원. HTTP503만으로 모델 부적합 주장 불가 |

공식 정보는 이번 지침이 제공한 확인 사실을 사용했다: [모델](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [API 오류](https://ai.google.dev/gemini-api/docs/api-errors). 이번에는 웹 조회도 하지 않아 현재 서비스 상태는 확인하지 않았다.

## 가장 필요한 다음 조치 하나
**별도의 명시적 동의를 받아, 같은 고정 모델에 무해한 합성 텍스트만 보내는 최대 1회 최소 연결 진단 호출을 별도 예산으로 수행한다.** 실제 목표·피드백은 보내지 않고 반환 HTTP 상태만 확인하며 실패도 1회로 차감하고 재시도·유료 전환·fallback은 하지 않는다. 성공하면 최소 요청 수락만 확인되며 원래 업무 요청 성공을 보장하지 않는다. 이 보고는 호출 승인이 아니며, 무료 여부도 자동으로 확정하지 않는다.

이번 외부 API/YouTube 호출·연결 테스트·웹 조회 0회. 테스트 스위트 실행 없음. 소켓/DNS를 차단한 요청 생성 검사만 수행했다(초기 진단 경로 설정 오류를 바로잡아 재실행). 검사 전후 실제 studio 파일 56개 SHA-256 목록 동일. 코드·원장·산출물·동의·서명·키·미추적 파일 불변; 보고서만 추가하고 main에 저장한다.
