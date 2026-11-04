# Gemini 3.5 Flash-Lite 신규 프로젝트 연동 및 첫 완주 준비

2026-11-04 KST. `git pull --ff-only`로 951699e 반영. 핵심 원칙·AGENTS.md·한국어 규칙·지정 지시서와 기존 Gemini adapter/company/store/launcher/동의/역할 schema 및 내부 도구 수정 테스트를 확인했다.

**기존 Gemini 3.1 프로젝트를 변경하지 않고, 3.5 전용 신규 프로젝트의 최초 실행 전까지 준비했다. 이번 실제 AI API 호출 0회, 기존 프로젝트 execute/run/continue/approve 0회다.** 단건 연결·관리자 형식 진단의 200 성공은 지시서의 선행 사실이며, 실제 회사 완주/지속 안정성의 증거로 확대하지 않는다.

## 최소 격리 변경

- `autonomous_gemini35.py`: 고정 모델 `gemini-3.5-flash-lite`, 정확한 generateContent endpoint, 별도 Gemini35Adapter/Config/Store/Company를 추가했다. 3.1 회사의 계획·직원 실행·manager review/revision·인계·최종 보고 구현을 상속해 재사용한다.
- `gemini35_first_project.py`: 3.5 전용 prepare/execute 명령. 기존 비밀 없는 합성 목표 템플릿으로 새 프로젝트를 생성한다. 과거 프로젝트의 goal/plan/직원 결과를 읽어 복사하지 않는다. O_EXCL 시작 소진 표식과 최초 서명 동의·상태 hash 검사를 유지한다.
- `autonomous_gemini.py`: 고정 binding/adapter/비용 정책·환경변수 이름을 클래스 속성으로 분리했다. **기본 값은 기존 3.1 그대로**이며 model/endpoint allowlist를 넓히거나 환경값에 따라 임의 모델을 선택하지 않는다.
- `gemini_provider.py`: build_request의 endpoint를 해당 어댑터의 고정 ProviderSpec에서 얻는다. 기존 GeminiFreeAdapter의 spec은 3.1 그대로이고 새 Gemini35Adapter의 spec만 3.5다. 출력 정규화·strict 역할 schema·실패 진단은 재사용한다.
- `tests/test_autonomous_gemini35.py`, 이 보고서.

새 marker는 `.autonomous-gemini35-free-v2-store`, mode=`autonomous_gemini35_free_v2`, policy=`gemini35_free_v2`, prefix=`gemini35company-`다. 기존 `.autonomous-gemini-free-v2-store` 및 gemini_free_v2는 유지했다. 서로 다른 store 로더로 읽으면 차단하며, 기존 3.1 계약·3.1 모델/endpoint·이전 비용 정책을 새 3.5 승인에 사용할 수 없다.

3.5 실행 설정은 GEMINI35_MODEL/GEMINI35_ENDPOINT/GEMINI35_AUTONOMOUS_FREE_ENABLED로 분리했다. 비밀키는 기존 GEMINI_API_KEY를 메모리에서만 사용한다. 3.1의 GEMINI_MODEL/GEMINI_ENDPOINT/활성화 설정을 덮어쓰지 않는다. 원래 `gemini_first_project.py`와 기존 `--provider gemini` CLI의 3.1 경로는 호환성 보존을 위해 유지하며, **새 3.5 프로젝트는 새 전용 launcher를 사용한다**. 자동 fallback·자동 이전·기존 동의 재사용은 없다.

## 공식 모델·무료 조건 확인

2026-11-04에 공개 문서만 조회했다. [공식 모델 페이지](https://aistudio.google.com/docs/models/gemini-3.5-flash-lite)는 stable ID `gemini-3.5-flash-lite`와 Structured outputs 지원을 명시한다. [공식 가격표 Standard Free Tier](https://aistudio.google.com/docs/pricing#gemini-3.5-flash-lite)에서 입력과 출력(생각 토큰 포함)이 무료임을 확인했다. 모델 음성 생성 기능을 추가한 것이 아니며 한국어 음성은 기존 로컬 espeak-ng다.

현재 프로세스의 GEMINI_API_KEY 존재 bool=true만 확인했다. Google 계정의 실시간 billing/free tier를 인증 API로 조회하지 않았다. 기존 사용자 Free Tier 확인 및 별도 성공 진단은 준비 근거이며 실행 때 해당 키 프로젝트가 여전히 무료임을 사용자 confirm-free-tier로 확인해야 한다. 가격표와 프로젝트 실제 결제 등급은 별개다. 무료 쿼터/속도 제한의 현재 잔여량도 조회하지 않았다. 유료 설정/모델·다른 공급자·계정 대체는 추가하지 않았다.

정확한 endpoint는 `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`다. 네이티브 systemInstruction/contents/generationConfig의 responseJsonSchema·JSON MIME을 유지한다. manager/employee/review/finalize 모두 같은 고정 3.5 binding으로만 송신할 수 있다. schema 검증·4096 출력 토큰/바이트 제한·사용량 확인·원장 선예약·HTTP/실패 분류·동의/비용/쿼터·중복 보호는 이전과 같다. 출력 cost 필드 부재를 청구액0 증명으로 바꾸지 않으며 서명된 무료 계정 정책을 비용 근거로 사용한다.

## 오프라인 검증

```bash
python -B -m unittest tests.test_autonomous_gemini35 tests.test_autonomous_gemini tests.test_internal_tool_review tests.test_autonomous_groq tests.test_autonomous_free tests.test_autonomous_live
```

**79개 통과, 실패/오류0, exit0 (37.733초).** 외부 socket/DNS를 차단한 임시 store·가짜 키·fake 네이티브 응답만 사용했다.

- 새 3.5 endpoint/헤더/모든 역할 단계 binding, 기존 3.1 adapter endpoint 유지, 양방향 store 격리, 다른 모델/endpoint/비용 정책 동의안 차단, 잘못된 review hash·중복 준비·미승인 실행 차단을 확인했다.
- 3.5 fake manager→첫 직원 도구 실패(caption_overflow/local_tool_failed/narration_exceeds_scene)→manager revise→직원 수정→실제 로컬 renderer MP4→manager accept→다른 직원에 선행 인계→final.md 시나리오를 검증했다. 수정은 가짜 모델의 선택이며 production에 업무 판단을 고정하지 않았다.
- 관리자 stop/운영 권한 요청/실패 결과 부당 수락 차단, task/전체 revision 상한·정체 차단, hard safety 오류 정지, review API429 실패 후 active_operation/실패 원장 보존, crash 전후 중복 API 재송신 차단을 재검증했다.
- 기존 Gemini3.1/Groq/OpenRouter 경로 및 역할 JSON 계약 회귀도 통과했다. 로컬 receipt·디코딩·실제 파일 무결성 검사와 모델의 의미/미적 품질 판단은 구별한다.

이 결과는 **오프라인 fixture 성공**이며 실제 Gemini 3.5 회사 완주가 아니다. 독립 진단 스크립트는 import/실행/초기화하지 않았다. 기존 UI·미디어 기능·자막/품질 기준은 변경하지 않았다.

## 기존 기록 보존

기존 data/backups/checkpoints와 지정 3.5 진단 스크립트 두 개를 합친 **103개 파일의 SHA256 전후 모두 동일**을 확인했다. 기존 사용자 미추적 파일도 건드리지 않았다. `.env`/키/계정·billing/proxy/TLS 설정 변경0, reset/clean/force push0이다.

기존 GeminiStore 로더로 실제 3.1 저장소 3개가 무결성 load되는 것을 읽기 전용 확인했다. 첫 번째는 stopped/work/caption_overflow·시도2, 두 번째는 stopped/work/local_tool_failed·시도2, 세 번째는 paused/plan/provider_unavailable·시도1이다. 기존 각 model/endpoint/consent/status/hash 및 active_operation·소진 표식은 그대로다. 새 3.5 모델로 호환시켜 실행하지 않았다. 과거 503·로컬 오류를 새 성공으로 소급 표시하지 않는다.

`git diff --check` 통과. Git에는 비밀 없는 소스·테스트·보고서만 선택적으로 저장한다. 새 프로젝트 상태/동의안은 Git 제외 data 경로에 둔다.

## 신규 3.5 프로젝트 준비 상태

실행한 준비 명령은 `python -B gemini35_first_project.py prepare` 하나이며 실제 송신은 없다.

- store: `data/gemini35-first-autonomous-20261104`.
- project: `gemini35company-2b01639ee7284443b5c68dfdae206949`.
- 상태 ready, enabled=false, attempts=0. grant·서명 키·시작 소진 표식 없음.
- 최초 동의안 발행: 2026-11-04T15:31:13+09:00, 만료: **2026-11-05T15:31:13+09:00**. 무료 등급 확인의 24시간 조건도 적용한다.
- 목표: 개인·회사 비밀 없는 합성 AI 질문 작성법을 한국어 자막·로컬 음성 20~30초 MP4와 최종 보고서로 제작. 실제 계획/담당/품질 기준/수정 판단은 모델이 정한다.
- 외부 전송: 목표, 생성 계획/기준/배정, 직원 제출물 및 안전한 도구 실패 메타데이터, 관리자 검토, 최종 통합. 원문 stderr/키/환경값/외부 파일/실제 사업정보 전송은 포함하지 않는다.
- 로컬 도구: 기존 caption_video_v1. 비용0/무료 모델만, 유료 fallback·자동 API retry 없음. 기존 수정/정체/시간/공급자 한도와 receipt/실제 MP4 검증을 유지한다.
- tool_failure_review=1의 새 정책을 동의안에 포함했다. 실패한 직원 제출물을 관리자 검토 자료로 보존하고, 관리자가 수정/정지/운영 권한 요청을 결정한다. 실패 도구를 성공으로 accept하지 못한다.

새 정책·목표·무료 등급·전송 범위를 검토하고 신규 프로젝트 최초 실행에 동의한 뒤 Codespaces 터미널에서 실행할 명령은 다음 하나다. **이번에는 실행하지 않았다.**

```bash
python -B gemini35_first_project.py execute --review-hash b630b2780910935526291862aed53263cb2e4a0f20ff76f7f773ff9625eb920c --owner-confirmed --confirm-free-tier
```

남은 검증은 실제 3.5 manager↔employee 협업·내부 검토/수정·최종 MP4/보고 완주와 서비스 안정성이다. 단건 성공이 이를 보장하지 않는다. 이번 변경은 검증된 새 모델을 기존 자율 회사 경로에 연결해 실제 완주 준비를 마쳤고, 정상 흐름에 사용자 업무 중간 결재를 추가하지 않았다. 기존 수동 프로젝트의 승인 부채는 변경하지 않았다. 최초 프로젝트 운영 동의만 다음 실행의 안전 경계로 남는다.
