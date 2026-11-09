# AI Company OS — 분야별 전문 회사 구조

기준일: 2026-11-09 KST

## 구조 선택
버전별 폴더가 아닌, 하나의 **공통 엔진 + 여러 전문 회사**를 운영한다.

```text
core/                       # 공통 워크플로·AI 관리자·직원·API 안전/원장
companies/video/            # 영상 제작 전문 회사 (현재 시작 영역)
companies/product/          # 필요할 때 새로 개설
companies/software/         # 필요할 때 새로 개설
tests/                      # 현재 핵심 회귀
docs/                       # 현재 유효한 설계
```

`companies/product`, `companies/software`는 **미래 후보일 뿐 현재 생성하지 않는다**.

## 현재 이동된 파일
공통 엔진: `ai_provider_adapter.py`, `ai_safety.py`, `autonomous_company.py`, `autonomous_free.py`, `autonomous_gemini.py`, `autonomous_gemini35.py`, `autonomous_live.py`, `gemini_connection_once.py`, `gemini_provider.py`, `groq_provider.py`, `local_artifacts.py`, `project_budget.py`, `role_json_schema.py`, `uncertain_reservations.py` (14개).

영상 회사: `production_video.py`, `video_production_company.py` (2개).

기존 `src/` 16개 파일의 blob SHA는 모두 유지한다. 기존 코드의 절대/상대 import 방식을 일괄 재작성하지 않고 `PYTHONPATH=core:companies/video`로 사용한다. `local_artifacts.py`는 공통 회사 엔진이 호출하므로 일단 공통 폴더에 남겼다. 도메인별 명확한 분리는 실제 기능 개발 시 필요할 때 수행한다.

## 과거 자료 정리
과거 `phase1/`의 277개 추적 파일과 원본은 Git 이력 커밋 `d102e84d51f029828ecdec1bc85367c9478c655f`에서 되찾을 수 있다. 현행 프로젝트의 개발에 직접 사용하지 않는 문서/진단/테스트는 현재 트리에서 제거하고, `core/`, `companies/video/`, `tests/`, `docs/`만 실제 작업 영역에 둔다. 삭제된 것은 Git에 **추적되는 과거 파일의 현재 트리 경로**이지 과거 Git 역사나 로컬 gitignored 사용자 데이터가 아니다.

## 다음 제품 개발 기능 묶음
1. 사용자 목표 → AI 관리자 적응형 질문 → 답변 → 구체화된 프로젝트 요구사항/성공 기준.
2. AI 전문 작업과 산출물 실제 품질 평가 → 피드백·수정 루프.
3. 사용자 선호/프로젝트 경험/검증된 개선 사항을 분리 저장하고 관련 다음 프로젝트에 선택적으로 검색·반영.
4. 한 번의 통합 실행 검증으로 실제 영상 제작 회사에서 품질·개입·비용 측정.

이전 개발 이력 재구축이나 버전별 전체 소스 복제를 하지 않는다. 새 제품 경로에 필요한 기능부터 구현한다.
