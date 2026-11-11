# 미션 01 — DNS 실패 이력 보존형 재개 준비

2026-11-11 KST. 기준 GitHub `e1f1250`. 이번 작업은 개발과 격리 오프라인 검증만 수행했다. **실제 Gemini/YouTube 외부 호출은 각각 0회, 실제 신규 업무·제안·서명 생성도 0건**이다.

## 변경과 보존

기존 `run`은 실패 업무의 재실행을 차단하므로 공통 엔진을 변경하지 않고 영상 회사의 분리 업무 생성 경로를 추가했다.

- `representative_workflow.py`: `stage_mission_resume`는 명시적 새 실행 확인 후 컷룸·기존 업무 잠금 아래 단 한 개의 분리 업무를 연결한다. 실패 업무의 상태·시도·active_operation·서명은 수정하지 않으며 기존 업무 ID는 컷룸 history에 남긴다. 새 업무의 consent는 비어 있다.
- `video_mission_one.py`: `create-resume --confirm-new-execution` CLI 추가. 첫 관리자 계획 요청이 DNS 실패한 경우만 허용한다. HTTP 응답·웹 시도·배정 업무가 있거나 이미 재개 업무이면 거부한다. 과거 서명의 진위는 확인하되 과거 승인을 재사용하지 않으며 과거 만료 시각도 새 승인을 대신하지 않는다. 새 제안에 실패 업무/시도 ID, 기존 상태 해시, 수신 여부 unknown, 기존 소모 1회, 총 상한 10회/신규 9회를 포함하고 새 검토 해시와 서명을 요구한다. 동일 목표·입력·원장 해시·컷룸 연결을 다시 확인한다. 새 업무 한도와 승인 한도 모두 9회이고 기존 전송 전 호출 가드가 강제한다. YouTube는 과거 0회이므로 검색/정보 각각 4회를 유지한다. 재개 업무의 재재개나 구 업무 재발송은 허용하지 않는다. 웹 원장이 null인 실패 업무의 화면 조회도 처리한다.
- 기존 키 바인딩·무료 전용·모델·엔드포인트·만료·자동 retry/fallback 금지와 `report_plan` 연결을 재사용했다. 화면 디자인은 변경하지 않았다.

실제 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`는 `research_planning`, 연결된 기존 업무 `qualityprovider-504d90900918450f98dd62b6f7704f1b`는 `stopped/free_request_failed` 그대로다. 기존 Gemini 실패 시도 1회, active_operation `45658f60c61c4dc89efae8487c6ccd2d`와 기존 서명·세션을 보존했다. 공급자 수신 여부는 불명으로 취급한다. 실제 기획안·대본·대표 승인 대기는 생성하지 않았다.

읽기 전용 확인 시 파일 SHA-256:
- 기존 컷룸 JSON: `b3017e46c36b83ef7e0eb38b524654825a2c2cbf8e5e50750ce5c822cdf6ca42`
- 기존 실패 업무 JSON: `650a7ceb5e749b26909af7d85275805a710d18107f90ab13a87d0acf6d52dcb7`

## 검증

`PYTHONPATH=core:companies/video python -B -m unittest tests.test_video_mission_one tests.test_employee_web_research tests.test_representative_workflow tests.test_quality_provider`: **22개 통과, 37.821초**. `git diff --check` 통과. 실제 기존 업무에도 `resume_reference`를 읽기 전용으로 적용해 재개 대상 적격성과 기존 컷룸 연결을 확인했으며 새 업무·제안·서명은 생성하지 않았다. 테스트는 임시 저장소에서 DNS와 소켓을 차단하고 HTTP 응답을 fixture로 제공한다. 실제 프로젝트에는 fixture를 등록하지 않았다. 새 승인 전 호출 차단, 구 서명 재사용/상한 증액/실패 참조 변조/중복 생성 차단, 기존 업무·서명 파일 바이트 보존, 신규 9회 소진 시 10번째 호출 차단, fixture 기획의 동일 컷룸 `awaiting_plan_approval` 연결 및 실제 결과로의 제출 거부를 검증한다.

## 다음 대화에서 필요한 단일 승인 문구

> 미션 01의 DNS 실패 이력과 소모 1회를 보존한 새 분리 업무 실행을 승인합니다. 동일 목표로 Gemini gemini-3.5-flash-lite 신규 최대 9회(실패·타임아웃 포함, 과거 1회와 합계 최대 10회), YouTube search.list 최대 4회·videos.list 최대 4회만 허용합니다. 프로젝트 gen-lang-client-0938732315의 무료 서비스만 사용하고 유료 전환·자동 재시도·fallback은 금지합니다. 목표·공개 YouTube 자료·이번 AI 직원 결과의 Google 무료 API 전송과 서비스 개선·인적 검토 가능성에 동의합니다. 실제 기획안·전체 한국어 대본을 같은 컷룸의 대표 승인 대기까지만 제출하고, 대표 승인·음성·MP4·게시 없이 결과 보고 후 중단하세요.

**이번 개발 지시는 이 승인을 대신하지 않는다.** 다음 대화에서 위 범위의 명시적 승인을 받은 뒤에만 아래 명령을 수행한다. 현재 원장 구조상 재개 경로는 준비되었으나 실제 네트워크·무료 모델 접근 성공은 미검증이다. 실제 첫 요청 실패 시 소비 기록 후 중단하며 권한을 바꾸어 재전송하지 않는다.

```bash
export PYTHONPATH=core:companies/video
export GEMINI35_MODEL=gemini-3.5-flash-lite
export GEMINI35_ENDPOINT=https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent
export GEMINI35_AUTONOMOUS_FREE_ENABLED=1
python -B -m video_mission_one create-resume company-aba553f29cfb454c8c05bad4abb49969 --confirm-new-execution
python -B -m video_mission_one prepare company-aba553f29cfb454c8c05bad4abb49969 --account-project gen-lang-client-0938732315 --youtube-project gen-lang-client-0938732315 --quota-note '2026-11-11 KST 사용자 화면과 URL: 두 키 동일 프로젝트 및 결제 미연결 확인. 독립 검증 아님. 과거 DNS 실패 1회 소비, 신규 승인 최대 9회, 잔여량 unknown.' --confirm-free-account --confirm-youtube-policy > /tmp/mission01_dns_resume_proposal.json
```

생성된 JSON의 `mission_resume`, 한도 9/4/4, 모델·무료/데이터 처리 범위 및 `review_hash`를 검토한다. 다음 `검토한_review_hash` 자리는 그 JSON의 실제 검토 해시로 대체한다. 숫자 잔여량은 입력하지 않는다. 키는 기존 환경에서만 읽으며 출력하지 않는다.

```bash
python -B -m video_mission_one approve company-aba553f29cfb454c8c05bad4abb49969 --proposal /tmp/mission01_dns_resume_proposal.json --review-hash '검토한_review_hash' --confirm-free-data-policy
python -B -m video_mission_one run company-aba553f29cfb454c8c05bad4abb49969
```

기존 업무에 직접 run하거나 create-resume을 반복하지 않는다. 새 제안 만료 시에는 미실행 신규 업무에 대해서만 다시 prepare/검토하며 과거 서명은 재사용하지 않는다. 기존 미추적 로그/프로브 7개, 사용자 데이터·키·백업·음성/영상은 보존한다. 실제 프로젝트 연결 변경은 다음 승인 뒤로 남겼으며 이번에는 소스 2개·관련 테스트 1개·이 보고서만 저장하고 중단한다.
