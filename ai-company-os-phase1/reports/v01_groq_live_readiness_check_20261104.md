# Groq 실사용 직전 읽기 전용 준비 점검

점검 시각: 2026-11-04T11:19:13+09:00 KST. `git pull --ff-only` 성공, main `15914a1` 반영. 핵심 원칙·AGENTS.md·한국어 규칙·지정 선행 보고서 3개 및 Groq adapter/동의/CLI/원장 보호 코드를 확인했다. 기존 사용자 미추적 파일은 작업 범위와 겹치지 않았으며 변경하거나 스테이징하지 않았다.

**결론: GROQ_API_KEY는 현재 환경에 존재한다. 무료 계정 조건은 미확인으로, 아직 실사용 승인 가능한 상태가 아니다. 실제 Groq/OpenRouter/Gemini AI API 호출 0회, 실제 approve/run/continue 0회, 새 동의안 발행 0건, 유료 사용 0건이다.** 키 값·길이·접두어·해시를 출력하거나 기록하지 않았다. 기존 AI_API_KEY와 설정 파일도 변경하지 않았다.

## 프로젝트와 기존 초안

- store: `data/groq-video-smoke-20261104` (전용 marker 확인).
- ID: `groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e`.
- 목표 hash: `3cf69cc191d65718ef1571671a3f85940676d3c8da7992f7d1760eec45bbb5c9`.
- 현재 상태 hash: `25d3e5d7c3666acac578d278aab63f00848716f904a4cb1dbe7f22dcc495db5f`.
- 상태 `ready/plan`, attempted 0, enabled=false, consent 비어 있음, grant·실사용 서명 키 없음. plan/active_operation 없음, session/event 0건. 예기치 않은 승인·송신 흔적 없음.
- 기존 `operating-proposal.json`의 목표/초기 상태 hash가 현재 프로젝트와 일치한다. 현재 계약 필드·provider/model/endpoint·scope·도구·비용 정책·limits/rules·유효기간을 로컬 검증했다. 계정 확인값은 false/null인 기존 미승인 상태다.
- 계정 검증을 제외한 계약 검사는 통과했고, 전체 `GroqStore._check_contract`는 예상대로 `groq_free_account_unverified`를 반환했다. 승인 또는 서명을 수행하지 않았다.
- 기존 초안 만료: `2026-11-11T10:32:43+09:00` KST. 이는 계정 미확인 초안의 만료이며 실행 동의를 뜻하지 않는다.

공급자는 `groq`, 모델은 `openai/gpt-oss-20b`만 허용한다. 계약의 base URL은 `https://api.groq.com/openai/v1`, 실제 adapter의 고정 POST URL은 `https://api.groq.com/openai/v1/chat/completions`다. 기존 OpenRouter 키/동의 재사용이나 공급자·유료 fallback은 없다.

외부 송신 범위는 이 프로젝트 목표와 생성 계획·품질 기준·업무 배정·직원 결과·관리자 검토·최종 통합 텍스트(대본/자막/장면, 선행 결과와 수정 피드백 포함), 로컬 렌더 메타데이터다. 기존 파일/코드 본문/영상·음성 원본/계정 정보/비밀키를 모델 메시지로 전송하지 않는다. 로컬 도구는 `caption_video_v1`로 제한되며 FFmpeg/선택적 한국어 eSpeak 합성, 네트워크·업로드 없음이다. 무료 총/시작당 인위적 호출 상한 없음, 최대 업무 8개·30분·수정/품질 정체/중복/실패 보호를 유지한다.

## 필요한 사용자 확인과 다음 단계

사용자가 [Groq Console](https://console.groq.com/)에서 **Free plan, 결제·과금 비활성, `openai/gpt-oss-20b` 사용 가능**을 직접 확인했다는 명시적 전달이 아직 없다. 키 존재는 이 세 조건이나 API 연결 성공을 증명하지 않는다. 이번에는 계정 로그인·공급자 조회·연결 진단을 하지 않았고, `--confirm-groq-free-account`를 사용하지 않았다. 필요한 사용자 확인은 이 세 계정 조건에 대한 확인 한 가지다.

그 확인을 전달받은 뒤에만, 같은 프로젝트의 기존 초안을 별도 로컬 안전 위치에 백업·보존하고 아래 prepare를 수행한다. 아래 명령은 **이번에 실행하지 않았으며**, 출력 경로는 존재하지 않는 새 이름이어야 한다(CLI는 기존 파일 덮어쓰기를 거부한다).

```bash
python -B -m autonomous_live_cli --store data/groq-video-smoke-20261104 prepare groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e --confirm-groq-free-account --proposal-out /tmp/groq-account-reviewed-proposal-20261104-next.json
```

이후 실제 발행된 제안의 review hash·최신 목표/상태 hash·전송/로컬 도구 범위·만료 KST를 확인하고 최초 프로젝트 운영 동의를 별도로 받아야 한다. 이번에는 새 계약을 발행하지 않았으므로 실전 승인용 review hash를 제시하지 않는다. 계정 확인만으로 실행이 승인되는 것은 아니다. 업무 내용·계획·직원 결과에 대한 반복 중간 승인은 요구하지 않는다.

## 검증과 보존

읽기 전용 Python 점검으로 환경변수 존재 여부, `GroqStore.load`의 저장 hash/namespace, 기존 초안과 현재 계약의 일치, 계정 미확인 차단, 기존 실패 원장 상태를 확인했다. 공급자 네트워크 호출을 하는 함수는 실행하지 않았다.

실행한 최소 오프라인 테스트 명령:

```bash
python -B -m unittest tests.test_autonomous_groq.GroqTests.test_unverified_account_prepare_no_side_effects_and_no_send tests.test_autonomous_groq.GroqTests.test_contract_provider_model_scope_schema_cost_and_key_guards tests.test_autonomous_groq.GroqTests.test_cli_draft_dispatch_and_provider_switch_block
```

결과: **3개 통과, 실패/오류 0, exit 0** (0.045초). 임시 store·합성 키/동의·외부 socket/DNS 차단 테스트이며 실제 계정 확인이나 실제 AI 성공이 아니다. 제품 코드 변경이 없어 전체 회귀나 영상 생성 테스트는 반복하지 않았다.

- 데이터/백업/프로젝트 파일 총 **67개**를 실행 전후 SHA256 및 파일 목록으로 비교: 변경·추가·삭제 0건. Groq 프로젝트/기존 초안, 실제 서명 키·승인, 기존 mock MP4도 보존했다.
- OpenRouter `freecompany-ae4aa334511d470c8c517685e9902a53`: stopped/plan, attempted 1, unvalidated/active_operation 보존. 상태 hash `f28ebea41f84d1f08917acab1f6ae1e1c548a164e482710273828b7e5936e7b1` 유지.
- `cb44b605b498`: attempted 9/20, reserved 0. `c85d9853906a`: attempted 1/7, reserved 1 유지.
- `git diff --check` 통과. 변경 파일은 이 보고서 하나다. 원본 proposal·계정 자료·로컬 데이터·키·검증용 /tmp 파일은 Git에 포함하지 않는다.

이번 점검은 목표 입력→실제 AI 자율 협업→최종 산출물에 앞서 필요한 공급자/계약 안전 상태와 차단 요인을 분명히 했다. 실제 AI 협업·MP4 제작 한 사이클은 실행하지 않았으며 성공으로 주장하지 않는다. 새 업무별 중간 승인 단계는 추가하지 않았다. 기존 수동 프로젝트의 반복 승인 부채와 기존 OpenRouter 실패 복구는 남아 있고, 이번 범위에서 변경하지 않았다. 현재 필요한 계정 조건 확인 및 최초 전송·실행 동의는 운영 안전 경계다.
