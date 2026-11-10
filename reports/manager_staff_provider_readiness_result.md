# 관리자·직원 provider 연결 준비 결과 — 2026-11-10 KST

## 판정

별도 실AI 전용 저장소/실행 경계와 실제 Gemini native 요청·응답 경로를 구현하고 **모의 HTTP로 계약 검증**했다. 실제 모델 추론 성공, 실제 무료 계정 검증, 영상 품질 향상이나 운영 전환을 증명한 결과가 아니다. 실제 API 호출0회/비용0원/외부 자료 전송0회. 기존 mock 경로와 인수1/1 저장소는 유지했다.

지정 보고서 실제 경로: `reports/manager_staff_provider_readiness_result.md`.
샘플: `/tmp/manager_staff_provider_20261110/sample.json` (요청 본문 컨텍스트, 수정 전후 프로젝트, QA, 피드백 수신/선택 기록). 로그: 같은 폴더의 `integration.log`, `focused.log`. 모두 로컬 테스트 자료이며 GitHub 업로드 대상이 아니다.

## 구현 및 기존 코드 재사용

- `core/quality_provider.py`: `QualityProviderStore`/`QualityProviderCompany`. 기존 Gemini35Store/Company, Gemini native wire 어댑터, strict 역할 JSON schema, 서명·취소·만료 동의, 호출 선예약/해시/잠금/중단·재시도 차단 재사용. 저장소 표식 `.quality-provider-gemini35-v1`, mode/policy `quality_provider_gemini35_v1`. mock 프로젝트를 변환하거나 simulation 값을 바꾸지 않는다. 실AI 모드는 simulation=false이며 테스트에서만 HTTP를 대체했다.
- 품질 입력의 domain/대상/답변/제약/capabilities/선별 경험/피드백 원문과 해시, 역할 prompt 해시를 동의 계약에 추가. 입력 변경 시 승인 불일치로 차단. 외부 호출 기본 정책 `QUALITY_TRANSPORT_ENABLED=False`는 환경변수/키 존재/일반 서명 동의로 활성화되지 않는다. 1~20회의 유한 호출 cap만 허용(기본12); 기존 수정·실행시간·pacing·중복연산 보호 유지.
- `core/autonomous_live.py`: 기본값이 빈 집합인 추가 컨텍스트 허용 필드 확장점만 추가. 기존 provider의 허용 데이터 범위는 그대로이고 새 클래스에서만 품질 컨텍스트 허용.
- `core/quality_feedback.py`: 기존 경험 선택 정책을 공통 함수로 추출. 기존 mock 저널의 구조/수정·철회/provenance는 유지. 새 실AI 피드백은 별도 실AI 프로젝트의 `feedback_proposals`에 기록한다.
- `companies/video/quality_workflow.py`: `VideoProviderQualityCompany` 추가. 기존 대본/샷/음성 artifact 검증·수치 반복 검사 재사용. writer/editor/voice/qa/feedback를 capability로 제공하고 실제 역할·의존성·내용은 모델 응답에서 결정. QA 모델의 assessments/defects를 별도 검증; 음성·구성·동기·게시 감각 항목의 근거 없는 met/점수는 거절. 계획 경로는 `external_clip_pending`으로 종료하며 재실행 시 추가 호출 없음.
- `tests/test_quality_provider.py`: 소켓/DNS 차단+HTTP 대체 상태에서 native 요청→모델 답변 검증→계획→실제 결과/해시 인수→수정→QA→피드백 수신·선별→철회 검증 및 안전 실패 사례6개. `README.md`에 새 API와 비활성 정책/샘플 저장법 설명.

## 역할별 프롬프트·출력 계약과 공개 데이터 범위

공통 ROLE_CONTRACTS와 영상 역할 지시는 목표 시청자, 필요한 질문과 이유, 한 가지 메시지,60초 흐름, 장면/실제 소스 수량, 대본/목소리, 업무 분배/완료 기준/재작업 근거를 요구한다. 새 고정 질문·후크·대본 생성 규칙은 없다. 필요한 질문은 모델이 stop과 이유로 제시하는 최소 경계이며, 새 적응형 문답 UI는 구현하지 않았다.

- plan/execute/review/finalize는 기존 공급자 비종속 역할 계약과 `role_json_schema.py`를 유지. Gemini 어댑터는 이를 native `responseJsonSchema`와 `{result:...}`로 변환한다. 다른 provider의 wire 어댑터·계정 정책은 별도로 연결해야 하며 임의 provider 등록/endpoint 변경은 제공하지 않는다.
- 직원의 content는 JSON 문자열이며 도메인별 artifact 계약으로 다시 검증한다. `previous_results`, `handoff_refs`(task/revision/hash/source), `version_history`, `revision_feedback`, 대상/제약/선별 경험을 전달한다. JSON 자동수정·도구 실행·영상 생성 없음.
- 요청은 명시적인 planning inputs와 엔진이 생성한 계획·결과·검토 컨텍스트만 보낸다. 프로젝트/원장 전체, 동의·서명키·storage_hash·local_path 등 보호 필드가 inputs 안에 들어오면 거절. 경험의 원 프로젝트/원문/저널 전체는 `experience_context()`에서 제외한다. 키는 요청 인증 헤더에만 사용하고 본문/URL/프로젝트 응답에서 배제한다. 테스트에서 실제 요청을 검사했다.
- 자유 입력 텍스트에 사람이 적은 민감정보를 완전히 판별하는 DLP는 미구현이다. 명시적 허용 필드에 자유 텍스트가 있으므로 실제 호출 전 전송 내용을 검토해야 한다. 원장과 로컬 자산을 자동 수집하는 기능은 없다.

## 모의 네트워크에서 실제 저장된 사례

외부 모델 대신 작성된 테스트 응답을 native Gemini envelope로 반환했다. 저장소는 실제 provider 클래스를 사용하지만 응답 내용은 **offline fixture**이다.

- 모의 native 요청16개: 계획1, writer 작성·검토·수정·재검토4, editor4, voice2, QA2, feedback2, 통합1. 대본2버전/샷2버전/음성·QA·피드백 각1버전. 모든 요청은 전송 전에 reserved 상태·해시가 디스크에 존재하고 검증 후 validated가 된다.
- 대본20초 인사→3초 질문형 도입. 샷20초×3/6초 동일 소스→6초×10/서로 다른 계획 ID. 수정 지시와 이전 버전이 실제 후속 요청에서 확인됐다. 수치 검사는 반복 초과/ID 중복을 검출하며 의미·흥미 평가는 별도 모델 주장이다. 기존 테스트 fixture를 재사용한 예이며 실제 모델이 만든 개선이 아니다.
- QA 요청은 선행 content/hash 및 application 측 `plan_evidence`를 읽고 hook에 대한 텍스트 주장과 voice=`unassessed`를 반환. 실제 영상/음성은 제공하지 않았다.10점 체크리스트 총점=null, 실제 음성·영상 감각 점수 없음. 과거 사용자2~3/10이7/10으로 올랐다는 결론 없음.
- feedback 작업은 원문 중 “친근한 말투가 좋겠다”를 근거로 대상 한정 구조화를 반환. 필드/신뢰도/프로젝트·대상/원문 인용을 검증. 모델의 verified 주장·대상 확장·원문에 없는 근거를 거절. 관리자가 수락한 결과만 receipt로 기록하고 source=`provider_model_claim`, verification=`hypothesis` 유지.
- 같은 domain/target_segment에서 ID/hash를 선택하고 다른 대상은 제외. 중복 수신 차단, 철회 후 미선택 확인. 새 결과로 교체하는 replaces/version 이력 경계 제공. 의미 기반 유사도 검색이나 독립적인 경험 검증은 미구현이다.
- 마지막 상태 external_clip_pending; 최종 MP4/게시 완료가 아니다. 기존 사용자 영상은 재렌더하지 않았으며 새 TTS 추론/다운로드 없음.

## 검증 결과

전체 기능 묶음 통합1회:
`env -u AI_CLIP_ACCEPTANCE_ROOT PYTHONPATH=core:companies/video PROVIDER_SAMPLE_OUTPUT=/tmp/manager_staff_provider_20261110/sample.json python -B -m unittest discover -s tests -v`

37개 발견,35통과/1실패/1skip(19.014초). 기존 실행30개 모두 통과. 선택적 실제 MeloTTS/60초 렌더 인수1개는 skip. 실패는 새 테스트의 고정 모의 시계가 pacing 시간에 도달하지 않아 `clock_or_throttle_stalled`로 정지한 fixture 오류였다. 제품의 간격 검사를 완화하지 않고 테스트 시계가 진행하도록 수정했다.

수정 후 새6개만 재검증:
`PYTHONPATH=core:companies/video PROVIDER_SAMPLE_OUTPUT=/tmp/manager_staff_provider_20261110/sample.json python -B -m unittest tests.test_quality_provider -v`

6개 모두 통과(1.902초). 최종 고유37개 기준36통과/1skip. 전체 회귀/미디어 렌더를 반복하지 않았다. 추가 진단도 새 임시 저장소의 모의 HTTP만 사용했다. `git diff --check` 통과.

검증한 차단: 키·환경·서명만으로 기본 전송 비활성, 동의/무료 계정 확인 누락, 취소된 승인, 품질 입력 변경, 다른 저장소 모드, 무제한·과대 호출 예산, 유한 cap 소진, timeout/중단 후 자동 재전송, 잘못된 schema, nonzero cost, 피드백 범위·근거 위조, 미청취 감각 합격. 기존 서명/모의 Gemini 인수 회귀도 통과. 실제 과거 인수 저장소는 읽거나 재사용하지 않았다(파일 보존 해시 읽기 제외).

## 남은 필수 게이트와 최소 실제 호출 승인 범위

이번 작업으로 실제 호출을 승인하거나 계정 무과금을 확인하지 않았다. 기존 inherited free-tier 확인은 사용자 진술 기반이고 독립적인 현재 계정/키/결제 검증의 대안이 아니다. 기존 일반 전송/인수 정책은 변경하지 않았다.

가장 작은 후속 실제 인수 제안은 **새 저장소·새 가상 목표의 관리자 plan1회, max_calls=1, 실패/중단 포함1회 소모, 자동 재시도/모델 대체/직원 호출/영상 생성/게시 없음, 최대 추가 비용0원 정책**이다. 실제 실시 전 다음을 별도로 완료해야 한다.

1. 사용자가 provider/model/endpoint, 정확한 전송 목표·품질 입력·사용자 피드백 포함 여부, Google 데이터 이용 정책과1회 호출 범위를 명시적으로 승인.
2. 현재 사용하려는 키와 프로젝트의 연결, Free 등급/잔여쿼터/Billing 비활성·유료 전환 없음·현재 모델 가격/정책을 확인하고 키 자체는 비표시 로컬로 취급. 기존 단일 인수 키 확인/동의/1회 원장은 재사용하지 않음.
3. 새 경계에 요청·현재 키/계정 증거·유효기간을 묶는 좁은 실제 호출 활성화 절차를 별도로 구현·검토. 현재 상수만 켜거나 환경변수 설정으로 이 절차를 대체하지 않음.
4. 모호한 응답·timeout은 보존 후 종료. 후속 직원/수정 대본 검증은 이1회 범위에 포함되지 않으며 추가 범위 승인이 필요.

현재 코드의 세션 전체 호출 한도는 signed finite cap이나, provider 교체·독립 계정 검증·실제 호출용 좁은 활성화·실모델 대본 품질 평가는 미완료다. 최종3편 운영 전환 시험도 미수행이며 운영 게이트 통과 선언 없음.

## Git 및 자산 보존

시작 기준은 최신 main `fb22f3f`. 구현·테스트·사용법 커밋은 `b2ae9d0` (`Prepare isolated provider boundary for manager and staff quality workflow`). 본 보고서는 별도 결과 커밋으로 함께 main에 반영한다. 원격 최종 SHA 일치 여부는 최종 응답에 기록한다.

코드·테스트는 새 임시 저장소에서만 쓰기를 수행했다. 기존 Gemini 인수 호출·서명·동의·비용·시도 원장, 입력 Flow 클립·기존 영상·MeloTTS 모델/샘플, backups/별도 아카이브를 재개·초기화·수정하지 않았다. 기존 미추적 영상 로그/JSON7개는 커밋하지 않는다. 외부 AI0회, 추가 비용0원, 사용자 영상 재렌더0회, 새 TTS/모델 다운로드0회, 외부 업로드/게시0회. 기존 미디어 회귀의 짧은 로컬 코덱 fixture 검증만 실행했다.

보존 검증: `data/`, `backups/`, `artifacts/`, `.env` 중 존재하는 일반 파일45,349개의 SHA-256과 파일 목록을 개발 전후 대조해 전부 일치(추가/변경/삭제0) 확인. 로컬 근거: `/tmp/manager_staff_provider_20261110/before.json`, `preservation.json`. 민감 자료/해시 원장은 Git에 추가하지 않는다. 저장소 밖 별도 아카이브는 접근하지 않았다.
