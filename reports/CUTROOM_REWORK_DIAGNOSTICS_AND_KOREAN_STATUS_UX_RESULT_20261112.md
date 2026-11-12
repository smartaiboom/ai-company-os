# 컷룸 재작업 진단·한국어 진행 현황 개선

2026-11-12 KST, 최신 main `4358949`·AGENTS.md·지정 지침 확인. **실제 원장은 읽기만 했고 UI/조회 투영만 개선했다. 추가 API0회·재실행0회.**

- 실제 job `qualityprovider-3cb52d1ab205460897e9f03fea21ca71`: stopped/invalid_dependencies, phase=plan, plan/rework_plan=null, 직원 산출물 없음. 관리자 시도1건은 **HTTP200/completed, role_result_status=json_parsed(서버 validated 아님)**. 16:06:16 전송 시작, 16:06:22 응답/중단 KST. response SHA `66097f98e78e1adcc770cc26d12faf1501ffda018e90202ed793dd7f1b44df3c`, JSON 파싱 완료, 6797bytes, 토큰9743/1549/11292. sessions1·active_operation=동일 시도ID 보존. 즉 이번은 환경 차단/전송0이 아니므로 기존 disabled 복구 대상이 아니다.
- 원인 범위: core validate_plan의 depends_on/criteria_ids 참조 검사에서 거부됐다. 선행 업무 ID/등록된 평가 기준 ID/중복 금지 중 어떤 항목이 틀렸는지는 **응답 전문·후보 plan이 원장에 보존되지 않아 확정할 수 없다**. 파싱/응답 hash만으로 원문을 복원했다고 주장하지 않는다. 원장/응답 자동 보정·재시도·새 job/grant 없음.
- UI: representative_rework.py의 읽기 전용 progress_view가 동의→재기획→대본→검토→스토리보드→검토→새 대표 승인 대기의 단계/담당/완료·진행·중단과 KST 갱신 시각을 실제 events/assignments/attempts에서 도출한다. studio_server.py가 이를 조회 응답에 제공하고 studio.js가 한국어 카드로 표시한다. 현재는 **재기획 · AI 관리자 · 재작업 중단/새 결과 미완료**. 부정확한 진행률은 표시하지 않는다.
- invalid_dependencies는 업무 순서·참조 관계 검증에서 중단/새 대본 미생성/담당 개발 점검 필요로 설명한다. 설정 비활성·동의 만료·서비스/한도·전송 불명·품질 오류도 한국어 안내한다. 원 오류 코드는 접힌 기술 진단에만 표시한다. 요청 시도1/전송 시작1/HTTP 정상1/서버 검증0/전송 실패0을 구별하고 quota·청구 미확인을 유지한다. 중단 업무 실행 버튼 없음, 새로고침은 조회만 한다. 이전 mission needs_user_review은 '이전 미션 기획 보존 · 참고용(최신 재작업 아님)'으로 접어 구분한다.
- 표적 테스트1개 통과(0.053초): `PYTHONPATH=core:companies/video python -B -m unittest tests.test_rework_status`. stopped invalid_dependencies/attempt1·running/검토·completed 상태 투영, 원본 불변, Node VM 한국어 렌더/실행·재개 버튼 비노출/오류 상세 격리를 확인했다. DNS/socket 차단. node --check 및 git diff --check 통과, 전체 suite 미실행·브라우저 시각 검사 미수행. 실제 조회에서도 위 단계/시각/호출 수를 확인했다.

기존 원장·동의/lock·컷룸4개 SHA 전후 동일. 기수락 미션 v1·과거 대본/스토리보드/서명·음성/영상·data/backups/artifacts/.env·미추적 파일 보존. Gemini 기존21+이번 사용자 실전1=누적22(과거 불명 포함), 이번 Codex 추가0. YouTube search2/videos2 변화 없음. 동의에 묶인 모델 지시/검증 규칙도 이번에는 바꾸지 않았다.

**대표의 다음 행동:** 컷룸의 '담당 개발 점검 필요' 안내에 따라 다음 실행 전 기획 계약의 선행 업무·평가 기준 참조 규칙 보완을 요청한다. 현재 실패 업무는 다시 시작하지 않는다. 보완 시 새 승인 범위를 검토해야 하며 이번에는 실행하지 않았다. 소스3개·표적 테스트1개·이 보고서 main commit/push/readback 후 중단한다.
