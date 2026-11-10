# Gemini TTS 모델 목록 실제 조회 결과 — 2026-11-10 KST

**기존 키로 models.list GET 1회 성공(HTTP200), 전체61개 모델 반환. 목표 TTS3종 모두 현재 키의 응답에 포함됐다.** 최신 main `a91eb1d` 및 AGENTS.md/지정 지시서를 확인하고 승인된 읽기 전용 목록 조회만 실행했다. 실제 TTS 생성0회, 추론0회, 추가비용0원(모델 메타데이터 조회만), Billing/계정 변경0, 새 B WAV 없음.

## 실제 응답 증거

조회 시각: `2026-11-10T16:00:07.481412+09:00`.
요청: `GET https://generativelanguage.googleapis.com/v1beta/models?pageSize=100`.
실제 GET1회·HTTP200·모델61개·nextPageToken 없음·목록 완결. 추가 페이지/재시도/대체 endpoint 호출0.

아래는 공개 문서의 후보 목록을 복사한 것이 아니라 **현재 GEMINI_API_KEY로 받은 응답에서 추출한 값**이다.

|실제 반환 name|supportedGenerationMethods|inputTokenLimit|outputTokenLimit|
|---|---|---:|---:|
|models/gemini-3.8-flash-tts|generateContent, countTokens, batchGenerateContent|8192|16384|
|models/gemini-3.8-flash-lite-tts|generateContent, countTokens, batchGenerateContent|8192|16384|
|models/gemini-2.5-flash-preview-tts|countTokens, generateContent|8192|16384|
|models/gemini-2.5-pro-preview-tts|countTokens, generateContent, batchGenerateContent|8192|16384|
|models/gemini-3.1-flash-tts-preview|generateContent, countTokens, batchGenerateContent|8192|16384|

상위3행이 지정한 확인 대상이고 하위2행도 TTS 이름 필터에 포함됐다. 반환 토큰 한도는 모델 메타데이터이며 **현재 남은 무료 쿼터가 아니다**. 반환 methods에는 Interactions가 직접 명시되지 않았으므로 이번 목록 조회를 기존 Interactions payload 실행 성공/호환성 검증으로 간주하지 않는다. generateContent/countTokens/batch API도 실제 호출하지 않았다.

## 계정 증거와 한계

- 사용자 화면 확인(이번 지시서에 전달됨): `Default Gemini Project`, 해당 프로젝트 ID, API 키1개, 무료 등급. 기존3.1/3.5 사용량 화면은 지원 목록이 아닌 과거 사용 기록이다. 전체 프로젝트 ID를 이 결과 보고서에 반복하지 않는다.
- 로컬 확인: 기존 관리자 경로가 사용하는 **GEMINI_API_KEY**가 존재한다. 기존 격리 인수 스토어의 과거 사용자 로컬 키 비교 기록 서명이 유효하며, 현재 키의 HMAC 바인딩과 일치한다. 과거 기록의 프로젝트 표시명도 사용자 화면의 표시명과 일치한다. 키/credential binding/signing key 값은 출력·보고서 저장하지 않았다. 키가 설정된 환경변수 이름만 기록한다.
- 과거 기록은 만료돼 **현재 TTS 동의/계정 증거로 재사용하지 않는다**. 표시명 일치는 프로젝트 ID 소속의 독립 검증이 아니다. API listing은 키 인증과 반환 모델 목록을 확인하지만 실제 프로젝트 ID/무료 등급/지역/잔여 무료쿼터/Billing 비활성/합성 성공·비용0을 증명하지 않는다. 사용자 화면의 무료 등급과 공급자 메타데이터를 구분한다.
- 공식 [models.list](https://ai.google.dev/api/models), [공개 모델 문서](https://ai.google.dev/gemini-api/docs/models), [가격](https://ai.google.dev/gemini-api/docs/pricing)을 조회했다(2026-11-10 KST). 모델당 공개 Standard Free Tier 표시와 실제 키 목록 포함은 각각 확인했지만, 둘을 결합해 현재 계정의 무료 합성을 보장하지 않는다. Billing/쿼터/청구원장 조회 API는 호출하지 않았다.

## 안전 실행·로컬 저장·검증

기존 `send_once`(ProxyHandler 빈 설정/NoRedirect)를 재사용한 `/tmp/check_gemini_tts_models_once.py`로 실행했다. GET/고정 도메인, 키는 x-goog-api-key 헤더만, timeout30초, 응답2MB 수락 상한, 키/원시 header/page token/원시 응답/예외 내용을 저장하지 않았다. 승인된 동일 GET 페이징만 지원하고 429/5xx/timeout에는 중단한다. 실제 실행에서는 첫 페이지만으로 끝났다. 신규 공급자/게이트/제품 코드는 추가하지 않았다.

로컬 보호 경로: `/workspaces/ai-company-os/data/gemini_tts_model_list/20261110T160007_KST/`.
`operation.json`과 `page_1_attempt.json`을 요청 전 exclusive/fsync 생성했으며 `result.json`에 응답코드·시각·선별 모델 name/methods/토큰 한도·매칭 결과를 저장했다. 전체 원시 응답/키는 저장하지 않았고 이 로컬 자료는 Git 제외다. 기존 승인/시도/사용량/비용 원장을 수정하지 않았다. 모델 조회 시도 영수증은 TTS 생성1회 예약과 분리돼 있다. TTS 실행 상수 False 유지, 사용자 대신 서명 승인0.

실행 전 네트워크 금지 상태에서 모의 GET 인코딩·2페이지 처리, timeout 재시도0, HTTP429 재시도0을 확인했다(3시나리오 통과). 저장 결과의 실제 요청수1/상태200/모델61/목표3매칭·기밀값 비포함을 확인했다. 제품 코드 변경이 없어 전체 회귀는 반복하지 않았다. 기존 미추적 파일7개/영상/대본/음성/키/기존 원장을 보존하고 결과 보고서와 CURRENT_PROGRESS만 커밋한다.

## 다음 최소 조치 하나

**AI Studio에서 gemini-3.8-flash-tts의 현재 무료 할당량과 Billing 비활성 상태를 확인해 결과를 알려주기.** 확인할 수 없는 항목은 미확인으로 남기고 키는 보내지 않는다. 이후 실제 음성1회는 기존 정확 본문/Google 무료 데이터 처리 조건/1회·$0의 별도 서명 동의가 필요하다. 이번 모델 조회 동의는 생성/추론/대체모델 실행 동의가 아니다.
