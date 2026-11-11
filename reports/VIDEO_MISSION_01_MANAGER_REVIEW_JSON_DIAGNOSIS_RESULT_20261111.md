# 미션 01 — 관리자 검토 JSON 오프라인 진단

2026-11-11T15:17:24+09:00 (KST). 기준 GitHub `74e9373`. **실제 API 호출 0회, 업무 재실행·재개 0회. 보고서만 변경했다.**

## 확인된 실패 지점과 증거 한계

확인 가능한 직접 원인은 **조사 관리자 accept 검토의 `feedback` 문자열을 내부 JSON으로 파싱하는 단계의 실패**다. 바깥 JSON 파싱이나 HTTP 접근 실패가 아니다. 원문이 없어 잘못된 문자·이스케이프·일반 문장·코드 펜스 등 구체적 출력 형태는 확정할 수 없다.

대상은 `qualityprovider-299a51b38e6d4d50b651b9fbb39dabad`, 마지막 시도 `2c9ccf0e1edb4a088b6cb4e9afc14fca`, `review/task_research`다. 원장에는 HTTP 200, finish=stop, envelope_json=parsed, json_parse=parsed, validation=json_parsed, role_result_status=json_parsed가 남아 있다. 응답 크기 1757바이트, 모델 content 길이 798자이며 리뷰 기록은 0건이다. 최종 system_safety_stop 코드는 `invalid_model_json`이다.

코드와 저장 상태를 대조한 경로:

1. `core/autonomous_gemini.py:131`의 `_parse_role_content`는 바깥 content를 parse하고 역할 스키마를 검사한 뒤 `value['result']`를 반환한다. `core/autonomous_live.py:324` 이후 validation=json_parsed 및 response_hash가 기록돼 있으므로 이 단계는 통과했다. 바깥 스키마 불일치였다면 `invalid_role_schema`이고 현재 상태와 다르다.
2. `MissionOneCompany._call` (`companies/video/video_mission_one.py:251`) 이전의 `_manager_selection` (`:203`)은 accepted 연구 업무가 없으므로 None이다. 연구 업무는 실제로 awaiting_ai_review이며 reviews=[]다. 따라서 저장된 과거 feedback을 재파싱하다 난 오류가 아니다.
3. 해당 클래스의 상속 경로를 확인했다. 연구 역할에는 대본 파싱 검사가 없고, 이번 연구는 depends_on=[]여서 선행 대본 파싱도 없다. super 호출이 응답을 반환한 뒤 연구 review/action=accept 분기 `video_mission_one.py:257–258`에서 `validate_selection(parse(result['feedback']), ...)`가 실행된다. 이 분기의 내부 parse가 현재 상태에서 `invalid_model_json`을 일으키는 지점이다. accept 여부는 원문 확인이 아닌 이 분기와 상태에 근거한 추론이다.
4. `core/autonomous_company.py:55`의 parse는 JSON 읽기 중 ValueError/TypeError/RecursionError를 `invalid_model_json`으로 바꾸며 원인 예외는 `from None`으로 숨긴다. 로그에는 이 코드만 있고 traceback·JSON 오류 위치·원인 예외 메시지는 보존되지 않았다. 뒤의 `validate_selection` 필수 필드·근거·길이 검증은 도달 전이다. 이후 공통 validate_review 및 리뷰 저장도 도달하지 못했다.

## 네 가지 가능성 구분

| 구분 | 판단 |
|---|---|
| (a) 실제 JSON 문법 오류 | 바깥 JSON 문법 오류는 배제된다. 내부 feedback의 parse 실패는 코드/상태로 특정되지만, 원문이 없어 구체적인 문법 오류인지 기타 파서 거부 조건인지 구분 불가다. |
| (b) 바깥 래퍼/역할 구조 차이 | 이번 중단 원인으로 배제된다. 바깥 역할 스키마 검사까지 통과한 뒤 해시가 기록됐다. |
| (c) 내부 feedback 기대 형식/필드 불일치 | 내부 문자열의 JSON 파싱 실패는 특정된다. JSON 객체의 필드 누락·길이·근거 ID 불일치는 후속 validate_selection 단계이므로 이번 오류로 확인된 사항이 아니다. |
| (d) 유효한 모델 출력에 비해 과도한 계약 | 바깥 계약은 feedback을 문자열로 허용하지만 미션 프롬프트/코드는 accept feedback에 JSON 문자열을 요구하는 이중 계약이다. 이 구조 차이는 확인됐다. 실제 모델이 일반 문장이나 다른 유효 형식을 반환했는지, 따라서 과도한 계약이 직접 원인인지는 원문 없어 판단 불가다. 검증 완화 근거로 쓰지 않는다. |

## 응답 원문 보존 여부

**이번 실행 경로의 로컬 기록에는 세 번째 실제 응답 원문이 없다.** 대상 업무·동의 파일과 연결 컷룸, 해당 /tmp 제안·실행 로그를 관련 범위에서 확인했다. 제안은 요청 전 자료이고 실행 로그는 `invalid_model_json` 한 줄뿐이다. 업무에는 앞선 계획/조사 결과는 있지만 세 번째 raw envelope·모델 content·미검증 review/feedback 값은 없다. 별도 응답 보관 파일도 해당 업무 저장 위치에서 확인되지 않았다. 전역 개인자료·백업 전수 검색은 하지 않았다.

`FreeCompany._request_json`은 raw/envelope를 메모리에서 처리하고 크기·상태·진단만 저장한다. LiveCompany는 파싱한 역할 결과의 해시만 기록하며, 미션 검사에서 예외가 나 공통 workflow가 review를 저장하기 전에 멈췄다.

- 마지막 response_hash: `d1b0e98009942970d434a4fff91bb1eec759304289940723fa4d0529cb86ec12` — 정규화 후 파싱된 역할 결과의 canonical digest이며 원시 HTTP 바이트의 해시가 아니다.
- 마지막 result_hash: `f276ee45ed2464204e5dcde50cc2cb4a68baa575d0bc820244eaffe3d4767a93` — `LiveCompany._call`의 context.result, 즉 검토 대상인 조사 직원 결과의 해시다. 세 번째 관리자 응답 본문 보관이 아니다.
- 위 해시·길이·진단에서 원문을 복원할 수 없다. 예전 보고서의 상태와 일치하지만 실물 응답의 문법을 재현한 증거는 아니다.

따라서 기존 응답을 추가 호출 없이 오프라인 재파싱·검증·승격하는 것은 불가능하다. 실패 상태를 성공으로 바꾸거나 새 모델 호출로 원문을 재생성하지 않았다.

## 최소 수정 방향과 이번 변경

필요한 최소 방향은 미션의 **연구 accept 검토 계약과 진단 경계**다. 일반 feedback 문자열 계약과 미션의 구조화된 선정 결정 요구를 일치시키는 미션 전용 응답 계약을 설계하고, 내부 parse 실패를 별도 단계로 식별할 수 있는 비밀값 없는 진단을 남겨야 한다. 필수 선정 필드·evidence ID·길이·Shorts 불확실성 검증은 유지해야 한다. 텍스트 JSON 자동 수선·일반 문장을 임의 선정으로 변환·실패 리뷰 강제 수락은 해결책이 아니다. 진단만으로 응답 원문이 없는 과거 업무를 소급 통과시킬 수 없다.

이번에는 제품 코드·테스트를 변경하지 않았고 단위/회귀 테스트도 실행하지 않았다. 실물 응답이 없어 실물 재현 fixture를 만들지 않았으며 가상 예시를 실제 응답으로 표시하지 않았다. 실제 API 전송 함수나 run/prepare/approve를 실행하지 않았다.

## 보존 확인과 다음 조치

작업 중 대상 컷룸 및 두 업무의 JSON·동의·lock 파일 총 7개의 SHA-256을 기록하고 종료 전 동일함을 확인했다. 새 업무는 stopped/invalid_model_json, active_operation은 위 시도 ID, 구 DNS 실패 업무는 stopped/free_request_failed 및 기존 active_operation 유지, 컷룸은 **research_planning**다. Gemini 합산 **4/10회**(과거 실패1+신규3), YouTube search **2/4회**, videos **2/4회**가 보존됐다. 과거 공급자 수신 불명 1회도 소모 유지다. 새로운 제안·서명·업무·요청은 없고 재시도/fallback 0회다. 키·기존 음성/영상·백업·사용자 자료·기존 미추적 파일 7개는 보존했다.

**다음 조치 한 가지:** 사용자 검토 후, 외부 호출 없이 미션 전용 연구 검토 계약과 내부 JSON 실패 진단을 정비하고 명시적으로 합성 표시한 fixture로 검증하는 개발 작업을 진행한다. 실제 재실행은 별도의 새 사용자 승인과 이력·잔여 예산 보존 절차 전까지 금지한다. 현재 업무에 run을 재호출하지 않고 중단한다.
