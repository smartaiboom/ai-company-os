"""One separately approved editing assignment and rights-scoped media acquisition."""
from datetime import datetime
from tempfile import TemporaryDirectory

from ai_clip_pipeline import validate_editing
from autonomous_company import CompanyError, digest, exact, now, parse, require
from autonomous_gemini35 import ENDPOINT, MODEL
from goal_dialogue import safe_text
from measured_timeline import approved_clip_timeline, measurements
from mission_production import (ProductionManager, approved_manager_result, canonical_bytes, clip_job,
                                draft_id, production_keys)
from official_media import MAX_BYTES, download_mp4, registered_media
from owner_operating_policy import OwnerOperatingPolicy
from production_operating import delegated_call, run_worker, unit
from production_sources import library_entries
from role_json_schema import S, arr, enum, obj
from tts_job import private_write


SCHEMA=obj(action=enum('edit','hold'), review_criteria=S, scenes=arr(obj(scene_id=S,asset_id=S,
    in_frame={'type':'integer'},framing=enum('letterbox_center','letterbox_top'),
    transition=enum('cut'),caption_position=enum('safe_lower','safe_upper'),suitability=S)))
SYSTEM=(
    '당신은 영상 편집 직원입니다. JSON과 한국어 설명만 사용하고 ID는 원문으로 보존합니다. '
    '기존 승인 장면·자막 원문·순서와 실측 음성은 고정입니다. 권리가 등록된 후보 ID를 한 장면에 하나씩 사용하고 '
    '같은 후보를 반복하지 마세요. 이미 인수한 장면에는 그 후보만 사용하세요. 24fps 기준 구간 시작 프레임을 선택하고 '
    '장면 전체에 충분한 길이인지 확인하세요. 길이가 확인되지 않은 로컬 후보는 in_frame=0으로 제안하세요. '
    '허용 도구는 중앙·상단 레터박스, 컷 전환, 상·하단 자막뿐입니다. 이전 기술 시안의 카드와 반복 화면, '
    '음성과 화면이 어긋나는 장면을 피하되 이전 다른 주제의 품질 평가를 이 영상 평가로 사용하지 마세요. '
    '후크, 맥락·자막 배치, 실제 장면 변화 및 음성 대응을 사람에게 확인할 근거를 제시하세요. 직접 시청·청취하지 않았습니다. '
    '길이·권리·내용을 종합할 때 적합한 후보가 부족하면 hold와 빈 배열을 반환하세요. '
    '다운로드 주소, 검색 요청, 새 라이선스 주장, 소스 생성은 반환하지 마세요.'
)


def extension_store(manager, plan):
    inputs=manager.contract['input']
    return OwnerOperatingPolicy(manager.root/'asset_extension',dict(mode='cutroom_asset_editing_v1',
        project=manager.acceptance_project,provider='Google Gemini and registered official HTTPS publishers',
        plan_sha256=inputs['approved_plan_hash'],direction_sha256=digest(plan),revision_scope=manager.root.name))


def registries(root):
    library=root/'production_source_library'
    return library,library_entries(library),registered_media(root/'production_official_media')


def edit_context(manager, plan, constraints, clips, libraries, offices, source_result):
    _,base=clip_job(manager,plan)
    spec,timeline_hash=approved_clip_timeline(manager,plan,constraints,clips,base)
    lengths=[round((row['end']-row['start'])*24) for row in spec['approved_timeline']]
    candidates={}
    for name,item in libraries.items():
        candidates['local:'+name]=dict(description=item['description'],frames=None,asset_hash=digest(item),
                                       content_sha256=item['sha256'],route=item['origin'])
    for name,item in offices.items():
        candidates['official:'+name]=dict(description=item['description'],frames=item['duration_frames'],
                                          asset_hash=digest(item),content_sha256=item['sha256'],route='official_direct_media')
    for clip in clips:
        candidates['existing:'+clip['scene_id']]=dict(description='Previously verified import for this scene',
            frames=int(clip['media']['duration']*24),asset_hash=clip['sha256'],content_sha256=clip['sha256'],
            for_scene=clip['scene_id'],route='existing')
    rows=measurements(manager,plan,clips)
    scenes=[]
    for shot,length,row,direction in zip(manager.contract['input']['storyboard'],lengths,rows,plan['scenes'],strict=True):
        require(row['min_frames']<=length,'narration_exceeds_scene')
        scenes.append(dict(scene_id=shot['scene_id'],narration=shot['narration'],caption=shot['caption'],frames=length,
                          narration_seconds=row['seconds'],narration_sha256=row['audio_sha256'],scene_goal=direction['request']))
    return dict(goal=manager.contract['input']['goal'],plan_sha256=manager.contract['input']['approved_plan_hash'],
                direction_sha256=digest(plan),timeline_sha256=timeline_hash,scenes=scenes,candidates=candidates,
                previous_source_assessment=source_result,
                known_quality_issue='Procedural card preview and distractingly repeated imagery are unsuitable as gameplay evidence.')


class AssetEditor(ProductionManager):
    marker_name='.cutroom-asset-editing-v1'
    acceptance_scope='cutroom_asset_editing_once_v1'

    def freeze_contract(self):
        file=self.root/'inputs.json'
        if not file.exists():
            private_write(file,canonical_bytes(self.contract['input']))

    def validate_plan(self,value):
        safe_text(value['review_criteria'],1000)
        choices=value['scenes']
        if value['action']=='hold':
            require(not choices,'invalid_source_edit')
            return
        inputs=self.contract['input']
        by_scene={item.get('for_scene'):name for name,item in inputs['candidates'].items() if 'for_scene' in item}
        require([c['scene_id'] for c in choices]==[s['scene_id'] for s in inputs['scenes']]
                and len({c['asset_id'] for c in choices})==len(choices),'invalid_source_edit')
        hashes=set()
        for choice,scene in zip(choices,inputs['scenes'],strict=True):
            item=inputs['candidates'].get(choice['asset_id'])
            start=choice['in_frame']
            safe_text(choice['suitability'],700)
            require(item is not None and 0<=start
                    and (scene['scene_id'] not in by_scene or choice['asset_id']==by_scene[scene['scene_id']])
                    and item.get('for_scene',scene['scene_id'])==scene['scene_id']
                    and (start==0 if item['frames'] is None else start+scene['frames']<=item['frames']),
                    'invalid_source_edit')
            sha=item.get('content_sha256')
            if sha:
                require(sha not in hashes,'invalid_source_edit')
                hashes.add(sha)


def editor(manager, context=None):
    root=manager.root/'asset_editor'
    file=root/'inputs.json'
    require(not root.is_symlink() and not file.is_symlink(),'invalid_acceptance_path')
    if file.exists():
        require(file.is_file() and file.stat().st_size<=65536,'invalid_source_edit')
        context=parse(file.read_text())
    require(context is not None,'asset_edit_missing')
    return AssetEditor(root,dict(input=context,system=SYSTEM,schema=SCHEMA))


def transfer_unit(name, asset):
    return unit('download:'+name,'direct_https_get',asset['url'],['request_url','connection_metadata'],
                payload_sha256=digest(dict(method='GET',url=asset['url'])),rights_sha256=digest(asset),
                max_bytes=MAX_BYTES,publisher=asset['issuer'])


def offer(manager,plan,root,constraints,clips,state):
    if plan['voice']['tool']!='gemini_scene' or (state.get('timeline') or {}).get('status') not in ('approved','original_fits'):
        return dict(status='waiting_audio')
    try:
        _,libraries,offices=registries(root)
        context=edit_context(manager,plan,constraints,clips,libraries,offices,state['source_assessment'].get('result'))
    except (CompanyError,OSError,ValueError):
        return dict(status='registry_blocked')
    missing=len(plan['scenes'])-len(clips)
    if len(libraries)+len(offices)<missing:
        return dict(status='waiting_rights',local=len(libraries),official=len(offices),missing=missing)
    worker=editor(manager,context)
    units=[unit('editor',MODEL,ENDPOINT,['approved_storyboard','timing_and_voice_hashes','asset_descriptions_and_hashes',
            'existing_source_assignment'],payload_sha256=digest(worker._payload(None)),max_output_tokens=4096)]
    units.extend(transfer_unit(name,asset) for name,asset in sorted(offices.items()))
    store=extension_store(manager,plan)
    proposal=store.proposal(units)
    proposal.update(max_downloads=min(missing,len(offices)),rights_review=list(offices.values()),
                    local_entries=[{k:item[k] for k in ('id','description','origin','rights','sha256')} for item in libraries.values()])
    return dict(status='available',proposal=proposal,review_hash=digest(proposal),local=len(libraries),official=len(offices))


def edit_status(manager,plan,root,constraints,clips,state):
    store=extension_store(manager,plan)
    grant=store.read('policy.json')
    if grant is None:
        return offer(manager,plan,root,constraints,clips,state)
    ledger=store.attempts()
    outcome=dict(status='active',used=len(ledger),expires_at=grant['expires_at'],proposal=grant['proposal'])
    if store.read('revoked.json'):
        outcome['status']='revoked'
    elif datetime.fromisoformat(now())>=datetime.fromisoformat(grant['expires_at']):
        outcome['status']='expired'
    elif (any(not row['result'] or row['result']['status']!='completed' for row in ledger.values())
          or any(not store.read('local-completed-'+p.name.removeprefix('local-start-'))
                 for p in store.root.glob('local-start-*.json'))):
        outcome['status']='stopped'
    if ((ledger.get('editor') or {}).get('result') or {}).get('status')=='completed':
        decision=approved_manager_result(editor(manager))
        outcome['decision']=decision
        if decision['action']=='hold':
            outcome['status']='hold' if outcome['status']=='active' else outcome['status']
    return outcome


def import_selected(job,root,name,scene,source_hash,row,minimum_duration,receipt=None):
    rights=row.get('rights',row.get('rights_evidence'))
    source=dict(provider='official_direct_https' if receipt else 'local_library',provenance=dict(
        kind='operator_provided_clip',evidence='registered rights record '+digest(row)),
        generated_at=None,license='registered for local edit review',terms_url=row.get('terms_url','local declaration'),
        usage_rights='local edit and review only',commercial_use='unknown',allowed_to_publish=False,watermark='unknown',
        rights_verified=False,rights_evidence=rights,estimated_cost=0,actual_cost=None)
    return job.import_generated_clip(root,name,scene,source,expected_sha256=source_hash,
                                     minimum_duration=minimum_duration,direct_mp4=receipt is not None)


def perform_extension(workflow,project,manager,plan,state,action,body):
    store=extension_store(manager,plan)
    key,_=production_keys()
    root=workflow.store.root
    constraints=project['representative']['constraints']
    job,base=clip_job(manager,plan)
    clips=job.load()['clips'] if job.root.exists() else []
    if action=='production-assets-approve':
        exact(body,('review_hash','confirmed'))
        candidate=offer(manager,plan,root,constraints,clips,state)
        require(body['confirmed'] is True and candidate['status']=='available','asset_extension_not_ready')
        return store.approve(candidate['proposal'],body['review_hash'],key)
    exact(body,())
    require(action=='production-policy-run','invalid_request')
    grant=store.active(key)
    ledger=store.attempts()
    require(state['asset_execution']['status'] in ('active','hold')
            and all(item['result'] and item['result']['status']=='completed' for item in ledger.values()),
            'owner_policy_unresolved_attempt')
    library,libraries,offices=registries(root)
    if 'editor' not in ledger:
        context=edit_context(manager,plan,constraints,clips,libraries,offices,state['source_assessment'].get('result'))
        worker=editor(manager,context)
        wire=digest(worker._payload(None))
        require(state['manager_enabled'] and draft_id(worker) is None,'asset_extension_not_ready')
        item=unit('editor',MODEL,ENDPOINT,['approved_storyboard','timing_and_voice_hashes','asset_descriptions_and_hashes',
            'existing_source_assignment'],payload_sha256=wire,max_output_tokens=4096)
        delegated_call(store,key,item,wire,lambda proof,check:run_worker(worker,key,proof,wire,check))
    worker=editor(manager)
    decision=approved_manager_result(worker)
    if decision['action']=='hold':
        return False
    catalog=worker.contract['input']['candidates']
    selected=decision['scenes']
    require(sum(s['asset_id'].startswith('official:') for s in selected)<=grant['proposal']['max_downloads'],
            'owner_policy_scope_changed')
    current={clip['scene_id']:clip for clip in clips}
    scene_frames={item['scene_id']:item['frames'] for item in worker.contract['input']['scenes']}
    for choice in selected:
        store.active(key)
        scene,name=choice['scene_id'],choice['asset_id']
        if scene in current:
            continue
        route,asset_id=name.split(':',1)
        minimum_duration=(choice['in_frame']+scene_frames[scene])/24
        row=(offices if route=='official' else libraries).get(asset_id)
        require(row is not None and digest(row)==catalog[name]['asset_hash'],'production_source_asset_changed')
        if not job.root.exists():
            job.create(base)
        if route=='local':
            suffix=digest(scene)+'.json'
            store.write('local-start-'+suffix,dict(scene_id=scene,asset=name,sha256=row['sha256'],at=now()))
            try:
                import_selected(job,library,row['file'],scene,row['sha256'],row,minimum_duration)
            except Exception:
                store.write('local-failed-'+suffix,dict(scene_id=scene,asset=name,status='failed_or_uncertain',at=now()))
                raise
            store.write('local-completed-'+suffix,dict(scene_id=scene,asset=name,sha256=row['sha256'],at=now()))
        else:
            require(route=='official','invalid_source_edit')
            item=transfer_unit(asset_id,row)
            def download(proof,check):
                with TemporaryDirectory(dir=store.root) as directory:
                    from pathlib import Path
                    folder=Path(directory)
                    check()
                    receipt=download_mp4(row,folder/'asset.mp4')
                    store.write('download-'+asset_id+'.json',dict(policy_sha256=proof,asset=name,scene_id=scene,
                        rights_sha256=digest(row),url=row['url'],terms_url=row['terms_url'],at=now(),**receipt))
                    import_selected(job,folder,'asset.mp4',scene,receipt['sha256'],row,minimum_duration,receipt)
            delegated_call(store,key,item,item['payload_sha256'],download)
    return True


def editing_handoff(manager,plan,clips,spec):
    store=extension_store(manager,plan)
    if not store.read('policy.json'):
        return None
    ledger=store.attempts()
    require(ledger and all(item['result'] and item['result']['status']=='completed' for item in ledger.values())
            and all(store.read('local-completed-'+p.name.removeprefix('local-start-'))
                    for p in store.root.glob('local-start-*.json')), 'owner_policy_unresolved_attempt')
    worker=editor(manager)
    decision=approved_manager_result(worker)
    require(decision['action']=='edit','asset_edit_hold')
    rows=measurements(manager,plan,clips)
    current=[(row['scene_id'],row['audio_sha256'],round((cue['end']-cue['start'])*24))
             for row,cue in zip(rows,spec['approved_timeline'],strict=True)]
    require(current==[(row['scene_id'],row['narration_sha256'],row['frames'])
                      for row in worker.contract['input']['scenes']],'timeline_evidence_changed')
    selected=worker.contract['input']['candidates']
    by_scene={clip['scene_id']:clip for clip in clips}
    editing=[]
    for choice in decision['scenes']:
        scene,name=choice['scene_id'],choice['asset_id']
        clip=by_scene[scene]
        route,asset_id=name.split(':',1)
        if route=='existing':
            require(clip['sha256']==selected[name]['asset_hash'],'production_source_asset_changed')
        elif route=='local':
            require(clip['source']['provenance']['evidence']=='registered rights record '+selected[name]['asset_hash'],
                    'production_source_asset_changed')
            receipt=store.read('local-completed-'+digest(scene)+'.json')
            require(receipt and receipt['asset']==name and receipt['sha256']==clip['sha256'],
                    'production_source_asset_changed')
        else:
            receipt=store.read('download-'+asset_id+'.json')
            require(receipt and receipt['asset']==name and receipt['scene_id']==scene
                    and receipt['rights_sha256']==selected[name]['asset_hash']
                    and receipt['sha256']==clip['sha256'],'production_source_asset_changed')
        editing.append(dict(scene_id=scene,clip_sha256=clip['sha256'],
                           **{k:choice[k] for k in ('in_frame','framing','transition','caption_position')}))
    validate_editing(spec,clips,editing)
    return dict(direction_sha256=digest(decision),scenes=editing,
                review_criteria=decision['review_criteria'],
                review_notes=[item['suitability'] for item in decision['scenes']])
