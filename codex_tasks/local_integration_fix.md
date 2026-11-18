# 회사 PC 로컬 환경 통합 검증 및 오류 수정

## 목표
AI Company OS의 기존 기능과 대본 복구 경로를 보존하면서 회사 PC(Windows 11 / WSL2 Ubuntu, Python 3.14.4)에서 통합 테스트와 컷룸 로컬 실행을 완료한다. 프로젝트 루트는 ~/projects/ai-company-os, 가상 환경은 .venv이다. AGENTS.md를 먼저 읽고 준수한다.

## 확인된 증상
2026-11-18 사용자 실행 결과 83개 테스트 중 8개 실패. 6건은 tests/test_video_mission_one.py의 공통 fixture 2008행에서 rework_obvious_goal_drift 대신 invalid_model_json 발생. 2건은 116행과 174행의 미승인 작업 검증에서 각각 mission_internal_review_incomplete, mission_independent_web_research_unavailable 대신 operating_consent_required 발생. 행 번호는 사용자 실행 당시 기준이다. 원인을 Python 버전으로 단정하지 말고 현재 로컬 코드와 테스트를 확인한다.

## 실행 범위
- git status 및 현재 HEAD 확인. 작업 중인 기존 사용자 변경을 덮어쓰지 않는다.
- Python 3.14 호환성, JSON fixture 및 검증 순서, 동의 검증과 미승인 작업 차단 조건을 함께 분석하고 근본 원인을 필요한 최소 변경으로 해결한다. 오류 코드 기대값을 변경하는 경우 실제 안전 계약과 의도에 맞다는 근거를 남긴다.
- 기존 기획/대본을 재사용하는 복구 흐름이 현재 브랜치에 있다면 원본 보존, 서명/동의, 신규 호출 원장, 대본 수정부터 시작, 최종 대표 승인 대기까지 오프라인 검증한다. 다른 구현이 이미 존재하면 중복 개발하지 않는다.
- 아래 세 테스트 모듈과 JS 문법 검사 실행. 누락 모듈은 확인 후 현재 대응 테스트를 실행하고 보고한다. 테스트 결과를 숨기지 않는다.
  ```bash
  source .venv/bin/activate
  PYTHONPATH=core:companies/video python -B -m unittest -q tests.test_rework_quality_followup_unit tests.test_rework_script_review_defects_unit tests.test_video_mission_one
  node --check companies/video/studio/studio.js
  ```
- 컷룸은 실제 API를 비활성화한 별도 임시 테스트 데이터 환경 및 localhost에서 기동/조회 확인하고 종료한다. 실제 환경 변수나 실데이터는 건드리지 않는다.
- 실제 Gemini/YouTube API 호출, 외부 데이터 전송, 유료 실행, 자동 재시도, 기존 데이터/백업/호출 원장/동의 변경 또는 삭제 금지. 실제 API 키, 서명 키, .env, 원본 실사용 데이터, 가상 환경, 생성 영상은 GitHub에 올리지 않는다.
- 불필요한 중간 확인을 요구하지 않고 가능한 범위에서 한 번에 완료한다.

## 결과 전달
reports/local_integration_fix_result.md에 한국어로 원인, 수정 파일, 테스트별 실제 결과/실패 수, 컷룸 확인 범위 및 남은 문제, 실제 AI 호출 0회 여부, 실행한 명령, HEAD와 변경 내역을 기록한다. 실패가 남아 있으면 명확히 보고하고 테스트 성공을 가장하지 않는다.

보고서 및 이번 작업에서 검증된 소스/테스트 변경만 명시적으로 git add 후 commit/push하여 GitHub main에 전달한다. 사용자 기존 변경, 미검증 코드, 민감정보는 포함하지 않는다. 검증 실패 시 미검증 소스 변경은 push하지 말고 보고서만 전달한다. 원격 충돌 또는 인증 문제 발생 시 강제 push 없이 중단하고 보고한다. 다른 PC에서도 결과를 GitHub에서 확인할 수 있도록 커밋/푸시 결과를 최종 메시지에 표시한다.
