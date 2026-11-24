"""Representative review of research-only reports, independent of script approvals."""
import re
from datetime import datetime, timedelta

from autonomous_company import digest, exact, now, require
from goal_dialogue import safe_text
from owner_operating_policy import OwnerOperatingPolicy
from role_json_schema import S, arr, enum, obj
from web_research import evidence_catalog

MODE='general_research_report_v1'


def eligible(workflow,project):
    from video_mission_one import GAME_GOAL, MissionOneStore
    flow=project['representative']
    job_id=flow.get('mission_one_job')
    if (not job_id or flow['stage']!='research_planning' or flow['plan_versions'] or flow['planning_jobs']
            or flow.get('budget_job') or project['goal']==GAME_GOAL):
        return False
    store=MissionOneStore(workflow.store.root/'mission_one_provider')
    job=store.load(job_id)
    return (job['status']=='ready' and not job['real_ai']['attempts'] and not job['real_ai']['consent']
            and not store._grant_path(job_id).exists())


def base_for(workflow,project):
    flow=project['representative']
    return dict(mode=MODE,mission=flow['mission_one_job'],target=project['goal'],audience=flow['audience'],
                constraints=flow['constraints'],output='research and planning report only; no script, voice or video',
                required='Use observed dates, views, durations, source links and sample limits. Report duration distribution, '
                         'format and hooks only within observed evidence. Recommend three topics with rationale, proposed length '
                         'and visual feasibility. Distinguish rights unknown and proposals from observations.')


def evidence_branch(feedback, observations, at):
    """Compare requested evidence against the prior report's verified evidence types."""
    rows=list(evidence_catalog(observations).values())
    when=datetime.fromisoformat(at)
    metrics=[row for row in rows if row['scope']=='api_metric' and row['origin']=='youtube_data_api'
             and timedelta(0)<=when-datetime.fromisoformat(row['observed_at'])<timedelta(days=30)]
    pages=[row for row in rows if row['scope']=='public_page']
    rules={
        'video_metrics':r'조회수|(?:영상|쇼츠).{0,6}(?:길이|링크|출처)|관측\s*(시점|날짜)|view count|video links?|duration',
        'recent_examples':r'최근|인기|순위|새.{0,4}(사례|게임|영상)|게임명|실제.{0,5}(영상|쇼츠)|recent|trending',
        'rights_conditions':r'라이선스|사용\s*조건|편집\s*권|사용\s*권|license|licen[cs]ing',
    }
    requested=[kind for kind,pattern in rules.items() if re.search(pattern,feedback,re.I)]
    missing=[]
    if 'video_metrics' in requested and not metrics:
        missing.append('video_metrics')
    if 'recent_examples' in requested:
        missing.append('recent_examples')  # A top sample alone does not establish popularity or cover newly requested examples.
    if 'rights_conditions' in requested:
        missing.append('rights_conditions')  # A page excerpt alone never establishes asset-level permission.
    polishing=bool(re.search(r'요약|표현|문장|가독|형식|정리|명확|summary|wording|clarif',feedback,re.I))
    uncertainty=not requested and not polishing
    return dict(method='rule_based',route='collect' if missing or uncertainty else 'rewrite',
                requested=requested,missing=missing,uncertain=uncertainty,
                available=dict(metrics=len(metrics),direct_pages=len(pages),search_leads=sum(r['scope']=='search_lead' for r in rows)))


def reviewed_search(report):
    return any(row['tool'].startswith('youtube_sample') for row in report['staff']['observations'])


def versions(workflow,project,*,through=None):
    from research_workflow import research_store
    base=base_for(workflow,project)
    history=[]
    while True:
        version=len(history)+1
        base={**base,'version':version}
        store=research_store(workflow.store.root,project,base)
        if base.get('previous') and not store.read('policy.json'):
            prior=history[-1]
            branch=evidence_branch(prior['decision']['feedback'],prior['report']['staff']['observations'],
                                   prior['decision']['at'])
            if branch['route']=='collect':
                base={**base,'revision_plan':branch}
                store=research_store(workflow.store.root,project,base)
                if not store.root.exists() and (reviewed_search(prior['report'])) and set(branch['missing']).intersection(
                        ('video_metrics','recent_examples')):
                    base={**base,'adaptive_sample':True}
                    store=research_store(workflow.store.root,project,base)
                    if not store.root.exists() and any(row['tool'].startswith('youtube_sample_')
                            for row in prior['report']['staff']['observations']) and re.search(r'모바일|mobile',base['target'],re.I):
                        from mobile_game_evidence import planned_queries
                        base={**base,'diverse_games':planned_queries(prior['report']['staff']['observations'],
                                                                    prior['decision']['at'])}
                        # Use JSON-shaped sequences so a reloaded signed scope compares identically.
                        base['diverse_games']=[list(item) for item in base['diverse_games']]
                        store=research_store(workflow.store.root,project,base)
        transition=store.read('continuation.json')
        while transition and transition['route'] in ('collect','report'):
            saved=transition['checkpoint']
            require(digest(saved)==transition['checkpoint_sha256'],'general_report_changed')
            base={**base,'continuation':dict(source_sha256=digest(base), checkpoint_sha256=digest(saved),
                excluded_units=saved['excluded_units'], excluded_payloads=saved['excluded_payloads'])}
            if transition['route']=='report':
                base['continuation']['report_only']=True
            base.pop('work_anchor',None)
            if base.get('adaptive_sample') and re.search(r'모바일|mobile',base['target'],re.I):
                base['verified_mobile_report']=True
            store=research_store(workflow.store.root,project,base)
            transition=store.read('continuation.json')
        result=store.read('research-result.json')
        review=store.read('manager-review.json')
        if not result or not review:
            return base,store,history
        require(review['result_sha256']==digest(result),'general_report_changed')
        report=dict(version=version,staff=result,manager=review['decision'],at=review['at'],
                    provenance=review.get('provenance','provider_model_claim'),revision=base.get('previous'),
                    duration_sample=duration_sample(result['observations'],fresh_only=bool(base.get('adaptive_sample'))))
        if 'game_evidence' in review:
            report['game_evidence']=review['game_evidence']
        report['sha256']=digest(report)
        decision=store.read('owner-review.json')
        require(not decision or decision['report_sha256']==report['sha256'],'general_report_changed')
        history.append(dict(report=report,decision=decision))
        if version==through or not decision or decision['action']!='revise':
            return base,store,history
        base={**base_for(workflow,project),'previous':dict(version=version,report_sha256=report['sha256'],
            feedback=decision['feedback'],manager=report['manager'],staff_claims=result['claims'])}
        if 'game_evidence' in review:
            base['verified_mobile_report']=True
        if review.get('work_anchor'):
            base['work_anchor']=review['work_anchor']


def review(workflow,project,body):
    exact(body,('action','version','sha256','feedback'))
    require(eligible(workflow,project),'research_scope_invalid')
    base,store,history=versions(workflow,project)
    require(history and history[-1]['report']['version']==base['version'] and history[-1]['decision'] is None,'general_report_changed')
    current=history[-1]['report']
    require(current['version']==body['version'] and current['sha256']==body['sha256']
            and body['action'] in ('approve','revise','reject'),'general_report_changed')
    if body['feedback'] or body['action']=='revise':
        safe_text(body['feedback'],1200)
        require(body['feedback'].strip(),'invalid_text')
    else:
        require(body['feedback']=='','invalid_text')
    store.write('owner-review.json',dict(action=body['action'],feedback=body['feedback'],
                                        report_sha256=current['sha256'],at=now()))


def duration_sample(observations,*,fresh_only=False):
    if fresh_only:
        observations=[row for row in observations if row['status']=='observed']
    seconds=[]
    for row in evidence_catalog(observations).values():
        if row['scope']=='api_metric' and row['origin']=='youtube_data_api':
            match=re.fullmatch(r'YouTube Data API views=\d+; duration_seconds=(\d+)\. .*',row['excerpt'])
            if match:
                seconds.append(int(match[1]))
    return sorted(seconds)


def observed_metrics(result,*,fresh_only=False):
    return {row['id'] for group in result['observations'] if not fresh_only or group['status']=='observed'
            for row in group['sources'] if row['scope']=='api_metric' and row['origin']=='youtube_data_api'}


def manager_schema(result,*,collection=False,diverse=False):
    catalog=evidence_catalog(result['observations'])
    refs={**arr(enum(*catalog) if catalog else S),'maxItems':min(3,len(catalog))}
    candidate=dict(title=S,rationale=S,length=S,visuals=S,source_ids=refs,rights=enum('unverified'))
    if collection:
        candidate['game']=S
    usable=len(observed_metrics(result,fresh_only=collection))>=(3 if collection else 1)
    if diverse:
        from mobile_game_evidence import game_evidence
        usable=len({row['game'] for row in game_evidence(result['observations'],result['at']).values()})>=3
    return obj(action=enum('hold','use_with_limits') if usable
               else enum('hold'),note=S,topics={**arr(obj(**candidate)),'minItems':3,'maxItems':3})


def validate_manager(value,result,*,collection=False,diverse=False):
    catalog=evidence_catalog(result['observations'])
    require(len({topic['title'].strip().casefold() for topic in value['topics']})==3,'general_report_changed')
    if diverse and value['action']=='use_with_limits':
        from mobile_game_evidence import canonical_game,game_evidence
        verified=game_evidence(result['observations'],result['at'])
        games={canonical_game(topic['game']) for topic in value['topics']}
        require(len(games)==3 and None not in games,'research_evidence_invalid')
        for topic in value['topics']:
            keys=topic['source_ids']
            require(keys and all(ref in verified and verified[ref]['game']==canonical_game(topic['game']) for ref in keys),
                    'research_evidence_invalid')
    elif collection and value['action']=='use_with_limits':
        games={topic['game'].strip().casefold() for topic in value['topics']}
        require(len(games)==3 and not games.intersection({'','미확인','unknown'}),'research_evidence_invalid')
        all_metrics=set()
        for topic in value['topics']:
            metrics=set(topic['source_ids']) & observed_metrics(result,fresh_only=True)
            require(metrics and not metrics.intersection(all_metrics),'research_evidence_invalid')
            all_metrics.update(metrics)
    for topic in value['topics']:
        if collection:
            safe_text(topic['game'],100)
        require(len(set(topic['source_ids']))==len(topic['source_ids'])
                and all(ref in catalog for ref in topic['source_ids']),'research_evidence_invalid')
        for key in ('title','rationale','length','visuals'):
            safe_text(topic[key],320)


def discovery_queries(base):
    """Offer separate hypotheses for demand, gameplay and format in the project's search domain."""
    target=base['target']
    mobile=bool(re.search(r'모바일|mobile',target,re.I))
    root='모바일 게임' if mobile else '게임'
    english='mobile gaming' if mobile else 'gaming'
    known=[topic.get('game','').strip() for topic in base['previous']['manager']['topics']]
    games=[name for name in known if name and name.lower() not in ('미확인','unknown')
           and len(name)<=36 and re.fullmatch(r"[\w .'-]+",name)]
    # Three requested candidates, with discovery, gameplay and Shorts-oriented perspectives.
    themes=(f'{root} 인기',f'{english} trending',f'{root} 인기 순위',
            f'{root} 플레이 하이라이트',f'{english} gameplay highlights',f'{root} 공략',
            f'{root} 쇼츠',f'{english} shorts',f'{english} gameplay shorts')
    tailored=[f'{game} gameplay shorts' for game in dict.fromkeys(games)]
    return list(dict.fromkeys([*tailored,*themes]))[:len(themes)]


def youtube_tool(query,key,*,variant=None,seen=None):
    from employee_web_research import ENDPOINT, TOOL, collect, usable_observations
    from production_operating import unit
    from web_research import Tool, evidence
    lookback=30 if variant is None else (30,60,90)[variant%3]
    order='viewCount' if variant is None or variant%2==0 else 'relevance'
    operations={name:unit('youtube-'+name+(f'-{variant}' if variant is not None else ''),'youtube_data_api_v3',ENDPOINT+name,
                          ['approved_public_query' if name=='search' else 'public_video_ids'],
                          **({'query':query, **({'lookback_days':lookback,'profile':'public_video_sample','order':order}
                               if variant is not None else {})} if name=='search' else {})) for name in ('search','videos')}

    def observe(option,invoke):
        # The existing collector builds exactly one search and one optional metadata request.
        class WorkingState:
            def save(self,_project):
                pass

        def dispatch(resource,sha,receive):
            response=[]
            def execute(check):
                check()
                if variant is None:
                    response.append(receive())
                    return
                from urllib.error import HTTPError
                from decision_recovery import ProviderFailure
                try:
                    response.append(receive())
                except HTTPError as exc:
                    exc.close()
                    error=ProviderFailure('employee_web_failed_no_retry')
                    error.provider_response={'http_status':exc.code}
                    raise error from None
            invoke(operations[resource],sha,execute)
            return response[0]

        receipt=collect(WorkingState(),{},'general-research',dict(tool=TOOL,queries=[
            dict(query=query,purpose='shorts_examples',lookback_days=lookback,order=order)]),
            key,lambda:None,provenance='employee_requested_api',dispatch=dispatch,exploratory=variant is not None,seen=seen)
        rows=[]
        if any(row['status']=='metadata_verified' for row in receipt['observations']):
            for row in usable_observations(receipt):
                rows.append(evidence('https://youtu.be/'+row['id'].split(':',1)[1],row['title'][:200],
                    f"YouTube Data API views={row['view_count']}; duration_seconds={row['duration_seconds']}. "
                    "A top search sample, Shorts format and rights unverified.",
                    'api_metric','youtube_data_api',row['observed_at'],row['published_at']))
        diagnostic={}
        if variant is not None:
            diagnostic=dict(query=query,requests=[{field:entry[field] for field in
                ('request_hash','http_status','response_sha256','finished_at')} for entry in receipt['attempts']],
                rejected=sum(':' in row['id'] and row['status']!='metadata_verified'
                             for row in receipt['observations']))
            if not rows:
                diagnostic['reason']=next((row['reason'] for row in receipt['observations'] if ':' not in row['id']),
                                          'metadata_ineligible')
        return dict(status='observed' if rows else 'empty',sources=rows,**diagnostic)

    return Tool('youtube_sample' if variant is None else f'youtube_sample_{variant}','Sample up to five recent game videos. View counts and durations are observed; Shorts format is unconfirmed.',
                {'sample':query},None,requests=tuple(operations.values()),observe=observe)
