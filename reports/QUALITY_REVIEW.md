# 품질 검토 자료 — 2026-11-10 KST

**모의 HTTP fixture 산출물. 실제 AI 추론/새 실제 영상 아님.**
실제 사용자가 확인할 중간 결과와 측정 근거를 아래에 보존했다. 이 자료는 현재 구현 범위의 계약 시연이며 게시 합격 자료가 아니다.

## 관리자 계획
초보자에게 AI에 질문하는 한 가지 방법을 실제 입력 예로 설명; 10개 기능 나열은 과밀하여 제외.
모의 전략. 사실/시청/청취·권리는 검증하지 않음. 외부 전송 불허.

### script · writer
초보자 대상 한 메시지: 목적과 조건을 함께 적기. 0~3초 질문 후크→입력 사례→시연→마무리. 총60초.
의존성: 없음

#### 대본 버전1
- 20초: 안녕하세요. 오늘은 인공지능에 대해 알아보겠습니다.
- 20초: 인공지능에는 많은 기능이 있습니다.
- 20초: 여러분도 사용해 보세요.
#### 대본 버전2
- 3초: AI 답이 모호한가요? 목적과 조건을 적으세요.
- 12초: 질문을 구체적으로 적는 한 가지 방법을 보여 드릴게요.
- 15초: 저녁 메뉴를 알려 줘 대신 냉장고에 두부와 달걀이 있어요. 두 사람이 먹을 메뉴 하나를 제안해 줘라고 적어 보세요.
- 15초: 화면에서 두 질문을 비교해 보세요. 실제 답변과 조리 가능성은 직접 확인해야 해요.
- 10초: 목적, 가진 재료, 인원처럼 필요한 조건을 더해 보세요. 개인 정보는 넣지 마세요.
- 5초: 오늘 질문 하나에 조건을 더해 볼까요?
관리자 재작업 지시: [{"issue": "bland_opening", "owner": "writer", "severity": "major", "evidence": "segments[0]의 인사와 주제 소개가20초; 첫3초에 얻을 가치 없음 (fixture 평가)", "correction": "첫3초에 구체적 실패 질문; 목적+조건 입력 사례로 교체", "expected_metric": "후크 구간3초"}]

### shots · editor
인수 대본 문장에 대응하는 60초 샷; 6초 소스10개, 화면녹화 시연 포함. 수동 소스 확보 대기.
의존성: script

#### 샷 버전1
| 계획 소스 | 장면/소스 길이 | 대응 내레이션 | 상태 |
| --- | --- | --- | --- |
| same-clip | 20초/6초 | AI 답이 모호한가요? 목적과 조건을 적으세요. | planned |
| same-clip | 20초/6초 | 저녁 메뉴를 알려 줘 대신 냉장고에 두부와 달걀이 있어요. 두 사람이 먹을 메뉴 하나를 제안해 줘라고 적어 보세요. | planned |
| same-clip | 20초/6초 | 목적, 가진 재료, 인원처럼 필요한 조건을 더해 보세요. 개인 정보는 넣지 마세요. | planned |
#### 샷 버전2
| 계획 소스 | 장면/소스 길이 | 대응 내레이션 | 상태 |
| --- | --- | --- | --- |
| planned-0 | 6초/6초 | AI 답이 모호한가요? 목적과 조건을 적으세요. | planned |
| planned-1 | 6초/6초 | AI 답이 모호한가요? 목적과 조건을 적으세요. | planned |
| planned-2 | 6초/6초 | 질문을 구체적으로 적는 한 가지 방법을 보여 드릴게요. | planned |
| planned-3 | 6초/6초 | 질문을 구체적으로 적는 한 가지 방법을 보여 드릴게요. | planned |
| planned-4 | 6초/6초 | 저녁 메뉴를 알려 줘 대신 냉장고에 두부와 달걀이 있어요. 두 사람이 먹을 메뉴 하나를 제안해 줘라고 적어 보세요. | planned |
| planned-5 | 6초/6초 | 화면에서 두 질문을 비교해 보세요. 실제 답변과 조리 가능성은 직접 확인해야 해요. | planned |
| planned-6 | 6초/6초 | 화면에서 두 질문을 비교해 보세요. 실제 답변과 조리 가능성은 직접 확인해야 해요. | planned |
| planned-7 | 6초/6초 | 목적, 가진 재료, 인원처럼 필요한 조건을 더해 보세요. 개인 정보는 넣지 마세요. | planned |
| planned-8 | 6초/6초 | 목적, 가진 재료, 인원처럼 필요한 조건을 더해 보세요. 개인 정보는 넣지 마세요. | planned |
| planned-9 | 6초/6초 | 오늘 질문 하나에 조건을 더해 볼까요? | planned |
수치 검사: 최초 길이 초과3건+중복 ID1건 → 수정 계획0건. 소스 미확보이므로 실제 화면 다양성은 미평가.
관리자 재작업 지시: [{"issue": "repeated_clip", "severity": "major", "owner": "editor", "evidence": "shots[0]: 20s / 6s source", "correction": "추가 샷/실제 시연을 확보하고 내레이션에 맞게 분할", "expected_metric": "planned source repeats=0"}, {"issue": "repeated_clip", "severity": "major", "owner": "editor", "evidence": "shots[1]: 20s / 6s source", "correction": "추가 샷/실제 시연을 확보하고 내레이션에 맞게 분할", "expected_metric": "planned source repeats=0"}, {"issue": "repeated_clip", "severity": "major", "owner": "editor", "evidence": "shots[2]: 20s / 6s source", "correction": "추가 샷/실제 시연을 확보하고 내레이션에 맞게 분할", "expected_metric": "planned source repeats=0"}, {"issue": "reused_source", "severity": "major", "owner": "editor", "evidence": "duplicate source_id in shot plan", "correction": "다른 소스와 시연으로 교체", "expected_metric": "unique source ids per shot"}]

### speech · voice
대본과 장면 인수; 쉬운 한국어 발음, 친근한 톤과 속도. MeloTTS 한계 기록. 청취 미평가.
의존성: script, shots

```json
{
  "instructions": "성인 초보자에게 차분하고 또렷하게; 속도는 발화 길이 실측 후 조정. MeloTTS는 기계적인 억양 가능, 자연스러움은 청취 전 unassessed.",
  "pronunciation": "AI는 에이아이, 전문 용어는 쉬운 한국어로. 새 TTS 실행 없음."
}
```

### quality · qa
반복 수치와 의미 검토를 분리; 감각 품질 미평가
의존성: script, shots, speech

```json
{
  "assessments": [
    {
      "criterion_id": "hook",
      "status": "met",
      "evidence": "수정 대본의 질문형 도입; fixture 판단",
      "source": "model_claim"
    },
    {
      "criterion_id": "voice",
      "status": "unassessed",
      "evidence": "음성 미제공",
      "source": "model_claim"
    }
  ],
  "defects": [],
  "sensory_quality": "unassessed"
}
```

### experience · feedback
입력 피드백 원문을 근거로 대상 한정 가설 추출
의존성: quality

```json
{
  "project": "qualityprovider-bc9469dbb4954981ba91068b33913012",
  "domain": "video",
  "target_segment": "30~40대 주부",
  "issue": "반복 화면",
  "positive_preference": "친근한 말투",
  "proposed_correction": "다른 장면과 친근한 말투",
  "evidence": "친근한 말투가 좋겠다",
  "source": "model extraction of user text",
  "confidence": 0.7,
  "verification": "hypothesis"
}
```

## 남은 수동 소스 작업 — Codex 제안, 모델 생성 결과 아님
아래는 새 소스가 필요할 때의 제안 목록이다. 실제 클립을 생성하거나 파일이 존재한다고 주장하지 않는다. 고유한 촬영/시연 장면으로 대체 가능하며, 생성물과 내레이션의 의미 일치는 별도 검토해야 한다.
| 제안 파일명 | 필요 길이 | 수동 제작/생성 지시 |
| --- | --- | --- |
| proposed-shot-01.mp4 (미생성) | 6초 | 세로9:16, 초보 사용자가 노트북 앞에서 질문을 고민하는 도입. 개인정보·로고 노출 없음. |
| proposed-shot-02.mp4 (미생성) | 6초 | 목적과 조건을 메모하는 손 클로즈업, 차분한 조명. 읽을 글자는 편집 자막으로 추가. |
| proposed-shot-03.mp4 (미생성) | 6초 | 냉장고에서 두부와 달걀을 꺼내는 실제 촬영/손 동작. |
| proposed-shot-04.mp4 (미생성) | 6초 | 두 사람이 먹을 재료를 식탁에 놓는 서로 다른 구도. |
| proposed-shot-05.mp4 (미생성) | 6초 | 가상 개인정보 없는 화면녹화: 모호한 메뉴 질문을 입력. 실제 UI는 수동 시연. |
| proposed-shot-06.mp4 (미생성) | 6초 | 화면녹화: 재료·인원 조건을 추가하는 입력 장면. 실제 결과는 미검증 표시. |
| proposed-shot-07.mp4 (미생성) | 6초 | 두 질문을 나란히 비교하는 편집용 실제 화면 캡처, 민감정보 없음. |
| proposed-shot-08.mp4 (미생성) | 6초 | 답변의 조리 가능성을 확인하는 메모/체크 장면, 사실 보증 없음. |
| proposed-shot-09.mp4 (미생성) | 6초 | 개인정보를 입력하지 않는 예시 시연, 실제 개인정보 사용 금지. |
| proposed-shot-10.mp4 (미생성) | 6초 | 사용자가 새 질문을 메모하고 마무리하는 별도 구도. |

새 영상 출력 경로: **없음(미생성)**. 수동 클립과 권리/워터마크 근거를 확보한 뒤 기존 안전한 수입 경로로 처리해야 한다.
기존 시안(이번 변경 없음): `data/video_ai_clip_review/20261109T161931_KST/shorts/preview.mp4`. 이것을 개선된 새 영상으로 제시하지 않는다.

## 판정과 다음 개선
실제 미디어가 없어10점 항목 모두 unassessed, 총점=null. QA의 텍스트 평가와 반복 수치 검사만 존재한다. 게시 수준을 막는 항목은 실제 모델 인수 미실시, 소스 미확보/권리 미확인, 새 합성·청취·시청 및 사용자 최종 평가 미수행이다.
가장 영향 큰 다음 단계는 새 저장소에서 별도 승인한 관리자1회로 모델이 만든 제작 전략을 사람이 평가하는 것이다. 이어서 한 메시지에 맞는 다양한 실제 시연 소스와 명확한 대본을 확보한다. 음성 자연스러움은 현재 미평가이며 API/TTS 변경은 이번 범위 밖이다.
경험은 대상 한정 hypothesis로 저장·선택하며 실제 품질 개선 증거로 승격하지 않았다. 최종 게이트/승인 범위는 provider readiness 보고서 참조.
