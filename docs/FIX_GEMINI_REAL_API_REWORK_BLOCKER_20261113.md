# AI Company OS — 실제 Gemini API 장애 해결 집중 작업 (2026-11-13 KST)

## 이번 목표
사용자는 한 달간 AI Company OS를 개발했지만 **첫 대본은 실제 API로 만들었는데 대표 재검토의 AI 관리자 재기획만 계속 중단**되어 지쳐 있다. 추가적인 진단 지시서·새 승인 UI·job 복구·무료 키 반복 확인·범용 기능 추가는 하지 않는다. **실제 성공했던 호출과 현재 실패 호출의 차이를 근거로 API 연결 장애를 가능한 범위 내에서 코드로 개선**한다. 오프라인 성공을 실제 Gemini 성공이라고 보고하지 않는다. 실제 호출은 이번 Codex 작업에서 **0회**이며 기존 진단 1회 승인도 이번 지시에서는 소진하지 않는다.

## 확정 현황
- 11/12 16:06 KST rework plan: Gemini HTTP200, 33,985 bytes, 실제 입력 9,743 tokens, 출력 1,549, 이후 서버 validate_plan의 invalid_dependencies 실패. **재기획 단계에서도 실 API 통신 성공한 적 있음**.
- 11/12 16:41, 11/13 09:17: rework plan HTTP503 각각, 36,671 bytes 동일 실제 payload(다른 job ID만), 각 전송 2초 후 실패. 서버 response body / request ID가 보존되지 않아 503의 상세 Google 원인은 불명.
- 코드: `core/autonomous_free.py::_request_json` HTTPError 분기에서 `exc.close()` 전에 body를 읽거나 sanitize해 저장하지 않음. `companies/video/representative_rework.py::_prepare_payload`는 `generationConfig.responseJsonSchema`와 `contents[].parts[].text.output_contract`에 동일 2.6 KB JSON Schema를 중복 포함. 다른 공통 계약에도 중복될 수 있으니 임의 삭제/변경 금지.
- 최초 '대본 작성' 성공한 job의 정확한 모델/토큰/req path/응답 성공 분량은 **로컬 ledger에서 비교해야 함**, GitHub 보고서만으로 단정 불가.
- 기존 결제/키/무료 프로젝트는 여러 차례 사용자 확인했고 재차 요청하지 말 것. 실제 호출은 별도 승인된 전송만. 중단 job 원장 불변.
- 기존 1회 최소 합성 문장 진단 승인은 이미 존재하지만 **호출0, 무료 계정 독립 검증 불가로 진행 안 함**. 이를 우회해 새 테스트를 실행하지 말 것.

## Codex 작업 절차 (단일 기능 묶음)
1. **성공·실패 실제 로컬 ledger 비교, 읽기만**: 최초 성공한 AI 대본 job을 정확히 찾아 provider/model/api path/HTTP 상태/요청 크기/시각/구조와 11/12 HTTP200 rework plan 및 두 503을 비교. 'success'가 다른 모델이었으면 숨기지 말 것. 기존 기록으로 모르는 점은 '미확인'으로. 503은 Gemini API HTTP 응답이고 response hash null임을 확인. 기존 state/approval/signature 비변경.
2. **실질적인 문제를 바로잡는 최소 코드 수정**:
   - core request error handling에서 HTTPError의 body를 **한 번만 상한 작게(예: 4~8KiB) 읽고**, 예상 JSON 오류만 strict parsing해 공개해도 안전한 error.status / error.code / 분류된 reason 정도만 ledger에 기록. raw error message, API key, Authorization, request payload, prompt, goal, feedback, headers 전문, 민감 ID 저장/노출 금지. HTTP 503 등 4xx/5xx의 origin/error code를 구분하여 'Google UNAVAILABLE' 같은 구조 진단 확보. 성공/일반 에러 처리 훼손 금지, except path에 새로운 네트워크 호출 불필요. 기존 동작대로 exception close, rate-limit & retry-after 처리, status='failed', 1회 차감, 자동 재시도 0.
   - 과거 503 body는 복구 불가능하다고 명시. Error logging change 자체가 503 해결이라고 말하지 말 것.
   - **재기획 요청이 크고 JSON schema가 2회 복제됨**: 기존 payload 생성·검증·서명 바인딩/consent에 대한 보안 영향과 Gemini API schema 요구를 확인하고, 가능한 경우 rework-plan 전용에서만 중복을 제거해 전송량을 줄일 것. **서명 범위/전송할 내용 변경이면 기존 동의 재사용 금지, 새 plan contract hash/독립 신규 job 승인 없이 실제 송신 금지**. 최소 수정이 안전하지 않으면 출력 구조 변경 없이 '제약상 미수정'으로 보고. 품질 검증 규칙과 input content 훼손, 결과 JSON schema validation 완화 금지.
   - 호출 성공 경험과 동일한 adapter/transport path가 실제 재기획에도 연결되는지 확인하고, 구체적으로 확인된 잘못된 설정/코드만 수정. Google 오류 503을 단지 요청이 커서라고 추정해 억지 수정하지 말 것.
3. 표적 테스트 1개 혹은 적은 수를 묶어 1회 실행: fake HTTPError(503 body에 UNAVAILABLE/민감한 message 포함)를 반환하는 합성 transport로 1회의 failure ledger / 상태 / 안전한 코드 추출 확인, 서버 정상200 schema response 회귀 확인. 실제 Gemini 외부 호출0. 필요시 새 payload만 크기 hash 출력, old signed contract와 drift 체크. 기존 검증 완료 코드 및 old job state 그대로 유지.
4. **마지막에 사용자에게 필요한 단일 다음 행동**을 보고하라. 조건이 안전하게 충족되면 새로운 서명/대표 동의가 필요하다는 것을 설명하고, 기존 실패 job 자체를 절대 재실행하지 말 것. 503이 재발해도 새 오류 코드가 남도록 한 것이 핵심 관측 개선. 실제 제공자 문제로 보이는 경우 그 한계를 솔직히 인정할 것. 별도 무료 승인/새 API 호출/타 모델 테스트 금지.
5. `reports/FIX_GEMINI_REAL_API_REWORK_BLOCKER_RESULT_20261113.md`에 ① 최초 성공 호출 대비 재기획 실패 핵심 차이 ② 실제 수정/미수정 및 이유 ③ 오프라인 테스트/호출0 ④ 다음 행동 하나만 간결히 작성. main commit/push/readback. 결과는 사용자에게 ChatGPT가 GitHub에서 바로 조회할 것.

## 보존 및 금지
AGENTS.md, KST, 기존 data/backups/artifacts/.env/모든 job/consent/grants/attempts/서명·음성·영상·미추적 파일 불변. Git clean/reset --hard/force push 금지. 실제 provider 호출0, 대체 모델/유료 전환/오토 retry0. **핵심 목표: 실제 AI 관리자→직원 호출을 안정화**, 부가기능 개발 전면 보류. 실제 가능한 수정을 한 번에 끝내고 반복 작업 지시서를 만들지 말 것.
