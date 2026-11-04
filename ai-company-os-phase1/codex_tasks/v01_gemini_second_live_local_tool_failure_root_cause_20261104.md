# AI Company OS — 두 번째 실제 Gemini 실행의 local_tool_failed 분석과 도구 복구

기준 2026-11-04 KST.

## 사용자 목표 (최우선)
사용자는 목표만 입력한다. **실제 AI 관리자**가 계획·담당·품질 기준·수정 판단을 내리고 **실제 AI 직원**이 실행하며 결과를 인계하고 최종 산출물을 만든다. 외부 개발자/Codex/고정 로직이 영상의 자막, 미적 품질, 직원 판단을 대신하지 않는다. 시스템은 물리적·보안적·실제 도구 실행 제약과 결과를 정확히 전달하고, AI 관리자·직원이 복구를 판단하게 해야 한다. 최상위 원칙 파일을 세부 버그 수정보다 우선한다. 개발을 무의미한 단발 진단/테스트로 반복하는 대신 실제 완주에 가까워질 구체적 문제를 해결한다.

## 실패 상황 (실제 사용자 실행)
`python -B gemini_first_project.py --store data/gemini-caption-recovery-20261104 execute --review-hash f8f3a1f74b79d57f4f7f1297200d289ab670d9fd9efc352f0721b86615f5c000 --owner-confirmed --confirm-free-tier`
결과:
```json
{"id":"geminicompany-df65908337b04143b576e5cbfc076abb","status":"stopped","reason_code":"local_tool_failed","phase":"work","artifacts":{}}
```
기존 실패 저장소/원장/시작 소진 파일은 수정·초기화·재실행하지 않는다. **이번 지시서에서 외부 Gemini/Groq/OpenRouter API 요청 0회.** 별도 새 실사용 프로젝트를 멋대로 실행하지 말 것.

## 작업 전 코드와 파일 읽기
`AI_COMPANY_OS_CORE_PRINCIPLES.md`, `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`, 직전 `reports/v01_gemini_caption_overflow_first_live_recovery_20261104.md`, `local_artifacts.py`, `autonomous_free.py`, `autonomous_live.py`, `autonomous_gemini.py`, `gemini_first_project.py`, 관련 test. 특히 `local_artifacts.run_command`가 모든 subprocess OSError/CalledProcessError/TimeoutExpired를 `local_tool_failed` 하나로 축약하며 stderr를 아예 버리는 현재 문제를 확인할 것. **이것만으로 어떤 프로그램이 실패했는지 아직 모른다.**

## 1. 첫 실사용과 두 번째 실사용 분리 조사 (읽기 전용)
- 새 실패 프로젝트 저장소 `data/gemini-caption-recovery-20261104`에 대해 프로젝트/시도 원장/이벤트·계획·직원 업무·도구 reservation·로컬 산출물 목록을 저장소 로더로 확인. 저장 SHA/state 검증 및 건수, phase, 성공/실패·비밀 없는 출력만 보고.
- 실제 Gemini manager·employee 성공 수, HTTP 상태, 결과 검토·인계 진행, 실패 시점에서 대기/소진된 operation 및 active_operation을 정확하게. `completed` API 호출과 `validated` 직원 산출물/MP4 생성은 분리. raw 응답 본문이 없으면 조작해 복원하지 않는다.
- 어느 도구 단계를 통과/실패했다고 저장 기록만으로 추론할 수 있는지 확인. 정확한 stage가 저장되지 않았으면 **미확정**이라 표기. 기존 일회성 실행 명령을 절대 다시 실행하지 않는다.
- 기존 첫 실패 프로젝트 `data/gemini-first-autonomous-20261104`와 2.5 synthetic/기타 공급자 원장도 보존.

## 2. 로컬 도구 문제를 재현 가능한 증거로 해결
- 모델 호출 없이 **새 임시 디렉터리**, 사용자 프로젝트와 무관한 안전한 합성 자막/장면을 사용해 renderer의 로컬 `ffmpeg`, `ffprobe`, `espeak-ng` 실제 실행 경로를 시험. 이건 외부 API 요청이 아니며 AI 관리자 판단 대체가 아니라 도구 자체 정상성 검사. 영상 오디오 true/false와 단일/다중 scene, stdout/returncode, codec/filter/audio length, FFmpeg 설치 기능, 폰트 경로, 시간 초과 등을 단계별로 분석. 사용자 개인/회사 자료나 실패한 Gemini 직원의 비밀을 subprocess/stderr로 흘리지 않는다.
- 원인이 Python/FFmpeg 파이프라인 결함이면 **최소 수정**하고 합성 fixture로 실제 미디어 디코딩까지 확인. 예: 명령 옵션 순서, 필터 구성, 설치 라이브러리, 장면 오디오 처리, concat, ffprobe. 기술적으로 필요한 제한은 정확히 검사하되 자막 길이·화면 구성·미적 품질 결정은 AI 관리자와 직원 판단에 두어라. 단지 '더 짧은 자막을 쓰라'는 고정 업무 규칙 추가가 해결책이 되어서는 안 된다.
- 증거가 부족하면 성공을 주장하지 말고 필요한 최소 관측 장치를 보완. 미래 로컬 호출에서 **오류 단계 식별자만** allowlist enum으로 보존 (예: espeak_audio, ffprobe_audio, ffmpeg_segment, ffmpeg_concat, ffprobe_final, ffmpeg_decode), 예외 유형의 고정 분류(executable_missing, exit_nonzero, timeout, os_error 등) 및 안전한 exit code 정수 정도. stderr 원문/실행 환경/명령 인자(텍스트 파일 경로 포함), 키/사용자 데이터/프로젝트 path는 저장하거나 모델에 넘기지 않음. 오류 정보를 AI 관리자에게 전달할 안전한 구조까지 검토.
- **내부 AI 자율복구 원칙을 점검**: 실제 작업에서 로컬 도구 실패가 단순한 기술적 일시 결함인 경우 안전 경계 안에서 내부 AI 관리자에 전달해 직원에게 해결 지시할 수 있는지 검토. 외부 Gemini 호출/실제 과금/중복전송을 허용 없이 자동 재개하는 설계 금지. 이전 stopped 원장은 실패로 남기고, 앞으로 신규 프로젝트의 검증된 범위에서만 자율 회복. 대규모 상태머신 변경이 필수라면 오프라인 단계에서는 최소 계약 정의 후 범위 및 복구 방식 보고.
- `caption_overflow` 수정 뒤 또다시 내부 외부 통제가 늘어나는 것을 방지: 기술적 불변 제약과 AI 업무 품질 판단을 명시적으로 분리. Codex가 28자/4줄 등 비즈니스/품질 기준을 임의 확대하거나 자막 내용을 정하지 말 것. 필요시 렌더링의 물리적 constraints를 AI가 알 수 있게 정확히 노출하고, 선택은 AI가 하도록 할 것.

## 3. 검증
- 실제 외부 AI API 0회. 수동 기존 project execute/continue/run/approve 0회. 기존 프로젝트/계정/키/동의/원장/동영상/백업 수정 0.
- 외부 socket 없는 테스트 fixture로 subprocess 각 단계 실패/안전한 오류 식별 보존, 미디어 렌더 단일/다중 및 audio true/false, 기존 Gemini fake workflow 회귀를 가급적 짧게 확인.
- 테스트 실패를 해결하지 못하면 '완료'라고 쓰지 말 것. `git diff --check` 확인. 변경 파일/보고서만 선택적 commit/push. 기존 Git 사용자 미추적 파일·백업 보존, reset/clean/force push 금지.
- `reports/v01_gemini_second_live_local_tool_failure_20261104.md`에 한국어/KST로 근거, 실 API 요청 횟수와 성공 단계, local tool 정확한 원인 **확인/미확정 구분**, 수정·실제 로컬 media test, 남은 제약, 다음 실사용 완주를 위해 필요한 단 하나의 후속 조치를 작성.
- 수정이 확정되고 오프라인 엔드투엔드 검증이 성공했다면, 새 격리된 세 번째 테스트 프로젝트 **준비만** 가능. 준비 시 모델/무료 계정/전송 범위/최초 동의안 서명 검토, 만료, 실행 명령을 보고하되 실제 API 전송은 이번 작업에서 승인되지 않았다. 기존 stopped 프로젝트 동의·원장을 재사용하지 않는다.

## 완료 기준
'AI가 실패했다' 같은 추측이나 무작정 키/모델 재시도를 하지 말고 **실제 Gemini 2차 수행 단계 + 로컬 FFmpeg/TTS 실패를 재현 및 해결하거나 최소 관측으로 좁힌다.** 최종 목표는 실제 AI 자율 협업→최종 MP4/보고서 완주이며 Codex의 offline fixture는 실제 AI 성공이 아니다.
