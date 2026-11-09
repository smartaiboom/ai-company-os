# AI Company OS — 실전 중심 두 번째 무료 AI 영상 시험 준비 (추가 실제 송신 없음)

## 목표
AI Company OS의 불변 제품 목표: **사용자가 목표를 한 번 입력하고 실제 AI 관리자가 계획/기준/분배/검토를 맡고, 실제 AI 직원이 협업·수정하여 최종 MP4를 제출**한다. 테스트 600여 개를 늘리는 것 자체가 목적이 아니다. Codex는 개발자이며 AI 관리자 역할을 대신하지 않는다.

2026-11-04 첫 실사용 프로젝트 `freecompany-ae4aa334511d470c8c517685e9902a53`의 실제 OpenRouter 무료 관리자 계획 1회가 `incomplete_response`로 중단. 정확한 finish_reason은 원래 기록되지 않아 사후 확정 불가. 이후 읽기 전용 회복 진단에서 해당 프로젝트 `completed_unvalidated_legacy / blocked_pending_audit`, proposed 추가 시도 0건. **이 원본을 절대 변경/재전송/초기화/복구 우회하지 않는다.** 실제 호출이 아니라 새 미래 실험을 준비한다.

## 꼭 읽기
`AI_COMPANY_OS_CORE_PRINCIPLES.md`, `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`, `reports/v01_real_free_ai_video_one_cycle_20261104.md`, `reports/v01_real_free_provider_response_recovery_20261104.md`, `reports/v01_real_free_autonomous_video_smoke_prepare_20261103.md`, 현행 무료 manager/worker 응답 프롬프트/검증 및 MP4 local_artifacts 코드.

## 이번에 Codex가 끝까지 수행할 개발 목표
**실제 무료 라우팅 모델이 중단 없이 정상적인 관리자 계획과 직원 결과를 반환할 가능성을 높이도록, 현재의 출력 계약·최소 계획 복잡도·응답 종료 조건을 검토하고 실제 중단 진단을 검증하라.** 필요하다면 안전 정책을 완화하지 않는 범위에서 간결한 JSON 출력/요청 크기/관리자 최소 유효 DAG/단계별 필수 데이터·토큰 한도 등의 명백한 과다 요구를 줄인다. **지금부터는 회복 체계의 복잡도를 더 늘리기보다 실제 한 사이클의 도달 가능성을 높이는 데 집중하라.**

### 실행 세부 기준
1. **이전 실사용 실패 프로젝트는 읽기 전용**. 현재 완료-but-unvalidated attempt, consent, active operation과 기존 수동 프로젝트 `cb44b605b498`, `c85d9853906a` 및 backup/data는 변경 금지. 기존 mock MP4 유지. 다른 프로젝트 데이터 복사/재서명 금지.
2. **짧지만 진짜 협업이 가능한 정상 경로**를 테스트한다: 관리자 계획은 최소 AI 직원 간 선행 결과 전달, 관리자 검토와 최종 영상 산출물을 만족하도록 모델이 자율 구성하고, 예시 장면·대본을 Codex가 고정하지 않는다. 업무 수·성공 기준의 불필요한 과잉 요구를 줄이되 프로젝트별 계획/검토 판단을 사용자/하드코딩 규칙으로 대체하지 않는다. MP4는 실제 로컬 ffmpeg/TTS의 검증된 allowlist로 생성. 무료 모델과 strict JSON/finish reason/cost 0 검증을 임의 완화하거나 불완전 JSON을 성공으로 속이지 않는다.
3. 개발 후 **실제 API는 단 한 번도 호출하지 말고**, fake HTTPS로 짧은 관리자 계획→직원 2명 이상→검토/필요 시 수정→후속 전달→실제 MP4 렌더/기술 검사→final까지 run 한 번으로 검증. 정상 및 length/tool/filter/error/missing/refusal/비용 미확정 등 중단 사례가 적절히 기록되는지 확인. 기존 22회 시나리오/수정 경로 회귀도 지킨다.
4. **다음 실제 테스트는 첫 프로젝트의 무단 복구가 아니라 별도 신규 시험**이다. 별도 free-v2 저장소에 같은 공개적 비민감 목표 — “ChatGPT 초보자에게 좋은 질문하는 방법을 알려주는 한국어 20~30초 자막 영상(MP4)을 만들어라. 가능하면 로컬 음성도 포함하고 최종 파일을 검증해서 보고하라.” — 로 **새 프로젝트 단 하나** create, local-video 허용, 최초 운영 동의 **prepare까지만** 수행. 기존 첫 프로젝트와 별도임을 서명 정책·원장·project_id가 드러내야 하고 이전 동의를 재사용하지 않는다. 동일 작업 재실행 시 중복 생성 방지. 외부 전송 전 새 프로젝트 목표/동의 hash·만료일·범위 확인.
5. 아직 사용자 새 프로젝트 단위 최초 전송 동의가 없으므로 이번에는 **실제 API 호출 0회, approve 0회, run 0회**. 새로운 API key 발급/전역 .env 변경, 다른 무료/유료 모델 교체, fallback, 서비스 가입, 유료 TTS/영상 API, 임의 인터넷 조사/외부 업로드 금지. 무료 기존 로컬 ffmpeg/TTS 사용 가능.
6. 상태별 diagnostics는 content·비밀키 없이 제한된 숫자/분류만 기록. 별도 실제 품질 개선 도구 없이 좋은 영상 퀄리티를 보장한다고 주장하지 말 것. mock MP4는 텍스트·eSpeak 중심이며 사용자가 이미 영상/음성 품질에 불만족했다고 판단. 따라서 영상의 기술적 성공과 사용자 체감 품질을 명시적으로 분리.
7. 기존 테스트 중 핵심 경로+전체 회귀를 실행하고 `reports/v01_practical_second_video_trial_prepare_20261104.md`에 변경사항, 사용자에게 실제 새 프로젝트 승인을 요청할 정확한 project_id/goal/store/contract review hash/만료/전송 범위/로컬 도구 범위, 실제 송신 0회, fake MP4 성공/실패, 이전 원장 보존 근거, 다음 한 번의 live run 단계를 보고. 코드/테스트/보고서만 선택적 Git commit/push, 실제 데이터/제안/비밀키/영상 파일은 Git 제외.

## 합격
성능 과장 없이 **짧은 실제 관리자 출력이 끝까지 유효 처리되는 정상 경로를 오프라인으로 검증하고**, 실전용 새 격리 프로젝트와 실제 모델 전송 동의안까지 준비. 이번 작업에서 live 성공을 주장하지 않는다. 사용자가 다음 새 프로젝트 계약을 직접 승인하면 그때만 실제 한 사이클을 1회 실행한다.
