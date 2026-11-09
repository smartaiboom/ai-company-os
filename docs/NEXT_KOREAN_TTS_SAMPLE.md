# 다음 작업: 한국어 TTS 실제 샘플 검증 (2026-11-09 KST)

## 결정과 완료 기준
첫 기술 시안의 espeak_reference 음성은 사용자가 **내용을 알아들을 수 없다고 직접 평가**했으므로 실패다. 영상 연출/질문 프롬프트보다 한국어 음성 이해도가 최우선. 사용자 청취 전까지 "자연스러운 음성 품질 통과"나 "완성 영상"으로 판정하지 않는다.

이번 작업은 **짧은 실제 한국어 음성 파일을 생성하고 청취할 수 있게 만드는 것**까지. 60초 영상 재제작, ChatGPT 실제 계정 접속/화면 녹화, 새 Gemini/기타 유료 API 요청, 자동 업로드는 범위 밖이다.

## 원본과 환경
- 먼저 AGENTS.md, companies/video/production_video.py, core/local_artifacts.py, 기존 data/video_baseline_review/20261109T132912_KST/narration.txt 및 script.md, 확정된 인수 초안 출력물을 확인.
- 기존의 확정 인수 초안 / 호출 원장 / 원본 preview.mp4 / Codex 로컬 보관본 / 백업 삭제·수정 금지.
- 기존 Python/FFmpeg 의존성/실행 환경을 조사하고 기존 renderer/AI Company OS 코드를 보존. 별도 독립 환경(.venv 또는 해당 별도 환경)을 사용하고 기존 환경을 깨지 말 것. 설치 용량·다운로드·메모리 확인 후 용량 부족이면 안전하게 중단.

## 1차 TTS 후보
- 공식 원본 https://github.com/myshell-ai/MeloTTS ; 한국어 모델 https://huggingface.co/myshell-ai/MeloTTS-Korean . 프로젝트 및 모델 카드 모두 MIT 표기. 실제 사용할 특정 모델의 라이선스와 필요한 모델 아티팩트를 재확인.
- 공식 예: from melo.api import TTS; model=TTS(language='KR',device='cpu'); speaker_ids=model.hps.data.spk2id; model.tts_to_file(text,speaker_ids['KR'],output_path,speed=1.0).
- 반드시 공식 저장소/공식 모델만 사용하고 부적합한 유사 이름의 포크·임의 서드파티 유료 서비스는 쓰지 않는다.
- 설치 시 CPU/Python 버전/torch/PyTorch 의존성, 미지원 버전, 모델 자동 다운로드/외부 네트워크 전송 범위를 먼저 확인. 한국어 일반 비민감 샘플 텍스트 외 사용자/회사 데이터·키·로그를 외부 서비스로 보내지 말 것. 모델/패키지 **다운로드는 가능**하지만 추론은 로컬 CPU, 새로운 클라우드 추론/API 호출 금지.
- MeloTTS 설치가 현재 Codespaces에서 파이썬/시스템 리소스/의존성으로 불가능하면 이유를 실측하고, 아키텍처 오염 없이 더 가벼운 **무료/로컬** 한국어 TTS 대안 하나를 현실적으로 검토. 설치가 어려운 상황을 숨기거나 음질이 좋아졌다고 쓰지 말 것.

## 샘플 제작
1. 기존 60초 샘플의 실제 대본에서 연속된 **15~20초 분량** 한국어 발화 원고를 사용한다. 초보자 대상 설명의 이해도를 평가할 수 있도록 영어 고유명사(예: ChatGPT) 1개 이상 포함.
2. 기본 자연 속도로 WAV 또는 MP3로 생성; 수동 비교를 위한 다른 속도 버전이 쉽게 가능하면 0.9~1.0x 범위에서 최대 하나 추가. 임의로 너무 빠르게 재생하지 않는다.
3. data/tts_korean_review/YYYYMMDDTHHMMSS_KST/ 아래 sample_ko.wav (또는 mp3), sample_script.txt, tts_evaluation.md, 실행 설정/메타데이터를 저장. 생성된 샘플은 사용자에게 재생 가능해야 한다. gitignore 영역 사용, 모델 체크포인트·큰 wav를 Git commit 금지.
4. ffprobe로 지속 시간·샘플레이트·채널 및 파일 열기·전체 디코딩 정상 여부를 확인. 무음/비정상 길이/깨진 오디오 검출. ffprobe만으로 '자연스러움' 판정 금지; **사용자 청취 판정 대기**.
5. 가능하다면 향후 교체가 쉬운 TTS adapter/설정 경계 설계는 간단히 기록하되 **샘플을 직접 듣기 전 영상 제작 엔진과의 본격 통합/규격 확대/웹 UI 개발은 보류**. 기존 코드를 불필요하게 대규모 수정하지 않는다.

## 안전·비용
- 이미 실제 Gemini 목표 문답 호출 1/1 사용. 이번 작업의 실제 AI API 호출 **0회**. Gemini/외부 TTS API/사용량 과금/재시도/회사 handoff 금지.
- 로컬 모델 다운로드가 일어나면 네트워크 출처·모델 명·용량을 기록. 무료 라이선스와 무과금 확인. 기업/개인 비공개 콘텐츠 외부 전송 금지.
- 기존 승인과 별도로 API 비용·유료 서비스가 필요하면 **실행 중단** 후 사전 승인 요청.

## 보고
- 통합 실행/파일 검증 1회 완료 시에만 docs/IMPLEMENTATION_STATUS.md 마지막에 짧게 결과 추가하고 GitHub push(필요하면). 실제 샘플 위치와 생성 성공 여부, 라이브러리/모델, 초 단위 길이, 사용자 청취 대기, 해결되지 않은 이슈만 보고.
- Codespaces 파일 탐색기에서 sample_ko.wav 파일을 Download해 듣는 방법 안내. 테스트가 실패했다면 장애 원인, 실행 시도/환경 훼손 여부, 대안만 간결히 보고.
- 핵심: **소리가 나는 한국어 실파일**이 없으면 성공이라 표현하지 않는다.
