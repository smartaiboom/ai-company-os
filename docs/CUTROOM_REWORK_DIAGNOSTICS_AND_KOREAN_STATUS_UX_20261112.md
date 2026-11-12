# 컷룸 대표용 직관적 AI 진행 현황판 + invalid_dependencies 진단
2026-11-12 KST

## 현황 및 목적
현재 사용자 실제 재작업 job qualityprovider-3cb52d1ab205460897e9f03fea21ca71 은 UI에서 invalid_dependencies, 시도1, 새 재작업 완료 없음. 사용자: "내가 직관적으로 확인하기가 너무 어렵다". 기술 코드 대신 한눈에 현재 진행 단계·담당 AI·완료/중단·호출 기록·다음 행동을 알 수 있는 대표용 UI로 개선한다. 원본 프로젝트와 이전 수락된 미션01 v1을 보존한다.

## 주의
현재 시도1은 이전 환경차단 시도0과 다르다. 모델 호출이 실제 송신되었을 가능성이 있다. 유효한 추가 승인이 없는 한 실제 API 호출/자동 재시도/실패 시도 삭제/새 job 생성/과거 grant 재발급 모두 금지. 이번 Codex는 원장 읽기 진단, UI 구현, 오프라인 테스트만.

## 먼저 실제 원장 읽기 진단
동일 재작업 job의 저장된 provider 시도[0], phase, HTTP status, response hash, response parser, response receipt, error reason, sessions/active_operation, 이벤트 및 동일 컷룸 흐름 상태를 읽기 전용으로 확인. 핵심 필드만 보고하고 API 키·비밀 데이터 노출 금지. core/autonomous_company.py의 validate_plan 검증은 순차 tasks에 대해 depends_on이 *이미 앞에 나온 task ID*만, criteria_ids는 기획 criteria ID만, 중복 참조 금지이며 invalid_dependencies의 유력 발생 지점. 실제 AI 응답을 확인해 정확히 무엇이 잘못됐는지 판별하되 저장 원본을 변조하거나 재시작하지 말 것.

## 대표 UI 변경 목표
1. 컷룸 대표 피드백 재작업 영역: 한국어 단계 카드(동의 준비/AI 관리자 기획 중/대본 직원 작성/관리자 검토/스토리보드 직원 작성/검토/새 대표 승인 대기/실패·중단), 현재 담당 역할과 진행 단계, 최종 KST 갱신 시각, 분명한 완료/미완료 표시. job의 실제 phase/assignments/events/attempts에서 안전하게 도출하며 근거 없는 진행률이나 시간/호출 횟수 조작 금지.
2. 오류 한국어 번역 + 행동 안내: invalid_dependencies는 "AI 관리자가 작성한 업무 순서나 참조 관계가 유효하지 않아 기획안 검증에서 중단됐습니다. 새 대본은 아직 생성되지 않았습니다. 담당 개발 점검이 필요합니다."로 표현. gemini_execution_disabled, 동의 만료, 전송·모델 오류 등도 한국어로 설명. error code는 접힌 상세 정보에만 유지. 시스템 중단 시 재실행 버튼 절대 노출하지 않음.
3. 기존 미션01 작업 needs_user_review은 이전 버전 v1 보존/참조임을 명확히 표시하고 최신 재작업과 혼동하지 않기. 상단 기획 수정 요청 상태와 별도 AI 재작업 상태 사이의 혼란을 줄일 보조 문구.
4. 사용자 화면에서 실제 외부 호출 시도/완료/실패 여부를 구분하고 비용/무료 quota unknown 여부는 그대로 정직하게 표시. 보기 쉬운 UI 우선, 상세 ledger는 펼쳐보기. 새로고침은 데이터 조회만.
5. 새 호출 없는 미래 개선: 이번 invalid_dependencies가 모델이 잘못 계획한 것이라면 writer 먼저/editor 다음, depends_on은 선행 업무 ID만, criteria_ids는 존재하는 기준 ID만 쓰도록 다음 승인된 실행에서 모델 contract를 명료하게 하는 최소 수정 검토. 현재 실패 job에 대해서는 자동 보정/몰래 재시도 금지. 모델 응답이 의심 원인과 다르면 실제 원장 근거로 판단.

## 검증/결과
오프라인 표적 테스트: stopped invalid_dependencies attempts1/이전v1, running, completed 각 화면 구별, 실제 전송0/재실행 버튼 비노출, node --check. 전체 suite 반복 금지.
reports/CUTROOM_REWORK_DIAGNOSTICS_AND_KOREAN_STATUS_UX_RESULT_20261112.md 단일 짧은 보고에 실전 attempt1 진단(성공/HTTP·validation 단계), UI 변경 파일/동작, 표적 테스트, API0회, 대표 다음 행동. main commit/push/readback 후 종료.
KST, AGENTS.md 준수, 기존 data/backups/artifacts/.env 및 프로젝트·서명·동의·attempt·대본·오디오·동영상·미추적 파일 보존. git clean/reset --hard/force push 금지.