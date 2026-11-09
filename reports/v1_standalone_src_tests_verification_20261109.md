# v1.0 src·tests 독립 오프라인 검증

- 일자: 2026-11-09 KST. 대상 커밋: `077804d10ec887e5d1bf02b3378d8ae15d774f82`.
- 로컬 상태 확인 후 `git pull --ff-only`로 최신 변경을 가져오고, 루트 `AGENTS.md`와 `docs/V1_MIGRATION_STATUS.md`를 먼저 확인했다.
- **결과: phase1 없이 src 16개 모듈 import 성공, 신규 tests 4개 모두 통과. 소스·테스트 수정 불필요.**

## 방법과 실행 결과

Git 추적된 `src/`, `tests/`만 `/tmp/v1-standalone-x4e39ynm/`에 복사했다. 기존 데이터·비밀·원장·백업은 복사하지 않았다. 격리 영역에는 `phase1/`, `ai-company-os-phase1/`, 루트의 기존 `app.py`가 없고 Python 검색 경로에서도 원본 저장소를 제외했다. 로드된 프로젝트 모듈의 파일 경로는 모두 격리된 `src/`와 `tests/` 내부였다.

1. `python -B /tmp/v1_standalone_audit.py`: Python 3.14.2에서 16개 모듈 전부 import 후 unittest discovery 실행. **4개 통과, 실패·오류·건너뜀 0건**(0.303초). 실제 연결·DNS·송신 및 저장소 파일 쓰기를 audit hook으로 차단했고, 네트워크 이벤트는 0건이었다.
2. 사전 import에 따른 영향을 배제하기 위해 새 Python 프로세스에서 아래 문서 명령을 별도로 실행했다. **4개 통과**(0.256초).
3. 아래 독립 import 명령도 성공했고, 두 모듈 모두 격리된 `src/`에서 로드됐다.

```bash
PYTHONPATH=src python -B -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPATH=src python -B -c 'import video_production_company, autonomous_gemini35'
```

별도 프로세스는 API 키 등 기존 환경변수를 제거한 `env -i` 환경에서 실행했다. 첫 환경 구성에서 PATH에 Python 설치 경로가 없어 실행되지 않아, `/home/codespace/.python/current/bin`을 추가한 후 위 명령을 정상 실행했다. 제품·테스트 오류는 없었다.

검증한 네 항목은 두 업무 분야의 모의 목표→계획→직원 실행→내부 검토·수정→최종 파일과 재실행 시 호출 불변, 실패·한도 초과 시 결과 미게시, 중단된 operation 자동 재시도 금지, 미동의 프로젝트 생성 차단이다.

## 보존·변경·남은 범위

- Codex가 이번 작업에서 실행한 **실제 AI API 호출 0회**, 기존 프로젝트 재실행 0회. AI 관리자·직원 응답은 fixture이며 운영 권한·동의·원장을 변경하지 않았다.
- `ai-company-os-phase1/`, `phase1/`, `src/`, `tests/` 및 존재하는 루트 `data/`, `backups/`, `artifacts/`의 일반 파일 **750개**를 격리 검증 전후 SHA-256으로 비교해 목록·내용이 동일함을 확인했다. 기존 미추적 파일도 수정·삭제하지 않았다.
- 변경 파일은 이 보고서 하나다. 임시 실행기·로그·요약은 `/tmp/`에만 두었다(`tests.log`, `summary.json`).
- 핵심 모의 회사 흐름과 import의 과거 폴더 독립성을 확인했다. 신규 4개는 과거 150개 회귀 테스트를 대체하지 않는다. 이번에는 실제 영상 렌더·공급자 통신·실제 AI 품질을 검증하지 않았다.
- 실제 사용자용 v1.0 실행 진입점/CLI/UI, 목표 문답, 사용자 평가 및 경험 검색·재사용을 통한 품질 향상은 별도 구현·검증 대상이다. **실서비스 독립 실행 완료를 의미하지 않는다.** 이번 범위의 미해결 import 의존성·테스트 오류·권한 문제는 없다.
