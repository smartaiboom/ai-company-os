# 미션 01 공식 제작사 자료 확보 결과

## 운영 확인

대표의 마지막 Commons 복구는 GET 8회, 무료 Gemini 메타데이터 판단 1회로 종료됐다. 검색에서 기술 기준을 통과한 항목은 중복 제거 전 15건이었다. 기존 진단 후보를 포함해 화면에 남은 후보는 19건이다. Gemini가 판단한 장면–후보 조합 7건 중 5건은 불명확했고 2건은 무관했다. 장면에 적합한 후보와 새 권리 승인 모두 0건이다. 모델 전 검토에서는 권리 근거 부족 11건, 화면 유형 부적합 1건이 확인됐다. 해당 복구를 재실행하지 않았다.

| 기존 검색어 | 유형 | 기술 통과 | 기술 제외 |
| --- | --- | ---: | ---: |
| `intitle:"mobile PC games"` | 영상 | 0 | 0 |
| `intitle:"Don't Starve Together"` | 이미지 | 0 | 1 |
| `intitle:"World of Warcraft Forever"` | 영상 | 0 | 0 |
| `intitle:"Hogwarts Legacy"` | 영상 | 1 | 4 |
| `"mobile PC"` | 이미지 | 5 | 0 |
| `"Don't Starve Together"` | 영상 | 0 | 0 |
| `"World of Warcraft"` | 이미지 | 4 | 1 |
| `"Hogwarts Legacy"` | 이미지 | 5 | 0 |

도입 설명, Don't Starve Together, World of Warcraft Forever, Hogwarts Legacy의 네 장면 모두 자산 인수 대기다. 승인 대본 v2, 실측 WAV 4개(3.68 / 7.36 / 5.16 / 6.40초), 승인 시간표 840프레임(24fps, 35초), 기존 검토·평가 및 운영 원장을 보존했다.

## 공식 출처 조사

- **Klei** 공개 게임 페이지의 개별 이미지 링크에서 농사, Cave Toad 전투, Maxwell 그림자 공격을 확인했다. Press Kit은 Dropbox에, 트레일러는 YouTube에 연결된다. 지원 문서는 게임을 플레이하며 제작하는 영상과 스트리밍을 다룬다. 개별 제작사 이미지의 다운로드·로컬 편집 허가와 사이트·CDN의 robots는 개발 조사에서 확인되지 않았다. [게임·미디어 페이지](https://www.klei.com/games/dont-starve-together/) · [게임 영상 정책 지원 문서](https://support.klei.com/hc/en-us/articles/360029557192-Can-I-stream-or-make-videos-of-Don-t-Starve-Together)
- **Blizzard** 2026년 11월 4일 게시된 출시 키트와 공개 키트에 개별 보도 이미지가 있다. Games Press가 안내하는 편집 보도와 트레일러 재게시는 적용 범위가 다르며, 편집·다운로드의 구체적 적용과 자동 접근 허용 확인이 필요하다. 이 제공처는 운영 자동 탐색 범위에 등록하지 않았다. [출시 키트](https://blizzard.gamespress.com/WoW-Forever-Launch-Press-Kit) · [공개 키트](https://blizzard.gamespress.com/en-US/Kit/Details/wowforeverreveal) · [자산 FAQ](https://www.gamespress.com/en-US/FAQ---Use-of-Assets) · [이용 조건](https://www.gamespress.com/en-US/Site/TermsAndConditions)
- **WB Games** 게임 소개 및 공식 미디어 페이지에 이미지 경로가 있다. 보도 시스템의 계정 요건과 공개 이미지의 다운로드·편집 조건은 미확인이다. Commons에서 확인한 호그와트 영상 원본 361.2MB, 546.5MB, 1.69GB는 64MiB 상한을 넘는다. 공식 저해상도 파일이나 파생본은 해당 버전의 제공 조건, 권리와 해시를 확인할 수 있을 때만 후속 검토 대상이다. [WB 게임 소개](https://warnerbrosgames.com/article/hogwarts-legacy) · [공식 미디어](https://www.hogwartslegacy.com/en-us/media) · [Commons 4K 발표 영상](https://commons.wikimedia.org/wiki/File:Hogwarts_Legacy_%E2%80%93_Official_4K_Reveal_Trailer.webm) · [Commons 제작 영상 목록](https://commons.wikimedia.org/wiki/Category:Documentary_videos) · [Commons State of Play](https://commons.wikimedia.org/wiki/File:Hogwarts_Legacy_State_of_Play_-_Official_Gameplay_Reveal_4K.webm)

## 컷룸에서 실행할 수 있는 범위

현재 컷룸의 다음 업무에서 **공식 제작사 자료 탐색 검토·승인 → 공식 제작사 자료 탐색 실행**을 선택한다. 이번 운영 범위는 Klei 사이트·CDN robots와 정책·게임 페이지를 합쳐 GET 최대 4회, 무료 Gemini 최대 1회, 미디어 다운로드 0회, 비용 상한 $0이다. 게임 페이지는 승인 장면에서 추출한 게임명과 제작사별 등록 범위로 구성하며 개별 자료 링크는 공개 HTML에서 추출한다. Gemini는 접근이 확인된 후보가 있을 때 장면 요구와 후보 메타데이터를 바탕으로 공식 자료, 추가 허가, 권리 확인 자체 캡처 또는 보류 경로를 판단한다. 이 단계에서 실제 파일을 열람하거나 다운로드하지 않는다.

호스트·경로, 공개 IP에 고정한 TLS, robots, 명시적 자동 접근 제한, MIME, 응답 크기와 제한 시간을 확인한다. robots가 없거나 금지된 경로, 리다이렉트, 접근 제한, 외부 호스트, 압축 파일은 건너뛴다. 무료 다운로드와 로컬 편집 허가가 선택 파일에 적용되는 경우에만 공식 문서의 정확한 문구와 출처를 컷룸에서 확인한다. 이후 기존 자산·편집 범위에서 자료별 다운로드를 다시 승인한다. 게시 권리는 별도다. PNG/JPEG는 설명·참고 라벨을 붙여 기존 이미지 모션으로, MP4/WebM은 기존 ClipJob으로 인계한다. 실제 게시, 동적 사이트·미디어 JSON API, 유료·로그인 보도 시스템, 생성 실행기는 이번 경로에 연결하지 않았다. 기존 FFmpeg 기반 로컬 이미지 모션은 검증했고 별도 생성 도구는 설치하지 않았다.

## 검증

- 오프라인 테스트에서 허용 도메인·경로, robots 차단, 로그인·CAPTCHA 징후, 제3자 링크·압축·스크립트 제외, 리다이렉트·크기 제한, 빈 후보의 모델 호출 차단, 컷룸 다음 액션을 확인했다.
- 운영 복제본의 모의 제작사 HTML, 정적 메타데이터 및 공식 권리 문서로 탐색했다. 별도 모의 Gemini 판단 1회, 권리 원문 불일치 거부, 공식 자료 권리 검토, 별도 편집 승인 뒤 이미지 1장·WebM 3개와 운영본에서 복사한 WAV 4개를 처리했다. FFmpeg 출력은 35초·840프레임이었다. 이미지 장면 라벨, 자산 4개의 출처 표시 및 합성 검토용 버전 인계를 확인했다.
- 운영 서버를 기존 실행 인수·환경·작업 루트로 재시작했다. localhost의 컷룸과 정적 파일, 공식 제작사 자료 탐색 대기, 새 승인 0건, 기존 JSON·MP4·WAV 체크섬과 음성·승인 시간표 보존을 확인했다.
- 문서 개발 조사 외 실제 미션 신규 호출, 실제 미디어 다운로드, 운영 승인 생성, 도구 설치 및 생성은 모두 0회다. 실제 제공처 자동 접근과 편집 허가, 게임 자료 확보 및 본편 품질은 미검증이다.
