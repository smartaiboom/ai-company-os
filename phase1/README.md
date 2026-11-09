# AI Company OS — Phase 1

A small, dependency-free starter for project management and saved state.

## What is included
- Create and list projects
- Open a project and update its status
- Save project state to JSON
- Store artifacts in a project-specific folder
- Resume by reopening saved project state

## Run
From this folder:

```bash
python app.py
```

Then open the URL printed in the terminal (default: http://127.0.0.1:8000).

## Data safety
All new data is written only under this folder's `data/` directory.
This starter does not access, move, or modify files from the existing AI Company OS project.
The default mock mode makes no external AI requests. Real AI mode sends data to the configured provider when planning or executing tasks.

## Phase 1 acceptance checks
1. Create a project.
2. Refresh the page; the project remains listed.
3. Open the project and change its status.
4. Restart the app and confirm the status remains saved.
5. Confirm the project has its own artifacts directory.


## 실행 엔진 설정

기본 설정은 `AI_ENGINE=mock`이며, 외부 API를 호출하지 않는 모의 실행을 사용합니다.

OpenAI 호환 Chat Completions API를 연결하려면 Codespaces의 환경변수 또는 비밀 저장소에 다음 값을 설정합니다.

- `AI_ENGINE=openai_compatible`
- `AI_API_BASE_URL`: OpenRouter API 기본 URL (`https://openrouter.ai/api/v1`)
- `AI_API_KEY`: 제공자가 요구하는 API 키
- `AI_MODEL=openrouter/free`: 실제 요청에 허용되는 유일한 모델 ID
- `AI_API_TIMEOUT`: 선택 항목, 요청 제한 시간(초), 기본값 90

`openai-compatible` 별칭도 같은 실제 실행 모드입니다. 화면에는 현재 모드와 외부 전송 안내가 표시됩니다. 계획 작성 또는 작업 실행 시 프로젝트 목표, 작업 지시, 필요한 입력 자료 및 선행 결과가 설정한 외부 제공자에게 전송될 수 있습니다. 화면 조회만으로 AI 요청을 보내지는 않습니다.

실제 요청 전에 모델 ID가 정확히 `openrouter/free`인지 검사하며, 값이 없거나 다르면 중단합니다. 유료 모델 전환이나 fallback은 없습니다. 지원하지 않는 실행 모드도 요청 전에 오류로 중단합니다. API 키를 소스 코드나 Git 저장소에 기록하지 마세요. 설정 오류나 API 호출 실패는 성공으로 처리되지 않습니다. 실제 AI 응답 역시 별도 검증이 필요합니다.

### 실제 호출 안전 경계 (M2)

실제 요청은 기본 비활성입니다. 위 엔진 설정만으로 송신하지 않으며, 향후 M4에서 구체적 전송 자료와 한도를 사용자가 별도 승인해야 합니다. 서버 활성화와 프로젝트별 목표 지문·전송 범위 동의가 모두 필요합니다. 화면의 '실제 무료 AI 시작·재개'는 동의를 새로 만들거나 활성화하지 않습니다.

계획과 수동/연속 업무 요청은 공통 검사와 프로젝트별 영속 예산을 사용합니다. 정확한 OpenRouter HTTPS 주소만 허용하며 리다이렉트·유료 fallback은 없습니다. 새 프로젝트 기본 20회(기존 명시 한도는 유지), 시작·재개당 최대 2회로 전송 전에 시도를 예약합니다. 실패·타임아웃도 소비하며 미완료 예약은 재시작 후 자동 재전송하지 않습니다. 입력 JSON 최대 128KiB, 응답 최대 256KiB, 출력 최대 4096토큰(계획은 3000), 제한 시간 최대 90초입니다. 승인 대기·실패·한도에서 멈추고 화면에 잔여 예산과 이유를 표시합니다.

M2의 실제 경로는 모의 전송으로만 검증했습니다. 실제 API 연결은 후속 단계이며 현재 mock 전용 자동 진행·수정 기능도 유지합니다.

## mock 협업과 확정본 다운로드

기본 mock 모드에서 목표 입력 → 관리자 계획 작성·사용자 승인 → 자동 진행 시작·재개로 업무를 처리합니다. 선행 결과의 사용자 승인이 필요하면 멈춥니다. 모의 형식 검사는 제목 존재만 검사하며, 수정 필요 결과에는 명시적으로 '수정 1회 및 재검토'를 요청할 수 있습니다. 일반 mock 엔진이 의견을 이해해 결과를 개선하는 것은 아닙니다.

마지막 결과도 사용자가 검토·승인해야 확정됩니다. 상세/보고서 화면의 'Markdown 확정본 다운로드'는 현재 유효한 확정 버전만 제공합니다. 목표·결과·승인 근거가 바뀌거나 보관 파일이 손상되면 다운로드를 거절하며, 기존 JSON 버전은 보존합니다. 다운로드와 화면 조회는 프로젝트 JSON이나 보관 파일을 수정하지 않습니다.


### 의미 검토와 사용자 승인 수정 (M3)

계획 승인 후 품질 업무 실행 전에 상세 화면에서 대상 업무 ID, 바로 다음의 `품질 검토 담당` 업무 ID, 성공 기준(1~8줄)을 사용자가 승인합니다. 목표 도메인에 맞는 기준을 입력하며 별도의 최종 보고 업무가 있어야 합니다. 이 승인은 M2의 외부 전송 동의·서버 활성화를 대신하지 않습니다. 실제 요청은 여전히 기본 차단입니다.

대상 결과를 사용자 승인한 뒤 ‘의미 검토 시작·재검토’를 실행합니다. 구조화된 판정은 `pass`·`changes_needed`·`inconclusive`와 기준별 근거·위험·제안을 포함하며 전부 모델 주장입니다. 독립 사실 검증이나 사용자 승인이 아닙니다. 빈/잘못된 응답, 오래된 결과·입력 지문, 판정 불가는 통과하지 않습니다. 기존 mock 제목 형식 검사와 별도입니다.

수정 필요 시 대상 ID·기존 승인·의견·남은 API 예산을 확인하고 ‘수정 요청 승인’ 또는 거절을 선택합니다. 승인 전에는 기존 승인을 유지합니다. 승인 후 대상 담당 업무를 한 번 실행하고 사용자가 재승인한 뒤 같은 품질 담당이 한 번 재검토합니다. 수정·검토 예약과 실패는 자동 재시도하지 않으며 프로젝트당 대상 하나·수정 한 번·재검토 한 번입니다. 기존 mock 수정 예약은 유지합니다.

의미 검토는 별도 추가 직원 호출 대신 기존 품질 업무의 실행입니다. 4단계 계획 fixture는 계획 1 + 최초 두 업무 2 + 의미 검토 1 + 수정 1 + 재검토 1 + 최종 업무 1 = 총 7회로 M2 예산을 지킵니다. 이 예시는 7회로 제한한 과거 fixture이며 새 프로젝트 기본 한도는 20회입니다. 더 긴 계획이나 다른 수동 호출은 예산을 먼저 소모할 수 있습니다. 최신 의미 검토 pass 및 사용자 승인을 거쳐 최종 확정한 동일 보관본을 Markdown과 JSON으로 다운로드합니다. 구형 프로젝트는 의미 검토 설정 없이 기존 흐름을 유지합니다.

M3도 격리된 모의 전송·HTTP 검증만 수행했습니다. 실제 모델의 의미 품질, 무료 제공자 가용성과 브라우저 조작은 M4 별도 승인·인수 조건입니다. 새 외부 도구·검색·코드 실행 기능은 없습니다.

### 프로젝트 추가 호출 예산

기본 20회는 OpenRouter 무료 할당량이나 비용을 보장하지 않습니다. 한도 변경은 실제 실행/외부 전송 동의와 별개이며 실패·시간 초과·예약도 소모합니다. 명시 저장된 과거 한도(예: 7회)는 자동 상향하지 않습니다.

예산 소진 시 공통 요청 경로는 외부 전송 전에 멈추고 추가 예산 요청을 저장합니다. 예상 부족은 소유자가 확인된 로컬 도구 `app.prepare_project_budget(project_id, usage_plan)`로 점검합니다. usage_plan은 `[{"purpose": "추가 검토", "calls": 5}]` 형식이며 AI 추론이 아닌 호출자 제공 예상치입니다. 직접 제안은 `app.request_project_budget(project_id, additional, reason, usage_plan)`을 사용합니다.

`app.project_budget_requests(project_id)`에서 요청 사유·추가 횟수·현재 사용량·상태·stale·expected_hash를 확인합니다. 실제 사용자 결정을 확인한 로컬 운영 도구만 `app.decide_project_budget(project_id, request_id, expected_hash, "approve" 또는 "reject", user_confirmed=True, reason="사용자 결정 근거")`를 호출합니다. 공개 HTTP 증액/승인 경로는 없습니다. 제안 자체나 모델 주장은 승인이 아닙니다.

승인 시 요청한 횟수만 증가하며 한 요청의 추가량은 1~50회, 프로젝트 절대 한도는 200회입니다. 중복·동시·변조·오래된 증액 승인은 거절합니다. 오래된 요청도 유효한 서명과 명시적 사용자 거절로 정리할 수 있으나 예산은 바뀌지 않습니다. 로컬 서명 키는 Git 제외 data/.budget-approvals에 보존하며 삭제/초기화하지 않습니다. 한도 20회 초과에는 사용자 증액 서명이 필요합니다. 실제 호출은 기존 모델·동의·예약·시작당 2회 검사와 미확정 예약 차단을 계속 거칩니다.
