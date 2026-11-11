# 미션 01 — 대본 provenance 계약 최소 수정 결과

2026-11-12T08:47:15.065762+09:00 (KST). 최신 main `971b5b5`·AGENTS.md·지정 지시서 및 직전 실전 결과를 확인했다. 실제 실패 원문은 없으므로 provenance.mock/model의 반환값이나 실패 원인을 소급 확정하지 않는다.

## 판단과 변경

전송 경로는 `VideoProviderQualityCompany._tool_notice` → `LiveCompany._call`의 system 메시지 → Gemini adapter의 `systemInstruction`이다. 기존 공통 지시는 provenance={author,model,mock}에 actual invocation provenance를 쓰라는 설명만 제공했다. 모델에는 구체적인 서버 고정 출처 값을 명시하지 않으면서, 응답 인수 시 `inspect_script(mock=False)`와 `model==bound_model`을 요구하는 전달 공백이 있었다. 원장에는 서버 설정으로 model/provider/endpoint·전송 예약/HTTP·응답 hash가 기록되며, 모델이 만든 대본 JSON의 provenance는 별도 자기 신고다.

- `companies/video/quality_workflow.py`: 실제 provider 대본 경로의 system 지시에 **provenance.mock=false**, **provenance.model=서버 bound_model**을 명시했다. 미션에서는 `gemini-3.5-flash-lite`다. author는 모델이 주장하는 창작 역할이며 신원 검증이 아님을 명시했다. mock/model은 서버 설정·전송 원장과 일치해야 하며, 그 값을 출력했다는 이유만으로 실제 호출이 입증되는 것은 아니다.
- 응답을 정규화하거나 provenance를 덮어쓰지 않는다. 기존 mock/model 검사와 고정 provider/모델/키·서명/계정 가드를 유지했다. 모의 워크플로의 mock=True 계약도 유지한다. native HTTP 합성 fixture는 실제 호출 계약을 모의할 뿐 최상위 source는 여전히 `offline_http_fixture`이며 실제 결과로 승격하지 않는다.
- 향후 대본 provenance 실패에는 기존 신규 attempt에 `script_provenance_diagnostics`를 기록한다: stage, category, model_matches/mock_matches/ledger_model_matches(bool), response_hash. author·응답 원문·임의 model 문자열·비밀키를 복제하지 않고 실패를 그대로 재전파한다. 기존 실제 실패 원장에는 새 진단을 소급 기록하지 않았다.

## 오프라인 검증

`PYTHONPATH=core:companies/video python -B -m unittest tests.test_video_mission_one tests.test_script_quality tests.test_quality_provider`: **39개 통과, 10.376초**. 임시 합성 저장소·mock native HTTP, DNS/socket 차단에서 관련 묶음을 1회 실행했다. `git diff --check` 통과.

새 검증: 전송될 systemInstruction에 고정 mock/model 및 author 신뢰 설명 포함, 올바른 고정 출처의 합성25초 대본→미정 대상 AI 제안/근거→편집 인수→임시 컷룸 승인 대기, 잘못된 mock 및 다른 model 거부·안전 진단·원문/키 미노출·실패 후 자동 재호출 차단/파일 바이트 불변. 기존 mock/실제 계약 충돌, 주제·길이·transcript·시청자 추론·선정 근거·권리/팩트 불확실성·provider/키/계정·한도/동의 가드 관련 회귀도 통과했다. 테스트 fixture는 실제 실패 응답 복원이나 새 실제 대본이 아니다.

## 실제 상태와 다음 한 단계

실제 Gemini/YouTube/기타 provider API **0회**, 실제 stopped 재실행·신규 실제 업무·승인 생성 **0건**. GitHub 동기화/commit/push만 수행한다. 기존4개 stopped 업무 및 컷룸 관련 JSON/consent/lock 등 **14개 파일 SHA-256 시작/종료 동일**을 확인했다. 서명·attempt·active_operation·실패 응답 hash·원 조사와 선정25초 유지. Gemini 누적 **7/10**, YouTube search **2/4**, videos **2/4**, 컷룸 **research_planning** 그대로다. data/, backups/, artifacts/, .env·키·음성/영상·기존 미추적7개 파일을 수정/삭제하지 않았다.

**다음 한 단계:** 실제 후속 실행 범위와 남은 호출 한도를 대표가 별도로 승인해야 한다. 현재 잔여3회는 실행 허가가 아니며, 새 경로 생성이나 기존 stopped 재전송을 하지 않았다. 실제 모델의 수정된 프롬프트 준수는 미검증이며, 4단계 작성/검토 흐름과 잔여3회의 불일치도 다음 승인 전에 고려해야 한다. 이번에는 실패 복구/실제 대본 완성으로 주장하지 않고 소스1개·테스트1개·이 보고서만 commit/push 후 중단한다.
