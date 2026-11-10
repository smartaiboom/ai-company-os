# 영상제작 회사 품질·도구 결정 — 2026-11-10 KST

오프라인 준비 계약 구현과 새 대본 수정까지 완료했다. **실제 AI 관리자 판단, 새 영상·보이스 생성, 체감 품질 개선·게시 합격은 미완료/미검증**이다. 사용자 평가 “두 시안의 차이가 크지 않음/정적 카드가 지루함/Melo 음성이 어색함”을 기존 수치검사 통과로 덮지 않았다. 외부 모델·영상·TTS 호출0, 신규 비용$0, 다운로드/업로드/결제/게시0. 웹 공식문서 조회와 GitHub 동기화만 수행했다.

## 실제 구현과 검증 범위

- `quality_tool_adapters.py`: 기존 scene검증·DisabledAPIProvider 재사용. provider-neutral `prepare`가 실제 대본/품질규격/단일요청 USD상한/권리/상위해시를 검증하고 공개요율 추정·미준비 사유·결과검증 항목을 직원에게 전달한다. Runway5/10초, Eleven10000자, Google5000bytes 입력 한도, Unicode문자 과금 추정. 상한 초과 거절. `execute`/기존 scene생성 모두 항상 차단, 자동 재시도·대체공급자 없음.
- 기존 영상회사에 별도 읽기전용 `quality_tool_decision_context()` 제공. 공통core 재구축, 기존 실AI 도구목록·서명/승인 게이트 변경 없음.
- 기존 Company/Store/MockManagerProvider/MockEmployeeProvider로 새 입력 writer→video/voice→QA 계약 실제 실행. 4역할/각1버전/모의콜백10회, simulation=true. 공급자 이름 codex-authored, 내용은 Codex 작성이며 실제 AI 추론 아님. `preparation_hash`/상위대본해시/기존엔진 의존결과·버전해시로 인수 검증. QA는 publishable=false, 최종 manager_final_stopped, artifacts={}.
- `ExperienceJournal.select`로 기존 실제 사용자경험 journal company-2fe594ab90bd4f5f861b1866c674f475의 experience-1/2/3을 video·한국어 직장인 AI 초보자 범위에서만 선택. 각각 움직임/음성A-B/근거주제 비교로 **Codex가 편집 반영**했다. 초등학생 범위에서는3개 모두 제외. ID·원본 journal_hash·record_hash·적용 이유를 새 폴더에 기록했다. 원 저널은 읽기만 했고, 개선 효과는 hypothesis 유지. 자율 AI가 학습·적용했다고 주장하지 않는다.
- 실제 HTTP transport, 유료요청의 영속 선예약/결제계정 검증·응답다운로드/실미디어 검사 연결은 아직 없다. payload_template의 null이미지/voice는 실제 요청 불가 상태다. 이번 범위는 승인 전 계약 준비이며 JSON을 실생성으로 표시하지 않는다.

## 원인별 판단과 실제 변경

|문제|원인·검증 한계|이번 변경/남은 일|
|---|---|---|
|대본이 평범/관심 부족|모델능력 우열을 시험하지 않음. 추상 프롬프트·사례 부족/근거없는 QA 확신도 원인|출처3주제 비교 뒤 원문 있는 한 사례로 좁힘. 초안의 미실행AI오류·효과 단정 삭제; 실모델 검토는 미실시|
|정적 카드/짧은Flow 장면 늘리기|렌더 수치통과와 장면 품질은 별개. 자동 고품질 소스 공급 부재|40초 원문 조작시연+4×5초 서로 다른 생성장면 설계. 카드 전용0초/루프0. 소스·시드이미지 미확보, 새60초 강제렌더 안 함|
|Melo 어색함|실제 사용자 청취평가 기준 미달. 한국어지원/재생가능은 자연스러움 증거 아님|외부TTS 동일대본 단1회A/B 비용·한도 준비. Qwen 기존RAM3.89GB<6.5GB 차단 유지, 동일 사전검사/설치 재시도0|

## 주제·대본 실물

공개 근거는 [11/8 국내 AI앱 이용 기사](https://www.yna.co.kr/view/AKR20261106147600017)와 [오픈서베이 7월 업무·지식 검색 조사](https://blog.opensurvey.co.kr/trendreport/ai-search-2-2026/). 최신 앱 관심과 이전 업무 수요조사이며 특정 쇼츠 유행/흥행 증거는 아니다. 후보: 회의 제안·기한 구분(선정), 답변 표형식 제한(이전A와중복), 검색출처 날짜대조(60초범위과밀). 이번 새 가상원문은 “금요일15시 제안→고객확인 필요/미정→민수가 목요일까지 확인·공유”이고 실제 고객자료가 아니다.

초안: “AI가 회의 시간을 마음대로 확정했나요? 메모를 붙이면 금요일 세 시로 정리됩니다…표로 나누면 빨라집니다.” 실제 실행/효과 증거가 없어 삭제·구체화했다.

수정 대본(446자, 공백·줄바꿈 포함;60초 **목표**, 새 음성으로 길이 미검증):

 한국어 직장인 AI 초보자. 가치: 제안된 회의 시각과 확인 업무 기한을 분리.

00–03초: 오후 세 시, 확정인가요? 원문은 미정입니다.

03–10초: 회의 메모를 정리할 때, 제안과 확정을 한 칸에 넣으면 헷갈립니다. 지금 화면은 설명을 위한 가상 회의입니다.

10–19초: 민수는 금요일 세 시를 제안합니다. 지연은 고객 확인이 필요하다고 답하죠. 여기서 회의 시각은 아직 미정입니다.

19–28초: 반면 민수가 목요일까지 확인하고 다시 공유하겠다는 말은 있습니다. 회의 시간과 확인 기한을 따로 보세요.

28–38초: 정리 요청도 바꿉니다. 확정된 일, 제안, 미정을 나누고, 담당자와 기한 옆에 근거 문장을 붙여 달라고 해 보세요.

38–48초: 이 예시에서 담당자는 민수, 할 일은 고객 확인 후 재공유, 확인 기한은 목요일입니다. 금요일 세 시는 확정 시간이 아닙니다.

48–56초: 표가 그럴듯해도 원문을 대조하세요. 이 화면은 작성 예시이지, 특정 인공지능의 실제 답변이나 정확도 실험은 아닙니다.

56–60초: 회의 시간은 미정. 확인 기한은 목요일. 두 칸을 분리하세요.



## 유력 도구와 비용 결정

우선 **Runway 자동 영상 API + 한국어 TTS의 작은 청취시험**을 준비한다. TTS 최소비용 후보는 Google Chirp3-HD, 품질 비교 대안은 Eleven multilingual_v2다. 샘플을 듣지 않았으므로 유료가 더 자연스럽다거나 CapCut 수준이라고 확정하지 않는다. 자세한 공식비교는 아래와 같고 계정별 견적/권리/제공 voice는 미확인이다.

# 자동 도구 비교 — 공식 문서 조회 2026-11-10 KST
계정/가입/결제/키 확인 없음. 품질 샘플 청취·생성 없음. 아래는 공개 요율 기반 예산이며 과금 약정이 아니다.

|자동 API|한국어/입력 한도·출력|1편/10편 사용료 USD|권리·초기 현금/판정|
|---|---|---|---|
|Runway gen4_turbo|image_to_video, 검증 대상5/10초,720:1280; 실제 이미지는 미확보|생성60초 $3/$30; 이번20초 $1/$10;5초$0.25|최소 API충전$10 별도. 상업 사용 ToS 준수, 참조권리 별도. 영상 후보|
|Eleven multilingual_v2|한국어 지원/10000자; voice_id미선정,MP3 44.1k128kbps|446자 $0.03568/$0.35680; 기존60자A/B $0.0048|무료 상업권 없음/Voice Library API 제한. 공개 Starter 정가$6월, PAYG최소금액·계정권리 미확인. 음성 품질 비교 후보|
|Google Chirp3-HD|ko-KR;요청5000bytes;음성미선정,LINEAR16|446자 $0.01338/$0.13380;60자A/B $0.0018|Cloud약관 준수 상업매체 사용,청구/API활성 필요. 무료할당 실제잔량 미확인. 최소 음성시험 우선 제안|
|Kling 직접API|공식 플랫폼 존재만 확인|공식 직접 요금/계정 조건 미확인|비교가격 산정/도입 후보 확정 제외|
|Qwen0.6B CPU|기존 기록RAM3.89GB<6.5GB|이번 호출0|현재 실행 불가; 재측정/설치/다운로드 재시도 안 함|

요율: 영상5credits/s×$0.01, Eleven$0.08/1000chars, Google$30/1Mchars. 세금/재시도/이미지/가입비 제외. 신규60초 대본446 Unicode문자(UTF8 1066bytes), 기존A/B60자. 실제 발화 길이 미검증. 400~600자60초 목표 가정 시 Eleven $0.032~0.048/편($0.32~0.48/10편), Google $0.012~0.018/편($0.12~0.18/10편). 문자/요청단가와 구독의 포함분은 중복 청구로 더하지 않는다. Runway 충전$10은 $0.25 한 번 시험과 다르며 잔액이 남는다. Eleven 할인/종료된 프로모션은 산정 제외. 신규계정 최소현금은 결제화면 확인 전 확정 불가.

Runway는 이미지와 영상 모델을 같은 API계정에서 제공하여 공급자/크레딧 관리 단순화 가능. 시드이미지 생성비는 본 영상 견적에 포함하지 않았다. 같은 계정 TTS권한/한국어 품질은 확인하지 않았으며 통합 음성까지 있다고 단정하지 않는다. Eleven 웹제품의 영상기능도 해당 API/요금 확인 없이 통합으로 간주하지 않는다. 수동 Flow/CapCut 제작·업로드는 목표 경로가 아니다.

API 준비: Runway POST /v1/image_to_video(키/버전·현재 wire 재확인 필요), Eleven POST /v1/text-to-speech/{voice_id}(multilingual_v2에 language_code전송 금지), Google text:synthesize. 계정별 동시성/분당요청/리전·선택voice 실제 제공 여부 미확인. 현재 코드는 payload_template/차단·비용·인수계약만 있고 실제HTTP전송은 미구현. prepare 성공은 생성가능 판정 아님.

보이스 예시: 공식 [Eleven Korean TTS](https://elevenlabs.io/docs/ko/overview/capabilities/text-to-speech), [Voice Library 안내](https://elevenlabs.io/docs/eleven-creative/voices/voice-library), [Google Chirp3-HD 보이스/샘플](https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd). 이번에는 청취하지 않았고 특정 보이스ID를 지어내지 않았다. 한국어 지원은 CapCut 수준 자연스러움 증거가 아니다.

공식 근거:
- [Runway 요율](https://docs.dev.runwayml.com/guides/pricing/), [API설정/최소충전](https://docs.dev.runwayml.com/guides/setup/), [API](https://docs.dev.runwayml.com/api/), [웹/API크레딧 구분](https://help.runwayml.com/hc/en-us/articles/15124877443219-How-do-credits-work), [상업사용](https://dev.runwayml.com/learn/commercial-use).
- [Eleven API요율](https://elevenlabs.io/pricing/api), [변환API](https://elevenlabs.io/docs/api-reference/text-to-speech/convert), [상업권](https://elevenlabs.io/docs/help-center/legal/can-i-publish-the-content-i-generate-on-the-platform).
- [Google 요율](https://cloud.google.com/text-to-speech/pricing?hl=ko), [한도·매체 사용약관](https://docs.cloud.google.com/text-to-speech/quotas), [청구·API설정](https://docs.cloud.google.com/text-to-speech/docs/before-you-begin).
- [Kling 공식 개발자](https://kling.ai/dev/model/image): 직접요금 페이지 본문을 검증할 수 없어 미확인으로 남김.

## 실제 결과 위치·다음 실행 계획

새 작업 루트: `/workspaces/ai-company-os/data/video_quality_iteration/20261110T120412_KST/` (Codespaces 로컬 데이터, GitHub 업로드 안 함).

- `topic_comparison.md`, `demo_input.txt`, `script_draft.md`, `manager_review.md`, `script_revised.md`, `script_revised.txt`, `fact_checks.md`, `shot_plan.md`: 이번 신규 원문/초안/수정/60초 장면 설계.
- `tool_options.md`, `cost_estimates.json`, `capabilities.json`, `tool_inputs.json`, `prepared_requests.json`, `quality_blockers.json`: 비용·입력·해시·미생성/권리/청취 차단 증거.
- `experience_application.json`, `offline_contract_result.json`, `offline_contract_store/`: 실제 경험 선별과 명확한 mock 실행상태.
- `next_execution_plan.json`, `execution_receipt.json`: 다음 승인 범위와 이번 호출0 영수증. 계획은 승인이 아니다.

다음 가장 작은 제안은 기존 `data/video_quality_iteration/20261110T110100_KST/ab_script.txt`60자를 **Google ko-KR 보이스 단1회**, 예상$0.0018/요청상한$0.01로 합성해 기존 `A_reference_melo.wav`10.982초와 사용자 블라인드 청취하는 것이다. Eleven 대안은 같은60자 단1회 예상$0.0048/상한$0.02(무료 상업권 불가, PAYG/최소현금·선택voice 조건 별도). 둘을 자동 연속 호출하지 않는다. 승인 대상 공급자/계정·모델·원문해시·전송·1회·요금·출력경로를 위 파일에 고정한다. 키는 보고서에 넣지 않는다. 승인되더라도 먼저 실제 transport/영속선예약·불확실중단·결과해시 검증을 구현·오프라인 검증해야 한다. 현재 코드를 바로 실행해 생성할 수 있다고 약속하지 않는다.

영상은 별도 범위로 자체 참조이미지1장 해시·업로드 권리를 승인한 경우에만 Runway5초 단1회 예상/상한$0.25. 신규 API계정 최소충전$10은 별도 현금결정이고 본 과금상한 승인이 가입·충전을 승인하지 않는다. 시드이미지 생성은 별도비용/호출이며 현재 계획에서 자동생성 안 함. 성공·청취 선호 확인 전60초 확장/재시도/게시 금지. 기존A/대본SHA는 next_execution_plan.json에 실파일로 바인딩했다. 네트워크 타임아웃·시도 불확실 시 요청 추가0으로 정지한다.

**이번 새 MP4/WAV/MP3는 없다.** 마지막60초는 `data/video_quality_iteration/20261110T102849_KST/preview.mp4`,15초 무음검토는 `data/video_quality_iteration/20261110T110100_KST/motion_study/visual_motion_study_15s.mp4`,Qwen B는 없다. 기존 출력들을 재생성하지 않았다.

## 통합·보존 검증

- 통합 1회: `PYTHONPATH=core:companies/video python -B -m unittest discover -s tests -v`(미디어 재생성 opt-in 환경변수3개 해제), **59개 중56통과/3선택skip/실패0**,31.362초. 기존 엔진·동의·피드백·미디어 fixture와 새 비용/한도/변조/실행거절/4역할 인수계약 포함. 실제 기존영상/Melo/Qwen 재생성 시험은 하지 않았다.
- 로그: `/workspaces/ai-company-os/data/video_quality_iteration/20261110T120412_KST/integration.log`, 실행명령·검증소스SHA: 같은 폴더 `verification.json`. 네트워크 금지 패치하에서 신규4테스트 통과. `git diff --check` 통과.
- 사전45,510개 보호 파일(data/backups/artifacts/.env 및 기존 실관리자 준비 저장소)의 SHA256·존재 대조: 변경/삭제0, 새 작업폴더 밖 추가0. `/workspaces/ai-company-os/data/video_quality_iteration/20261110T120412_KST/preservation.json`. 이후 이 새 폴더에 검증로그/영수증만 추가했다. 실제 기존 동의·비용·시도 원장 변경 없음.
- 원격 최신 main `8e18257`에서 구현. 커밋 대상은 도메인코드2개·테스트1개·본 보고서·CURRENT_PROGRESS만. 로컬 자료/모델/미추적 기존7파일/비밀키 제외. 커밋·푸시 후 원격HEAD 일치는 최종 응답에 실제 해시로 보고한다.

남은 일: 승인 전 실제 transport·영속시도 예약 구현, 계정별 과금/보이스/권리 확인; 승인 후 단1회 음성A/B, 필요시 별도5초 영상 시험과 실제 사용자 재평가. 아직 게시 수준60초 새 산출물은 없다.
