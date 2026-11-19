# 미션 01 Commons 후보 제외 진단 · 2026-11-19 KST

## 실제 기록

최초 검색은 영상 4회에서 모두 후보 0건·기술 제외 0건이었고 별도 Gemini 대안 판단 1회가 완료됐다. 개선 검색은 GET 8회가 완료됐으며 결과는 후보 0건·기술 제외 **30건**이다. 아래는 각 요청의 서명된 메타데이터와 시도 원장을 조회한 결과다.

| 순서 | 장면·형식 | 실제 검색어 | 후보 | 기술 제외 |
| --- | --- | --- | ---: | ---: |
| 1 | scene-1 · 영상 | mobile PC games | 0 | 5 |
| 2 | scene-2 · 이미지 | Don't Starve Together | 0 | 5 |
| 3 | scene-3 · 영상 | World of Warcraft Forever | 0 | 0 |
| 4 | scene-4 · 영상 | Hogwarts Legacy | 0 | 5 |
| 5 | scene-1 · 이미지 | mobile PC | 0 | 5 |
| 6 | scene-2 · 영상 | Don't Starve Together | 0 | 0 |
| 7 | scene-3 · 이미지 | World of Warcraft | 0 | 5 |
| 8 | scene-4 · 이미지 | Hogwarts Legacy | 0 | 5 |

기존 운영 디렉터리와 확인 가능한 로그 위치에서 원본 Commons 응답을 찾지 못했다. 기존 `metadata-*.json`에는 통과 후보, 제외 수, 시각만 있고 요청 원장에는 서명된 요청 해시와 상태가 있다. **30건 각각의 실제 원인은 복구할 수 없다.** 재분석할 원본이 없어 과거 기록을 새 판정으로 채우지 않았다.

## 재현한 결함과 변경

MediaWiki는 설정이 켜져 있을 때 `imageinfo.url`에 `utm_source=commons.wikimedia.org`, `utm_campaign=imageinfo`, `utm_content=original`을 붙일 수 있다. Wikimedia에 공개된 실제 WebM 응답 예시를 기존 파서 조건에 넣으면 정상 원본 경로도 쿼리 문자열 때문에 제외된다. 새 파서는 이 정확한 세 쌍만 인식해 제거한 뒤 기존 HTTPS·호스트·원본 경로 검증을 적용한다. 쿼리 추가·중복, 자격 증명, 다른 호스트, 조각, 잘못된 퍼센트 인코딩과 인코딩된 경로 탈출은 계속 차단한다. 다운로드 요청은 검증된 쿼리 없는 URL만 쓴다. 이 결함이 과거 30건에 기여했을 가능성이 있으나 비율과 다른 원인은 미확인이다. [MediaWiki 원본 URL 구현](https://raw.githubusercontent.com/wikimedia/mediawiki/master/includes/Api/ApiQueryImageInfo.php), [Wikimedia 운영 설정](https://raw.githubusercontent.com/wikimedia/operations-mediawiki-config/master/wmf-config/InitialiseSettings.php), [Wikimedia의 실제 응답 예시](https://phabricator.wikimedia.org/T415202)

요청의 `generator=search`·`prop=imageinfo`·`formatversion=2`와 페이지 배열, 파일 이름공간, `imageinfo` 배열, MIME·mediatype·바이트 크기를 공식 계약과 대조했다. 영상은 VIDEO와 MP4/WebM, 이미지는 BITMAP과 PNG/JPEG가 필요하다. 이미지 8MiB·영상 64MiB, 기존 공개 IP·TLS·리다이렉트·픽셀 제한과 권리 검토를 유지했다. 공급자가 다른 형식이나 빠진 필드를 보내면 사유가 남는다. [MediaWiki 속성 조회](https://www.mediawiki.org/wiki/API:Properties/en), [JSON v2 형식](https://www.mediawiki.org/wiki/API:JSON_version_2), [Imageinfo 필드](https://www.mediawiki.org/wiki/API:Imageinfo/en), [파일 검색 유형](https://www.mediawiki.org/wiki/Help:CirrusSearch#File_properties_search)

새 요청은 후보별 페이지 ID, 정제한 파일명, MIME·미디어 유형·크기, 원본 경로 통과 여부, 응답 JSON 해시와 판정 코드를 저장한다. 원문 응답·HTML·거부 URL은 스냅샷에 남기지 않는다. 기술 제외, 권리 근거 미확인, 장면 적합성 미평가를 각각 표시한다. 한 항목에 여러 기술 코드가 기록될 수 있다. 컷룸 **관련 상세 보기**에서 최초·개선·진단 기록을 각각 확인할 수 있다.

## 대표 다음 조작

**현재 상태 / 다음 작업 → Commons 제외 원인 진단 검토·승인 → Commons 제외 원인 진단 실행**을 선택할 수 있다. 기존에 5건이 제외된 **Don't Starve Together · 이미지** 검색을 선정했으며 원래 요청 해시와 동일한 Commons GET **최대 1회**, 비용 $0, 다운로드·Gemini 0회다. 기존 정책과 별도이며 반복 실행은 차단된다. 이 조회는 현재 응답의 판정 근거를 확보하기 위한 것이며 과거 30건의 응답을 복원하지는 못한다. 통과 후보는 **진단 후보 권리 검토**를 거쳐 기존 편집 후보로 인계할 수 있다. 나머지 검색은 이번 범위에 포함되지 않는다.

## 검증 및 운영 보존

- 복제본에서 운영 집계 8회·30건을 새 로컬 서명으로 재현한 뒤 모의 진단을 한 번 실행했다. 알려진 추적 값이 포함된 URL은 통과했고, 위험 URL·MIME·유형·크기 복합 실패, 페이지 및 imageinfo 필드별 오류, 중복 페이지 ID, 권리 미확인·잘못된 검토 해시와 재조회 차단을 검증했다. 후보는 권리 검토 뒤 기존 자산 등록 경로에서 조회됐다. 복제본의 운영 WAV 바이트도 대조했다.
- 서버를 기존 환경과 루트로 재시작해 localhost 상세, 최신 JS/CSS, 기존 검색 원장과 승인 타임라인·WAV 네 건 및 선택한 운영 파일 해시를 확인했다. 대본 v2, 840프레임 조정안, 저장 청취 의견, 기존 관리자와 작업 원장을 보존했다. 운영 진단은 미승인 상태다. 브라우저 실조작은 미검증이다.
- Python 33건 중 32건 통과·1건 건너뜀. JavaScript 구문·상태 분기와 Git diff 검사 통과. 이번 실제 Commons 검색·진단·다운로드·Gemini·TTS·영상 생성 요청은 모두 **0회**다. 개발 문서만 조회했다.
