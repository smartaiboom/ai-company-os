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
No API calls are made in Phase 1.

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
- `AI_API_BASE_URL`: 제공자의 API 기본 URL (예: `https://제공자-주소/v1`)
- `AI_API_KEY`: 제공자가 요구하는 API 키
- `AI_MODEL`: 제공자가 지원하는 모델 이름
- `AI_API_TIMEOUT`: 선택 항목, 요청 제한 시간(초), 기본값 90

API 키를 소스 코드나 Git 저장소에 기록하지 마세요. 실제 AI 엔진을 선택하면 프로젝트 목표, 작업 지시, 필요한 입력 자료 및 이전 작업 결과가 설정한 외부 API 제공자에게 전송됩니다. 제공자의 데이터 처리 및 요금 정책을 먼저 확인하세요. 설정이 없거나 API 호출이 실패하면 작업은 성공으로 처리되지 않습니다. 실제 AI 응답 역시 별도 검증이 필요합니다.
