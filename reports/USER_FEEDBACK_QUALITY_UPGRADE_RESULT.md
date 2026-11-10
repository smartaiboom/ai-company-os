# 실제 사용자 피드백 반영 결과 — 2026-11-10 KST

## 판정: 부분 완료

사용자의 실제 평가3건을 기록·선별 적용하고,소재 비교·새 대본·자산/음성 게이트를 구현했다. **새 검토 실물은15초 무음 움직임 영상과10.982초 기존 음성 A이며,새60초 완성본/대체 음성 B/A-B 합격은 없다.** 부족한 자산과 무승인 모델 설치를 빈 카드·Melo 재합성으로 대체하지 않았다. ‘새 영상이 더 좋다’/점수 상승/자연스러움 합격/자율 회사 달성은 주장하지 않는다.

- 새 작업 폴더: `/workspaces/ai-company-os/data/video_quality_iteration/20261110T110100_KST/`
- 시각 검토 실물: `motion_study/visual_motion_study_15s.mp4` — 실제 존재,15.000초/720×1280/H.264/24fps/무음,ffprobe·전체 decode 통과.8초 기존 Flow 움직임+7초 가상 문서 대조/강조/수정. 외부 클립 반복0.60초 영상이나 오디오 포함 완성본이 아니다.
- 소리 A: `A_reference_melo.wav` — 실제 존재,10.982초/PCM/44.1kHz 모노,probe·decode 통과. 기존 완전한3구절을 그대로 연결했다. 새 합성0,가속/발음 자르기0. B WAV 없음.
- 화면 검토: `contact_sheet.png`, `document_detail.png`. Codex가 실제 출력 프레임을 확인했다. 원문 목요일/교육용 오류 금요일/수정 예시의 시각 대비와 예시 고지를 확인한 것이며 미감·전체 시청의 사용자 합격은 아니다.
- 코드/테스트/사용법 커밋 `feed01b` (`Gate audience visual assets and replacement voice comparison on actual evidence`). 시작 main `0deac2a`. 본 보고서는 별도 커밋으로 함께 main에 반영한다. 미디어/모델/실제 프로젝트 데이터는 GitHub에 올리지 않는다.

## 피드백별 조치·실제 바뀐 점·미달

| 실제 사용자 피드백 | 이번 조치/증거 | 미달 |
| --- | --- | --- |
| 정보 전달은 되지만 이미지/움직임이 부족해 지루함 | 카드 추가 대신 사람/업무 움직임8초+문서 선택/오류 강조/수정7초 실제 시연. 카드 상한 총6초/연속3초로 검사. 원본 프레임을 letterbox로 보존,안내는 영상 바깥 여백 | 기존 Flow를 재활용한15초 검토이고 새 움직임 소스를 확보한 완성60초가 아님.전용 시연4종/물리적 B-roll2종 미확보 |
| MeloTTS 음성이 어색함 | 실제 사용자 평가를 유지하고 대체 음성 미준비 시 gate 실패. 동일 A-B용 대본/기존 A10.982초를 보존. Qwen/다른 후보의 모델·코드/자원 조사 | B 없음.설치 승인·CPU 메모리·권리 검토/청취 비교 필요.속도 조정이나 코덱 검사로 합격 처리하지 않음 |
| 최신 관심사·트렌드 소재로 평가 필요 | 직장인 초보자 대상으로3후보 비교 후 ‘회의 요약의 날짜 원문 대조’ 선택. 무근거30초 성능 주장 삭제,가상 오류 예시임을 고지 | 이번 주 급상승 키워드/조회수 자료는 없음.업무AI와 신뢰라는 공개 맥락을 적용한 편집 판단 |

피드백 원문은 새 폴더의 별도 ExperienceJournal3건에 `user_structured`/실제 사용자 지시서 출처로 저장했다. fixture나 실제 모델 응답으로 바꾸지 않았다. `feedback_context.json`은 actual_user_feedback=true/not_fixture=true를 기록한다. verification=hypothesis는 수정 효과와 새 시청자군 적용의 미검증 가설을 뜻하며 사용자 시청 평가가 허구라는 뜻이 아니다. 기존 저널의 수정/철회·범위 선택을 재사용했다.

같은 한국어 직장인 초보자에3건을 선택해 실제 카드 제한·새 소재·음성 대기 정책으로 반영했고 어린이 동화 대상은0건으로 제외했다. 대상 범위는 Codex가 좁힌 적용 가설이며 보편적 규칙으로 승격하지 않았다. 경험ID/해시와 ROLE_CONTRACTS에 연결할 품질 inputs를 `provider_context.json`에 검증해 저장했지만 외부로 보내지 않았다. 실제 회사 LLM API0회다.

## 소재와 최신 근거

비교는 `topic_decision.md`에 관심/실용성/시각 시연/검증/자산·비용·권리/교육 가치를 기록했다.

1. **선정: 회의 요약의 요일이 바뀌었다면 원문 대조.** 한 가지 확인 행동을 가상 문서로 보여 줄 수 있다.
2. ChatGPT vs Gemini 활용 비교: 실제 동일 조건 앱/모델 실험이 미승인이고 조사 만족도를 모델 능력으로 바꿀 수 없어 제외.
3. 회의록을 세 할 일로 정리: 유용성은 추정되나 검증 없는 시간 절약 주장과 일반 질문 강좌 반복을 피하기 위해 보류.

[연합뉴스,2026-11-08](https://www.yna.co.kr/view/AKR20261106147600017)의 모바일인덱스 보도는2026년10월 국내 ChatGPT 앱 MAU 약1,876만명 규모를 제시한다. Android/iOS 앱 기준이며 웹은 제외되고 Gemini 이용경로 집계 한계가 있다. 특정 쇼츠 소재의 유행 증거로 쓰지 않았다. 기사 사진/그래프/본문을 영상에 복사하지 않았다.

[오픈서베이 블로그,2026-07-13](https://blog.opensurvey.co.kr/trendreport/ai-search-2-2026/)는2026-07-02 전국10~59세1000명 조사에서 업무/지식의 생성형AI 검색과 신뢰 문제를 다룬다. 직장인만의 조사나 이번 주 검색 추세는 아니다. 새 주제의 수요는 이 맥락에서의 **Codex 추정**이며 급상승 키워드라고 표시하지 않았다.

실제 대본에는 외부 통계나 모델 성능 숫자를 넣지 않았다. 목요일/금요일은 직접 작성한 가상 교육 예시다. `claim_evidence.json`에 공개 맥락/가상 문서/거절한 성능 주장을 구분했다. 실제 모델이 금요일이라고 답했다고 주장하지 않는다.

## 실제 저장한 제작 자료와 제품 코드

새 폴더에 `topic_decision.md`, `script_draft.md`, `manager_review.md`, `script.md`, `shot_plan.md`, `asset_requests.md`, `tts_comparison_plan.md`, `evaluation.md`, `source_rights.md`를 저장했다. 초별60초 계획은 있으나 preview.mp4는 만들지 않았다. 초안의 ‘30초 완성/복사해 전송’은 근거가 없어 반려하고 원문 검증으로 재작성했다. 판단/작성은 **Codex authored/offline editorial judgement**이다.

`companies/video/audience_visual_review.py`는 기존 open_input/probe/해시/잠금/원자적 저장/명령 실행기를 재사용한다. 실제 파일이 없거나 해시·경로·길이가 잘못되면 거절하고,외부 클립 반복·카드 상한·동작 미검증·대체 음성 대기를 검사한다. WAV 코덱만으로 사용자 음성 선호를 승인하지 않는다. 별도15초 검토 도구는 사용권 미확인을 유지하고 완성 쇼츠로 분류하지 않는다. 다운로드·설치·모델 호출 기능은 추가하지 않았다.

`quality_gate.json`의 현재 실패 항목은 **6개 장면 자산 미확보+replacement_voice_pending**. 카드0초 계획이라도 render_ready=false/publish_ready=false다. `asset_requests.md`에 원문 추적8초/달력 손8초/차이 대조9초/수정 동작9초/실제 검토 전달10초/근거 요약8초의 필요한 역할·규격·수량·권리를 명시했다.3단계 PNG를 길고 다양한 영상으로 간주하지 않았다.

권리: 검토에 쓴 Flow2개는 사용자 제공 AI 출처 진술이며 독립적 생성/상업권·워터마크 검증 없음. 새 영상 생성·실제 인물/장소 촬영으로 위장하지 않았다. 각각 원본7.93초 중4초씩1회 사용하고 전체 프레임을 보존했다. 원본명/SHA/권리는 `motion_study/receipt.json`,새 파일 해시/가용 상태는 `asset_receipts.json`. 문서 시연은 로컬 코드 생성/Noto 기존OFL이며 가상임을 표시. 사용자 미디어/음성 권리가 확인되지 않아 게시 불가다.

## TTS A/B 결과와 보류 사유

현재 A만 있고 B는 없다. 기존 모델을 다시60초 합성하지 않았다. A 원문/receipt와 B 동일 대본 조건·평가표를 보존했지만 새로운 사용자 청취 비교/발음·강세·감정 점수는 미평가다.

단일 최우선 후보는 [Qwen3-TTS-12Hz-0.6B-CustomVoice](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice)의 한국어 Sohee preset. 코드/모델의 Apache-2.0 표기를 각각 확인했으나 음성 출력/프리셋의 상업 사용권은 별도 확인 대상으로 남겼다.1.7B와 같은 instruction control 또는 자연스러움을 보장하지 않는다. [XTTS-v2](https://huggingface.co/coqui/XTTS-v2)는 한국어 지원이 있으나 모델 CPML/코드 MPL-2.0 및 복제 자료·사용 조건을 해결하지 못해 우선 후보에서 제외했다. eSpeak를 자연스러운 대체 음성으로 취급하지 않는다.

현재 CPU2개/RAM총8.33GB·가용3.95GB/swap0/디스크여유11.40GB/GPU 장치 미발견. Python3.12는 존재하지만 Qwen 패키지·가중치는 없다. [공식 모델 파일 목록](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice/tree/main)은 repo약2.5GB를 표시한다. CPU FP32 전개/추가 메모리·지연은 미실측이다. 가용RAM6.5GB/디스크8GB는 우리가 정한 보수적 사전 조건이며 공식 최소 사양이 아니다. 현재 RAM 조건은 미달한다.

`tts_comparison_plan.md`에 고정 모델 revision/별도Python3.12/CPU 의존성/로컬 경로만의 추론/동일 대본 B1회/600초 중단/네트워크 차단/실패 재시도 없음과 단일 승인 범위를 기록했다. 공식 파일 조회는 했지만 가중치·패키지 설치/다운로드는 하지 않았다.

**남은 사용자 결정 하나:** RAM 조건 충족 시에만 Qwen0.6B/Sohee 모델+CPU 의존성 최대6GB 다운로드/새 환경 준비와 B1회(최대600초,유료API/미디어 업로드0)를 허용할지. 승인만으로 RAM 조건을 무시하지 않는다. 실제 작업 전 CPU dependency constraints와 다운로드 합계·현재 라이선스를 재확인해야 한다. 아직 실행 명령을 승인받은 것으로 해석하지 않는다.

## 통합 검증과 기존 자료 보존

기능 묶음 끝에 전체 통합1회:

```bash
env -u AI_CLIP_ACCEPTANCE_ROOT -u VIDEO_EDITORIAL_ACCEPTANCE_ROOT AUDIENCE_VISUAL_REVIEW_ROOT=/workspaces/ai-company-os/data/video_quality_iteration/20261110T110100_KST PYTHONPATH=core:companies/video python -B -m unittest discover -s tests -v
```

**55개 발견,53통과/2skip/실패0/오류0,25.271초.** 기존60초 재제작 시험2개는skip. 새5개는 실제 파일/변조/미확보,카드·반복·길이,실제 사용자 원문·대상 선택/철회,음성/메모리/승인 게이트,실제15초 검토 제작을 검증했다. 기존 HTTPError mock의 cleanup ResourceWarning2개는 있었으나 테스트 실패는 없었다. 로그 `/tmp/audience_upgrade_20261110/integration.log`. 반복 전체 테스트/60초 렌더/모델 합성 없음.15초 검토1회(짧은 구성 segment3개 후 concat),A는 기존 PCM 연결만 수행. 추가 contact sheet/오디오 probe·decode는 재렌더/새 합성이 아니다.

기존 보호 일반 파일45,454개(기존 영상2편·모델·키/원장·신규 관리자 인수 준비 포함)의 SHA-256/목록 대조 결과 변경/삭제0,허용한 새 작업 폴더 밖 추가0. 근거 `/tmp/audience_upgrade_20261110/before.json`, `preservation.json`. 이전 실사용/동의/비용/시도/미확정 원장·.env 불변,과거Gemini1/1과 신규plan0/1 미사용. 외부 아카이브 미접근,reset/clean/삭제 없음. 기존 미추적 로그/JSON7개도 커밋하지 않음.

새 LLM/TTS 외부API0회,새 로컬 신경망 합성0회,새 모델/미디어 다운로드0,유료API추가 비용0원,사용자 미디어/키/원장 외부 전송·게시0. 공개 문서 검색·메타데이터 조회와 승인된 GitHub 텍스트/코드 반영은 수행했다. 이를 모든 네트워크 요청0으로 표현하지 않는다. 전송 정책2개는 비활성 유지. GUI/웹 서버 개발 없음.

## 사용자가 확인할 파일과 다음 단계

Codespaces 탐색기에서 아래 실제 파일 우클릭→Download:

- `data/video_quality_iteration/20261110T110100_KST/motion_study/visual_motion_study_15s.mp4` — **무음 시각 방향 검토**.
- `data/video_quality_iteration/20261110T110100_KST/contact_sheet.png` — 사람/업무 장면과 원문 대조5프레임.
- `data/video_quality_iteration/20261110T110100_KST/A_reference_melo.wav` — 기존 음성 기준 A만.
- 같은 폴더의 `tts_comparison_plan.md`, `asset_requests.md`, `evaluation.md` — 승인 범위·부족 자료·실제 상태.

마지막 완전한60초 시안은 여전히 `data/video_quality_iteration/20261110T102849_KST/preview.mp4`. 그 전 Flow60초는 `data/video_ai_clip_review/20261109T161931_KST/shorts/preview.mp4`이며 둘 다 덮어쓰거나 재렌더하지 않았다. 두 편 모두 사용자의 ‘큰 개선 없음/지루함/음성 어색함’ 평가를 이번에 반영했다.

지금 판단받을 것은 새15초의 움직임·원문 대조 방식이 방향에 맞는지이며 완성 영상 품질 평가는 아니다. 다음 우선순위는 조건을 갖춘 B 음성1회 비교와 미확보 장면의 실제 자산 확보/시연 구현이다. 실제 회사 모델이 소재·비판·직원 수정을 자율 수행한 제품 수준은 여전히 미검증이다.
