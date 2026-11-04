# 두 번째 Gemini 실사용 local_tool_failed 분석과 안전한 단계 진단

2026-11-04 14:32 KST. `git pull --ff-only`로 e48550a 반영. 핵심 원칙·AGENTS.md·한국어 규칙·지정 지시서·직전 자막 보고서와 기존 로컬 도구/회사/Gemini/실행 준비 경로 및 관련 테스트를 확인했다.

**Gemini 두 번째 프로젝트도 실제 관리자 계획과 첫 직원 응답까지 HTTP 200으로 성공했다. 실패는 이후 로컬 subprocess 실행 경로에서 발생했다. 과거 정확한 실패 프로그램/단계/종료 코드는 저장되지 않아 미확정이다. 이번 작업에서는 실제 AI API 호출 0회, 기존 프로젝트 재실행·approve/run/continue/execute 0회다.**

## 첫 번째와 두 번째 실사용의 관측 범위

각 프로젝트를 기존 GeminiStore.load로 읽고 storage_hash 무결성을 검증했다. 상태/원장/이벤트만 제한적으로 요약했으며 raw 응답·직원 자막·키·환경값을 출력하지 않았다.

| 프로젝트 | 실제 관리자 plan | 실제 직원 execute | 저장된 업무/검토 | 정지 사유 |
|---|---|---|---|---|
| 첫 번째 db22e41… (data/gemini-first-autonomous-20261104) | 14:11:19→14:11:22, HTTP200, completed/validated | 14:11:22→14:11:23, HTTP200, completed/json_parsed | 계획3개/기준4개, 직원 버전0·검토0 | caption_overflow |
| 두 번째 df659083… (data/gemini-caption-recovery-20261104) | 14:27:39→14:27:41, HTTP200, completed/validated | 14:27:41→14:27:43, HTTP200, completed/json_parsed, task_01 | 계획3개/기준4개, 직원 버전0·검토0 | local_tool_failed |

두 번째 대상의 전체 ID는 `geminicompany-df65908337b04143b576e5cbfc076abb`. 각 프로젝트의 실제 시도는 2회씩이며, 이 두 프로젝트에서 합계 4회 HTTP200이다. 이는 기존 단건 인사/다른 공급자의 호출 수를 포함한 전체 계정 사용량이라는 뜻이 아니다. 모델은 gemini-3.1-flash-lite다.

completed는 API 요청 처리 완료이지 최종 직원 결과/MP4 완료가 아니다. 두 번째 직원 결과는 역할 JSON 파싱까지 도달했고 local_tool_reserved 이후 실패해 version 저장·관리자 review 전이다. task_01/02/03 모두 pending, 버전/검토0, active_operation은 마지막 시도를 가리킨 채 보존된다. 실패 API 예약으로 임의 바꾸거나 active_operation을 해제하지 않았다.

두 번째 이벤트는 operating_scope_approved→ai_manager_decision(plan)→local_tool_reserved→system_safety_stop이다. 상태 stopped/phase work, artifacts={}, 최종 보고/MP4 없음. 첫 번째도 최종 보고/MP4가 없다. 후속 직원 간 인계·검토·수정·finalize는 두 프로젝트 모두 실제 실행되지 않았다.

## 정확히 확인된 것과 복원 불가한 원인

두 번째 local_tool_failed는 기존 `run_command`가 subprocess의 OSError/CalledProcessError/TimeoutExpired 등 모든 실패를 같은 코드로 축약한 것이다. 이 호출은 renderer의 자막 준비·구조 검증·출력 경로/폰트 존재 확인 뒤에만 시작한다. 따라서 두 번째는 첫 번째의 caption_overflow 지점보다 더 진행해 subprocess 경로에 진입한 것으로 구분할 수 있다.

하지만 어떤 프로그램이 실행됐는지, 음성 true/false인지, 어느 scene인지, 종료 코드·timeout·실행 파일 누락 중 무엇인지는 저장되지 않았다. 실패한 직원 content는 version에 없고 raw response도 보존되지 않았다. 임시 작업 폴더는 컨텍스트 종료 때 정리되므로 남은 MP4/파일이 없다는 사실만으로 concat 이전 실패라고 추론할 수 없다. 과거 오류를 복원하거나 FFmpeg/TTS/권한/메모리 원인 중 하나로 단정하지 않았다.

확인된 코드 결함은 **로컬 오류의 발생 단계·종류가 사라지는 진단 손실**이다. 원래 media 실행 실패 자체의 특정 원인이 해결됐다고 주장하지 않는다.

## 실제 로컬 재현 검사

사용자 프로젝트를 사용하지 않고 새 `/tmp` 임시 디렉터리에서 안전한 합성 문구만 넣어 `render_video`를 직접 실행했다. 실제 모델/업무 판단 대체가 아니라 도구 정상성 검사다.

| 720×1280 합성 입력 | 결과 | ffprobe 측정 길이 |
|---|---|---|
| 단일 scene / 무음 | 렌더·디코딩 성공 | 3.000초 |
| 3 scene / 무음 | 렌더·concat·디코딩 성공 | 9.000초 |
| 단일 scene / 로컬 한국어 음성 | TTS·렌더·디코딩 성공 | 3.02322초 |
| 3 scene / 로컬 한국어 음성 | TTS·렌더·concat·디코딩 성공 | 9.02322초 |

실행한 로컬 진단은 Python에서 `TemporaryDirectory`와 `render_video`를 호출한 4개 조합이며, 실제 회사 execute 명령은 사용하지 않았다. returncode를 숨겨 실패를 성공으로 간주한 것이 아니라 renderer의 check=True subprocess와 기존 ffprobe·전체 디코딩 검사를 통과했다. 이 4개 입력으로 과거 local_tool_failed는 재현되지 않았다.

로컬 설치 확인: ffmpeg/ffprobe/espeak-ng 모두 존재, 한국어 폰트 존재. `ffmpeg -hide_banner -filters`와 `-encoders`는 각각 returncode=0이며 drawtext/apad/color 및 libx264/aac 제공 여부를 boolean만 확인했다. 설치된 모든 버전/과거 실행 환경이 동일하다는 보장은 아니다. 합성 검사는 기존 옵션 순서·필터·음성 입력·concat 경로가 현재 입력에서 정상임을 보여주며, 과거 특정 입력·자원 상태까지 증명하지 않는다. 재현되지 않은 pipeline을 추측으로 변경하지 않았다.

## 수정 내용과 내부 AI 복구 경계

변경 파일은 `local_artifacts.py`, `autonomous_free.py`, `tests/test_local_tool_diagnostics.py`, `tests/test_autonomous_gemini.py`, 이 보고서다.

`run_command`는 각 호출에 고정 stage를 요구하고 LocalToolError로 다음 정보만 반환한다.

- stage: espeak_audio / ffprobe_audio / ffmpeg_segment / ffmpeg_concat / ffprobe_final / ffmpeg_decode.
- category: executable_missing / exit_nonzero / timeout / os_error.
- exit_code: 허용 범위의 정수 또는 null. 오류 메시지/errno 문자열은 사용하지 않는다.

stage/category/exit code를 클래스에서도 검사한다. stdout은 기존 probe 처리에만 사용하며 오류 diagnostics에는 넣지 않는다. stderr 원문, command/인자, 자막·임시 파일 경로, 사용자 환경·키·프로젝트 path를 보존하거나 모델에게 넘기지 않는다. 기존 reason_code=local_tool_failed는 호환성을 위해 유지한다.

미래 신규 프로젝트에서 FreeCompany가 LocalToolError를 받으면 `local_tool_failed` 이벤트에 task_id와 위 고정 diagnostics, automatic_retry=false를 저장한 뒤 기존 안전 정지 흐름으로 넘긴다. API completed/직원 result validation과 로컬 실패를 구분할 수 있다. 과거 원장에 새로운 stage를 소급 작성하지 않았다.

이 이벤트는 향후 관리자에게 전달할 최소 안전 계약이다. 아직 관리자 prompt로 자동 재전송하거나 stopped 프로젝트를 재개하지 않는다. 내부 자율 회복을 구현하려면 신규 프로젝트에서 실패한 직원 결과와 안전한 tool_failure를 보존하고, 기존 manager review에 전달해 수정/정지/운영 권한 요청을 판단하도록 해야 한다. 실패한 로컬 도구 동작을 AI 요청 실패와 구별하고 기존 task revision/전체 revision·중복 operation·미확정 보호를 함께 적용해야 한다. 이번에는 상태 기계를 크게 바꾸거나 허가 없는 추가 모델 호출을 만들지 않았다.

자막 28자/4줄 등 기존 검사·내용·크기/장면 구성은 변경하지 않았다. Codex가 미적 품질 기준을 늘리거나 직원 내용을 재작성하지 않았다. TTS 길이 초과·실제 파일 존재·디코딩 같은 기술 검사는 유지하며, 의미/시각/음성 품질 판단은 AI 관리자/직원의 역할로 남긴다.

## 회귀 검증과 보존

```bash
python -B -m unittest tests.test_local_tool_diagnostics tests.test_local_artifacts tests.test_caption_reflow tests.test_autonomous_gemini
```

**22개 통과, 실패/오류0, exit0 (28.995초).** socket/DNS 차단 fixture로 6개 stage 각각의 실행 파일 부재/permission OSError/양수·음수 종료 코드/timeout을 주입했다. 비밀이 담긴 가짜 stderr/command 문자열이 예외 표시·diagnostics에 포함되지 않음을 검증했다. unknown stage는 subprocess 전에 차단된다. 가상 Gemini 업무의 도구 실패 이벤트 저장·원장 소진 보존·추가 run 무재송신도 확인했다. 기존 로컬 음성/무음 MP4, 자막 reflow, fake manager→직원 인계/수정→MP4→최종 보고 회귀를 포함한다. fixture 성공을 실제 AI 완주로 표현하지 않는다.

`git diff --check` 통과. 기존 data/backups/checkpoints **90개 파일 전후 SHA256 모두 동일**. 두 실사용 stopped 프로젝트, 소진 시작 표식, 동의/서명 키/attempt/active_operation, 과거 Gemini 2.5 단건·Groq/OpenRouter 실패/예약, 기존 영상·백업 및 사용자 미추적 파일을 보존했다. 실제 API0회, 기존 execute/run/continue/approve0회, 기존 업무 데이터 수정0건이다.

## 남은 한계와 다음 조치 한 가지

현재 결론은 **과거 local tool 정확한 원인 미확정, 진단 손실 수정 및 현재 합성 media 정상성 확인**이다. 특정 pipeline 결함이 재현/확정돼 고쳐진 상태가 아니므로 세 번째 실사용 프로젝트를 자동 생성·승인·실행하지 않았다. 키/모델/무료 계정/결제/proxy/TLS 설정도 변경하지 않았다.

다음 한 가지 조치는 **단계 진단을 적용한 새 독립 프로젝트의 최초 운영 동의 후 완주 실행 1회를 별도로 승인하는 것**이다. 이전 stopped 프로젝트/동의를 재사용하지 않고 새 목표·고정 모델·무료 조건·전송 범위·로컬 도구·소진 원장을 검토해야 한다. 이번 보고서는 그 실제 실행 권한을 생성하지 않는다.

목표→AI 자율 협업→최종 산출물 앞에서 Gemini 응답 자체는 이미 성공했다는 근거를 확인했고, 다음 로컬 실패를 모호한 단일 코드로 잃지 않게 했다. 실제 직원 결과 저장·내부 검토/수정·인계·최종 MP4/보고 완주는 여전히 미완료다. 새 사용자 업무 중간 결재는 추가하지 않았으며 로컬 도구 실패의 내부 AI 복구와 기존 수동 프로젝트 승인 부채는 남아 있다.
