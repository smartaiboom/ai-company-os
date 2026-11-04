# 영상 제작 전문 회사 프로필·v2 도구와 실제 시각 샘플

2026-11-04 KST. `git pull --ff-only`로 22e69d8 반영. 핵심 원칙·AGENTS.md·지정 지시서·기존 회사/도구/동의/실행 기록을 확인했다.

**시각 개선 MP4와 영상 제작 전문 회사 프로필을 구축했다. 자연스러운 한국어 신경망 음성은 이번에 확보하지 못했다.** 아래 영상은 개발자가 작성한 도구 품질 데모이며 실제 AI 회사의 신규 납품물/E2E 성공이 아니다. 실제 Gemini·유료 API·외부 TTS·외부 이미지 API 요청0회다. 공개 기술 문서 조회와 Git 통신만 별도 수행했다.

## 실제 결과 파일과 보기/다운로드

프로젝트 루트는 `/workspaces/ai-company-os/ai-company-os-phase1`이다. 영상·프레임은 Git 제외 data 아래에 보존하며 GitHub에는 소스/테스트/이 보고서만 저장한다. GitHub에서 MP4가 호스팅된다고 주장하지 않는다.

| 파일(루트 기준) | 실제 검증 |
|---|---|
| `data/video-quality-pilot-20261104/visual-demo/video.mp4` | **시각 개선 무음 데모**, 24.000초,1280×720,H264,24fps,718926bytes. 오디오 stream0 |
| `data/video-quality-pilot-20261104/reference-voice/video.mp4` | 동일 비주얼+**기존 espeak 참고 음성**,24.02322초,1280×720,H264/24fps,AAC mono44100Hz,875597bytes. 자연스러운 음성 개선본 아님 |
| `data/video-quality-pilot-20261104/contact-sheet.png` | 실제 MP4에서 추출한 장면별 대표 프레임4개,1280×720 |
| `data/video-quality-pilot-20261104/visual-demo/keyframe-00.png` ~ `keyframe-03.png` | 장면 중간의 실제 렌더 프레임 |
| 각 샘플 폴더의 `spec.json`, `source-00.svg`~`source-03.svg`, `receipt.json` | 개발 fixture/생성 그래픽 원본/입력·출력·소스 hash, 라이선스, 타임라인, 음성 길이, 검증 결과 |

Codespaces 파일 탐색기에서 위 경로의 MP4를 열거나 우클릭 **Download**로 내려받을 수 있다. 터미널에서 파일 위치/해시를 확인하는 정확한 명령:

```bash
ls -lh data/video-quality-pilot-20261104/visual-demo/video.mp4 data/video-quality-pilot-20261104/reference-voice/video.mp4 data/video-quality-pilot-20261104/contact-sheet.png
sha256sum data/video-quality-pilot-20261104/visual-demo/video.mp4 data/video-quality-pilot-20261104/reference-voice/video.mp4
```

실측 SHA256: 무음본 `b8cd53c5d03e62838e0e4283f4808edc6670dcf18f46efca372b3623fc5dd58d`, 참고 음성본 `9a9b68ea9a47b12ebc517a45bc6ec3260111f6ad97a483e854311bdd4881b527`.

## 기존 대비 시각 차이와 실제 확인

기존 v1은 고정 단색 화면의 중앙 텍스트였다. v2 샘플은 독립 그래픽4종(대화창 일러스트, 목표/화살표, 단계 연결도, 전후 비교 카드), 그라데이션/곡선 배경, 제목/그래픽/하단 자막의 분리 배치, 느린 줌/팬과 페이드·컷 전환을 사용한다. 단순 텍스트 애니메이션 추가만으로 완료했다고 표시하지 않는다. 웹 사진/B-roll을 사용한 영상은 아니며, 절차적으로 생성한 정보 그래픽 중심의 설명 영상이다.

실제 keyframe-00과 4장 contact sheet를 이미지 뷰어로 직접 확인했다. 글자와 도형이 읽히고 목표·흐름·비교가 각각 다른 도형 구성으로 드러나며, 표본 프레임에서 잘린 글자는 보이지 않았다. 같은 첫 scene의1초/4초 RGB 프레임 hash가 달라 카메라 변화도 확인했다. 이것이 사용자 감상 만족도나 전문 편집자의 미적 평가를 대체하지는 않는다.

두 MP4 모두 ffprobe와 전체 ffmpeg 디코딩을 통과했다. 무음 모드에는 가짜 silent audio stream을 넣지 않았다. 참고 음성본의 실측 내레이션 길이는3.487211/3.668980/4.251383/3.496417초로 각6초 scene 안에 들어간다. AAC 전체 길이와 영상 길이 차이는0.2초 이내다. 평균 음량-22.1dB, 최대-0.5dB를 관측했으나 이것은 자연스러움/발음 품질의 증거가 아니다. 자막은 scene 시작·끝에 맞춘 **장면 단위 동기화**이며 단어 단위 강제 정렬은 구현하지 않았다.

## 회사 역할과 v2 도구 구현

변경 파일:

- `video_production_company.py`: 별도 VideoProductionStore/Company. Gemini35의 계획→직원→review/revision→인계→최종 보고 상태 기계를 재사용한다. 제작 총괄, 대본·구성, 소스·아트, 음성·편집, QA는 **선택 가능한 역량 목록**이다. 실제 목표의 역할 수/업무/기준/콘셉트·수정 판단을 고정 계획으로 강제하지 않는다.
- `production_video.py`: `production_video_v2` strict schema/검증/절차 SVG 그래픽/FFmpeg 카메라·전환·음성 참고·자막·키프레임/라이선스/receipt. 새 프로필만 해당 catalog를 사용한다. 외부 URL·사용자 소스 경로·임의 filter/shell/코드 입력은 받지 않는다.
- `video_quality_pilot.py`: 명확히 표시된 개발 fixture 및 무음/참고 음성 샘플 생성 명령. 특정 주제는 이 데모에만 있으며 renderer/회사 엔진의 업무 규칙이 아니다.
- `autonomous_free.py`: store별 도구 catalog/실행 훅의 최소 분리. 기본 catalog와 실행은 v1 그대로다.
- `autonomous_gemini35.py`: 도구 입력 검증 훅 분리. 기본 검증은 기존 v1 그대로다.
- `tests/test_production_video.py`, 이 보고서.

기존 `local_artifacts.TOOLS`/caption_video_v1은 변경하지 않았다. 새 profile은 별도 marker `.video-production-gemini35-v1-store`, mode/policy=`video_production_gemini35_v1`, prefix=`videocompany-`를 사용한다. 최초 동의안에 production_profile와 v2 catalog·외부 TTS/소스 비활성화를 명시하며, 누락/변조/이전 store로 로드하면 차단한다. 기존 서명 동의를 v2 승인으로 바꾸지 않는다.

새 회사는 목표 하나로 `VideoProductionStore.create(goal)`에서 생성하고 기존 prepare→최초 approve→run API를 사용한다. 별도의 UI/편집기/복구 프레임워크는 만들지 않았다. 실제 프로필 실행·동의는 이번에 발급하지 않았다. 정상 업무의 사용자 중간 결재를 추가하지 않는다.

AI가 palette/문구/그래픽/카메라/전환/scene 길이를 선택한다. 도구의 제한은16:9, 짝수640~1920폭, 최대12scene/120초, 입력/텍스트·메모리·레이아웃 등 기계적 범위다. 도구 원본 XML은 앱이 만들며 사용자 text는 XML escape한다. 필터는 allowlist enum에서만 생성한다. 경로/URL·SVG 원문을 입력으로 받지 않고 출력 symlink/덮어쓰기/허용되지 않은 TTS를 차단한다. 입력 오류·분류 가능한 렌더 오류는 기존 manager review/revision으로 연결하며 물리적 실패를 accept하지 못한다.

receipt의 검토 입력은 실제 scene keyframe/해시·storyboard kind·scene/자막 시각·측정 내레이션 길이·소스/라이선스·전체 decode 결과다. **현재 텍스트 모델에 이미지/오디오 바이트를 전송하는 기능은 추가하지 않았다.** 따라서 model_visual_review_performed/model_audio_review_performed=false다. 모델이 실제 영상을 봤거나 목소리를 듣고 검수했다고 표시하지 않는다. 자연스러운 음성이 필수인 목표는 현재 none/espeak_reference로 충족했다고 주장하지 말고 중단/운영 권한 요청하도록 profile에 명시했다.

## 출처와 권리

외부 사진·웹 영상·브랜드 로고·Pexels/Wikimedia 콘텐츠는0건 사용했다. PEXELS_API_KEY는 존재 bool=false만 확인했다. 새 키/계정 발급이나 이미지 API 호출은 하지 않았다.

그래픽은 이번 renderer가 자체 생성하는 도형/SVG이며 생성 자산의 CC0-1.0 정책·creator·개별 source hash를 receipt에 남겼다. 이 표기는 제3자 사진이나 코드 전체를 재라이선스한다는 뜻이 아니다. 한국어 글꼴은 설치된 Noto CJK이며 `/usr/share/doc/fonts-noto-cjk/copyright`의 SIL OFL1.1을 확인했다. 폰트 파일 자체를 새로 배포하지 않는다. 소스 검증 없는 외부 자료 자동 삽입은 지원하지 않는다.

## 자연스러운 한국어 TTS 비교와 현재 한계

환경은 CPU2개, 시스템 메모리 약7.8GiB, 디스크 여유14.8GiB였다(cgroup memory/cpu 추가 상한 표시는 max). FFmpeg의 SVG decoder/gradients와 한국어 폰트가 있어 새 패키지 설치 없이 제작했다. torch/transformers/melo/numpy/Pillow 및 HF 모델 cache는 없었다. 큰 런타임/가중치를 무단 다운로드하거나 서비스에 문장을 보내지 않았다.

| 후보 | 무료·권리·CPU 근거 | 외부 전송/이번 상태 |
|---|---|---|
| **MeloTTS-Korean, 우선 로컬 후보** | [제작자 모델 카드](https://huggingface.co/myshell-ai/MeloTTS-Korean)는 한국어 지원·MIT·CPU 실행 예제를 제공하고, CPU 실시간 가능은 제작자 주장이다. [코드도 MIT](https://github.com/myshell-ai/MeloTTS). 이번 장비의 속도/자연스러움은 미검증 | 로컬 추론 시 문장 외부 전송 불필요. 패키지·가중치 다운로드/설치 규모와 의존 모델 확인 필요. 설치/실행/청취0회 |
| Meta MMS-TTS Korean | [공식 모델 카드](https://huggingface.co/facebook/mms-tts-kor)는 한국어 checkpoint와 CC-BY-NC4.0. 로컬 PyTorch 추론 후보이나 이번 CPU 성능 미검증 | 문장 로컬 처리 가능, 가중치 다운로드 필요. 비상업 제한 때문에 상업 제작 기본 후보로 채택하지 않음. 호출/설치0회 |
| Azure Speech Neural ko-KR | [공식 F0 가격표](https://azure.microsoft.com/en-us/pricing/details/speech/)는 neural 월50만 문자 무료, [공식 voice 목록](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts)에 SunHiNeural 등 한국어 포함. 해당 계정/지역의 F0 조건·키·quota는 미확인 | Azure로 내레이션 text/voice·설정 송신. 별도 공급자/무료 계정·금액0 상한·정확한 전송 문장 범위 동의 전 요청 금지. 계정 생성·키 입력·호출0회 |

edge-tts/공개 HF Spaces를 공식 무료 production API로 간주하지 않았고 호출하지 않았다. Gemini의 기존 동의를 다른 TTS 공급자 승인으로 확대하지 않았다. 현재 샘플의 espeak는 기존 기술 참고 음성 그대로이며 '신경망 TTS 향상 완료'가 아니다. 따라서 **사용자의 자연스러운 한국어 음성 품질 기준은 미달**이다.

다음 우선 조치는 **MeloTTS-Korean 로컬 실행을 별도 격리 환경에서 용량/라이선스 확인 후 제한된 설치·음성 청취 평가로 검증하는 것**이다. 이번 결과를 미루지 않도록 시각 샘플을 먼저 남겼다. Azure 등 외부 경로를 선택한다면 제공자/계정 F0·한도/한국어 내레이션 원문과 voice 설정 전송 범위를 별도 명시 동의해야 하며, 현재는 해당 송신 구현/권한이 없다.

## 실제 실행 명령과 테스트

실행한 샘플 명령(기존 경로 덮어쓰기 거부, 재생성 시 새 output 경로 사용):

```bash
python -B video_quality_pilot.py --output data/video-quality-pilot-20261104/visual-demo
python -B video_quality_pilot.py --output data/video-quality-pilot-20261104/reference-voice --reference-voice
ffmpeg -nostdin -v error -pattern_type glob -i 'data/video-quality-pilot-20261104/visual-demo/keyframe-*.png' -vf 'scale=640:360,tile=2x2' -frames:v 1 -threads 1 data/video-quality-pilot-20261104/contact-sheet.png
```

```bash
python -B -m unittest tests.test_production_video tests.test_local_artifacts tests.test_nested_tool_review tests.test_internal_tool_review tests.test_autonomous_gemini35 tests.test_autonomous_gemini tests.test_autonomous_free tests.test_autonomous_groq
```

**68개 통과, 실패/오류0, exit0(47.163초)**. profile 전용 동의/catalog 격리, URL/팔레트/타입/초과·잘못된 입력, XML injection escape, 오디오 비활성, symlink/덮어쓰기, 가상 회사의 도구 실패→manager revise→직원 수정→실제 v2 로컬 MP4→인계→최종 보고까지 검증했다. 해당 fixture는 fake API8회/실 API0회/사용자 업무 승인0회다. 기존 v1·Gemini3.1/3.5·Groq/OpenRouter 및 내부 수정/원장 보호 회귀도 포함했다.

profile의 v2 도구 필수 조건/자연음성 미충족 안내를 보강한 뒤 `python -B -m unittest tests.test_production_video`를 추가 실행해 **3개 통과(1.224초)**를 확인했다. 샘플2개는 별도로 ffprobe·전체 decode와 키프레임 직접 열람을 검증했다. `git diff --check` 통과.

기존 data/backups/checkpoints **128개 파일 SHA256 전후 모두 동일**. 특히 보호 대상 delivered 프로젝트는 delivered/시도8/artifact3 그대로 load됐으며 모든 기존 영상·동의·원장·백업·사용자 미추적 파일을 보존했다. 이번 신규 실제 AI 프로젝트/외부 음성 호출0회다.

이번 변경은 목표→제작 전문 AI 역할 협업→내부 검토/수정→더 풍부한 실제 media 산출물을 위한 도구와 관찰 근거를 추가했다. 실제 새 AI 회사 E2E와 자연스러운 한국어 음성은 아직 미완료다. 기존 수동 경로 승인 부채는 유지되지만 새 업무 중간 결재는 추가하지 않았다. 외부 TTS 동의는 업무 결재가 아닌 새로운 데이터 전송 안전 경계로 남는다.
