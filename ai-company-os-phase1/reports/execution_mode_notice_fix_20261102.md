# 실행 모드 및 외부 전송 안내 수정 결과

작성 시점: 2026-11-02 10:54 KST
기준 커밋: `02ef0c9` (main/origin/main에서 fast-forward pull 후 착수)

## 변경 내용

- `app.py`: 프로젝트 상세 화면의 고정된 '모의 관리자/외부 호출 없음' 설명을 현재 실행 엔진별 안내로 교체했다. mock은 '외부 AI 요청 없음', 실제 모드와 `openai-compatible` 별칭은 허용 모델 `openrouter/free`, 목표·업무 입력·선행 결과의 외부 전송 가능성, 모델 설정 오류 시 요청 전 중단을 안내한다. 미지원 모드는 설정 오류와 외부 요청 차단을 안내한다. 설정값 자체나 키를 화면에 삽입하지 않는다.
- `README.md`: 모의 모드에 한정된 무호출 설명, 실제 요청 시점과 전송 자료, OpenRouter 기본 주소, 유일한 허용 모델 및 fallback 없음 설명을 현재 구현에 맞췄다.
- `tests/test_project_ui.py`: 임시 프로젝트 저장 경로에서 mock/실제/별칭/미지원 모드 화면을 검증하는 테스트를 추가했다. 네트워크 함수를 mock하여 조회 시 무호출을 확인하고 테스트용 인증 값과 잘못된 모델 값이 화면에 노출되지 않음을 검사한다.
- `codex_tasks/task_history.md`: 완료 이력과 보고서 링크를 추가했다.
- `reports/execution_mode_notice_fix_20261102.md`: 이 보고서 신규 작성.

기존 실행 엔진·계획기의 모델 검사 및 오류 동작은 그대로 유지했다. 실행 방식이나 데이터 구조 변경, 유료 모델·fallback 추가, 의존성 설치는 없다. 기존 사용자 데이터·백업·미추적 파일은 수정·삭제·스테이징하지 않는다.

## 실행한 검증

```text
python -B -m unittest tests.test_project_ui tests.test_execution_engine tests.test_manager_plan tests.test_manager_plan_persistence
```

결과: 41개 통과 (OK). 신규 화면 테스트 1개 안에서 4가지 모드를 검사했다. 실제 엔진과 계획기의 비무료/누락 모델 요청 전 차단 및 모의 응답 테스트도 포함한다.

```text
python -B -m unittest tests.test_explicit_workflow_links tests.test_task_execution_persistence tests.test_company_workflow_e2e tests.test_quality_review_flow tests.test_downstream_review tests.test_review_approval_gate
```

결과: 18개 통과 (OK). 결과 전달·실패 보존·수정 요청·재승인·최종 보고의 기존 동작을 확인했다. 실행한 테스트의 저장은 임시 경로이며 API는 모의 처리했다. 두 명령 합계 59개 통과.

`git diff --check`: 통과. 보고서 저장 후 다시 읽어 변경 범위와 검증 기록을 확인했다. 커밋 전 staged diff도 확인한다.

## 제한 및 API 여부

- 실제 AI API 호출: 없음. 비밀 설정 파일 및 실제 인증 값 조회·출력 없음.
- 실제 제공자 연결과 브라우저 화면을 이번에 실행하지 않았다. HTML 렌더링을 직접 검사했다.
- HTTP·브라우저 테스트는 이번 변경에서 재실행하지 않았다. `tests/test_smoke.py`는 실제 저장 경로 격리가 보장되지 않아 실행하지 않았다. 과거 전체 60개 통과 기록과 이번 59개 실행 결과를 구분한다.
- 미해결 테스트 실패나 충돌 없음. 잘못된 실제 모델 설정은 화면 조회 자체를 차단하지 않고 허용 모델과 중단 정책을 안내하며, 계획 작성/업무 실행 요청 시 기존 검사가 거절한다.
- 관련 파일만 선택적으로 커밋·푸시하고 원격 main 커밋 일치를 확인한다. 최종 SHA는 완료 응답에서 제공한다.
