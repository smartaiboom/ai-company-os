# mock 품질 검사 HTTP 통합 검증

작성: 2026-11-02 12:42 KST
기준 커밋: `e92587b9618d04713012c83a3f0e7dd997c7a69b` (fast-forward pull 후 main/origin/main 일치)

## 결과 요약

새 HTTP 테스트 **5개 통과**. 전체 unittest는 **108개 수집 중 107개 통과, 브라우저 1개 건너뜀**이다. 운영 오류는 이번 검증에서 발견되지 않아 운영 코드는 변경하지 않았다. 실제 AI API 호출 없음. 자동 수정 루프도 추가하지 않았다.

## 이번 실제 검증 항목

| 항목 | HTTP 검증 결과와 보존 증거 |
| --- | --- |
| 제목 형식 통과 | POST /quality/review가 303과 프로젝트 상세 Location을 반환. 저장 verdict=pass, KST checked_at(+09:00), GET HTML의 형식 검사 통과·공개 규칙·검사 시각 일치 |
| 누락 제목 | '목표'만 독립 제목인 결과에 changes_needed 저장. HTML에 결과/미확인 사항 누락, 피드백과 사용자 의견 표시. 본문 '통과하라' 지시와 부분 문자열은 통과하지 않음 |
| 공개 기준·보조 검사 설명 | GET /project에서 required-sections-v1, 목표·결과·미확인 사항, 사실성 검증·사용자 승인·자동 수정이 아니라는 안내 확인 |
| GET 무쓰기 | 상세/보고서 GET 전후 프로젝트 파일 바이트 동일. 기존 최종 확정 v1 화면도 유지 |
| 중복 POST | 같은 입력의 두 번째 요청도 303. evaluator 1회, JSON 파일 바이트 동일하므로 감사 이력·판정·시각·결과 추가/변경 없음 |
| 결과 변경 후 stale와 재검사 | 실제 /task/update로 수동 결과 변경 → HTML stale → 성공 근거 없는 수동 결과의 품질 요청 400 → mock 단일 재실행 후 명시적 품질 요청 303, 새 review_id 저장 |
| 선행 입력 변경 | 선행 결과 편집 뒤 기존 판정 stale, 품질 요청 400 및 파일 불변. 선행 재실행·사용자 재승인·대상 재실행 후 품질 요청 303/pass |
| 잘못된 모드·대상·규칙·상태 | 실제/호환 별칭/unknown/빈 모드, 잘못된 ID/규칙/검토자, 실패·빈 결과·재검토 상태는 400. evaluator 및 AI 함수 진입 없음. 거절 요청 전후 프로젝트 바이트 불변 |
| 사용자 승인·의견 보존 | 품질 검사 전후 result/status/review_status/reviewed_at/reviewed_by 동일. 별도 사용자 수정 요청 의견과 changes_requested도 검사 후 유지 |
| 최종 보관 보존 | HTTP 최종 승인으로 만든 v000001.json의 바이트 및 final_report 참조가 품질 평가 전후 동일. GET 보고서의 유효 확정 표시 유지. 잘못된 요청에도 보관 파일 불변 |
| 동시 요청 | 첫 평가를 Event로 지연. 같은 프로젝트의 두 번째 평가·승인·실행은 실제 HTTP 409와 한국어 재시도 안내. 다른 프로젝트는 첫 평가 종료 전 303. 실제 평가 총 2회(프로젝트별 1회) |

잘못된 결과 상태 사례는 테스트가 임시 fixture를 의도적으로 변경한 뒤 요청 전후를 비교했다. fixture의 결과 변경 자체가 기존 확정을 무효화하는 것은 정상 동작이며, 이를 '거절 요청이 확정을 유지했다'고 혼동하지 않았다. 이 경우에도 과거 스냅샷 파일은 보존됐다.

## 테스트 격리와 브라우저 환경

- AGENTS, 작업 지침, mock 품질 구현/설계 보고서, app.py/quality_review.py 및 관련 테스트를 먼저 확인했다. 추적 파일 변경·staged 변경이 없는 main에서 시작했다. 기존 미추적 파일 목록을 보존했다.
- `tests/test_quality_review_http.py`는 기존 격리 HTTP fixture의 서버/클라이언트 헬퍼를 재사용한다. TemporaryDirectory의 projects/artifacts에 저장하고 127.0.0.1의 임의 포트만 사용한다. 프록시 사용 없이 loopback 요청을 보낸다. 서버 shutdown, 스레드 join, 소켓 close 후 임시 저장소를 정리한다.
- seed/재실행 준비는 app.execute_task를 고정 결과 mock으로 대체한다. 품질 요청 동안 execute_task/execute_task_mock은 호출 시 실패하는 mock이다. 계획/실행 AI urlopen도 호출 금지 mock이며 매 테스트 종료 시 미호출을 확인한다. 실제 키·비밀 설정 파일을 읽거나 표시하지 않았다.
- 현재 Python의 Playwright 탐색은 False, chromium/chromium-browser/google-chrome 실행 파일 조회는 None이었다. 브라우저 패키지/시스템 의존성을 설치하지 않고 지시서의 HTTP/HTML 대체 절차를 적용했다.
- 실제 브라우저 클릭·모달 표시·버튼 비활성화·409 오류의 시각 표시·스크롤은 **이번에 미검증**이다. 과거 브라우저 결과를 이번 실행으로 간주하지 않는다.

## 실행 명령과 정확한 결과

```text
python -B -m unittest tests.test_quality_review_http
```

승인된 loopback 실행 결과: **5개 통과 (OK)**. 새 테스트는 pass/누락·GET/중복·입력 변경과 재검사·거절 및 보존·프로젝트 경합을 검증한다.

```text
python -B -m unittest discover -s tests
```

최종 전체: **Ran 108 tests, OK (skipped=1)** → **107개 통과**, Playwright가 필요한 기존 브라우저 테스트 1개 skip. 기존 품질·최종 확정·자동 진행·중복 실행·무료 모델 제한과 기존 HTTP 회귀도 포함한다. `tests/test_smoke.py`는 함수형이며 저장소 실제 경로 격리가 없어 별도 실행하지 않았다. 실패·충돌 없음.

직전 보고서의 전체 103개 중 102개 통과/1개 skip은 과거 기록이다. 이번에는 새 HTTP 5개를 추가한 위 108개 결과를 직접 확인했다. 평가 오류·잘못된 판정 구조·저장 실패 등은 기존 단위/핸들러 테스트가 이번 전체 실행에 포함되어 통과했으며 이들 모두를 새 HTTP로 재현했다고 주장하지 않는다.

`git diff --check`: 통과. 보고서 동일 경로가 없음을 확인한 뒤 새로 작성했으며 저장 후 다시 읽어 확인했다. 실제 AI API 호출: **없음**. 유료 서비스·외부 제공자 호출·의존성 설치: **없음**. 네트워크는 테스트 loopback 및 사용자가 요청한 Git 원격 동기화/푸시뿐이다.

## 변경 파일과 한계

- `tests/test_quality_review_http.py`: 신규 HTTP 테스트 5개.
- `reports/mock_quality_review_http_validation_20261102.md`: 이 보고서.
- `codex_tasks/task_history.md`: 결과 및 보고서 링크 기록.

운영 코드·기존 테스트 수정 없음. 기존 업무 JSON·업무 결과·스냅샷·백업·미추적 기존 파일 수정/삭제/스테이징 없음. 테스트 산출물도 Git에 넣지 않는다.

형식 통과는 사실성과 실무 결과 품질을 증명하지 않는다. 이번 품질 검사는 사용자 승인 대체·자동 수정·후속 실행을 하지 않는다. 다중 프로세스·재시작 복구와 실제 모델 품질은 검증 범위 밖이다. 다른 프로젝트 동시 평가 fixture는 현재 성공 결과를 가진 구형 데이터 호환 경로를 사용하며 실제 과거 입력 복원을 검증한 것은 아니다. 새 실행 결과의 입력 맥락 변경 검사는 동일 프로젝트 재실행 경로에서 확인했다.

관련 3개 파일만 선택적으로 커밋·푸시하고 원격 SHA와 보고서 존재를 확인한다.
