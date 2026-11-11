# 미션 01 — 내부 호출 예산 2배 증액 및 실전 대본 재개 준비
작성일: 2026-11-12 KST

## 사용자 승인과 해석
대표가 명시적으로 지시했다. "10회 한도는 임의로 정한 거잖아? 저거 넘는다고 유료로 전환되는 것도 아니고. 한도를 다 두 배로 높여."
- 기존 프로젝트 내부 한도 Gemini 10 → **총20 요청 시도**, YouTube search.list 4 → **총8**, videos.list 4 → **총8**.
- 기존 실제 소모 Gemini **7**, YouTube search **2**, videos **2**는 보존한다. 증액 후 잔여는 각각 **13, 6, 6**. 실패/시간초과/불명 요청도 시도 횟수에 포함.
- 이는 **현재 미션 01의 호출 예산 증액 승인**이며 기존 실패한 호출 재실행, 실제 새 provider 전송, 유료 전환, 모델/계정 교체, 게시 승인이나 Google 무료 quota 확인을 뜻하지 않는다. 내부 승인 수량 ≠ 공급자 실제 무료 quota. 새 독립 분리 업무의 실제 전송은 별도 명시적 실행 승인 및 새 proposal/grant가 필요하다.
- 이전 10/4/4 서명/동의/실제 소모 기록은 과거 사실로 보존. **기존 서명된 승인/원장/attempt를 직접 편집하여 20/8/8로 바꾸지 않는다.**

## 기존 실전 상태
- `AGENTS.md`, `reports/VIDEO_MISSION_01_APPROVED_WRITER_RESUME_REAL_RUN_RESULT_20261112.md`, `reports/VIDEO_MISSION_01_WRITER_PROVENANCE_CONTRACT_FIX_RESULT_20261112.md`, `reports/VIDEO_MISSION_01_WRITER_STAGE_RESUME_PREPARATION_RESULT_20261112.md` 확인.
- 컷룸 ID `company-aba553f29cfb454c8c05bad4abb49969`; phase `research_planning`.
- stopped 4개: 최초 DNS `qualityprovider-504d90900918450f98dd62b6f7704f1b`; 연구 검토 실패 `qualityprovider-299a51b38e6d4d50b651b9fbb39dabad`; 대본 audience 실패 `qualityprovider-4cbe762cbf554e40af5e7d990ceaf46b`; 가장 최근 대본 provenance 실패 `qualityprovider-bb394ad486014277998d8a64b62e8199`. 각 서명·동의·소모·attempt·active_operation 불변.
- 기존 원 조사 10개 YouTube 메타데이터 관측과 AI 관리자 선정(롤토체스 및 모바일 퍼즐류, 25초; evidence `q0:TAidk7sXHk4`, `q0:0FVBz6iWhOY`, `q1:9YjDIwCAnsw`)을 유지. 원 조사/선정 자료는 입증된 출처/유효기간·SHA 재검증을 통과하는 경우에만 재사용. 미검증 대본은 복원하거나 성공으로 승격하지 않는다.
- 마지막 provenance 수정 `quality_workflow.py` systemInstruction에 실제 모델/mock 정보 명시, 실전 재확인은 아직 못함.

## 이번 Codex 업무: 예산 증액을 실제 제품의 안전한 새 승인 경로에 반영
1. 현재 예산 검증이 미션 01 경로에 고정 `MAX_CALLS=10`, 원 체인 사용6+신규4, YouTube 4 또는 신규2 등으로 박혀 있다. 기존 코드/CLI 및 grant 예산 검증만 필요한 범위에서 살펴본다. **모든 제품/기존 프로젝트의 정책을 전역 20/8/8로 변경하지 말 것**. 미션 01의 **향후 새 독립 업무 1개**와 새 사용자 승인 정책 버전/추가 budget grant만 합계 20/8/8을 허용하게 한다.
2. 기존 네 stopped 업무 및 과거 서명 예산은 원본 그대로 유효했던 과거 상태로 남긴다. 기존 resume/successor/writer-resume 가드를 약화·우회하지 말고 네 번째 provenance 중단의 후속 대본 재개에 필요한 **새 적격성 검증 및 별도 새 승인 경로**를 최소 추가한다. 지난 세 차례 체인 인계의 원본 SHA·연결·자료 유효기간/목표·현재 소모7/선정25초 검증을 유지한다.
3. 새 제안에 사용자 승인한 총 한도 `Gemini 20, YouTube search 8, videos 8`, 실제 과거 소모 `7,2,2`, 신규 잔여 `13,6,6`, 고정 `gemini-3.5-flash-lite`, 계정 `gen-lang-client-0938732315`, 동일 기존 Google 무료 데이터 처리 조건을 **명확히 구분해** 기록한다. 사용자가 기존 연구 재사용 경로를 선택했으므로 **새 실전 실행에서 YouTube 추가 조회는 0회**가 원칙이며 잔여 할당량을 중복 조사 근거로 사용하지 않는다.
4. 새 코드가 실제 요청 전 원본 chain·신규 승인/서명·누적 사용량 한도·동의·고정 모델/엔드포인트/계정/키 바인딩·자료 유효기간을 검증하고 실패·불명 요청도 소모하도록 유지한다. 20회를 절대적 무료 할당량이라고 표시 금지, 실제 Google quota/결제 확인하지 않았다면 `unknown/unverified`. 유료 전환/대체 모델/fallback/자동 재시도 금지.
5. 새 예산 승인 단계는 현재 **예산 증액 동의를 문서화하는 준비 및 오프라인 검증**까지만 수행한다. 실제 작업 데이터에 새 후속 업무/서명/승인 이벤트를 생성하거나 외부 provider를 호출하지 말 것. 합성 fixture에서 새 검증 경로에 의해 이미 검증된 조사·관리자 선정/25초를 인계해 대본 작성→검토→편집→검토→동일 임시 컷룸 대표 승인 대기에 도달할 수 있는지와 누적 한도20/8/8 차단, 실패4개 보존, 과거서명 불변을 표적 검증한다. 새 관리자 계획/조사를 불필요하게 재생성하지 말 것.
6. 되도록 코드 변경을 최소화하고 기존 프로젝트별 예산 원장의 재사용 가능성을 살펴보되, 안전한 마이그레이션이 필요하면 무리해서 붙이지 않는다. **핵심 미션 지연 방지**: 이번 범위를 예산 UI나 동의 갱신 시스템 재개발로 확장하지 말 것.
7. 성공·실패·중단 어느 경우에도 `reports/VIDEO_MISSION_01_DOUBLE_CALL_BUDGET_RESULT_20261112.md`로 보고하고 GitHub commit/push 후 중단. 증액된 수치와 실제 사용량, 변경한 경로, test 결과, 실 API 0회/실사용 원장 변경0건, 다음 실전 실행 승인을 위한 요청 1건을 간결히 기록한다.

기존 data/, backups/, artifacts/, .env/비밀 키·음성·영상·미추적 파일 보존. `git clean`, `git reset --hard`, force push, 기존 서명/attempt 소모 변경 금지. KST 유지.
