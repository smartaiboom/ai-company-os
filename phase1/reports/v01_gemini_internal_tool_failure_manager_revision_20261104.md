# 로컬 도구 실패의 AI 관리자 검토·직원 수정 연결

2026-11-04 KST. `git pull --ff-only`로 1277e0d 반영. 핵심 원칙·AGENTS.md·한국어 규칙·지정 지시서·최근 Gemini 분석/연동 보고서 및 기존 회사 상태 기계/역할 계약/동의/원장/로컬 도구/테스트를 확인했다.

**신규 Gemini 프로젝트에서 로컬 도구 실패→기존 관리자 review→직원 revision→도구 재실행→검토·인계·최종 MP4/보고 흐름을 구현하고 오프라인 검증했다. 실제 AI API 요청 0회, 기존 실패 프로젝트 execute/run/continue/approve 0회다. 실제 Gemini 전체 사이클 성공은 아직 주장하지 않는다.**

## 구현 범위와 상태 전이

기존 Company의 awaiting_ai_review/revision_requested, validate_review, task당/전체 수정 상한과 업무 의존 인계를 재사용했다. 새 상태 기계나 별도 자율복구 엔진은 만들지 않았다.

1. 직원 API 응답과 역할 JSON을 먼저 검증한다. 기존과 같이 durable API 선예약 및 completed/json_parsed가 기록된다.
2. 로컬 도구가 안전하게 분류 가능한 오류로 실패하면 직원 content/evidence/uncertainty를 수정하지 않고 보존한다. API attempt에 local_tool_failure를 별도로 기록하고, 해당 직원 version에 tool_status=failed와 tool_failure를 시스템 메타데이터로 붙인다. MP4 receipt/성공 artifact는 만들지 않는다.
3. 기존 ai_employee_result 커밋으로 실패한 검토 자료를 영속화하고 awaiting_ai_review로 이동한다. 이 커밋의 role_result_status=validated는 **역할 JSON과 검토 자료 저장 완료**이며 media 성공이 아니다. 정상 커밋 이후에만 active_operation을 해제하므로 같은 API 요청을 재송신하지 않는다.
4. 다음 관리자 review는 기존 result 안의 실패 표시와 원래 직원 제출물을 받는다. 관리자가 revise/stop/needs_operational_permission을 실제 모델 출력으로 선택한다. 실패한 도구 version에 대한 accept는 시스템이 failed_tool_cannot_be_accepted로 차단한다.
5. revise면 기존 구체적 feedback을 직원 revision_feedback으로 전달한다. 직원의 새 응답·새 context/operation으로 로컬 도구를 실행한다. 성공한 수정본만 정상 검토 후 수락·후속 직원 인계에 사용한다. 오래된 실패 version은 그대로 남는다.
6. 모든 직원이 수락되고 실제 MP4와 수락된 입력에 결합된 receipt가 있어야 기존 final 검증·파일 무결성 확인·최종 전달로 진행한다.

정상 업무 흐름에 사용자 계획/직원/품질 중간 승인을 추가하지 않았다. 관리자 판단 내용·직원 수정 내용은 production 코드에 사전 작성하지 않았다.

## 파일 변경

- `autonomous_company.py`: 직원 version의 시스템 메타데이터 및 수락 안전 검사 훅 2개 추가. 기본 구현은 no-op이어서 기존 mock/다른 경로의 판단 정책은 바꾸지 않는다.
- `autonomous_free.py`: 분류 가능한 로컬 실패를 기존 이벤트와 실패 검토 자료로 보존하는 최소 처리, failed tool의 수락 차단. 기본 복구 활성화는 false다.
- `autonomous_gemini.py`: 신규 프로젝트에 tool_failure_review=1 표식, 동의안에 버전/허용 오류/기존 수정 상한/전송 범위를 담은 TOOL_REVIEW_POLICY 추가. 정책 hash 일치가 없으면 승인/실행을 차단한다. 기존 프로젝트에는 표식을 소급 추가하지 않는다. Gemini 전용 prompt에 실패 자료 해석과 관리자 결정 책임을 명시했다.
- `tests/test_internal_tool_review.py`: 실패→수정→실제 로컬 MP4/인계/최종 보고 및 정지·안전 경계·crash 검증.
- `tests/test_autonomous_gemini.py`: 기존 중단 동작 회귀는 명시적으로 이전 정책 프로젝트로 생성해 보존했다.
- 이 보고서.

## 안전한 실패 정보와 동의 범위

내부 검토 대상은 caption_overflow, narration_exceeds_scene, 기존 LocalToolError의 고정 stage/category/exit_code뿐이다. 각각 caption_validation/audio_duration_validation 또는 기존 espeak_audio/ffprobe_audio/ffmpeg_segment/ffmpeg_concat/ffprobe_final/ffmpeg_decode 단계를 사용한다. stderr/exception 원문·명령 인자/경로·환경·헤더·키를 넣지 않는다.

원래 직원의 업무 제출물은 기존 generated employee results 저장 정책으로 남기며, 새 실패 메타데이터도 같은 manager review 자료에 포함된다. API raw response 전체나 숨은 thought를 새로 저장하지 않는다. 기존 `_call`의 허용 top-level context와 출력 JSON schema는 유지했다. 확장은 **result 내부의 시스템 생성 실패 메타데이터**뿐이다. role output에 모델이 tool_status를 임의로 추가하는 것은 기존 strict schema가 허용하지 않는다.

새 최초 동의안은 이 처리가 generated_employee_results_and_manager_reviews 범위임을 명시한다. 이전 동의안에 해당 정책을 몰래 추가하거나 기존 서명·프로젝트를 바꾸지 않았다. 일반 OpenRouter/Groq의 기본 복구는 활성화하지 않았으며, 신규 Gemini 표식도 유효한 형식과 서명 계약 검사를 통과해야 한다.

기술 오류를 revise로 자동 결정하지 않는다. 관리자 선택이 stop이면 중단하고 운영 권한 요청이면 기존 needs_operational_permission을 따른다. 보안/파일 경계 위반, tool_not_allowed, 기타 미분류 실패는 내부 수정 대상으로 전환하지 않는다. API 인증/쿼터/429/503/timeout·미확정 전송·동의 만료·비용·속도/시간/수정/정체 제한도 기존 안전 정지 경계를 유지한다. 기존 실패 API attempt를 성공으로 바꾸지 않는다.

도구 재실행은 관리자의 검토와 직원의 새 결과 뒤에만 가능하다. 기존 repeated_employee_result 검사도 유지하므로 같은 내용의 무의미한 반복은 차단된다. subprocess 자동 retry나 API 네트워크 재전송/fallback은 추가하지 않았다.

## 고정 검사와 AI 판단의 구분

시스템은 허용 도구·파일 경계·검증된 실제 MP4/receipt·디코딩과 실행/수정 한도만 강제한다. 업무 계획·기준·자막 내용·수정 지시·미적/의미적 품질 판단은 모델 역할이다. 기존 28자/4줄 및 공백 reflow는 이번에 확대하거나 제거하지 않았다. 이 제약은 현재 renderer의 고정 레이아웃 정책이며 모든 해상도에서 픽셀 단위 미적 적합성을 입증하는 기준은 아니다. 오류가 나면 해당 기술 조건을 관리자에게 보여주고 AI가 내용을 수정하거나 중단하도록 한다. Codex가 자막을 잘라 통과시키지 않는다.

## 오프라인 테스트

초기 Gemini/내부 검토 집중 실행 14개 중 1개 실패가 있었다. accept 차단 fixture가 checks=unmet을 반환해 기존 quality_unverified에서 먼저 막혔다. fixture의 accept checks를 met으로 바꿔 물리적 도구 실패 수락 차단을 직접 검증했다. 실제 accept 정책이나 기존 품질 검사를 느슨하게 하지 않았다.

```bash
python -B -m unittest tests.test_internal_tool_review tests.test_autonomous_gemini tests.test_autonomous_groq tests.test_autonomous_free tests.test_autonomous_live tests.test_local_tool_diagnostics tests.test_caption_reflow
```

최종 집중 회귀 **76개 통과, 실패/오류0, exit0 (33.974초)**. 가짜 manager/employee와 socket/DNS 차단, 임시 store/가짜 키·동의만 사용했다.

- caption_overflow / narration_exceeds_scene / classified local_tool_failed 각각에서 첫 직원 도구 실패→관리자 review의 revise→새 직원 결과→실제 로컬 renderer MP4→관리자 accept→다른 직원에 선행 결과 전달→final.md까지 성공했다. 각 시나리오 fake API 8회, 사용자 업무 승인0, 실제 API0이다. local_tool_failed는 결정적 failure injection이며 과거 실제 실패 원인을 재현했다는 뜻이 아니다.
- 관리자 stop/운영 권한 요청/실패 도구에 대한 부당한 accept, task 수정 한도/전체 수정 한도/반복 실패·품질 정체를 검증했다. 실패 자료를 수락/전달하거나 무한 재시도하지 않는다.
- hard file safety 오류는 관리자 복구로 전환하지 않는다. 관리자 review API 429 실패에서는 직원의 completed/validated와 새 manager failed attempt를 구별해 보존하고 active_operation은 manager 실패 시도에 남긴다. 재개 요청으로 재송신되지 않는다.
- 직원 실패 자료 커밋 전 crash는 completed/json_parsed와 active_operation을 보존하고 재전송을 거부한다. 새 정책 누락 동의안은 승인되지 않는다. 기존 OpenRouter/Groq 및 Gemini 오류/예산·동의/중복 보호 회귀도 통과했다.

깨끗한 실패 자료 커밋 후 checkpoint에서 직원 요청을 반복하지 않고 manager review부터 이어지는 검사를 추가했다.

```bash
python -B -m unittest tests.test_internal_tool_review.InternalToolReviewTests.test_clean_failure_checkpoint_resumes_review_without_employee_replay
```

추가 **1개 통과 (0.719초)**. 커밋 후 awaiting_ai_review/active_operation=null을 확인하고, 명시적 clean checkpoint continue에서 첫 요청이 review임을 검증했다. 전체 fake 호출은 여전히 8회이며 직원 최초 요청을 중복하지 않았다. 이 테스트는 정상 자율 실행 중간에 사용자가 반복 재개해야 한다는 뜻이 아니다.

`git diff --check` 통과. 기존 data/backups/checkpoints **90개 파일 전후 SHA256 모두 동일**. 두 Gemini stopped 프로젝트·API/로컬 실패 원장·동의·시작 소진 표식·서명 키·기존 Groq/OpenRouter 실패/예약·영상/백업을 변경하지 않았다. 기존 사용자 미추적 파일도 보존했다. 테스트/실행 준비 외 실제 업무 데이터 수정0, 실제 API0이다.

## 새 독립 최초 완주 준비와 후속 조치 하나

아래 준비 명령만 실행했다.

```bash
python -B gemini_first_project.py --store data/gemini-internal-tool-review-20261104 prepare
```

새 프로젝트 `geminicompany-c082111e380a4d7098f9cc97b2500025`는 ready/enabled=false/attempts=0, grant/서명 키/시작 소진 파일 없음이다. 새 동의안에 tool_failure_review 정책이 포함돼 있다. 발행 2026-11-04T14:49:00+09:00, 만료 2026-11-05T14:49:00+09:00.

목표는 기존과 같은 비밀 없는 AI 질문 작성법 한국어 자막/로컬 음성 MP4 및 최종 보고다. 모델은 gemini-3.1-flash-lite, endpoint는 고정 Gemini generateContent, 비용 상한0/유료 fallback 없음이다. 외부 전송은 합성 목표·생성 계획/기준·배정·직원 제출물과 안전한 로컬 실패 메타데이터·관리자 검토·최종 통합으로 한정한다. 허용 로컬 도구는 caption_video_v1이다. 기존 task당 수정1/전체 수정2, 1800초 실행 경계·무료 공급자 쿼터·속도 제한을 적용한다. 총/시작당 자의적인 무료 호출 구간 결재는 없다.

현재 프로세스의 GEMINI_API_KEY 존재 bool=true만 확인했다. 사용자 Free Tier 확인 기록을 바탕으로 동의안을 준비했으나 이번에 Google 계정/청구 API를 조회한 것은 아니다. 실제 실행 시 현재 해당 키 프로젝트가 여전히 Free Tier임을 확인해야 한다. 기존 모델 가격 정책을 바꾸거나 새 온라인 접속을 하지 않았다.

**사용자에게 필요한 후속 조치는 새 정책·무료 등급·전송 범위를 검토한 뒤 이 독립 프로젝트의 최초 자율 실행에 동의하는 것 하나**다. 아래 명령은 승인 후의 실행 방법이며 이번에는 실행하지 않았다.

```bash
python -B gemini_first_project.py --store data/gemini-internal-tool-review-20261104 execute --review-hash 3b63157a29c809d1c4016ad57a52993b943329ef188eb4650ca8fb0f232e3051 --owner-confirmed --confirm-free-tier
```

실제 Gemini 계획→직원→실패 시 내부 검토/수정→인계→최종 MP4/보고 완주는 다음 별도 실행으로 검증해야 한다. 두 번째 과거 로컬 실패 원인은 여전히 미확정이며, 새 시스템의 내부 검토 경로가 이를 성공으로 소급 변경하지 않는다. 이번 변경은 사용자의 목표 이후 AI 내부 판단으로 복구할 수 있는 거리를 줄였고, 새 업무 중간 결재를 추가하지 않았다. 기존 수동 프로젝트의 반복 승인 부채와 실제 실사용 완주 검증은 남아 있다.
