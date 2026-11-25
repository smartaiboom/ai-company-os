"""Generate a public-safe snapshot of the latest signed Cutroom research report."""
from datetime import datetime, timedelta, timezone
import argparse
from pathlib import Path
import re
import subprocess
from tempfile import NamedTemporaryFile

from autonomous_company import require
from general_research_report import eligible, versions

REPO=Path(__file__).resolve().parents[2]
LOCAL_ROOT=REPO/'artifacts'/'review_exports'
PUBLIC_PATHS={'company-062d79eeabeb4e5baab3d60ec462db5f':'reports/review_exports/mobile_game_latest.md'}
VIDEO=r'https://youtu\.be/[A-Za-z0-9_-]{11}'
METRIC=r'YouTube Data API views=(\d{1,18}); duration_seconds=(\d{1,5})\. A top search sample, Shorts format and rights unverified\.'
SENSITIVE=re.compile(
    r'AIza[\w-]{12,}|(?:tvly-|sk-|gh[pousr]_|github_pat_)[\w-]+|[A-Fa-f0-9]{24,}|'
    r'\b(?:token|password|secret|authorization|api[ _-]?key|bearer)\b|'
    r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|\b(?:\+?82[- .]?)?01[016789][- .]?\d{3,4}[- .]?\d{4}\b|'
    r'https?://|(?:^|\W)[A-Za-z]:[\\/]|[\\/]|(?:^|\W)(?:localhost|127\.0\.0\.1)\b',re.I)
DECISIONS={None:'대표 검토 대기','approve':'대표 승인','reject':'대표 반려','revise':'대표 수정 요청'}


def timestamp(value):
    try:
        result=datetime.fromisoformat(value)
        if result.utcoffset() is None:
            return '미확인'
        return result.astimezone(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')
    except (ValueError,TypeError):
        return '미확인'


def clean_title(value, private):
    # Public video titles are the only free text passed through. Markdown syntax is stripped.
    if not isinstance(value,str) or SENSITIVE.search(value):
        return '제목 비공개'
    if any(fragment and fragment in value.casefold() for fragment in private):
        return '제목 비공개'
    title=re.sub(r'[^\w\s!?.,:()\-–가-힣]', ' ', value)
    return ' '.join(title.split())[:110] or '제목 비공개'


def public_sources(report,private):
    result={}
    for group in report['staff']['observations']:
        if group['status']!='observed' and not (group['status']=='preserved' and report.get('game_evidence')):
            continue
        for row in group['sources']:
            if group['status']=='preserved' and row['id'] not in report['game_evidence']:
                continue
            if row['scope']!='api_metric' or row['origin']!='youtube_data_api':
                continue
            metric=re.fullmatch(METRIC,row['excerpt'])
            if not metric or not re.fullmatch(VIDEO,row['url']):
                continue
            result[row['id']]=dict(url=row['url'],title=clean_title(row['title'],private),
                views=int(metric[1]),seconds=int(metric[2]),observed=timestamp(row['observed_at']),
                published=timestamp(row['source_date']))
    return result


def decision(record):
    action=(record['decision'] or {}).get('action')
    return '제한된 근거로 기획 인계' if action=='plan' else DECISIONS.get(action,'검토 상태 미확인')


def assemble(project,history,store):
    latest=history[-1]
    report=latest['report']
    feedback=[(item['decision'] or {}).get('feedback','') for item in history]
    fields=[project['goal'],project['representative']['audience'],*feedback,
            *project['representative']['constraints'].values()]
    private={line.strip().casefold() for value in fields if isinstance(value,str)
             for line in value.splitlines() if len(line.strip())>=8}
    sources=public_sources(report,private)
    # Ordinals are local to the export. Internal source IDs never leave the repository.
    labels={key:f'S{index}' for index,key in enumerate(sources,1)}
    topic_rows=[]
    games=set()
    for index,topic in enumerate(report['manager']['topics'],1):
        refs=[ref for ref in topic['source_ids'] if ref in sources]
        name=topic.get('game','')
        supported_name=(isinstance(name,str) and 2<=len(name)<=30
                        and any(name.casefold() in sources[ref]['title'].casefold() for ref in refs)
                        and re.fullmatch(r'[\w -]+',name) and clean_title(name,private)==name)
        if report.get('game_evidence') is not None:
            from mobile_game_evidence import canonical_game
            from mobile_game_evidence import normalized
            canonical=canonical_game(name) if isinstance(name,str) else None
            if report.get('supplement_of') and isinstance(name,str) and not canonical:
                canonical=normalized(name)
            supported_name=bool(canonical and clean_title(canonical,private)==canonical and any(report['game_evidence'].get(ref,{}).get('game')==canonical
                                                  for ref in refs))
            name=canonical
        if supported_name:
            games.add(name.casefold())
        sample=sources.get(refs[0]) if refs else None
        length=re.fullmatch(r'(\d{1,3})\s*초',topic['length'])
        topic_rows.append(f"| {index} | {name if supported_name else '미확인'} | "
                          f"{sample['title'] if sample else '공개 표본 미확인'} | "
                          f"{length[1]+'초' if length else '미확인'} | "
                          f"{', '.join(labels[ref] for ref in refs) or '없음'} | 미확인 |")
    hold=report['manager']['action']=='hold'
    summary=(f'직원 관측에서 공개 영상 메타데이터 {len(sources)}건을 검토용으로 추출했다. '
             f'후보와 연결된 공개 제목에서 확인한 게임명은 {len(games)}종이다.')
    comparison=''
    if len(history)>1:
        previous=history[-2]['report']
        previous_count=len(public_sources(previous,private))
        comparison=f"직전 v{previous['version']} 대비 공개 메타데이터 {previous_count} → {len(sources)}건."
    candidates=(['| 후보 | 공개 제목에 근거한 게임명 | 참고 영상 제목 | 제안 길이 | 출처 | 사용권 |',
                 '| --- | --- | --- | --- | --- | --- |',*topic_rows]
                if topic_rows else ['관리자가 대표 검토 후보를 제안하지 않았다.'])
    lines=['# 컷룸 최신 조사 검토 요약','',
           '- 프로젝트 표시명 · 게임 쇼츠 조사 / 분야 · 영상 기획',
           f"- 보고서 v{report['version']} · {timestamp(report['at'])} · {decision(latest)}",
           f"- 근거 유형 · {'공급자 모델 결과' if report['provenance']=='provider_model_claim' else '오프라인 모의 결과'}",
           '', '## 요약과 관리자 판단','', summary,
           f"관리자 판단 · {'보류' if hold else '제한적 활용 의견'}. "
           +('세 게임 비교 및 영상 사용 조건의 근거가 부족하다.' if hold and len(games)<3
             else '확인한 메타데이터의 범위와 별도 권리 검토 조건을 유지한다.'),
           comparison,'','## 후보 비교','',
           *candidates,'','## 공개 관측','',
           '| 출처 | 공개 제목 | 조회수 | 영상 길이 | 관측 시각 | 게시 시각 |',
           '| --- | --- | ---: | ---: | --- | --- |']
    for key,row in sources.items():
        lines.append(f"| [{labels[key]}]({row['url']}) | {row['title']} | {row['views']:,} | "
                     f"{row['seconds']}초 | {row['observed']} | {row['published']} |")
    if report.get('game_evidence') is not None:
        from mobile_game_evidence import MOBILE_GAMES
        verified={}
        from mobile_catalog_evidence import listing_id
        for ref,row in report['game_evidence'].items():
            game=row['game']
            url=row['platform_source']
            known=game in MOBILE_GAMES and url==MOBILE_GAMES[game][1]
            app_listing=report.get('supplement_of') and listing_id(url)
            if ref in labels and (known or app_listing) and clean_title(game,private)==game:
                verified.setdefault((game,url),[]).append(labels[ref])
        lines+=['','## 게임별 연결 근거','',
                f'공식 모바일 지원과 연결된 게임은 {len({game for game,_ in verified})}종이다. '
                '영상의 실제 플랫폼은 미확인이다.']
        for (game,url),refs in verified.items():
            lines.append(f'- {game} · 관측 {", ".join(refs)} · [공식 모바일 지원]({url})')
    if judgment:=report.get('judgment'):
        measured=judgment['measured']['criteria']['independent_mobile_comparison']
        comparison=judgment['comparison']
        lines+=['','## 근거 상태와 품질 변화','',
                f"- 독립 모바일 근거 기준 · {measured['observed']}/{measured['target']}종"]
        dimensions={'linked_games':'독립 근거 연결 게임','linked_candidates':'독립 근거 연결 후보',
                    'candidates_with_length':'구체적 길이 제안','observed_sources':'직접 관측',
                    'candidate_count':'후보'}
        for key,label in dimensions.items():
            old,new=comparison['before'][key],comparison['after'][key]
            lines.append(f'- {label} · {old} → {new}'+(' · 감소' if key in comparison['declined'] else ''))
        if completion:=judgment.get('completion'):
            if completion['reviewer_attention']:
                lines.append('- 직원은 미충족 기준과 추가로 사용할 수 있는 도구를 남기고 종료했다.')
    lines+=['','## 미확인 사항과 실행 요약','',
            '- 공개 메타데이터는 실제 시청, Shorts 분류, 편집·게시 권리, 전체 인기 순위를 확인하지 않는다.']
    counts={}
    proposal=(store.read('policy.json') or {}).get('proposal',{}) if report.get('supplement_of') else {}
    stores=(store,)
    if proposal.get('development_parent_input_sha256') or proposal.get('followup_scope'):
        from research_quality_loop import development_chain
        stores=development_chain(store)
        lines.append('- 호출 집계는 같은 개발 승인에서 이어받은 서명 원장 기준이다.')
    elif proposal.get('resume_source_input_sha256'):
        from research_supplement_resume import ancestry
        stores=ancestry(store)
        lines.append('- 호출 집계는 이번 보완과 재개 과정에서 이어받은 서명 원장 기준이다.')
    for source in stores:
        for unit,item in source.attempts().items():
            vendor=('YouTube' if unit.startswith('youtube-') else 'Tavily' if unit=='general-web' or unit.startswith(('supplement-web-','web:'))
                    else 'App Store 공개 페이지' if unit.startswith('listing-') else 'Gemini')
            counts.setdefault(vendor,[0,0])
            counts[vendor][0]+=1
            counts[vendor][1]+=int((item['result'] or {}).get('status')=='completed')
    names=('Gemini','Tavily','YouTube')
    if report.get('supplement_of'):
        names+=('App Store 공개 페이지',)
    for name in names:
        reserved,completed=counts.get(name,(0,0))
        lines.append(f'- {name} · 예약 {reserved}회 / 완료 {completed}회')
    if len(history)>1:
        lines+=['','## 이전 검토 이력','']
        for item in history[:-1]:
            old=item['report']
            lines.append(f"- v{old['version']} · {decision(item)} · 공개 메타데이터 {len(public_sources(old,private))}건")
    return ('\n'.join(lines)+'\n').encode()


def write_latest(path,data):
    require(not any(p.is_symlink() for p in (path,*path.parents)),'review_export_path_blocked')
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_file() and path.read_bytes()==data:
        return
    with NamedTemporaryFile(dir=path.parent,delete=False) as temp:
        temp.write(data)
        temporary=Path(temp.name)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def synced(path,data):
    if not path:
        return False
    try:
        result=subprocess.run(['git','show','refs/remotes/origin/main:'+path],cwd=REPO,
                              capture_output=True,timeout=3,check=False)
    except (OSError,subprocess.TimeoutExpired):
        return False
    return result.returncode==0 and result.stdout==data


def generate(workflow,project):
    if not eligible(workflow,project):
        return None
    _,store,history=versions(workflow,project)
    if not history:
        return None
    # Pending revision stores have no result. Resolve the latest completed report's signed ledger.
    from research_workflow import research_store
    completed=history[-1]['report']
    if not store.read('manager-review.json'):
        base,_,_=versions(workflow,project,through=completed['version'])
        store=research_store(workflow.store.root,project,base)
    data=assemble(project,history,store)
    write_latest(LOCAL_ROOT/project['id']/'latest.md',data)
    destination=PUBLIC_PATHS.get(project['id'])
    return dict(version=completed['version'],local=True,shared=synced(destination,data),
                preview=data.decode(),public_path=destination)


def main():
    from studio_server import Studio,ROOT
    parser=argparse.ArgumentParser()
    parser.add_argument('--project',required=True)
    parser.add_argument('--root',type=Path,default=ROOT/'studio')
    parser.add_argument('--confirmed-public-version',type=int)
    args=parser.parse_args()
    studio=Studio(args.root)
    result=generate(studio.workflow,studio.project('workspace',args.project))
    require(result is not None,'review_export_missing')
    if args.confirmed_public_version is None:
        print(result['preview'],end='')
        return
    require(result['version']==args.confirmed_public_version and result['public_path'],'review_export_version_changed')
    write_latest(REPO/result['public_path'],result['preview'].encode())
    print(result['public_path'])


if __name__=='__main__':
    main()
