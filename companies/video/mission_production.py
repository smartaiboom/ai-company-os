"""Mission production over one-call consent, scene TTS and offline clip import."""
import hmac
import os
from pathlib import Path

from autonomous_company import CompanyError, digest, exact, now, parse, require
from autonomous_gemini35 import ENDPOINT, MODEL, Gemini35Config
from goal_dialogue import safe_text
from goal_dialogue_live import OneCallAcceptanceStore
from manager_plan_once import ManagerPlanAcceptanceStore, canonical_bytes
from role_json_schema import S, arr, enum, obj
from video_mission_one import MISSION_ACCOUNT
from video_production_company import approved_portrait_direction, offline_clip_decision_context
from tts_execution import GeminiTTSAdapter, TTSExecution
from tts_job import ENDPOINT as TTS_ENDPOINT, MODELS, private_write, sha

SCHEMA = obj(
    voice=obj(tool=enum('gemini_scene','melo_local','hold'), model=enum(*MODELS,'local','none'),
              voice=enum('Puck','Kore','local','none'), rationale=S),
    fit=enum('letterbox'), timeline=S, review_criteria=arr(S), work_order=arr(S),
    scenes=arr(obj(scene_id=S, source=enum('operator_clip','hold'), request=S, direction=S,
                   transition=enum('cut'), speech_style=S)),
)


class ProductionManager(ManagerPlanAcceptanceStore):
    marker_name = '.mission-production-manager-v1'
    acceptance_scope = 'mission_production_manager_once_v1'
    acceptance_project = MISSION_ACCOUNT

    def __init__(self, root, contract):
        self.contract = contract
        super().__init__(root)

    def _authorize_transport(self, p, api_key):
        config=Gemini35Config.from_env()
        require(os.getenv('GEMINI35_AUTONOMOUS_FREE_ENABLED')=='1'
                and (config.model, config.endpoint)==(MODEL,ENDPOINT), 'production_manager_execution_disabled')
        OneCallAcceptanceStore._authorize_transport(self,p,api_key)

    def validate_plan(self, value):
        inputs=self.contract['input']
        require([s['scene_id'] for s in value['scenes']]==[s['scene_id'] for s in inputs['storyboard']],
                'production_scene_mismatch')
        voice=value['voice']
        tool=voice['tool']
        require((tool=='gemini_scene' and voice['model'] in MODELS and voice['voice'] in ('Puck','Kore'))
                or (tool=='melo_local' and voice['model']==voice['voice']=='local')
                or (tool=='hold' and voice['model']==voice['voice']=='none'),'production_voice_contract')
        require(tool!='melo_local' or inputs['tools']['melo_installed'],'melo_runtime_missing')
        require(1<=len(value['review_criteria'])<=8 and 1<=len(value['work_order'])<=8,
                'production_plan_incomplete')
        for text in [value['timeline'],voice['rationale'],*value['review_criteria'],*value['work_order']]:
            safe_text(text,600)
        for scene in value['scenes']:
            for field in ('request','direction','speech_style'):
                safe_text(scene[field],600)


class SceneVoice(TTSExecution):
    scope_id='mission_production_scene_tts_once_v1'

    def __init__(self, root, plan_hash, direction_hash, scene, selected, text):
        super().__init__(root)
        self.job=dict(model=selected['model'],voice=selected['voice'],max_seconds=min(20,scene['end']-scene['start']),
                      max_response_bytes=2000000)
        require(self.job['model'] in MODELS and self.job['voice'] in ('Puck','Kore'),'tts_model_voice_policy')
        require(len(text.encode())<=1000,'tts_input_limit')
        self.job['payload']=dict(model=self.job['model'], input=[dict(type='user_input',content=[dict(
            type='text',text=text,annotations=[dict(type='speech_metadata',style=scene['speech_style'])])])],
            response_format=dict(type='audio',mime_type='audio/wav',sample_rate=24000),
            generation_config=dict(speech_config=[dict(voice=self.job['voice'])]))
        self.raw=canonical_bytes(GeminiTTSAdapter.payload(self.job))
        self.scope=dict(scope=self.scope_id,project=MISSION_ACCOUNT,plan_hash=plan_hash,direction_hash=direction_hash,
            scene_id=scene['scene_id'],model=self.job['model'],endpoint=TTS_ENDPOINT,voice=self.job['voice'],
            text_sha256=sha(text.encode()),payload_sha256=sha(self.raw),output=str(self.root/'B_gemini.wav'),
            requests=1,max_cost_usd=0,store=False,max_output_tokens=1024,local_max_seconds=self.job['max_seconds'],
            local_max_response_bytes=2000000,quality='unassessed',publish_ready=False,
            google_unpaid_data_policy='inputs_and_outputs_may_be_used_for_improvement_and_human_review',
            automatic_retry=False)

    def create_scene(self):
        self.root.mkdir(mode=0o700,parents=True,exist_ok=False)
        self._write('scope.json',self.scope)
        private_write(self.root/'payload.json',self.raw)

    def _load(self):
        require(parse(self._read('scope.json').decode())==self.scope and self._read('payload.json')==self.raw,
                'tts_scope_changed')
        return self.job,self.scope,self.raw

    def execution_enabled(self):
        return os.getenv('GEMINI_PRODUCTION_TTS_ENABLED')=='1'


def production_keys():
    key=os.environ.get('GEMINI_API_KEY','')
    independent=os.environ.get('GEMINI_PRODUCTION_PROJECT_API_KEY','')
    require(bool(key and independent) and hmac.compare_digest(key,independent),'production_project_key_unverified')
    return key,independent


def production_manager(workflow, project):
    from local_melo_tts import MeloLocal
    flow=project['representative']
    require(flow['stage']=='video_revision','production_revision_required')
    plan=flow['plan_versions'][-1]
    workflow.mission_production_spec(flow,plan['version'],plan['sha256'],'none')
    prior=flow['video_versions'][-1]
    require((prior['render_receipt'].get('visual_scope')=='local_procedural_cards_no_game_footage'
             or prior['render_receipt'].get('visual_scope')=='imported_operator_clips')
            and prior['plan_sha256']==plan['sha256'],'production_preview_required')
    decision=flow['decisions'][-1]
    require(decision['stage']=='video' and decision['action']=='request_revision'
            and not decision['changes_plan'] and decision['sha256']==prior['sha256'],
            'production_revision_required')
    storyboard=next(parse(t['versions'][-1]['content']) for t in plan['task_history'] if t['role']=='editor')
    inputs=approved_portrait_direction(project,plan,storyboard)
    inputs.update(approved_plan_hash=plan['sha256'],preview_hash=prior['sha256'],revision_feedback=decision['feedback'],
        tools=dict(melo_installed=MeloLocal().available(),clips=offline_clip_decision_context(),
                   tts_models=list(MODELS),tts_voices=['Puck','Kore'],tts_mode='exact scene text only; consent per scene',
                   current_free_quota='owner verification required', supported_transition='cut'))
    if prior['render_receipt'].get('visual_scope')=='local_procedural_cards_no_game_footage':
        inputs['representative_quality_note']='무음 카드 기술 시안 품질에 대한 대표 평가와 개선 목표. 세부 점수 미제공.'
    inputs['storyboard']=[{**s,'scene_id':f'scene-{i}'} for i,s in enumerate(inputs['storyboard'],1)]
    contract=dict(input=inputs,schema=SCHEMA,system=(
        'You are the AI video production manager. Return only the JSON schema. Preserve approved narration and scene order. '
        'Choose a voice tool, candidate and Korean performance style appropriate for this audience; prior listening scores '
        'are for other content and do not certify this video. Compare local and signed per-scene TTS, or hold. '
        'For each scene give concrete matching clip requirements, framing/direction and speech style. '
        'Only operator-provided clips and cut transitions can run. Request rights and enough unique footage for each scene. '
        'Search metadata is not footage or a license. No downloads, automatic generation, or repeat are available. '
        'Explain timing and listening/viewing checks, owner/worker sequence and blockers. Never claim to have heard or watched media.'))
    root=workflow.store.root/'production_direction'/project['id']/digest(dict(plan=plan['sha256'],revision=decision))
    require(not any(p.is_symlink() for p in (root,root.parent,root.parent.parent)), 'invalid_acceptance_path')
    return ProductionManager(root,contract)


def draft_id(manager):
    drafts=[p.stem for p in manager.root.glob('dialogue-*.json') if '.' not in p.stem]
    require(len(drafts)<=1,'production_duplicate_draft')
    return drafts[0] if drafts else None


def voice_scene(manager, result, scene_id):
    scenes=dict((s['scene_id'],s) for s in result['scenes'])
    inputs=dict((s['scene_id'],s) for s in manager.contract['input']['storyboard'])
    require(scene_id in scenes and scene_id in inputs and result['voice']['tool']=='gemini_scene',
            'production_voice_contract')
    source=inputs[scene_id]
    return SceneVoice(manager.root/'voice'/scene_id,manager.contract['input']['approved_plan_hash'],
                      digest(result),{**source,'speech_style':scenes[scene_id]['speech_style']},
                      result['voice'],source['narration'])


def approved_manager_result(manager):
    jid=draft_id(manager)
    require(jid is not None, 'production_manager_missing')
    draft=manager.load(jid)
    attempts=draft['real_ai']['attempts']
    result=draft.get('manager_plan')
    require(draft['status']=='needs_user_review' and len(attempts)==1
            and len(draft['grants'])==1
            and attempts[0]['status']=='completed' and result is not None
            and attempts[0]['response_hash']==digest(result)
            and attempts[0]['payload_hash']==digest(manager._payload(draft)),
            'production_manager_unverified')
    grant=draft['grants'][0]
    record=grant['record']
    body=record['body']
    require(hmac.compare_digest(grant['signature'],manager._sign(record))
            and record['owner_confirmed'] is True and record['free_project_confirmed'] is True
            and body['draft_id']==draft['id'] and body['id']==attempts[0]['grant_id']
            and body['calls']==body['total_limit']==1 and body['payload_hash']==attempts[0]['payload_hash'],
            'production_manager_unverified')
    manager.validate_plan(result)
    return result


def clip_job(manager, result):
    from ai_clip_pipeline import ClipJob
    inputs=manager.contract['input']
    job=ClipJob(manager.root/'clips')
    spec=dict(goal=inputs['goal'],decision_source='gemini_manager_'+digest(result),
              total_seconds=inputs['duration'],fit=result['fit'],allow_repeat=False,scenes=[],approved_timeline=[])
    for source,decision in zip(inputs['storyboard'],result['scenes']):
        if decision['source']!='operator_clip':
            raise CompanyError('production_waiting_for_source_plan')
        spec['scenes'].append(dict(id=source['scene_id'],request=dict(prompt=decision['request'],
            aspect_ratio='9:16',duration_target=source['end']-source['start'],reference_image=None),
            utterances=[source['narration']]))
        spec['approved_timeline'].append(dict(start=source['start'],end=source['end'],caption=source['caption']))
    if job.root.exists():
        require(job.load()['plan']==spec,'production_clip_plan_changed')
    return job,spec


def import_operator_clip(manager,result,scene_id,filename,rights):
    from pathlib import PurePath
    require(isinstance(filename,str) and PurePath(filename).name==filename and '/' not in filename
            and '\\' not in filename and filename.lower().endswith('.mp4'),'invalid_source_path')
    safe_text(rights,600)
    inbox=manager.root/'inbox'
    require(inbox.is_dir() and not inbox.is_symlink(),'production_inbox_missing')
    job,spec=clip_job(manager,result)
    if not job.root.exists():job.create(spec)
    source=dict(provider='operator_provided',provenance=dict(kind='operator_provided_clip',evidence=rights),
        generated_at=None,license='operator attested for local review',terms_url='local owner declaration',
        usage_rights='local review only',commercial_use='unknown',allowed_to_publish=False,watermark='unknown',
        rights_verified=False,rights_evidence=rights,estimated_cost=None,actual_cost=None)
    return job.import_generated_clip(inbox,filename,scene_id,source)


class SceneSpeechReceipts:
    def __init__(self,manager,result):
        self.manager=manager
        self.result=result

    def validated(self,scene_id):
        from local_melo_tts import file_hash
        voice=voice_scene(self.manager,self.result,scene_id)
        _,scope,_=voice._load()
        result=parse(voice._read('result.json').decode())
        attempt=parse(voice._read('attempt.json').decode())
        consent=voice._verified('consent.json')
        path=Path(scope['output'])
        require(result.get('status')=='audio_validated' and result.get('decoded') is True
                and attempt['scope_hash']==digest(scope) and attempt['consent_hash']==digest(consent)
                and attempt['payload_sha256']==scope['payload_sha256']
                and attempt.get('status')=='reserved_consumed'
                and not path.is_symlink() and file_hash(path)==result['audio_sha256'],
                'production_voice_receipt_changed')
        return path,result

    def synthesize(self,texts,folder):
        import wave
        from local_artifacts import run_command
        from local_melo_tts import file_hash
        utterances=[]
        for scene,text in zip(self.manager.contract['input']['storyboard'],texts,strict=True):
            require(scene['narration']==text,'narration_speech_text_mismatch')
            path,result=self.validated(scene['scene_id'])
            dest=folder/(scene['scene_id']+'.wav')
            run_command(['ffmpeg','-nostdin','-v','error','-protocol_whitelist','file,pipe','-i',str(path),
                         '-ar','44100','-ac','1','-c:a','pcm_s16le',str(dest)],stage='ffmpeg_segment')
            with wave.open(str(dest),'rb') as wav:
                duration=wav.getnframes()/44100
            utterances.append(dict(file=dest.name,text=text,spoken_text=text,duration=duration,
                sha256=file_hash(dest),source_audio_sha256=result['audio_sha256']))
        return dict(engine='gemini_scene_receipt',utterances=utterances)


def imported_preview_inputs(workflow,project):
    from local_melo_tts import MeloLocal
    manager=production_manager(workflow,project)
    result=approved_manager_result(manager)
    job,spec=clip_job(manager,result)
    require(job.root.is_dir(),'pending_external_clip')
    state=job.load()
    require(len(state['clips'])==len(spec['scenes']),'pending_external_clip')
    require(all(c['source']['provenance']['kind']=='operator_provided_clip' for c in state['clips']),
            'invalid_provenance')
    tool=result['voice']['tool']
    if tool=='gemini_scene':
        speech=SceneSpeechReceipts(manager,result)
        for scene in result['scenes']:speech.validated(scene['scene_id'])
    else:
        speech=MeloLocal()
        require(tool=='melo_local' and speech.available(),'production_voice_unavailable')
    return job,speech,dict(plan=spec,clips=[c['sha256'] for c in state['clips']],direction_hash=digest(result))


def render_imported(job,speech,spec,folder):
    import json
    import shutil
    from local_artifacts import run_command
    from local_melo_tts import file_hash
    from production_video import portrait_font
    media=job.render(synthesizer=speech)
    require(media['audio'] and media['decoded'] and not media['synthetic_test_fixture'],
            'production_media_unverified')
    shutil.copyfile(job.root/media['file'],folder/'video.mp4')
    require(file_hash(folder/'video.mp4')==media['sha256'],'representative_artifact_changed')
    review=[]
    timing=parse((job.root/'timeline.json').read_text())
    for i,scene in enumerate(timing['scenes']):
        frame=f'keyframe-{i:02}.png'
        shutil.copyfile(job.root/frame,folder/frame)
        review.append(dict(scene_index=i,keyframe=frame,keyframe_sha256=file_hash(folder/frame),
            start_seconds=scene['start'],end_seconds=scene['end'],narration_duration_seconds=scene['speech_seconds']))
        samples=[]
        for fraction in (.2,.5,.8):
            position=scene['start']+(scene['end']-scene['start'])*fraction
            pixels=run_command(['ffmpeg','-nostdin','-v','error','-ss',str(position),'-i',str(folder/'video.mp4'),
                '-frames:v','1','-vf','scale=32:32,format=gray','-threads','1','-f','rawvideo','pipe:1'],
                stage='ffmpeg_decode')
            require(len(pixels)==1024,'production_motion_sample_missing')
            samples.append(sha(pixels))
        review[-1]['distinct_sampled_frames']=len(set(samples))
    # Asset metadata, review timing and subtitle file remain verifiable local artifacts.
    metadata=folder/'production-evidence.json'
    metadata.write_text(json.dumps(dict(timing=timing,source_receipts=media['source_receipts']),ensure_ascii=False))
    shutil.copyfile(job.root/'captions.srt',folder/'captions.srt')
    receipt=dict(tool='approved_imported_portrait_v1',at=now(),input_hash=digest(spec),sha256=media['sha256'],
        duration_seconds=media['duration'],width=720,height=1280,audio=True,decoded=True,audio_mode='local_speech',
        voice_engine=media['audio_engine'],visual_scope='imported_operator_clips',subtitle_sync='measured_scene_audio',
        technical_quality=dict(unique_clip_hashes=len({c['sha256'] for c in media['source_receipts']}),
            repeats=sum(scene['repeat_count'] for scene in timing['scenes']),
            caption_chars_per_second=[round(len(c['text'].replace('\n',''))/(c['end']-c['start']),2)
                                      for c in timing['captions']], perceptual_quality='unassessed'),
        font_license=portrait_font()[1],review_material=review,natural_korean_voice_verified=False,
        source_licenses=[dict(file=name,sha256=file_hash(folder/name),creator='로컬 제작 도구',
                             license='소스 사용권은 제공자 진술 · 게시 미승인')
                         for name in ('production-evidence.json','captions.srt')])
    (folder/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False))
    return receipt


def production_status(workflow,project):
    try:
        manager=production_manager(workflow,project)
    except CompanyError:
        return None
    jid=draft_id(manager)
    config=Gemini35Config.from_env()
    result=dict(status='unprepared',scope=manager.contract['input'],attempts=0,plan=None,
                manager_enabled=os.getenv('GEMINI35_AUTONOMOUS_FREE_ENABLED')=='1'
                and (config.model,config.endpoint)==(MODEL,ENDPOINT),
                tts_enabled=os.getenv('GEMINI_PRODUCTION_TTS_ENABLED')=='1',
                key_ready=False,key_setup='missing_runtime_key',render_ready=False,clips=[],voices={})
    if os.getenv('GEMINI_API_KEY'):
        result['key_setup']='mismatch' if os.getenv('GEMINI_PRODUCTION_PROJECT_API_KEY') else 'missing_comparison_key'
    try:
        production_keys()
        result.update(key_ready=True,key_setup='ready')
    except CompanyError:
        pass
    if jid is None:
        return result
    draft=manager.load(jid)
    attempts=draft['real_ai']['attempts']
    result['attempts']=len(attempts)
    if attempts:
        result['manager_attempt']=attempts[-1]['status']
    result['status']='stopped' if attempts else 'approved' if draft['grants'] else 'prepared'
    proposal=manager._proposal_path(jid)
    if proposal.is_file():
        body=parse(proposal.read_text())
        result['review_hash']=digest(body)
        result['expires_at']=body['expires_at']
    if draft['status']!='needs_user_review':
        return result
    plan=approved_manager_result(manager)
    result.update(status='waiting_assets',plan=plan,inbox=str(manager.root/'inbox'))
    if plan['voice']['tool']=='gemini_scene':
        for scene in plan['scenes']:
            voice=voice_scene(manager,plan,scene['scene_id'])
            if not voice.root.exists():
                continue
            info=dict(consent=(voice.root/'consent.json').is_file(),
                      attempted=(voice.root/'attempt.json').is_file(),
                      payload_sha256=voice.scope['payload_sha256'],
                      payload=parse(voice.raw.decode()),review_hash=None)
            if (voice.root/'review.json').is_file():
                review=voice._verified('review.json')
                info.update(review_hash=digest(review),expires_at=review['expires_at'])
            if (voice.root/'result.json').is_file():
                info['status']=parse(voice._read('result.json').decode()).get('status')
            result['voices'][scene['scene_id']]=info
    try:
        job,_=clip_job(manager,plan)
        if job.root.exists():
            clip_state=job.load()
            result['clips']=[c['scene_id'] for c in clip_state['clips']]
            if not clip_state['attempts']:
                imported_preview_inputs(workflow,project)
                result['render_ready']=True
            else:
                result['render_attempt']=clip_state['attempts'][-1]['status']
    except CompanyError as exc:
        result['render_blocker']=exc.code
    except FileNotFoundError:
        result['render_blocker']='pending_external_clip'
    return result


def production_action(workflow,pid,action,body):
    """Explicit owner operations. The representative project remains bound under its lock."""
    with workflow.store.lock(pid):
        project=workflow.store.load(pid)
        manager=production_manager(workflow,project)
        jid=draft_id(manager)
        if action=='production-plan-prepare':
            exact(body,('free','quota','docs'))
            require(all(body[k] is True for k in body),'current_docs_and_quota_confirmation_required')
            key,independent=production_keys()
            if jid is None:
                manager.root.mkdir(mode=0o700,parents=True,exist_ok=True)
                jid=manager.create()['id']
            current=manager.load(jid)
            require(not current['grants'] and not current['real_ai']['attempts'],'consent_replay')
            manager.verify_project_key(jid,api_key=key,project_api_key=independent,project=MISSION_ACCOUNT,
                free_tier_confirmed=True,billing_disabled=True,quota_available=True,official_docs_reviewed=True)
            return manager.prepare_consent(jid)
        require(jid is not None,'production_manager_missing')
        if action=='production-plan-consent':
            exact(body,('review_hash','free','policy'))
            key,_=production_keys()
            return manager.approve_consent(jid,body['review_hash'],api_key=key,owner_confirmed=True,
                    free_project_confirmed=body['free'],google_data_policy_accepted=body['policy'])
        if action=='production-plan-run':
            exact(body,())
            key,_=production_keys()
            result=manager.ask_ai(jid,api_key=key)
            (manager.root/'inbox').mkdir(mode=0o700,exist_ok=True)
            return result
        result=approved_manager_result(manager)
        if action=='production-clip-import':
            exact(body,('scene','filename','rights','confirmed'))
            require(body['confirmed'] is True,'production_rights_confirmation_required')
            return import_operator_clip(manager,result,body['scene'],body['filename'],body['rights'])
        require(isinstance(body,dict) and isinstance(body.get('scene'),str),'production_scene_mismatch')
        voice=voice_scene(manager,result,body['scene'])
        key,independent=production_keys()
        if action=='production-voice-prepare':
            exact(body,('scene','evidence','free','quota'))
            require(body['free'] is True and body['quota'] is True,'tts_account_evidence_required')
            safe_text(body['evidence'],300)
            require(len(body['evidence'].strip())>=20,'tts_account_observation_required')
            require(key not in body['evidence'],'tts_secret_in_evidence')
            require(not voice.root.exists(),'tts_attempt_already_prepared')
            voice.create_scene()
            from datetime import datetime, timedelta
            checked=now()
            evidence=dict(project=MISSION_ACCOUNT,model=voice.job['model'],tier='Free',billing='disabled',
                model_access='available',region_supported=True,paid_fallback=False,remaining_requests=1,
                remaining_input_tokens=2048,remaining_output_tokens=1024,checked_at=checked,
                expires_at=(datetime.fromisoformat(checked)+timedelta(hours=1)).isoformat(),
                method='owner_aistudio_review_not_independent_verification',evidence_sha256=digest(body['evidence']),
                source_url='https://aistudio.google.com/',observation=body['evidence'])
            voice.verify_key(key,independent,evidence)
            return voice.review(key)
        if action=='production-voice-consent':
            exact(body,('scene','review_hash','policy'))
            return voice.approve(body['review_hash'],key,owner_confirmed=True,accept_google_data_policy=body['policy'])
        require(action=='production-voice-run','invalid_request')
        exact(body,('scene',))
        require(not (voice.root/'attempt.json').exists(),'tts_attempt_already_consumed')
        return voice.execute(key)
