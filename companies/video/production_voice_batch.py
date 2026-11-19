"""One representative consent over a finite list of existing exact scene requests."""
from datetime import datetime, timedelta

from autonomous_company import digest, exact, now, parse, require
from mission_production import SceneSpeechReceipts, production_keys, voice_scene
from tts_execution import TTSExecution, fresh


def state_store(manager):
    return TTSExecution(manager.root/'voice_batch')


def previous_account(manager, plan, key):
    speech=SceneSpeechReceipts(manager,plan)
    for scene in plan['scenes']:
        voice=voice_scene(manager,plan,scene['scene_id'])
        if (voice.root/'result.json').is_file() and parse(voice._read('result.json').decode())['status']=='audio_validated':
            speech.validated(scene['scene_id'])
            proof=voice._verified('account.json')
            require(proof['scope_hash']==digest(voice.scope) and proof['root']==str(voice.root)
                    and proof['credential_binding']==voice._sign(dict(scope=voice.scope_id,
                        project=voice.scope['project'],credential=key)), 'tts_account_binding')
            return proof
    require(False,'voice_batch_previous_account_required')


def batch_status(manager, plan, voices):
    if plan['voice']['tool']!='gemini_scene':
        return None
    records=state_store(manager)
    if (records.root/'review.json').is_file():
        review=records._verified('review.json')
        status='prepared'
        if (records.root/'run.json').exists():
            status='completed' if (records.root/'completed.json').exists() else 'stopped'
        elif (records.root/'approved.json').exists():
            status='approved'
        return dict(status=status,review=review,review_hash=digest(review))
    if records.root.exists():
        return dict(status='stopped')
    scenes=[s['scene_id'] for s in plan['scenes'] if s['scene_id'] not in voices]
    return dict(status='available',scenes=scenes) if scenes and any(
        info.get('status')=='audio_validated' for info in voices.values()) else None


def batch_member(manager, scene):
    store=state_store(manager)
    if not store.root.exists():
        return False
    # If preparation was interrupted before its signed review, fail closed.
    if not (store.root/'review.json').is_file():
        return True
    return any(item['scene_id']==scene for item in store._verified('review.json')['requests'])


def batch_action(manager,plan,action,body):
    require(plan['voice']['tool']=='gemini_scene','production_voice_contract')
    records=state_store(manager)
    key,project_key=production_keys()
    if action=='production-batch-prepare':
        exact(body,('free','quota','remaining_requests','remaining_input_tokens','remaining_output_tokens'))
        require(body['free'] is True and body['quota'] is True,'tts_account_evidence_required')
        prior=previous_account(manager,plan,key)
        scenes=[voice_scene(manager,plan,s['scene_id']) for s in plan['scenes']]
        voices=[v for v in scenes if not v.root.exists()]
        count=len(voices)
        require(0<count<=12 and not records.root.exists(),'voice_batch_unavailable')
        for field,minimum in (('remaining_requests',count),('remaining_input_tokens',2048*count),
                              ('remaining_output_tokens',1024*count)):
            require(type(body[field]) is int and minimum<=body[field]<=10**9,'tts_quota_evidence_required')
        issued=now()
        expires=(datetime.fromisoformat(issued)+timedelta(hours=1)).isoformat()
        evidence={**prior['evidence'],'checked_at':issued,'expires_at':expires,
                  **{key:body[key] for key in ('remaining_requests','remaining_input_tokens','remaining_output_tokens')}}
        records.root.mkdir(mode=0o700)
        requests=[]
        for voice in voices:
            voice.create_scene()
            voice.verify_key(key,project_key,evidence)
            review=voice.review(key)
            requests.append(dict(scene_id=voice.scope['scene_id'],scope=voice.scope,
                                 payload=parse(voice.raw.decode()),review_hash=review['review_hash']))
        review=dict(plan_hash=manager.contract['input']['approved_plan_hash'],direction_hash=digest(plan),
                   issued_at=issued,expires_at=expires,requests=requests,max_requests=count,max_cost_usd=0,
                   prior_attestation_hash=digest(prior))
        records._write('review.json',records._signed(review))
        return review

    review=records._verified('review.json')
    require(review['plan_hash']==manager.contract['input']['approved_plan_hash']
            and review['direction_hash']==digest(plan) and fresh(review['issued_at'],review['expires_at']),
            'voice_batch_review_invalid')
    voices=[]
    for item in review['requests']:
        voice=voice_scene(manager,plan,item['scene_id'])
        _,scope,raw=voice._load()
        require(scope==item['scope'] and parse(raw.decode())==item['payload']
                and not (voice.root/'attempt.json').exists(),'voice_batch_review_invalid')
        voices.append((item,voice))
    require(not (records.root/'run.json').exists(),'voice_batch_already_consumed')
    if action=='production-batch-consent':
        exact(body,('review_hash','policy'))
        require(body['policy'] is True and body['review_hash']==digest(review)
                and not (records.root/'approved.json').exists(),'voice_batch_review_invalid')
        for item,voice in voices:
            voice.approve(item['review_hash'],key,owner_confirmed=True,accept_google_data_policy=True)
        records._write('approved.json',records._signed(dict(review_hash=digest(review),at=now())))
        return review

    exact(body,())
    require(action=='production-batch-run' and records._verified('approved.json')['review_hash']==digest(review),
            'voice_batch_review_invalid')
    require(all(voice.execution_enabled() for _,voice in voices),'tts_execution_disabled')
    records._write('run.json',records._signed(dict(review_hash=digest(review),at=now(),retry=False)))
    for _,voice in voices:
        voice.execute(key)
    records._write('completed.json',records._signed(dict(review_hash=digest(review),at=now())))
