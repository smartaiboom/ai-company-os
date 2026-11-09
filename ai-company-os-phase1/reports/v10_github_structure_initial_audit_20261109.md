# AI Company OS v1.0 — GitHub 구조 1차 직접 조사 (ChatGPT)

조사일: 2026-11-09 KST
방법: 연결된 GitHub 저장소 `smartaiboom/ai-company-os` 기본 브랜치 파일 목록 API와 관련 원본 파일을 **읽기 전용** 조사. 이번 보고서만 신규 생성. Codex 사용/소스 변경/삭제/실행/실 API 호출 없음.

## 현재 상태
- GitHub `ai-company-os-phase1/` 아래 **282개 tree 항목(폴더 포함)**. 이 중 개발 지시서 `codex_tasks/` 하위 75개 파일, 보고서 `reports/` 하위 90개 파일, `tests/` 하위 67개 파일, `diagnostics/` 하위 3개 파일 (폴더 항목 각 1 제외).
- 루트에 `app.py` 140KB 등 오래된 모놀리식 소스와 신규 `autonomous_*.py`, `video_*.py`, `real_manager_*_tool.py` 등 실험용 스크립트가 혼재한다.
- GitHub에서 관리하는 파일만 확인했으며 **Codespaces에만 있는 gitignored data, backups, artifacts, 비추적 파일, 디렉터리 실제 크기·디스크 사용량·현재 실행 중 프로세스는 확인 불가**. 이 부분을 미확인이라고 명시한다.

## 재사용 가능한 실제 경로(읽은 import에 근거)
- v2 전문 영상 프로필 `video_production_company.py` → `autonomous_gemini35.py` → `autonomous_gemini.py` → 기존 자율 회사/무료/live 계층. `production_video.py`는 `autonomous_company.py`의 검사/해시/시간과 `local_artifacts.py`의 명령 실행/글꼴을 재사용한다.
- `autonomous_free.py`는 `autonomous_live.py`, `autonomous_company.py`, `ai_provider_adapter.py`, `ai_safety.py`를 사용한다. 따라서 파일 이름이 낡았거나 공급자가 다르다고 무작정 삭제하면 v1.0 도구도 깨질 수 있다.
- `AI_COMPANY_OS_CORE_PRINCIPLES.md`, `AGENTS.md`는 현재 개발 안전·역할 규칙이고 사용자의 **새 단계적 품질 개선/피드백 기반 학습** 방향과 동기화가 필요하다. 원칙 개정은 별도 단계.
- 최근 실제 Gemini35 첫 delivered 결과와 프로젝트 원장/동의·일회 소진 표식은 Git에 없는 data에 있다. 어떤 이동/정리도 실제 파일을 확인하기 전 수행하면 안 된다.

## 현재 확인 가능한 분류 (잠정)
| 분류 | 예시 | 판단 |
|---|---|---|
| A — 새 v1.0에서 재사용할 기능 후보 | `autonomous_company.py`, `autonomous_live.py`, `autonomous_free.py`, `autonomous_gemini.py`, `autonomous_gemini35.py`, `ai_provider_adapter.py`, `ai_safety.py`, `gemini_provider.py`, `role_json_schema.py` | 상속·계약·안전 의존성이 있어 제거 금지 |
| B — 새 목표에 맞게 검토·수정할 후보 | `video_production_company.py`, `production_video.py`, `local_artifacts.py`, `README.md`, 목표/품질/기억 관련 로직 | 실제 품질 검토·사용자 피드백·경험 검색/재사용 인터페이스는 새 설계 필요 |
| C — 유지할 회귀 테스트 후보 | `tests/` 중 자율 엔진, Gemini35, 실제 로컬 도구, 보안·원장·장기 경로 | 전체 67개를 무조건 지우면 안 됨. 실제 import·fixture/커버리지 분석 후 선별 |
| D — 활성 개발 화면에서 보관 영역으로 분리 검토 | 과거 `codex_tasks/`, `reports/`, `diagnostics/`, `gemini_connection_once.py`, `synthetic_groq_compat_once.py`, `real_manager_*_tool.py`, `real_task002_once_tool.py`, `video_quality_pilot.py` | 일회성/역사 자료일 가능성이 높지만 **삭제 확정 아님** |
| E — 제외 가능 후보 | 아직 확정 없음 | 디렉터리 목록과 일부 import만으로 삭제 안전성을 증명할 수 없음 |

## 권장 구조
원본 `ai-company-os-phase1/`을 당장 정리/삭제하지 않고, **새 `ai-company-os-v1/` 또는 동등한 독립 작업 폴더**에서 핵심을 재사용·통합. 기존 원본은 과거 실사용 프로젝트를 열람 가능한 상태로 보존. 새 폴더 최상위에는 `README.md`, `src/`, `tests/`, `docs/`, `config/` 정도만 노출. 수십 개의 일회성 스크립트·개발 지시서·보고서가 신규 제품의 실행 루트에 함께 놓이지 않도록 함.

현재 여러 상속 계층이 서로 직접 import하므로, 단순 파일 복사만으로 돌아간다고 가정하지 않는다. 이전 후에는 실제 시스템 테스트·저장소 격리·KST·원장/비용 보안 검증이 필요. 새 v1.0은 처음부터 전면 재개발하지 말고 **검증된 코드 선별 재사용**이 원칙.

## 이후 개발 파일 정리 정책
- 새 기능 전에 기존 재사용 가능 함수·모듈 검색.
- 실행 루트에는 운영 진입점과 실제 필수 코드만. 일회성 진단은 `devtools/` 등으로, 역사 문서는 `archive/`/이전 버전에서 보관.
- 핵심 회귀 테스트는 계속 유지. 특정 실패를 단 한 번 관측하는 스크립트는 반복 사용 가치가 없으면 보관·제외 후보로 분류.
- 기능을 교체하면 옛 코드 참조 여부·저장 데이터 버전/동의 해시·백업·테스트를 확인하고 정리. 파일 이동/삭제는 사용자 승인 후 범위별로 처리.
- 실사용 원장·사용자 데이터·비밀키·산출물은 임의로 청소하거나 git clean으로 제거 금지.

## 다음 단계
GitHub에서 확인 가능한 구조와 핵심 의존성을 파악했음. **아직 Codespaces 로컬 미추적 파일 및 모든 모듈 의존성을 전수 분석한 것이 아니므로 실제 삭제를 승인할 근거가 부족**. 새 v1.0 폴더를 만드는 단계에서는 Codex가 최소 1회 로컬 파일/실제 테스트를 확인해야 함. 그 전까지 ChatGPT가 GitHub 문서·구조 설계, 파일 분류, 신규 작업 계획을 직접 맡아 Codex 사용량을 줄일 수 있음.

다음 정리 단계의 목표는 **원본 불변 보존 + 새 루트에 검증된 핵심 파일만 선별 이식 + 필수 자동 회귀 테스트 + 사용자의 단계적 품질 향상 목표 반영**이다.
