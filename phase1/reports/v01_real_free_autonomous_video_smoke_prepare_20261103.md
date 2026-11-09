# 실제 무료 자율 영상 smoke 준비 — 설치·MP4 경로·운영 동의 제안

작성: 2026-11-04T09:42:00+09:00 (KST). `git pull --ff-only` 성공, main cbe0d03에서 시작. 핵심 원칙·AGENTS.md·지정 지시서·기존 무료 자율 보고서·autonomous_free.py·autonomous_live_cli.py 및 공통 상태 기계/실제 공급자 경로를 확인했다.

안내문 목표는 폐기하고 **ChatGPT 초보자를 위한 좋은 질문 방법, 한국어 20~30초, 이해하기 쉬운 화면/자막, 가능하면 음성, 재생 가능한 MP4와 제작 보고서**로 준비했다. 이번 결과는 개발용 fake HTTPS/모의 콘텐츠의 실행 도구 검증이며 실제 AI 제작 성공이 아니다. 실제 OpenRouter/타사 AI API 호출 **0회**, 실제 프로젝트 운영 승인 **0건**, 유료 서비스 사용 **0건**. 무료 패키지 설치와 Git 통신은 수행했다.

## 설치와 권한 오류

1. 실제 실행 `sudo -n apt-get update`는 샌드박스에서 exit 1. 정확한 오류:
   - `sudo: /etc/sudo.conf is owned by uid 65534, should be 0`
   - `sudo: The "no new privileges" flag is set, which prevents sudo from running as root.`
   - 컨테이너 설정 조정이 필요할 수 있다는 sudo 안내가 뒤따랐다.
2. 동일 명령을 권한 확장으로 실행해 exit 0. `sudo -n apt-get install -y ffmpeg fonts-noto-cjk espeak-ng`도 권한 확장 실행으로 exit 0. 임의 설치 스크립트나 유료 서비스는 사용하지 않았다.
3. Ubuntu 24.04 공식 archive/security 저장소의 패키지: FFmpeg/ffprobe `7:6.1.1-3ubuntu5`, Noto CJK `1:20230817+repack1-3`, eSpeak NG `1.51+dfsg-12build1`. apt 목록 갱신에는 기존 설정된 Microsoft 저장소도 조회되었지만 요청한 영상 도구는 Ubuntu 패키지다.
4. 설치된 `/usr/share/doc/{ffmpeg,fonts-noto-cjk,espeak-ng}/copyright` 확인: FFmpeg 패키지 GPL 계열(기본 바이너리 GPL-2+, 문서 등 GPL-3+ 및 LGPL 구성 포함), Noto 글꼴 SIL OFL 1.1(패키징 GPL-3+ 포함), eSpeak NG GPL-3 계열. 설치 환경의 저작권 파일을 근거로 기록했다.
5. `espeak-ng --voices=ko`에서 Korean 확인. 이 조회는 Pulse 설정 디렉터리의 읽기 전용 오류도 출력했으나, `espeak-ng -v ko ... -w WAV` 파일 합성은 성공했다. 오디오 장치 재생은 사용하지 않는다.

## 변경과 실제 AI 연결

- `local_artifacts.py`: 작은 allowlist 도구 인터페이스 `execute(tool, spec, folder)` 및 `caption_video_v1`. 장면 JSON만 허용하고 AI 생성 셸/코드/입출력 경로/필터를 실행하지 않는다. 배경은 로컬 색상, 자막은 설치된 한국어 글꼴로 생성한다. 선택적 한국어 음성은 로컬 eSpeak NG, 출력은 H.264/yuv420p + 선택적 AAC다.
- `autonomous_free.py`: 새 프로젝트 생성 시에만 선택적 `local_tools`를 저장하고 운영 계약에 도구 정의를 결합한다. 기존 프로젝트·기존 계약에 도구 권한을 소급 적용하지 않는다. 로컬 도구 허가는 외부 전송 scope와 별도 필드다. 기존 `rules.tools_available=false`는 모델의 직접적인 도구/파일 접근 불가를 유지하며, 별도 allowlist 실행기만 앱에서 호출한다.
- `autonomous_live.py`: 기본값이 빈 `_tool_notice` 훅 하나로 free-v2에서 허가된 실행 능력을 설명한다. legacy 경로의 동작과 응답 계약은 유지했다.
- `autonomous_live_cli.py`: 새 free-v2 `create --local-video` 옵션. 기존 legacy 프로젝트에서는 거부한다.
- `tests/test_local_artifacts.py`: fake HTTPS→관리자 계획→직원 초안→관리자 수정→직원 수정→검토→선행 결과를 받은 영상 담당→실제 FFmpeg 렌더/ffprobe/디코딩→관리자 검토→최종 통합을 검증한다. 중간 업무 승인 0, run 1, fake 요청 8회다. 음성 없는 렌더도 검증한다.
- 기존 `tests/test_manager_plan_persistence.py`, `tests/test_task_execution_persistence.py`, `tests/test_uncertain_reservations.py`, `tests/test_m4_runner_shutdown.py`: 무료 adapter의 인증키 필수 조건과 맞지 않던 모의 입력에 **가짜 테스트 키**만 추가했다. 실제 키·프로덕션 보호 코드는 바꾸지 않았다.

직원 `execute.content`는 문자열 계약을 유지하면서 JSON 문자열 `{"tool":"caption_video_v1","width":1280,"height":720,"audio":true,"scenes":[{"text":"직원이 생성한 자막","seconds":6}]}`을 제출할 수 있다. 작업 수·역할·품질 기준·영상 내용·최종 판정은 모델이 정하며, 위 숫자는 입력 예시이지 엔진 고정 규칙이 아니다. 크기·문자 수·장면 수·총 렌더 길이 상한은 도구 자원/입력 보호 한도다.

실행기는 직원 응답을 검증하고 최초 운영 권한을 재확인한 다음 KST 예약 이벤트와 입력 hash를 저장한다. 작업별 내부 경로에 MP4를 생성하고 SHA256/길이/코덱/크기/프레임 수/디코딩 여부를 원장 이벤트와 artifact에 기록한다. stdout/stderr·환경·키는 프로젝트에 기록하지 않는다. 완료 receipt가 직원 evidence에 붙어 관리자 검토·후속 직원·최종 통합 입력으로 전달된다. 모델 전송은 목표와 해당 새 프로젝트 생성 자료/로컬 도구 측정 메타데이터에 한정되며 MP4/WAV/기존 파일은 업로드하지 않는다.

렌더 실패, 글꼴 없음, 입력 초과, 음성이 장면보다 긴 경우, MP4 검사 실패는 안전 정지한다. 미완료/미확정 실행을 자동 재전송하지 않는다. MP4 없는 모델의 완료 주장도 차단하며, 최신 직원 결과와 대응하는 완료 도구 이벤트가 AI 관리자에게 수락되어야 전달한다. 기존 artifact SHA256 조회 검사도 유지한다. 프로세스 timeout/예약은 보존되며 자동 복구를 주장하지 않는다.

## 로컬 증거 — mock 소재이며 실제 AI 아님

- 증거 저장소: `/workspaces/ai-company-os/ai-company-os-phase1/data/video-offline-evidence-20261104`
- mock 프로젝트: `freecompany-28bd85018368469d9a5259d64602b57d`
- 실제 MP4: `/workspaces/ai-company-os/ai-company-os-phase1/data/video-offline-evidence-20261104/artifacts/freecompany-28bd85018368469d9a5259d64602b57d/tool-6adbf21f001ecdb5f004735760e88f425d8ef900ddb4e9603c9d828c9abbd95f/video.mp4`
- ffprobe/전체 디코딩: **성공**, 1280×720, 약 24.02322초, 24fps/576프레임, H.264, 한국어 자막과 AAC 한국어 합성 음성 포함.
- MP4 SHA256: `8db61afd9bade347c1a6e37946dca05663be8f44b94d0c82d5409604c16e4574`
- 같은 프로젝트의 `final.json`, `final.md`, 상태 JSON에 선행 전달·수정·검토·KST·도구 실행 기록 보존. Git에는 넣지 않는다.
- 8초 프레임을 추출하여 한글 자막이 실제 표시됨을 눈으로 확인했다. 오디오 합성·스트림·디코딩을 검사했으며 음성의 자연스러움이나 전 구간 시청 품질을 독립 검증했다고 주장하지 않는다.

## 신규 실제 실행 대기 프로젝트와 운영 동의안

중복 생성 없이 새 저장소 프로젝트 **1건**을 create/prepare까지만 만들었다.

- 저장소: `/workspaces/ai-company-os/ai-company-os-phase1/data/free-video-smoke-20261104`
- 프로젝트: `freecompany-ae4aa334511d470c8c517685e9902a53`
- 최초 상태 hash: `acf84d8651d7c0ef0093d18644cce97aa5890608671009c63dd65e4aa8a70c7c`
- 목표 hash: `e45e9e0da6ce050ed0492583b129cb5313b63fa7f52693260770523fdbe098f6`
- 제안 파일: `/workspaces/ai-company-os/ai-company-os-phase1/data/free-video-smoke-20261104/operating-proposal.json`
- 제안 검토 hash(canonical JSON): `c36981e3e8e6d565e3a7566185869a5bf49fcddafdb36a73764d23ad6c0316c2`
- 동의안 만료: `2026-11-11T09:30:14+09:00` (KST, 7일). 만료 후에는 승인 전에 prepare로 최신 제안을 다시 검토해야 한다.
- 상태 ready/plan, 호출 원장 0, enabled=false, 승인 grant·서명 키 없음. 실제 운영 approve/owner-confirmed/live run을 실행하지 않았다. 테스트의 합성 동의와 별개다.

사용자가 다음에 검토할 **단 한 번의 최초 운영 범위**는 이 목표/ID/hash, OpenRouter `openrouter/free`, 비용 0/유료 fallback 없음, 목표와 새 프로젝트 생성 계획·기준·업무·대본·자막·장면·직원 결과·검토·수정·통합·도구 receipt 메타데이터 전송, MP4/기존 파일/코드/계정 정보 미전송, 로컬 자막 MP4·한국어 TTS 도구 허가, 유효기간이다. 2회/20회 인위적 비용성 상한은 없고 기존 공급자 제한·30분 실행·수정/중복/불확실 예약 보호는 유지된다. 이 보고서는 동의 요청 준비이며 승인이 아니다.

그 승인을 별도로 받은 후에만 지정 계약으로 승인하고 보호된 환경에서 run 한 번으로 실제 관리자/직원의 계획·수정·협업·MP4 전달을 검증한다. 공급자의 비용 0 응답/JSON 준수/가용성, 실제 모델의 도구 JSON 작성과 품질 판단은 아직 검증하지 않았다. 잘못된 응답/도구 실행 실패는 정지하며 자동 재시도하지 않는다. 영상 파일 자체를 모델이 보거나 듣지는 못하므로 기술 검사와 모델의 콘텐츠 검토를 구별한다.

## 테스트와 보존

- `python -B -m unittest tests.test_autonomous_free tests.test_autonomous_live`: 45개 통과.
- `python -B -m unittest tests.test_local_artifacts`: 최초 6개 중 1개 실패(음성 AAC 컨테이너 길이 24.02322초를 24초와 정확 비교). 길이 허용 오차 0.2초로 수정 후 6개 통과. 실제 도구 검사에도 같은 허용 오차를 적용한다.
- `python -B -m unittest tests.test_local_artifacts tests.test_autonomous_free tests.test_autonomous_live`: 51개 통과.
- 최초 `python -B -m unittest discover -s tests`: 593개, 실패 5/오류 36/skip 1. 로컬 소켓 sandbox PermissionError와 당시 길이 비교 및 기존 가짜 인증키 누락이 포함된다.
- 권한 확장 전체 회귀 재실행: 593개, 실패 8/오류 6/skip 1. 소켓 제한은 해결됐고 기존 4개 테스트 파일의 인증키 누락을 확인했다.
- 가짜 인증키 보완 후 `python -B -m unittest tests.test_manager_plan_persistence tests.test_task_execution_persistence tests.test_uncertain_reservations`: 26개 통과.
- 최종 전체 회귀 `python -B -m unittest discover -s tests` (권한 확장, 로그 `/tmp/video-full-verified.log`): **593개 실행, 592개 통과·1개 건너뜀, 실패/오류 0, exit 0** (73.847초).
- `git diff --check`: 최종 재확인 통과.

기존 업무/백업 파일 29개의 SHA256 보존 기준을 새 프로젝트 생성 전에 확보했고 이후 변경 0건을 확인했다. 기존 `cb44b605b498`, `c85d9853906a` 및 원장·대기 상태를 변경하는 코드는 실행하지 않았다. 실사용 동의/키/한도/백업도 수정하지 않았다. 사용자 기존 미추적 파일은 유지하며 이번 작업 파일만 커밋 대상으로 삼는다.

이번 변경은 **목표→자율 협업→실물 MP4** 사이의 로컬 실행 도구 공백을 메웠다. 새 경로의 불필요한 업무별 승인/재개 요구는 0회다. 기존 수동 프로젝트에는 업무별 승인 부채가 남아 있고 소급 변경하지 않았다. 전체 제품 1단계의 실제 AI 한 사이클 완주는 아직 미검증이며, 최초 외부 전송 동의 후 실증이 남아 있다. 현황판/UI 고도화는 하지 않았다.
