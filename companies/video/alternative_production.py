"""A separately reviewed local pilot backed by the existing production renderer."""
import re
from shutil import which

from autonomous_company import CompanyError, digest, exact, now, parse, require
from goal_dialogue import safe_text
from mission_production import (ProductionManager, SceneSpeechReceipts, approved_manager_result,
                               clip_job, draft_id, prepare_manager_request, production_keys, production_manager)
from owner_operating_policy import OwnerOperatingPolicy
from production_video import portrait_font, render, units, validate_portrait
from role_json_schema import S, arr, enum, obj
from task_replanning import strategy_schema, strategy_assignment

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
    root=parent.root/'alternative_production'
    require(not root.is_symlink(),'invalid_acceptance_path')
    return StrategyManager(root,dict(input=inputs,schema=SCHEMA,system=SYSTEM)),spec,speech


def records(manager):
    return OwnerOperatingPolicy(manager.root/'pilot',dict(scope='alternative_production_pilot',
        input_sha256=digest(manager.contract['input'])))


def view(manager):
    jid=draft_id(manager)
    if not jid:
        return dict(status='unprepared',input=manager.contract['input'])
    draft=manager.load(jid)
    attempts=draft['real_ai']['attempts']
    if not attempts:
        if draft['grants']:
            return dict(status='approved')
        review=manager.path(jid).with_suffix('.review.json')
        require(review.is_file() and not review.is_symlink(),'strategy_approval_required')
        saved=parse(review.read_text())
        return dict(status='prepared',review_hash=saved['review_hash'],expires_at=saved['body']['expires_at'],
                    input=manager.contract['input'])
    if attempts[0]['status']!='completed':
        return dict(status='stopped')
    decision=approved_manager_result(manager)
    store=records(manager)
    approval=store.read('approval.json')
    receipt=store.read('rendered.json')
    assignment=strategy_assignment(decision,SCHEMA,manager.contract['input'],ROLES)
    return dict(status='rendered' if receipt else 'stopped' if store.read('started.json') else
                'assigned' if approval else 'review' if assignment else 'hold',
                decision=decision,proposal_sha256=digest(decision),assignment=approval['assignment'] if approval else None,
                receipt=receipt,evaluation=store.read('evaluation.json'))


def status(workflow,project):
    if project['representative']['stage']!='video_revision':
        return None
    try:
        manager,_,_=setup(workflow,project)
        result=view(manager)
        if result.get('receipt'):
            result['url']=f"/media/workspace/{project['id']}/alternative/{result['receipt']['id']}"
        return result
    except (CompanyError,FileNotFoundError) as exc:
        return dict(status='unavailable',reason=getattr(exc,'code','strategy_inputs_missing'))


def action(workflow,pid,name,body):
    with workflow.store.lock(pid):
        project=workflow.store.load(pid)
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
