# 실제 Gemini 재기획 장애 개선 결과
2026-11-13 KST · 기준 main `dc1b61e` · 실제 외부 API 호출 0회, 기존 합성 진단 승인 미소진.

## 실제 성공·실패 비교
로컬 `data/video_representative_workflow/studio`의 업무·전송 원장을 직접 확인했다. 아래 모두 `gemini-3.5-flash-lite`, `/v1beta/models/gemini-3.5-flash-lite:generateContent`다.

| 실제 호출 | 작업 ID | KST | 요청 / 응답 근거 |
|---|---|---|---|
| 가장 이른 대본 HTTP200 | qualityprovider-4cbe762cbf554e40af5e7d990ceaf46b | 11/11 15:31:47~51 | 28,171B, 입력 8,021 / 출력 972토큰, 응답 4,398B. JSON 파싱 성공 후 script_audience_mismatch로 중단, 저장 대본 버전 없음 |
| 처음 서버 검증된 대본 | qualityprovider-da3dcacd66e147318ad83a9634547667 | 11/12 14:08:05~11 | 42,068B, 입력 10,741 / 출력 1,233토큰, 응답 5,291B, validated. 이후 별도 수정 호출의 503과 구별 |
| 대표 제출 v1의 마지막 대본 | qualityprovider-57981d7b32e14a6cbed733eb1f316f61 | 11/12 14:37:16~22 | 52,027B, 입력 13,338 / 출력 987토큰, 응답 4,223B, validated; 작업 needs_user_review, writer 버전 3개(이전 버전 재사용 포함) |
| 재기획 HTTP200 | qualityprovider-3cb52d1ab205460897e9f03fea21ca71 | 11/12 16:06:16~22 | 33,985B, 입력 9,743 / 출력 1,549토큰, 응답 6,797B. API 성공 후 invalid_dependencies |
| 재기획 HTTP503 | qualityprovider-63f5d501fc34496292167736371b990c / qualityprovider-23bccf52ca0d4aa38ba6232c38294b82 | 11/12 16:41:21~23 / 11/13 09:17:59~09:18:01 | 각 36,671B, failed/unvalidated, 응답 hash 없음. context 동일, 요청 차이는 시스템 안내의 작업 ID뿐 |

현재 대본·재기획 모두 `ReworkCompany/MissionOneCompany → VideoProviderQualityCompany → Gemini35Company → Gemini35Adapter`의 공통 native wire 및 `video_mission_one._open_transport → goal_dialogue_live.send_once`를 사용한다. 고정 POST·90초 timeout·프록시 배제·리다이렉트/재시도 금지 경로다. 대본은 execute 단계의 직원 계약, 재기획은 plan 단계의 관리자 계약이라는 차이가 있다. 성공했던 더 큰 요청도 있으므로 **36KB 크기 자체가 503 원인이라고 단정할 근거는 없다**. 과거 503의 오류 본문은 미보존되어 복구 불가능하며 Google 내부 원인은 여전히 미확인이다.

## 최소 수정
- `core/autonomous_gemini.py`: 공통 `_request_json`이 HTTPError를 닫기 전에 호출하는 기존 Gemini 오류 훅을 확장했다. 본문은 4,097바이트를 한 번만 읽어 4KiB 초과 여부를 판정하고, 엄격한 JSON(중복 키/NaN 거부)에서 정수 error.code·허용 목록 status/reason만 `provider_error_body`에 기록한다. raw message/헤더/요청 ID/metadata/키/프롬프트는 저장하지 않는다. 비정상/과대/읽기 실패도 고정 분류만 남기며 원래 실패 처리를 가리지 않는다. UNAVAILABLE 등의 Google RPC 형식 진단은 얻지만 이것만으로 응답 출처를 인증하지 않는다. 기존 HTTP 상태·Retry-After·close·failed 원장·1회 차감·자동 재시도 없음은 유지한다. 다른 제공자의 공통 오류 처리와 정상 응답 경로는 변경하지 않았다. **오류 기록 개선 자체가 503 해결은 아니다.**
- `companies/video/representative_rework.py`: plan 전용으로 사용자 메시지의 중복 output_contract 스키마를 짧은 참조로 바꾸고, 실제 `generationConfig.responseJsonSchema`는 유지한다. 출력 구조·writer→editor 관계·품질/응답 검증은 유지하며 스키마/참조 변조를 거부한다. review와 다른 공통 계약의 전송 구조는 건드리지 않았다. PLAN_RULES를 v3으로 갱신(설명 포함)해 새 서명 hash에 결합하고, 옛 동의로 새 요청을 전송하는 것을 차단한다. 기존 새 준비 경로는 계약이 바뀐 경우에만 이전 1회 복구 제한을 넘어 별도 작업을 준비할 수 있고, 동일 v3 계약 반복은 차단한다. 기존 실패 job 재실행·원장 수정·새 UI는 없다.
- 요청 재생성은 메모리 복사·전송 직전 가로채기로만 확인했다. HEAD의 v2 계약을 적용한 역사 요청은 기존 11/13 request_hash와 정확히 일치, 36,671B다. v3은 34,177B로 2,494B(약 6.8%) 감소했다. 새 요청 hash `e536a8bac9e6384adf47a6b4d2feb763e57d57b8f94046361656844bba59618d`, 새 계약 hash `cb07f445deb5324f4c05917ac88cefd93dd5cdd1342b5f1725881e030f0af95b`. 이것은 오프라인 비교값이며 기존 동의로 송신하지 않았다.

## 검증·보존
`PYTHONPATH=core:companies/video python -B -m unittest tests.test_video_mission_one.MissionOneTests.test_rework_plan_wire_and_http_error_diagnostics_offline tests.test_video_mission_one.MissionOneTests.test_new_consented_rework_after_final_503_to_v2_offline`

한 묶음 실행, **2 tests / 13.656s / OK**. 소켓/DNS 차단·합성 transport만 사용. 민감 메시지 포함 HTTP503→안전 코드 추출·본문 1회 읽기·close·Retry-After·실패 attempt 1개·재시작 거부, malformed/중복 키/NaN/과대 body 차단, 구계약 승인/전송 차단, 스키마·참조 drift 차단을 확인했다. 정상 합성 HTTP200 manager/writer/editor 및 v2 awaiting_plan_approval도 통과했다. 실제 Gemini 성공이나 실제 새 대본 생성으로 보고하지 않는다.

검사 전후 studio 파일 56개의 SHA-256 목록 동일. 기존 job/consent/grant/attempt/plan_versions·서명·산출물·미추적 파일 불변. data/backups/artifacts/.env는 수정하지 않았다. 광범위 회귀·실제 호출·다른 모델·유료 전환·무료 계정 재확인 요청 없음.

**다음 행동 하나:** 컷룸에서 **새 AI 재작업 준비 → v3 전송 범위의 새 독립 동의 → AI 재작업 시작**으로 새 작업을 승인한다. 기존 실패 job은 재실행하지 않는다. 실제 제공자 503이 재발할 수 있고, 다음 시도부터 안전한 상세 오류 코드가 남는다. 이번 작업에서는 새 업무/동의 생성이나 실제 전송을 수행하지 않았다.
