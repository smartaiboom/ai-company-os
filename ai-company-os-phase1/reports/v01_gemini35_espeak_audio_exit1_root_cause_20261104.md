# 실제 Gemini 3.5 직원 제출물의 espeak exit1 재현·수리

2026-11-04 KST. `git pull --ff-only`로 91f35f9 반영. 핵심 원칙·AGENTS.md·한국어 규칙·지정 지시서·기존 보고서/로컬 도구/관리자 검토 경로를 확인했다.

**확정 원인: 이 환경의 espeak-ng가 긴 파일명 인자를 199바이트 ASCII 경로에서 잘라 처리한다. 앱이 깊은 프로젝트 경로의 자막 파일을 절대 경로로 전달해 읽기 실패/exit1이 발생했다.** 같은 파일을 app-owned 작업 디렉터리에서 짧은 상대 파일명으로 전달하도록 수리했다. 자막·언어·음성 요청·장면 시간을 바꾸지 않았다.

실제 AI API 호출 **0회**, 기존 프로젝트 execute/run/continue/approve0회, 기존 업무 기록 수정0건이다. 실제 직원 제출물 두 버전은 읽기 전용으로 가져와 임시 경로의 로컬 실험에만 사용했다.

## 실사용 근거와 입력 특징

대상은 `data/gemini35-nested-tool-review-20261104` / `gemini35company-1dc335e5b1324ce690a0e9f19945691d`. Gemini35Store.load로 storage_hash를 검증했다. 기존 상태는 stopped/work/manager_stopped, artifacts={}다.

실사용 API5회 모두 HTTP200/completed/validated: plan→execute→review→execute→review. 첫 manager review=revise, 수정 후 두 번째 review=stop이다. 첫 task의 직원 version2개 모두 tool_status=failed, espeak_audio/exit_nonzero/exit_code1이 저장돼 있다. 뒤 업무는 아직 pending이며 MP4/최종 보고는 없었다. validated는 역할/검토 자료 커밋이지 도구 성공이 아니다. 실제 AI가 내부 검토·수정까지 수행했음을 확인했으며 그 판단을 Codex가 대체하지 않았다.

두 version의 content는 완전한 내부 tool JSON으로 파싱되고 기존 schema/prepare_video 검증을 통과했다. 원문과 prepare_video 후 caption은 두 버전 모두 동일(reflow0)이다. 원문 content/자막 전문은 대화·Git·보고서에 복사하지 않았다.

| 직원 version | 장면별 문자 수(개행 포함) | 줄 수 | 장면 seconds | audio |
|---|---|---|---|---|
| 1 | 20,19,20,20 | 2,3,3,3 | 5,7,8,7 | true |
| 2 | 25,23,29 | 3,3,3 | 7,8,8 | true |

UTF-8 파일, BOM 없음, 제어문자는 허용 개행뿐이다. 주로 한글·공백·개행이며 일부 대문자 라틴 문자가 있고 ASCII 특수기호는 없다. 특정 직원 내용이나 회사 자료를 노출하지 않고 특징만 확인했다.

## 로컬 재현으로 원인 분리

기존 프로젝트 폴더에는 쓰지 않고 새 TemporaryDirectory에서만 조사했다. renderer와 같은 `espeak-ng -v ko -s 155 -f <caption-file> -w <wav-file>` 옵션과 실제 prepare_video 후 UTF-8 caption을 사용했다. stderr/stdout은 메모리에서 기술 판별에만 사용하고 저장/출력하지 않았다.

1. 짧은 `/tmp` 경로에서 실제 7개 scene을 각각 실행: **7/7 exit0, WAV 생성**, stderr0 bytes. 짧은 합성 한국어도 같은 결과였다. 바이너리 부재·ko voice 부재·자막 인코딩/문장 길이 자체 문제를 이 재현에서 배제했다.
2. 새 임시 경로를 길게 만든 뒤 같은 실제 caption을 그대로 사용: **7/7 exit1, WAV 미생성**. 시험 input 경로는 ASCII224자였으며 오류가 참조한 경로는 입력의 처음199바이트와 일치하고 전체 경로/200바이트 prefix와는 일치하지 않았다. 원문 오류 메시지·경로는 보고하지 않고 원인 enum `tts_filename_argument_truncated`로 요약한다.
3. 같은 물리적 파일·동일 deep directory를 그대로 두고 자식 프로세스 cwd를 해당 디렉터리로 지정, `-f 0.txt -w 0.wav`로 실행: **7/7 exit0, WAV 생성**. 파일 권한·내용·voice·rate를 바꾸지 않고 인자 길이만 바꿔 원인을 분리했다.

합성 경로 비교에서도 파일 경로105/184자는 성공, 224/264/304/344자는 exit1이었다. 실제 기존 tool 폴더 자체의 절대 경로 길이가217자이고 여기에 renderer의 임시 폴더와 caption 파일명이 붙으므로 문제 경계를 넘는다. 예전 짧은 임시 경로 fixture가 이 결함을 놓친 이유도 확인됐다.

추가 분리 검사: 긴 `-f`/짧은 `-w`는 exit1, 짧은 `-f`/긴 `-w`는 exit0이지만 기대한 WAV 경로에 파일이 없었다. 양쪽 상대 파일명을 쓰면 정상 생성됐다. 따라서 입력·출력 두 파일명을 모두 짧게 전달해야 하며 exit0만으로 성공을 단정해서도 안 된다. 기존 ffprobe/파일 검사도 계속 유지한다. 이 수치는 **현재 설치 빌드의 실측**이며 모든 espeak 버전의 보편적 제한이라고 주장하지 않는다.

과거 다른 프로젝트의 local_tool_failed는 당시 stage/raw 입력이 없으므로 이번 원인을 그 기록에 소급 확정하지 않았다. 이번에 보존된 두 version과 동일 기술 조건의 재현이 확인 대상이다.

## 최소 수리와 실제 제출물 검증

변경 파일: `local_artifacts.py`, `tests/test_espeak_long_path.py`, 이 보고서.

run_command에 optional cwd를 추가하고, espeak 호출만 app-owned 임시 작업 폴더를 cwd로 사용한다. `caption.name`과 `wav.name`을 인자로 보내며 글로벌 os.chdir는 하지 않는다. ffprobe/FFmpeg 경로·필터·출력/진단 정책은 그대로다. 실패 시 기존 고정 stage/category/exit_code를 유지하고 stderr/인자/cwd는 영속화하거나 모델에 전달하지 않는다.

자막 단축/삭제·JSON 재작성·audio:false 강제·voice 변경·언어 변환·장면 시간 변경·자동 retry는 없다. 기존 관리자 검토/직원 수정/도구 receipt 및 안전 경계도 변경하지 않았다.

수리 후 실제 직원 두 version의 **원본 spec**을 새 deep TemporaryDirectory에서 render_video로 완전 렌더했다.

| 직원 version | 결과 | 실측 길이 | 해상도 | 음성 |
|---|---|---|---|---|
| 1 | MP4 존재, ffprobe 검사·전체 디코딩 성공 | 27.02322초 | 640×360 | true |
| 2 | MP4 존재, ffprobe 검사·전체 디코딩 성공 | 23.02322초 | 640×480 | true |

이 MP4는 **실제 Gemini가 저장해 둔 제출물을 로컬 수리 실험에서 렌더한 결과**다. 원래 stopped 프로젝트의 artifact로 넣지 않았고 manager의 사후 수락/최종 보고를 만들지 않았다. 임시 실험 출력은 컨텍스트 종료로 정리됐다. 음성·영상 기술 정상성은 확인했지만 의미·미학·실제 회사 전체 완주는 평가/주장하지 않는다.

## 회귀 테스트와 보존

```bash
python -B -m unittest tests.test_espeak_long_path tests.test_local_tool_diagnostics tests.test_local_artifacts tests.test_nested_tool_review
```

**13개 통과, 실패/오류0, exit0 (19.654초).** 긴 app-owned 경로에서 한국어 음성 MP4 실렌더/디코딩, espeak 입력·출력 인자가 짧은 basename인지, cwd 전달 후에도 안전한 실패 진단만 유지되는지, 기존 stage/자막/미디어·가상 manager 수정/인계/최종 보고를 확인했다. fixture는 외부 socket/DNS 차단·가짜 모델만 사용하며 실제 API 성공과 구별한다.

위 단위 테스트 외에 실제 제출물7개 scene의 수리 전후 TTS 비교와 원본2개 spec의 전체 media 검사를 별도로 수행했다. `git diff --check` 통과. 기존 data/backups/checkpoints **117개 파일 SHA256 전후 모두 동일**. 기존 모든 프로젝트/동의/원장/소진 표식/키/백업·artifact와 사용자 미추적 파일을 보존했다. 모델/공급자/계정/결제·proxy/TLS 변경0이다.

## 독립 프로젝트 준비와 후속 경계

원인 수리·검증 후 `python -B gemini35_first_project.py --store data/gemini35-espeak-path-fix-20261104 prepare`만 실행했다. 새 project=`gemini35company-cfb4b6f6b98d4075ba4e272caf00ee56`, ready/enabled=false/attempts0, grant·서명 키·시작 소진 파일 없음. 기존 직원 결과/동의/해시를 복사하지 않았다.

발행 2026-11-04T15:56:13+09:00, 만료 **2026-11-05T15:56:13+09:00**. 동일 비밀 없는 합성 목표, gemini-3.5-flash-lite/고정 generateContent, 기존 무료 계정·비용0 정책/허용 전송 범위/로컬 도구 및 nested/manager 검토 정책의 신규 동의안이다. 계정/청구 API는 조회하지 않았으며 실제 사용 시 현재 Free Tier 확인과 별도 사용자 최초 운영 동의가 필요하다.

필요한 후속 행동은 **새 프로젝트의 무료 등급·목표·전송 범위/동의안을 검토한 뒤 최초 실행에 별도로 동의하는 것 하나**다. 그 동의 후에만 사용할 명령이며 이번에는 실행하지 않았다.

```bash
python -B gemini35_first_project.py --store data/gemini35-espeak-path-fix-20261104 execute --review-hash 4ad68684604ecf76ae1a716cf7faaa7c8f6e010947b9777d2852613adbe9f092 --owner-confirmed --confirm-free-tier
```

이번 수리는 실제 AI가 두 번 수정/검토해도 해결할 수 없던 로컬 파일명 전달 결함을 제거해 목표→AI 자율 협업→MP4 최종 산출물의 실행 거리를 줄였다. 사용자 업무 중간 결재나 고정 품질 판단은 추가하지 않았다. 실제 회사의 최종 MP4 수락/후속 인계/최종 보고 완주, 서비스 안정성 및 기존 수동 프로젝트 승인 부채는 남아 있다.
