# 미션 01 — 잔여량 게이트 수정 및 실행 판단

2026-11-11 KST. 기준 HEAD `4293780` (`main`, 최신 지시서 fast-forward 반영).

## 변경

- `companies/video/video_mission_one.py`: 공급자 잔여량은 생략 시 `unknown`으로 제안에 기록한다. 관측 정수는 0 이상만 허용하며 음수·불리언·문자 숫자 등을 거부한다. 잔여량을 승인 예산으로 사용하지 않는다. Gemini 승인 상한 10회, YouTube 검색/메타데이터 상한 각각 4회를 별도 서명 대상 필드로 고정했다. CLI 잔여량 인수는 선택 사항이다.
- `companies/video/employee_web_research.py`: 기존 합계 8회 제한에 검색·메타데이터 각각 4회 제한을 송신 전 추가했다. 기존 배치 예약·요청별 선소모·실패/불명 상태 재실행 차단은 유지한다.
- `tests/test_video_mission_one.py`, `tests/test_employee_web_research.py`: unknown 잔여 승인·격리 모의 인수, 상한 변조, 잘못된 관측값, 서명 검토 해시 불일치, Billing 비활성 확인 누락, 다른 엔드포인트, 429/timeout 소모와 재호출 금지, 검색 4회/메타데이터 4회 및 초과 질의 차단을 검증했다.

`core/` 엔진·UI·기존 데이터·서명/시도 원장은 수정하지 않았다. 승인 본문이 달라지므로 이전 제안은 그대로 사용하지 않고 새 본문/해시 검토가 필요하다. 기존 consent 파일을 재작성하거나 자동 마이그레이션하지 않았다. 현재 대상 업무의 consent는 비어 있어 이전 승인 이관은 발생하지 않았다.

## 검증 결과

`PYTHONPATH=core:companies/video python -B -m unittest tests.test_video_mission_one tests.test_employee_web_research tests.test_representative_workflow tests.test_quality_provider`: **20개 통과**, 56.736초. 관련 테스트는 임시 저장소와 모의 전송을 사용했다. 실제 미션 상태로 저장하지 않았다. 테스트 실행 중 추가한 웹 상한 변조 검증을 반영한 뒤 해당 통합 사례 1개도 재실행해 통과했다. `git diff --check` 통과.

기존 10회 모의 기획/수정 경로 및 8회 텍스트+2회 웹 모의 인수도 통과했다. 이는 실제 모델의 조사·대본 생성이나 실제 무료 접근 성공 증거가 아니다.

## 안전 판단 및 실제 상태

최신 지시서의 기존 승인(텍스트 최대 10, 검색/메타데이터 각각 최대 4, 무료 전용, 데이터 처리 동의)을 수용했다. 키·YouTube 할당량·결제 등록 여부에 대한 일괄 감사를 반복하지 않았다. 잔여량 미확인은 더 이상 차단 사유가 아니다. 무료 이용 조건과 승인 상한은 별개다. 기존 `billing_disabled=True`, `free_usage_verified=True`는 소유자 확인 진술이며 공급자 조회나 비용 보증이 아니라는 점을 코드에 명시했다. 정확 모델/엔드포인트·실행 플래그·서명·키 연결·만료·중복 실행·총 시도 소모 가드는 유지했다. 유료 fallback과 자동 재시도는 추가하지 않았다.

**불충족 조건 한 가지:** 현재 실행 키가 속한 프로젝트에 Billing이 연결되지 않았다는 프로젝트별 근거가 없다. 사용자 보고 “Google Cloud 결제 미등록”은 근거의 일부로 수용했지만, 특정 실행 키 프로젝트와 연결되는 확인 자료가 없어 과금 노출이 없다고 확정하지 않았다. 코드에 임의 프로젝트/무료 확인 사실을 입력하지 않았다.

**정확한 해결 방법:** 현재 Gemini 키가 소속된 프로젝트를 AI Studio에서 확인하고, 동일 프로젝트의 Cloud Console Billing 화면에서 결제 계정 미연결 상태를 확인한 비밀정보 없는 프로젝트 식별 정보·확인 시각을 제공한다. 키 원문은 필요 없다. 잔여 쿼터 숫자나 사전 성공 API 호출 증거는 요구하지 않는다. 이 조건이 해소되면 unknown 잔여량으로 기존 `prepare → approve → run`을 진행할 수 있다. 이번에는 무료 안전 조건 미충족에 따라 이 명령들을 실행하지 않았다.

|실제 실행 항목|결과|
|---|---|
|Gemini 요청/실패|0 / 0|
|YouTube search 요청/실패|0 / 0|
|YouTube videos 요청/실패|0 / 0|
|API 시험 호출·자동 재시도·모델 대체|모두 0|
|신규 제안/서명/세션/예약|0|
|컷룸 `company-aba553f29cfb454c8c05bad4abb49969`|`research_planning` 유지|
|업무 `qualityprovider-504d90900918450f98dd62b6f7704f1b`|`ready`, consent 비어 있음, 텍스트/웹 시도 0|
|실제 게임·길이·대본·대표 승인 대기 카드|생성하지 않음|

로컬 확인 참조는 `data/video_representative_workflow/studio/`의 위 컷룸 JSON 및 `mission_one_provider/`의 위 업무 JSON이다. 이 파일들은 읽기만 했다. 과거 음성/영상·동의/시도 원장·백업·`.env`에 쓰기/삭제/재실행을 하지 않았다. 기존 미추적 로그/프로브 7개도 보존하고 커밋에서 제외한다. 이번 저장 범위는 코드 2개·관련 테스트 2개·이 보고서다. 대표 승인·TTS/WAV·MP4·업로드/게시 없이 중단한다.
