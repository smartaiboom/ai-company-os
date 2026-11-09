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

폴더 이동 시 기존 `src/` 16개 파일의 blob SHA를 유지했다. 기존 코드의 절대/상대 import 방식을 일괄 재작성하지 않고 `PYTHONPATH=core:companies/video`로 사용한다. `local_artifacts.py`는 공통 회사 엔진이 호출하므로 일단 공통 폴더에 남겼다. 도메인별 명확한 분리는 실제 기능 개발 시 필요할 때 수행한다.

## 과거 자료 정리
과거 `phase1/`의 277개 추적 파일과 원본은 Git 이력 커밋 `d102e84d51f029828ecdec1bc85367c9478c655f`에서 되찾을 수 있다. 현행 프로젝트의 개발에 직접 사용하지 않는 문서/진단/테스트는 현재 트리에서 제거하고, `core/`, `companies/video/`, `tests/`, `docs/`만 실제 작업 영역에 둔다. 삭제된 것은 Git에 **추적되는 과거 파일의 현재 트리 경로**이지 과거 Git 역사나 로컬 gitignored 사용자 데이터가 아니다.

## 다음 제품 개발 기능 묶음
1. 사용자 목표 → AI 관리자 적응형 질문 → 답변 → 구체화된 프로젝트 요구사항/성공 기준.
2. AI 전문 작업과 산출물 실제 품질 평가 → 피드백·수정 루프.
3. 사용자 선호/프로젝트 경험/검증된 개선 사항을 분리 저장하고 관련 다음 프로젝트에 선택적으로 검색·반영.
4. 한 번의 통합 실행 검증으로 실제 영상 제작 회사에서 품질·개입·비용 측정.

이전 개발 이력 재구축이나 버전별 전체 소스 복제를 하지 않는다. 새 제품 경로에 필요한 기능부터 구현한다.

## 목표 문답 통합

`core/goal_dialogue.py`는 독립 표식 저장소, 원자적 쓰기·상태 해시·프로세스 잠금을 기존 Store에서 재사용한다. 별도 초안에 원래 목표, 질문/답변 변경 이력, KST 시각, 제한 라운드, 명세, 사용자 확정 해시를 보존한다. 공급자는 명시적 offline 인터페이스만 허용하며 실 API 어댑터는 제공하지 않는다. 입력 JSON의 필드·근거 참조·중복 질문을 검증한다. 예약 후 실패한 제안과 프로젝트 생성은 자동 재시도하지 않는다.

영상 진입점은 `companies/video/goal_dialogue_cli.py`다. 확정 명세·누적 답변은 새 VideoProductionStore 프로젝트의 goal에 JSON으로 포함되어 기존 Company의 plan 컨텍스트에 도달한다. 기존 전송 필드·prepare/approve·원장·비용·상태 해시 계약은 수정하지 않는다. 새 프로젝트는 실행 미승인 상태이며 기존 동의는 재사용하지 않는다. 자동 제작·실 AI 문답 운영 검증·실 영상 품질 평가·경험 재사용은 후속 개발이다. Gemini 문답 승인 계약은 아래 별도 모드에서 제공한다.

## Gemini 관리자 연결

`core/goal_dialogue_live.py`의 LiveDialogueStore는 독립 mode/표식, `simulation=False`, 별도 real_ai 원장과 서명키를 사용한다. 기존 DialogueStore의 생성 훅·응답 검증·답변·명세·확정·handoff를 재사용하며 기존 오프라인 데이터를 자동 변경하지 않는다. 모델 판단은 동일 questions/sufficient/spec 구조로만 받는다. 질문 목록은 코드에 고정하지 않는다. user_notes는 사용자 자연어 수정이며 `note-N` 근거로 추적한다. 사용자 수정 명세도 다음 전송 입력에 포함한다.

기존 LiveStore의 HMAC 서명 함수를 독립 저장소에서 재사용한다. prepare-consent는 별도 제안 파일에 상태·입력·정확한 wire payload 해시, 고정 Gemini 3.5 모델/endpoint, 0비용/무료 전용 정책, 1회/전체 호출 한도 및 KST 만료를 묶는다. approve-consent는 검토 해시·현재 상태·명시적 사용자/무료 계정 확인을 검사하고 서명한다. 이전 서명 동의는 보존한다. ask-ai는 서명·입력 바인딩·미소진·만료·전체 예산·네임스페이스를 확인한다. 실제 전송은 무료 계정/키 검증 구현 전까지 코드 정책에서 기본 차단한다. 사용자 확인만으로 무료 계정이 검증되었다고 표시하지 않는다.

네트워크 허용 시의 경로는 기존 Gemini35Adapter 요청/응답 정규화를 재사용하며, 호출 예약을 디스크에 먼저 기록하고 잠금을 유지한다. 제한 크기·정상 종료·usage·비용·JSON·근거·중복 질문·라운드를 검증한 뒤에만 completed로 저장한다. 실패는 uncertain, 프로세스 중단은 reserved로 남고 자동 재전송되지 않는다. 응답 원문·임의 오류·키는 원장에 남기지 않는다. 별도 HTTP opener는 프록시 환경과 리다이렉트를 허용하지 않는다. 전송 allowlist에 원장·서명·로컬 경로는 포함하지 않는다. 영상 Store.prepare/approve 및 기존 실행 원장은 수정하지 않았다.

## 단일 요청 인수 범위

같은 `goal_dialogue_live.py`의 OneCallAcceptanceStore는 새 mode/표식의 단일 초안 저장소다. 일반 LIVE_TRANSPORT_ENABLED/POLICY를 변경하지 않는다. 기존 서명·요청 해시·잠금·선예약·응답 검증 경로를 재사용하며, 고정 가상 목표와 빈 첫 입력만 허용한다. 별도 호출 예산은 1, 문답 라운드는 2여서 첫 응답의 질문 1~3개 또는 sufficient 명세 모두 유효하다. 추가 초안 생성·후속 전송·영상 handoff는 거절한다.

사용자는 로컬 비표시 입력으로 프로젝트 키와 환경키를 직접 대조하고 Free/Billing 비활성을 확인한다. 서명된 확인 기록은 초안/저장소/현재 키의 로컬 HMAC 및 1시간 만료에 묶인다. 이는 사용자 확인 근거이며 원격 계정·쿼터 조회 증명이 아니다. 정책에 그 기록의 해시, 범위 해시, Google 무료 데이터 이용 동의 요건을 포함하고 기존 approve-consent에서 전체 검토 해시/상태를 재검증한다. 해당 키·서명·입력·1회 예산·명시적 Google 데이터 정책 승인까지 통과한 인수 범위에만 좁은 전송 예외를 적용한다. 실제 전송 승인 전 준비는 호출/예약 0회이며 기존 원장/동의를 재사용하지 않는다. 응답 검증 후 usage를 보존하고, 실패/중단은 소모된 예약으로 유지한다. 배포의 일반 전송은 계속 비활성 상태다.
