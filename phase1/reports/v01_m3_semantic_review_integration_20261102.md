# v0.1 M3 — 의미 검토·사용자 승인 수정·재검토 통합

작성: 2026-11-02 13:47 KST. 시작 기준: `540ff69a83f832c113462566136cab552f9607f6` (git pull --ff-only 후 main/origin/main 일치).

**M3 구현 및 모의 통합 검증 완료. 실제 AI API 호출 0회.** 실제 모델의 품질·가용성을 실증하거나 v0.1 전체 인수를 완료한 것은 아니다. 실제 동의 부여/서버 활성화/실제 비밀 키 조회 없이 테스트 가상 동의와 전송 fixture만 사용했다.

## 구현과 기존 재사용

- 신규 `semantic_review.py`: 의미 검토 전용 JSON 계약. schema_version, 대상 업무 ID·최신 result_revision·결과 해시·입력 맥락 해시·정책/검토 담당 지문·사용자 기준 지문을 대조한다. 기준별 criterion/status/evidence/risk/suggestion/source와 pass/changes_needed/inconclusive를 엄격히 검증한다. 초과/누락 필드, 빈 근거, 잘못된 판정, 판정과 근거 불일치, 오래된 지문, 중복 JSON 키, 잘린 응답·reasoning만 있는 응답은 통과시키지 않는다. unknown은 inconclusive, unmet은 changes_needed, 전부 met일 때만 pass다.
- 모든 근거의 source는 `model_claim`이다. 독립적으로 사실 확인하는 기능은 없으며 검토 JSON·화면에서 모델의 관찰을 확인된 사실로 승격하지 않는다. 기존 quality_review.py의 mock 제목 형식 검사는 수정 없이 별도 유지했다.
- `app.py`: 승인된 계획의 품질 업무 실행 전에 대상 ID·검토 담당 ID·성공 기준을 사용자가 명시적으로 승인한다. 기준은 중복 없이 1~8개, 각각 500자 이내. 의미 검토는 대상 바로 다음의 `품질 검토 담당` 업무 실행이며 별도 최종 업무가 필요하다. 기존 실행기·선행 승인·결과 버전·실패 보존·프로젝트 잠금·HTTP 오류 처리를 재사용한다. 일반 업무 실행/자동 진행으로 품질 전용 경로를 우회할 수 없다.
- changes_needed는 승인된 대상을 자동 수정하거나 승인 취소하지 않는다. UI에 대상 ID·기존 승인/시각·근거/위험/제안·남은 API 예산을 표시한다. 정확한 최신 binding_hash를 제출한 별도 사용자 ‘수정 요청 승인’ 뒤에만 기존 changes_requested·review_feedback·후속 무효화 경로를 적용한다. 이전 승인과 원문도 별도 revision 기록에 보존한다. 거절은 기존 대상 결과·승인에 손대지 않고 추가 수정을 차단한다.
- 수정 실행은 같은 담당 업무의 기존 execute_project_task/실제 엔진 경로를 사용한다. 프로젝트당 대상 하나·수정 한 번이며 실행 전 예약한다. 새 결과는 pending으로 저장하고 사용자 재승인 뒤 같은 품질 업무가 최신 revision으로 한 번 재검토한다. 오류·판정 불가·개선 없음은 멈추고 자동 반복하지 않는다. 기존 quality_revision_once mock 예약을 삭제하거나 실제 실행 권한으로 전용하지 않는다.
- M2 `ai_safety.request_json`, 전송 직전 무료 모델/정확한 HTTPS 주소/동의/크기 검사와 영속 시도 예약·최대 7회·요청당 2회를 그대로 사용한다. 의미 검토도 kind=semantic_review로 같은 예산에 포함한다. 수정 승인에는 최소 수정+재검토 2회 잔여 예산이 필요하다. 승인 화면은 실제 외부 전송 동의나 서버 활성화를 새로 만들지 않는다.
- `execution_engine.py`, `manager_plan.py`: 사용자 목표와 역할·승인 기준·선행 결과에 집중하도록 프롬프트를 정리했다. 제품 기획을 무관한 AI Company OS 개발로 강제하던 문구를 제거했다. 검색·도구·코드 실행 기능은 추가하지 않았다. 제품을 재고 도메인으로 고정하지 않았다.
- 최종 승인/후속 실행은 최신 의미 pass와 기존 사용자 승인 경계가 필요하다. 성공 기준·검토 결과를 최종 근거에 포함하고 기존 불변 보관 및 맥락 검증을 재사용한다. 의미 설정이 없는 구형 프로젝트의 근거 형식은 유지한다. 입력 맥락 해시에서 의미 출력 자체를 제외해 순환 지문을 방지하며 기준은 별도 지문으로 검사한다.
- 지시서의 JSON·Markdown 다운로드 검증을 위해 기존 검증된 다운로드 핸들러에 JSON 형식을 추가했다. 둘 다 동일 load_confirmed_snapshot과 현재 유효한 버전·경로·해시·승인 검증을 거쳐 attachment로 응답한다. GET 쓰기 없음, 과거 보관본 덮어쓰기 없음.

변경 파일 **8개**: `app.py`, `execution_engine.py`, `manager_plan.py`, 신규 `semantic_review.py`, 신규 `tests/test_semantic_review_integration.py`, `README.md`, `codex_tasks/task_history.md`, 이 보고서. M2 안전 모듈·mock 검사/수정 모듈과 기존 테스트 파일은 변경하지 않았다.

## 단일 종단 시나리오와 예산

신규 테스트의 소켓 없는 핸들러와 실제 loopback HTTP 양쪽에서 같은 시나리오를 검증했다. 저장은 TemporaryDirectory의 프로젝트/아티팩트만 사용한다. 제공자 응답은 고정 fixture이며 ai_safety.build_opener는 실패 mock이다. 테스트 환경 변수는 clear=True와 가짜 키로 구성해 실제 키를 읽지 않는다.

1. 일반 목표 ‘소규모 매장 재고 업무 개선 제안’ → 실제 계획 경로의 가상 응답 → 4단계 사용자 승인 → 명시적 재고 성공 기준 승인.
2. TASK-001 요구사항 및 TASK-002 초안을 실제 실행 경로/가상 전송으로 처리하고 사용자가 각각 승인한다. 선행 결과 전달과 목표·기준·역할이 담긴 요청을 확인한다.
3. TASK-003 품질 담당이 TASK-002 최신 지문에 changes_needed를 반환한다. 대상 승인과 원문이 그대로임을 확인한다.
4. 사용자 수정 요청 승인으로 TASK-002만 changes_requested가 되고 의견이 같은 콘텐츠 제작 담당에게 전달된다. 정확히 한 번 실행한 새 결과 revision=2는 pending이며 재승인 전 재검토가 거절된다.
5. 사용자 재승인 후 같은 TASK-003이 revision=2를 pass로 재검토한다. TASK-003 사용자 승인 후 TASK-004 최종 보고를 실행하고 별도 최종 사용자 승인으로 JSON을 보관한다.
6. JSON·Markdown attachment GET이 동일 보관본과 일치한다. GET 전후 프로젝트 바이트 동일, 잘못된 버전은 거절, 중복 수정·재검토·기준 덮어쓰기 거절 후 기존 보관 바이트가 유지된다. 기존 mock reserved 기록도 그대로 남는다.

호출 기록은 정확히 **plan → task → task → semantic_review → task(수정) → semantic_review(재검토) → task(최종)**, 총 **7회**다. 의미 검토를 추가 별도 직원 호출로 만들지 않고 기존 품질 역할 실행에 연결하여 예산을 지켰다. 테스트의 결과 개선과 pass는 공급한 fixture의 주장이지 실제 모델 성능 증거가 아니다.

## 직접 실행한 테스트와 결과

```text
python -B -m unittest tests.test_real_ai_safety_budget tests.test_execution_engine tests.test_manager_plan tests.test_final_report_approval tests.test_quality_revision_once
```

초기 구현 후 기존 관련 **65개 통과**.

```text
python -B -m unittest tests.test_semantic_review_integration
python -B -m unittest tests.test_semantic_review_integration.SemanticIntegrationTests
```

초기 실행은 샌드박스 loopback 소켓 권한 오류와 테스트 계획 fixture 첫 단계의 필수 input_task_ids 누락으로 실패했다. loopback 허용 실행으로 전환하고 fixture에 빈 배열을 추가했다. 소켓 없는 7개 통과, 실패/재검토 보강 후 양쪽 경로 합계 **18개 통과**. 실제 전송을 허용해 고치지 않았다.

```text
python -B -m unittest tests.test_semantic_review_integration tests.test_real_ai_safety_budget tests.test_quality_revision_once tests.test_final_report_approval tests.test_execution_engine tests.test_manager_plan
```

최종 집중 **83개 통과**. 신규 18개는 양쪽 경로에서 pass/changes_needed/inconclusive, 엄격한 계약·stale 결과/기준/역할, 사용자 거절·승인 우회, 재시도 차단·동의/예산 부족·409 경합, 타임아웃·빈 응답·reasoning-only·예약 저장 실패, 기존 원문/버전·mock 예약 보존을 확인한다. M2 기존 테스트로 모델·호스트·크기·7회/요청당 2회·디스크 예약·재시작 차단도 회귀 확인했다.

```text
python -B -m unittest tests.test_semantic_review_integration.SemanticHTTPTests.test_goal_to_seven_calls_final_json_markdown_and_preserved_archive tests.test_v01_m1_end_to_end
```

JSON 다운로드 추가 후 M3/M1 다운로드 관련 **7개 통과**.

```text
python -B -m unittest discover -s tests
```

최종 전체 안전 회귀 **1회 실행**, 종료 코드 0: **Ran 156 tests in 23.225s, OK (skipped=1)** → **155개 통과, Playwright 부재의 기존 브라우저 1개 건너뜀**. 구형 JSON·M1 승인/다운로드·mock 품질 수정·기존 동시성/무료 모델 보호 포함. 실제 경로가 격리되지 않은 함수형 smoke 테스트는 별도 실행하지 않았다. 미해결 실패·충돌 없음. `git diff --check` 통과.

## 한계와 M4 인계

- M3는 구현 및 모의 전송 통합 완료다. 실제 모델의 JSON 준수율·근거 적절성·의미 개선, OpenRouter 무료 라우팅/계정 가용성, 브라우저 클릭·모달·다운로드 저장은 미검증이다. M4 별도 실제 호출 승인 전에는 활성화하거나 호출하지 않는다.
- 의미 검토 설정은 한 번이며 대상 바로 다음 품질 역할 및 별도 최종 역할이라는 좁은 구조를 지원한다. 기준/대상 재설정·다중 대상 수정·추가 반복·예약 해제·예산 증액 UI는 없다. 기존 프로젝트를 자동 마이그레이션하지 않는다. 더 긴 계획/추가 수동 호출은 7회 예산을 먼저 소모하므로 임의의 모든 계획이 수정 포함 완주한다고 보장하지 않는다.
- 성공 기준 승인과 수정 요청 승인은 외부 전송 동의가 아니다. 실제 모델과 공유할 목표·입력·기준·선행 결과·피드백을 구체적으로 제시하고 M4 승인을 별도로 받아야 한다. 신뢰된 단일 프로세스·최신 JSON·앱 잠금이라는 M2 한계도 유지한다. 사용자 인증/CSRF/다중 서버/임의 파일 변조 방어를 새로 구현한 것은 아니다.
- 예약 후 중단·저장 오류에서는 실행 여부가 불명확해 기회를 소비하고 보수적으로 차단할 수 있다. API 수신 완료와 계약/의미 성공은 다르다. 성공한 원문을 보존하더라도 업무 상태는 실패/재검토 필요로 남을 수 있으며 자동 복구·재전송하지 않는다.
- 명확한 기준의 pass도 모델 주장이다. 독립 사실 확인, 외부 조사, 도구 실행은 없으며 최종 사용자 승인도 별도다. 실제 결과 품질과 웹 사용성 인수 후에만 v0.1 완료를 판단한다.

실제 OpenRouter/OpenAI 요청 **0회**, 실제 키 조회/출력 **없음**, 유료 모델·결제·외부 의존성 설치 **없음**. 기존 업무 JSON·스냅샷·백업·추적/미추적 파일은 보존하고 이번 Git 변경에서 제외한다. 보고서 저장 후 재독하고 관련 8개 파일만 선택적으로 커밋·푸시한 뒤 원격 SHA와 보고서 존재를 확인한다.
