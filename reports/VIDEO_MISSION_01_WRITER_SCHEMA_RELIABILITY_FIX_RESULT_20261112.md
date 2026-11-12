# 미션 01 — writer 전체 스키마 신뢰성 개선

2026-11-12T10:39:22.435487+09:00 (KST). 최신 main `c69d1df`·AGENTS.md·지정 지시서·마지막 실전 결과를 확인했다. 실제 실패 원문/shot_type 값은 없으므로 추정하지 않는다.

## 왜 여러 계약 오류가 드러날 수 있었나

기존 Gemini responseJsonSchema는 execute의 content를 **문자열**로만 제한했다. 실제 대본 JSON은 그 문자열 안에 있어 nested shot_type·provenance·주제·길이를 provider schema가 제한하지 못했다. 설명문과 서버 검사에 의존했고 첫 실패에서 중단돼 다른 오류가 다음 실행에서 드러날 수 있었다. 이는 확인된 구조적 한계이며 과거 모델이 구체적으로 어떤 값을 반환했는지의 증명은 아니다.

## 변경 — 소스3개, 테스트1개

- `script_quality.py`: SHOT_TYPES/SOURCE_STATUSES/FACT_STATUSES를 기존 inspector·설명·schema가 공유한다. `writer_contract`가 required 필드 전체·nested beats/topic/provenance·enum/형식/범위와 relational invariants를 한 곳에서 정의한다. 선정 title, duration, 고정 모델/mock=false는 승인된 context/서버에서 동적으로 넣는다. 이 미션 source_status는 pending 전용, fact_status는 illustrative/verification_pending이다. author는 모델의 창작 역할 주장일 뿐 검증된 신원은 아니다.
- `video_mission_one.py`: writer execute에만 **result.content를 JSON 객체로 받는 native 구조화 schema**를 연결했다. 실제 전송 위치는 `generationConfig.responseJsonSchema`, 동일 계약은 contents의 output_contract와 `data.quality.writer_contract`, 객체 반환 지시는 systemInstruction에 있다. 전송 직전 세 위치의 계약 일치를 검사한다. 다른 역할의 wire 계약은 유지한다. 동적 선정값·25초·원 evidence는 기존 manager_selection으로 계속 인계하며 제목 카피와 후킹 문구를 구분한다.
- 공유 엔진은 content 문자열을 저장하므로 수신 객체를 **값 변경 없이 JSON 직렬화**한다. 모델의 잘못된 값을 서버가 덮어쓰거나 수선하지 않는다. nested enum/required/type은 schema와 서버 검사 모두 사용하고, schema만으로 표현할 수 없는 장면 연속성·0–3초 hook/최종 길이·transcript/close 일치·미정 대상 추론/근거는 서버의 shared validator에서 검사한다. 장면 연속성/hook/최종 길이 결함은 이 구조화 writer 경로에서 저장 전 invalid_script_timeline으로 거부한다. 일반 inspector의 기존 품질 결함 보고 방식은 유지한다.
- `quality_workflow.py`: writer hard error 전반을 기존 신규 attempt의 script_validation_diagnostics로 기록한다. category/error_code·고정 field_path, enum 오류의 첫 beat 인덱스·allowed_set_match·타입/안전한 길이·응답 hash만 저장한다. 예: invalid_script_shot → narrative_beats[0].shot_type. audience/provenance/topic 기존 진단도 유지한다. wire 객체 계약 오류도 안전한 경로/hash로 남긴다. 원문·대상값·API 키를 복제하지 않고 실패는 stopped/재시도 금지다. 과거 실제7개 원장은 수정하지 않았다.

소스 변화는 위3개와 관련 테스트뿐이다. 예산/무료 정책·다른 서비스·새 successor CLI를 추가하지 않았다. 잘못된 유료 경로/모델·중복/불명 전송 가드와 최종 사람 승인 경계는 그대로다.

## 표적 오프라인 검증

한 unittest 묶음에서 다음5개를 실행: writer required/관계 오류 단위 사례, native 잘못된 shot 안전 진단, 기존6개 합성 실패 체인을 재사용하는 종단 인수, 제목 공백 불일치 거부, 미정 추론 이유 누락 진단. **5개 통과, 3.386초**. `PYTHONPATH=core:companies/video python -B -m unittest`에 해당 개별 사례를 지정했다. `git diff --check` 통과.

임시 저장소·mock native HTTP·외부 DNS/socket 차단에서 실제 요청의 schema/context/system 지시 위치를 검증했다. required 필드 각각 제거 시 거부, shot_type 세 허용값 수락, 잘못된 shot/source/fact/title/model/mock/audience/timeline/transcript/길이 거부, 진단 원문·키 미노출, 실패 후 재호출0 및 파일 불변을 확인했다. 합성25초·원 가상 선정/관측 재사용→writer→manager review→editor→manager review→임시 동일 컷룸 awaiting_plan_approval을 통과했다. source=offline_http_fixture이며 실제 AI 대본이 아니다. 이전 전체 테스트를 반복하지 않았다.

실제 Gemini가 이 확장 schema를 수용하고 새 계약을 준수하는지는 외부 요청0회이므로 미검증이다. native schema는 관계/의미 품질 전체를 표현하지 못하므로 서버 검사와 관리자 검토가 계속 필요하다.

## 반복 successor 문제 — 구현하지 않은 최소 제안

사유별 CLI를 계속 늘리는 대신, **단일 검증된 후속 진입점**이 다음을 수행하도록 좁게 설계한다.

1. 원 signed chain/목표·사용자 입력/동일 컷룸·모델/계정/키·데이터 정책·원본/관측 기간과 accepted 결과만 검증한다. 과거 attempt ID/소모/실패·grant hash·storage hash를 immutable receipt로 참조한다. 불명 전송을 같은 작업 재전송으로 복구하지 않는다.
2. 실패 task와 새 요청 목적/수정된 writer 계약 version/schema hash를 명시한 사용자 승인 범위로 새 proposal/grant를 만든다. 이미 accepted된 계획/조사/선정은 참조하고 실패 대본은 이식하지 않는다. 무료 카운터를 새 실행 허가로 취급하지 않는다.
3. `(원업무 ID, 새 목적 hash, 새 계약 hash)`에 대한 프로젝트 잠금/단일 successor 연결로 중복 생성을 막고, 새 동의/시도/세션으로 실행한다. 기존 실패별 검증기는 역사 증명의 adapter로 재사용하고 과거 grant/attempt를 수정하지 않는다.

이는 설계 메모이며 범용 successor 코드·실제 업무/동의는 만들지 않았다. 기존 체인을 한꺼번에 마이그레이션하지 않는다. 응답 원문 보관도 구현하지 않았다. 필요 시 별도 동의 아래 별도 암호화 키·0600 파일·짧은 보존기간·브라우저/로그 미노출을 갖춘 진단 저장을 검토할 수 있으나 이번 범위를 확장하지 않았다.

## 실제 보존과 다음 행동 하나

**실제 provider API0회, 실제 successor/grant/승인 생성0건.** 원7개 stopped 업무 및 컷룸 관련 JSON/consent/lock **23개 SHA-256 시작/종료 동일**. Gemini 누적10·YouTube search2/videos2, 컷룸 research_planning, 원 조사10건/관리자25초 선정·서명·attempt·active_operation 그대로다. data/backups/artifacts/.env·키·사용자 미디어·기존 미추적7개 파일을 변경/삭제하지 않았다.

**다음 최소 행동:** 별도 실행 승인 범위에서 일곱 번째 invalid_script_shot 실패를 보존하는 단일 검증 후속 연결을 최소 구현·확인하고, 이 writer 객체 계약으로 실제 대본/스토리보드 제작을 바로 수행한다. 현재 실패를 억지 run하거나 자동 successor를 만들지 않았다. 이번 소스3개·테스트1개·이 보고서를 GitHub commit/push하고 main 읽기 확인 후 중단한다.
