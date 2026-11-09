# AI Company OS — 실제 Gemini AI 관리자 목표 구체화 연결
2026-11-09 KST. Codex용 단일 개발 묶음. 이전 기능을 중복 개발하지 말 것. 이번에는 코드 구현 완료 후 통합 테스트를 한 번에 실행하고 간결한 결과 기록만 남길 것.

## 이번 목표
기존 오프라인 GoalDialogue의 관리자 제안 부분을 실제 Gemini 관리자와 연결할 수 있도록 확장한다. 사용자가 목표 입력 → AI 관리자가 적응형 질문(필요 시 질문 생략) → 사용자 답변 → AI 관리자 명세 작성/수정 → 사용자가 확인 후 영상 제작 회사 handoff. 사용자가 JSON 제안을 직접 만드는 현재 CLI의 한계를 해소한다. 질문/계획의 실제 판단은 AI 모델이 하고 정적 코드가 영상 질문을 하드코딩하지 않게 한다.

## 참조 및 기존 계약
- core/goal_dialogue.py : DialogueStore.create/propose/answer/revise/confirm/handoff_video/planning_goal.
- companies/video/goal_dialogue_cli.py : 기존 offline propose, CLI 및 저장 ID.
- core/autonomous_gemini35.py 및 core/gemini_provider.py : Gemini 3.5 모델 및 wire adapter, 검증된 정상 응답 형식.
- core/autonomous_live.py : 승인 준비/서명 검증, project 상태 해시, 호출 시도 원장 및 안전 정책.
- core/ai_safety.py, core/project_budget.py, core/uncertain_reservations.py : 호출/동의/예산/미확정 응답 보호.
- companies/video/video_production_company.py : 최종 요구 명세에 따른 영상 회사의 프로젝트 생성 및 기존 실행 동의 계약.
- tests/test_goal_dialogue.py, tests/test_v1_core.py 및 루트 AGENTS.md.

## 기능을 묶어서 구현
1. 범용 관리자 모델 응답 인터페이스: 현재 offline JSON 제안은 하위 호환 유지. 별도 live Gemini provider가 동일 구조(questions, sufficient, spec)로 응답. 독자적으로 누락된 필수 정보/선호/불확실성을 판단하고, 필요한 경우에만 한국어 질문 1~3개. 기존 goal_dialogue.py의 검증/근거/상태/중복/라운드 로직 재사용. 질문 고정 목록 금지.
2. 실제 사용자 CLI: create/show/answer/skip/revise/confirm/handoff 유지하면서 'ask-ai' 또는 동등한 명시적인 실행 명령과 'prepare-consent', 'approve-consent' 등 **동의 준비/사용자 확정** 경로를 제공. 질문·답변과 명세를 자연스럽게 확인할 수 있는 출력(원시 JSON 직접 작성 강요 금지). 제공자/모델/전송 범위/한도/동의 상태를 사람이 이해하기 쉽게 고지.
3. 외부 AI 질문 단계도 프로젝트 원래 목표, 기존 답변, 사용자 수정 사항을 원격 전송하는 행위이므로 기존 LiveCompany와 동등한 수준의 프로젝트별 명시 승인, 모델/endpoint 고정 검증, 무료/유료 비용 보호, 실제 호출 상한 및 예약 시도 원장 관리 필수. 단순 env 플래그, 입력된 'yes', API 키 존재만으로 승인된 것으로 취급 금지. 동의된 내용 외 전송 차단. 모델 실존/무료 쿼터는 당시 제공자 정책 확인 전까지 실제 요청 기본 비활성.
4. 기존 DialogueStore는 mode=goal_dialogue_offline_v1, simulation=True, real_ai 미허용이므로 여기에 무턱대고 live provider만 주입하지 말 것. 신규 별도 live 대화 모드/스토어나 명시적인 버전 스키마를 설계해 독립된 데이터·시도 기록/서명키로 보존하되 기존 오프라인 기록을 자동 변경·승격·재승인하지 않는다. 기존 데이터 스토어와 동의 기록/실패 시도 이력 보존. 중단 시 uncertain/reserved 상태 자동 재전송 금지. 무결성·재개 보장.
5. 동일한 기존 사용자 답변이 다음 Gemini 질문 입력에 반영되는지, 모델이 준비 완료를 판단하면 명세로 넘어가는지 검증. AI가 제시한 사실과 사용자가 명시한 사실 구분, 원본 goal / answer evidence 추적, JSON 검증 및 오류 처리. 승인된 확정 명세만 영상 회사로 handoff. 영상 제작 API 사용/영상 렌더 시작은 이번 작업에서 수행하지 않으며 별도의 기존 VideoProductionStore 승인 계약 필수.
6. 구현 UI는 간단한 CLI 중심. 대시보드/영상 퀄리티/경험 메모리/신규 영상 도구 개발 금지. 새 소스 파일/테스트는 최소한만; 구 보고서/일회성 코드 파일을 불필요하게 남기지 말 것.

## 안전 및 개발 방식
- **이번 개발 및 모든 테스트에서 실제 외부 AI API 호출 0회**. mock HTTP 응답으로 요청 구성·승인/해시 바인딩·호출 원장/한도·JSON 응답·네트워크 차단·명세 handoff를 시험.
- 이번 대화는 '개발을 진행'하라는 요청이지 Gemini 데이터 외부 전송이나 유료 비용 발생 승인이 아님. 승인 전 어떤 실제 호출도 금지.
- 기존 비용/동의/실제 프로젝트를 변경하거나 이미 처리된 시도를 재실행하지 말 것. Codespaces 별도 과거 데이터 보관본 접근·변경·삭제 금지. KST 유지. API 키·민감 입력 로그 출력 금지.
- 서명/권한 기능을 복사하는 경우 핵심 보안 조건을 약화하는 임시 우회 코드를 만들지 않는다. 기존 API 계약과 충돌 시 안전한 독립 설계로 해결하고, 불가능하면 구체적 장애와 다음 변경만 보고.
- Gemini API 현재 모델/가격/무료 여부는 개발 시 공식 문서로 확인하여 설정을 명확히 한다. 실제 API 통신 없이 모의 응답을 사용하고 실시간 이용 가능성을 확인했다고 주장하지 말 것.
- 사소한 단위별 테스트/보고 반복 금지. 코드 구현 마친 후 새 경로의 문답+사전 승인/실제 모델 시뮬레이션+영상 company handoff+기존 7개 회귀를 한 번에 통합 검증. 실패 시 수정을 하고 다시 묶어서 검증.

## 완료 기준
- 사용자는 JSON 파일을 작성하지 않아도 새 CLI에서 실제 AI 관리자에 질문을 요청하도록 준비/승인하고, 질문에 답하며 최종 명세를 확정할 수 있어야 한다. 실제 AI 동작은 mock 전송으로만 시뮬레이션하므로 사용자에게 별도 표시한다.
- 승인이 없는 실제 모델 연결은 불가능하고, 기존 offline 방식도 작동. 변경된 목표/답변에 연결된 전송 계약의 재승인 조건이 정확해야 한다.
- 공통 엔진→영상 회사 handoff 데이터가 바뀌지 않고, 실 제작 실행 권한을 자동 부여하지 않는다.
- README.md 및 docs/ARCHITECTURE.md는 실제 사용 명령과 제한만 간단히 갱신. docs/IMPLEMENTATION_STATUS.md 한 파일에 기능/통합 테스트/AI 실제 호출 0회/남은 운영 검증을 요약.
- 코드 변경과 통합 검증 후 main에 commit/push. 기존 원본 파일·백업/원장 삭제 금지.
