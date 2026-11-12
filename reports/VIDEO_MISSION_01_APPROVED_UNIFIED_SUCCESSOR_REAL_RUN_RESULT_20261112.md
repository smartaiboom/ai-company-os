# 미션 01 — 승인된 공통 후속 업무 실제 실행 결과

2026-11-12T11:15:04.284178+09:00 (KST). 최신 main `040dbf6`·AGENTS.md·승인 지시서 및 지정 직전 결과2개를 확인했다. 최소 공통 경로/표적 검증 후 승인된 새 업무1건을 생성·제안 검토/서명하고 실제 run을 **한 번** 실행했다.

## 공통 후속 연결과 오프라인 검증

`video_mission_one.py`의 `unified_successor_reference`/`create-validated-successor`, `representative_workflow.py`의 대응 stage를 추가했다. 기존 실패별 reference/CLI를 약화하거나 새 사유별 CLI를 늘리지 않았다. 기존7번째 topic-successor의 invalid_script_shot을 anchor로 검증하고, 같은 공통 경로의 향후 완료/파싱된 writer 계약 실패도 서명/원본 체인을 재검증하도록 했다.

새 reference는 원업무·state/grant/reference hash·원 시도ID/누적 사용량·명시된 새 목적·현재 writer_contract_hash를 담는다. 과거 grant는 역사 증명이며 신규 전송 허가로 재사용하지 않는다. 동일 목표/입력/계획/수락 연구/선정/관측 기간·원 컷룸/모델/계정/키/무료 정책을 유지한다. `(previous_job_id,new_purpose,writer_contract_hash)` 중복 키를 컷룸 잠금 아래 저장하고, 연결 저장 중단으로 남은 orphan도 같은 키의 재생성을 차단한다. 새 업무는 빈 동의/시도/세션·writer/editor pending부터 시작한다. 기존 일곱 번째와 새 grant의 키/anchor 바인딩을 전송 전에 확인한다.

공통 경로 이후 같은 계약으로 다시 실패한 경우 목적 이름만 바꾼 후속 생성도 거부하며 계약 hash 변경과 별도 승인이 필요하다. 지원 범위는 **accepted writer가 아직 없는 단일 HTTP200/json_parsed writer 계약 실패**다. provider 실패/불명 전송·관리자 검토 단계 이후 부분 산출물 인계는 무리하게 일반화하지 않고 차단한다. 이전 이력을 마이그레이션하거나 원본을 수정하지 않는다.

`PYTHONPATH=core:companies/video python -B -m unittest tests.test_video_mission_one.MissionOneTests.test_unified_writer_successor_preserves_seven_failures_and_hands_off`: **1개 통합 테스트 통과, 3.331초**. 합성 실패7개·임시 저장소·mock native HTTP·DNS/socket 차단에서 원본 바이트 불변, 소모10/서명/선정·계정·계약 hash 변조/구 승인 재사용/중복·키 변경 거부, capNone/web0, native writer 객체→손실 없는 문자열 저장→검사→manager→editor→manager→임시 동일 컷룸 awaiting_plan_approval을 확인했다. source=offline_http_fixture이며 실제 성과가 아니다. `git diff --check` 통과 후에만 실제 업무 생성/전송을 수행했다.

## 실제 결과 — native schema 수용, literal 미정 대상 검사 중단

Gemini writer **1회 HTTP200**, native writer 객체 응답을 파싱·직렬화한 뒤 **script_audience_inference_required**로 stopped. 안전 진단은 **detail_code=literal_unspecified_audience**, field_path=unknowns, field=target_audience, audience_unspecified=true다. 검사 순서와 진단에 따르면 반환 대상이 정규화 기준으로 미정에 해당했다. 실제 원문 문자열은 보존되지 않아 정확한 표기는 알 수 없다. 새 schema의 target_audience는 비어 있지 않은 문자열을 요구하지만 literal 미정 배제/미확정 추론의 의미 조건은 현재 서버 검사 영역이다.

이번 요청에서 공급자가 확장 responseJsonSchema를 거부하지 않고 **result.content 객체**를 반환한 것까지 확인했다. 이는 대본 전체 schema/관계 검사 및 AI 검토가 성공했다는 의미는 아니다. shot_type/선정 제목 등 뒤쪽 검사 통과 여부는 이번 중단으로 확인하지 못했다. 응답 자동 수정·검사 완화·재시도·추가 successor는 없다.

연구 accepted 재사용, writer/editor pending·versions0·reviews0. **검증된 대본·스토리보드·대표 승인 대기 카드 없음**. 같은 컷룸은 **research_planning**, final=None, artifacts={}. 관리자 writer/editor review, accepted_review_handoff 및 별도 AI 최종 평가는 미수행이다.

| API | 과거 소모 | 신규 시도 | 신규 HTTP 성공 | 신규 전송 실패/불명 | 현재 누적 |
|---|---:|---:|---:|---:|---:|
| Gemini | 10 | 1 | 1 | 0/0 | 11 |
| YouTube search.list | 2 | 0 | 0 | 0/0 | 2 |
| YouTube videos.list | 2 | 0 | 0 | 0/0 | 2 |

신규1회 completed/json_parsed, 과거 DNS 수신 불명도 과거10회에 보존. 토큰 prompt10100/completion1290/total11390. 임의 내부 호출 상한은 None이며 카운터 때문에 중단된 것이 아니다. 공급자 quota=unknown, 비용=unverified/signed_free_tier_attestation. 기존 무료/결제 미연결 소유자 진술·서명·키 바인딩을 검증했지만 실제 청구/무료 잔여 quota 독립 조회는 하지 않았다. 유료 전환·fallback·계정 순환·자동 retry·시험 API 요청0회다.

## 새 제안·승인·원장

- 원 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`; 새 업무 **qualityprovider-3cfbbaec56d746799703489fe889a727**.
- 새 원장 `data/video_representative_workflow/studio/mission_one_provider/qualityprovider-3cfbbaec56d746799703489fe889a727.json` 및 대응 `.consent.json`. 실제 검증된 대본/스토리보드 파일은 없다.
- 제안 `/tmp/mission01_unified_successor_proposal_20261112.json`; review SHA **be14c47a1ce5234bafdf6226c4911f6be99618d6b1c436f91bc796b95c99900a**. writer_contract_hash **8d0ff0d818b0f7dfee18c13b506801b00ba588b14d9a45b173e497b6d540672f**. 원 소모10/한도None/YouTube0·선정25초·새 목적/무료 정책·계정/모델·원본 hash를 승인과 대조했다.
- 새 grant **9069f0e0730947f4a8a1e80208ac3bc2**, 승인 **2026-11-12T11:12:34+09:00**. 정책 mission01_validated_writer_successor_20261112_v1. 과거 만료 제안/동의를 재사용하지 않았다.
- 고정 모델 gemini-3.5-flash-lite, 엔드포인트 https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent, Gemini/YouTube 프로젝트 gen-lang-client-0938732315. 기존 키와 Google 무료 데이터 정책 유지, 활성화 설정은 실행 프로세스 범위에만 적용했다.
- 세션 **df7e5e16a37d454ab2363c87e2447231**, attempt/보존 active_operation **6a1543f6071748cab64a6d09d3ca7434**. 예약 **2026-11-12T11:13:17+09:00**, 응답/종료 **11:13:22+09:00**.
- 응답 SHA **00e72f123ef11c953d68d17b0159ce42f66b7865c2f8979726073d6242e5d6ae**, response_bytes5725, finish=stop/json_parsed. 실행 출력 `/tmp/mission01_unified_successor_real_run_20261112.log`. 키·원 응답 전문·시청자 개인정보는 공개하지 않는다.

## 원본 보존과 다음 행동 하나

기존7개 stopped 업무의 JSON/consent/lock **21개 SHA-256 시작/종료 동일**. 원 서명·attempt·active_operation·실패/불명 소모 불변이다. 컷룸에는 승인된 새 연결/history/중복 방지 키만 추가하고 기획 상태를 유지했다. 새 plan/employee_web은 원본과 동일. 원 조사10건·AI 관리자 롤토체스/모바일 퍼즐 소재 **25초** 및 evidence `q0:TAidk7sXHk4`, `q0:0FVBz6iWhOY`, `q1:9YjDIwCAnsw`를 재사용했다. Shorts 형식·영상 권리·성과는 미확정 유지.

계획 SHA `23ee4a8e9e2ab0079a5cf881be852c4f823eac0422f33fde1f357289f48b5c74`, receipt SHA `651b936fb9542aa188a3bf3a0a3ab803e914b8285f26a9e043fd041a9aeeb04b`, selection SHA `e4296e6a276d6462599d3c3bdb1a86bc5fb3ba2472bfd53eb78d98e6a8d47587`와 유효기간을 기존 가드로 검증했다. data/backups/artifacts/.env·키·사용자 미디어·기존 미추적7개 파일을 삭제/초기화/임의 수정하지 않았다. 대표 승인/반려·TTS/MP4/렌더·업로드/게시0회다.

**다음 행동 하나:** 추가 API 없이 미정인 사용자 입력과 직원이 제안해야 할 target_audience를 혼동하지 않도록 native writer 대상 계약을 좁게 보완한다. 이번 stopped 업무를 재실행하거나 동일 계약으로 후속 생성하지 않는다. 이번 소스2개·테스트1개·이 보고서만 main에 commit/push하고 원격 읽기 확인 후 중단한다.
