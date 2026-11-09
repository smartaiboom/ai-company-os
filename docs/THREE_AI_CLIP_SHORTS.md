# 두 번째·세 번째 실제 AI 영상 장면 준비 (2026-11-09 KST)

## 목적
현재 60초 혼합 쇼츠는 Google Flow 출처의 실제 AI 클립 scene-1 1개 + 비AI FFmpeg fixture scene-2/scene-3 2개. 미리보기 합성 및 GitHub 코드 동기화까지 완료. 이제 **두 fixture만 실제 AI 생성 클립으로 교체**해 첫 전 장면 AI 영상 시안을 제작한다. MeloTTS를 유지하며 음성 품질은 최종 산출물 피드백 후 개선한다.

## 현황/안전
- AGENTS.md, reports/real_ai_clip_import_result.md, reports/real_ai_clip_sync_result.md, companies/video/ai_clip_pipeline.py 선확인.
- 구 혼합 시안: data/video_ai_clip_review/20261109T155436_KST/shorts/preview.mp4. 원본과 입력 클립, 원장, 백업 수정 금지.
- 무료 Google Flow의 UI를 사용자가 직접 이용한다. 실제 계정 무료 크레딧 안에서만, 결제/업그레이드 화면이면 중단. 사이트 UI와 사용권/워터마크/상업 이용 조건을 화면에서 확인해야 하며 이 문서로 보장하지 않는다.
- **Codex가 직접 Google Flow 로그인/브라우저 자동화/유료 API 호출 금지.** 다운로드한 파일을 별도 로컬 inbox에 저장한 뒤에만 시스템 수입 가능.
- 한 번에 두 클립을 만들기 부담스럽거나 무료 한도가 부족하면 가능한 범위만 진행. 추가 서비스 강제 가입 불필요.

## 장면 2: AI에 목적을 말하는 상황
Prompt (9:16 portrait, available 5–8s clip):
```
Vertical 9:16 realistic cinematic video, 5 seconds, educational short film. Over-the-shoulder view of an adult at a tidy bright desk, thoughtfully planning an everyday task with a blank notebook and laptop, then typing an instruction. Natural warm daylight, gentle camera movement, visually coherent hands and laptop, calm approachable atmosphere for a beginner learning AI. Reserve the lower-center safe area for subtitles. No readable text on screen, no fabricated ChatGPT UI, no logos, no captions, no spoken audio. Single continuous shot.
```
Output file: data/video_ai_clip_inbox/scene-2.mp4 (or keep original download name and record mapping).

## 장면 3: 결과를 확인하고 활용하는 상황
Prompt (9:16 portrait, available 5–8s clip):
```
Vertical 9:16 realistic cinematic video, 5 seconds. A beginner at a bright home work desk looks satisfied while comparing notes in a paper notebook with a laptop screen, then confidently starts typing the next idea. Natural daylight, subtle smooth push-in, thoughtful and optimistic educational mood, realistic hands, stable geometry, consistent subject throughout. Leave subtitle-safe space near the lower center. No readable screen text, no fake AI interface, no brand logos, no subtitles, no spoken audio. Single continuous shot.
```
Output file: data/video_ai_clip_inbox/scene-3.mp4 (or keep original download name and record mapping).

## Codex 작업 (두 입력 파일이 실제로 존재할 때만)
1. 상세 검증과 실행은 파일로 기록한다. 신규 작업지시를 채팅에 길게 재출력하지 않는다.
2. `data/video_ai_clip_inbox/`에 두 실제 다운로드 파일이 있는지 확인. 입력이 없으면 추정 영상 생성 금지. 있으면 새 KST job으로 기존 원본 scene-1 + scene-2 + scene-3의 AI 클립 3개를 수입. 기존 job은 1회 렌더 제한을 가지므로 **새 job 필수**, 기존 원본을 변경하지 않는다.
3. 새 9:16/60초 MP4를 MeloTTS 한국어 음성·한글 자막과 합성. FFmpeg/ffprobe 전 디코딩, 출처·클립 수·권리 상태·워터마크·오디오·타임라인·해상도를 기록. 무료 서비스 상업권리 미확인 시 publish_ready=false.
4. 짧은 클립 3개를 각각 20초 장면으로 늘릴 경우 반복 루프가 생긴다는 사실을 `evaluation.md`에 명시. 반복만으로 영상 품질 합격이라고 평가하지 말고 추가 샷 수/편집 전략을 후보로 남긴다.
5. 실제 외부 AI 호출 0회(이번 Codex 작업 기준), 유료 비용 0원, 기존 사용자 Gemini 문답 호출 1/1 유지. 기존 음성·영상/원장/백업 보존. 사용자가 최종 편집 파일을 본 후 자연어 피드백을 축적하는 기능은 다음 개발 단계이며 지금 임의 구현하지 않는다.
6. 결과는 `reports/three_ai_clips_shorts_result.md`에 저장. 생성파일 경로, 3개 소스, 검증 결과, 한계, 새 호출/비용/보존, 다음 권고를 짧게 쓰고 GitHub에 보고서만 반영. 코드를 수정한 경우에만 최소 범위 테스트 후 코드도 푸시. 사용자에게는 완료 사실만 짧게 전달.
