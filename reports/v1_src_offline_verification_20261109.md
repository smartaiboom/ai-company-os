# v1.0 src 오프라인 점검 결과

- 일자: 2026-11-09 KST. 대상: `main`의 `5ed3e724dd0592e0e01a5e98ddba41dc79c9c903`.
- `git pull --ff-only`로 최신 변경을 반영하고 `docs/V1_MIGRATION_STATUS.md`를 확인했다.
- **결과: src 16개 모듈 import 성공, 기존 핵심 오프라인 테스트 150개 통과**(실패 0, 오류 0, 건너뜀 0; 최종 실행 25.793초).

## 검증 방법과 범위

Git 추적 소스·테스트만 `/tmp`의 격리 영역에 복사했다. 기존 데이터·백업·산출물·비밀 파일은 복사하지 않았다. 모듈 검색 순서는 `src`, `phase1`이며 16개 모듈의 실제 로드 경로가 모두 격리된 `src/`임을 확인했다. 원본 `src/`와 `phase1/`의 해당 16개 파일은 Git blob SHA도 모두 같다.

실행 명령: `python -B /tmp/v1_offline_audit.py`(이번 점검용 임시 실행기). 다음 기존 테스트 모듈을 unittest로 로드했다. 상속된 테스트 실행도 150개에 포함된다.

```text
tests.test_autonomous_company       tests.test_autonomous_live
tests.test_autonomous_free          tests.test_autonomous_gemini
tests.test_autonomous_gemini35       tests.test_production_video
tests.test_ai_provider_adapter      tests.test_project_budget
tests.test_real_ai_safety_budget
```

관리자 계획·직원 실행·내부 검토/수정·결과 전달·최종 산출물, Gemini 3.5 바인딩, 공급자 어댑터, 예산·동의·중복 호출 방지와 로컬 영상 제작을 검증했다. AI 응답은 모의 transport를 사용했다. Python audit hook으로 외부 소켓 연결·DNS·송신과 저장소 쓰기를 차단하고, 자식 Python에도 같은 보호를 적용했다. 실제 AI API 호출 **0회**, 네트워크 차단 이벤트 **0건**이다.

첫 실행은 150개 실행 중 자식 프로세스 재조회 한 항목에서 오류 5건이 발생했다. 기존 fixture의 환경변수 초기화(`clear=True`)로 `PYTHONPATH`가 사라지는 실행기 문제였다. 임시 실행기에 자식 프로세스의 모듈 경로를 명시한 뒤 동일 150개를 다시 실행해 모두 통과했다. 제품 코드나 기존 테스트는 수정하지 않았다.

## 보존 및 남은 범위

- `ai-company-os-phase1/`, `phase1/`, `src/` 및 존재하는 루트 `data/`, `backups/`, `artifacts/`의 일반 파일 745개를 실행 전후 SHA-256으로 비교해 파일 목록과 내용이 동일함을 확인했다. 기존 원장·백업·이전 폴더와 사용자 미추적 파일을 수정·삭제하지 않았다.
- 변경 파일은 이 보고서 하나다. 최종 실행 로그와 요약은 로컬 `/tmp/v1-offline-audit-2hk5dxb_/tests.log`, `summary.json`에 남겼다.
- 기존 테스트는 아직 `phase1/`의 app·실행 엔진·fixture·런처 등 보조 코드에 의존한다. **src 단독 제품 실행, 전체 테스트, 실제 AI 품질·운영 연결을 검증한 것은 아니다.** 테스트 이전과 새 진입점 정비가 남아 있다.
- 이번 점검은 목표 입력→AI 자율 협업→산출물 경로의 기존 오프라인 회귀 근거를 확보했다. 실제 AI 한 사이클과 문서에 적힌 v1.0 경험 검색·재사용은 미검증이며, 기존 수동 업무 승인 경로의 해소도 이번 범위에 포함하지 않았다.
