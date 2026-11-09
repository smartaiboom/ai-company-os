# 다음 개발: AI 영상 클립 기반 무료 쇼츠 제작 엔진 (2026-11-09 KST)

## 최상위 목표와 사용자 결정
사용자는 텍스트 슬라이드보다 AI 생성 영상 클립을 활용한 유튜브 쇼츠를 원한다. 현재 예산은 **무료 우선**, 향후 유료 영상 생성 API 추가가 가능해야 한다. 사용자는 최종 산출물에 자연어 피드백을 주며, AI 관리자가 대본·장면·음성·영상 선택을 자율 판단해야 한다. 제작 과정에서 음성/클립을 매번 사용자에게 고르게 해서는 안 된다.

이번 작업은 실제로 AI Company OS 안에서 AI 생성 클립을 **수입→검증→9:16 쇼츠 편집→MeloTTS 음성/자막 합성→파일 검증**할 수 있는 오프라인 제작 경로를 만드는 것이다. 무료 AI 영상 서비스에 미승인 클라우드 호출을 하거나, 텍스트 애니메이션을 AI 생성 영상이라고 포장하지 말 것.

## 이미 확인된 실제 시스템
- 기존 renderer: companies/video/production_video.py / core/local_artifacts.py. production_video는 width*9==height*16의 **16:9 전용**, SVG + espeak_reference. 원본 코드를 무작정 치환하지 말고 독립 새 렌더 경로와 호출 경계로 확장.
- 영상 회사: companies/video/video_production_company.py. 기존 Gemini35 엔진의 작업/승인/오류 기록과 별도로 테스트 가능하게 설계. 공통 회사 엔진 core/ 코드 중복 금지.
- MeloTTS: 실제 16.783초 한국어 WAV 성공. 별도 로컬 런타임은 data/tts_korean_review/runtime-melotts-py310. 이 모델/런타임 재사용. 기존 모델 다운로드/기존 샘플/승인 기록 보존.
- 확정 목표: AI 초보자를 위한 ChatGPT 활용법 1분 **9:16 유튜브 쇼츠**, AI 회사가 대본/내레이션 제작. 기존 인수 초안은 1/1 호출 완료이며 수입/제작을 위해 권한 변경하거나 재호출하지 말 것.
- 기존 기준선: data/video_baseline_review/20261109T132912_KST/ (대본, storyboard, 16:9 preview.mp4).
- AGENTS.md 지침 필독.

## 영상 생성 도구 전략
1. 제공자 비종속의 영상 클립 contract/interface를 **companies/video/** 안에 구현: prompt, aspect_ratio=9:16, duration target, reference image(optional), result clip metadata, source/provider, license/terms/usage rights, allowed_to_publish, provenance, generated_at(KST), cost estimate/actual, status, original checksum. 예: `generate_scene` 작업 계약과 `import_generated_clip` 수입 경로.
2. 무료 계정의 **Google Flow, Pika, Kling** 등 웹 UI에서 생성한 클립을 수입하는 것이 **1차 구현 경로**. 이들 무료 웹 서비스는 개발자 API 무료권/자동화 권한이 검증된 것이 아니다. 브라우저 자동 로그인/웹 스크래핑/비공식 API/토큰 탈취/약관 우회 금지. Provider capability에 `manual_import` 명시; provider API가 없는 경우 `automatic_generation_supported=false`. 향후 유료 API는 `api_adapter`를 별도로 추가할 수 있지만 실제 API 코드 네트워크 실행은 승인까지 비활성. 무료/유료 웹 크레딧과 API 비용 별개임을 분명히 표현. 특정 provider 하나에 시스템 결합 금지.
3. 한 번의 제작 작업에 들어간 모든 클립의 출처·원본 파일·권리/사용 제한·원본 해시를 남긴다. 라이선스/비상업·워터마크 조건을 확인하지 못하면 `publish_ready=false`로 기록. 임의로 권리 문제를 가정하거나 워터마크 제거 금지.
4. 실제 외부 클립이 아직 없는 경우 AI 비디오 생성 성공이라고 거짓말하지 않는다. 코덱 검증용 자체 제작 영상/기존 기술 시안을 쓰는 경우 `synthetic_test_fixture`/비AI 클립이라고 명확히 기록.

## 이번 개발 묶음
- **클립 입출력 계약과 임포트**: 사용자/Codex가 로컬에 제공한 mp4/mov 파일을 허용된 작업 폴더에서만 안전하게 가져오기. 원본은 불변. symlink/경로 이동/오염/확장자 신뢰 금지, ffprobe로 콘텐츠 검증, 길이·규격/프레임·오디오 유무·중복 해시 검사, 클립 사용 권한/프로비넌스/상태 저장.
- **9:16 최종 편집기**: 업로드된 클립을 화면비 맞게 crop/letterbox (피사체 손상 방지 기본값), 길이 맞춰 트림/필요 시 장면 연결, 큰 한국어 자막과 안전영역 적용. 최종 720×1280 등 지원, 1분 총 길이, 장면별 9:16 확인.
- **음성**: 확인된 MeloTTS 로컬 한국어 WAV 생성 경로(기존 런타임 재사용), 기존의 로봇 espeak_reference는 기본값 사용 금지. 녹음 시간에 맞춰 장면별 대본과 타임라인을 맞추고 WAV/자막/영상을 합성. 음성이 더 길면 숨기거나 속도만 무리하게 바꾸지 말고 길이/대본 조절이나 명확한 실패 판정. MeloTTS가 오프라인 환경상 재사용 불가하면 이유 기록하고 거짓 패스 금지.
- **검증**: ffprobe + 전체 FFmpeg decode, 비디오 9:16, 오디오 트랙, 60초 근접, 자막/음성 타임라인, 원본 해시 및 근거·사용 권한 문서. 객관적 테스트와 '실제 사람이 시청/청취한 품질' 구분. 원본 파일 손상 금지.
- **AI 관리자/직원 연결 준비**: 범용 의사결정 경계를 유지. 영상 생성 provider별 기능표/비용·워터마크·상업적 사용 가능 여부를 입력으로 받아 선택하도록 인터페이스 설계. 단, 현재 없는 AI 기능을 동작했다고 주장하지 말 것. 실제 제품 AI 작업 실행은 기존 사용자 동의/비용/한도 보호 정책 준수.
- **실물 테스트**: 사용자의 1분 목표로 자동 생성되는 9:16 장면 설계·클립 프롬프트 2~4개를 생성·파일로 보존. 외부에서 생성한 실제 클립을 아직 받지 못했으면 테스트 파일로 미디어 편집 경로만 검증하고 최종 AI 클립 포함 쇼츠 완성은 `pending_external_clip`로 표시. 재생 가능한 9:16 기술 시안만 만들 수 있어도 그 산출물을 제시. *실제 AI로 생성한 영상 클립은 외부 서비스로 생성되어 수입된 경우에만 'AI 생성'으로 판정.*

## 안전·비용·속도
- **이번 작업에서 새로운 외부 AI API 호출 0회**, 유료 전환 0원, 자동 재시도·업로드 0회. 무료 웹 서비스 계정 자동화/로그인은 사용자 승인 없이 수행 금지. 계정 개설이나 사용자가 직접 클릭해야 하는 동작은 별도 수동 단계로 표시.
- 원본의 로컬 data/, backup/, artifacts/, API 키/이전 승인·사용량 원장/별도 아카이브 불변. `git reset --hard`, `git clean` 금지.
- 기존 목적과 호환되는 최소 변경, 필요할 때만 모듈 추가. 한 작업 묶음으로 구현하고 **최종 통합 테스트 한 번** 실행, 중간 반복 보고/테스트 불필요. 3~5초 샘플 몇 개와 기존 대본으로 기술 시안 먼저 만들고 외부 클립 수입은 사용자가 파일을 제공하는 단계에서 진행해도 됨.
- 테스트/산출물은 data/video_ai_clip_review/YYYYMMDDTHHMMSS_KST/ 내에 저장(gitignored), MP4를 GitHub 커밋하지 않는다. 소스 변경사항만 Git commit/push.

## Codex 최종 보고 (간결)
- 구현한 기능, 명령어/진입점, 실제 만들어진 파일 경로 및 ffprobe 검증 결과.
- AI 생성 외부 클립이 실제 사용됐는지 명확히 분리, 무료 외부 서비스의 **수동 클립 다운로드·이동 절차**.
- MeloTTS 합성/자막/9:16 성공·실패와 사유, 라이선스·워터마크·상업 이용 미확인 사항.
- 실제 Gemini/API 호출 = 0회, 유료 비용 = 0원, 이전 원장/백업 불변 확인.
- docs/IMPLEMENTATION_STATUS.md 말미에 5~8줄만 추가. 실제 사용자 피드백 학습/AI 직원 자율 완성은 별도 남은 목표로 명시.
