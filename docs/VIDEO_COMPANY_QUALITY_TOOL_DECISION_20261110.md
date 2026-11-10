# 영상제작 회사 — 품질개선 실행·도구 선별 2단계 (2026-11-10 KST)

## 최상위 방향
**현재는 영상제작 전문 AI 회사의 2단계(결과물 품질 향상)**. 1단계 관리자/직원 구조를 재설계하거나 재구축하지 않는다. 목표: 사용자는 하나의 영상 목표를 주고, 영상제작 회사의 관리자/전문 직원이 주제/대본/화면/음성을 결정·제작·평가·개선한다. 제작 도구의 품질 한계가 확인되면 **실제 AI 직원이 API로 직접 호출할 수 있는 유료 도구 도입을 제안**한다. 사람이 매번 Flow/CapCut에서 만들어 수동 업로드하는 것을 운영 목표로 삼지 않는다. UI는 게시 수준의 실물 결과를 사용자에게 인정받은 다음.

**작업 지시서이며 이번 턴에서 코드·검증·보고까지 수행한다. 문서만 읽고 종료하지 말라.** 재질문 없이 기존 작업을 진행하되 새로운 유료 API 호출/다운로드/가입·결제/사용자 자산 외부 업로드는 사용자 별도 승인 없이는 절대 실행 금지.

## 선행 확인 / 중복 작업 금지
- AGENTS.md, docs/OPERATIONS_READINESS_GATE.md, reports/manager_staff_feedback_engine_result.md, reports/manager_staff_provider_readiness_result.md, reports/VIDEO_QUALITY_ITERATION_RESULT.md, reports/USER_FEEDBACK_QUALITY_UPGRADE_RESULT.md, reports/QWEN_TTS_AB_RESULT.md, reports/CURRENT_PROGRESS.md를 확인.
- core/quality_provider.py, core/quality_feedback.py, companies/video/quality_workflow.py, companies/video/ai_clip_pipeline.py, companies/video/editorial_video.py, companies/video/audience_visual_review.py, companies/video/local_melo_tts.py와 테스트 분석. 기존 구현에 있는 것부터 재사용. 모의 fixture와 실제 AI 호출, Codex 편집 판단은 엄격히 구분.
- 11/9 Flow 3클립 60초 시안, 11/10 로컬 카드형 60초 시안, 15초 motion 검토, A Melo 음성, Qwen B 미생성 상태와 기존 모든 사용자 자료 및 원장 보존. 강제 reset/clean, 재생성·모델 설치 재도전 금지.

## 실제 사용자 의견 — 영상제작 회사 개선에 직접 반영
- 영상 두 편 모두 체감 개선이 크지 않다.
- 이미지·영상이 부족하고 정적 카드 중심으로 지루하다.
- MeloTTS 음성은 CapCut에서 들어 본 자연스러운 TTS보다 어색하다.
- 대본은 최신 관심과 실제 시청자 수요를 반영하는 소재여야 정확히 평가할 수 있다.
- **현재 Qwen0.6B 로컬 CPU 시험은 가용RAM 3.89GB < 안전 기준6.5GB로 정지. 동일 사전검사·코드만 되풀이하지 마라.** 로컬 Qwen은 현재 상태에서 실행 불가라고 분류하되 추후 실행 환경 개선 가능성은 열어 둔다.

## 이번 작업의 중점 1 — 원인별 품질 진단 및 도구 비교
- 대본/기획의 부족은 모델/프롬프트/QA 판단 문제인지, 시각/음성 부족은 실제 생성 도구 문제인지 구분. 시청자가 확인한 ‘큰 차이 없음’ 평가를 기술 점수 통과로 덮지 말 것.
- **트렌드**: 한국어 쇼츠 시청자에게 실용적이고 시각적으로 시연 가능한 주제 3개를 출처·조회 일자·사실/추정 구분과 함께 비교하고 1개를 고른다. 리서치 도구가 실시간 검색 불가능하면 최신 유행이라고 가장하지 말고 가능한 범위 내 공개 근거 기반 선정.
- **대본**: 주제/타깃/핵심 가치를 동시 설계, 3초 후크→구체적 실험/데모→결과의 검증/주의→간결한 마무리. 60초 대본 초안/관리자 평가/수정 대본과 사실 검증표를 새 작업 폴더에 기록. 사용자에게 트렌드 선정만 여러 번 반복하지 않는다.
- **영상**: 텍스트 카드만 반복하는 방식과 7~8초짜리 Flow 클립을 20초 쓰는 방법 모두 제외. 실제 장면/이미지/화면 시연 비중 및 확보 가능 여부를 초별 샷플랜과 해시·권리·비용/모델별로 정리. AI 직원이 직접 생성·수입·검사하는 어댑터 기반 도구 경계가 없는 것은 명시적 개발 과제로 삼는다.
- **음성**: 기존 MeloTTS CapCut 기준 미달이라는 사용자 평가를 확정 근거로 반영. RAM 부족으로 Qwen 재시도하지 말고, **외부 자동 API TTS** 후보를 비용·한국어·보이스 예시·상업권·API 연동·요청한도 기준으로 평가. 무료라도 상업 사용 불가면 게시 후보에서 제외. 유료 후보는 구체적인 60초 한국어 1편/10편 예상 과금 범위와 가장 작은 A/B 실험 단가를 계산하되 가격은 공식 자료를 확인하고 미확인이면 미확인으로 표시.
- 영상 API 예: Runway Dev image_to_video 문서 https://docs.dev.runwayml.com/api/, 현재 모델별 요금 https://docs.dev.runwayml.com/guides/pricing/ ; Kling 공식 개발자 문서 https://kling.ai/dev/model/image ; **출처·계정 별 실제 API 가격/요금과 구독 웹 크레딧의 차이** 확인.
- TTS API 예: ElevenLabs 한국어 공식 문서 https://elevenlabs.io/docs/ko/overview/capabilities/text-to-speech 및 공식 요금 https://elevenlabs.io/ko/pricing/api ; Google Cloud TTS 공식 요금 https://cloud.google.com/text-to-speech/pricing?hl=ko . ElevenLabs 무료 tier의 상업 라이선스/보이스 라이브러리 제한, Google 청구계정/API 활성화 여부를 확인. 공짜라고 무조건 API 호출하지 않는다.
- 모델/서비스 추천은 **실제로 직원이 자동 호출 가능한지**를 최우선으로, 품질 수준은 샘플을 듣기 전 미검증으로 구분. 임의로 특정 공급자 가입/키를 요구하거나 과금하지 않는다. 동일 공급자가 영상과 이미지까지 제공할 수 있으면 운영/원가 장점 평가.

## 이번 작업의 중점 2 — AI 직원의 실제 도구 사용 준비를 코드로 구축
- 기존 영상/음성 공급자 계약을 재사용해서 회사의 전문 직원에게 **구체적인 품질 스펙, 도구 입력, 준비 상태, 단일 작업 비용 상한, 결과 검증/권리, 실패·재시도 차단**이 전달되게 하는 최소의 provider-neutral capability/quality adapter를 구현한다. **이미 있는 기능이면 추가 구현 없이 그대로 재사용**하고 실제 부재한 기능에만 투자.
- 단순 JSON 계획 생성 또는 mock을 자율 AI 운영으로 포장 금지. 실제 모델/API 키가 없으면 해당 경계를 offline 검증하고, 실제 생성 불가와 필요한 최소 승인 사항을 명시. 유료 API 실제 요청은 없음. 실제 LLM/영상/TTS 외부 호출·결제·업로드/게시 금지.
- 작업 선택 예제 1개를 통해 관리자→대본 직원→영상·음성 직원→QA로 전달하는 **코드 실행 가능한 계약**을 검사. 예전 fixture 복사로 결과물이 좋아졌다고 주장하지 말고, 새 실제 입력과 각 계약의 블로커/원인을 기록.
- 비밀키를 파일·GitHub에 저장하지 말 것. 사용자 결제 계정/자동 결제/전환은 절대 진행하지 않는다.
- 수치검사 통과와 영상미/자연스러움 평가 차이를 유지. 새 외부 자료 없으면 억지로 카드형 60초 MP4를 렌더하지 말 것.
- 실제 사용자 피드백의 효과가 어떤 판단/작업에 어떻게 반영되는지 경험 ID/범위/적용·비적용 근거를 추적. 기존 expérience 저널/스토어는 보존.

## 반드시 남길 실물/비교자료와 최종 결정
- 새 작업폴더 data/video_quality_iteration/<KST폴더>/ 아래: `topic_comparison.md`, `script_draft.md`, `manager_review.md`, `script_revised.md`, `fact_checks.md`, `shot_plan.md`, `tool_options.md`, `capabilities.json`, `quality_blockers.json` 등 실제 구현 내용에 맞는 자료.
- 이번에도 실제 비디오/새 보이스를 만들 만한 자동 도구가 없으면 **원인과 선택 가능한 유료 자동 API**를 명확히 결론내라. 새 60초 영상 없는 상태에서 실물 성공 주장 금지.
- `reports/VIDEO_COMPANY_QUALITY_AND_TOOL_DECISION.md`에 (1) 현재 관리자·직원 기반의 구현·실제 검증과 미검증, (2) 3개 품질 문제별 원인 및 오늘 한 개선, (3) 트렌드 소재/수정 전후 대본, (4) API가 자동 가능한 영상/음성 도구 중 유력 후보 1~2개·공식 근거·비용·권리·상업 사용, (5) 실물 파일이 있다면 실제 경로/검증, 없다면 정확 블로커, (6) **사용자가 한 번 승인하면 가장 작은 비용·호출로 진짜 품질을 비교할 수 있는 구체적 파일 기반 다음 실행 계획**을 작성.
- 사용자에게 무조건적인 유료 전환을 강요하지 말고, 비교표를 바탕으로 **어떤 무료 한계를 유료로 해결하는지** 명시. 이번엔 결제/실 API 호출 없이 비용을 따져 보는 것이 목적.
- reports/CURRENT_PROGRESS.md 갱신. 기존 파일·데이터/원장 해시 보존, 신규 비용0, 원격 모델 호출0, 품질 재평가 미실시 구분.
- 변경이 있으면 단위 통합 검증 **한 번** 실행하고 검증 코드/테스트/보고서를 GitHub main 커밋·푸시. GUI/웹 서버 개발 금지.

## 성공 정의
**한 번의 개발 묶음 안에서 영상제작 회사의 품질 판단과 도구 선택이 실질적으로 좋아지고, 어떤 API를 최소로 연결하면 더 나은 실물 영상을 제작할지 결정을 내릴 객관적 근거를 제공한다.** 현 단계에서는 기술 데모를 반복해 성공처럼 보여주는 것이 실패다. 인간이 하는 수동 Flow·CapCut 작업을 목표 아키텍처에 넣지 않는다. 현재 1단계 기능을 통째로 재설계하지 않는다.
