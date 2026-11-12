# AI Company OS — 재기획 검증 장애를 끝내고 대본까지 가는 최소 구현 (빠른 경로)
작성 2026-11-12 KST

## 최우선 사용자 목표
"대본, 영상, 음성 품질 향상이 큰 문제인데 또다시 개발 수정에 뺑뺑이 돌고 있다." 기능을 추가하는 게 아니라 **재작업 AI 관리자가 실제 기획을 수락하고 writer/editor에 전달하여 새 대본을 대표에게 제출**하는 데 집중한다. 기존 제작·음성 기능 훼손 금지. 이번은 한 번에 근본 원인 방지/검증, 불필요한 개발 UI·감사 기능 증설 금지.

## 확정 사실
현재 실제 미션01 컷룸 rework job qualityprovider-3cb52d1ab205460897e9f03fea21ca71 은 stopped/invalid_dependencies, phase=plan. Gemini 호출1(HTTP200/completed, JSON parsed, 서버 기획 검증 실패), 새 대본·storyboard 없음. 원 응답은 SHA만 남고 전문이 없어 정확히 어떤 depends_on/criteria_ids가 잘못됐는지는 불명. **실패 job/동의/시도 원장 불변 보존, 다시 실행 금지.** 사용자에게 이전 결과를 성공으로 위장하지 말 것.

코드 관측: core/autonomous_company.py validate_plan은 tasks 순서에 따라 depends_on은 앞선 task ID만, criteria_ids는 criteria ID만 허용하고 중복 불가, 모든 기준은 최소 한 업무가 사용해야 함. companies/video/representative_rework.py NOTICE는 writer→editor만 지시하지만 실제 생성 스키마는 '일반 계획 1~8 tasks'를 허용해서 모델이 위반할 여지가 있음. 또한 plan phase의 재기획 replan은 원 목표/피드백을 반영해야 함.

## 구현 범위 (이 순서)
1. 기존 프로젝트·모듈의 실전 기획 계약과 검증 함수/응답 스키마를 한번 확인하고, **rework plan phase만** 모델이 따라야 할 관계를 한곳에 명료히 정의: 정확히 2개 task (writer 다음 editor), 고유 ID, writer.depends_on=[], editor.depends_on=[writer ID], criteria ID 존재/고유, 양쪽 criteria_ids는 기획 기준 중 존재하는 값만, 모두 사용, no forward references, replan의 selected_topic/duration/feedback_response 원목표 일치. AI 모델에게 명시 전달하고 가능하면 JSON schema에서도 범위(항목 수 등) 제약하되 공급자/기존 strict schema 호환성 파괴 금지. 다른 회사/미션 plan validator 전체 완화하지 말 것. 비결정적 plan/task ID와 criteria는 AI가 생성하게 하고, 애플리케이션이 응답을 조용히 자동 수정해 성공 처리하지 말 것.
2. plan 결과가 **정상 JSON이지만 의존성 검증에 실패한 경우** 검증자가 어떤 업무와 어떤 필드가 틀렸는지 구체적으로 진단(미래 전용, 기존 과거 원본 회복 주장 금지). 다음 실행에서 AI 관리자에게 그 오류를 전달해 **승인된 호출 예산 안에서만** 올바른 계획을 재작성할 기회를 주는 설계가 안전하게 가능한지 확인해 최소 구현. 이 때 추가 모델 호출은 새로 시작된 별도 동의된 실행 범위에서만, **최대 1회 교정**/예산에 포함, 무단 네트워크 재시도 금지. API 응답이 오류나 송신 불명/쿼터일 때 재시도 금지. 기존 실패 job 재개 불가 유지. 일반 자유형 기획 문제와 이 미션 구조형 계획 문제를 구분. 1회 수정을 지원하는 구조 변경이 지나치게 크다면 **명시적 prompt + 엄격 검증 + 원인 기록**만 구현하고 보고서에 '교정 호출은 미구현'으로 솔직히 기록하라. 억지로 안전성 우회하지 말 것.
3. 전후의 **실제 목표 적합성 품질** 관문 유지: 게임 쇼츠 '만드는 방법'이 아니라 실제 게임 소재를 다루는 흥미로운 쇼츠여야 함. 선행 연구 자료 검증 수준 이상 단정 금지. 관리자가 주제를 재해석하고 writer가 대본, editor가 storyboard, manager가 각각 검토하여 같은 컷룸에 계획 v2 제출. 품질 검증을 우회하여 빈 대본/예시 대본으로 제출 금지.
4. 이미 종료된 기존 job의 불명 시도를 지우거나 기존 grant 재사용해 새 실행하지 말 것. **새 재작업 실행**은 대표의 새 승인 범위/서명과 별도 job을 필요로 한다. 현재 컷룸 UI에 사용자에게 이해 가능한 다음 경로(새 수정판 요청 준비/승인/시작)를 *필요한 최소 범위만* 열 수 있는지 확인; 기존 검증 실패 후 재시도 버튼으로 옛 job을 실행하는 UI는 금지. 새 승인 전 실제 외부 요청0회. 자동화 복잡성이 크면 범위/절차만 명확히 보고.
5. 외부 호출 없이 단 1개의 유의미한 **오프라인 표적 종단 테스트**: 잘못된 depends_on / criteria_ids 거절 및 구체 사유 → 유효한 관리자 plan → writer/editor→manager review→같은 컷룸 v2 승인 대기; 정상 구조/원목표 품질 기준 유지, 기존 실패 원장 불변, 실API0. 실제 원본 대본/v1은 보존. 전체 suite, 대규모 UI 리디자인, 불필요한 테스트·문서 생성 금지.
6. 결과는 reports/REWORK_FAST_TRACK_PLAN_VALIDATION_TO_SCRIPT_RESULT_20261112.md 한 파일에 **짧게**: 수정 파일/실제 원인 개선/목표까지의 남은 차단(특히 새 동의 및 향후 실제 호출), 오프라인 종단 결과, 이번 실전 호출0, 다음 대표의 단순한 컷룸 단계. main commit/push/readback 후 즉시 종료.

우선 AGENTS.md 준수. core/ 기존 엔진/공통 모델 자유도 과도 수정하지 않고 rework path에만 구현. KST. 기존 data/backups/artifacts/.env/서명키/이전 plan·video·audio/실제 ledger/미추적 파일 삭제·변조 금지. git clean/reset --hard/force push 금지. 새로운 유료 모델이나 전송 정책 변경/실제 API 호출 금지. 어려우면 최소 변경·명확한 미완료 보고, 목적 없는 재설계 금지.
