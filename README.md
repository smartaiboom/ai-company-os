# AI Company OS

AI Company OS는 **공통 AI 회사 운영 엔진**을 기반으로 분야별 전문 AI 회사를 운영하는 시스템이다. 버전마다 폴더를 복제하지 않고, **전문 회사별 폴더**로 확장한다.

## 현재 구조

```text
ai-company-os/
├── core/                 # 공통 AI 관리자·직원 실행 엔진, 모델/안전/비용/저장 로직
├── companies/
│   └── video/            # 현재 1차 전문 회사: 영상 제작
├── tests/                # 현재 유지할 간결한 핵심 테스트
├── docs/                 # 현재 유효한 설계 문서
├── AGENTS.md             # 개발 원칙
└── README.md
```

- `core/`: 기존 검증된 Python 공통 엔진 14개 모듈. 필요 이상의 재개발이나 파일 복제를 피한다.
- `companies/video/`: 기존 영상 회사 프로필 및 렌더러 2개 모듈. 실제 영상 품질 향상은 앞으로 개발한다.
- `companies/product/`, `companies/software/` 등은 필요할 때 추가한다.
- `tests/`: 기존 협업 엔진을 사용하는 독립 모의 테스트 4개. 전체 기능 검증이 아니므로 실제 제품 개발 시 필요한 검증을 묶어 보강한다.
- `docs/ARCHITECTURE.md`: 현재 구조와 다음 개발 계획.

## 실행·개발 주의

현재 import는 단일 패키지가 아니라 파일명 기준이므로 로컬에서 다음 경로를 지정한다.

```bash
PYTHONPATH=core:companies/video python -B -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPATH=core:companies/video python -B -c 'import video_production_company, autonomous_gemini35'
```

새 폴더 경로에서 기존 핵심 4개와 목표 문답 통합 3개 테스트를 통과했다. 목표 문답 CLI는 오프라인 및 승인 보호 Gemini 연결 경로를 제공한다. 실제 전송 운영 검증·산출물 품질 검토·경험 재사용은 후속 개발 대상이다.

## 과거 자료 정리

이전 `phase1/` 보관본, 일회성 이관 스크립트, 과거 검증 보고서는 **현재 Git 작업 트리에서 제거**했다. 다만 Git 커밋 이력에는 남아 있어 필요할 경우 이전 커밋에서 열람·복원할 수 있다. 현재 제품용으로 쓸 코드/테스트는 위 폴더에 보존했다.

GitHub에 없는 과거 로컬 데이터·원장·백업·비밀키는 삭제/이동하지 않는다. 앞서 Codespaces에서 실행한 로컬 보관 스크립트로 생성된 `/workspaces/ai-company-os-local-archive-XXXXXXXX/`는 GitHub에 포함되지 않으며 보존해야 한다.

## 목표

사용자 목표 → AI 관리자의 필요 질문 → 전문 AI 직원의 실제 제작 → 결과물 검토·수정 → 사용자 평가 → 경험·성공 방식 저장 → 다음 작업에서 재사용 및 성능 비교. 장기적으로 사용자 개입을 줄이고 회사의 자율 운영을 강화한다. 향후 AI Company OS vs ChatGPT 비교 콘텐츠로 품질·효율 변화 검증.

## 목표 구체화 문답 (오프라인)

```bash
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli create '안전 교육 영상'
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli show <초안ID>
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli propose <초안ID> proposal.json
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli answer <초안ID> audience '초등학생'
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli skip <초안ID> duration
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli revise <초안ID> spec.json
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli confirm <초안ID> <show의-review_hash>
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli handoff <초안ID>
```

모든 명령은 동일 ID로 재개한다. 기본 저장소는 `data/goal_dialogues`, 새 영상 초안은 `data/dialogue_video_projects`이며 기존 저장소와 분리한다. `--root`는 하위 명령 앞에 지정한다. `handoff`는 초안 생성만 하며 실행·운영 동의를 부여하지 않는다.

현재 `propose`는 사용자가 준비한 **오프라인 JSON 제안**을 읽는다. 실제 AI 판단이 아니며 고정 질문 생성기도 제공하지 않는다. 테스트에서만 누적 답변에 따라 질문을 바꾸는 모의 관리자를 사용한다. 오프라인 모드는 실 AI 질문을 허용하지 않는다. 별도 Gemini 모드의 승인 경로와 기본 차단 정책은 아래를 참고한다.

제안 형식은 `{"questions":[{"id":"audience","text":"누가 보나요?","reason":"설명 수준 결정"}],"sufficient":false,"spec":{...}}`이다. 충분하면 `questions:[]`, `sufficient:true`를 사용한다. 명세는 아래 형식이며 모든 필드가 필요하다.

```json
{
  "audience": {"value":"미정", "evidence":[]},
  "deliverable": {"value":"안전 교육 영상", "evidence":["goal"]},
  "style": {"value":"미정", "evidence":[]},
  "quality": {"value":"미정", "evidence":[]},
  "constraints_budget": {"value":"미정", "evidence":[]},
  "summary":"확인할 영상 요구사항",
  "assumptions":["근거가 없는 항목은 미확정 가정"]
}
```

`evidence`는 원래 목표 `goal` 또는 현재 답변의 질문 ID이다. 근거가 없는 값은 추정이다. 참조는 해석의 정확성을 보증하지 않으므로 사용자가 명세를 검토·수정하고 해시로 확정한다. 정정 시 기존 명세는 폐기된다. 라운드 한도는 기본 4회(최대 8회), 질문은 회당 1~3개다. 실패·중단된 제안은 자동 재호출하지 않으며 `revise`로 명세를 직접 검토해 복구할 수 있다. 확정 후 변경은 새 초안으로 시작한다. 목표·명세·답변 전체의 계획 입력이 기존 엔진의 4,000자 한도를 넘으면 연결을 차단한다. 비밀키는 입력하지 않는다(일반 키 패턴은 저장 전 차단하지만 완전한 비밀 탐지는 보장하지 않는다).

## Gemini 관리자 문답 (별도 저장소·실제 전송 기본 차단)

새 초안은 `--live`로 생성한다. 기존 오프라인 초안을 승격하지 않는다. JSON 파일 없이 다음 흐름으로 준비·승인·질문·답변·수정·확정할 수 있다.

```bash
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli --live create '어린이 안전 교육 영상'
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli --live prepare-consent <ID>
# 표시된 전송 내용, 모델, 한도, 무료 계정 여부를 실제로 검토한 뒤에만 승인한다.
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli --live approve-consent <ID> <검토해시> --owner-confirmed --verified-free-project
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli --live ask-ai <ID>
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli --live answer <ID> <질문ID>
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli --live revise <ID> --text '친근한 애니메이션으로 바꿔 주세요'
# 답변/수정 후 prepare-consent → approve-consent → ask-ai를 다시 수행한다.
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli --live show <ID>
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli --live confirm <ID>
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli --live handoff <ID>
```

`answer`는 값을 생략하면 질문을 보여주고 입력받는다. `confirm`은 명세를 표시하고 명시적인 최종 확인을 받는다. `revise --text`는 다음 관리자에게 보낼 사용자 수정이며 확정 전에 재검토가 필요하다. 기존 JSON `propose`/`revise`, `skip`, 해시를 지정하는 `confirm`도 유지한다. 출력은 기본 한국어이며 자동화 도구는 전역 `--json`을 사용할 수 있다. `--live`를 사용하면 `data/goal_dialogues_gemini35`에 별도 표식·서명키·동의·시도 원장을 저장한다. `--root`로 기존 오프라인 저장소를 지정해도 변환되지 않고 거절된다.

동의는 현재 목표·질문/답변·사용자 수정·현재/사용자 수정 명세·라운드 한도와 **정확한 요청 해시**에 묶인 1회 전송이며 1시간 만료다. 입력이 바뀌면 재승인해야 한다. 원래 목표를 바꾸려면 새 초안을 만든다. 기본 총 호출 한도는 4회(`create --max-rounds 1~8`), 실패·중단 예약도 소모한다. 타임아웃/잘못된 응답/중단 후 재시도와 원장 초기화는 지원하지 않는다. 사용자가 명세를 직접 검토하는 기존 경로는 유지하되 미확정 호출은 계속 차단한다. 영상 초안 생성은 영상 실행 동의가 아니다.

실제 전송은 `core/goal_dialogue_live.py`의 정책 게이트에서 **비활성**이다. API 키, 환경 플래그, `--owner-confirmed`, `--verified-free-project`만으로 활성화할 수 없다. 계정/키의 무료 프로젝트 연결을 독립적으로 확인하는 운영 검증이 아직 없어 비용 0을 보장할 수 없기 때문이다. 구현된 Gemini wire 경로는 통합 테스트에서만 모의 HTTP로 실행한다. 키는 향후 `GEMINI_API_KEY`로만 읽으며 저장·출력하지 않는다. 게이트를 단순히 켜는 것을 무료 검증의 대안으로 사용하면 안 된다.

2026-11-09 KST 공식 문서 확인: [모델](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [가격](https://ai.google.dev/gemini-api/docs/pricing), [한도](https://ai.google.dev/gemini-api/docs/rate-limits). `gemini-3.5-flash-lite`와 구조화 출력 지원, Standard 무료 티어와 유료 티어의 구분을 확인했다. 계정별 실제 쿼터·무료 이용 가능성은 확인하지 않았다. 무료 서비스 입력이 제품 개선에 사용될 수 있으므로 전송 동의 전에 제공자 정책도 확인한다. 유료 전환·모델 대체·검색/도구 호출·자동 재시도는 없다.

## Gemini 실제 1회 인수 테스트 준비

일반 `--live` 전송 차단은 유지한다. `--acceptance`는 지시서의 가상 목표 하나만 허용하는 별도 저장소(`data/gemini_one_call_acceptance`)다. 저장소당 초안은 하나이며 예약·실패·중단을 포함해 API 요청은 최대 1회다. 첫 응답에 질문을 허용하기 위해 문답 라운드는 2로 표시되지만 **실제 호출 예산은 1회**이며 후속 질문 전송은 불가능하다. 영상 회사 handoff도 차단한다.

```bash
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli --acceptance create
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli --acceptance prepare-consent <ID>
# 아래는 사용자가 해당 프로젝트의 Free 등급/Billing 비활성 및 키를 직접 확인한 후에만 수행한다.
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli --acceptance verify-acceptance-key <ID> --free-tier-confirmed --billing-disabled
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli --acceptance prepare-consent <ID>
# 재준비 출력의 전체 요청·한도·만료·해시·Google 데이터 정책을 검토하고 명시적으로 승인한 뒤에만:
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli --acceptance approve-consent <ID> <새 검토해시> --owner-confirmed --verified-free-project --accept-google-data-policy
# 별도로 승인받은 시점에만 실행한다. 실패해도 반복하지 않는다.
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli --acceptance ask-ai <ID>
```

키 대조는 AI Studio의 `Default Gemini Project`에서 사용자가 복사한 키와 현재 `GEMINI_API_KEY`를 비표시 로컬 터미널 입력으로 비교한다. **키를 채팅·명령 인수·로그에 넣지 않는다.** 비표시 입력이 보장되지 않으면 거절한다. 원격 프로젝트 조회나 추가 API 호출은 없으며 로컬 HMAC 결합만 저장한다. 키 대조와 Free/Billing 확인은 사용자 확인 근거이고, 제공자 측 계정 조회나 실시간 쿼터 검증이 아니다. 스크린샷/환경키 존재만으로 검증·승인을 대신하지 않는다. 계정·결제 상태가 불명확하면 전송하지 않는다.

키 대조 후에는 반드시 동의를 다시 준비한다(상태·승인 해시 변경). 키 변경·서명 변경·입력 변경·1시간 만료 시 차단한다. 전송 본문과 scope/payload 해시는 `prepare-consent` 출력과 해당 초안의 `.review.json`에서 확인한다. 인증키는 본문/검토 파일에 포함하지 않으며 고정 Google endpoint의 인증 헤더에만 사용한다. 무료 입력·응답은 [Google 정책](https://ai.google.dev/gemini-api/terms)에 따라 제품 개선 및 사람의 검토에 이용될 수 있다. 비용 정책은 0원/무료 전용이지만 계정별 무과금·남은 쿼터를 코드가 보장하는 것은 아니다. 유료 전환·자동 재시도·fallback·영상 실행은 없다. 성공 시 검증된 토큰 usage를, 실패 시 제한된 오류 범주/HTTP 상태만 기존 시도 원장에 남긴다.

## 수입한 영상 클립으로 9:16 쇼츠 제작 (오프라인)

기존 SVG/espeak 제작 계약은 유지하며, 새 경로는 `companies/video/ai_clip_pipeline.py`다. 외부 생성/로그인/업로드를 자동화하지 않는다. Flow·Pika·Kling 등은 **manual_import**이며 현재 무료·상업 이용·워터마크 조건은 기본 미확인이다. 웹 크레딧과 API 비용은 별개다. 향후 API 공급자는 SceneProvider 계약으로 추가할 수 있지만 DisabledAPIProvider는 항상 실행을 거절한다.

```bash
# 기존 대본에서 3개 장면/클립 프롬프트를 만드는 Codex 기준선 (실 AI 관리자 호출 아님)
PYTHONPATH=core:companies/video python -B -m ai_clip_pipeline baseline data/video_ai_clip_review/my-job
# 또는 관리자/사용자가 준비한 scene_plan.json으로 생성
PYTHONPATH=core:companies/video python -B -m ai_clip_pipeline create data/video_ai_clip_review/my-job scene_plan.json
# 사용자가 웹 서비스에서 직접 생성·다운로드한 원본과 권리 근거를 inbox에 보관한 뒤 수입
PYTHONPATH=core:companies/video python -B -m ai_clip_pipeline import data/video_ai_clip_review/my-job data/my-inbox scene1.mp4 scene-1 source.json
# 모든 장면을 수입한 후, 기존 MeloTTS 환경으로 로컬 합성/편집
PYTHONPATH=core:companies/video python -B -m ai_clip_pipeline render data/video_ai_clip_review/my-job
```

새 job 폴더는 없어야 한다. `baseline`과 `create` 중 하나만 사용한다. 장면별 파일을 수입해야 하며 duplicate hash·경로 이탈·symlink·가짜 확장자·비정상 미디어는 거절한다. 원본은 바꾸지 않고 해시를 검증한 복사본만 사용한다. `fixtures <새 inbox>` 명령은 로컬 코덱 테스트 영상을 생성하며 **AI 영상이 아니다**. source.json 예제도 함께 생성하므로 형식을 확인할 수 있다. 실제 클립은 provider, external_ai_clip 근거, KST 생성시각, license/terms_url/usage_rights, commercial_use, allowed_to_publish, watermark, rights_verified/rights_evidence, estimated_cost/actual_cost를 해당 원본에 맞게 기록한다. 자동으로 권리를 검증했다고 간주하지 않는다.

기본 720×1280 레터박스는 피사체와 워터마크를 보존한다. crop은 계획에 명시하고 워터마크 absent 확인이 필요하다. 짧은 클립 반복은 `allow_repeat`가 true일 때만 허용하고 횟수를 기록한다. 원본 음성은 버리고 로컬 MeloTTS를 사용한다. 측정된 음성이 총 길이를 넘으면 실패하며 임의로 가속하거나 자르지 않는다. 24fps 타임라인과 60/60/180px 좌우/하단 안전여백의 한국어 자막을 합성한다. 발화 경계는 실측, 구절별 자막 시간은 문자 비중 추정으로 단어 정렬을 보장하지 않는다.

MeloTTS는 기존 `data/tts_korean_review` 런타임/모델을 읽기 전용 재사용하고 실행 중 네트워크·DNS를 차단한다. 다운로드/자동 재시도/espeak 대체는 없다. 실행이 중단·실패한 job은 덮어쓰거나 재실행하지 않고 파일을 보존한다. 최종 MP4/음성/ASS·SRT/타임라인/원본 영수증/키프레임은 job 폴더에 저장하며 권리 미확인 시 publish_ready=false다. fixture가 하나라도 있으면 pending_external_clip이며 AI 클립 완성본이 아니다. 영상 회사의 `offline_clip_decision_context()`/`create_offline_clip_job()`은 향후 관리자 계획 입력 경계이며 기존 LiveCompany 권한·도구 목록을 확대하지 않는다.

```bash
# 기존 회귀 + 새 단위/미디어 테스트 (짧은 합성 테스트 음성 사용)
PYTHONPATH=core:companies/video python -B -m unittest discover -s tests -v
# 실제 MeloTTS와 60초 기술 시안까지 한 번에 검증: 새 경로를 지정
AI_CLIP_ACCEPTANCE_ROOT=data/video_ai_clip_review/my-acceptance PYTHONPATH=core:companies/video python -B -m unittest discover -s tests -v
```

## 관리자·직원 품질 루프와 피드백 (오프라인 계약 검증)

`core/quality_feedback.py`는 기존 Store를 사용하는 별도 경험 저널과 계획 컨텍스트를,
`companies/video/quality_workflow.py`는 기존 Company를 사용하는 영상 품질 어댑터를 제공한다.
새 빈 로컬 폴더의 `Store.create(..., opt_in=True)` 결과에 `bind_context()`로
`answers/constraints/capabilities/experiences/permissions`를 한 번 결합하고,
`VideoQualityCompany(store, MockManagerProvider(...), MockEmployeeProvider(...)).run(id)`로 실행한다.
`capabilities()`가 역할별 입력·출력 계약과 수동 클립 수입 경계를 제공한다.
`permissions`는 정확히 `{"external_calls": false, "cost_limit": 0}`이어야 한다.
기존 사용자 프로젝트 저장소를 지정하지 않는다.

피드백은 원문과 명시적으로 구조화한 값으로 `ExperienceJournal.record()`에 저장하고,
`select(domain=..., target_segment=...)`의 선택/제외 기록을 다음 프로젝트 컨텍스트에 전달한다.
`record(..., replaces=id)`와 `withdraw()`는 수정·철회 이력을 보존한다.
현재 자동 자연어 추론기는 없으며, 제공되는 모의 시나리오는 실제 AI 판단이 아니다.
역할별 향후 모델 지시는 `ROLE_CONTRACTS`에 있지만 실제 provider 전송을 활성화하지 않는다.

```bash
PYTHONPATH=core:companies/video python -B -m unittest tests.test_quality_feedback -v
```

샘플은 테스트가 만드는 임시 저장소에서 실행된다. `QUALITY_SAMPLE_OUTPUT=/tmp/<파일명>.json`을
지정하면 대본/샷 계획의 수정 전후 버전, 검토, 경험 적용/비적용 데이터를 보존한다.
실제 미디어가 없는 이 계획 경로는 `external_clip_pending`으로 끝나며 완료·게시 승인을 하지 않는다.
10점 체크리스트의 감각 품질은 미평가로 남긴다. 실제 모델·영상 품질 개선은 별도 승인·검증 대상이다.

## 품질 작업의 실AI provider 연결 준비

`core/quality_provider.py`의 `QualityProviderStore`와 영상 회사의
`VideoProviderQualityCompany`는 기존 mock 경로와 분리된 실AI 전용 모드다.
기존 Gemini35 native 어댑터·서명 동의·호출 원장·엄격한 역할 JSON 검증을 재사용한다.
새 빈 저장소에서 `create(goal, inputs=..., max_calls=...)`로 준비한다. inputs 필드는
`domain/target_segment/answers/constraints/capabilities/experiences/feedback_text`이며,
영상 capabilities는 `quality_workflow.capabilities()`를 쓴다.
선별 경험은 `quality_provider.experience_context(selection)`으로 전송 필드만 투영한다.

`prepare()`는 전송 입력과 해시를 포함한 동의 제안을 만들며 승인을 뜻하지 않는다.
**실제 전송은 코드 정책에서 비활성**이고 키·환경변수·서명 동의만으로 활성화되지 않는다.
기존 인수 저장소를 지정하거나 기존 동의를 재사용하지 않는다. 현재 계정의 무료 등급·결제·키 연결 확인과
별도 실제 호출 승인/활성화 절차는 후속 작업이다. 비용 0은 계정 상태 검증 없이 보장하지 않는다.

writer/editor/voice/qa/feedback 작업은 모델이 의존성과 함께 배정한다.
직원은 선행 결과/해시·이전 버전·관리자 수정 지시를 받는다. QA의 텍스트 평가는 모델의 주장이고
수치 검사와 별개이며 실제 미디어가 없으면 감각 점수는 미평가다.
승인된 feedback 직원 결과를 `record_feedback()`으로 수신·검증하고
`select_feedback()`으로 대상별 선택, `withdraw_feedback()`으로 철회한다.
`record_feedback(..., replaces=id)`는 새로 검증된 직원 결과로 대체할 때 버전을 남긴다.
실제 전송을 하지 않는 계약 검증은 다음으로 실행한다.

```bash
PYTHONPATH=core:companies/video python -B -m unittest tests.test_quality_provider -v
```

테스트만 HTTP를 대체하고 차단 정책을 메모리에서 임시 교체한다. 소켓과 DNS는 차단된다.
`PROVIDER_SAMPLE_OUTPUT=/tmp/<파일명>.json`으로 요청/수정/QA/피드백 샘플을 보존할 수 있다.
상세 결과·필수 승인 게이트는 `reports/manager_staff_provider_readiness_result.md`를 참조한다.
