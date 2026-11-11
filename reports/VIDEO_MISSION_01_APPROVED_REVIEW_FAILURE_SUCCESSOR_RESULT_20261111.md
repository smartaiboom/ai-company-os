# 미션 01 — 승인된 연구 검토 실패 후속 업무 결과

2026-11-11T15:33:40+09:00 (KST). 기준 GitHub `d5dcae5`에 아래 최소 코드 변경을 적용·오프라인 검증한 뒤 실제 실행했다.

## 결과: 새 연구 검토 통과, 대본 대상 시청자 불일치로 중단

새 독립 후속 업무 `qualityprovider-4cbe762cbf554e40af5e7d990ceaf46b`를 한 건 생성하고 새 제안 검토·서명 후 run을 **한 번** 실행했다. 관리자 연구 검토는 새 selection 객체 계약 및 기존 근거/길이 검증을 통과했다. 이어 대본 직원 응답을 받았으나 **단일 중단 사유 `script_audience_mismatch`**로 stopped 처리됐다.

실패 지점은 `companies/video/script_quality.py:52`의 `inspect_script`: 반환 대본의 target_audience가 기존 quality_inputs.target_segment인 `미정`과 같아야 하는 검사다. 대본 응답 원문은 저장되지 않아 실제 반환 문자열은 확인할 수 없다. 검증을 완화하거나 target_segment를 임의 변경하지 않았다. 대본 직원 결과는 역할 바깥 JSON까지 파싱됐지만 최종 대본 검사에 통과하지 못해 versions에 저장되지 않았다. 연구 업무 accepted_by_ai_manager, 대본/편집 업무 pending, 컷룸 **research_planning** 유지다. 대표 승인 대기·검증된 전체 한국어 대본·스토리보드는 아직 생성되지 않았다.

| API | 과거 소모 | 이번 시도 | 이번 HTTP 성공 | 이번 전송 실패/응답 불명 | 누적 / 총 상한 |
|---|---:|---:|---:|---:|---:|
| Gemini | 4 | 2 | 2 | 0 / 0 | 6 / 10 |
| YouTube search.list | 2 | 0 | 0 | 0 / 0 | 2 / 4 |
| YouTube videos.list | 2 | 0 | 0 | 0 / 0 | 2 / 4 |

이번 두 번째 Gemini 응답은 업무 검증 실패 1건이며 원장 transport status=completed, role_result_status=json_parsed다. 시도 소모에서 제외하지 않았다. 과거 DNS 시도의 공급자 수신 불명 1회는 여전히 과거 4회에 포함된다. 잔여 Gemini 4회/YouTube 각 2회는 자동 재시도 허가가 아니다. 시험 호출·자동 재시도·fallback·모델 변경 모두 0회다.

## 재사용 자료와 실제 관리자 결정

구 두 번째 업무의 검증된 관리자 계획과 직원 조사 결과만 원래 출처 그대로 새 업무로 인계했다. 기존 미검증 관리자 feedback/selection·실패 요청·서명·세션은 이식하지 않았다. 조사 10개 관측과 실제 검색/정보 요청 각 2회의 HTTP 200·영수증·증거 ID·동일 목표/입력·취득시각·30일 보존기간을 확인했다.

- 조사 출처 업무: `qualityprovider-299a51b38e6d4d50b651b9fbb39dabad`.
- 원 조사 취득 시각: 2026-11-11T14:55:45+09:00 ~ 14:55:46+09:00. 보존 만료는 기존 expires_at(2026-12-11 KST)을 유지한다.
- 영수증 SHA: `651b936fb9542aa188a3bf3a0a3ab803e914b8285f26a9e043fd041a9aeeb04b`.
- 계획 SHA: `23ee4a8e9e2ab0079a5cf881be852c4f823eac0422f33fde1f357289f48b5c74`. 과거 검증된 AI 계획이며 새 계획 생성으로 표시하지 않았다.
- 직원 조사 결과 SHA: `f276ee45ed2464204e5dcde50cc2cb4a68baa575d0bc820244eaffe3d4767a93`. 검토 대상의 원본 해시와 일치한다.
- 새 업무는 phase=work/연구 awaiting_ai_review에서 시작했고 실제 새 관리자 선정 검토부터 호출했다. 신규 YouTube 조회는 없다. 재조사가 필요하다는 수정 요청이 나오면 자동 새 질의 실행 없이 중단하도록 했다.

새 관리자의 실제 검토 기록에는 게임을 ‘전략적 팀 전투 (Teamfight Tactics / 롤토체스 및 모바일 퍼즐류)’, 주제를 ‘인기 게임 쇼츠 트렌드 및 최적의 20~30초 길이 분석’, 길이를 **25초**로 선택했다. 근거 ID는 `q0:TAidk7sXHk4, q0:0FVBz6iWhOY, q1:9YjDIwCAnsw`다. 관리자 설명은 수집된 짧은 영상 표본과 설명 분량을 근거로 한 모델 판단이다. 조회수 표본만으로 세계적 인기나 유지율 개선을 입증한 결과가 아니다. Shorts 분류와 권리는 여전히 미확인이다. Codex는 게임·길이 답안을 선제 주입하지 않았다. 공개 메타데이터 전체는 GitHub 보고서에 복제하지 않았다.

## 새 승인과 보존된 실패 체인

- 최초 DNS 실패 업무 `qualityprovider-504d90900918450f98dd62b6f7704f1b`, 두 번째 실패 업무 `qualityprovider-299a51b38e6d4d50b651b9fbb39dabad`는 기존 stopped 상태·consent·attempt·active_operation 그대로다. 두 업무 관련 기존 6개 파일(JSON/동의/lock)의 시작/종료 SHA-256 동일 확인.
- 새 제안 `/tmp/mission01_successor_proposal_20261111.json`, 검토 해시 `d396c54edb792d114a71acb440d2a3a1372deba413b9fdf228b560739690e8df`.
- 새 승인 ID `507ae3ce19f6451fba446053ba4c6926`, 시각 `2026-11-11T15:31:38+09:00`. 구 서명을 재사용하지 않았다.
- 새 세션 `292353ade73e4644a8f1351385d99178`, 시작 `2026-11-11T15:31:42+09:00`, 마지막 응답 `2026-11-11T15:31:51+09:00`. active_operation `a9d4f025a5614afc9882f8d9dba70a79` 보존.
- 새 제안에는 두 과거 업무 상태 해시·네 과거 시도 ID·Gemini 소비4/신규6/총10·YouTube 각 소비2/신규2/총4·자료 인계 해시와 research/review 계약 버전1/스키마 해시 `4f06af63ea31aee883a6ff8f8da48a87712c53cb2b29e68c0f9205b4d934dfdf`를 포함해 서명했다.
- 모델 `gemini-3.5-flash-lite`, 기존 고정 엔드포인트·프로세스별 환경 설정 유지. 두 API 프로젝트는 `gen-lang-client-0938732315`; 사용자 제공 화면/URL과 결제 미연결 진술에 근거하며 독립 공급자 검증이 아니다. 공급자 잔여량은 unknown. 비용 진단 unverified/서명 무료 계정 진술 근거이며 청구 계측을 수행했다고 주장하지 않는다.
- 새 원장/승인: `data/video_representative_workflow/studio/mission_one_provider/qualityprovider-4cbe762cbf554e40af5e7d990ceaf46b.json` 및 같은 폴더의 대응 consent.json. 실제 검증된 선정은 assignments의 research.reviews에 있다. 실행 출력 `/tmp/mission01_successor_run_20261111.log`.

| 단계 | HTTP | 역할 결과 상태 | 응답 SHA-256 |
|---|---:|---|---|
| review | 200 | validated | 35086161c0e3c8e91314a4fcc9efac7c4e76e26d4a33ed76c76b05ebc2f3ec44 |
| execute | 200 | json_parsed | e5ab83322eba258f1f88ad65f366ac86f23d5627e5422d9f0f33e32ec3a15999 |

## 최소 코드 변경과 오프라인 검증

- `companies/video/video_mission_one.py`: DNS 전용 가드를 바꾸지 않고 `successor_reference`와 `create-successor` CLI를 추가했다. 과거 두 업무의 서명 진위·해시·소모/단계/상태·자료 출처/기간을 검증한다. 후속 업무 한도6, 새 승인·누적 참조 및 YouTube 상한2를 강제한다. 매 전송 직전 기존 grant 검증을 통해 전체 체인과 자료가 그대로인지 확인한다. 재사용 조사는 기존 배치 상태로 보존돼 재수집할 수 없으며, 연구 재실행 요구는 모델 전송 전에 차단한다. 성공 결과 검사는 새 6개 요청과 검증된 과거 계획/조사 인계를 구분하고 보고 카드에 reuse.source_job/newly_observed=false를 표시한다.
- `companies/video/representative_workflow.py`: 컷룸 잠금과 원업무 잠금 아래 후속 업무 한 건을 연결한다. 새 업무는 빈 consent/attempt/session으로 시작하며 원업무 원장을 변경하지 않는다. 중복 후속 생성·실패 후 자동 후속 생성은 금지한다.
- `tests/test_video_mission_one.py`: 명시적으로 합성한 DNS→검토 실패 체인 fixture로 캐시 인계→새 구조화 검토→대본/편집/최종검토→동일 임시 컷룸 승인 대기까지 신규 6회에 완료하는 경로를 검증했다. 누적 10회 도달 시 추가 호출 차단, 별도 새 승인 요구, 소비/상한 변조 거부, 중복 생성 금지, 옛 파일 불변, 실제 결과와 fixture 구분도 검증했다. 실제 세 번째 응답 재현으로 주장하지 않는다.

`PYTHONPATH=core:companies/video python -B -m unittest tests.test_video_mission_one tests.test_employee_web_research tests.test_quality_provider`: **29개 통과, 8.043초**. 이후 보고 카드의 재사용 표시를 추가한 통합 사례 **1개 통과, 1.004초**. 테스트는 임시 저장소에서 DNS/소켓을 차단하고 HTTP를 모의했다. `git diff --check` 통과. 테스트 완료 후에만 실제 후속 업무 생성·승인·실행했다. fixture를 실제 프로젝트에 등록하지 않았다.

## 다음 한 단계 및 중단

**다음 조치:** 실제 호출 없이 target_segment=미정의 대본 대상 시청자 인수 계약과 미검증 응답 진단을 검토한다. 이번 실패 응답을 다시 생성하거나 원장을 초기화하지 않는다. 별도 승인 전 추가 API 호출·업무 재개·추가 후속 업무 생성은 금지한다.

기존 사용자 자료·키·음성/영상·백업·미추적 파일 7개 보존. 대표 승인·TTS/WAV·MP4/렌더·업로드/게시 없이 중단한다. GitHub 저장 범위는 위 소스 2개·관련 테스트 1개·이 보고서다.
