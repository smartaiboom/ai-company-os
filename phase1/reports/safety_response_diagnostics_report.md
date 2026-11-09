# 안전성 판정 응답 진단 정보 추가 보고서

작업일: 2026-10-29

## 조사 결과

`execution_engine.py`는 API 응답 JSON의 `choices[0].message`에서 `content`를 가져오며, 비어 있으면 `reasoning_content`, `reasoning`, `output_text`를 차례로 확인한다. 결과 문자열 전체가 정규화 후 `user safety: safe`, `safe`, `user safety: unsafe` 중 하나와 정확히 같으면 안전성 판정 전용 응답으로 처리해 업무 결과 저장을 거부한다.

이번 변경은 이 감지 기준이나 `openrouter/free` 검증을 바꾸지 않았다. 실제 모델/제공자가 왜 그 문구만 반환했는지는 확인되지 않았다. 실제 API 호출 없이 코드 경로와 모의 응답으로 검증했다.

## 추가한 진단 로그

안전성 판정 전용 응답 또는 빈 응답이 감지되면 `execution_engine` 경고 로그에 제한된 메타데이터를 기록한다:

- `finish_reason`: 짧은 영숫자/밑줄/하이픈 값만 기록하고, 없거나 형식이 다르면 `missing` 또는 `other`로 기록
- `message_fields`: 값이 아닌 필드 이름만 기록하며 이름 형식과 개수 제한을 적용
- `content_length`: 메시지에서 선택한 본문 문자열(목록형 본문이면 기존 변환 적용)의 문자 수. 응답 전문은 기록하지 않는다.
- `content_empty`: 본문이 비어 있거나 문자열이 아닌지 여부
- `safety_verdict`: 감지된 판정 유형(`safe`/`unsafe`); 빈 응답에서는 `none`

로그에는 API 키, 인증 헤더, 전체 프롬프트, 프로젝트 입력 자료 또는 AI 응답 본문을 기록하지 않는다. 빈 응답의 사용자 오류 메시지에서도 서버가 준 동적 필드명·종료 사유를 제거하고, 진단 로그를 확인하라고 안내한다.

## 테스트 결과

- `python -m unittest tests.test_execution_engine` — **15개 테스트 통과 (OK)**.
- `python -m unittest tests.test_company_workflow_e2e` — **1개 테스트 통과 (OK)**.
- `git diff --check` — 통과.

모의 테스트는 안전성 판정만 있는 응답을 오류로 분류하면서 안전한 진단 로그가 기록되고 응답 본문과 프롬프트 표식은 로그에 들어가지 않는지 검사한다. 빈 응답 로그도 확인한다. 일반 업무 결과에 `safe`라는 단어가 포함되면 업무 결과로 허용됨을 확인한다. 모든 API 전송은 mock 처리했으며 실제 AI API 호출은 없다.

## 확인된 사실과 미확인 사항

**확인된 사실**

- 코드의 안전성 응답 오류 조건은 세 문자열 중 하나와 전체 본문이 정확히 일치하는 경우다.
- 종료 사유, 응답 필드 이름, 본문 문자 수, 빈 여부 및 판정 유형을 제한된 로그로 남긴다.
- 기존 `openrouter/free` 제한 및 유료 모델 차단 경로는 수정하지 않았다.
- 관련 모의 테스트 16개가 통과했다.

**미확인 사항**

- 다음 실제 실행에서 제공자가 어떤 응답 필드와 종료 사유를 반환할지.
- 실제 라우팅 모델/제공자가 안전성 판정 문구만 반환하는 근본 원인.
- 운영 로그 수집기가 이 Python 경고 로그를 어떤 위치와 보존 기간으로 저장하는지. 이번 변경은 표준 Python logger에 기록하며 배포 환경의 로그 설정은 확인하지 않았다.

## 변경 파일 및 보존

- 변경: `execution_engine.py`, `tests/test_execution_engine.py`, `reports/safety_response_diagnostics_report.md`.
- 프로젝트 데이터, 기존 작업 결과, 백업 파일 및 비밀값: 변경하지 않음.
- 실제 AI API 호출: 없음.
