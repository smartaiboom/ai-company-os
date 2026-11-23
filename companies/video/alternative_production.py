"""A separately reviewed local pilot backed by the existing production renderer."""
import re
from pathlib import Path
from shutil import which

from autonomous_company import CompanyError, digest, exact, now, parse, require
from goal_dialogue import safe_text
from mission_production import (ProductionManager, SceneSpeechReceipts, approved_manager_result,
                               clip_job, draft_id, prepare_manager_request, production_keys, production_manager)
from owner_operating_policy import OwnerOperatingPolicy
from production_video import portrait_font, render, units, validate_portrait
from role_json_schema import S, arr, enum, obj
from task_replanning import strategy_schema, strategy_assignment

FIXTURE_ROOT=Path(__file__).resolve().parents[2]/'artifacts'/'alternative-production-fixtures'

ROLES={'local_graphics':'visual_production'}
ROUTES=(*ROLES,'research','rights_cleared_assets','capture','restructure','hold','ask_owner')
GRAPHICS=('conversation','target','workflow','comparison')
CAMERAS=('hold','push_in','pan_right')
SCHEMA=strategy_schema(ROUTES,obj(scene_id=S,title=S,graphic=enum(*GRAPHICS),labels=arr(S),camera=enum(*CAMERAS)))
SYSTEM=('Act as the production manager. Preserve the approved objective, narration, captions and timings. '
        'Use local_graphics only for an honest visual explanation with specific, varied scene designs. '
        'Never represent an illustration as gameplay or use unsupported claims as on-screen fact. Other routes '
        'require separate review and have an empty work array. Choose hold or ask_owner if the goal cannot be met. '
        'Do not infer rights or propose downloading. Answer in Korean using the given JSON schema.')


class StrategyManager(ProductionManager):
    marker_name='.alternative-production-manager-v1'
    acceptance_scope='alternative_production_manager_once_v1'

    def _context(self,p):
        inputs=self.contract['input']
        data={key:inputs[key] for key in ('goal','audience','feedback','limits','source_limits',
                                         'local_ready','research_context') if key in inputs}
        fields=('scene_id','narration','caption','frames','caption_frames','visual_need','third_party_media')
        data['scenes']=[{key:row[key] for key in fields if key in row} for row in inputs['scenes']]
        return data

    def _policy(self,p):
        return {**super()._policy(p),'provider_quota':'unknown','provider_billing':'unknown',
                'external_tools':[],'max_cost_usd':0}

    def validate_plan(self,value):
        assignment=strategy_assignment(value,SCHEMA,self.contract['input'],ROLES)
        if assignment:
            scenes=self.contract['input']['scenes']
            require([row['scene_id'] for row in assignment['work']]==[s['scene_id'] for s in scenes],
                    'strategy_scene_mismatch')
            require(self.contract['input']['local_ready'],'strategy_local_unavailable')
            for row in assignment['work']:
                safe_text(row['title'],40)
                require('\n' not in row['title'] and units(row['title'])<=32,'strategy_invalid')
                require(1<=len(row['labels'])<=3,'strategy_invalid')
                for label in row['labels']:
                    safe_text(label,24)
                    require('\n' not in label and units(label)<=38,'strategy_invalid')


def setup(workflow,project):
    from measured_timeline import approved_clip_timeline
    parent=production_manager(workflow,project)
    plan=approved_manager_result(parent)
    flow=project['representative']
    version=flow['plan_versions'][-1]
    spec=workflow.mission_production_spec(flow,version['version'],version['sha256'],'local_speech')
    _,timeline=clip_job(parent,plan)
    timeline,timing_hash=approved_clip_timeline(parent,plan,flow['constraints'],[],timeline)
    require(timing_hash is not None,'strategy_timeline_required')
    speech=SceneSpeechReceipts(parent,plan)
    scenes=[]
    for shot,cue,scene,need in zip(parent.contract['input']['storyboard'],timeline['approved_timeline'],
                                   spec['scenes'],plan['scenes'],strict=True):
        _,receipt=speech.validated(shot['scene_id'])
        frames=round(cue['end']*24)-round(cue['start']*24)
        scene['seconds']=frames/24
        scenes.append(dict(scene_id=shot['scene_id'],narration=shot['narration'],caption=shot['caption'],
                           frames=frames,caption_frames=round(cue['caption_seconds']*24),visual_need=need['request'],speech_sha256=receipt['audio_sha256'],
                           third_party_media='unavailable_to_this_pilot'))
    inputs=dict(goal=project['goal'],audience=parent.contract['input']['audience'],scenes=scenes,
        plan_sha256=version['sha256'],timeline_sha256=timing_hash,feedback=flow['decisions'][-1]['feedback'],
        quality=plan['review_criteria'],limits=dict(cost_usd=0,downloads=0,publishing=False),
        source_limits='Visual use requires asset-level rights. The pilot includes no third-party media or AI image generator.',
        local_ready=bool(which('ffmpeg') and which('ffprobe') and portrait_font()))
    from research_workflow import status as research_status
    research=research_status(workflow,project) or {}
    supervision=research.get('supervision') or {}
    outcome=supervision.get('outcome') or {}
    if (outcome.get('decision') or {}).get('action')=='hold' and outcome.get('goal_achieved') is False:
        inputs['research_context']=dict(decision='hold',
            reason='Official source text and asset-level editing rights were not established. Search leads are not evidence of rights.')
    root=parent.root/'alternative_production'
    require(not root.is_symlink(),'invalid_acceptance_path')
    return StrategyManager(root,dict(input=inputs,schema=SCHEMA,system=SYSTEM)),spec,speech


def records(manager):
    return OwnerOperatingPolicy(manager.root/'pilot',dict(scope='alternative_production_pilot',
        input_sha256=digest(manager.contract['input'])))


def view(manager):
    jid=draft_id(manager)
    if not jid:
        return dict(status='unprepared',input=manager._context(None))
    draft=manager.load(jid)
    attempts=draft['real_ai']['attempts']
    if not attempts:
        if draft['grants']:
            return dict(status='approved')
        review=manager.path(jid).with_suffix('.review.json')
        require(review.is_file() and not review.is_symlink(),'strategy_approval_required')
        saved=parse(review.read_text())
        return dict(status='prepared',review_hash=saved['review_hash'],expires_at=saved['body']['expires_at'],
                    input=manager._context(None))
    attempt=attempts[0]
    run=dict(attempts=1,completed=int(attempt['status']=='completed'),
             response_received=attempt.get('response_received',attempt['status']=='completed'),
             total_tokens=(attempt.get('usage') or {}).get('total_tokens'))
    if attempt['status']!='completed':
        from decision_recovery import failure_kind
        run.update(failure_category=failure_kind(attempt),diagnostic=attempt.get('diagnostic'),
                   provider_http_status=attempt.get('http_status'),request_id=attempt['id'])
        return dict(status='stopped',reason=attempt.get('reason'),run=run)
    decision=approved_manager_result(manager)
    store=records(manager)
    approval=store.read('approval.json')
    receipt=store.read('rendered.json')
    assignment=strategy_assignment(decision,SCHEMA,manager.contract['input'],ROLES)
    return dict(status='rendered' if receipt else 'stopped' if store.read('started.json') else
                'assigned' if approval else 'review' if assignment else 'hold',
                run=run,decision=decision,proposal_sha256=digest(decision),assignment=approval['assignment'] if approval else None,
                receipt=receipt,evaluation=store.read('evaluation.json'))


def fixture(project_id):
    """Resolve a local, explicitly mock preview without involving the operational pilot."""
    if not re.fullmatch(r'company-[a-f0-9]{32}',project_id):
        return None
    folder=FIXTURE_ROOT/project_id
    manifest=folder/'sample.json'
    if any(path.is_symlink() for path in (manifest,folder,FIXTURE_ROOT,FIXTURE_ROOT.parent)):
        return None
    if not manifest.is_file() or manifest.stat().st_size>1024:
        return None
    try:
        data=parse(manifest.read_text())
        exact(data,('id','sha256','provenance'))
    except (CompanyError,OSError,ValueError):
        return None
    if not all(isinstance(value,str) for value in data.values()):
        return None
    if (data['provenance']!='mock_manager_and_mock_approval'
            or not re.fullmatch(r'mock-[a-f0-9]{32}',data['id'])
            or not re.fullmatch(r'[a-f0-9]{64}',data['sha256'])):
        return None
    video=folder/data['id']/'video.mp4'
    if video.is_symlink() or video.parent.is_symlink() or not video.is_file():
        return None
    return data,video


def fixture_media(project_id,fixture_id):
    from local_melo_tts import file_hash
    found=fixture(project_id)
    if not found or found[0]['id']!=fixture_id:
        raise FileNotFoundError
    data,path=found
    require(file_hash(path)==data['sha256'],'representative_artifact_changed')
    return path


FIXTURE_REVIEW_FIELDS=('visual','audio','captions','interest','improvement')


def fixture_reviews(path, data):
    return OwnerOperatingPolicy(path.parent/'review',dict(scope='alternative_fixture_owner_review',
                                id=data['id'],video_sha256=data['sha256']))


def evaluate_fixture(pid,body):
    exact(body,('id','sha256',*FIXTURE_REVIEW_FIELDS))
    found=fixture(pid)
    require(found and (body['id'],body['sha256'])==(found[0]['id'],found[0]['sha256']),
            'strategy_approval_required')
    data,path=found
    fixture_media(pid,data['id'])
    notes={field:body[field] for field in FIXTURE_REVIEW_FIELDS}
    for note in notes.values():
        safe_text(note,400)
        require(bool(note.strip()),'invalid_text')
    store=fixture_reviews(path,data)
    store.root.mkdir(mode=0o700,exist_ok=True)
    store.write('evaluation.json',dict(at=now(),fixture_id=data['id'],video_sha256=data['sha256'],
                source='owner',provenance=data['provenance'],notes=notes,publish_allowed=False))


def status(workflow,project):
    if project['representative']['stage']!='video_revision':
        return None
    try:
        manager,_,_=setup(workflow,project)
        result=view(manager)
        if result.get('receipt'):
            result['url']=f"/media/workspace/{project['id']}/alternative/{result['receipt']['id']}"
        sample=fixture(project['id'])
        if sample:
            result['fixture']=dict(**sample[0],evaluation=fixture_reviews(sample[1],sample[0]).read('evaluation.json'),url=f"/media/workspace/{project['id']}/alternative-fixture/{sample[0]['id']}")
        return result
    except (CompanyError,FileNotFoundError) as exc:
        return dict(status='unavailable',reason=getattr(exc,'code','strategy_inputs_missing'))


def action(workflow,pid,name,body):
    with workflow.store.lock(pid):
        project=workflow.store.load(pid)
        if name=='alternative-fixture-evaluate':
            return evaluate_fixture(pid,body)
        manager,spec,speech=setup(workflow,project)
        jid=draft_id(manager)
        if name=='alternative-prepare':
            return prepare_manager_request(manager,jid,body)
        require(jid is not None,'production_manager_missing')
        if name=='alternative-consent':
            exact(body,('review_hash','confirmed'))
            key,_=production_keys()
            return manager.approve_consent(jid,body['review_hash'],api_key=key,owner_confirmed=body['confirmed'],
                free_project_confirmed=body['confirmed'],google_data_policy_accepted=body['confirmed'])
        if name=='alternative-decide':
            exact(body,())
            key,_=production_keys()
            return manager.ask_ai(jid,api_key=key)
        decision=approved_manager_result(manager)
        assignment=strategy_assignment(decision,SCHEMA,manager.contract['input'],ROLES)
        store=records(manager)
        require(assignment is not None,'strategy_requires_separate_review')
        if name=='alternative-approve':
            exact(body,('confirmed','proposal_sha256'))
            require(body['confirmed'] is True and body['proposal_sha256']==digest(decision) and not store.root.exists(),
                    'strategy_approval_required')
            scenes=[]
            for scene,work,source in zip(spec['scenes'],decision['work'],manager.contract['input']['scenes'],strict=True):
                scene.update(title=work['title'],camera=work['camera'],
                             graphic=dict(kind=work['graphic'],labels=work['labels']))
                scenes.append(dict(scene_id=work['scene_id'],narration=source['narration'],caption=source['caption'],
                    goal=source['visual_need'],style=scene['graphic'],source_audio_sha256=source['speech_sha256'],
                    rights='local procedural artwork; existing approved narration; local review only',
                    output='720x1280 MP4',completion=decision['success_criteria'],unresolved=decision['risk']))
            validate_portrait(spec)
            assignment.update(scenes=scenes,input_refs=dict(plan=manager.contract['input']['plan_sha256'],
                              timeline=manager.contract['input']['timeline_sha256']),publish_allowed=False)
            store.root.mkdir(mode=0o700)
            store.write('approval.json',dict(assignment=assignment,spec=spec,at=now(),owner_confirmed=True))
            return
        if name=='alternative-evaluate':
            exact(body,('sha256','feedback'))
            receipt=store.read('rendered.json')
            require(receipt and body['sha256']==receipt['sha256'],'strategy_approval_required')
            safe_text(body['feedback'],1000)
            store.write('evaluation.json',dict(at=now(),video_sha256=receipt['sha256'],feedback=body['feedback'],
                                               source='owner',publish_allowed=False))
            return
        exact(body,())
        approval=store.read('approval.json')
        require(name=='alternative-render' and approval and approval['owner_confirmed']
                and approval['assignment']['decision_sha256']==digest(decision)
                and approval['assignment']['input_sha256']==digest(manager.contract['input'])
                and not store.read('started.json'),'strategy_approval_required')
        import uuid
        pilot_id=uuid.uuid4().hex
        store.write('started.json',dict(id=pilot_id,at=now()))
        folder=store.root/pilot_id
        folder.mkdir(mode=0o700)
        receipt=render(approval['spec'],folder,speech=speech,illustrated=True,
                       caption_frames=[row['caption_frames'] for row in manager.contract['input']['scenes']])
        store.write('rendered.json',dict(id=pilot_id,sha256=receipt['sha256'],decoded=receipt['decoded'],
                    seconds=receipt['duration_seconds'],quality='unassessed',at=now()))


def media(workflow,project,pilot_id):
    from local_melo_tts import file_hash
    manager,_,_=setup(workflow,project)
    store=records(manager)
    receipt=store.read('rendered.json')
    require(receipt and re.fullmatch('[a-f0-9]{32}',pilot_id) and receipt['id']==pilot_id,'strategy_media_missing')
    path=store.root/pilot_id/'video.mp4'
    require(path.is_file() and not path.is_symlink() and not path.parent.is_symlink()
            and file_hash(path)==receipt['sha256'],'representative_artifact_changed')
    return path
