# 미션 01 — 관리자 선정 주제 전달 계약 최소 수정

2026-11-12T09:59:09.905200+09:00 (KST). 최신 main `15e7a6d`·AGENTS.md·지정 지시서·직전 실제 실행 결과를 확인했다. 실제 실패 응답 원문은 없으므로 제목만 달랐는지 의미상 주제가 바뀌었는지 확정하지 않는다.

## 변경·판단

기존 `_mission_call`은 검증된 관리자 selection을 `quality.manager_selection`에 동적으로 주입했지만, 재사용 분기의 시스템 지시는 topic/title의 정확한 필드 연결을 명시하지 않았다. 새 제목 필드나 스키마를 만들지 않고 고정값 복사 규칙을 분명히 하는 최소 방법을 선택했다.

- **소스1개** `companies/video/video_mission_one.py`: 게임 미션의 실제 시스템 지시에 `topic.title = quality.manager_selection.selected_topic`을 명시했다. 승인된 context의 동적 문자열을 공백·문장부호까지 그대로 복사하고, 축약/의역/번역/재선정하지 않도록 한다. 창의적 시청자용 문구는 기존 hook_0_3s/promise/viewing_reason에 작성하게 구분했다. 게임/제목 답안을 제품 코드에 하드코딩하지 않았고 원 selection을 변경하지 않는다.
- 완전 일치 검사는 유지한다. 공백 차이도 자동 허용/수선하지 않는다. 이후 불일치의 신규 attempt에만 script_validation_diagnostics를 저장한다: stage=writer_selected_topic_validation, category=mission_selected_topic_mismatch, exact_match/normalized_match(boolean), 두 문자열 길이·해시 및 응답 해시. 정규화 비교는 NFKC·연속 공백·대소문자 기준의 진단일 뿐 수락 조건이 아니다. 원문·키·대상 문자열을 복제하지 않으며 실패는 기존 stopped 정책으로 유지한다. 이미 stopped된 실제6번째 원장에는 진단을 소급 기록하지 않았다.

## 표적 검증 — 묶음1회

**변경한 테스트 파일1개** `tests/test_video_mission_one.py`. 같은 unittest 실행에 아래7개만 포함했다: 새 복사 계약/25초 인수, 공백 차이 불일치 진단, 기존 다른 주제 거부, 다른 모델 거부, mock 충돌 거부, 미정 대상 이유 누락 진단, 기존 대본 필드 보존 테스트. **7개 통과, 1.840초**. `PYTHONPATH=core:companies/video python -B -m unittest`에서 위 개별 사례들을 지정했다. `git diff --check` 통과.

임시 저장소·합성 fixture·mock native HTTP·외부 DNS/socket 차단에서, 전송될 systemInstruction의 복사 규칙과 context의 정확한 동적 선정값을 함께 확인했다. 다른 합성 선정 문자열을 정확히 복사한25초 대본은 미정 대상 제안/근거·실제 호출 계약의 model/mock 검사→관리자 수락→editor→관리자 수락→임시 컷룸 awaiting_plan_approval을 통과했다. source=offline_http_fixture 유지로 실제 성과와 구분했다. 기존 장면/transcript·출처·권리 불확실성 검사도 유지한다.

다른 제목은 normalized_match=false, 공백만 바꾼 제목은 normalized_match=true여도 둘 다 실패했다. 진단의 길이/해시·원문/키/대상 미노출·실패 후 재호출0 및 파일 바이트 불변을 확인했다. 서버가 모델 대본을 교체하지 않았고 실제 모델이 새 지시를 따르는지는 미검증이다.

## 실제 보존·다음 한 단계

**실제 Google/provider API0회, 실제 신규 업무/동의/grant/승인0건.** 기존6개 stopped 업무와 컷룸 JSON/consent/lock **20개 SHA-256 시작/종료 동일**. 실제 누적 Gemini9·YouTube search2/videos2, 컷룸 research_planning 그대로다. 원 조사10건·관리자 선정25초/evidence·원본 연결 해시·서명·attempt·active_operation을 변경하지 않았다. data/, backups/, artifacts/, .env·키·미디어·기존 미추적7개 파일을 수정/삭제하지 않았다. 호출/예산 정책과 다른 기능은 변경하지 않았다.

**다음 최소 절차:** 여섯 번째 mission_selected_topic_mismatch 실패와 누적9회를 보존하는 별도 신규 업무 경로 및 실제 실행 승인 필요. 기존 audience-successor 가드는 다섯 번째 실패 전용이므로 여섯 번째 업무에 우회 적용하지 않는다. 이번에는 후속 경로/실제 제안·서명·실행을 만들지 않고 소스1개·테스트1개·이 보고서만 GitHub commit/push 후 중단한다.
