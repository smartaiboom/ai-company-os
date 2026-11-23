# 일반 조사·기획 Gemini 공급자 오류: 안전 진단·중단 이후 이어가기 (2026-11-23)

## 실제 운영 현상
모바일 게임 3종 조사 대상 project company-062d79eeabeb4e5baab3d60ec462db5f, 최신 조사 v5 실행 중 컷룸 오류:
"Gemini 호출 또는 응답 확인 중 중단됐습니다. transport_or_response_failed · Gemini 호출·응답 · 공급자 오류 응답 · Gemini 예약 2회·완료 1회, Tavily 예약 0회·완료 0회 · 공급자의 실패 응답이 기록됐습니다. · 현재 조사 상태에서 복구 가능 여부를 확인하세요."
대표는 무료/승인된 총예산 안에서 충분히 조사하길 원하며, 정상 요청에 임의의 소량 제한을 두지 말라는 정책 확정. 다만 **실패·전송 미확정 요청의 무단 자동 재시도는 금지**한다. 원본 모든 v1-v4 보고서, 현재 v5 관측, 서명, 원장, 사용자 결정을 보존. 사용자에게 재실행 버튼을 마구 누르게 하지 말 것.

## GitHub 코드 1차 발견
companies/video/research_workflow.py research_diagnostics는 실패 operation/response_received/category/code 및 일부 usage를 반환하지만 HTTP status/provider_response 노출은 연결 여부에 따라 제한. recovery_status / recovery_offer 는 기존 일부 경로에서만 구현. status()의 조건 'if ledger and not review and not base.get("mode")'에 의해 **general research report mode에서는 recovery와 replan을 전혀 표시하지 않음**. 별도 recovery_offer는 research-[0-3] 정규식, 고정 ROUNDS=4, 결정 검증 rejection/decision_receipt 기반만 허용하므로 Gemini 공급자 오류 또는 adaptive sample의 여러 단계에서 복구 불가. research-run은 'not store.attempts()'라 단순 재실행도 차단.

## 작업 순서
1. 현재 실제 v5 로컬 ledger, Gemini attempt, 공급자 응답의 HTTP status, provider_error_type/message(민감내용 최소화), 'response_received' 및 usage 기록, 첫 성공 단계의 관측 여부와 다음 단계 인덱스, 현재 grant/work 예산/만료 확인. 오류가 429(쿼터), 401/403(인증/권한), 5xx(공급자), 모델 부적합/JSON 응답, 네트워크 모호/중복 위험 가운데 무엇인지 **증거로 구분**하고 직접 원인 불명은 미확인. 이전에 성공한 실제 요청과 도구 관측 기록은 전부 보존. 인증키·원문 데이터 노출 금지.
2. 이미 실패한 Gemini 요청은 HTTP 응답이 있었더라도 공급자 모델이 출력을 생산/과금했는지 미확정일 수 있으므로 **같은 payload를 자동 재전송하지 않음**. 실패를 '단순한 검사 오류'로 간주해 기존 예약을 되돌리거나 재사용하지 않음. 429/401/403/결제 오류/현재 공급자 중단 징후는 그대로 중지. 응답 자체를 검증 가능한 경우에만 기존 기록을 활용.
3. 운영 모드 일반 조사에도 **안전한 후속 작업 연계**를 설계. 원래 실패한 단계 복구가 가능한지와 불가능한지를 구별. 실패한 정확히 같은 요청을 retry하는 대신, 정식으로 별도 계획/새 서명된 요청·명시 승인된 범위 내에서 *완료된 이전 단계의 관측을 읽기 전용으로 승계해* 이후 작업을 이어갈 수 있도록; 모든 새로운 실제 요청은 고유 ledger 기록, 승인된 공급자·모델·전송 자료·총 예산 차감, 반복 무한 루프 방지. 동일 이미 완료된 Gemini 단계를 다시 호출하지 않는다. 원래 업무 전체 승인 잔량을 임의 유출/이월하지 않는다. 새 권한·공급자·데이터 유형·예산이 필요할 때만 사용자에게 **한 번의 구체적 승인**. 기존 완료 자료만으로 관리자가 보류 보고서를 만들 수 있다면 추가 호출 없이도 보류 가능하게 검토.
4. 사용자 UI에는 '실패 유형/이미 완료된 단계/사용 가능한 근거/사용된 한도/이어가기 가능 여부 및 다음 행동'을 간결히 보여주고 일반 조사 모드에서 무조건 '복구 여부 확인' 문구만 표시하지 않도록. '이어가기'는 실제로 안전하고 구현된 경우에만 제공. 금지된 오류 자동재시도 버튼처럼 보이지 않게.
5. 실사용 복제 환경에서 완료 1회 + 공급자 오류 1회 + 관측 자료/승인 존재를 모의하여, (a) 일반 조사 모드의 복구 상태, (b) 동일 실패 요청 자동 재전송 0, (c) 보존 정상 결과 이어받기, (d) 한도/권한/새 서명/전송 안전, (e) 429·401·403·503·응답 모호 중단, (f) 실제 게임 3종 판정과 v4 데이터 보존, (g) 새 검토 요약 공개는 사용자가 별도 허용할 때만, (h) KST, (i) 로컬 컷룸 상태 표시를 통합 검증. 재시도에 실제 외부 API 사용하지 말 것. **이 작업에서 새로운 Gemini/YouTube/Tavily 호출 0회** unless already explicitly approved and verified to match exact newly requested call; default no external calls.
6. 개발 완료 후 보고서 reports/GENERAL_RESEARCH_GEMINI_FAILURE_CONTINUATION_RESULT_20261123.md에 직접 진단 사실, 운영 복구 가능성, 오프라인/실제 구분, 이후 사용자 행동 단 1개, 민감정보 없는 실패/성공 합계 및 남은 과제 명확히. 관련 코드·테스트·보고서만 commit/push main, GitHub remote SHA 확인. 기존 data/backup/.env/consent/ledger 수정·삭제/기존 서버 종료 금지.

## 완료 판정
실제 공급자 오류 원인과 복구 가능 범위를 확인했고, 일반 조사·기획 작업이 **이전 성공 작업을 재호출하지 않고** 안전하게 계속될 수 있도록 작동 검증(오프라인)된 상태. 코드 수정 성공과 **실제 v5 조사 완료를 절대 혼동하지 말 것**. 사용자에게 같은 정보를 반복 확인시키지 말 것.
