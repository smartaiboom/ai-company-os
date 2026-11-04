# AI Company OS — 실제 Gemini 3.5 첫 한 사이클 차단 원인: espeak_audio exit=1 정밀 재현·최소 수정

기준: 2026-11-04 KST. **Codex 오프라인 로컬 도구 수리 지시**. 실 Gemini API 호출/기존 stopped 실행 재사용/새 실사용 프로젝트 동의·실행 0회.

## 최우선 원칙
`AI_COMPANY_OS_CORE_PRINCIPLES.md`, `AGENTS.md`, 한국어 규칙과 기존 개발 보고서를 먼저 읽는다. 사용자는 목표만 제공하고 **AI 관리자가 계획·업무 판단·품질 기준·수정 지시**, 시스템은 실제 실행 도구를 제공한다. 이번 문제는 AI 관리자가 이미 정상적으로 두 번 검토했으나 **로컬 TTS 프로세스가 exit 1**로 실패해 최종 MP4가 안 나온 것. 관리자 업무 판단을 고정하거나 자막 단축·음성 제거로 우회해서 성공을 위장하지 말 것. 최소 기술적 수리만.

## 실사용 근거
실행 프로젝트 `data/gemini35-nested-tool-review-20261104` / `gemini35company-1dc335e5b1324ce690a0e9f19945691d`.
- 상태 stopped, reason manager_stopped, phase work, artifacts={} / API 시도 5회.
- task_1 `Draft Video Script and Tool Input JSON`, versions 2, 둘 다 `tool_status=failed`, `tool_failure={stage:espeak_audio,category:exit_nonzero,exit_code:1}`.
- 첫 manager review revise, 한국어 TTS/format 개선 지시, 직원 재수정 후 동일 exit=1, 두 번째 manager review stop. task_2/3 pending, 최종 MP4 없음.
- 앞선 오프라인 합성 문구로 espeak/ffmpeg/TTS 단일·다중 성공했으므로 espeak 바이너리가 무조건 없는 것이라고 추측 금지.
- 직원 결과 **versions에 보존된 원본 content**를 로더로 읽을 수 있음. 기존 프로젝트 전체 해시/원장/소진 표식은 불변. 예전 실패들의 content는 보존되지 않았지만 이번 실패 버전은 남음.

## 이번 단계 필수 작업
1. 실제 로컬 store의 두 직원 version을 `Gemini35Store.load`로 **읽기 전용** 확인하고, 각각 `content`의 내부 tool JSON 파싱·스키마·장면별 text 타입/문자 종류/특수기호/문장 길이/scene seconds/audio 플래그 등 **민감정보 없는 안전한 특징 요약만** 남긴다. 대화/보고서/Git에 raw text·키·프로젝트 내부 payload 전문을 올리지 말 것. 이 프로젝트는 비밀 없는 합성 목표지만 최소 노출 준수. 완전한 parse 가능한 input이면 그 JSON을 도구에 재전달하는 것은 **로컬 실험에서만**.
2. **기존 프로젝트 execute/run/continue/approve 절대 금지**. 기존 아티팩트 폴더에도 변경 금지. 새로운 `tempfile.TemporaryDirectory` 아래에서만 실패한 각 직원 입력의 TTS 단계(`espeak-ng -v ko -s 155 -f <textfile> -w <wavfile>`)를 원래 렌더 경로와 같은 옵션/UTF-8 파일로 재현. 텍스트를 파일에 써서 실제 espeak 종료 코드와 stdout/stderr(로컬 분석용만)를 조사하되 stderr/경로/직원 원문/비밀을 Git/로그/보고서로 저장하지 않음. stderr는 오직 기술적 원인 판별에 사용한 뒤 **무해한 enum 원인**만 보고. scene별 재현 여부, 두 version 결과를 분리 기록. `render_video`의 `prepare_video` 후 실제 전달되는 캡션이 원문과 어떻게 달라지는지 반영.
3. 동일 환경에서 **짧은 합성 한국어**와 **직원 실제 캡션**의 비교. 문장 인코딩/BOM, 개행, espeak ko voice, 입력 Unicode, espeak 자체의 exit1 원인을 입증. 호출된 binary 존재 여부·옵션 오류·파일 경로/권한·파일 내용/길이·언어 voice·WAV 생성 여부 등을 코드와 재현 결과로 구분. 정확한 원인이 확인되지 않으면 **미확정**으로 정직하게 보고하고, 재현 가능한 최소 관측 방법만 제공.
4. 원인이 코드/도구 환경의 **순수 기술 문제**라면 최소 변경으로 수정: espeak 입력 UTF-8/제어문자/언어 모드/옵션·오디오 생성, 경로·권한·필터 등 재현된 문제만. AI 관리자의 자막·내용·수정 판단, 사용자의 한국어 음성 요청을 우회하거나 audio:false 강제 금지. 에러 발생 시 안전 stage/category/exit_code 진단 그대로 유지, stderr·환경값을 영속화하지 않는다. 실행 실패를 MP4 성공으로 기록 금지.
5. 로컬에서 실제 실패 두 버전과 정상 합성 문구를 사용하여 수리 전후 재현 결과 확인. 가능한 경우 임시 격리 렌더 출력 `ffprobe`/전체 디코딩까지 검증. 텍스트/음성의 의미 및 미학을 개발자 고정 품질 판단으로 넣지 않는다.
6. 외부 AI API 요청 0회, 기존 모든 프로젝트/동의/원장/백업·artifact 0 수정, 외부 네트워크 없는 검사. 신규 UI/별도 자동복구/모델 변경/새 공급자/새 비디오 스타일/전면 재개발 금지. 원장 SHA256 보존, 필요한 테스트만, `git diff --check`. 소스·테스트·보고서만 선택적으로 commit/push.
7. **보고서** `reports/v01_gemini35_espeak_audio_exit1_root_cause_20261104.md`: 두 versions 실 입력 재현됐는지, 확정된 물리적 원인, 수리 근거와 로컬 테스트, 기존 기록 보존, 실제 Gemini API 0회 및 남은 한계. 가능하면 새 독립 3.5 프로젝트를 prepare만 하되 과거 동의·해시 재사용 금지. 구체적 무료 계정/동의 범위/만료/실행 명령은 별도 후속 사용자 동의가 있을 때만 사용. 준비 실패/원인 미확정은 숨기지 말 것.

## 완료 기준
**실제로 반복 실패한 espeak_audio exit1을 직원의 저장된 입력으로 로컬 재현한 뒤 기술 원인을 해결하거나, 최소한 재현 부재를 명확히 입증**. 새로운 범용 기능 개발보다 **첫 실사용 한 사이클을 막는 로컬 도구 문제**만 고친다.
