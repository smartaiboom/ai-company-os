# 회사 PC 로컬 통합 검증 결과 (2026-11-18 KST)

## 재현 및 수정

`git pull --ff-only`로 `main`을 `8721885`에서 `3a31a9dec9493df48d145988261fae19f9781c04`로 갱신했다. 갱신 직후 작업 트리는 깨끗했다. WSL2 Ubuntu의 프로젝트 `.venv`에서 Python 3.14.4로 지정된 83개 테스트를 실행해 기존 8건의 실패를 재현했다.

- 목표 이탈 6건은 공통 픽스처가 평문을 JSON 파서에 넘겨 `invalid_model_json`이 발생했다. 실제 대본 형식의 JSON을 사용해 관리자가 수락한 목표 이탈을 시스템이 검출하고, 수정 한도에 따라 재수정 또는 중단으로 전환하는지 확인했다.
- 미승인 보고 2건의 첫 차단 원인은 현행 서명 동의 검증이다. 미승인 보고는 `operating_consent_required`, 동의 이후 내부 검토를 마치지 않은 보고는 `mission_internal_review_incomplete`로 차단됨을 확인했다. 게임 미션에서 독립 웹 조사 연결이 없을 때 준비와 실행은 기존 조사 차단 코드로 거부된다. 이 검증에서 송신은 0회였다.
- 대본 복구 통합 테스트에서 컷룸의 HTTP 경로와 화면 버튼에 등록된 `rework-script-recover-prepare`가 서버 액션 목록에서 빠져 404로 끝나는 결함을 확인했다. `companies/video/studio_server.py`의 액션 목록에 등록해 기존 복구 함수에 연결했다. `tests/test_video_mission_one.py`에 위 계약 검증과 서명된 대본 복구 시나리오를 반영했다. 운영 환경의 동의 검사 순서와 모델 실행 로직은 수정하지 않았다.

## 검증

| 대상 | 실행 | 실패·오류 |
| --- | ---: | ---: |
| `tests.test_rework_quality_followup_unit` | 15 | 0 |
| `tests.test_rework_script_review_defects_unit` | 4 | 0 |
| `tests.test_video_mission_one` | 65 | 0 |
| 통합 실행 | 84 | 0 |

세 모듈은 모두 존재했고, 통합 실행은 175.005초에 완료됐다. `node --check`와 `git diff --check`도 통과했다.

대본 복구 테스트는 현재 코드에서 자동 보완하는 자막 결함 검토 실패를 과거 검증 방식으로 재현했다. 원본 기획 보고서, 미션 파일, 실패 작업 파일 및 서명된 동의 파일을 바이트 단위로 비교했다. 새 작업은 빈 호출 원장에서 별도 서명 동의 후 시작했고, 모의 응답 4건은 대본 수정 → 대본 검토 → 편집 → 편집 검토 순으로 기록됐다. 후속 보고서는 원본 출처를 포함해 대표 승인 대기 상태에 도달했다.

컷룸은 환경을 비우고 `GEMINI35_AUTONOMOUS_FREE_ENABLED=0`을 설정한 뒤 임시 작업·참조 디렉터리에서 기동했다. 샌드박스가 로컬 소켓 생성을 제한해 승인된 실행에서 `127.0.0.1`의 임의 포트로 다시 기동했다. `/`, `/studio.js`, `/studio.css`, `/api/studio` 응답은 모두 HTTP 200이었고, 대시보드 프로젝트 및 보류 목록이 비어 있음을 확인한 뒤 서버를 종료했다. 실제 Gemini·YouTube API 호출과 유료 실행은 0회였다. 실사용 데이터, 환경 파일, 기존 동의와 호출 원장을 사용하지 않았다. 브라우저 조작, 실사용 데이터 기반 컷룸 검증 및 실제 AI 동작 검증은 수행 범위 밖이었다.

## 실행 명령

```bash
git pull --ff-only
git status --short --branch
git rev-parse HEAD
source .venv/bin/activate
python -VV
PYTHONPATH=core:companies/video python -B -m unittest -q tests.test_rework_quality_followup_unit tests.test_rework_script_review_defects_unit tests.test_video_mission_one
PYTHONPATH=core:companies/video python -B -m unittest -q tests.test_video_mission_one.MissionOneTests.test_signed_script_recovery_reuses_plan_and_starts_with_writer_revision
PYTHONPATH=core:companies/video python -B -m unittest -q tests.test_rework_quality_followup_unit
PYTHONPATH=core:companies/video python -B -m unittest -q tests.test_rework_script_review_defects_unit
node --check companies/video/studio/studio.js
git diff --check
```

컷룸 확인은 환경을 비운 Python 검사에서 `python -B -m studio_server --host 127.0.0.1 --port 0 --root <임시 작업 경로> --reference <임시 참조 경로>`를 자식 프로세스로 실행하고, 표준 라이브러리 `http.client`로 네 경로를 조회한 후 프로세스를 종료하는 방식으로 진행했다.

## Git 전달

이 보고서와 위 소스·테스트 파일만 경로를 지정해 `git add`, `git diff --cached --check`, `git commit -m "Fix Cutroom script recovery integration"`, `git push origin main` 순서로 전달한다. 결과 커밋은 이 보고서를 추가한 Git 이력에서 확인할 수 있다.
