# Qwen 한국어 TTS A/B 실행 결과 — 2026-11-10 KST

## 판정: 자원 게이트 실패, 다운로드·설치·B 합성 미실행

최신 main `532caa6`과 AGENTS.md/실행 지시서를 확인했다. **사용자의 조건부 승인(모델1종/최대6GB/B최대1회/600초)은 받았으나,현재 가용RAM 조건에 미달해 실행하지 않았다.** 추가 승인이 없는 상태라고 잘못 설명하거나,조건을 완화해 진행하지 않는다. CapCut 수준의 음성 또는 A/B 완료를 주장하지 않는다.

측정 시각 `2026-11-10T11:24:19+09:00`. 실제 준비 폴더:
`/workspaces/ai-company-os/data/tts_quality_ab/20261110T112419_KST`

## 지금 측정한 안전 게이트

| 항목 | 실제 값 | 조건/판정 |
| --- | --- | --- |
| CPU |2 logical CPUs |로컬 CPU만 허용 |
| RAM 총량 |8,328,077,312bytes (8.328GB) |총량을 가용량으로 대신하지 않음 |
| 호스트 MemAvailable |3,886,338,048bytes |현재 측정값 |
| cgroup memory.max |`max` |조회한 cgroup에 유한 제한 미표시. 호스트가 무제한이라는 뜻 아님 |
| cgroup memory.current |2,528,681,984bytes |호스트 가용RAM을 대체하지 않음 |
| 실효 가용RAM |3,886,338,048bytes (3.886GB) |6,500,000,000bytes 이상 필요 → **실패** |
| 부족량 |2,613,661,952bytes |임계값을 낮추지 않음 |
| swap |0bytes |추가/변경 안 함 |
| 디스크 여유 |11,398,340,608bytes (11.398GB) |8,000,000,000bytes 이상 → 통과 |
| Python3.12 / GPU |Python3.12 존재 / GPU 장치 미발견 |환경 생성·패키지 설치 안 함 |

원자료 `resource_precheck.json`. 기존 `tts_candidate_gate()`를 조건부 승인=true와 현재 실효 자원으로 평가했고 memory blocker만 반환했다. 유한 cgroup 제한이 있다면 그 headroom과 호스트 MemAvailable 중 작은 값을 쓰도록 측정했다. 이번 cgroup은 max로 표시돼 호스트 MemAvailable을 사용했다. GB는10억bytes 단위다.

가중치 다운로드/의존성 설치/추론을 시작하지 않았고,다른 프로세스 강제 종료·swap 확대·제한 우회·GPU/클라우드 대체도 하지 않았다. 메모리가 늘기를 기다리는 반복 실행이나 게이트 재도전 없음.

## 모델·설치·다운로드·합성 기록

- 허용 모델: `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`,Korean/Sohee preset.
- 고정 대상 revision: `85e237c12c027371202489a0ec509ded67b5e4b5` (이전 공식 조사에서 선택한 값).
- 이전 조사: [공식 코드](https://github.com/QwenLM/Qwen3-TTS)/[모델 카드](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice)에 코드·가중치 Apache-2.0 표시. Sohee 프리셋/생성물 상업 사용권은 독립 확인이 안 돼 게시 불가. CapCut 음성/성우를 추출·복제하지 않았다.
- 모델 repo 약2.5GB와 qwen-tts0.1.1 등은 **이전 준비 조사값**이다. 이번에는 RAM 게이트에서 중단해 현재 패키지 전체 다운로드·캐시/설치 크기·라이선스 재조회를 진행하지 않았다. 총 필요 다운로드 바이트는 미확정이며 6GB 내 설치 가능하다고 단정하지 않는다.
- `download_receipt.json`: 실제 다운로드 **0bytes**,환경 생성/설치 없음,한도6,000,000,000bytes. 의존성 resolution/pip dry-run/자동 모델 로딩 안 함.
- `synthesis_receipt.json`: **B 시도0/1**,600초 타이머/추론 미시작,B_file=null. 성공/실패/시간초과의 합성 시도 자체가 없었다. 따라서 승인된1회를 소모했다고 기록하지 않는다. 향후 실제 시작 전에는 별도 지속 선예약/단일 실행 검증이 필요하다.

## 실제 A와 미생성 B

A 사본 실제 경로:
`/workspaces/ai-company-os/data/tts_quality_ab/20261110T112419_KST/A_reference_melo.wav`

원본은 `data/video_quality_iteration/20261110T110100_KST/A_reference_melo.wav`. 정확 사본으로 해시 일치:
`a011f8bb6b83e5d3515171bcdf6fc9e9aa09d42844f8e14cfbb8955de18b25a5`

동일 발화문은 새 폴더의 `ab_script.txt`,원문 파일 SHA-256:
`ec1e2906fd065530a2bbfc79bfab9d3769a9f72296897887f5b02d4efeeffa59`

A 확인: 10.982109초,PCM16bit/44.1kHz 모노,ffprobe·전체 FFmpeg decode 통과. RMS=0.141353,peak=0.848969,클리핑비율=0.000000,저진폭비율(절댓값≤32/32768)=0.326930. 이 비율에는 쉼/배경 저진폭이 포함되며 발음·자연스러움 합격 지표가 아니다. 상세 `A_verification.json`. A 새 합성·가속·리샘플·발음 잘라내기 없음.

**B WAV는 없다.** B codec/길이/실제 발화 내용·발음과 A의 일치도는 아직 검사할 수 없다. 존재하지 않는 B 경로/해시를 만들지 않았다. `comparison.md`와 `synthesis_receipt.json`에 보류 상태를 명시했다.

## 사용자 품질 목표·제품 연결·검증 범위

‘예전에 CapCut의 음성이 자연스럽고 좋았다,그 정도 수준을 원한다’는 실제 사용자 목표를 새 별도 ExperienceJournal/`quality_target.json`에 `user_structured`로 보존했다. fixture 아님. 적용 대상은 한국어 직장인 AI 초보자로 한정한 가설이며 개선 효과 검증은 아니다. CapCut 음성/성우 복제 승인은 false,자동 자연스러움 판정은 false,사용자 청취 필요는 true다. 기존 저널/원장은 수정하지 않았다.

기존 자원 게이트·해시·원자적 파일 저장·음성 검사 실행기를 재사용했고 **제품 소스 코드는 변경하지 않았다**. 지시서의 RAM 미달 시 종료 분기를 수행했으므로 불필요한 Qwen runner/설치 로직을 추가하지 않았다. 회귀 테스트 재실행0회(코드 변경 없음). 필요한 실제 검사만 이번 묶음에서1회: 자원 게이트→원문/A사본 해시 대조→WAV 프레임/RMS/peak/클리핑 분석→probe/전체 decode. 모든 검사 조건에 대한 assert 통과. 새60초 영상/다른 모델 비교/새 로컬 신경망 합성0회. `git diff --check` 통과.

사용자가 B를 실제로 듣기 전 자연스러움·발음·강약/리듬·감정/친근함·CapCut 목표와의 거리는 **미평가**다. 기존 Melo에 대한 ‘어색함’ 평가를 기술 검사로 덮지 않는다.

## 보존·비용·다음 가장 작은 조치

새 파일은 위 `data/tts_quality_ab/20261110T112419_KST/`에만 생성했다. 기존 Flow·Melo·MP4·모델·비용/동의/시도/미확정 원장·키·새 관리자 인수0/1 상태를 변경하거나 재실행하지 않았다. 원본 A/대본은 읽기와 SHA 대조만 했다. 기존 미추적 로그/JSON7개는 그대로 두고 커밋하지 않는다.

실제 LLM/TTS API0회,모델/패키지 다운로드0bytes,새 음성 합성0회,추가 과금0원,사용자 자료/키/음성 외부 업로드·게시0. 기존 GPT/Gemini 차단2개 유지. GUI/웹 서버/새60초 렌더 없음. GitHub에는 이 결과와 진행 상태 텍스트만 반영한다.

가장 작은 다음 조치는 **가용RAM6.5GB 이상·디스크8GB 이상을 확보한 CPU 환경에서 동일 범위의 사전 점검을 다시 수행하는 것**이다. 사용자가 불필요한 자신의 작업을 정리하거나 이미 여유 있는 환경을 선택할 수 있지만 에이전트가 프로세스 종료·유료 환경 확장·swap 증설을 실행하지 않는다. 현재 승인 범위를 다시 요청하지 않으며 조건 충족도 추정하지 않는다. 충족 시에도 다운로드 예상 합계6GB/라이선스/단일 선예약과600초 제한을 확인한 뒤만 B1회 가능하다. 오늘은 B 생성/청취 비교가 완료되지 않았다.

보존 최종 확인: 기존 일반 파일45,499개의 SHA-256·파일 목록이 모두 일치했다(변경/삭제0,허용된 신규 A/B 폴더 밖 추가0). 새 폴더에만11개 파일 추가. 로컬 근거 `/tmp/qwen_tts_ab_20261110/before.json`, `preservation.json`. 준비 필수 파일의 실제 존재와 B 파일 부재/다운로드0bytes/합성0시도를 다시 대조했다. 데이터/원장/음성/키/해시 원장은 커밋하지 않는다.
