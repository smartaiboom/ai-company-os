"""Apply signed private-owner delegation to the existing production adapters."""
from datetime import datetime, timedelta
import re

from autonomous_company import CompanyError, digest, exact, now, require
from autonomous_gemini35 import ENDPOINT, MODEL
from measured_timeline import measurements, timeline_worker
from mission_production import (MISSION_ACCOUNT, draft_id, prepare_manager_request, production_keys,
                                production_status, voice_scene)
from owner_operating_policy import OwnerOperatingPolicy
from production_sources import source_assignment
from tts_job import ENDPOINT as TTS_ENDPOINT

VOICE_DATA=['approved_scene_narration','existing_scene_performance_direction']
SOURCE_DATA=['approved_goal_and_storyboard','approved_production_direction','representative_revision_feedback','existing_public_metadata',
             'local_asset_description_and_hash']
TIMELINE_DATA=['approved_goal_and_storyboard','scene_audio_hash_and_duration','clip_hash_and_duration',
               'caption_reading_metrics']


def policy_store(manager,plan):
    return OwnerOperatingPolicy(manager.root/'owner_operating',dict(
        project=MISSION_ACCOUNT,provider='Google Gemini',plan_sha256=manager.contract['input']['approved_plan_hash'],
        direction_sha256=digest(plan),revision_scope=manager.root.name,mode='cutroom_production_v1'))


def unit(identifier, model, endpoint, data, **kwargs):
    return dict(id=identifier,model=model,endpoint=endpoint,data_types=data,max_cost_usd=0,**kwargs)


def policy_offer(manager,plan,state):
    units=[]
    timing=state.get('timeline') or {}
    sources=state['source_assessment']
    if (any(not info['attempted'] for info in state['voices'].values())
            or timing.get('status') in ('prepared','authorized')
            or sources['status'] in ('prepared','approved')):
        return policy_store(manager,plan).proposal(units)
    if plan['voice']['tool']=='gemini_scene':
        for shot in plan['scenes']:
            voice=voice_scene(manager,plan,shot['scene_id'])
            if not voice.root.exists():
                units.append(unit('voice:'+shot['scene_id'],voice.job['model'],TTS_ENDPOINT,VOICE_DATA,
                    payload_sha256=voice.scope['payload_sha256'],max_input_tokens=2048,max_output_tokens=1024))
    if timing and timing['status'] in ('waiting_voice','unprepared'):
        units.append(unit('timeline',MODEL,ENDPOINT,TIMELINE_DATA,max_output_tokens=4096))
    if sources['status']=='unprepared' and len(state['clips'])<len(plan['scenes']):
        units.append(unit('source',MODEL,ENDPOINT,SOURCE_DATA,input_sha256=digest(sources['scope']),
                          max_output_tokens=4096))
    return policy_store(manager,plan).proposal(units)


def policy_status(manager,plan,state):
    store=policy_store(manager,plan)
    grant=store.read('policy.json')
    if grant is None:
        offer=policy_offer(manager,plan,state)
        return dict(status='available' if offer['units'] else 'unavailable',proposal=offer,review_hash=digest(offer))
    attempts=store.attempts()
    status='active'
    if store.read('revoked.json'):
        status='revoked'
    elif datetime.fromisoformat(now())>=datetime.fromisoformat(grant['expires_at']):
        status='expired'
    elif any(not item['result'] or item['result']['status']!='completed' for item in attempts.values()):
        status='stopped'
    else:
        try:
            key,_=production_keys()
            store.active(key)
        except CompanyError:
            status='blocked'
    pending={item['id'] for item in grant['proposal']['units']} - attempts.keys()
    voice_pending=any(name.startswith('voice:') for name in pending)
    timing_pending='timeline' in pending and (state.get('timeline') or {}).get('status')=='unprepared'
    source_pending='source' in pending and state['source_assessment']['status']=='unprepared'
    return dict(status=status,proposal=grant['proposal'],used=len(attempts),expires_at=grant['expires_at'],
                can_run=bool(state['render_ready'] or voice_pending or timing_pending or source_pending),
                run_blocker=('tts_execution_disabled' if voice_pending and not state['tts_enabled'] else
                             'production_manager_execution_disabled' if (timing_pending or source_pending)
                             and not state['manager_enabled'] else None),
                attempted={key:item['result']['status'] if item['result'] else 'reserved'
                           for key,item in attempts.items()})


def delegated_call(store,key,operation,payload_hash,execute):
    reservation=store.reserve(key,operation,payload_hash)
    try:
        store.active(key)
        execute(reservation['policy_hash'], lambda:store.active(key))
    except Exception:
        store.finish(reservation,'failed_or_uncertain')
        raise
    store.finish(reservation,'completed')


def run_voice(voice,key,comparison,policy_hash,before_send):
    voice.create_scene()
    issued=now()
    evidence=dict(project=MISSION_ACCOUNT,model=voice.job['model'],tier='Free',billing='disabled',
        model_access='available',region_supported=True,paid_fallback=False,
        method='owner_operating_policy_v1',provider_quota='unknown',provider_billing='unknown',
        policy_sha256=policy_hash,delegated_payload_sha256=voice.scope['payload_sha256'],
        internal_limit=dict(requests=1,input_tokens=2048,output_tokens=1024),
        evidence_sha256=policy_hash,observation='Owner confirmed the signed private operating policy.',
        source_url='https://aistudio.google.com/',checked_at=issued,
        expires_at=(datetime.fromisoformat(issued)+timedelta(hours=1)).isoformat())
    voice.verify_key(key,comparison,evidence)
    review=voice.review(key)
    voice.approve(review['review_hash'],key,owner_confirmed=True,accept_google_data_policy=True)
    before_send()
    return voice.execute(key)


def run_worker(worker,key,policy_hash,payload_hash,before_send):
    prepared=prepare_manager_request(worker,None,dict(free=True,quota=True,docs=True),operating_policy_hash=policy_hash)
    jid=draft_id(worker)
    require(prepared['body']['payload_hash']==payload_hash,'owner_policy_scope_changed')
    worker.approve_consent(jid,digest(prepared['body']),api_key=key,owner_confirmed=True,
                           free_project_confirmed=True,google_data_policy_accepted=True)
    before_send()
    return worker.ask_ai(jid,api_key=key)


def policy_action(workflow,project,manager,plan,action,body):
    store=policy_store(manager,plan)
    key,comparison=production_keys()
    state=production_status(workflow,project)
    if action=='production-policy-approve':
        exact(body,('review_hash','confirmed'))
        require(body['confirmed'] is True,'owner_policy_required')
        return store.approve(policy_offer(manager,plan,state),body['review_hash'],key)
    exact(body,())
    require(action=='production-policy-run','invalid_request')
    grant=store.active(key)
    require(state['owner_policy']['status']=='active','owner_policy_unresolved_attempt')
    require(all(not info['attempted'] or info['status']=='audio_validated' for info in state['voices'].values())
            and (state['voice_batch'] or {}).get('status')!='stopped'
            and state['source_assessment']['status']!='stopped'
            and (state['timeline'] or {}).get('status')!='stopped','owner_policy_unresolved_attempt')
    units={item['id']:item for item in grant['proposal']['units']}
    already=store.attempts()
    pending_voices=[item for name,item in units.items() if name.startswith('voice:') and name not in already]
    require(not pending_voices or state['tts_enabled'],'tts_execution_disabled')
    for item in pending_voices:
        scene=item['id'].split(':',1)[1]
        require(re.fullmatch(r'scene-[1-9][0-9]{0,2}',scene),'owner_policy_scope_changed')
        voice=voice_scene(manager,plan,scene)
        require(not voice.root.exists() and item==unit('voice:'+scene,voice.job['model'],TTS_ENDPOINT,VOICE_DATA,
            payload_sha256=voice.scope['payload_sha256'],max_input_tokens=2048,max_output_tokens=1024),
            'owner_policy_scope_changed')
        delegated_call(store,key,item,voice.scope['payload_sha256'],
                       lambda proof,check:run_voice(voice,key,comparison,proof,check))
    state=production_status(workflow,project)
    timeline=state.get('timeline') or {}
    library=workflow.store.root/'production_source_library'
    needs_timing=timeline.get('status')=='unprepared' and 'timeline' in units
    needs_source=state['source_assessment']['status']=='unprepared' and 'source' in units
    require(not (needs_timing or needs_source) or state['manager_enabled'],'production_manager_execution_disabled')
    if needs_timing:
        from mission_production import clip_job
        job,_=clip_job(manager,plan)
        clips=job.load()['clips'] if job.root.exists() else []
        rows=[{key:value for key,value in row.items() if key!='representative_listening'}
              for row in measurements(manager,plan,clips)]
        worker=timeline_worker(manager,plan,project['representative']['constraints'],rows)
        item=unit('timeline',MODEL,ENDPOINT,TIMELINE_DATA,max_output_tokens=4096)
        require(draft_id(worker) is None,'owner_policy_scope_changed')
        wire_hash=digest(worker._payload(None))
        delegated_call(store,key,item,wire_hash,lambda proof,check:run_worker(worker,key,proof,wire_hash,check))
    if needs_source:
        worker=source_assignment(manager,plan,library)
        item=unit('source',MODEL,ENDPOINT,SOURCE_DATA,input_sha256=digest(worker.contract['input']),
                  max_output_tokens=4096)
        require(draft_id(worker) is None,'owner_policy_scope_changed')
        wire_hash=digest(worker._payload(None))
        delegated_call(store,key,item,wire_hash,lambda proof,check:run_worker(worker,key,proof,wire_hash,check))
    return production_status(workflow,project)['render_ready']
