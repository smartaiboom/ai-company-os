# Qwen3-TTS 음성 A/B 시험 실행 — 2026-11-10 KST

## 지금 실행할 실제 개발 지시
읽기만 하고 종료하지 말 것. 사용자는 **CapCut에서 듣던 자연스럽고 친근한 한국어 TTS 수준**을 품질 목표로 정했다. **Qwen3-TTS-12Hz-0.6B-CustomVoice, Korean Sohee** 한 모델에 한해서 조건부 다운로드/독립환경 설치(총 다운로드 최대 6GB)와 동일 대본 B 샘플 **최대 한 번** 생성을 승인했다. 이는 CapCut 음성·성우 복제 승인이나 품질 보증이 아니다.

## 선행자료
AGENTS.md, reports/USER_FEEDBACK_QUALITY_UPGRADE_RESULT.md, reports/CURRENT_PROGRESS.md, 새 작업 폴더 data/video_quality_iteration/20261110T110100_KST/tts_comparison_plan.md, A_reference_melo.wav, 관련 대본/receipt, companies/video/local_melo_tts.py 및 기존 테스트와 git status를 먼저 확인. 기존 코드·원장·영상·기존 모델과 미추적 파일 모두 보존. git clean/reset hard 금지.

## 실행 안전 게이트
1. **지금의** CPU, RAM(총량/가용량/cgroup 제한), 디스크 여유와 설치에 필요한 예상 총 다운로드 바이트, 설치 후 안전 여유, 모델과 패키지 버전/라이선스를 측정. 과거 보고 기준 CPU2/RAM 8.33GB/가용 3.95GB/swap0/디스크11.4GB/GPU 없음.
2. 사전 합의한 **가용 RAM 6.5GB 이상, 디스크 여유 8GB 이상**이라는 보수적 게이트를 충족하지 않으면 **가중치 다운로드·의존성 설치·합성 작업을 진행하지 말 것**. 다른 프로세스 강제 종료, swap 강제 증설, 메모리 한계 우회 금지. 조건이 안 되면 정확한 수치와 안전한 다음 선택지를 보고서에 남기고 종료.
3. 조건 충족 시 공식 https://github.com/QwenLM/Qwen3-TTS 및 https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice 출처만 이용. 정확한 revision/파일 크기와 코드·가중치·Sohee 음성/생성물 라이선스 확인. 모델+패키지+캐시 다운로드 누적 **최대 6GB**. 사전 추정 초과/불명확/유료 계정 필요 시 중단. 모델과 패키지는 새 gitignored 경로 및 독립 Python 환경에만 설치, 기존 Melo 환경과 기본 Python 변경 금지. 모든 모델 파일 다운로드는 승인된 해당 모델과 필요 의존성에 한정. GPU 또는 클라우드 API가 필요하면 중단.
4. 개인정보·기존 영상·오디오를 외부 업로드하지 않으며 무료 로컬 CPU 추론만 수행. 현재 GPT/Gemini 관리자·직원 외부 호출 차단은 유지하고 추가 LLM API 호출0회/비용0원/게시0.

## A/B 청취 샘플
1. 기존 A 파일 data/video_quality_iteration/20261110T110100_KST/A_reference_melo.wav 와 관련 원문을 그대로 기준 삼는다. **B도 정확히 같은 대본**이어야 한다. 길이는 동일 발화문 약10~15초; 텍스트/발음 후보가 다르면 제대로 된 A/B라고 하지 말 것. A 새 합성 금지.
2. 조건 충족 때에만 Qwen 0.6B Korean Sohee로 B WAV **최대 1번 생성**. 600초 상한, 실패·오류·중단·시간초과 시 자동 재시도/새 모델 우회 금지. 일관된 샘플 rate/코덱 차이와 내용 동일성을 검증.
3. 별도 폴더 data/tts_quality_ab/<새 KST 식별자>/에 동일 대본, A 원본 사본(해시 일치), 성공 시 B_qwen_sohee.wav, resource_precheck.json, download_receipt.json, synthesis_receipt.json, comparison.md 저장. 실제 WAV가 없으면 경로를 꾸며내지 말 것.
4. ffprobe/전체 decode/길이/RMS/피크/클리핑/무음/정확 텍스트 해시를 확인. 자연스러움·감정·친근함·발음 품질은 **사용자가 실제 듣기 전 미평가**. CapCut 수준이라고 미리 주장하지 말 것. 가중치/Sohee 프리셋 상업 이용 조건 불명확하면 게시 불가 표기.

## AI Company OS 발전/기록
- 기존 companies/video TTS 품질 계약에 반복 가능한 음성 모델 A/B 비교 기록, 입력/출력 해시, 발화/음향 기술 검사, 사용권 불확실성, 사용자 청취 평가(향후 입력)/선택적 경험 재사용을 중복 개발 없이 최소 통합.
- 사용자가 “예전에 CapCut의 음성이 자연스럽고 좋았다, 그 정도 수준을 원한다”고 평가했다는 사실을 정확히 보존. 제품이 목소리 자연스러움을 자동 판정했다고 주장하지 말 것.
- GUI·사용자 화면, 새로운 60초 영상 렌더, 모델 다중 비교 시험 및 불필요한 대규모 리팩터링 금지.
- 기존 자산/비용·승인·호출 원장/이전 Flow·Melo·MP4 보존 및 KST 준수. 기존 로컬 파일 검사·SHA 대조, 테스트는 기능 묶음 이후 필요 범위 한 번만.

## 결과 파일/완료
- **reports/QWEN_TTS_AB_RESULT.md**: 실제 게이트 측정값과 pass/fail, 설치/다운로드 여부·바이트수·CPU 합성 1회 여부, 정확 모델/revision/라이선스, A/B WAV 실제 경로와 해시/검사, 사용자 청취해야 할 비교 항목(발음·강약/리듬·친근함·CapCut에 가까운지), 비용0·외부 API0·기존 데이터 보존, 부족하면 다음 가장 작은 안전 조치.
- **reports/CURRENT_PROGRESS.md** 갱신, 코드 수정 시 테스트 및 검증된 코드+보고서를 GitHub main에 커밋·푸시. WAV/대용량 모델·비밀정보는 커밋하지 말 것.
- 메모리 조건 불충족이면 무리한 설치 대신 측정과 정확한 차단 사유를 보고하고, 추가 다운로드/합성을 시도하지 않은 것을 명확히 기록.
