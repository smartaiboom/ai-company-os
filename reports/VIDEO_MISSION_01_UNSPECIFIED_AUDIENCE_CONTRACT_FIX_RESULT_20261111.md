# 미션 01 — 대상 시청자 미정 계약 수정 결과

2026-11-11T15:39:50+09:00 (KST). 기준 GitHub `00dc7c3`.

## 변경과 근거

`미정`은 사용자가 대상 시청자를 지정하지 않은 상태다. 이를 실제 대상 이름으로 대본에 그대로 출력하도록 요구하던 검사와 추론 허용 프롬프트 사이의 불일치를 수정했다. 실제 실패 대본 원문은 보존되지 않았으므로 당시 출력한 audience 값이나 이 수정으로 실제 모델 문제가 해결됐다고 추정하지 않는다.

- `companies/video/script_quality.py`: `inspect_script`에서 입력 audience가 정확히 `미정`인 경우에만 AI의 구체적 target_audience 제안을 허용한다. 제안값 자체가 `미정`이면 거부하며, 기존 unknowns에 `AI 추론(사용자 미확정):`로 시작하고 제안 대상값 및 비어 있지 않은 `근거:` 설명을 포함하도록 강제한다. 표시는 모델이 작성하고 프로그램은 검사만 한다. 구체적으로 지정된 사용자 audience는 기존의 정확한 일치 검사를 그대로 적용한다. 공통 대본 프롬프트에도 같은 조건을 명시했다.
- `companies/video/video_mission_one.py`: 미션의 두 분기에서 exact target_segment 요구와 미정 추론 요구가 충돌하지 않도록 같은 명시적 audience 정책을 전달한다. 입력 target_segment를 덮어쓰거나 대본을 자동 재작성하지 않는다. 기존 대본 생성/검토/최종 인수는 동일 inspect_script 조건을 재사용한다.
- 대본 직원의 `script_audience_mismatch` 또는 `script_audience_inference_required` 실패에 한해 기존 신규 시도의 `script_validation_diagnostics`에 stage=writer_script_validation, category, field=target_audience, audience_unspecified, response_bytes, response_hash를 기록한다. 원문·실제 대상 문자열·키·헤더·개인 자료는 진단에 복제하지 않는다. 검사 실패는 여전히 중단되며 자동 수선/재시도하지 않는다.

주제·길이·모델 provenance·narration beats·자막·transcript·근거 ID·권리/팩트 불확실성 및 기타 검증을 제거하거나 완화하지 않았다. 기존 확정 audience의 뜻도 변경하지 않았다. unknowns의 대상 제안은 사용자 사전 확정값이 아니라 AI의 미확정 추론으로 남는다. 구체적인 게임/시청자/길이 답안을 제품 코드에 주입하지 않았다.

## 오프라인 검증

`tests/test_script_quality.py`, `tests/test_video_mission_one.py`에 **명시적 합성 fixture**를 추가했다. 실제 실패 대본을 재현한 fixture가 아니며, 실제 사용자 프로젝트에는 등록하지 않았다. 임시 저장소에서 소켓/DNS를 차단하고 HTTP 전송을 모의했다.

- `PYTHONPATH=core:companies/video python -B -m unittest tests.test_script_quality tests.test_video_mission_one tests.test_employee_web_research tests.test_quality_provider`: **37개 통과, 9.581초**.
- 이후 미정 대상의 선정 주제 변조 사례 1개를 추가해 해당 테스트만 실행: **1개 통과, 0.289초**. 전체 회귀를 반복하지 않았다.
- `git diff --check` 통과.

미정 입력 그대로/AI 대상·근거 표시/모델 provenance·unknowns 보존 → 대본 검토·편집 → 임시 컷룸 대표 승인 대기까지 인수했다. 확정 audience 불일치, 미정의 추론 표시 누락, literal 미정 대상은 거부했다. 새 진단 필드와 실패 후 추가 호출 차단을 확인했다. 길이·transcript·provenance 변조, 관리자 선정 주제 변조도 거부했다. 기존 실제 증거 ID 변조 차단, 호출 상한·동의·원장 보존 테스트도 통과했다. 합성 결과는 offline_http_fixture로 구분되며 실제 AI 산출물로 표시하지 않았다.

## 실제 데이터 보존과 제한

실제 Gemini/YouTube 등 API 요청 **0회**, 실제 stopped 업무 재실행/재개 **0회**, 신규 실제 successor·제안·서명 생성 **0건**이다. 작업 시작 시 세 stopped 업무 및 컷룸의 JSON/consent/lock 파일 10개에 대해 SHA-256을 기록하고 종료 시 동일함을 확인했다.

- 첫 업무 `qualityprovider-504d90900918450f98dd62b6f7704f1b`: stopped/free_request_failed.
- 두 번째 업무 `qualityprovider-299a51b38e6d4d50b651b9fbb39dabad`: stopped/invalid_model_json.
- 세 번째 업무 `qualityprovider-4cbe762cbf554e40af5e7d990ceaf46b`: stopped/script_audience_mismatch, 기존 active_operation `a9d4f025a5614afc9882f8d9dba70a79` 보존.
- 컷룸 `company-aba553f29cfb454c8c05bad4abb49969`: research_planning 유지. Gemini 누적 **6/10**, YouTube search **2/4**, videos **2/4** 유지. 복제된 조사 캐시 요청을 신규 호출로 중복 집계하지 않았다.

이전 관리자 선정 게임·25초·증거 3개 ID·미확인 분류/권리 기록을 변경하지 않았다. 사용자 자료·키·음성/영상·백업·기존 미추적 파일 7개 보존. 위 표적 소스/테스트와 이 보고서 외 무관한 파일은 커밋하지 않는다.

남은 한계는 실제 모델 응답의 새 계약 준수와 제안 대상의 의미적 타당성이다. 표식과 근거 텍스트를 검사한 결과가 사용자 확인이나 시청자 반응 검증을 뜻하지 않는다. 기존 실패 응답 원문이 없으므로 소급 재검증/성공 승격은 불가능하다.

**다음 한 단계:** 사용자 검토 후, 기존 누적 소모·검증된 선정의 출처를 보존하는 후속 실행 절차와 별도 승인 범위를 결정한다. 이번에는 실제 API·추가 후속 업무·서명을 만들지 않고 중단한다.
