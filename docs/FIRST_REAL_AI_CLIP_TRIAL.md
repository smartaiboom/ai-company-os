# 첫 번째 실제 AI 영상 클립: 무료 생성 → 로컬 수입 검증

## 목적
사용자가 본 기괴한 테스트 패턴은 비AI FFmpeg fixture였음. 다음 실험은 실제 AI 영상 생성 서비스에서 **세로형 실물 클립 1개를 생성**하고, AI Company OS의 기존 클립 import 기능으로 연결하는 것. 한 번에 3개 제작하지 말고 1개 성공 확인 후 확장. 기존 MeloTTS는 당분간 유지, 사용자 선호는 나중에 최종 산출물 자연어 피드백으로 축적.

## 사용자 수동 생성 (무료 계정 한정)
서비스 1순위: https://labs.google/fx/tools/flow (Google Flow). 계정별 현재 무료 크레딧·모델·워터마크·상업 사용 가능 여부는 **실제 화면에서 확인**. 무료 크레딧 초과나 유료 결제 화면이면 중단. 사용자는 9:16, 5~8초 등 서비스가 허용하는 짧은 클립을 생성. 영상 모델 동작 비용이 0 현금인지 확인. 웹 서비스 로그인/생성/다운로드를 Codex가 무단 자동화하지 않는다.

### 1번 장면 프롬프트
```
Vertical 9:16 cinematic video, 5 seconds. A Korean-speaking adult beginner discovering an AI assistant on a laptop at a bright, tidy desk. Warm natural window lighting, realistic cinematic footage, subtle camera push-in, expressive hands typing, inviting educational mood, coherent realistic anatomy. Keep the subject clearly visible in center frame. Leave lower center area uncluttered for Korean subtitles. No logos, no readable screen text, no fabricated software interface, no captions, no watermarks added by prompt, no spoken audio. No cuts.
```
사용자가 제공하는 피드백으로 후속 프롬프트를 조정한다. 무료 서비스 자체 워터마크는 제거하지 않는다. 화면상의 실제 ChatGPT UI를 재현했다고 거짓 주장하지 않는다.

## 사용자 파일 전달
Flow에서 실제 mp4 또는 mov 클립을 다운로드한 뒤 Codespaces의 `data/video_ai_clip_inbox/`에 업로드하고 `scene-1.mp4` 등으로 이름 지정 (클립 확장자, 원본 파일 해시와 원본 유지). 파일 이름을 바꿀 수 없는 경우 업로드 이름을 기록한다. '생성 완료'만 말하고 파일이 없으면 실제 합성 성공으로 주장하지 않는다.

## Codex 다음 실행 (파일 수신 후)
1. AGENTS.md, companies/video/ai_clip_pipeline.py, docs/IMPLEMENTATION_STATUS.md를 확인. 현재 60초 기술 시안 경로 `data/video_ai_clip_review/20261109T145000_KST/`와 실사용 데이터는 변경 금지.
2. 새 `data/video_ai_clip_review/YYYYMMDDTHHMMSS_KST/` job을 만들어 기존 baseline_plan 사용. 본 작업의 실제 외부 생성 클립을 `scene-1`에 수입하고, 나머지 장면은 비AI 패턴을 쓰더라도 결과물에 **혼합 기술 시안**이라고 표시. 다만 전체가 AI 생성이라고 주장 금지.
3. `ai_clip_pipeline import <job> <inbox> <filename> scene-1 <source.json>`은 `source.json`의 정확한 필드(provider, provenance, generated_at(+09:00), license, terms_url, usage_rights, commercial_use, allowed_to_publish, watermark, rights_verified, rights_evidence, estimated_cost, actual_cost)를 요구. 사용자 화면에서 확인할 수 없는 권리는 unknown/false로 기록, 출처를 추정해 verified라고 표시 금지. API 호출 0. 상업 이용 검증 전 publish_ready=false.
4. 전체 쇼츠 렌더를 하려면 3개 scene의 클립 모두 필요하며 다른 두 scene은 비AI fixture 사용 가능. 기존 코드의 중복 해시 제약과 새 job/한 번 렌더 제한을 준수. 실제 파일이 수신되기 전엔 클립을 수입했다고 주장하지 말 것.
5. 720×1280, 60초, MeloTTS, 자막, 전체 FFmpeg decode, 실제 소스 혼합 여부, watermark/상업권리 검증 여부 보고. AI 클립 수가 1개여도 `ai_generated_clip_used`와 `publish_ready` 코드를 사실과 다르게 개선/보고하지 말 것. 새 job에만 기록.
6. 기존 API 키/계정/호출 원장, 이전 결과 보존. 코드는 이미 import 기반으로 개발됐으므로 **클립이 오기 전에는 새 개발을 반복하지 말고**, 입력 파일만 기다린다.

## 최종 목표
AI Company OS AI 관리자가 도구를 자율 선택하는 구조는 장기 목표. 이번에는 무료 웹 비자동화 제약으로 영상 생성은 사용자 수동 1회, 편집은 AI Company OS에서 자동화하여 검증.
