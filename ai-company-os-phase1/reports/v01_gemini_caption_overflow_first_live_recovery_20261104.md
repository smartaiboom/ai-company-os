# Gemini 첫 실사용 진행 확인 및 caption_overflow 회복 준비

2026-11-04 KST. `git pull --ff-only`로 fce7276 반영. 핵심 원칙·AGENTS.md·한국어 규칙·지정 지시서·직전 연동 보고서·회사 실행 경로·Gemini·로컬 도구·관련 테스트를 확인했다.

**첫 프로젝트는 실제 Gemini 관리자 계획과 첫 직원 응답까지 성공했고, 로컬 자막 입력 검증에서 중단됐다. 이번 작업의 추가 실제 AI API 호출·기존 프로젝트 재실행은 모두 0회다.** 네트워크 연결 실패로 추측하지 않는다. 첫 MP4 및 최종 보고 완주는 아직 미달이다.

## 읽기 전용 실사용 근거

기존 `GeminiStore.load`로 저장 무결성(storage_hash)을 검증하고 상태·이벤트·원장을 읽었다. 대상은 `data/gemini-first-autonomous-20261104`, 프로젝트 `geminicompany-db22e41adcc4446d9904e44c363df5fc`다.

| 실제 단계 | KST 예약→완료 | HTTP/원장 | 도달한 범위 |
|---|---|---|---|
| 관리자 plan | 14:11:19→14:11:22 | 200 / completed / validated | 실제 계획·품질 기준 채택 |
| 직원 execute, task_1 | 14:11:22→14:11:23 | 200 / completed / json_parsed | 역할 JSON 검증 후 로컬 도구 진입; 업무 완료 커밋 전 중단 |

실제 모델은 `gemini-3.1-flash-lite`. 저장된 실사용 시도는 **2회, 두 요청 모두 HTTP 200**이다. completed는 HTTP 요청 처리가 끝났다는 의미이며 두 직원 업무가 완료됐다는 뜻이 아니다. active_operation은 마지막 시도를 가리킨 채 보존돼 있다.

관리자가 생성한 업무는 3개, 기준은 4개다. task_1=스크립트 작성/콘텐츠 기획자, task_2=영상 제작/영상 편집자(선행 task_1), task_3=최종 검토 및 보고/AI 관리자(선행 task_2)로 저장돼 있다. 세 업무의 저장 상태는 pending이고 versions/reviews/revisions 모두 0이다. 첫 직원이 도구 JSON을 반환해 렌더 경로에 진입했지만 결과 버전 저장 이전에 실패했다. 이후 직원 간 인계·관리자 검토/수정·finalize는 아직 실행되지 않았다.

이벤트는 operating_scope_approved→ai_manager_decision(plan)→local_tool_reserved(task_1)→system_safety_stop이다. 상태 stopped, phase work, reason caption_overflow, artifacts={}, final=null이다. 해당 store에서 MP4 0개, final.md 0개를 확인했다. raw request/response·자막 전문·키를 출력하지 않았다.

## 정확한 중단 규칙과 남지 않은 정보

실행 경로: `FreeCompany._call`의 직원 역할 JSON 처리→tool JSON 파싱→local_tool_reserved 저장→`local_artifacts.execute`→`render_video`→`validate_video`다. 이 검증은 FFmpeg/TTS 실행 전 수행된다.

기존 자막 조건은 scene 총 text 120자 이하뿐 아니라 **줄당 28자 이하, scene당 최대 4줄**이었다. 후자의 어느 조건이든 위반하면 caption_overflow를 발생시킨다. 그러나 모델에게 전달한 기존 TOOLS 설명에는 줄 길이/줄 수 제한이 누락됐다. 도구를 쓰라는 안내와 실제 검사 계약의 불일치가 확인됐다.

당시 원장에는 도구 입력 hash만 저장됐고, 실패한 직원 결과/scene 원문은 버전으로 저장되지 않았다. 아티팩트 폴더에도 자막 파일이 없다. 따라서 **과거 초과 scene index·줄 길이·줄 수는 복원 불가**다. 특정 줄이 몇 자였다고 꾸며 쓰지 않는다. caption_overflow 이전의 검사 순서상 최상위 구조와 실패 지점까지의 scene 120자·duration 검사는 통과했지만 실패 scene이 몇 번째인지는 알 수 없다. 생성 응답의 전체 문자 수를 자막 길이로 간주하지 않았다.

## 최소 수정

- `local_artifacts.py`: TOOLS에 줄당 28자/최대 4줄/총120자(개행 포함), 1~16 scene, 0.5~30초/scene·총120초, 짝수 해상도 240~1920, boolean audio, 허용 제어문자와 TTS 시간 초과 조건을 명시했다. 기존 시스템 prompt가 TOOLS를 포함하므로 모든 관련 모델 단계에서 같은 계약을 받는다.
- `prepare_video`: 구조·길이·duration을 먼저 검사하고, 긴 줄의 ASCII 공백을 결정적으로 개행으로 교체한다. 기존 개행과 모든 비공백 글자를 그대로 유지한다. 한 단어를 중간에서 나누거나 글자를 삭제/축약/재작성하지 않는다. 공백 경계로도 28자×4줄 안에 못 넣으면 계속 caption_overflow로 중단한다. strict `validate_video`는 기존과 같이 긴 원문을 직접 통과시키지 않는다.
- 렌더는 원문 spec의 독립 복사본만 사용한다. 원래 직원 content/기존 input_hash는 유지하고 receipt의 caption_reflow에 원문/렌더 spec hash, 변경 scene index, 공백→개행 문자 위치, 전후 줄 길이를 남긴다. 원문 버전과 위치를 함께 보면 변환을 정확히 재구성할 수 있다. 단순 줄바꿈을 AI의 새 작성 결과로 표시하지 않는다.
- `gemini_first_project.py`: `--store`로 새 독립 준비 경로를 지정할 수 있게 했다. 기본 경로는 유지하며 기존 폴더가 있으면 prepare를 거부한다. stopped/동의/시도/소진 시작 표식은 초기화하지 않는다.
- `tests/test_caption_reflow.py`, `tests/test_autonomous_gemini.py`, 이 보고서.

TOOLS는 기존 서명 계약에 포함되므로 이전 동의를 새 도구 설명으로 바꾸지 않았다. 새 프로젝트는 수정된 TOOLS를 포함한 새 최초 동의안이 필요하다. 대규모 상태 전이를 피하기 위해 **도구 입력 실패→관리자 피드백→직원 재수정의 자동 회복은 이번에 추가하지 않았다**. 줄바꿈 불가/줄 수 초과가 남으면 안전 정지한다. 향후 내부 회복은 직원 실패 입력/분류의 보존, manager 수정 지시, 기존 revision 예산과 operation 중복 보호를 함께 설계해야 한다. 사용자 업무 중간 결재를 대안으로 추가하지 않았다.

`narration_exceeds_scene`은 실제 로컬 음성 길이가 장면보다 긴 경우이며 그대로 유지했다. `local_tool_failed`/폰트·디코딩·미디어 검사 실패도 가능하다. 자막 줄바꿈만으로 음성 길이·영상 미적 품질·의미 검증이 해결되는 것은 아니다. 목표의 20~30초를 실행 로직에 하드코딩하지 않았다.

## 오프라인 검증

초기 집중 검사 19개 중 1개 실패: 같은 scene 객체를 여러 번 참조하는 입력에서 복사본이 alias를 유지해 변환 이력이 하나만 남았다. scene별 독립 복사로 수정했다. 경계 fixture의 120자 길이도 정확히 맞췄다.

최종 실행 명령:

```bash
python -B -m unittest tests.test_caption_reflow tests.test_local_artifacts tests.test_autonomous_gemini tests.test_autonomous_groq
```

**29개 통과, 실패/오류 0, exit 0 (31.357초).** 긴 한국어 공백 경계, 28자 경계, 기존 개행, 최대4줄/초과, 총120자/121자, 단어 분할 불가, 다중 scene, duration 및 도구 설명 일치, 원문 불변/위치 재구성/멱등성을 검증했다. Gemini fake 협업에 긴 자막을 주입해 manager→직원 인계·검토/수정→실제 로컬 MP4→최종 보고까지 확인했다. 이 fixture는 무음으로 자막 변환을 검증하며 기존 음성 MP4 fixture도 별도로 통과했다. 네트워크/socket/DNS를 차단한 가상 모델 테스트이며 **실제 Gemini 추가 성공이 아니다**. 로컬 기술 검사/디코딩 통과와 시각·음성 품질 판단은 구별한다.

`git diff --check` 통과. 기존 data/backups/checkpoints 82개 파일 SHA256 전후 모두 동일. 첫 실사용 프로젝트, 원장·grant·서명 키·소진 시작 파일, 과거 Gemini 단건·Groq/OpenRouter 실패 및 예약, 기존 영상·백업을 보존했다. 기존 사용자 미추적 파일도 변경하지 않았다. 이번 추가 API 0회, 기존 run/continue/execute 0회, 과거 상태 변경 0건이다.

## 새 독립 프로젝트 준비와 한 가지 후속 조치

오프라인 준비 명령 `python -B gemini_first_project.py --store data/gemini-caption-recovery-20261104 prepare`를 실행했다. 새 프로젝트는 `geminicompany-df65908337b04143b576e5cbfc076abb`, ready/enabled=false/attempts=0, grant·서명 키·시작 소진 파일 없음이다. 기존 목표와 같은 합성 목표이며 기존 plan/직원 결과를 복사하거나 재승인하지 않았다. 새 동의안은 2026-11-05T14:18:55+09:00에 만료된다.

사용자에게 필요한 정확한 다음 조치는 **수정된 도구 계약을 포함한 신규 프로젝트의 최초 운영 동의 후 자율 실행 한 번**이다. 해당 키 프로젝트의 실제 Free Tier를 확인하고 새 목표/전송 범위를 검토한 뒤 유효기간 내 아래 한 명령으로 진행할 수 있다. 이것은 이번 작업에서 실행하지 않았다.

```bash
python -B gemini_first_project.py --store data/gemini-caption-recovery-20261104 execute --review-hash f8f3a1f74b79d57f4f7f1297200d289ab670d9fd9efc352f0721b86615f5c000 --owner-confirmed --confirm-free-tier
```

모델/endpoint는 고정 Gemini 3.1 Flash-Lite generateContent, 비용 상한 0/유료 fallback 없음이다. 외부 전송 범위는 합성 목표·계획·기준·직원 결과·관리자 검토·최종 통합이며 기존 로컬 caption_video_v1만 허용한다. 요청 원장 선예약/중복 보호·쿼터/실패/미확정 중단·수정 상한은 유지한다. 모델·계정 무료 조건의 새 온라인 검증이나 실제 API 접속을 이번에 수행했다고 주장하지 않는다.

이번 변경은 실제 AI 계획/첫 직원 작업 뒤 최종 산출물을 막았던 도구 계약 불일치를 줄였다. 실제 관리자 검토·직원 인계·MP4 최종 완주는 아직 남아 있다. 신규 자율 경로에 업무별 사용자 승인 단계를 추가하지 않았고 기존 수동 프로젝트의 반복 승인 부채는 이번 범위에서 변경하지 않았다.
