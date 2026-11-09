# AI Company OS

AI Company OS는 **공통 AI 회사 운영 엔진**을 기반으로 분야별 전문 AI 회사를 운영하는 시스템이다. 버전마다 폴더를 복제하지 않고, **전문 회사별 폴더**로 확장한다.

## 현재 구조

```text
ai-company-os/
├── core/                 # 공통 AI 관리자·직원 실행 엔진, 모델/안전/비용/저장 로직
├── companies/
│   └── video/            # 현재 1차 전문 회사: 영상 제작
├── tests/                # 현재 유지할 간결한 핵심 테스트
├── docs/                 # 현재 유효한 설계 문서
├── AGENTS.md             # 개발 원칙
└── README.md
```

- `core/`: 기존 검증된 Python 공통 엔진 14개 모듈. 필요 이상의 재개발이나 파일 복제를 피한다.
- `companies/video/`: 기존 영상 회사 프로필 및 렌더러 2개 모듈. 실제 영상 품질 향상은 앞으로 개발한다.
- `companies/product/`, `companies/software/` 등은 필요할 때 추가한다.
- `tests/`: 기존 협업 엔진을 사용하는 독립 모의 테스트 4개. 전체 기능 검증이 아니므로 실제 제품 개발 시 필요한 검증을 묶어 보강한다.
- `docs/ARCHITECTURE.md`: 현재 구조와 다음 개발 계획.

## 실행·개발 주의

Python 모듈은 **내용을 바꾸지 않고 위치만 옮겼다**. 현재 import는 단일 패키지가 아니라 파일명 기준이므로 로컬에서 다음 경로를 지정한다.

```bash
PYTHONPATH=core:companies/video python -B -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPATH=core:companies/video python -B -c 'import video_production_company, autonomous_gemini35'
```

위 명령은 새 폴더 기준 검증 명령이다. **폴더 이동 이후에는 아직 실제 실행 결과를 확인하지 않았다.** 기존 검증(16개 import/모의 4개 통과)은 이전 `src/`에서 이루어졌다. v1.0 사용자용 실행 진입점·목표 문답·실제 산출물 품질 검토·경험 재사용은 개발 대상이다.

## 과거 자료 정리

이전 `phase1/` 보관본, 일회성 이관 스크립트, 과거 검증 보고서는 **현재 Git 작업 트리에서 제거**했다. 다만 Git 커밋 이력에는 남아 있어 필요할 경우 이전 커밋에서 열람·복원할 수 있다. 현재 제품용으로 쓸 코드/테스트는 위 폴더에 보존했다.

GitHub에 없는 과거 로컬 데이터·원장·백업·비밀키는 삭제/이동하지 않는다. 앞서 Codespaces에서 실행한 로컬 보관 스크립트로 생성된 `/workspaces/ai-company-os-local-archive-XXXXXXXX/`는 GitHub에 포함되지 않으며 보존해야 한다.

## 목표

사용자 목표 → AI 관리자의 필요 질문 → 전문 AI 직원의 실제 제작 → 결과물 검토·수정 → 사용자 평가 → 경험·성공 방식 저장 → 다음 작업에서 재사용 및 성능 비교. 장기적으로 사용자 개입을 줄이고 회사의 자율 운영을 강화한다. 향후 AI Company OS vs ChatGPT 비교 콘텐츠로 품질·효율 변화 검증.
