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

계획과 수동/연속 업무 요청은 공통 검사와 프로젝트별 영속 예산을 사용합니다. 정확한 OpenRouter HTTPS 주소만 허용하며 리다이렉트·유료 fallback은 없습니다. 기본 최대 7회, 시작·재개당 최대 2회로 전송 전에 시도를 예약합니다. 실패·타임아웃도 소비하며 미완료 예약은 재시작 후 자동 재전송하지 않습니다. 입력 JSON 최대 128KiB, 응답 최대 256KiB, 출력 최대 4096토큰(계획은 3000), 제한 시간 최대 90초입니다. 승인 대기·실패·한도에서 멈추고 화면에 잔여 예산과 이유를 표시합니다.

M2의 실제 경로는 모의 전송으로만 검증했습니다. 실제 API 연결과 의미적 품질 검토는 후속 단계이며 현재 mock 전용 자동 진행·수정 기능도 유지합니다.

## mock 협업과 확정본 다운로드

기본 mock 모드에서 목표 입력 → 관리자 계획 작성·사용자 승인 → 자동 진행 시작·재개로 업무를 처리합니다. 선행 결과의 사용자 승인이 필요하면 멈춥니다. 모의 형식 검사는 제목 존재만 검사하며, 수정 필요 결과에는 명시적으로 '수정 1회 및 재검토'를 요청할 수 있습니다. 일반 mock 엔진이 의견을 이해해 결과를 개선하는 것은 아닙니다.

마지막 결과도 사용자가 검토·승인해야 확정됩니다. 상세/보고서 화면의 'Markdown 확정본 다운로드'는 현재 유효한 확정 버전만 제공합니다. 목표·결과·승인 근거가 바뀌거나 보관 파일이 손상되면 다운로드를 거절하며, 기존 JSON 버전은 보존합니다. 다운로드와 화면 조회는 프로젝트 JSON이나 보관 파일을 수정하지 않습니다.
