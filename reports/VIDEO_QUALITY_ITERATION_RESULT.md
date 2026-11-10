# 품질 개선 실물 영상 결과 — 2026-11-10 KST

## 실제 완료와 재생 경로

**새60초 한국어 세로 MP4를 제작했다.** 입력 클립 반복 대신 질문 전후/조건 강조/문장 구성/사실 점검을 보여 주는 로컬 설명 그래픽으로 바꿨다. 수치 결함과 예시 전달 방식을 개선한 **사용자 평가용 시안**이며, 더 높은 감각 점수나 유튜브 게시 합격을 선언하지 않는다.

- 기존: `/workspaces/ai-company-os/data/video_ai_clip_review/20261109T161931_KST/shorts/preview.mp4`
- 새 영상: `/workspaces/ai-company-os/data/video_quality_iteration/20261110T102849_KST/preview.mp4`
- 새 파일 실제 크기809,607bytes, SHA-256 `96be6f1aaa6e9e9a9d81c345895ae57d0f40f0066b1828e05f29b4bd48a53424`.
- 두 파일 모두 실제 존재·ffprobe·전체 FFmpeg decode 통과. 새 영상60.000초,720×1280/9:16/SAR1:1,H.264/24fps/1440frames,AAC/44.1kHz 모노. 기존 영상도60초/720×1280/H.264/AAC 확인.
- 기술 영수증: 새 폴더의 `receipt.json`, `verification.json`, `baseline_media_check.json`. 검토 이미지 `review_contact.png`, `keyframe-06.png`.
- 코드·테스트·사용법 커밋 `4bcf30c` (`Render offline instructional Shorts with measured speech and quality guards`), 시작 main `1a362dc`. 보고서는 별도 결과 커밋으로 main에 함께 반영한다. MP4/음성/프로젝트 데이터는 로컬만 보존한다.

## 기존 시안과 새 시안의 실제 차이

| 항목 | 기존 | 새 영상 및 근거 |
| --- | --- | --- |
| 콘텐츠 | ChatGPT 시작/조건/수정/안전 안내를 B-roll 위에 설명 | ‘누구에게·무슨 일·원하는 답의 모양’ 한 메시지. 일정 변경 문자 한 사례로 전후 질문과 적용법 제시 |
| 도입 | “챗지피티가 처음인가요? 문장 하나부터 시작해 보세요.” | 첫3초 “답변이 너무 길다면?”과 긴 답의 시각적 문제 제시. 기존 실제 영상이20초 인사였다고 조작하지 않음 |
| 외부 움직임 소스 | 사용자 제공 Flow3개, 각 약7.93초.15.167/21.917/22.917초로 배치 | Flow 사용0개. 로컬 설명 장면10개,그래픽 빌드30파일/고유 이미지23개 |
| 외부 클립 추가 반복 | 총5회(장면별1/2/2) | 0회. 정지 그래픽 유지/단계별 노출은 존재하며 외부 영상의 반복과 구분 |
| 장면-말 대응 | 노트북/노트 B-roll | 짧은 질문→빠진 길이→대상→시계/변경 시간→정중한3문장→전체 질문→답의 구성→확인→요약 |
| 음성 | 기존6구절,발화55.181초 재사용 | 최종 대본과 일치하는 새10구절,발화52.755초. 기존 로컬MeloTTS CPU1회 프로세스/10구절 합성,속도1.0. 음성 잘라내기/가속 없음 |
| 자막 |14cue,발화 경계 실측/구절 추정 |15cue,최대2줄/줄당24폭단위(한글 전각은2),최대5.64문자/초. 대본 손실/음성 텍스트 불일치0건 |
| 사용자 감각 점수 | 과거 주관적2~3/10 | 미평가.7/10 달성 주장 없음 |

새 입력 예시는 “직장 동료에게 보낼 문자야 / 내일 회의를 오후 세 시로 바꿔 / 정중하게, 세 문장 이내로”처럼 바로 따라 쓸 내용을 실제 화면에 보여 준다. 응답 부분은 실제 생성 답변을 꾸미지 않고 ‘변경 안내→바뀐 시간→확인 요청’이라는 **확인할 구성 예시**만 제시한다. 전 장면에 ‘예시 화면·실제 앱 녹화 아님’을 고지했다. 이 자료는 새 웹 GUI가 아니라 영상 안의 설명용 그래픽이다.

## 문제→판단→수정→재검토의 실제 증거

이번 실제 콘텐츠 판단 주체는 **Codex authored/offline editorial judgement**다. 관리 역할로 초안을 비판하고 작성/편집/음성 작업을 수행한 기록이며, AI Company OS의 관리자·직원 모델이 자율 추론한 사례가 아니다. 새 대본은 기존 QUALITY_REVIEW의 두부·달걀 고정 fixture를 복사하지 않았다.

새 작업 폴더에 다음 원본/수정/인수 기록을 보존했다.

- `script_draft.md`, `plan_draft.json`: 새 제작 초안.12초 인사 태그·핵심 메시지 누락·6초 동일 소스20초 반복 계획의 문제.
- `inspection_before_after.json`, `manager_revision.json`: 수치 결함6건(길이 초과3/중복 소스1/메시지 누락1/도입1)을 담당·근거·수정 요청으로 인계. 최종 `plan_inspection.json` 해당 제약 결함0건. 이는 수치/작성자 태그 검사이며 의미 흥미의 자동 평가가 아니다.
- `script.md`, `shot_plan.md`, `plan.json`: 새 대본·10개 의미별 편집 장면. 로컬 설명 소스의 실제 생성 범위를 명시.
- `plan_before_visual_revision.json`, `visual_revision.json`: 정지화면 검토 중 질문 카드의 마지막 단어 단독 줄바꿈을 발견해 더 짧은 문구로 수정. 최종 렌더 전 반영.
- `handoff.json`: 초안/시각 검토 전/최종 plan의 파일명과 실제 해시, 판단 주체/작업 인계 경로.
- `speech/request.json`, `speech/receipt.json`: 새 대본과 실제 WAV를 텍스트·해시·실측 발화 길이로 대조. 이전 대본의 음성을 억지로 끼워 넣지 않음.
- `timeline.json`, `captions.srt`, `captions.ass`: 첫 장면3초,전체60초,실측 음성/자막 구간. 음성 전체를 유지하고 남는 시간을 읽기/쉼 구간으로 배정. 발화 내 구절 정렬은 문자 비중 추정이고 단어 단위 alignment를 보장하지 않음.
- `evaluation.md`: 실제 장면별 시작/끝·대본·화면 대응 표와 전후 수치. `verification.json`: 자막 원문 보존/경계·코덱·프레임·반복/검토 한계.

실제 출력에서10개 샘플 프레임과 질문 카드 확대 프레임을 Codex가 확인해 글자/자막 잘림·가림을 발견하지 못했다. 전 구간 연속 시청과 청취 자연스러움 검증을 수행했다는 뜻은 아니다. 감각 품질의10점 평가 항목은 미평가로 남긴다.

## 재사용 가능한 제품 코드와 검증

`companies/video/editorial_video.py`는 기존 ClipJob의 잠금·원자적 상태 저장, MeloLocal의 로컬 모델/네트워크 차단, 자막 writer, SVG 텍스트 줄바꿈, media probe와 전체 decode를 재사용하는 별도 설명 장면 합성 도구다. 외부 클립 fixture로 가짜 출처를 채우지 않는다. 기존 수치 QA를 사용해 반복·원본 길이 초과·명시 메시지/도입/레이아웃 결함을 렌더 전에 검사하고, 음성/자막/미디어 검사와 연결했다. 실패/중단/완료 후 같은 job의 중복 렌더를 거절한다. 기존 provider 승인 구조를 다시 설계하거나 전역 차단을 열지 않았다.

새 테스트 `tests/test_editorial_video.py`4개 안전 시험+실제 로컬 제작1개를 기존 회귀와 **한 번** 통합 실행:

```bash
env -u AI_CLIP_ACCEPTANCE_ROOT VIDEO_EDITORIAL_ACCEPTANCE_ROOT=/workspaces/ai-company-os/data/video_quality_iteration/20261110T102849_KST PYTHONPATH=core:companies/video python -B -m unittest discover -s tests -v
```

**50개 발견,49통과/1skip/실패0/오류0,214.351초.** 기존 MeloTTS+Flow baseline 인수1개는 의도적으로skip하고 이번 새 실물 제작 인수만 실행했다. 로그 `/tmp/video_quality_iteration_20261110/integration.log`. 최종 실물60초 MP4 렌더1회,새 로컬TTS 프로세스1회/10구절. 기존 회귀의 짧은 로컬 코덱 fixture 렌더는 별도 포함된다. 추가 최종 영상 재렌더/모델 재합성 없음. `git diff --check` 통과. 실제 출력 keyframe 추출/전체 decode/추가 영수증 검사는 재렌더가 아니다.

## 원본·원장·권리·비용

기존 일반 파일45,349개와 새 관리자1회 준비 폴더의7개,합계45,356개를 SHA-256·목록으로 대조해 변경/삭제0,허용된 새 영상 작업 폴더 밖 추가0 확인. 새 결과물은 위 `data/video_quality_iteration/20261110T102849_KST/`에만 추가했다. 로컬 근거 `/tmp/video_quality_iteration_20261110/before.json`, `preservation.json`. 기존 입력 Flow·음성/영상·모델·동의·비용/시도/미확정 원장·.env 불변,외부 백업/아카이브 미접근,reset/clean/삭제 없음. 기존 미추적 로그/JSON7개는 커밋하지 않는다.

외부 관리자/직원 LLM API0회,추가 유료 API비용0원,새 모델 다운로드0,외부 미디어 업로드/게시0. 기존 로컬 신경망 음성 합성은 위와 같이 실제 실행했으며 ‘AI 추론 전체0’으로 오인시키지 않는다. MANAGER_PLAN_EXECUTION_ENABLED=False/QUALITY_TRANSPORT_ENABLED=False 유지,과거 Gemini1/1과 새 plan0/1 원장 미사용·불변.

기존 Flow 출처는 사용자 진술이고 라이선스·상업권/워터마크 미확인 상태를 그대로 둔다. **새 영상에는 Flow를 쓰지 않았다.** 새 벡터는 로컬 코드 생성 설명 그래픽이며 source_assets에 작성자·해시를 기록했다. Noto CJK 폰트는 기존 OFL 표기를 유지한다. MeloTTS 가중치/음성의 실제 상업 사용권을 독립 확인하지 않았고 사용자 품질 평가가 없어 **publish_ready=false**. 새 영상이 자동으로 게시 가능한 완성품이라는 뜻은 아니다.

## Codespaces에서 비교·다운로드

1. 왼쪽 탐색기에서 `data/video_quality_iteration/20261110T102849_KST/preview.mp4`를 찾는다. 파일 우클릭→Download로 새 시안을 받는다.
2. 기존 비교 파일은 `data/video_ai_clip_review/20261109T161931_KST/shorts/preview.mp4`. 별도 이름으로 받아 두 영상을 재생한다.
3. 새 폴더의 `review_contact.png`는10장면 한눈 비교, `script.md`/`shot_plan.md`/`evaluation.md`는 대본·장면별 근거, `captions.srt`는 전체 자막이다. 바이너리는 GitHub가 아닌 Codespaces 로컬에 있다.

사용자에게 확인받을 핵심3가지:
- 첫3초의 문제 제시와 질문 전후 예시가 기존 영상보다 명확한가?
- 이 영상을 보고 본인 상황의 질문을 바로 써 볼 수 있는가?
- 음성의 어조·속도와 자막의 읽기 속도가 편한가? 가장 거슬리는 구간은 어디인가?

아직 부족한 것은 반복이 없는 것 자체를 넘어선 몰입감, 카드/단계별 노출 위주의 화면 리듬,실제 음성 자연스러움/세부 자막 싱크,실제 모델의 기획·비판·직원 수정 능력이다. 다음 우선순위는 이 실물의 구간별 사용자 평가를 저장·재사용하고,개별 승인된 관리자 plan1회로 실제 모델 전략을 별도 평가하는 것이다. 새 provider 개발 반복·GUI·무승인 다회 호출은 하지 않는다. 실제 앱 시연/추가 소스나 다른 음성 도구가 필요해지면 권리·비용·범위를 따로 확인한다.
