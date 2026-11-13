# 2026-11-13 — 503 중단 이후 새 대본까지, 최소 연결만
KST 2026-11-13. AGENTS.md 준수.

## 우선순위
대표의 원래 목표는 **흥미로운 실제 게임 쇼츠**다. 대본/영상/음성 품질 향상이 본 목표인데 반복 오류 개발로 지연됐다. 이번 작업은 **실제 새 대본 v2를 컷룸 대표 검토에 제출하도록 막힌 연결을 제거하는 최소 수정**이다. 새로운 UI 리디자인/대규모 보고/예산·영상·음성 기능 변경 금지.

## 이미 확인된 실제 사례
2026-11-12 16:41:21~16:41:23 KST Gemini plan 요청 결과 HTTP503, `provider_unavailable`, failed, `role_result_status=unvalidated`, response_hash null, request_hash bc787bb74af99b6a97cce47f3c5d4bd20a66c94c41d7136d423ba2a89439512a. **실제 전송 시도 1회**, 유효 기획안 및 새 대본 없음. 그 이전 별도 실패 `qualityprovider-3cb52d1ab205460897e9f03fea21ca71`의 `invalid_dependencies` HTTP200 역시 보존. 기존 그 2건의 job/consent/grant/attempt를 수정·초기화·재실행·자동 재시도하지 않는다. 새 사용 승인 없이 실제 외부 Gemini 호출0회.

## 사전 진단/실제 구현
1. **읽기 전용 현재 로컬 상태 확인**: 현재 503 rework job ID/phase/status, latest flow rework 상태, request completion vs active_operation/reservation, 기존 decision/plan v1 hash, 유효 계약 버전/동의·서명, 환경 플래그 설정 여부를 키 노출 없이 확인. 실제 로컬 데이터가 다르면 로그 기반으로 판단. 어떤 신규 작업도 송신 없이 시작해야 한다.
2. **503 후 별도 승인 경로 최소 연결**: 같은 컷룸의 현존 재작업 상태가 `stopped/provider_unavailable`, 이전 요청의 응답 HTTP503과 최종 실패 원장 명확, 네트워크 예약/전송 미확정 없음, 그 외 중복/보안 조건 통과할 때만 **'새 AI 재작업 준비' → 새 전송 범위 동의 → 'AI 재작업 시작'**이 가능하도록 한다. 절대 기존 실패 job을 다시 run하지 않고 **새 job, 새 독립 서명 consent/grant**를 사용. 기존 구상해 둔 `prepare_new_rework` 및 현재 UI/서버 재작업 흐름을 재사용하며, 새 사유가 503인 경우에만 제한적으로 확장. 성공/실패 history와 원본 피드백 보존. 무제한 반복 신설 금지: 동일 오류에 대해 이전과 **완전히 동일한 변경 없는 실행**을 다시 반복하게 하지 않고, 재실행 횟수/새 범위를 대표가 선택할 수 있게 준비만. 후속 장애에도 자동 재시도 없음.
3. **사전 확인**: `GEMINI35_AUTONOMOUS_FREE_ENABLED=1`, MODEL/ENDPOINT/key binding, 미확인 실제 무료 quota/billing, 기존 외부 전송 동의 만료 및 새 grant 필요 고지. 가능하다면 공개 상태는 별도로 검토하되 Gemini 가용성 확인만을 위한 **테스트 API 요청도 사용자 승인 전 금지**. 유료 모델 변경·fallback 금지. 실제 Gemini 503이 재발할 수 있음을 숨기지 말 것.
4. **관리자/직원 실제 대본 경로 유지**: 강화된 plan 구조(writer 1명 → editor 1명, criteria 유효 참조), 원 목표+대표 수정 요청 반영 검증, 대본 및 storyboard/manager review 후 같은 컷룸 v2 awaiting_plan_approval. 대본을 하드코딩하거나 offline fixture를 실전 성공으로 가장하지 않음.
5. **오프라인 표적 종단 통합 테스트 1개**: 임시 503 응답 기록이 있는 stopped job(실전과 동등한 final failed attempt/원본 grant) → 새 준비/별도 동의/독립 job → Gemini 합성 응답 manager/writer/editor → v2 대표 승인 대기. history 무변경, 503 아닌 오류/uncertain/reserved/이미 사용된 중복 계약은 거부, 실제 외부 API 0회. 포괄 전체 테스트 금지.
6. 단일 짧은 보고 `reports/REWORK_503_SAFE_NEW_RUN_TO_SCRIPT_RESULT_20261113.md`: 실제 503 job 진단, 변경 파일, 새 컷룸 버튼/절차, 오프라인 테스트, 실제 API0, 사용자 다음 단계. main commit+push+원격 확인 후 **중단**.

## 사용자 경험
대표가 F12를 열거나 코드를 실행하지 않고 컷룸에서 503 사유를 쉬운 한국어로 보고, 이전 대표 피드백을 재입력하지 않고 새 실행 범위를 승인해 스스로 새 시도를 시작할 수 있어야 한다. 다만 실제 Gemini 전송에는 사용자의 명시적 컷룸 동의·시작 행동이 필요하다.

보안/보존: 기존 `data/`, `backups/`, `artifacts/`, `.env`, 완료된 동영상·음성, GitHub commit 및 미추적 파일, 서명키·원장 그대로 보존. git clean, reset --hard, force push 금지. KST. 실제 API 호출/유료 전환/모델 변경/자동 재시도 금지. 변경이 필요 없으면 구현했다고 꾸미지 말고 정확히 상태와 다음 경로를 보고.
