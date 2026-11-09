# 실제 AI 클립 코드 동기화 결과

- 완료: 2026-11-09T16:05:59+09:00 KST.
- 코드 commit: 5316775375ac9ec022d579dc1da22f39bbbd0cdc. origin/main 푸시 성공 및 원격 SHA 일치 확인.
- 변경 파일: companies/video/ai_clip_pipeline.py, tests/test_ai_clip_pipeline.py. 이미 검증된 로컬 수정만 반영했고 추가 기능 변경 없음.
- 내용: 혼합 시안에서 사용자 제공 AI 클립과 fixture 개수/표시/상태를 구분. generated_at=null은 미확인 생성 시각만 의미하며, 값이 있으면 기존 KST 검증 유지. 출처·권리 필드와 publish_ready 조건·기존 동의/비용 계약은 유지.
- 기존 검증 근거: reports/real_ai_clip_import_integration.log — 25개 중 실제 실행 24개 통과, 선택적 새 TTS/fixture 테스트 1개 skip, 실패/오류0. 앞선 실제 혼합 영상은 ffprobe/전체 디코딩도 통과. 추가 코드 변경이 없으므로 테스트/렌더/추론을 반복하지 않음.
- 보존: 동기화 전후 코드 원문 및 보호 대상 데이터 68개 파일 해시 일치. 입력 MP4, 기존/신규 60초 영상, 인수 초안·승인·호출 원장 불변. backups/별도 아카이브 미접근. 데이터/영상/모델/런타임/키/원시 로그 업로드 없음.
- 권리: Google Flow 출처는 사용자 진술이며 상업 이용/워터마크/라이선스 확인 근거 없음. 실제 혼합 시안의 publish_ready=false 유지.
- 이번 새 외부 AI API 호출0, 유료 비용0원, 영상 생성·재생성·자동 업로드0. 기존 Gemini completed 1/1 유지.
- 다음: 사용자의 혼합 영상 평가를 먼저 받고, 이후 scene-2/3 클립의 무료 생성·수입 및 권리/비용 근거 확보. 이번에는 품질 개선·새 API 연결을 하지 않음.
- 이 결과 파일은 별도 보고서 커밋으로 main에 반영한다. 원본 수입 보고서와 원시 실행 로그는 변경하지 않았다.
