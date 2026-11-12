# 재작업 기획 계약 강화 결과

2026-11-12 KST, 최신 main `dc30a1a`·AGENTS.md·지정 지침 기준. **rework 경로만 기획 계약·관계 검증을 강화하고 오프라인 v2 인수를 확인했다. 실제 API0회.**

- `representative_rework.py`: PLAN_RULES 한곳에 정확히 writer→editor 2개 업무, writer 의존성 없음/editor는 writer ID만 참조, 고유 ID·존재하는 중복 없는 criteria_ids·모든 기준 사용·원 목표/대표 피드백/길이 근거를 명시. 실제 systemInstruction에 전달하고 native plan schema tasks도 min/maxItems=2로 제한한다. ID/내용은 모델이 생성하며 응답 자동 보정은 없다. 공통 core validator/다른 미션은 변경하지 않았다.
- 관계 검증 실패 시 미래 원장의 attempt에 업무 index/field/detail/응답 hash를 기록한다. replan의 비어 있지 않은 주제·길이/피드백 반영 사유와4~180초 범위도 검사한다. 기존 게임 소재 적합성/원문 근거·형식 품질 검토는 유지한다. 과거 실패의 구체적인 잘못된 참조를 복원했다고 주장하지 않는다.
- 강화된 계획 계약 hash를 **새 proposal의 서명 범위**에 넣는다. 역사 grant 검증은 유지하되 강화 계약의 실제 전송은 새 hash 동의가 있어야 한다. 기존 stopped job/no-restart 가드 불변. **최대1회 교정 호출은 미구현**: 이번에는 명시 계약·엄격 검증·원인 기록까지만 적용했으며 호출/회계/자동 retry를 확장하지 않았다.
- 표적 종단 테스트1개 통과(7.672초): `tests.test_video_mission_one.MissionOneTests.test_strict_rework_plan_contract_to_script_offline`. 잘못된 선행/편집 의존성·존재하지 않는/중복 criteria_ids 거부와 구체 사유·입력 불변, 실제 payload 규칙/2개 업무 스키마·새 서명 hash 확인 → 유효 manager 재기획→writer→manager→editor→manager→같은 임시 컷룸 v2 승인 대기. 기존 v1/실패 원장·서명 보존과 중복/503 차단도 기존 fixture로 확인했다. replan 공백/범위 검사 보완 후 동일 표적만 재실행했고 전체 suite는 하지 않았다. DNS/socket 차단 합성 모델이며 실제 새 대본 성과가 아니다. git diff --check 통과.

실제 `qualityprovider-3cb52d1ab205460897e9f03fea21ca71`의 invalid_dependencies/HTTP200 시도1 및 컷룸 plan_revision 그대로. 실제 원장·동의/lock·컷룸4개 SHA는 기존 보존 기준과 동일. 신규 job/grant/consent/실제 전송0, Gemini 누적22(과거 불명 포함)·YouTube search2/videos2 불변. data/backups/artifacts/.env·과거 제작/음성·미추적 파일 삭제/초기화 없음.

**남은 차단/대표 다음 단계:** 실패 업무에 재실행 버튼을 열지 않았다. 현재 UI에는 이 실패 이후의 새 수정판 job/동의 준비 연결이 아직 없다. 강화 계약의 독립 신규 업무를 준비하는 최소 연결을 별도 범위에서 마련한 뒤, 대표가 새 전송 범위를 확인·승인·시작해야 실제 대본을 받을 수 있다. 이전 grant/실패 요청은 재사용하지 않는다. 이번은 실전 실행 완료가 아닌 계약 강화/오프라인 검증 완료다. 소스1개·표적 테스트1개·이 보고서 main commit/push/readback 후 종료한다.
