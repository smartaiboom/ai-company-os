# Gemini 3.5 직원 내부 도구 JSON 오류의 관리자 검토 연결

2026-11-04 KST. `git pull --ff-only`로 6837273 반영. 핵심 원칙·AGENTS.md·한국어 규칙·지정 지시서와 기존 역할 JSON/도구 JSON 처리, 회사 review/revision·동의·원장·로컬 도구·테스트를 확인했다.

**신규 Gemini35 프로젝트에서 내부 도구 입력 파싱/형식 오류를 기존 관리자 검토·직원 수정으로 연결했다. 실제 AI API 호출 0회, 기존 프로젝트 실행/재실행/approve 0회다. 오프라인 한 사이클은 통과했으며 실제 Gemini 전체 완주는 아직 미검증이다.**

## 실제 실패 기록과 코드 위치 대조

대상 `data/gemini35-first-autonomous-20261104`, `gemini35company-2b01639ee7284443b5c68dfdae206949`를 기존 Gemini35Store.load로 읽어 storage_hash 무결성을 검증했다.

- 상태 stopped / phase work / reason invalid_model_json, active_operation 보존, artifacts 없음.
- 관리자 attempt: HTTP200 / completed / validated, envelope/역할 JSON parsed.
- 직원 attempt: HTTP200 / completed / json_parsed, envelope parsed, finish stop, 역할 JSON parsed. diagnostic content_chars=703, prompt1049/output324/total1373 tokens.
- 직원 version0·review0. 직원 결과 커밋·관리자 검토·인계·MP4/최종 보고 전 중단됐다.

HTTP/역할 JSON 성공과 내부 업무 문자열의 JSON 성공은 별개다. content_chars=703은 외부 역할 응답 진단이며 실제 내부 도구 JSON 길이라고 단정하지 않는다. 원문 직원 content는 저장돼 있지 않으므로 잘못된 따옴표/쉼표/이스케이프 등 구체적 문법을 복원하지 않았다.

`invalid_model_json`은 공용 parse에서 발생한다. 코드 경로를 비교하면 요청 payload parse는 전송 전, 외부 role parse는 role_result_status=json_parsed 설정 전이며, finalize의 수락 version parse는 phase finalize에서만 발생한다. mock parse는 이 live 경로가 아니다. 로컬 ffprobe의 json.loads는 이 고정 코드를 생성하지 않는다.

관측된 work/execute 및 역할 JSON parsed 이후에는 기존 FreeCompany._call의 `content.startswith('{') → parse(content)` 경계가 해당 오류와 일치한다. **현재 코드와 저장 전이에 따라 내부 parse 지점으로 좁혀지지만, 과거 stack trace/raw content가 없으므로 실제 예외 스택과 구체적 문법을 직접 확인한 것은 아니다.** 네트워크/모델 연결 실패로 해석하지 않는다.

## 최소 변경

변경 파일: `autonomous_free.py`, `autonomous_gemini35.py`, `tests/test_nested_tool_review.py`, 이 보고서.

기존 코드는 JSON처럼 시작하는 모든 content를 무조건 parse했고 예외가 도구 실패 검토 경계 밖으로 빠졌다. 바깥 역할 JSON은 정상이어도 내부 문자열 하나 때문에 즉시 stopped가 됐다. 새 정책에서는 아래처럼 구분한다.

| 직원 content | 신규 정책 동작 |
|---|---|
| 일반 산문 | 도구 실행 없이 정상 검토 자료 |
| 유효한 JSON 예시/데이터, 루트 tool 없음 | 도구 실행 안 함. 예: example 내부의 tool은 실행 선택자가 아님 |
| 루트 tool이 허용된 caption_video_v1인 객체 | strict 필드·타입·구조·기존 bounds 검증 후 기존 renderer 실행 |
| JSON처럼 시작하지만 파싱 불가 | tool_input_invalid_json / tool_input_parse 실패 자료로 관리자 검토 |
| 허용 도구 선택자는 있으나 구조/형식 오류 | tool_input_invalid_schema / tool_input_validation 실패 자료로 관리자 검토 |
| 도구 배열/도구 이름이 빠진 장면 구조/도구를 담은 실행용 markdown fence | tool_input_ambiguous로 검토. 성공한 산문으로 묵살하지 않음 |
| 알 수 없는 도구 또는 잘못된 tool 선택자 타입 | 기존 tool_not_allowed 안전 차단 |

루트 tool 선택자가 이 프로토콜의 실행 의사 표시다. 같은 모양의 실행 예시를 설명하려면 prose 또는 example 안의 JSON으로 표현하도록 prompt에 명시했다. 앱이 자연어의 모든 예시 의도를 추측하는 것은 아니다. 유효한 JSON/산문이라도 MP4가 필요한 최종 전달에는 기존 실제 artifact/receipt 검증이 별도로 적용된다.

앱은 내부 JSON을 자동 수정하거나 재작성하지 않는다. 기존 renderer의 공백 reflow/자막/음성/물리 검사는 그대로다. 구조 검증은 레이아웃 reflow 전에 수행할 수 있는 기존 `_validate_video(...,False)`를 재사용하고, 실제 실행은 기존 엄격한 schema·도구 allowlist·파일 경계를 통과해야 한다. 일반적인 data/API malformed 오류를 전역 recoverable로 바꾸지 않았다.

## 기존 내부 수정 흐름과 영속 경계

FreeCompany에 내부 tool spec 식별과 고정 진단 분류 훅을 추가하고, 기존 도구 실패 이벤트 저장을 공통 작은 helper로 재사용했다. 기본 동작은 이전과 같다. 새 파싱/형식 검토는 **nested_tool_review=1이 있는 신규 Gemini35 프로젝트에서만** 동작한다.

직원 바깥 역할 JSON은 기존 strict schema로 먼저 검증한다. 내부 입력만 잘못되면 원래 직원 제출물을 기존 저장 정책 안에서 실패 version으로 보존하고 tool_status=failed 및 고정 stage/category/exit_code(null)를 붙인다. 진단에는 raw response·exception 메시지·키·경로·헤더·환경을 추가하지 않는다. 원래 업무 제출물 보존과 디버그용 원문 로그는 구별한다.

이후 기존 ai_employee_result 커밋→awaiting_ai_review→관리자의 revise/stop/운영 권한 결정→revision_requested→새 직원 응답→도구 실행/검토를 따른다. role_result_status=validated는 역할 JSON/검토 자료의 커밋 완료이며 도구 성공이 아니다. active_operation은 정상 커밋 뒤에만 해제하며 기존 API 요청을 재전송하지 않는다. 실패 version의 accept는 계속 차단한다. 수정 task1/total2, 중복·정체·시간·쿼터/미확정 API·동의·비용·보안 경계도 유지했다.

새 동의안에 nested_tool_review 정책(버전1, generated_employee_results_and_manager_reviews 범위, JSON 자동 수선/transport retry 없음)을 명시하고 hash 일치를 검사한다. 기존 실패 프로젝트에는 이 표식을 추가하거나 동의를 다시 서명하지 않았다. 기존 3.1과 이전 3.5 store는 이전 binding/정책 그대로 load되며 신규 정책이 소급 활성화되지 않는다.

## 오프라인 한 사이클 및 안전 회귀

```bash
python -B -m unittest tests.test_nested_tool_review tests.test_autonomous_gemini35 tests.test_autonomous_gemini tests.test_internal_tool_review tests.test_autonomous_groq tests.test_autonomous_free tests.test_autonomous_live
```

**82개 통과, 실패/오류0, exit0 (41.474초).** socket/DNS 차단·가짜 키·임시 store·가상 manager/employee 응답만 사용했다.

- 파싱 불가/잘못된 도구 schema/불명확 장면 요청 각각에서 실패 직원 version→manager review의 수정 지시→직원 새 올바른 입력→실제 로컬 renderer MP4→manager accept→다른 직원 인계→final.md까지 통과했다. 각 시나리오 fake 요청8회, 사용자 중간 업무 승인0, 실제 API0이다.
- 실패 원문이 수정 없이 업무 version에 남고 고정 진단이 관리자에게 전달됨, completed API의 커밋/active_operation 정상 해제, 최종 실행 재요청의 무중복을 확인했다.
- 정상 산문/유효 JSON 예시/데이터가 도구로 해석되지 않음, 알 수 없는 도구의 hard 차단, 새 정책 누락 동의 거부, 관리자 stop/수정 한도 초과를 검증했다.
- 바깥 role JSON 자체가 깨진 경우 기존 invalid_model_json 정지를 유지하며 실패 자료로 수락/커밋하지 않는다. active_operation과 미완결 role validation을 보존하고 내부 도구 실패로 오분류하지 않는다.
- 기존 crash/소진 원장·API429 실패 보존·수정/정체/물리 artifact/파일 안전 경계 및 Gemini3.1/Groq/OpenRouter 회귀도 통과했다.

실제 로컬 media 검사 성공은 오프라인 fixture의 기술 검증이며 실제 Gemini의 업무 판단/영상 품질 성공을 뜻하지 않는다. 가짜 관리자 선택을 production 정책으로 강제하지 않았다. `git diff --check` 통과.

## 기존 기록 보존

기존 data/backups/checkpoints **109개 파일 SHA256 전후 모두 동일**. 실패한 Gemini35 프로젝트의 status/hash/attempt/active_operation/동의/시작 소진 표식과 기존 Gemini3.1/Groq/OpenRouter 기록·키·서명·백업·영상 모두 변경하지 않았다. 기존 사용자 미추적 파일도 보존했다. 진단 스크립트 재실행/소진 표식 초기화/실제 API 접속은 하지 않았다.

## 신규 프로젝트 준비 및 후속 행동 하나

오프라인 검증 뒤 아래 prepare만 실행했다.

```bash
python -B gemini35_first_project.py --store data/gemini35-nested-tool-review-20261104 prepare
```

새 project=`gemini35company-1dc335e5b1324ce690a0e9f19945691d`, ready/enabled=false/attempts=0, grant·서명 키·시작 소진 파일 없음. 기존 결과·동의를 복사하지 않고 같은 비밀 없는 합성 목표 템플릿으로 생성했다. 발행 2026-11-04T15:42:23+09:00, 만료 **2026-11-05T15:42:23+09:00**.

모델 gemini-3.5-flash-lite/고정 generateContent, 비용0/유료 fallback 없음, 기존 Free Tier 정책을 유지한다. 이번에는 계정/청구나 최신 잔여 quota를 온라인 조회하지 않았다. 실제 실행자는 해당 키 프로젝트의 현재 Google AI Studio Free Tier를 확인해야 한다. 전송 범위는 합성 목표·계획/기준·직원 제출물·안전한 내부 도구 오류·관리자 검토/수정·최종 통합이다. 로컬 caption_video_v1와 기존 실행/수정/중복 안전 한도를 유지하며 새 nested 정책을 동의안에 포함했다.

**후속 행동은 새 정책·목표·무료 등급·전송 범위를 검토한 뒤 이 신규 프로젝트 최초 실행에 동의하는 것 하나**다. 동의한 뒤 Codespaces에서 사용할 명령은 다음과 같으며 이번에는 실행하지 않았다.

```bash
python -B gemini35_first_project.py --store data/gemini35-nested-tool-review-20261104 execute --review-hash a9523ae537d581325ba86f0d22fd6ca67ff0480dc80de7c842c38b411f38661d --owner-confirmed --confirm-free-tier
```

이번 변경은 목표 입력 뒤 정상적인 직원 도구 형식 오류를 AI 내부 검토·수정으로 처리할 수 있게 해 실제 최종 산출물까지의 중단 지점을 줄였다. 사용자 업무 중간 결재는 추가하지 않았다. 실제 Gemini 한 사이클/MP4 완주와 서비스 안정성 검증, 기존 수동 프로젝트 승인 부채는 남아 있다.
