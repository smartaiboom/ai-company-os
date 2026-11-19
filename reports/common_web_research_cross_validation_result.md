# 공통 웹 조사·전문 API 교차 검증

## 기존 구조 확인

| 경로 | 기존 역할과 실행 경계 |
| --- | --- |
| `core/autonomous_company.py`, `autonomous_gemini.py`, `autonomous_gemini35.py`, `ai_provider_adapter.py` | 회사 상태, 직원 결과, 관리자 검토 및 공급자 계약. Gemini 3.5의 `_tool_spec`은 기존 로컬 렌더 JSON 선택·검증을 담당한다. 일반 웹 실행 수단은 없었다. |
| `owner_operating_policy.py`, `project_budget.py`, `project_budget_ledger.py` | 서명 범위, 키 결합, 유효 시간, 시도 예약과 실패 중단을 담당한다. 신규 조사는 고정 무료 한도의 기존 운영 정책을 쓴다. 기존 프로젝트의 예산 승인과 누적 사용량은 그대로 유지한다. |
| `quality_feedback.py` | 검증된 경험과 시청자 조건의 재사용을 담당한다. 이번 조사 결과는 출처를 첨부한 관리자 검토 자료로 건네며, 자동으로 검증된 경험으로 승격하지 않는다. |
| `employee_web_research.py`, `topic_research.py` | 조사 직원이 YouTube 공개 검색 질의를 만들고 코드가 검색·영상 메타데이터를 조회한다. 실제 관측은 관리자에게 다시 전달된다. 별도의 주제 비교는 최신 대상 표본과 배경 지표를 구분하고 시청자 가치·근거·실제 제작 가능성을 평가한다. 조회수 단일 관측으로 성장률, Shorts 여부, 시청자 지역, 영상 권리를 확정할 수 없다. |
| `commons_discovery.py`, `publisher_discovery.py`, `production_sources.py`, `asset_editing.py` | 서버가 승인 범위 안에서 Commons 질의 및 제작사 경로를 제한한다. 기존 AI 담당자가 후보 관련성과 확보·편집 판단을 맡는다. 자료 등록, 권리 검토, 파일 인수 및 합성이 별도 단계다. |

## 무료 도구 조사

- **Google Search Grounding**은 모델 기능 목록에 있으나 Gemini 3.5 Flash-Lite의 API 무료 프로젝트에서는 제공되지 않는다. 문서의 월 5,000건은 결제 연결 플랜의 공용 구간이며 이후 1,000건당 $14다. **URL Context**는 모델 지원 및 도구 무료 조건이 명시돼 있다. URL 직접 입력이 필요하고 토큰·프로젝트 한도가 적용되므로 범용 검색으로 계산하지 않았다. [모델 기능](https://aistudio.google.com/docs/models/gemini-3.5-flash-lite) · [요금과 도구 조건](https://aistudio.google.com/docs/pricing#gemini-3.5-flash-lite) · [URL Context 한계](https://aistudio.google.com/docs/url-context)
- **네이티브 함수 호출** 및 구조화 출력은 모델 문서에 나열돼 있다. 결합은 Gemini 3/4 계열 미리보기로 문서화됐다. 이 저장소의 `generateContent` 계약에서는 네이티브 결합 요청을 실행하지 않았다. 모의 HTTP로 기존 `responseJsonSchema`를 사용한 도구 선택과 결과 관찰을 검증했다. [함수 호출](https://aistudio.google.com/docs/function-calling) · [구조화 출력과 도구](https://aistudio.google.com/docs/structured-output#tools)
- **Tavily** Researcher는 가입 및 API 키가 필요하고 카드 없이 월 1,000크레딧을 제공한다. 기본 검색은 1크레딧, 종량제 선택 시 초과분은 크레딧당 $0.008이다. 신규 경로는 고정 기본 검색 1회만 지원한다. 내부 검색 결과 이용과 발췌 저장은 조건에 따르며 원 사이트의 권리까지 부여하지 않는다. 운영 계정 키 발급·조회·조건 변경은 하지 않았다. [무료 플랜](https://www.tavily.com/pricing) · [크레딧](https://docs.tavily.com/documentation/api-credits) · [API](https://docs.tavily.com/documentation/api-reference/endpoint/search) · [약관](https://www.tavily.com/terms) · [보관 조건](https://help.tavily.com/articles/1612400809-storing-caching-retaining-output)
- **Brave Search**는 무료 전용 플랜 대신 월 $5 크레딧을 제공하며 가입 시 카드 확인이 필요하다. Search는 1,000건당 $5다. 연결하거나 결제 정보를 확인하지 않았다. [공식 요금](https://api-dashboard.search.brave.com/documentation/pricing) · [가입·크레딧 조건](https://api-dashboard.search.brave.com/documentation/resources/help-feedback)

## 구현과 운영 상태

- `core/web_research.py`는 역할별 도구 옵션, 실제 실행 함수, 관측 시점·원출처·근거·범위를 연결한다. 직원은 도구와 승인된 옵션을 선택하고 결과를 받은 뒤 다음 도구 또는 종료를 결정한다. 검색 1회와 Gemini 최대 5회(직원 최대 4회, 관리자 1회)를 기존 서명 원장에 기록한다. 담당자 판단에 따라 전문 자료만 쓰고 종료할 수 있다. 빈 결과와 실패를 구분하고 실패·미확정에서 중단한다. 회차·승인·호출을 재사용하지 않는다.
- 검색 스니펫은 단서다. 직접 확인한 정책 페이지와 전문 API 원 관측은 확인 범위 안에서 사용한다. 인용은 실제 응답의 ID와 발췌에 일치해야 한다. 일치·상충에는 서로 다른 알려진 원출처와 호스트가 필요하다. 재게시와 검색 단서만 있는 주장은 미확인으로 남긴다. 의미와 수치 범위가 주장에 맞는지는 관리자 판단과 실제 원문 검토가 필요하다.
- `core/research_https.py`로 공개 IP 고정 TLS, HTML·robots 응답 처리, 제한 시간 및 접근 규칙을 분리했다. 제작사 실행기는 기존 호스트·경로 검증 및 HTML 추출을 재사용한다. 새로운 조사 범위는 완료된 제작사 HTML/미디어와 YouTube·Commons 관측을 전문 도구로 제공한다. 검색 결과에 나온 임의 호스트를 자동 방문하지 않는다. 기존 제작사 신규 조회는 별도로 승인된 주소에만 적용되며 미디어 다운로드나 게시 권한과 분리된다.
- 승인 전 영상 미션의 기존 기획 동의 화면에 관리자 검토를 통과한 자료를 표시한다. 승인된 자료는 관리자·조사 직원에게 기존 YouTube 근거와 함께 갈 수 있다. 현재 영상 미션에서는 대본·WAV·시간표를 유지하고, 별도 자료 권리 및 편집 범위가 충족됐을 때 서명된 편집 입력에 검토 자료를 첨부할 수 있다. 새 검색 링크로 자산을 등록하거나 편집 가능 여부를 자동 판정하지 않는다.
- 현재 컷룸의 **웹·전문 자료 교차 조사**는 무료 계정 설정 대기다. 무료 Researcher에 결제·종량제가 연결되지 않았고 잔량이 있다는 것을 확인한 뒤 서버 비밀 `TAVILY_API_KEY`와 서버 플래그 `TAVILY_RESEARCHER_FREE_ONLY=1`을 설정하면 **조사 범위 검토·승인 → 조사 실행**을 선택할 수 있다. Google 및 Tavily 계정 조건과 전송 범위는 해당 동의에서 확인한다. 탐색 최대 1크레딧, 무료 Gemini 최대 5회, 비용 상한 $0, 미디어 다운로드 0회다. 운영 계정의 현재 잔량·결제 상태는 API로 독립 확인하지 않았다.
- 원래 Klei 탐색은 GET 최대 4회/Gemini 최대 1회의 미실행 상태다. 최신 Commons 복구 8 GET+1 Gemini의 적합 후보 0건과 기존 서명을 보존했다. 현재 사용권을 확인한 새 자산은 0건이다. 승인 대본 v2, WAV 4개, 840프레임과 대표 평가를 보존했다.

## 검증 및 다음 비교

관련 Python 회귀 테스트 77건, 신규 조사·제작 경계 묶음 17건, 컷룸 Node 시나리오를 통과했다. 모의 HTTP로 모델의 도구 선택, 검색→공식 페이지→전문 기록→정확한 인용을 포함한 상충·미확인 판단→별도 관리자 검토를 확인했다. 전문 도구 단독 종료, 결과 없음, 파일 인수 없이 조회, 가짜 인용과 같은 원출처 중복 차단, 위험 URL과 승인 밖 도구 거부, 승인 전 호출·중복 실행 거부, 429 후 자동 재호출 없음, 승인 기획에 검토 기록 결합을 검증했다. 공개 경로의 robots·외부 호스트·리다이렉트·크기 제한은 기존 제작사 테스트로 확인했다. 컷룸을 기존 환경·루트로 재시작해 localhost와 정적 파일, 원본 JSON·WAV·영상의 해시, 공식 제작사 미실행 상태를 확인했다. 개발 문서 조회 외 실제 운영 Gemini/TTS/검색/다운로드/영상 생성/승인은 각 0회다.

향후 별도 승인 후 동일 모델·목표·기간으로 도구 없는 조사와 교차 조사를 비교한다. 주요 주장 정확도와 출처 원문 일치율, 독립 원출처 수, 상충 발견 및 미확인 표기율, 후보 주제의 다양성, 각 장면에서 권리와 제작 가능성이 확인된 자산의 비율, 호출·크레딧·토큰·소요 시간을 기록한다. 실제 검색 접근과 품질 측정은 미실행이다.
