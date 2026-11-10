# 실제 관리자 계획1회 인수 준비 결과 — 2026-11-10 KST

## 실제 완료 상태

요청 준비·검토·승인 게이트와 HTTP mock 안전 시험 완료. **실제 AI 요청은 발송하지 않았다. 새 실제 호출0회/비용0원/모델 데이터 전송0회**이며 현재 새 프로젝트는0/1 사용, 계정 증거·서명 승인 없음, 실행 정책 비활성이다. 실제 전략/대본/새 영상 또는 품질 향상을 달성했다고 보고하지 않는다.

- 코드·테스트·사용법 커밋: `f02d305` (`Prepare exact-payload single manager plan acceptance scope`). 시작 기준 main `2c87613`.
- 지정 결과 파일: `reports/real_manager_one_call_prepare_result.md`.
- 사용자 검토: `reports/REAL_MANAGER_CALL_REVIEW.md` — 정확한 모델/endpoint·보호 경로·scope/payload/review 해시·승인 대기 항목.
- 현재 진행: `reports/CURRENT_PROGRESS.md`.
- 전체 정확 payload와 계정/원장은 검토 파일이 가리키는 새 로컬 보호 폴더에만 저장. GitHub에는 올리지 않는다. 이 보고서는 별도 결과 커밋으로 함께 main에 반영한다.

## 구현 및 재사용 경계

1. `core/goal_dialogue_live.py`: 기존 LiveDialogueStore의 payload/context/바이트 생성에 기본 동작이 동일한 확장점 추가. 기존 OneCallAcceptanceStore의 목표/프로젝트/스코프 상수를 클래스 기본값으로 옮겨 새 하위 스코프가 동일한 단일 생성·HMAC·현재 키 결합·Free/Billing 사용자 확인·1시간 만료·정확 요청 승인·선예약·실패/중단 후 소모 로직을 재사용하도록 했다. 기존 인수 값/모드/상태/데이터는 변경하지 않았다.
2. `core/manager_plan_once.py`: 독립 ManagerPlanAcceptanceStore. 기존 일반 dialogue/quality 전송 게이트를 변경하지 않고 별도 `MANAGER_PLAN_EXECUTION_ENABLED=False`를 유지. 새 root에서 singleton 프로젝트 생성. root0700, payload/state/review0600. 현재 키 로컬 대조·무료/Billing/쿼터/공식 문서 사용자 확인을 서명한 증거로 묶고 최종 요청 승인 전에 검사. 정확 scope는 계약/모델/endpoint/plan1회에 묶이며 payload 바이트의 SHA-256도 승인에 결합한다. 계정 확인 후 prepare 재실행이 필요하다.
3. 기존 Gemini35Adapter의 native 요청/헤더·응답 정규화와 기존 send_once의 redirect/proxy/retry 차단을 재사용. 키를 URL/본문/원장에 저장하지 않는다. 새 sender나 provider fallback은 만들지 않았다.
4. `companies/video/manager_plan_acceptance.py`: 가상 목표/고정 데이터 범위와 독립 전략 JSON schema. 모델이 전략 또는 필수 추가 질문과 이유를 선택. 전략에는 대상/한 메시지/3초 후크 기획/시연/60초 이야기·소스 필요량/대본·음성 방향/직원 역할·의존성·완료 기준/불확실성을 포함. 장면60초, 소스 ID/수요 길이, 작업 의존성을 검증한다. source=external_clip_pending/rights=unverified/video=not_created만 허용해 구조적 허위 완료를 거절. 자유 자연어 안의 모든 사실/허위주장을 자동 의미 검증하는 기능은 없으며 실제 전략은 사람 검토 필요.
5. `core/role_json_schema.py`: 기존 strict schema checker에 유한 숫자/정수/boolean과 문자열 길이·배열 개수 범위 검증 추가. boolean을 duration으로 받지 않으며 NaN/Infinity는 기존 strict JSON parser와 검사에서 거절한다.
6. `companies/video/manager_plan_cli.py`: create/prepare/status, secure TTY 비표시 키 대조, 별도 approve/execute 명령. 이번에는 create/prepare만 수행. 키는 GEMINI_API_KEY와 비표시 입력을 비교하며 명령 인수/파일/채팅에 받지 않음. 비TTY 확인은 차단. approve 뒤에도 실행 정책은 열리지 않는다.
7. `tests/test_manager_plan_once.py`:8개 새 안전·계약 테스트. README에 준비 명령과 로컬 자료 보존 설명.

실제 budget은 independent real_ai.limit=1/limits.max_calls=1이며 직원/review/finalize/피드백/제작 요청으로 넘어가는 엔진을 호출하지 않는다. 기존 저장 형식 재사용을 위해 max_rounds=2라는 내부 문답 필드는 남지만, 새 모드는 첫 plan만 허용하고 질문 응답/수정/확정/영상 handoff를 차단하며 두 번째 API는 불가하다. 관리자가 질문을 반환해도 그 질문을 다시 모델에 보내는 권한은 없다.

## 실제 준비된 파일과 현재 차단

새 로컬 저장소 `/tmp/ai_company_manager_plan_20261110_2c87613`, 새 ID `dialogue-ae1e87db8bab4615b2af6806c1c00bc6`, mode=`video_manager_plan_once_20261110_v1`. 과거 `dialogue-f4eb...` 원장/키·승인을 재사용하지 않았다. 같은 Google 프로젝트 기본 라벨은 과거 승인 재사용을 뜻하지 않으며 현재 키/계정 대조가 별도로 필요하다.

전체 정확 request bytes 파일과 JSON schema, system/user를 포함한 검토 파일·해시는 `REAL_MANAGER_CALL_REVIEW.md` 참조. 생성 후 파일 hash와 실제 mock transport request.data의 완전 일치를 검증했다. 최초 검토는 계정 미확인 제안이며1시간 만료. 계정 증거를 추가하면 상태/서명/검토 해시가 달라지므로 현재 검토 해시를 최종 승인에 재사용할 수 없다.

현재 없음: 계정 증거·키 대조·무료/Billing/쿼터 확인·Google 무료 데이터 정책 동의·최종 개별 실행 승인·정책 활성화·실제 요청/응답. 현재 공개 근거는 공식 사이트 검색 발췌이고, 계정 내부 Billing/쿼터를 조회한 것은 아니다. 공식 문서 직접 열기는 도구의 text/markdown 처리 오류가 있었으며 세부 한계와 링크는 검토 파일에 기록했다. 계정/요금/지원이 불확실하면 보류한다.

## 단일 묶음 통합 검증

실행:
`env -u AI_CLIP_ACCEPTANCE_ROOT PYTHONPATH=core:companies/video MANAGER_PLAN_SAMPLE_OUTPUT=/tmp/real_manager_prepare_20261110/mock_sample.json python -B -m unittest discover -s tests -v`

**45개 발견,44통과/1skip/실패0/오류0 (16.915초)**. 전체 통합1회만 실행했으며 실패가 없어 반복하지 않았다. skip은 기존 실제 MeloTTS+60초 영상 인수 시험. 로그 `/tmp/real_manager_prepare_20261110/integration.log`, 모의 전략 응답·전략 평가표 샘플 `/tmp/real_manager_prepare_20261110/mock_sample.json`. 새 테스트는 소켓·DNS 차단 상태에서 `goal_dialogue_live.send_once`만 mock했다. 과거 단일 인수·일반 live/quality 모드·회귀도 함께 통과했다.

확인 사항:
- 정확 schema/system/user/request bytes hash와 폴더/파일 권한, 새 저장소 단일 프로젝트, mode 혼합 차단.
- 키/환경변수/서명 승인만으로는 실제 전송 차단. 계정/쿼터/문서 확인 누락, 키 불일치·변경, 승인 이전 입력 변경, 만료, 서명 변조 차단.
- 성공1회 후 재호출 불가. 필수 질문 반환도1회 소모. 직원/수정/추가 문답/영상 handoff 없음.
- timeout/429/503/잘못된 JSON은 uncertain, 인터럽트는 reserved로 보존. 다음 호출/재시도 차단하고 실패 응답 원문·임의 예외 문자열을 기록하지 않음.
- 구조적으로 권리 확인/소스 확보/영상 생성 완료를 주장하거나 timeline/소스 길이/의존성/schema가 잘못되면 수용 거절. 모델 답변이 거절되어도1회 소모.
- strategy_review는 별도7항목 모두 human_pending/unassessed. 영상10점 점수와 구분하며 mock 응답을 실제 모델 품질 평가로 승격하지 않음.

## 보존 및 다음 확인

`data/`, `backups/`, `artifacts/`, `.env` 중 존재하는 일반 파일45,349개를 개발 전후 SHA-256과 파일 목록으로 대조해 전부 일치(변경/추가/삭제0). 로컬 근거 `/tmp/real_manager_prepare_20261110/before.json`, `preservation.json`. 검사는 읽기 전용이며 새 준비/테스트 쓰기는 새 /tmp 경로만 사용. 기존 Flow 입력/MP4/TTS/동의/서명/비용/시도 원장/미확정 상태 불변, 외부 아카이브 미접근, reset/clean/삭제 없음. 기존 미추적 로그/JSON7개는 커밋하지 않는다. 해시 원장·원 payload·계정/키·미디어도 커밋하지 않는다.

다음은 사용자 현재 Free/Billing/쿼터/키 대조→정확 요청 재검토→Google 무료 입력 데이터 처리 동의→plan1회 개별 승인이다. 현재 사용자 계정 확인 화면을 보았다고 주장하지 않는다. 계정 확인·동의 이전에 execute를 실행하거나 정책 상수를 켜지 않는다. 검토 파일의 순서로 별도 승인한 뒤 좁은 실행 활성화를 검토해야 한다.

최소 실제 실행 명령 형태(**이번에는 실행하지 말 것; 현재 코드 정책에서도 차단됨**):

```bash
PYTHONPATH=core:companies/video python -B -m manager_plan_cli --root /tmp/ai_company_manager_plan_20261110_2c87613 execute dialogue-ae1e87db8bab4615b2af6806c1c00bc6
```

키는 명령에 넣지 않는다. secure TTY의 verify-key와 정확 새 review_hash의 approve가 먼저 필요하지만, 이번 작업은 이를 수행하지 않았다. 공식 정보·계정 증거·검토 해시가 만료/변경되면 재검토하며, 불확실한 호출을 새 저장소로 우회 재실행하지 않는다. 이번에는 승인1회도 소모하지 않았고 실제 요청0/1을 유지한다.

실제 모델의 전략 유용성/직원 역량 향상, 감각 품질, 새 실제 영상, 최종 게시 합격은 미검증/미완료다. GUI/웹 서버/TTS 업그레이드는 만들지 않았다. 다음 가장 작은 판단은 별도 승인된 관리자1회 응답을 전략 평가표로 검토하는 것이며 추가 직원/영상 제작은 별도 범위다.
