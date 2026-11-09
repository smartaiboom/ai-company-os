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

현재 import는 단일 패키지가 아니라 파일명 기준이므로 로컬에서 다음 경로를 지정한다.

```bash
PYTHONPATH=core:companies/video python -B -m unittest discover -s tests -p 'test_*.py' -v
PYTHONPATH=core:companies/video python -B -c 'import video_production_company, autonomous_gemini35'
```

새 폴더 경로에서 기존 핵심 4개와 목표 문답 통합 3개 테스트를 통과했다. 목표 문답 CLI는 오프라인으로 제공하며 실제 AI 문답·산출물 품질 검토·경험 재사용은 후속 개발 대상이다.

## 과거 자료 정리

이전 `phase1/` 보관본, 일회성 이관 스크립트, 과거 검증 보고서는 **현재 Git 작업 트리에서 제거**했다. 다만 Git 커밋 이력에는 남아 있어 필요할 경우 이전 커밋에서 열람·복원할 수 있다. 현재 제품용으로 쓸 코드/테스트는 위 폴더에 보존했다.

GitHub에 없는 과거 로컬 데이터·원장·백업·비밀키는 삭제/이동하지 않는다. 앞서 Codespaces에서 실행한 로컬 보관 스크립트로 생성된 `/workspaces/ai-company-os-local-archive-XXXXXXXX/`는 GitHub에 포함되지 않으며 보존해야 한다.

## 목표

사용자 목표 → AI 관리자의 필요 질문 → 전문 AI 직원의 실제 제작 → 결과물 검토·수정 → 사용자 평가 → 경험·성공 방식 저장 → 다음 작업에서 재사용 및 성능 비교. 장기적으로 사용자 개입을 줄이고 회사의 자율 운영을 강화한다. 향후 AI Company OS vs ChatGPT 비교 콘텐츠로 품질·효율 변화 검증.

## 목표 구체화 문답 (오프라인)

```bash
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli create '안전 교육 영상'
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli show <초안ID>
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli propose <초안ID> proposal.json
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli answer <초안ID> audience '초등학생'
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli skip <초안ID> duration
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli revise <초안ID> spec.json
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli confirm <초안ID> <show의-review_hash>
PYTHONPATH=core:companies/video python -B -m goal_dialogue_cli handoff <초안ID>
```

모든 명령은 동일 ID로 재개한다. 기본 저장소는 `data/goal_dialogues`, 새 영상 초안은 `data/dialogue_video_projects`이며 기존 저장소와 분리한다. `--root`는 하위 명령 앞에 지정한다. `handoff`는 초안 생성만 하며 실행·운영 동의를 부여하지 않는다.

현재 `propose`는 사용자가 준비한 **오프라인 JSON 제안**을 읽는다. 실제 AI 판단이 아니며 고정 질문 생성기도 제공하지 않는다. 테스트에서만 누적 답변에 따라 질문을 바꾸는 모의 관리자를 사용한다. 실 AI 질문은 전송·모델·비용·호출 한도 승인 계약 구현 전까지 차단한다.

제안 형식은 `{"questions":[{"id":"audience","text":"누가 보나요?","reason":"설명 수준 결정"}],"sufficient":false,"spec":{...}}`이다. 충분하면 `questions:[]`, `sufficient:true`를 사용한다. 명세는 아래 형식이며 모든 필드가 필요하다.

```json
{
  "audience": {"value":"미정", "evidence":[]},
  "deliverable": {"value":"안전 교육 영상", "evidence":["goal"]},
  "style": {"value":"미정", "evidence":[]},
  "quality": {"value":"미정", "evidence":[]},
  "constraints_budget": {"value":"미정", "evidence":[]},
  "summary":"확인할 영상 요구사항",
  "assumptions":["근거가 없는 항목은 미확정 가정"]
}
```

`evidence`는 원래 목표 `goal` 또는 현재 답변의 질문 ID이다. 근거가 없는 값은 추정이다. 참조는 해석의 정확성을 보증하지 않으므로 사용자가 명세를 검토·수정하고 해시로 확정한다. 정정 시 기존 명세는 폐기된다. 라운드 한도는 기본 4회(최대 8회), 질문은 회당 1~3개다. 실패·중단된 제안은 자동 재호출하지 않으며 `revise`로 명세를 직접 검토해 복구할 수 있다. 확정 후 변경은 새 초안으로 시작한다. 목표·명세·답변 전체의 계획 입력이 기존 엔진의 4,000자 한도를 넘으면 연결을 차단한다. 비밀키는 입력하지 않는다(일반 키 패턴은 저장 전 차단하지만 완전한 비밀 탐지는 보장하지 않는다).
