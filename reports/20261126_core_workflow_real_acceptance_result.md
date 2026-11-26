# 핵심 영상 업무 흐름 검증 결과

2026-11-26 KST · `origin/main`의 `75fa803`으로 fast-forward했다. 시작 시 로컬 추적 파일은 깨끗했다. 운영 프로젝트·원장과 기존 백업을 보존하고 검증 자료는 격리 폴더에 저장했다.

## 코드 반영

- 일반 보완 조사에서 관리자가 보류를 결정해도 컷룸이 다음 공식 조사 단계로 이동해 기존 미달성 결과 대신 새 승인 대기를 표시하던 문제가 있었다. 공식 조사·후속 조사로 넘어가려면 직전 서명에 해당 체크포인트가 있어야 하며 철회된 서명으로는 단계가 바뀌지 않도록 수정했다. 일반 보류 결과와 기존 관측 이력을 확인할 수 있다.
- `tests.test_research_replanning` 7개가 통과했다. 기존 실패였던 빈 검색 결과의 보류와 무진전 재검토에서 모두 `incomplete`가 남는다. 새 공급자나 승인 화면을 추가하지 않았다.

## 브라우저 및 오프라인 통합

- Playwright 1.65.2, Chromium Headless Shell 159, NSS·NSPR을 `/tmp/core-acceptance-browser`에 설치했다. 프로젝트 가상환경과 시스템 패키지에는 설치하지 않았다. 기존 `tests.test_cutroom_quality_browser`의 대표 수정 및 새 업무 준비가 Chromium에서 통과했다.
- 자체 가상 안내 영상으로 조사 보고서 인계, 관리자 기획, 직원 대본과 장면표, 버전·해시 기반 대표 수정, 수정 시안 및 다음 프로젝트 역할 입력을 검증했다. 공급자 응답과 대표 결정은 격리 fixture였다. 기술 시안의 최종 승인 차단과 경험 범위 변경 후 기존 서명으로 전송 차단을 오프라인 통합에서 확인했다.
- 별도의 Chromium 클릭 검증에서 실제 컷룸 화면으로 영상 전후 비교를 열고, 11자→5자로 바뀐 자막 기준을 기록했다. 새 프로젝트를 만들어 같은 대상의 선택과 다른 대상의 제외를 확인했다. 기존 제출 기획의 관리자·직원 입력 해시를 펼쳐 확인하고, 기록 철회 뒤 같은 대상에서도 해당 해시가 제외됨을 확인했다. 브라우저 요청은 localhost로 제한했다. 화면 캡처와 격리 작업 폴더는 `/tmp/cutroom-core-browser-f6h8ny9s`에 있다.

최종 전체 회귀 316개 중 313개가 통과했다. 실패는 0건이다. 별도 로컬 자료를 요구하는 선택 실행 3개(Melo 기반 영상 2개 및 실자료 시각 연구 1개)는 건너뛰었다. 최종 명령은 다음과 같다.

```bash
audio_root=/tmp/ai-company-audio-deps-P1tx8m/root
browser_root=/tmp/core-acceptance-browser
PATH="$audio_root/usr/bin:$PATH" \
LD_LIBRARY_PATH="$browser_root/deps/root/usr/lib/x86_64-linux-gnu:$audio_root/usr/lib/x86_64-linux-gnu" \
ESPEAK_DATA_PATH="$audio_root/usr/lib/x86_64-linux-gnu" \
FONTCONFIG_FILE=/tmp/cutroom-core-voice-xtHkbM/fonts.conf \
PYTHONPATH="$browser_root/python:core:companies/video" \
PLAYWRIGHT_BROWSERS_PATH="$browser_root/browsers" \
.venv/bin/python -B -m unittest discover -s tests -v
```

## 로컬 영상과 음성

- 기존 eSpeak NG 한국어 경로와 FFmpeg로 가상 점수 안내 영상 3개 버전을 렌더했다. 모두 H.264/AAC, 컨테이너 길이 60.023초, 전체 디코딩과 파일 해시 일치를 확인했다. 장면별 발화는 2.490~3.217초였고 모든 장면에서 배정 길이 이내였다. AAC 장면별 최대 레벨은 -2.1~-0.4 dBFS였다. 대본과 SVG 자막 원문 및 장면별 시작·종료가 일치했다. 자막은 장면 단위다.
- 영상은 `/tmp/cutroom-core-voice-xtHkbM/workspace/artifacts/company-72135e15a33b4dfbae2069712ff64eea/render-{1,2,3}/video.mp4`에 있다. eSpeak는 기술 비교용 한국어 음성이다. Melo 로컬 모델과 런타임은 준비되지 않았다.

- 기존 Windows Heami 경로로 직전 승인 대본의 720×1280 세로 기술 시안을 격리 렌더했다. H.264/AAC 전체 디코딩, 대본 입력·파일·WAV 해시와 장면별 비무음 신호를 검증했다. 발화는 2.440~3.030초였고 24fps 프레임에 맞춘 자막 노출은 2.458~3.042초였다. 장면별 최고 레벨은 -6.0~-3.3 dBFS이며 영상 컨테이너는 60.023초다. 작업 폴더는 `/tmp/cutroom-core-heami-p8hswi0z`다. 자체 카드와 로컬 검토용 한글 글꼴로 제작했다.
- 두 영상 모두 읽기 전용 컷룸의 Chromium에서 재생 시간이 증가했고 미디어 오류가 없었다. 같은 WSL 환경에서 검토할 수 있다. [Heami 세로 수정 시안](http://127.0.0.1:35035/#project/reference-0/company-3524c999bf394836b27f184e8abf0055) · [eSpeak 영상과 재작업 이력](http://127.0.0.1:35035/#project/reference-1/company-72135e15a33b4dfbae2069712ff64eea)

## 실제 공급자와 대표 평가

- `PYTHONPATH=core:companies/video .venv/bin/python -m studio_server --env-file .env --research-readiness` 결과 로컬 설정이 준비돼 있었다. 공급자 계정 상태, 청구와 쿼터는 미확인이다. 기본 작업 폴더에서 서명이 검증된 기존 조사 승인 27개는 모두 만료됐고, 조사에서 기획 인계까지 이어진 신규 업무의 승인도 확인되지 않았다.
- **실제 AI 공급자 호출 0건.** 기존 Gemini 503, Groq 403 및 이전 자동 권한 심사 거절 이후 정상 허용 경로가 확인되지 않았다. 정상 연결이 확인되면 기존 Gemini 3.5 Flash-Lite와 기존 제작 프로젝트의 무료 전용·비용 $0 범위에서, 새 모바일 게임 쇼츠 조사의 목적, 공개 자료·대표 검토·적합한 경험 데이터의 종류, 목적지, 유효기간 및 현재 승인 한도를 명시해 기존 승인 화면에서 서명한다. 신규 조사에 필요한 YouTube Data API·Tavily는 기존 무료 프로젝트와 승인된 검색·공개 메타데이터 범위가 서명에 포함된 경우에 사용한다. 새 업무의 조사 승인·실행 후 기획 인계에서 경험 포함 범위를 확인하고 관리자·직원 업무를 시작한다.
- 게임 화면이나 사용권은 확인되지 않았다. 실제 시청·청취 품질, 사실성·흥미와 최종 대표 평가는 미완료다. 실제 시연 자료 확보 및 사용권이 확인되면 실제 AI 결과와 함께 독립 검토할 항목이다.
