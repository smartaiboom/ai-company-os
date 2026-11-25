# 대체 AI 공급자 연결 준비 결과

2026-11-25 KST · GitHub main `6a9aac7`에서 시작.

## 우선 후보와 준비 상태

**GroqCloud의 `openai/gpt-oss-20b`를 우선 후보로 선정했다.** 기존 `GroqFreeAdapter`가 이 모델과 Chat Completions 경로, 역할별 strict JSON Schema, 제한된 오류 진단을 이미 구현한다. 공식 Free 한도는 30 RPM, 1,000 RPD, 8,000 TPM, 200,000 TPD로 게시돼 있다. 유료 요금표도 있으므로 모델 ID만으로 비용 0이 보장되지는 않는다. 실제 프로젝트의 Free 상태·결제 상태·모델 권한·남은 쿼터와 한국어 대본 품질은 미확인이다. [모델](https://console.groq.com/docs/model/openai/gpt-oss-20b) · [구조화 출력](https://console.groq.com/docs/structured-outputs) · [무료 한도](https://console.groq.com/docs/rate-limits) · [결제](https://console.groq.com/docs/billing-faqs)

현재 WSL 프로세스와 기존 로더로 읽은 `.env`에서 `GROQ_API_KEY`와 `OPENROUTER_API_KEY`의 존재 여부만 확인했으며 둘 다 없었다. 현재 Groq 어댑터의 `enabled`는 `False`다. 과거 Codespaces의 독립 합성 요청은 HTTP 403이었으며 응답을 생성한 계층은 미확정이다. 현재 프로젝트의 권한을 입증하는 자료로 사용하지 않았다. [과거 진단 기록](https://github.com/smartaiboom/ai-company-os/blob/703702e2b840211877d6b6c7ee66781e690314f1/ai-company-os-phase1/reports/v01_groq_403_origin_codespaces_offline_diagnosis_20261104.md)

OpenRouter의 기존 실행기는 동적 `openrouter/free`를 사용한다. 고정 무료 모델과 실제 수신 공급자를 별도로 선택하고 가격 0 상한, fallback 금지, 요구 파라미터 지원과 데이터 정책을 대조해야 하므로 이번 후보 선정에서는 보류했다. [OpenRouter 무료 모델](https://openrouter.ai/collections/free-models) · [라우팅 제어](https://openrouter.ai/docs/guides/routing/provider-selection)

## 코드와 검증

협업 대본 인계는 모듈의 고정 Gemini 모델 상수 대신 검증된 실행 서명에서 공급자·모델·목적지를 읽어 각 호출 원장과 대조한다. HTTP 200, 역할 응답 검증, 동일 승인 ID 및 비용 정책 해시를 확인한 뒤에만 기획 산출물에 제공자 식별을 남긴다. 기존 역할 검토, 모의 응답 식별 및 영상 인계 경로를 사용한다. Groq의 현재 협업 전송 연결은 계정·권한과 명시 승인이 확인된 후 기존 어댑터를 연결하는 지점에서 재개한다.

22개 관련 Python 테스트가 통과했다. 기존 모의 업무 통합 테스트에서 공급자·모델·목적지·서명 ID·비용 정책·응답 검증 상태를 각각 바꾸면 인계가 차단되는 것을 확인했다. 실제 외부 AI 호출과 새 공급자 서명은 0건이다. 운영 v8, Gemini 실패 원장, 기존 영상은 수정하지 않았다. 기존 전체 회귀의 Playwright·espeak-ng 미설치와 재계획 상태 불일치 두 건은 이전 기록을 따른다. [이전 전체 회귀 결과](20261125_reviewable_spoken_video_result.md)

격리 localhost 컷룸에서 모의 관리자·작가·편집의 기획·수정, 36초 무음 MP4 제작, 전체 GET 200·탐색 206·썸네일 200 및 영상 피드백을 반영한 다음 대본의 검토 대기를 확인했다. 로컬 검증 파일의 SHA-256은 `71a631d6a5706d85fc982333038b276b145252d0f18eb9734c7c479f94bc57f9`이다.

## 필요한 명시 승인

- **공급자·목적지** · GroqCloud의 `openai/gpt-oss-20b`, `https://api.groq.com/openai/v1/chat/completions`만 사용한다. 대표가 콘솔에서 승인할 조직/프로젝트 식별자, 조직 Free 및 유료 전환 미설정, 모델 사용 권한, 프로젝트 키의 로컬 등록을 확인한다. 키는 대화에 전달하지 않는다. [프로젝트](https://console.groq.com/docs/projects) · [모델 권한](https://console.groq.com/docs/model-permissions)
- **목적·전송 데이터** · 격리 개발 프로젝트의 가상 목표·대표 선택·승인된 공개 근거와 한계·기획과 한국어 대본·장면표·가상 수정 의견과 역할별 검토에 한한다. 운영 자료, 개인정보, 영상·음성 파일 및 로컬 실측 메타데이터는 승인 범위에서 제외한다. Groq는 일반 추론 입력·출력을 기본 보관하지 않지만 장애 진단·남용 조사 시 최대 30일 보관할 수 있으며 조직의 Data Controls에서 ZDR을 설정할 수 있다. [Groq 데이터 정책](https://console.groq.com/docs/your-data)
- **기간·중단 조건** · 서명 후 24시간, Free 전용 USD 0. 실제 프로젝트 한도·속도를 적용한다. 격리된 관리자 배정 → 작가 대본 → 편집 장면표 → 관리자 검토 → 가상 수정 의견 반영 → 제작 인계에 필요한 승인 범위 내 정상 요청을 기록한다. 공급자 오류·쿼터·권한·결제·전송 미확정에서 중단한다. 자동 재시도·공급자 전환은 사용하지 않는다.
