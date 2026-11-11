# 미션 01 — 실제 대본 출처(provenance) 계약 오류의 최소 수정
작성일: 2026-11-12 KST

## 최우선 목표
**실제 미션 01의 대본과 스토리보드 완성이 우선이다.** 이번 작업은 실전 `script_provenance_mismatch` 오류만 바로잡는 **짧은 오프라인 수정 및 테스트**다. 예산 관리 추가 개발, 대규모 리팩터링, 조사·주제·길이 재선정 금지. API를 다시 호출하지 않는다.

## 확인된 실제 결과
- `reports/VIDEO_MISSION_01_APPROVED_WRITER_RESUME_REAL_RUN_RESULT_20261112.md`: 새 업무 `qualityprovider-bb394ad486014277998d8a64b62e8199`, Gemini writer 1회 HTTP200 및 역할 JSON 파싱 성공, `script_provenance_mismatch`로 stopped. 실제 실패 대본 원문은 기록되지 않았고 추정 금지.
- 새 업무 이전 세 stopped 업무 및 원 조사·AI 관리자 선정은 불변. 현재 Gemini 누적 **7/10**, YouTube search **2/4**, videos **2/4**, 컷룸 `company-aba553f29cfb454c8c05bad4abb49969` = `research_planning`.
- `companies/video/script_quality.py` `inspect_script`가 `provenance={author,model,mock}`를 요구하며 실제 호출 mock=False 및 model nonempty를 검사. `video_mission_one.py`는 최종 보고 단계의 model==고정 모델까지 검사. 기존 프롬프트는 'use actual invocation provenance'라고만 전달할 수 있어 실제 출처를 모델이 추측하게 만드는 모순 가능성이 있다.
- 실제 실패 응답의 provenance.mock/model 세부값은 원문 부재로 불명. 새 테스트 fixture를 실제 대본으로 가장하지 말 것.

## 이번에만 할 일
1. `AGENTS.md`, 위 실전 보고, `script_quality.py`, `video_mission_one.py`, `quality_workflow.py`, `core/autonomous_live.py` 등 **해당 provenance 전달/검사 경로만** 확인한다. 정확히 어떤 데이터가 Gemini에 전달되고 무엇이 모델 생성 영역인지, 무엇이 전송 컨텍스트의 시스템 사실인지 분리해 불일치 원인을 문서화한다.
2. **출처 사실은 모델의 자기 신고만 신뢰하지 않는다.** 실제 provider/model/mock 여부는 서버가 고정한 실행 설정/원장에 근거해야 한다. 해결법은 최소 변경을 고르되: 프롬프트에서 직원에게 정확한 `provenance.mock=false`, `provenance.model=gemini-3.5-flash-lite` 형태를 명시하거나, 서버의 신뢰된 전송 메타데이터를 사용하여 구조화된 산출물 출처를 정규화·검증하는 방식을 적용한다. 모든 경우 실제 모델·모의 호출 구분은 원장 근거로 강제하고, 모의 결과를 실제 결과로 승격하거나 provider/검사를 무조건 통과시키지 말 것.
3. `provenance.author` 등 실제 창작 역할 출처와 `provenance.mock/model`의 신뢰 등급을 명시하고, 다른 모델/키/계정·응답 변조와 잘못된 임의 출처는 여전히 거부한다. 검증된 대본의 주제·25초·한국어 transcript·장면·시청자 추론/근거·unknowns·팩트/권리 불확실성 검사 모두 유지. 임의 게임/시청자 답안 주입 금지.
4. 비밀값이나 전체 응답을 남기지 않고, 앞으로의 provenance 실패를 진단할 수 있도록 `stage`, 검사 category, model/mock 일치 여부(원문 문자열 대신 bool), 응답 hash 등 최소 안전 진단을 남기는 방식을 검토한다. 해당 단계에서 수정하더라도 **실패한 원 요청을 복구했다고 주장하지 말 것**.
5. 임시 합성 fixture 오프라인 테스트에 mock/real provenance 충돌·다른 모델·올바른 고정 모델·검증된 실제 동작 구분·25초/선정/대본 다른 검사 보존을 포함한다. 실패→자동 재호출 금지, 원장 이력 불변도 확인. 관련 표적 테스트만 실행.
6. 신규 Gemini/YouTube/기타 실 API **0회**, 실제 stopped 업무 재실행/새 실제 분리 업무/실제 승인 생성 **0건**. 현재 누적 7회 유지, 잔여 3회를 자동 허가로 간주 금지. 기존 4개 stopped 업무의 서명/attempt/active_operation 및 컷룸·사용자 data/, backups/, artifacts/, 키·음성/영상·미추적 파일 보존.
7. **성공/실패/중단 모두** `reports/VIDEO_MISSION_01_WRITER_PROVENANCE_CONTRACT_FIX_RESULT_20261112.md`에 코드 변경·판단 근거·실제 테스트·실 API 0회·이력 보존·다음 한 단계(실제 후속 실행 별도 대표 승인 필요)를 짧게 기록하고 GitHub commit/push 후 중단.

## 금지
기존 실패 호출 재시도, 과거 consent/grant 재사용 또는 만료 우회, 실행 횟수 리셋, mock 출처 조작, 원장 삭제, 유료 전환/대체 모델/자동 fallback, `git clean`/`git reset --hard`/force push. 모든 시각 KST.
