# 명시 승인된 실제 무료 AI 영상 자율 운영 1회 — 첫 관리자 응답 미완료로 정지

2026-11-04 KST. **실제 OpenRouter 요청 1회 후 안전 정지했으며 MP4는 생성되지 않았다. 실사용 한 사이클 합격이 아니다.** 실제 모델 응답을 mock이나 개발자 작성 콘텐츠로 대체하지 않았고, 재시도·다른 프로젝트 실행·모델 변경을 하지 않았다.

## 계약 검증과 승인

`git pull --ff-only` 성공, main `8d21277` 반영. 핵심 원칙, AGENTS.md, 한국어 출력 규칙, 준비 보고서, 지정 실행 지시서와 CLI/free-v2/live/로컬 도구/adapter/transport 코드를 읽었다. 사용자 명시 승인에 따라 아래 정확한 프로젝트만 실행했다.

- store: `/workspaces/ai-company-os/ai-company-os-phase1/data/free-video-smoke-20261104`
- 프로젝트: `freecompany-ae4aa334511d470c8c517685e9902a53`
- 목표: ChatGPT 초보자용 좋은 질문 작성법, 한국어 20~30초 설명 영상, 자막·가능하면 음성, 재생 가능한 MP4 및 제작 보고서.
- 목표 hash: `e45e9e0da6ce050ed0492583b129cb5313b63fa7f52693260770523fdbe098f6`
- 승인 전 상태 hash: `acf84d8651d7c0ef0093d18644cce97aa5890608671009c63dd65e4aa8a70c7c`
- 제안: `data/free-video-smoke-20261104/operating-proposal.json`
- 제안 canonical JSON 검토 hash: `c36981e3e8e6d565e3a7566185869a5bf49fcddafdb36a73764d23ad6c0316c2`
- 만료: `2026-11-11T09:30:14+09:00`.

목표·초기 상태·제안 hash가 지시서와 모두 일치했다. free-v2 namespace, ready/plan, 호출 0, 승인 grant 없음, 기존 실행 session 없음, 유효기간과 현행 `_check_contract` 검증을 통과했다. 계약을 재생성·수정하거나 기존 프로젝트 동의를 확대하지 않았다.

허용 범위는 목표 및 새 프로젝트 생성 계획/기준/배정/대본/자막/장면/직원 결과/관리자 검토·수정·통합 텍스트와 로컬 도구 메타데이터다. 기존 파일·코드 본문·영상/음성 원본은 전송하지 않는다. 고정 OpenRouter HTTPS, `openrouter/free`, 비용 0, 가격 0 필터와 `allow_fallbacks=false`, 로컬 FFmpeg/TTS allowlist, 총/시작당 인위적 호출 상한 없음, 30분 실행과 기존 수정·중복·실패·불확실 예약 보호를 유지했다.

환경에서 API 키는 존재 여부만 확인했으며 값은 출력·저장하지 않았다. AI_ENGINE/AI_MODEL/기존 API endpoint가 예상값임을 확인하고, 실행 프로세스에서만 `AI_BASE_URL=https://openrouter.ai/api/v1`, `AI_AUTONOMOUS_FREE_ENABLED=1`을 설정했다. 기존 전역 설정·.env·수동 경로의 AI_REAL_REQUESTS_ENABLED guard는 변경하지 않았다. ffmpeg/ffprobe/eSpeak NG와 Noto CJK 파일 존재를 확인했다.

`/tmp/run_approved_free_video_once_20261104.py`는 위 hash와 미실행 상태를 다시 검증하고, 로컬 배타적 실행 표식을 만든 뒤 정상 CLI `approve --owner-confirmed`와 `run --state-hash APPROVED_STATE_HASH`를 각각 한 번 호출했다. 이 승인 행위는 지시서에 인용된 사용자의 명시 동의에 근거한다. 실제 요청/서명 보호를 monkeypatch하지 않았다.

## 실제 실행과 첫 오류

- 승인: `2026-11-04T10:03:19+09:00`.
- run/session/첫 요청 시작: `2026-11-04T10:03:19+09:00`.
- 응답 수신 및 정지: `2026-11-04T10:04:03+09:00`.
- 요청 모델 ID: `openrouter/free`, 역할: AI 관리자 `plan`.
- 실제 OpenRouter 요청 **1회**, HTTP 응답 수신 완료 **1회**, transport 실패 **0회**, reserved 상태 **0건**.
- 공급자 응답의 `usage.cost`가 숫자 **0**으로 검증되어 `cost_verified_zero=true`가 기록됐다. 비용 0 필터/무료 모델 고정 조건을 유지했고 유료 fallback·유료 서비스는 사용하지 않았다.
- **첫 오류: `incomplete_response`**. live 응답 검증에서 `finish_reason == stop` 조건이 충족되지 않았다. 따라서 관리자 계획을 채택하지 않고 정지했다. raw 응답을 저장하지 않는 현재 경로에서는 실제 finish_reason 값이나 본문을 사후 확정할 수 없다. 토큰 부족/응답 잘림 같은 구체적 원인을 추측해 단정하지 않는다.
- 저장 상태 `stopped`, phase `plan`, 원장 `completed`이나 `role_result_status=unvalidated`, `active_operation` 보존. completed는 응답 수신을 뜻하며 업무 성공이 아니다. reserved는 0건이지만 **업무 적용이 확정되지 않은 operation 1건**을 보존한다.
- 실제 AI 직원 호출 **0회**, 계획 채택 **0건**, 선행 결과 전달/수정/로컬 렌더 **0회**. 사용자 중간 업무 승인 요청 **0회**, run session **1개**.
- 자동 재시도·continue·중복 승인·두 번째 run **없음**. HTTP/CLI 프로세스 exit 0은 상태 조회/저장 성공일 뿐이며, 제품 실행은 `stopped`로 판정했다.

## MP4와 산출물

**실제 AI 프로젝트의 MP4 경로: 없음(미생성).** 해당 store 아래 MP4 0개, `final.json`/`final.md` 없음, artifacts 비어 있음. 그러므로 이번 실제 모델 결과에 대한 ffprobe·디코딩·자막/오디오·미적 품질 검증도 수행할 대상이 없다. 다운로드/preview 복사본 역시 만들지 않았다. 이전 mock MP4는 실사용 결과로 제시하지 않는다.

실제 운영 근거는 로컬 store에 보존했다(Git 제외):

- 프로젝트 상태: `freecompany-ae4aa334511d470c8c517685e9902a53.json`
- 서명된 운영 승인: `freecompany-ae4aa334511d470c8c517685e9902a53.consent.json` (서명 키/계약 원문을 보고서나 Git에 포함하지 않음)
- 중복 실행 방지 표식: `authorized-launch-20261104.json`
- 비밀 정보 없는 실행 요약: `authorized-run-summary-20261104.json`
- 상태 이벤트: `operating_scope_approved`, `system_safety_stop/incomplete_response`.

현재 상태 hash: `f28ebea41f84d1f08917acab1f6ae1e1c548a164e482710273828b7e5936e7b1`.

## 보존·검증·다음 조치

대상 신규 store를 제외한 기존 데이터/백업/프로젝트 파일 39개의 실행 전후 SHA256을 비교해 **변경 0건**을 확인했다. 여기에는 기존 mock 증거가 포함된다. `cb44b605b498`의 기존 9/20 원장과 `c85d9853906a`의 1/7 원장·reserved 1건을 읽기 전용으로 확인했고 그대로 보존했다. 다른 사용자 미추적 파일도 변경하지 않았다.

제품 코드 변경은 없다. 실제 실행 명령은 위 단일 실행 스크립트이며 정상 CLI 승인/run을 사용했다. 오프라인 검증으로 `python -B -m unittest tests.test_autonomous_free.FreeTests.test_revision_bound_quality_unknown_and_invalid_responses tests.test_autonomous_free.FreeTests.test_crash_completed_response_before_commit_blocks`를 실행했다. 이는 가짜 HTTPS·합성 키/동의·격리 저장소·네트워크 차단 테스트이며 실제 요청 횟수에 포함하지 않는다. 결과는 아래에 기록한다. 전체 회귀는 코드 변경이 없어 반복하지 않았다. `git diff --check` 통과.

다음 개발 과제는 정상 완료가 아닌 응답 종료 이유를 비밀 정보 없이 bounded metadata로 남기는 진단과, 미완료 응답에 대한 별도 한도/중복 방지/권한을 갖춘 복구 정책의 오프라인 검증이다. 실제 원장이나 active_operation을 지워 재시작하거나 성공 상태로 바꾸지 않는다. **현재 지시서는 첫 실행 후 임의 재시도를 금지하므로, 이번에는 추가 실제 요청을 하지 않는다.** 이후 실제 재실행에는 보존된 미확정 업무 적용 상태를 고려한 별도 명시 운영 복구 범위가 필요하다.

이번에는 목표→실제 관리자 호출과 비용 0 검증·안전 정지의 실사용 근거를 확보했지만, 자율 협업→최종 MP4에는 도달하지 못했다. 새 경로에서 업무별 승인 부채를 추가하지 않았으며, 반복 사용자 개입이 필요한 실패 복구는 남은 개발 과제다. 기존 수동 프로젝트 승인 부채는 이번 범위에서 변경하지 않았다. UI·대시보드는 개발하지 않았다.

오프라인 집중 테스트 결과: **2개 통과, 실패/오류 0, exit 0** (0.219초). 보고서를 저장 후 다시 읽어 파일 생성과 내용을 확인했다. 보고서만 선택적으로 Git에 반영하며 실사용 데이터/계약/키/원장은 제외한다.
