# 컷룸 실제 재작업 시작 실패 — 재작업 동의서 크기 상한만 정확하게 수정
2026-11-12 KST

## 확정 관측
미션01 동일 컷룸에서 'AI 재작업 동의 준비'와 '새 외부 전송 동의'는 성공하고, 'AI 재작업 시작'에서 HTTP 응답 `operating_consent_required` 발생. 사용자 로컬 관측:
- 재작업 신규 동의서 `qualityprovider-3cb52d1ab205460897e9f03fea21ca71.consent.json`
- 파일 크기 **28,841 bytes**, 기존 `LiveStore.grant`의 **16,384 byte** 상한 초과.
- 경로: `core/autonomous_live.py`의 `LiveStore.grant` 시작 조건 `path.stat().st_size<16384`; `companies/video/studio_server.py`의 `rework-run`이 `provider.grant(job)`를 실행하므로 호출 전 차단. 실패 시 `state['status']='approved'`인 것으로 예상(실제 상태 확인 필수). 이전 승인서 생성 후 아직 실제 Gemini 호출 없음(코드상 사전 검사 실패); 수동 수정·새 grant 발급 불필요.
- 등록 모델 `gemini-3.5-flash-lite`, endpoint 정확하고 API 키 등록 확인됨. 이미 정상 발급한 새 동의와 서명, 과거 원장/대표 피드백 보존 필수.

## 이번 수정 범위
1. **재작업 동의서에 한해서만** 정상적 예상 크기(최소 28,841 bytes) 허용. 합리적 엄격 상한 예: 64KiB, 단 실제 계약 데이터가 그 이상 필요한지 근거 확인. 일반 `LiveStore` 기존 16KiB 제한은 유지, 다른 작업의 계약 무제한 확장 금지. 가능한 간단한 구조: `LiveStore`에 안전한 클래스별 `max_consent_bytes=16384` 상수/속성 정의 후 `grant`에서 참조하고, `ReworkStore`에서만 이를 `65536`으로 제한적으로 오버라이드. 단, 기존 `MissionOneStore` 등 다른 store에 영향 없이 정확한 타입/상속 구조 검증. **파일 크기 상한은 검증 전 처리량 보호일 뿐이며 서명(HMAC), 만료, 계정/동의 범위, 바인딩, 상태, hash 검증 전부 그대로 유지**.
2. 이미 존재하는 동의서 **파일 자체, 서명키, approval·grant, 재작업 job과 프로젝트 상태를 읽기/검증만 하며 절대 수정하거나 재승인 받지 않기**. 동일 'AI 재작업 시작' 경로에서 정상적 28,841B 동의서 통과하도록 함. 기존 API 호출 전 오류 이후 상태가 'approved'임을 확인하며 강제 재승인/실행 요구 금지.
3. 작은 **오프라인 회귀 테스트**: 승인된 재작업 계약 >16KiB, <64KiB에서 grant 정상 검증; 변조/서명 무효, 크기 상한 초과(>=64KiB) 차단; 일반 LiveStore의 기존 <16KiB 제한 유지. 가능한 실제 기존 실패 경로 재현 및 `rework-run` 승인 → running 전이 검증 **외부 Gemini/YouTube API 전송 0회**, key 출력 0회. 기존 테스트 재활용. 테스트 데이터는 임시 디렉터리/fixture만; 실제 사용자 데이터/키를 읽거나 고치지 말 것. 프로덕션 서버에 대한 새로운 실행 시도 금지.
4. Python 핵심 검사와 `git diff --check`만 수행. 이번은 **버그 하나만** 고치고 재작업 워크플로/모델/프롬프트/예산/큐를 바꾸지 말 것. 수정 커밋 push.
5. 짧은 `reports/REWORK_CONSENT_SIZE_LIMIT_FIX_RESULT_20261112.md`에 수정한 파일, 검증 결과, 기존 동의서 자동 유효 여부(코드상 확인만; 실제 로컬 파일 미열람이면 미검증 명시), API 호출 0회, 사용자 다음 동작(서버 재시작 후 컷룸에서 기존 'AI 재작업 시작' **한 번만**; 새 동의 불필요)을 기록하고 종료.

### 주의
사용자는 기존 재작업 동의까지 마쳤고 'AI 재작업 시작' 오류 1회 뒤 **다시 누르지 않고 대기 중**. 소유자의 기존 동의 범위를 확대하거나 무료 정책/실전 호출 승인을 새로 생성하지 않는다. 무료/비용 실청구는 독립 확인 불가로 유지. 기존 작업 데이터 `data/`, `backups/`, `artifacts/`, `.env`, 과거 승인·실패 이력 보존, git clean/reset --hard/force push 금지. KST 유지. 더 큰 구조 변경/전체 suite 반복/장문의 보고서 금지.