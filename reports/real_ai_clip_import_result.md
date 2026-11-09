# 실제 AI 클립 수입 결과

- 상태: 완료. 실행: 2026-11-09T15:54:24+09:00 KST. 기준 commit: a7838823e84f80a24ac1638577cc60ab4246bcee.
- 최소 코드 수정: 혼합 소스의 ai_generated_clip_used/1+2 개수/혼합 시안 표시와 상태를 정확히 기록. 실제 생성 시각이 없는 입력은 generated_at=null 허용(수입 시각은 KST로 별도 기록). 관련 회귀 1개 추가. 기존 API/동의/비용 계약 변경 없음.
- 코드/테스트 수정은 로컬 작업 트리에 보존했으며 이번 지시에는 commit/push 요청이 없어 원격 반영하지 않음.
- 실제 입력: /workspaces/ai-company-os/data/video_ai_clip_inbox/Adult_beginner_using_laptop_356cf95b.mp4, 1,957,838 bytes, SHA-256 157b931157071563aa4eb87d5cc11047a1bbebb1fa05da98a09fdc1ec2aa35ad.
- 출처: 사용자 진술상 Google Flow. 독립적인 생성 서비스 인증·라이선스·워터마크·상업 이용 증빙 없음. 실제 생성 시각/원본 생성 비용도 미확인.
- 신규 job: /workspaces/ai-company-os/data/video_ai_clip_review/20261109T155436_KST/shorts.
- 출력 영상: /workspaces/ai-company-os/data/video_ai_clip_review/20261109T155436_KST/shorts/preview.mp4 (2,624,420 bytes).
- ffprobe/전체 FFmpeg decode: 통과. 720×1280, 60.000000초, 9:16, SAR1:1, H.264 24fps, AAC 44.1kHz 모노.
- MeloTTS 원본 음성6개를 텍스트·해시 확인 후 새 job에 복사하여 재사용. 새 TTS 추론 없음. 한글 자막 14개(ASS/SRT), 발화 경계 실측·구절 내부 정렬 추정.
- 사용자 제공 실제 AI 출처 클립 1개 + 비AI fixture 2개. mixed_source=true, ai_generated_clip_used=true, publish_ready=false. 전체 AI 영상이나 게시용 완성본이 아님.
- 3개 장면의 원본 해시·출처/권리·워터마크·반복 횟수는 job.json/receipt.json/timeline.json에 저장. 워터마크 미확인 상태에서 crop 없이 letterbox로 원본 보존.
- 기술적 재생/전체 디코딩 검증만 완료. 전체 연속 시청·음성 청취 및 사용자 품질 합격은 미판정. Codespaces에서 preview.mp4를 Download하여 재생 가능.
- 최종 통합 검증: unittest 25개, 실패 0, 오류 0, 선택적 새 TTS/fixture 인수 테스트 skip 1개. 실제 혼합 영상은 별도 같은 검증 묶음에서 1회 렌더. 상세: reports/real_ai_clip_import_integration.log.
- 보존: 기존 원장·인수 초안·TTS 샘플·기준선·이전 60초 job·입력 클립 98개 파일 전후 해시 일치=True. 원본 파일 수정/삭제·기존 작업 재실행 없음.
- 이번 새 Gemini/영상 AI API 호출 0회, 유료 결제/추가 비용/자동 업로드 0회. 기존 Gemini completed 1/1 유지. 원본 클립을 과거에 생성한 비용은 확인하지 못했으며 이번 로컬 편집 비용과 구분.
- 한계/남은 일: scene-2/3 실제 클립과 권리/워터마크/상업 이용 근거를 받기 전 게시 불가. 사용자 최종 시청·청취 후 다음 수정을 결정.
