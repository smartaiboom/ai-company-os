# 실제 관리자1회 호출 검토 — 2026-11-10 KST

**준비만 완료. 정식 실행하지 않음. 실제 호출0/1, 추가 비용0원, 계정 확인·최종 실행 승인 없음.**

| 항목 | 준비 내용/현재 상태 |
| --- | --- |
| 공급자/모델 | Google Gemini Developer API / `gemini-3.5-flash-lite` |
| endpoint | `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent` |
| 목적 | 새 가상 초보자60초 세로 쇼츠 목표에 대한 관리자 전략 또는 필수 질문1회 |
| 데이터 범위 | 가상 목표·대상·규격·소스0개/권리 미확인·기존 로컬 음성 한계·허용 작업 없음과 출력 schema. 기존 원본/원장/계정키/개인 피드백/프로젝트 전체 없음 |
| 호출/토큰 | plan1회(실패·429·timeout·중단 포함1회 소모), 최대 output4096 tokens. 직원/review/finalize/피드백/영상/게시/두 번째 요청0회 |
| 비용 정책 | 무료 계정 전용, 추가 비용 상한0원, 유료전환/대체/fallback/재시도 없음. 계정 상태를 확인하지 않아 실계정 무과금은 아직 보장하지 않음 |
| 실행 게이트 | `MANAGER_PLAN_EXECUTION_ENABLED=False`. 기존 `QUALITY_TRANSPORT_ENABLED=False`와 일반 dialogue 정책도 유지 |
| 계정/키/Billing/쿼터 | 사용자 현재 화면 확인·비표시 로컬 키 대조 대기. Codex가 계정 내부 Billing을 검증하지 않음 |
| 서명 승인 | 없음. 계정 확인 후 정확 payload를 다시 prepare하고 새 해시로 개별 승인해야 함 |
| 산출물 | 실제 전략 응답/직원 결과/새 영상 없음. 영상 점수 미평가 |

## 전체 payload의 실제 보호 경로와 해시

GitHub에는 payload 원문·원장·키·인증정보를 올리지 않는다. 아래 파일은 로컬 전용(폴더0700/파일0600)이다.

- 새 저장소: `/tmp/ai_company_manager_plan_20261110_2c87613`
- 새 프로젝트 ID: `dialogue-ae1e87db8bab4615b2af6806c1c00bc6` (과거 인수 프로젝트 아님)
- 정확 system/user/response schema를 포함하는 요청 파일: `/tmp/ai_company_manager_plan_20261110_2c87613/dialogue-ae1e87db8bab4615b2af6806c1c00bc6.payload.json`
- payload 파일 SHA-256/실제 request bytes 해시: `07988fccca5ac7b4466e9b21e9ae837c46254d2976c1afefde9136cc334d0168`
- 검토 파일: `/tmp/ai_company_manager_plan_20261110_2c87613/dialogue-ae1e87db8bab4615b2af6806c1c00bc6.review.json`
- 새 스코프 해시: `c115042c4e2dbc7ab0c82f7a6965982dcc6d6bab732a9167bc19508f344578be`
- 현재 임시 검토 해시: `ee40c10f6cb8ad54a5c3715620f66db38be6a96b8a72367c73d7d1bec99e3c9b`
- 생성 `2026-11-10T10:11:17+09:00`, 유효 기한 `2026-11-10T11:11:17+09:00`. **계정 확인 전 제안이며 최종 실행 승인용 해시로 재사용하지 않음.** 계정 증거 저장 시 상태가 바뀌므로 prepare를 다시 해야 한다. 계정/승인도 각각1시간 만료다.

이 경로는 `/tmp`이므로 환경 재시작 시 유실될 수 있다. 아직0회이지만 향후 호출/승인이 생기면 이 원장을 보존하고, 유실·불확실 시 새로 생성해서 재시도하지 않는다.

## 공식 정보 확인과 계정별 불확실성

2026-11-10 KST 공식 사이트 검색 발췌에서 모델 ID와 structured outputs 지원을 확인했다. 직접 문서 열기는 도구의 text/markdown 처리 오류가 있었으므로 검색 발췌 근거라는 한계를 남긴다. [공식 모델 문서](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite).

공식 가격 검색 발췌에는 이 모델 Standard의 Free Tier 입력·출력 무료와 Paid Tier가 구분되어 있다. 이는 이 계정의 무료 등급을 확인한 것이 아니다. [공식 가격](https://ai.google.dev/gemini-api/docs/pricing?authuser=6).

한도는 키별이 아닌 프로젝트별이며 현재 허용량은 AI Studio에서 확인해야 한다. 공개 문서만으로 현재 잔여쿼터를 추정하지 않는다. [공식 rate limits](https://ai.google.dev/gemini-api/docs/rate-limits?authuser=2).

**Google 무료 데이터 처리 경고:** 무료 서비스 입력/응답은 Google 제품·모델 개선에 사용될 수 있고 사람이 검토할 수 있다. 민감·기밀·개인정보는 보내지 않는다. 사용자는 실제 전송 전 이 정책에 별도로 동의해야 한다. [공식 약관](https://ai.google.dev/gemini-api/terms?authuser=00).

## 다음 사용자 확인 순서 — 아직 실행 금지

1. 현재 Google AI Studio의 해당 프로젝트에서 Free 등급, Billing 비활성, 선택 모델 사용 가능/잔여 쿼터를 직접 확인. 유료 또는 불확실하면 보류. 현재 코드가 대조할 프로젝트 이름은 기존 코드의 기본 라벨 `Default Gemini Project`이며, 그 이름만으로 올바른 계정임을 입증하지 않는다. 다른 프로젝트라면 먼저 별도 설정/검토가 필요하다.
2. 정확 payload를 로컬 파일에서 검토. 키는 채팅/명령 인수/로그에 넣지 않고 secure TTY의 `verify-key`에서 환경의 GEMINI_API_KEY와 비표시 대조한다. 이는 사용자 진술·키 대조이고 독립적인 Google 계정 조회가 아니다.
3. `prepare`를 다시 실행해 증거·현재 키 결합·스코프·payload·1시간 만료를 포함하는 새 검토 해시를 확인하고, Google 무료 데이터 정책과 정확한 plan1회에 대해 개별 실행 승인을 받는다.
4. 현재 실행 정책은 계속 비활성이다. 개별 승인 후 별도 검토된 좁은 정책 활성화가 필요하며, 환경변수/키 존재로 대신할 수 없다. 이번에는 승인/실행 명령을 수행하지 않았다.

## 실제 응답 이후의 전략 평가표 (현재 전부 미평가)

시청자 적합성, 한 가지 유용한 메시지, 후크/실제 시연 구체성,60초 장면/소스 실행 가능성, 직원 역할·인계/완료 기준, 불확실성 정직성, 추가 질문의 필요성을 사람이 항목별 근거와 함께 검토한다. 영상10점 점수와 별개이며 실제 응답이 없으므로 전략 점수도 매기지 않았다. 수치상 timeline60초/소스 길이·참조/의존성·미생성/권리 미확인 표시는 코드로 검증한다. 자연어 내용에 숨은 허위주장까지 자동 보증하지 않는다.
