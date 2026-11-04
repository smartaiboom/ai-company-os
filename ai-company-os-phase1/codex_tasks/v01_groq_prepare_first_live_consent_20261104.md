# AI Company OS — Groq 실제 무료 운영을 위한 최초 동의안 준비

작성일: 2026-11-04 KST
이번 작업 범위: **신규 Groq 프로젝트의 최신 운영 제안 prepare 및 검증까지. 실제 API 송신, approve, run 금지.**

## 확정된 사용자 확인 정보
사용자는 자신의 Groq Console 화면을 직접 확인하여 대화로 공유했다.
- Billing → Plans: **Free $0 / Current Plan** 표시. Developer와 Enterprise는 현재 플랜이 아님. 요금 발생 서비스를 이용하거나 유료 플랜으로 업그레이드하도록 승인한 적 없음.
- Organization Limits → Chat Completions: **openai/gpt-oss-20b** 모델이 현재 조직의 무료 모델 한도 표에 표시되어 있음. RPM=30, RPD=1,000, TPM=8,000, TPD=200,000. 실제 실행 시 프로젝트별 제한·잔여치·정책은 더 엄격할 수 있으며 이 수치가 보장된 예산은 아님.
- GitHub Codespaces에서 **GROQ_API_KEY 등록 성공** 출력 확인. 기존 OpenRouter AI_API_KEY도 계속 존재.
- 이 스크린샷은 **Free 플랜이 현재 활성 상태임을 뒷받침**하며 별도의 결제수단 보유 여부까지 단정하지 않는다. **유료 Developer 업그레이드/과금 활성화를 금지**하고 FREE tier만 대상으로 한다.

이 정보는 사용자가 신규 **계정 확인에 근거한 동의안 준비**를 요청했다는 의미다. 외부 Groq 송신과 실제 AI 운영에 대한 명시적 최초 동의는 아직 받지 않았다. `--confirm-groq-free-account`는 제공된 사용자 확인과 Console의 Current Plan=Free 및 유료 플랜 미활성에 근거한 계정 확인 선언에만 사용하고, 결제수단 부재를 추가 증명했다고 주장하지 않는다. 현행 계약이 보다 강한 별도 결제조건 확인을 요구한다면 **그 조건을 완화하거나 허위 확인하지 말고**, 준비를 중단해 정확히 부족한 항목만 보고한다.

## 시작 전 필독
- `AI_COMPANY_OS_CORE_PRINCIPLES.md` (자율 AI 회사 목표, 다중 무료 공급자 및 유료 별도 승인)
- `AGENTS.md`, `codex_tasks/README_KOREAN_LANGUAGE_RULE.md`
- `reports/v01_provider_agnostic_groq_free_integration_20261104.md`
- `reports/v01_groq_live_readiness_check_20261104.md`
- `autonomous_live_cli.py`, `autonomous_groq.py`, `groq_provider.py`, 운영 계약·키 확인·원장 관련 코드.

## 대상 신규 프로젝트 (기존 동일 프로젝트만 사용)
- Store: `data/groq-video-smoke-20261104`
- ID: `groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e`
- 보고서 기준 목표 hash: `3cf69cc191d65718ef1571671a3f85940676d3c8da7992f7d1760eec45bbb5c9`
- 보고서 기준 상태 hash: `25d3e5d7c3666acac578d278aab63f00848716f904a4cb1dbe7f22dcc495db5f`
- 공급자: Groq 고정, 모델 `openai/gpt-oss-20b`, endpoint `https://api.groq.com/openai/v1/chat/completions` 고정.
- 목표: ChatGPT 초보자에게 좋은 질문하는 방법을 알려주는 **한국어 20~30초 MP4**, 한국어 자막, 가능하면 로컬 음성 포함, 검증된 최종 파일과 제작 보고서.

## 수행 절차
1. `git pull --ff-only`로 최신 문서 확인. store marker/namespace/provider/project ID와 정확한 목표·초기 상태, ready/plan/attempted=0, 기존 운영 grant 미발급, active_operation 없음, 기존 draft 유효성을 검증. 실제 프로젝트가 이미 진행됐거나 계약/키/모델/상태가 예상과 다르면 **재생성/덮어쓰기/재승인하지 말고 멈춤**.
2. `GROQ_API_KEY` **존재 여부만** 확인. 키 값/길이/접두어/해시를 사람이 볼 수 있는 보고서/로그에 남기지 않는다. 내부 승인 계약의 키 결합 hash 처리는 설계대로 유지하되 외부 공개 금지. `AI_API_KEY`나 `.env` 설정을 변경하지 않는다.
3. Free 플랜/유료 플랜 미활성에 대한 사용자 제공 화면 증거와 Groq 20B 이용 한도를 근거로 계정 확인 단계를 진행하되, 최신 계약이 요구하는 조건을 충족하는지 확인한다. **유료 과금이 불가능하도록 현행 Free 정책과 공급자/모델/호출 제한 보호를 유지**한다. Groq 실제 외부 요청으로 플랜을 조회하지 않는다.
4. 동일 프로젝트의 **최신 최초 운영 제안**을 정상 CLI prepare로만 생성한다. 기존 `operating-proposal.json`은 원본 보존; 새 제안은 충돌하지 않는 별도 경로에 생성. 예:
   ```bash
   python -B -m autonomous_live_cli --store data/groq-video-smoke-20261104 prepare groqcompany-643c3fd8bd7d4aebb66cd881f54b9d0e --confirm-groq-free-account --proposal-out /tmp/groq-account-reviewed-proposal-20261104.json
   ```
   대상 경로에 이미 파일이 있으면 안전한 새로운 이름 사용. 계정 확인 정책이 불충분하면 위 flag를 실행하지 않고 그 사유를 보고할 것.
5. 로컬 검증: 새 proposal의 canonical review hash, 현재 state hash/goal hash, provider/model/URL/비용 조건/동의 범위/allowlisted local FFmpeg TTS/expiration KST, 최초 실행 최대 30분과 bounded 업무·수정·비정상 중단 보호 확인. 외부 전송 허용 예정 내용: **오직 신규 프로젝트 목표와 새로 생성되는 관리자 계획·성공 기준·직원 할당·대본·자막·장면·직원 결과·관리자 리뷰·수정·최종 통합 텍스트 및 로컬 렌더 메타데이터**. 기존 문서/코드/음성·영상 원본/API 키/계정 개인정보 전송 금지.
6. 비용/쿼터: 새 제안은 Groq Free 플랜 및 20B 고정, 유료 모델/유료 fallback/결제 업그레이드 금지; 30 RPM/1000 RPD/8000 TPM/200K TPD는 조직 화면상의 상한이며 provider 응답·프로젝트별 현재 제한 우선. 429/402/계약 불일치/비용 불확실/미확정 송신 정지와 중복 안전성 보존. 중간 업무 승인 요구 금지.
7. **중요: 이번 작업은 반드시 prepare까지만**. `approve --owner-confirmed`, `run`, `continue`, 실제 공급자 API 호출, 실제 운영 서명 키 생성, 외부 전송, 테스트 ping 등은 일절 실행하지 않는다. fake 테스트가 필요하면 네트워크 차단된 격리 fixture만 사용.
8. 기존 OpenRouter 실패 프로젝트 `freecompany-ae4aa334511d470c8c517685e9902a53`와 수동 프로젝트 `cb44b605b498`, `c85d9853906a`, 기존 데이터·백업·영상·사용자 미추적 파일 보존. Git reset/clean/force push 없음. KST 준수.
9. 결과 보고서 `reports/v01_groq_first_live_consent_prepared_20261104.md` 작성 후 Git에 **보고서만**(필요시 안전한 최소 코드/테스트 변경 포함) 선택적 커밋·푸시. 반드시 아래를 보고:
   - 신규 제안 prepare 성공/차단 근거와 사용자 확인 증거 범위
   - 실제 project ID 및 goal/state hash, canonical review hash, 새 제안 로컬 경로, KST 만료
   - 실제 승인 대상 공급자·모델·전송 텍스트·로컬 도구 범위·비용/무료 정책
   - 무승인·API 실제 호출 0회·원본 데이터 변경 없음
   - **이 다음 사용자 명시 승인 후에만** 실시할 정확한 한 번의 approve + 한 번의 run 절차 (이 단계에서는 실행 금지).

## 완료 판정
실제 Groq 호출을 하지 않고 **승인 검토 가능한 새 운영 제안이 생성**되거나, 부족한 계정 증빙을 명확히 식별·보고해야 한다. 현재 프로젝트나 기존 실패 원장을 임의로 건드리면 실패. **fake MP4 결과나 계정 화면은 실제 Groq 자율 실행 성공이 아니다.**
