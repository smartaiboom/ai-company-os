# 실제 사용자 음성 평가 반영 결과 — 2026-11-10 KST

**실제 평가 “B가 훨씬 자연스럽다 / B 자연스러움7/10”을 별도 저널에 저장하고, 같은 대상의 음성 추천·관리자 기준·대본→음성→편집→QA 인수 검증에 반영했다.** 이번 실 API 요청0, 비용0, 신규 실음성/WAV0. 실제 새 음질 향상이나 게시 합격을 주장하지 않는다. 최신 main `d2a9c32`와 AGENTS.md/지정 지시서에서 작업했다.

## 보존한 사용자 원문과 실물 연결

> 실제 음성 A/B 청취 평가 결과: 더 나은 음성=Gemini TTS(B), 새 Gemini 음성 자연스러움=7/10점, 의견=B가 훨씬 자연스러워.

출처 provenance=user_structured, verification=verified는 **이 A/B의 실제 사용자 선호·7점이라는 사실만** 뜻한다. A의 절대 점수, 억양/발음/속도 등 특정 결함, 일반적인 모델 우열, CapCut 동급, 새 샘플8점/게시 합격은 확인되지 않았다. 미래 개선은 hypothesis다.

|실제 파일|길이|기술 정보|SHA256|
|---|---:|---|---|
|A_reference_melo.wav|10.982109초|968666bytes,PCM16/mono44100Hz|a011f8bb6b83e5d3515171bcdf6fc9e9aa09d42844f8e14cfbb8955de18b25a5|
|B_gemini.wav|8.04초|392038bytes,PCM16/mono24000Hz|7674f8d8449f5011aff56efd6c4f52ba7d878c43541df6d7043442a4ba831419|

실제 기존 경로: `data/gemini_tts_single_free_trial_v1/operation/`. 두 파일을 실제로 찾아 SHA·ffprobe·전체 decode를 확인했다. 같은60자 입력 원문 SHA=`ec1e2906fd065530a2bbfc79bfab9d3769a9f72296897887f5b02d4efeeffa59`. 평가 evidence는 두 오디오·원문 SHA와 Gemini Developer/gemini-3.8-flash-tts/Puck을 바인딩한다. 저장 시각은 `2026-11-10T16:37:33+09:00`이며 별도 미제공인 실제 청취 시각을 창작하지 않았다.

## 실제 저장 ID·해시·범위

로컬 보호 경로: `/workspaces/ai-company-os/data/video_voice_feedback/20261110_AB_Puck_7of10/`.

- feedback/evaluation SHA: `8c4f6a2a7bcd6dbfaf23ea3868bef5f92429146e5bfc644a5f81550ec5da0bab`.
- immutable evidence 파일: 위 SHA 이름의 `.json`,0400. artifact SHA: `4b66620562db040488fb0f75c3225a453d60af2a2c2fa4640762b709b42c0505`.
- 별도 ExperienceJournal ID: `company-f99810729a2a42a48b45c8f28f057035`, feedback ID `experience-1`.
- journal hash: `e6bfa73e85d4529f7e061738bdc5019de4fdf32850bd0b2eaa43d4159bf79faf`.
- record hash: `6bf269e9b535de53a8fafed2fce45d24aba0836c730bc14f25ae6a7c3c84d043`.

기존 저널을 덮어쓰지 않았다. media/원문/평가의 SHA로 식별하고 외부 파일 잠금 아래 기존 저널을 재사용해 중복을 막는다. 동일 평가를 두 번 실제 저장 호출해 entry1개·ID·artifact/journal hash 불변을 확인했다. domain video / target_segment **한국어 직장인 AI 초보자**에서만1건 선택하며 초등학생/제품 분야는0건이다. 다른 한국어 대상이나 fixture/비검증 출처에는 B 추천을 전파하지 않는다. `scope_checks.json`에 선택·제외 증거를 저장했다.

## 실제 코드와 실행 결과

- `companies/video/voice_quality.py`: 기존 ExperienceJournal/Store/잠금/파일 저장/미디어 실행기를 재사용. 오디오·원문 해시 검증과 immutable 실제 평가 저장·idempotence, 엄격한 대상 선택, 추천과 실행 권한 분리를 구현했다. 추천은 해당 범위의 Gemini/Puck B 우선이며 Melo A는 대조군으로 보존한다.
- 기존 `video_production_company.voice_staff_quality_context()`에서 이 추천과 단 하나의 다음 샘플을 직무 context로 제공한다. 모델 추천은 외부 생성 권한이 아니다. 새 API 승인을 만들지 않는다.
- 기존 `quality_workflow.VideoQualityCompany`에 opt-in `voice_quality_contract_v1`을 연결했다. 실제 사용자7점을 baseline, 다음8점 이상은 **목표/hypothesis**로 관리자·음성직원에 전달한다. 기존60초 계획 형식/일반 품질 흐름은 유지한다.
- 새 검증은 본문 hash/인수 result hash·revision/장면 시간/자막 원문/음성 디렉션·추천 근거/점수 의미/생성 불허를 확인한다. 대본 변경, 잘못된 상위 참조,7→9점 과장, 가짜 음성 결과, 생성 권한 추가, 지원하지 않는 speed wire 파라미터를 거절한다. 쉼·호흡·속도·강조·숫자/영어/이름 발음은 **편집 검토 지침**이며 합성/청취를 했다는 주장이 아니다. 실제 wire 확장은 없고 스타일은 기존 speech_metadata.style에 담을 안내만 준비한다.

기존 회사 엔진으로 새 격리 프로젝트를 **실제 오프라인 실행**했다. manager plan→writer→voice→editor→QA→manager final stop,4역할/각1버전/총10모의 콜백, upstream content/hash/revision 인수와 관리자 검증을 기록했다. 종료는 manager_final_stopped, artifacts={}, simulation=true. 최종 QA는 새 음성/청취/권리 대기. 반복 run 시 콜백이10회에서 늘지 않았다.

이는 **codex-authored callbacks를 실행한 인수 검증**이며 실제 LLM 관리자/직원의 자율 판단·실제 영상 제작이 아니다. 단순 문서 저장을 넘어 실행 가능한 추천·검증 기능을 추가했지만, 실제 새 음성의 객관·체감 품질 향상은 미검증이다. 기존 실 API 승인 게이트/소모된1/1 guard/비용 원장과 live 회사는 변경·재실행하지 않았다.

검증 한 묶음: `PYTHONPATH=core:companies/video python -B -m unittest tests.test_voice_quality tests.test_quality_feedback tests.test_quality_provider tests.test_quality_tool_adapters tests.test_tts_execution tests.test_tts_job -v` → **33통과/실패0,4.818초**. 실제 사용자 evidence 저장·중복·scope·변조·미래 목표 의미·회사 인수 통합과 기존 품질/모의/실행 게이트를 포함했다. 로컬 실물 적용도 socket/DNS 금지 상태로 수행했다. 전체 회귀/실 API를 반복하지 않았다. `git diff --check` 통과.

## 다음에 제안하는 실제 샘플 딱 하나 (이번에는 생성하지 않음)

**주제:** 금요일 세 시, 회의 확정인가요? 직장인 AI 초보자가 제안된 회의 시각과 확인 업무 기한을 구분하는 가상 메모 사례다. 시청자 흥미·성과가 검증된 주제라는 뜻은 아니다. 기존446자60초 대본 전체를 전송하지 않고 아래137자/UTF-8 327bytes를 새 내레이션 후보로 작성했다.

> 금요일 세 시, 회의가 확정된 걸까요? 설명을 위한 가상 메모예요. 금요일 세 시는 제안이고, 회의는 아직 미정입니다. 목요일까지 고객에게 확인하고 다시 알려주겠다는 말은, 확인 업무의 기한이죠. 회의 시간과 확인 기한, 두 칸으로 나눠 보세요.

codex-authored, 원문SHA=`2cdff7ca3a91bbeaa4249cd3765c65548fdec016a9688dd1d9af13f7e49556ea`. 가상 source_text와 주장별 연결을 포함했다. 사실 검토 표시는 직접 작성한 가상 원문 내 일관성 지침이며 실모델 답변/외부 사실 검증이 아니다.

|장면|목표 시간|직원 인수 지시|
|---|---:|---|
|질문 후크|3초|확정 여부 질문, 시각 선택 강조|
|제안과 미정|5초|가상 예시 고지·원문 제안/미정 분리|
|확인 업무 기한|7초|목요일/금요일 혼동 여부 발음·자막 대조|
|두 칸 정리|5초|회의 시간/확인 기한 분리, 두 칸 가볍게 강조|

총20초는 **목표**이며 실제 발화 길이/자막 동기/음질은 미실측이다. 스타일은 친근하고 또렷한 한국어 대화체, 질문 뒤 짧은 쉼, 제안/미정 의미 구분, 과장·성우 모사 없음. 발음/속도 결함이 있다고 진단한 것이 아니라 다음 청취 체크다. voice/editor 인수 JSON에 정확 본문/방향/시간과 실제 alignment=null을 연결했다.

후보 모델/음성: Gemini Developer API / gemini-3.8-flash-tts / Puck. 제안 상한: 실패 포함 요청1회, 출력1024토큰, 응답2MB/음성20초 로컬 수락, 비용상한$0·무료 계정만·retry/fallback 없음. 현재 잔여 무료쿼터/권리/새20초의 출력 안정성은 이번에 조회·증명하지 않았다. 상업 사용은 미검증이며 무료 입력의 Google 개선/인적 검토 조건을 다음 승인 때 다시 정확한 본문과 연결해야 한다.

**새 정확 payload·모델/음성·출력위치·1회/$0·데이터정책에 대한 별도 다음 동의가 있어야 생성 가능하다.** 이 후보는 기존60자 승인과 다른 입력이므로 이미 소모된 실행 guard를 재사용할 수 없다. 현재 TTS 실행 경계는 이전60자에 한정돼 있으며 새 본문에 대한 실행 바인딩도 다음 승인 범위에서 별도 적용해야 한다. 이번에는 그 게이트를 바꾸거나 새 생성 권한을 만들지 않았다.

실제 저장 파일: `feedback_receipt.json`, `staff_context.json`, `writer_handoff.json`, `voice_handoff.json`, `editor_handoff.json`, `qa_handoff.json`, `next_narration.txt`, `next_sample.json`, `offline_workflow_result.json`, `execution_receipt.json`, `tests.log`. 기존 A/B를 다시 합성하거나 새 오디오/영상 파일을 만들지 않았다. 사용자 점수7/10은 그대로이며 향후8점 이상은 청취 전 목표일 뿐이다.

보존 확인: 새 피드백 폴더를 제외한 기존 data/ 및 존재하는 backups/artifacts/.env* **45,585파일 사전/사후 SHA256 대조 변경·삭제0**. 이전 평가 저널·실제1회 TTS guard/attempt·관리자1/1/준비0/1·비용/사용량 원장·A/B·모델/키 모두 보존했다. 사전 manifest/사후 결과는 새 보호 폴더에만 저장했다. 이번 신규 네트워크는 GitHub 동기화/보고서 반영뿐이며 Free Tier/키/모델 목록/생성 API는 조회하지 않았다.
