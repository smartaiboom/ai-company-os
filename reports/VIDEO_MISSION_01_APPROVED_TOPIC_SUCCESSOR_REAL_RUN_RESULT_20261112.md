# 미션 01 — 승인된 topic 실패 후속 실행 결과

2026-11-12T10:09:51.407418+09:00 (KST). 최신 main `59b3af6`·AGENTS.md·승인 지시서와 지정 직전 결과를 확인했다. 최소 후속 연결/표적 오프라인 검증 후 새 업무1건을 생성하고 새 제안을 검토·서명한 뒤 실제 run을 **한 번** 실행했다.

## 변경과 사전 검증

`video_mission_one.py`에 여섯 번째 mission_selected_topic_mismatch 전용 `topic_successor_reference`/`create-topic-successor`, `representative_workflow.py`에 대응 stage를 추가했다. 기존 audience/무료/DNS 등 가드는 넓히지 않았다. 원6단계 체인의 서명·상태/사유·단일 writer HTTP200/json_parsed·active_operation·원 목표/입력/계획/수락 연구/selection·자료 기간/영수증·소모9회/YouTube2+2를 검증해 같은 컷룸에만 인계한다. 새 policy=mission01_topic_successor_20261112_v1, max_calls=None, YouTube 신규0, 빈 동의/시도/세션의 writer pending부터 시작하며 실패 대본은 이식하지 않는다.

`PYTHONPATH=core:companies/video python -B -m unittest tests.test_video_mission_one.MissionOneTests.test_topic_failure_successor_preserves_six_failures_and_hands_off`: **1개 통합 테스트 통과, 2.727초**. 임시 합성 실패6개·mock native HTTP·DNS/socket 차단에서 새 적격성/중복·구 승인 재사용·다른 선정/계정/키 거부, 원파일 바이트 불변, capNone/web0, 25초 대본→manager→editor→manager→임시 동일 컷룸 awaiting_plan_approval을 확인했다. source=offline_http_fixture이며 실제 성과가 아니다. 기존 전체 테스트는 반복하지 않았다. `git diff --check` 통과 후에만 실제 업무를 생성했다.

## 실제 결과 — 장면 유형 계약 검사에서 중단

Gemini writer **1회 HTTP200**, 역할 JSON 파싱 후 **invalid_script_shot**으로 stopped. 현행 inspect_script의 narrative_beats.shot_type 허용값은 demo/detail/card이며 적어도 한 장면이 이 조건을 충족하지 못했다. 실패 응답 원문/shot_type 값은 저장되지 않아 실제 반환값이나 의미를 확정할 수 없다. 이 검사에서 멈춰 이후 topic.title 정확 일치 검사 통과 여부도 확인할 수 없다. 자동 수정·검증 우회·제목/주제 교체를 하지 않았다.

연구 accepted 재사용, writer/editor는 pending·versions0·reviews0. **검증된 실제 대본·스토리보드·대표 승인 대기 카드 없음**. 컷룸은 **research_planning**, final=None, artifacts={}. 관리자 writer/editor 검토 및 accepted_review_handoff/별도 AI 최종 평가는 모두 미수행이다. 신규 실패에는 blocker=invalid_script_shot과 응답 hash만 있으며 해당 필드의 별도 세부 진단은 기록되지 않았다.

| API | 과거 소모 | 신규 시도 | 신규 HTTP 성공 | 신규 전송 실패/불명 | 현재 누적 |
|---|---:|---:|---:|---:|---:|
| Gemini | 9 | 1 | 1 | 0/0 | 10 |
| YouTube search.list | 2 | 0 | 0 | 0/0 | 2 |
| YouTube videos.list | 2 | 0 | 0 | 0/0 | 2 |

신규1회는 completed/json_parsed로 소모를 유지했다. 과거 DNS 공급자 수신 불명도 과거9회에 포함한다. 신규 토큰 prompt8281/completion1311/total9592. 내부 임의 호출 상한은 None이며 카운터 때문에 중단된 것이 아니다. 공급자 quota=unknown, 비용=unverified/signed_free_tier_attestation. 기존 무료/결제 미연결 소유자 진술·서명/키 바인딩을 검증했으며 공급자 청구/무료 quota 독립 조회는 하지 않았다. 자동 retry·stopped 재실행·추가 successor·fallback·계정 순환·유료 전환·시험 API0회다.

## 새 제안·승인·실물 위치

- 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`; 새 업무 **qualityprovider-95e2b74978f24b4690368a8bf10ae72a**.
- 원장 `data/video_representative_workflow/studio/mission_one_provider/qualityprovider-95e2b74978f24b4690368a8bf10ae72a.json`, 대응 `.consent.json`. 실제 검증된 대본·스토리보드 산출물 파일은 없다.
- 제안 `/tmp/mission01_topic_successor_proposal_20261112.json`, review SHA **72d5e6b94caf7addbe6ce4d6214aa3901716b90d5b14d0407f5c6e390bb3e072**. 원 소모9/새 한도None/YouTube0·선정25초·무료 데이터 정책/고정 모델/계정/원본 해시를 승인 범위와 대조했다.
- 새 운영 grant **5cb46750501a44c596da2f3014be64a6**, 승인 시각 **2026-11-12T10:07:42+09:00**. 과거 grant는 역사 검증에만 사용했다.
- 모델 gemini-3.5-flash-lite, 고정 엔드포인트 https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent, Gemini/YouTube 프로젝트 gen-lang-client-0938732315. 기존 키 바인딩/Google 무료 데이터 정책 유지, 실행 환경만 프로세스 범위로 설정했다. 최신 exact topic.title 복사 시스템 지시를 사용했다.
- 세션 **1568af65af08432b86214ab16667137c**, 신규 attempt/보존 active_operation **07ecdf6aa7b0484cb69ad903f7a95d31**.
- 예약/전송 **2026-11-12T10:08:36+09:00**, 응답/종료 **10:08:41+09:00**. 응답 SHA **9df39292569613015ac159d40564cc633eaf5bfa372b00108e3cddff13cd0c7e**, finish=stop/response_bytes5776/json_parsed. 실행 출력 `/tmp/mission01_topic_successor_real_run_20261112.log`. 키·원 응답 전문·시청자 개인정보는 공개하지 않는다.

## 보존과 다음 한 단계

원6개 stopped 업무의 JSON/consent/lock **18개 SHA-256 시작/종료 동일**. 기존 서명·attempt·active_operation·실패/불명 소모·타임스탬프는 불변이다. 컷룸에는 승인된 새 연결/history를 추가했고 기획 상태는 유지했다. 새 plan/employee_web은 원본과 동일하다. 원 조사10건·관리자 선정 롤토체스/모바일 퍼즐 관련 소재 **25초**, evidence `q0:TAidk7sXHk4`, `q0:0FVBz6iWhOY`, `q1:9YjDIwCAnsw` 재사용. Shorts·소스 권리·성과 미확정 유지.

원 계획 SHA `23ee4a8e9e2ab0079a5cf881be852c4f823eac0422f33fde1f357289f48b5c74`, receipt SHA `651b936fb9542aa188a3bf3a0a3ab803e914b8285f26a9e043fd041a9aeeb04b`, selection SHA `e4296e6a276d6462599d3c3bdb1a86bc5fb3ba2472bfd53eb78d98e6a8d47587`와 자료 기간/출처를 기존 가드로 검증했다. data/, backups/, artifacts/, .env·키·음성/영상·기존 미추적7개 파일을 삭제/초기화/임의 수정하지 않았다. 대표 승인·TTS/MP4/렌더/게시0회다.

**다음 행동 하나:** 추가 실제 호출 없이 writer의 shot_type 허용값 전달 계약과 안전 진단만 오프라인 확인한다. 실패 후 반복 개발/새 successor/재시도를 시작하지 않았다. 이번 소스2개·테스트1개·이 보고서만 main에 commit/push하고 원격 읽기 확인 후 중단한다.
