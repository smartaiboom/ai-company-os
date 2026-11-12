# 미션 01 — native 시청자 입력/AI 제안 계약 최소 수정

2026-11-12T11:39:25.218265+09:00 (KST). 최신 main `05290ab`·AGENTS.md·지정 지시서·직전 실제 실행 결과를 확인했다. 이번에는 오프라인 계약 수정만 수행했다.

## 변경·판단

`script_quality.py` writer_contract 기본을 **v2**로 올렸다. 입력은 `audience_input={target_segment:미정,user_specified:false}`, 출력은 `audience_output.field=result.content.target_audience` 및 propose_one_concrete_audience_not_input_status 정책으로 분리한다. 원 quality_inputs.target_segment는 변경하지 않는다. schema의 target_audience/unknowns item에 역할 설명을 추가하고, 한국어 지시 및 template_only placeholder 예시로 관리자 선정/관측에 근거한 구체적 대상 하나와 AI 제안·사용자 미확정·실제 이유를 요구한다. 사용자 지정 대상은 기존 enum/정확 일치 검사와 복사 지시를 유지한다. 특정 대상·게임을 개발자가 선정하지 않는다.

현재 확인된 type/string/minLength/enum만으로 특정 문자열 미정만 제외하기는 어렵다. minLength를 늘리면 정상적인 짧은 대상명도 배제하므로 사용하지 않았다. 지시서의 허용된 fallback을 택해 **not/pattern 같은 미확인 schema 키를 넣지 않고 설명·구조화된 계약 정보·한국어 지시를 보강**했다. 따라서 native schema만으로 literal 미정을 논리적으로 배제했다고 주장하지 않는다. 반환 시 기존 서버 검사에서 literal_unspecified_audience로 거부한다. 원문 자동 수정/대본 승격은 없다.

`video_mission_one.py`는 해당 단일 계약의 audience_output_instruction을 실제 writer systemInstruction에 붙인다. 동일 v2 schema는 `generationConfig.responseJsonSchema`와 request output_contract, 전체 계약/예시는 `data.quality.writer_contract`에 전달되고 전송 직전 기존 해시 일치 검사로 검증한다. 이전 native writer 객체/손실 없는 문자열 직렬화·다른 필드 검사는 변경하지 않았다.

v1은 역사 검증용 함수 인자로 정확히 재현 가능하게 보존하고 새 기본 요청은 v2를 사용한다. 공통 successor/서명/중복 가드는 수정하지 않았다. 실제 기존 selection25초를 넣어 함수로 계산한 해시는 다음과 같다.

- 역사 v1: `8d0ff0d818b0f7dfee18c13b506801b00ba588b14d9a45b173e497b6d540672f` (기존 실제 grant와 동일).
- 새 v2: `4b1f627165a8398e3e47549563f8588708bf9066bde6bfd14c980953906355ff`.

실제8번째 업무에 unified_successor_reference를 읽기 전용으로 적용해, signed v1 history는 그대로 증명하고 새 계약 hash/누적11회로 미래 적격 참조를 계산할 수 있음을 확인했다. 실제 업무/제안/grant를 생성하지 않았다.

## 표적 오프라인 시험 1묶음

`PYTHONPATH=core:companies/video python -B -m unittest tests.test_video_mission_one.MissionOneTests.test_writer_schema_covers_required_fields_and_relational_errors tests.test_video_mission_one.MissionOneTests.test_native_audience_v2_preserves_history_and_allows_only_changed_contract`: **2개 통과, 3.762초**. 임시 합성 저장소·mock native HTTP·외부 DNS/socket 차단. `git diff --check` 통과.

입력/출력 역할과 설명/예시/한국어 지시가 실제 payload 세 위치에 들어가는지, v1/v2 hash 차이, literal 미정 거부/detail_code와 재호출 금지, 구체적 AI 미확정 제안·근거 허용, 명시 대상 exact match 및 다른 필드/주제25초/출처 검사를 확인했다. 합성 v1 운영 서명 아래 미정 실패를 남긴 후 같은 계약은 목적 이름만 바꿔도 후속 거부, v2 아래 별도 새 서명/중복 차단·구 hash 변조 거부→writer→manager→editor→manager→동일 임시 컷룸 awaiting_plan_approval을 통과했다. 원 signed 파일 바이트는 유지하고 결과 source는 offline_http_fixture로 구분했다. 합성 대본은 실제 성과가 아니다.

## 실제 보존·한계·다음 행동 하나

**실제 Gemini/YouTube/provider API0회, 실제 새 업무/grant/동의/전송0건.** 과거8개 stopped 업무와 컷룸 JSON/consent/lock **26개 SHA-256 시작/종료 동일**. 누적 Gemini11·YouTube search2/videos2, 컷룸 research_planning, 원 조사10건·관리자25초/원 해시·attempt·active_operation·서명 그대로다. data/backups/artifacts/.env·키·미추적7개 파일·사용자 미디어를 수정/삭제하지 않았다. 무료 임의 상한·모델/계정·유료 전환/자동 retry 정책은 변경하지 않았다.

새 설명/지시를 실제 모델이 준수하는지는 미검증이며 실제 검증된 대본·스토리보드·승인 대기 카드는 아직 없다. **다음 최소 행동:** 별도 대표 승인 아래, 보존된8번째 실패에서 기존 공통 후속 경로를 사용해 v2 계약의 새 독립 업무1건을 새 제안/서명 후 실제 제작하고 동일 컷룸 대표 승인 대기까지만 진행한다. 이번에는 실행하지 않고 소스2개·테스트1개·이 보고서를 GitHub commit/push/main 읽기 확인 후 중단한다.
