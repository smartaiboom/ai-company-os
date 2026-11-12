# 미션 01 — 승인된 audience 실패 후속 실행 결과

2026-11-12T09:53:07.500766+09:00 (KST). 최신 main `b69e315`·AGENTS.md·승인 지시서와 지정 직전 결과3개를 확인했다. 최소 새 경로와 표적 검증 후 승인된 새 업무1건을 생성·새 제안 서명·run1번 실행했다.

## 구현·오프라인 검증

`video_mission_one.py`에 다섯 번째 script_audience_inference_required 중단 전용 `audience_successor_reference`/`create-audience-successor`, `representative_workflow.py`에 대응 stage를 추가했다. 기존 실패별 가드를 넓히지 않았다. 원 free-writer reference와 과거4단계 서명/원장·목표/입력·계획/연구/선정/영수증·자료 기간·다섯 번째 execute HTTP200/json_parsed1회/active_operation·누적8회를 검증하고 같은 컷룸에만 연결한다. 새 policy=mission01_audience_successor_20261112_v1, max_calls=None, YouTube 신규0, 빈 동의/시도/세션에서 writer pending 시작. 과거 실패 대본은 이식하지 않는다. 새 제안·서명·계정/키/무료 전송 가드 및 기존 local handoff를 재사용한다.

`PYTHONPATH=core:companies/video python -B -m unittest tests.test_video_mission_one.MissionOneTests.test_audience_failure_successor_preserves_five_failures_and_hands_off`: **1개 통합 테스트 통과, 2.159초**. 합성 실패5개를 만든 임시 저장소·mock HTTP·DNS/socket 차단에서 다른 컷룸 연결/중복 생성/구 제안 재사용/소모·선정·계정·YouTube 범위 변조 거부, 원파일/서명 불변, 새 대본→관리자 검토→편집→검토→동일 임시 컷룸 awaiting_plan_approval을 검증했다. 25초/미정 AI 대상 제안·근거/fixture provenance를 유지했다. 기존53개 전체를 반복하지 않았다. `git diff --check` 통과. 오프라인 통과 후에만 실제 업무를 생성했다.

## 실제 실행 결과 — 선정 제목 일치 검사 중단

Gemini writer1회 **HTTP200**, 역할 JSON 파싱 후 **mission_selected_topic_mismatch**로 stopped. 기존 검사 순서상 시청자 추론 및 mock/model provenance 검사를 통과한 뒤 `topic.title == manager_selection.selected_topic`에서 불일치했다. 이는 전체 대본 검증/AI 관리자 수락 성공을 뜻하지 않는다. 원문 대본은 저장되지 않아 실제 제목 문자열이나 의미상 주제 변경 여부는 확정할 수 없다. 세부 detail_code는 이 주제 검사에 별도 저장되지 않았으며 blocker 코드와 응답 hash를 보존했다. 응답을 수정하거나 검사를 우회하지 않았다.

연구 accepted 재사용, writer/editor는 pending·versions0·reviews0. **검증된 대본·스토리보드·대표 승인 대기 카드 없음**. 동일 컷룸은 **research_planning**, final=None, artifacts={}다. 관리자 대본/편집 검토·별도 AI 최종 평가·accepted_review_handoff는 실행되지 않았다.

| API | 과거 소모 | 신규 시도 | 신규 HTTP 성공 | 신규 전송 실패/불명 | 누적 |
|---|---:|---:|---:|---:|---:|
| Gemini | 8 | 1 | 1 | 0/0 | 9 |
| YouTube search.list | 2 | 0 | 0 | 0/0 | 2 |
| YouTube videos.list | 2 | 0 | 0 | 0/0 | 2 |

신규 시도는 completed/json_parsed로 소모를 유지한다. 과거 DNS 수신 불명도 과거8회에 포함한다. 신규 토큰 prompt8161/completion1218/total9379. 카운터 상한 때문에 중단된 것이 아니다. 공급자 quota=unknown, 비용=unverified/signed_free_tier_attestation이며, 기존 무료·결제 미연결 소유자 진술과 키/계정 서명을 검증했을 뿐 청구/무료 quota 독립 검증은 하지 않았다. 유료 전환·fallback·계정 순환·자동 retry·시험 API 요청·실패 후 추가 successor0회.

## 새 제안·승인·저장 위치

- 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`; 새 업무 **qualityprovider-4109f683a75b466ba326a45df3bb7012**.
- 새 원장 `data/video_representative_workflow/studio/mission_one_provider/qualityprovider-4109f683a75b466ba326a45df3bb7012.json`, 대응 `.consent.json`. 검증된 대본/스토리보드 산출물 파일은 없다.
- 제안 `/tmp/mission01_audience_successor_proposal_20261112.json`; review SHA **368b72bef6afc8f6a85c99699786da0569f1406b102e17cfc1d83353b074fd2d**. 원 소모8·새 한도None·YouTube0·고정 모델/계정/무료 데이터 정책·선정25초·원 해시를 사용자 승인과 대조한 뒤 새 서명했다.
- 승인 ID **ce1b4035b60d4684a8ffade02b3cb975**, 시각 **2026-11-12T09:51:19+09:00**. 과거 동의/만료 제안을 재사용하지 않았다.
- 모델 gemini-3.5-flash-lite, 고정 엔드포인트 https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent, Gemini/YouTube 프로젝트 gen-lang-client-0938732315. 기존 키 바인딩·Google 무료 데이터 동의 유지, 실행 환경은 프로세스 범위에만 설정했다.
- 세션 **36582999a8644e7e92f666c5d8912cbb**, 신규 attempt/보존 active_operation **77745d1df72f407a874c4dd7e61570a3**. 예약/전송 **2026-11-12T09:51:42+09:00**, 응답/종료 **09:51:50+09:00**.
- 응답 SHA **f1d3eb676ca27173b1563b0ce9b9c13aaedc1424ab0eb9fb9a6cf300dadf79cc**, finish=stop, response_bytes5508, json_parsed. 실행 출력 `/tmp/mission01_audience_successor_real_run_20261112.log`. 키·원시 응답·시청자 개인정보는 보고서에 복제하지 않는다.

## 원본 보존과 다음 행동

원5개 stopped 업무의 JSON/consent/lock **15개 파일 SHA-256 시작/종료 동일**. 서명·attempt·active_operation·타임스탬프·실패/불명 소모 불변이다. 컷룸에는 승인된 후속 업무 연결/history를 추가하고 기획 상태는 유지했다. 새 업무의 계획/employee_web은 원본과 동일하다. 기존 조사10건·실제 관리자 선정 전략적 팀 전투/롤토체스 및 모바일 퍼즐류·**25초**, evidence `q0:TAidk7sXHk4`, `q0:0FVBz6iWhOY`, `q1:9YjDIwCAnsw` 유지. Shorts·시각 소스 권리·성과는 미검증이다.

원 계획 SHA `23ee4a8e9e2ab0079a5cf881be852c4f823eac0422f33fde1f357289f48b5c74`, 영수증 SHA `651b936fb9542aa188a3bf3a0a3ab803e914b8285f26a9e043fd041a9aeeb04b`, 선정 SHA `e4296e6a276d6462599d3c3bdb1a86bc5fb3ba2472bfd53eb78d98e6a8d47587` 및 자료 기간을 기존 가드로 검증했다. 사용자 data/backups/artifacts/.env·키·음성/영상·기존 미추적7개 파일을 삭제/초기화/임의 수정하지 않았다. 대표 승인/반려·TTS/렌더/게시0회다.

**다음 행동 하나:** 추가 API 없이 관리자 선정 제목의 정확 일치 계약이 writer에 충분히 전달되는지 오프라인 확인한다. 원문 없이 의미를 추정하거나 title을 자동 교체하지 않는다. 이번 실패를 재실행하지 않고 소스2개·테스트1개·이 보고서만 GitHub commit/push 후 main 읽기를 확인하고 중단한다.
