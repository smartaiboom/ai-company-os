# 영상제작 전문 AI 회사 — 실제 음성 평가 확정 및 대본 제작 능력 개선
기준일: 2026-11-11 KST
작업 범위: `companies/video/`, 기존 `core/` 재사용. 현 단계는 **이미 제작한 60초 영상의 낮은 품질을 개선하는 2단계**다.

## 1. 이번 사용자의 실제 평가 — 반드시 이전 평가와 구분하여 기록
사용자가 새 `B_next_gemini.wav`를 **직접 청취**하고 다음과 같이 답했다.

> 새로 생성한 148자 Gemini/Puck 21.52초 음성을 실제 청취했어. 전체 자연스러움 7/10점, 목소리·억양 좋음, 속도·쉼 적절함. 의견: 좋아 음성은 전체적으로 상당히 괜찮아! 이제 대본,영상,음성 중 음성은 충분하고 대본 생성 능력 향상에 힘쓰자.

실제 오디오 경로 `/workspaces/ai-company-os/data/video_voice_selection/20261110_v1/next_trial/B_next_gemini.wav`, SHA256 `6ef2673b6f977981a789d27b132c8233090e049e299cda6f11e946936ccb149f`, 21.520초. 실제 호출1/1 소모·HTTP200. 보고서 `reports/GEMINI_TTS_148_CHAR_REAL_ONE_SHOT_RESULT.md`.

**다른 과거 평가:** 2026-11-10 기존 **60자 / 8.04초** Gemini/Puck B SHA `7674f8d8449f5011aff56efd6c4f52ba7d878c43541df6d7043442a4ba831419`을 Melo A와 비교해 B 우세·7/10점을 준 기록, `data/video_voice_feedback/20261110_AB_Puck_7of10/`, `experience-1`. **두 개의 실오디오 SHA/원문/길이/평가 별도 ID**. 이전 원본 journal/entry 절대 덮거나 평균점수로 뭉개지 말 것. 새 평가 근거는 `user_structured`의 **개별 샘플에 대한 사용자 청취 의견**이며 일반적 모델 성능, 영상 게시 합격, 저작권 검증이 아님.

사용자 결정: **음성은 현 단계에서 충분/우선 사용 가능, 추가 TTS 도구·음성 모델 실험과 자동 음성 재호출은 당분간 보류. 대본 생성 능력 개선이 다음 1순위.** 이는 향후 새로운 대상/영상에도 모든 목소리를 Puck으로 고정하라는 의미가 아니다. 음성 평가 저장 외 더 이상 음성 시스템을 파고들지 말 것.

## 2. 먼저 실제 개발 상황 파악 후 기존 시스템에 최소 구현
읽기: `AGENTS.md`, `reports/CURRENT_PROGRESS.md`, `reports/VIDEO_VOICE_USER_AB_FEEDBACK_RESULT.md`, `reports/VIDEO_VOICE_SELECTION_AND_NEXT_SAMPLE_RESULT.md`, `reports/GEMINI_TTS_148_CHAR_REAL_ONE_SHOT_RESULT.md`, `companies/video/voice_quality.py`, `companies/video/quality_workflow.py`, `companies/video/video_production_company.py`, `companies/video/production_video.py`(존재 시), 관련 manager/employee provider·tests.

실제 확인 결과와 코드 실행 증거 없는 기능은 '구현돼 있다'고 쓰지 말라. 현 manager→writer→voice→editor→QA의 **codex-authored/mock 콜백**은 실제 LLM의 대본 자율판단 결과가 아니다. 단지 JSON 형식·60초 합계가 맞는 것이 '재미있는 대본'을 증명하지도 않는다.

### 2a. 새로운 사용자 평가 기록
- 기존 `ExperienceJournal` 또는 `voice_quality`의 실제 사용자 평가 저장·idempotence를 **재사용**하여 21.52초/148자 샘플을 별도 항목으로 연결. A/B 경험 `experience-1`은 불변. 새 평가 SHA 키로 중복 저장 방지; KST 저장시간/원래 청취시간 불명 구분.
- `overall_naturalness=7/10`, `voice_and_intonation='좋음'`, `pace_and_pauses='적절함'`, `user_says_voice_sufficient=true`, `next_priority='script_quality'`, `source='actual_user_listening_148_20261111'`.
- 특정 발음 오류가 있다거나 8점·9점을 달성했다고 꾸며내지 말 것. 다음 작업의 시스템 추천·사용자 품질 판단 기준에 반영하되 **음성 제작 호출 권한으로 오해하지 않기**.

### 2b. 이제는 대본 직원과 AI 관리자 능력 향상에 집중
현 영상제작 회사의 글쓰기/관리자 작업을 **실제 산출물 중심**으로 개선한다.

1. **짧은 영상용 좋은 주제 선정 기준:** 목표 시청자(한국어 직장인/AI 초보자), 영상의 한 가지 명확한 유용성, 시청 이유, 첫 3초 후크, 구체적인 실제 시연 가능 장면, 출처/최신성 필요 여부. 최신·유행을 임의 사실로 가장하지 말 것; 실검색 없으면 evergreen 주제/검증 필요 표시. 단순 가상 회의 메모가 매력적인 쇼츠 주제라고 자동 가정하지 않는다.
2. **대본 작성 계약(실제 직원 인수 가능):** target_audience, viewer_problem, promise, hook_0_3s, payoff, narrative_beats(시간/내레이션/시연 가능한 화면/근거 출처), close, transcript, target_duration=60s, estimation_method, unknowns, provenance(author/LLM/model/mock). 영상 편집 직원에게는 설명 카드만 반복하지 않게 '실제 화면 시연/장면 변화/짧은 샷'을 장면마다 지정하고 source unavailable이면 pending. 외부 실제 소스나 자료를 확보하지 않았는데 확보했다고 기록하지 말라.
3. **AI 관리자 평가·수정:** 별도의 평가 항목 — 처음 3초 관심, 1개 메시지, 실제 유용성, 지루한 중복·군더더기, 구체 사례와 시연 가능성, 사실/시점 검증, 60초 분량 적합성, 편집 현실성. 각 결함에 증거 문구·심각도·담당 직원·구체 수정 지시와 이전/수정본 비교 연결. **관리자가 매번 무조건 합격시키거나 점수를 꾸미는 구조 금지**. 특정 기준 미달이면 실제로 반려·재작성 경로가 동작하는지 테스트.
4. **객관 검증과 주관 품질 분리:** 60초 구조·중복어·샷/장면 대응/출처 미확인/자막 길이 등 deterministic checks는 코드로 검증. 재미·후크 매력·시청 유지 가능성은 실제 모델 판단 또는 사용자 평가 없이는 unassessed. 모의 응답을 'AI 관리자 자율판단 검증 완료'라고 표기 금지.
5. **연결 우선:** 기존 영상 제작 회사 `VideoProductionCompany`와 `VideoProviderQualityCompany` 또는 사용중인 workflow에 실제로 적용할 수 있는 최소 통합 개선. 새 대본 엔진·중복 회사 구조를 쌓지 말라. 실제 LLM invocation 통로가 이미 존재한다면 **권한·키/예산/승인 범위와 현재 호출 소모**를 확인하되, 이번 턴은 새 외부 호출·유료 전환 허가가 없으므로 실호출0. 별도 승인 없이 실제 AI 생성/검색/TTS/영상 생성 API 발송 금지.
6. **품질 비교 준비:** 기존 60초 대본/MP4(존재하는 실제 경로를 확인)와, 개선된 대본 후보 1개를 같은 사용자 목표에 대해 비교하는 산출물 생성. 후보 대본이 Codex가 만든 것이면 `codex-authored candidate`로 표시하고 **AI 직원 결과로 사칭 금지**. 실제 생성할 다음 실 AI 직원 대본 검증을 위해 각 품질 기준에 사용자 평가란(미평가) 마련. 영상·음성 신규 생성은 아직 하지 않는다. 불필요하게 여러 후보·보고서·장부를 늘리지 않는다.

## 3. 이번 개발 성과 기준
- 사용자 148자 21.52초 평가가 기존 60자 8.04초 A/B 평가와 **별도** 저장되고 2번 실행에도 중복0, 평가별 오디오 해시·타깃 분리 검증.
- **실행 가능한 대본 작성/검토 흐름 개선** + 최소 통합 테스트(관리자→writer→관리자 근거 기반 반려/수정→editor에게 개선본 전달). **반려 후 수정본**과 수정 증거·버전차가 실제 파일로 남아야 함. 테스트만 통과하고 결과물 없는 '준비'가 아닌 것.
- 기존 최초 60초 영상의 시청 피드백(지루한 카드·반복·약한 주제/대본)과 실제 실물 대본을 참고해 **개선 대본 1편**을 비교 가능하게 남김. 원본 영상·오디오 덮어쓰지 않기.
- 합격을 가르는 '실제로 생성/검증된 것' / 'Codex-authored 연습' / '실제 AI 직원 사고'를 세 칸으로 각각 보고.
- **실 외부 AI/검색/TTS/영상 API 호출0**, 비용0, 신규 MP4/WAV0. 기존 호출/시도/사용량/키/동의 기록 불변. 테스트에서 HTTP 실전송 금지.
- 불필요한 채널 대표 목소리/승인 wrapper/모의영상 추가, 재개발/테스트 무한루프 금지.

## 4. 결과 보고와 보존
- `reports/VIDEO_SCRIPT_QUALITY_IMPROVEMENT_RESULT.md`: 새 실 청취 평가/별도 experience ID와 음성 완료 판단, 기존 60초 대본/영상 참고 근거, 코드 실제 변경, 대본 후보/개선전후/지적결함, 관리자 반려·수정 실행 증거와 모의 vs 실제 LLM 경계, 관련 단위 테스트, **다음에 실 AI 대본 직원으로 진행할 단 하나의 정확 실행 제안**(필요 권한/예상 호출수/무료조건/기존 엔진 연결/완료 판정), 현재 미검증 품질 항목.
- `reports/CURRENT_PROGRESS.md`에 **품질 개선 2단계 / 음성은 사용자 수용 / 대본 개선 우선** 업데이트. 지난 사용자의 7점 두 건은 그대로.
- GitHub main에 코드·테스트·간결한 보고서만 커밋/푸시. 기존 `data/`, `backups/`, `artifacts/`, `.env*`, 사용자 영상/WAV·원장 그대로 보존; 새 로컬 파일은 비밀 없는 별도 작업 폴더. KST. git clean/reset hard 금지.
- 작업 후 ChatGPT가 GitHub의 보고서를 읽어 사실 기반으로 다음 진행 판단할 수 있어야 한다.

**최종 목표는 'AI 영상제작 회사가 목표만 받아 스스로 유튜브에 올리고 싶은 품질의 영상을 만든다'이고, 현재는 새 회사 구축이 아니라 이미 제작한 60초 영상의 대본 품질을 높이는 작업이다.**
