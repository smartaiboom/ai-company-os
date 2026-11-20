# 실환경 구성 및 실제 업무 통합 검증 결과

2026-11-20 13:15–13:16 KST. WSL2 Ubuntu와 VS Code 작업 루트는 `/home/jun/projects/ai-company-os`다. 깨끗한 작업 트리에서 GitHub `main`을 `6827017`에서 기준 커밋 `bdaa3aa`로 fast-forward했다. 공통 개발 규칙과 직전 효율적 조사 실행 결과를 확인했다.

## 읽기 전용 환경 진단

| 항목 | 결과 |
| --- | --- |
| Gemini 요청 키 | 로컬 `.env`에 등록됨. 대표가 제공한 AI Studio 화면의 키 끝 네 자리와 불일치. |
| Gemini 독립 제작 프로젝트 대조 키 | `.env`와 현재 프로세스 환경에 미설정. 확인한 로컬 환경 설정 파일에서도 발견되지 않음. |
| Gemini 무료 실행 플래그 | `GEMINI35_AUTONOMOUS_FREE_ENABLED` 비활성. |
| Tavily 키와 로컬 무료 전용 설정 | 키 등록 및 `TAVILY_RESEARCHER_FREE_ONLY=1` 확인. 화면의 키 끝 네 자리와 불일치. |

기존 진입점 `PYTHONPATH=core:companies/video .venv/bin/python -m studio_server --env-file .env --research-readiness`를 실행해 `gemini_free_execution_disabled`, `independent_production_key_missing`을 확인했다. 화면 대조는 프로세스 내부에서만 했고 값은 일치 여부만 기록했다. 끝 네 자리 비교는 전체 키와 프로젝트의 독립 검증을 대신할 수 없다. `.env`는 Git에서 제외되며 권한 `0600`과 기존 내용을 유지했다. 어떤 키도 복사·발급·삭제하지 않았다.

## 대표 화면 근거와 공급자 상태

대표가 제공한 Google AI Studio 화면에는 Default Gemini Project, 무료 등급, 결제 설정 안내가 표시됐다. Gemini 3.5 Flash Lite의 최근 28일 최대 사용량은 RPM 8/15, TPM 68.56K/250K, RPD 20/500이었다. 현재 잔량과 결제 비활성의 독립 증거는 없으며, TTS 쿼터 이력은 조사 모델과 별개다. Tavily 화면의 Researcher 플랜은 표시 시점에 사용 0/1,000크레딧, 잔량 1,000, Pay as you go OFF였다. 로컬 키 불일치로 이 화면을 현재 로컬 키의 계정 상태로 사용할 수 없다. 승인받지 않은 공급자 조회와 검증용 호출은 하지 않았다.

## 실제 실행과 보존

승인 전 v3 제안을 읽기 전용으로 확인했다. 현재 상태는 설정 대기이며 이전 독립 관리자 결과는 `hold`다. 범위는 Gemini 직원 최대 3회와 관리자 최대 2회, Tavily 1크레딧, Klei 공식 HTML 2개 및 robots 1개, 유효 24시간, 비용 $0이다. 최종 직원 보고와 독립 최종 검토 몫을 포함한다. 제안에는 보존 자료 12건이 있으며 신규 관측과 구분한다. 기존 누적 Gemini 예약 5회, 완료 3회, 기록 4,903토큰, Tavily 예약 0회다.

신규 승인·예약·요청·수신·완료·토큰·관측은 0건이다. 실제 Gemini·Tavily·공식 GET·YouTube·TTS·미디어 다운로드·게시도 각각 0회다. 실제 직원 수행, 관리자 보완, 업무 목표 달성과 편집 권리 근거는 검증하지 못했으며 Klei 외 장면 권리는 계속 보류다. 운영 서버와 실행 중 업무는 변경하지 않았다. 코드 수정 필요성이 확인되지 않아 진단만 수행했고 이미 마친 오프라인·브라우저 시험은 반복하지 않았다.

기존 운영 파일 227개의 SHA-256은 전후 동일했다. 비밀키와 잠금 파일은 비교에서 제외했다. 기존 대본 v2, WAV 4개, MP4 1개, 대표 평가, 제작사·Commons 및 승인·원장 기록을 보존했다. 새 감독 승인 디렉터리와 추가 백업은 만들지 않았다.

## 재개에 필요한 최소 조치

대표가 한 번에 AI Studio 지정 프로젝트와 Tavily 무료 계정의 결제 설정 및 현재 가용 한도를 확인하고, **기존 두 화면의 키를 로컬 보안 설정에 직접 등록**해야 한다. Gemini 제작 프로젝트 대조 키는 요청 키를 복사하는 방식과 별개로 AI Studio 지정 프로젝트에서 직접 확인해 `GEMINI_PRODUCTION_PROJECT_API_KEY`에 설정한다. 키를 채팅이나 Git에 전달할 필요는 없다. 이 확인이 끝나면 Codex가 로컬 대조, 무료 실행 플래그 설정과 새 서명 승인을 거쳐 조건부로 승인된 한 사이클을 검증할 수 있다.
