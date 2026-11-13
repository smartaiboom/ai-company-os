# AI 관리자 검토 후 후속조치 설계 (2026-11-13 KST)

## 목표
검토가 미달이라고 단순히 job을 중단하지 않는다. 관리자 판단 → 직원에게 구체적인 재작업 지시/재검토 → 다음 직원 인계, 혹은 대표에게 문제점·대안·추가 승인 필요성 보고로 이어진다.

## 현재 코드에서 확인한 문제
- core/autonomous_company.py의 validate_review는 accept/revise/stop/needs_operational_permission을 지원한다.
- 기본 상태 머신은 revise 시 직원의 state를 revision_requested로 변경하고 revision_feedback을 다음 직원 실행에 전달한다. 이미 max_revisions_per_task=1, max_total_revisions=1 제한이 있다.
- companies/video/representative_rework.py::_parse_role_content는 AI 관리자의 action=accept 시 goal_review 다섯 항목 중 하나라도 미달/근거 부족이면 rework_goal_not_met 예외를 발생시켜 이 정상 수정 흐름에 도달하지 못한다.
- 2026-11-13 10:22 KST 실제 재작업의 writer 대본은 성공적으로 작성되었으나 review는 HTTP200/unvalidated, 원본 review 응답이 저장되지 않았다. 실제 대본에는 근거 미확인 '1티어', '초보도 연승' 등의 주장이 있고, 게임에 관한 흥미로운 이야기 목표와 어긋날 가능성이 있다. 정확한 AI 관리자 실패 항목은 알 수 없다.

## 기대 운영 흐름
1. 품질 합격: goal_review의 목표 충족 및 근거 인용 유효 → 관리자 accept → 다음 직원에게 인계.
2. 품질 미달이고 수정 가능: 관리자 revise, 구체적인 잘못된 부분/근거/대표 피드백/목표/수정 완료 조건을 feedback에 작성 → 기존 revision_requested 흐름으로 직원 재작업 → 관리자 재검토. 승인된 API 호출 범위와 기존 수정 횟수 제한 반드시 준수.
3. 수정 불가/동일 문제 반복/수정 횟수 소진/판단 불확실: 대표에게 현재 결과물, 항목별 미충족 사유, AI 관리자 의견, 수정 방안, 추가 호출 승인 필요 여부 제시 → 사용자 판단 대기. 실패 상태로 소리 없이 끝내지 않는다.
4. HTTP503, 스키마 오류, 계정/서명 검증 실패 등 실제 운영 오류와 품질 미달은 구분하여 안전 중단. 자동 재시도 금지.
5. accept인데 goal_review 미충족: 성공으로 위조하거나 검증을 삭제하지 말 것. 실제 근거를 보존한 뒤, 안전하게 revise/대표 판단 대기로 전환할 수 있는 명시적인 정책과 테스트를 마련.

## 구현 및 사용량 규칙
- 기존 revise 상태 머신과 UI를 재사용. 별도 엔진·새 프로젝트·대규모 UI 재개발 금지.
- 모든 AI 검토 결함은 항목별 reason/status로 구조화하여 기록. raw API 키·민감정보·프롬프트 전문 저장하지 않음.
- 수정 요청은 명시적인 재작업 범위와 기존 정책에 의해 승인된 호출만 수행. 한도 초과 시 대표 승인 대기.
- 과거 실패 job/consent/grants/attempts 및 산출물 불변. 새 전송 계약은 새 동의. 오프라인 표적 테스트만, 실제 Gemini 호출0.
- 기존 코드의 최소 직접 GitHub 패치 우선, 로컬 데이터를 활용한 검증만 필요한 경우에 Codex 제한적 사용.

## 필요한 테스트
- accept+목표 충족 후 정상 인계.
- 목표 미충족 → 이유가 담긴 revise → 같은 writer 수정 → 재검토.
- 수정 한도 소진 → 대표 판단 대기, 추가 전송 없음.
- 운영 오류/불명확 응답을 품질 수정으로 오분류하지 않음.
- 원본 원장 무변경.