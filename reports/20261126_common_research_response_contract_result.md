# 공통 조사 응답 계약과 개발 검증 범위

2026-11-26 KST · 깨끗한 로컬 `main`을 `140c83b`로 fast-forward했다. 두 기존 실제 요청의 서명·실패 원장과 운영 데이터·백업을 보존했다. 기존 공급자·모델·연결 설정을 사용한다.

## 구현과 안전 경계

- 기존 두 실제 응답의 `option_not_allowed`, `mixed_tool_and_report`를 검토했다. 일반 조사에 공통 정규화를 연결했다. 도구와 옵션 조합이 명확하고 허용되며 부가 보고 필드도 내용·인용 검증을 통과한 경우에만 보고 필드를 수집 실행 입력에서 분리한다. 모델의 원본 결정, 정규화 결정, 이유와 해시를 로컬 시도 원장에 함께 저장한다. 분리한 주장은 근거 목록과 관리자 보고서에 들어가지 않는다. 모호한 명령, 잘못된 옵션, 권한·인용·사실 검증 위반은 실행 전에 차단한다.
- 기존 `OwnerOperatingPolicy`와 단계별 예약을 재사용해 **개발 검증**을 별도 서명으로 제공한다. 서명 해시에 프로젝트와 입력 참조, 공급자·모델·목적지, 데이터 유형과 검증 목적을 결합한다. 유효기간은 24시간이며 무료 전용·비용 $0, 공급자 잔량·청구 미확인 조건이다. 개발 범위 전체에 별도 호출 수치를 두지 않고, 한 조사 단계의 도구 수집·완료 조건과 공급자 한도를 적용한다. 기존 운영 수치형 계약을 유지한다.
- 새 범위에서 응답 수신과 로컬 계약 오류가 서명된 시도로 입증된 경우에 한해 서버의 검증 규칙·수정 지시로 **결정당 한 번** 다른 본문의 새 요청을 예약한다. 기존 실패 원장은 성공으로 수정되지 않으며, 성공한 보정과의 연결만 새 예약에 남는다. 첫 두 실패 본문 해시와 현재 단계 중복 본문을 차단한다. 보정 실패, 전송 미확정, 공급자·쿼터·권한 오류에서 멈춘다. 조사 보고서는 대표 검토 단계에 머물며 현재 개발 서명은 별도 운영 재작성 요청에 자동 적용되지 않는다.

## 집중 검증

- `PYTHONPATH=core:companies/video .venv/bin/python -B -m unittest tests.test_general_research_report tests.test_web_research tests.test_owner_operating_policy tests.test_research_replanning tests.test_supplement_response_contract -q` 결과 **37개 통과**. 허용된 수집의 원본 보존, 잘못된 도구·옵션·인용 및 근거 부족 차단, 정상 수집·보고, 새 서명·기한·철회, 중복 차단, 새 예약으로 보정 성공, 두 번째 계약 오류와 503·429·타임아웃 중단을 확인했다.
- `node --check companies/video/studio/studio.js` 및 `git diff --check`를 통과했다. 실제 프로젝트에서 Chromium을 GET 전용으로 열어 개발 승인 모달의 목적지·데이터, 결정당 보정 한 번 및 미선택 승인란을 점검했다. 이 단계에서 외부 요청은 없었다.

## 실제 실행 및 재개

- 실제 프로젝트 `company-02a635f303c947d3a075bd5a12f52535`에 **서명 없는 개발 검증 승인 초안**을 준비했다. 현재 승인, 새 예약, 실제 공급자 호출 및 보고서는 각 0건이다. 로컬 단계 경로는 `data/video_representative_workflow/studio/research-company-02a635f303c947d3a075bd5a12f52535-a215e7709a223c08dccf/`이고 개발 범위 서명·누적 원장은 같은 이름에 `-work`를 붙인 위치다.
- [컷룸 승인 화면](http://127.0.0.1:44453/#project/workspace/company-02a635f303c947d3a075bd5a12f52535)에서 **조사 범위 검토·승인**을 한 번 저장한다. 이 개발 범위의 실제 외부 전송을 대화에서도 명시 승인한 뒤 실행 권한 심사를 거친다. 발급 이후 24시간·무료 전용 $0 조건이다. 목적지는 아래와 같고 기존 로컬 공급자 키에 결합한다.

| 공급자 및 목적지 | 승인 데이터 |
|---|---|
| Gemini `gemini-3.5-flash-lite`, 제작 프로젝트 `gen-lang-client-0938732315`, `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent` | 조사 목표·제약, 도구와 승인 공개 질의, 관측 근거, 해당 업무의 이전 보고와 피드백, 서버 정의 검증 규칙과 수정 지시 |
| Tavily Researcher 기본 검색, `https://api.tavily.com/search` | 승인 공개 검색어 |
| YouTube Data API v3, `https://www.googleapis.com/youtube/v3/search` 및 `https://www.googleapis.com/youtube/v3/videos` | 승인 공개 검색어와 공개 영상 ID |

- 다음 실행은 기존 컷룸 **실제 조사 시작**에서 신규 서명과 예약을 대조한 뒤 진행한다. 새 실제 보고서가 없어 공개 출처와 관측일, 표본 조회수·길이, 시청자 가치, 시연과 편집 권리, 상충 근거 및 대표 품질 검토는 미완료다. 모의 제출 성공을 실제 품질 평가에 사용하지 않았다.
