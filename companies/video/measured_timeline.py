"""Separate measured edit, retaining the approved script and original direction."""
import math
import wave
from copy import deepcopy

from autonomous_company import digest, exact, now, parse, require
from goal_dialogue import safe_text
from mission_production import (ProductionManager, SceneSpeechReceipts, approved_manager_result,
                                canonical_bytes, draft_id, prepare_manager_request, production_keys)
from role_json_schema import S, arr, enum, obj
from tts_job import private_write

FPS = 24
SCHEMA = obj(decision=enum('keep_total','change_total','hold'), rationale=S, quality_checks=S,
             scenes=arr(obj(scene_id=S, frames={'type':'integer'}, caption_frames={'type':'integer'})))
SYSTEM = (
    '당신은 영상 편집 관리자입니다. 한국어 설명과 JSON만 반환합니다. 승인 대본·자막 원문과 장면 순서는 유지합니다. '
    '실측 발화, 승인 목표 길이와 제약, 클립 가용 길이, 후크, 컷의 호흡과 자막 읽기 조건을 종합하십시오. '
    '같은 총 길이에서 시간 재배분, 총 길이 변경 제안, 또는 보류를 판단하십시오. '
    '정수 24fps 프레임을 사용하고 음성 실측 최소 프레임 이상, 등록 클립의 최대 프레임 이하를 제안하십시오. '
    '자막 노출 프레임은 최소 발화 프레임 이상이고 장면 내여야 합니다. 분할 자막 노출은 글자 수에 비례합니다. '
    '소스 미확보는 가용성 미확인으로 표시하고 시청·청취를 주장하지 마십시오. 가속, 자르기, 반복, 재합성은 금지입니다. '
    'hold이면 장면 배열은 비워 두십시오. 어떤 시간 변경도 별도의 대표 승인 이후에만 적용됩니다.'
)


def local_records(manager):
    from tts_execution import TTSExecution
    return TTSExecution(manager.root/'timeline_local')


def listening_note(manager, plan, scene):
    records=local_records(manager)
    path=records.root/f'listening-{scene}.json'
    if not path.exists():
        return None
    note=records._verified(path.name)
    _,receipt=SceneSpeechReceipts(manager,plan).validated(scene)
    require(note['audio_sha256']==receipt['audio_sha256'], 'timeline_evidence_changed')
    return note


def measurements(manager, plan, clips):
    speech=SceneSpeechReceipts(manager,plan)
    sources={clip['scene_id']:clip for clip in clips}
    rows=[]
    for shot in manager.contract['input']['storyboard']:
        scene=shot['scene_id']
        path,receipt=speech.validated(scene)
        with wave.open(str(path),'rb') as wav:
            frames,rate=wav.getnframes(),wav.getframerate()
        clip=sources.get(scene)
        row=dict(scene_id=scene,audio_sha256=receipt['audio_sha256'], min_frames=math.ceil(frames*FPS/rate),
                 seconds=frames/rate, original_frames=(shot['end']-shot['start'])*FPS,
                 caption_chars=len(shot['caption'].replace('\n','')), clip_sha256=clip['sha256'] if clip else None,
                 clip_max_frames=math.floor(clip['media']['duration']*FPS) if clip else None)
        row['caption_chars_per_second_if_aligned']=round(row['caption_chars']/row['seconds'],2)
        note=listening_note(manager,plan,scene)
        if note:
            row['representative_listening']=dict(opinion=note['opinion'],scope=note['scope'])
        rows.append(row)
    return rows


class TimelineManager(ProductionManager):
    marker_name='.mission-measured-timeline-v1'
    acceptance_scope='mission_measured_timeline_once_v1'

    def freeze_contract(self):
        path=self.root/'inputs.json'
        if not path.exists():
            private_write(path,canonical_bytes(self.contract['input']))

    def validate_plan(self,value):
        safe_text(value['rationale'],1200)
        safe_text(value['quality_checks'],1200)
        inputs=self.contract['input']
        old=inputs['measurements']
        scenes=value['scenes']
        if value['decision']=='hold':
            require(not scenes,'invalid_measured_timeline')
            return
        require([s['scene_id'] for s in scenes]==[s['scene_id'] for s in old],'invalid_measured_timeline')
        total=sum(s['frames'] for s in scenes)
        require(FPS<=total<=120*FPS and (total==inputs['approved_total_frames'])==(value['decision']=='keep_total'),
                'invalid_measured_timeline')
        for scene,row in zip(scenes,old,strict=True):
            require(row['min_frames']<=scene['caption_frames']<=scene['frames']
                    and (row['clip_max_frames'] is None or scene['frames']<=row['clip_max_frames']),
                    'invalid_measured_timeline')


def timeline_worker(manager, plan, constraints, rows):
    root=manager.root/'measured_edit'
    snapshot=root/'inputs.json'
    require(not root.is_symlink() and not snapshot.is_symlink(),'invalid_acceptance_path')
    if snapshot.exists():
        inputs=parse(snapshot.read_text())
    else:
        fields=('goal','audience','approved_plan_hash','preview_hash','storyboard','duration')
        inputs={field:manager.contract['input'][field] for field in fields}
        target=inputs['duration']*FPS
        inputs.update(direction_hash=digest(plan), constraints=constraints, measurements=rows,
                      approved_total_frames=target, total_change_required=sum(r['min_frames'] for r in rows)>target,
                      existing_boundaries_fit=all(r['min_frames']<=r['original_frames'] for r in rows),
                      caption_timing='approved caption text; proportional display within proposed caption_frames')
    return TimelineManager(root,dict(input=inputs,schema=SCHEMA,system=SYSTEM))


def require_current_audio(worker, rows):
    require([(r['scene_id'],r['audio_sha256'],r['min_frames']) for r in rows]==
            [(r['scene_id'],r['audio_sha256'],r['min_frames']) for r in worker.contract['input']['measurements']],
            'timeline_evidence_changed')


def timeline_proposal(worker):
    decision=approved_manager_result(worker)
    base=dict(version=1,input_sha256=digest(worker.contract['input']),
              plan_sha256=worker.contract['input']['approved_plan_hash'],decision=decision)
    return {**base,'sha256':digest(base)}


def timeline_status(manager, plan, constraints, clips, voices):
    if plan['voice']['tool']!='gemini_scene':
        return None
    missing=[s['scene_id'] for s in plan['scenes'] if 'fits_timeline' not in voices.get(s['scene_id'],{})]
    if missing:
        return dict(status='waiting_voice',missing=missing)
    rows=measurements(manager,plan,clips)
    if all(r['min_frames']<=r['original_frames'] for r in rows):
        return dict(status='original_fits')
    worker=timeline_worker(manager,plan,constraints,rows)
    state=dict(status='unprepared',scope=worker.contract['input'],measurements=rows)
    jid=draft_id(worker)
    if jid is None:
        return state
    draft=worker.load(jid)
    state['status']='stopped' if draft['real_ai']['attempts'] else 'authorized' if draft['grants'] else 'prepared'
    proposal=worker._proposal_path(jid)
    if proposal.is_file():
        body=parse(proposal.read_text())
        state.update(review_hash=digest(body),expires_at=body['expires_at'])
    if draft['status']=='needs_user_review':
        edit=timeline_proposal(worker)
        approval=local_records(manager).root/'approved.json'
        state.update(proposal=edit,status='hold' if edit['decision']['decision']=='hold'
                     else 'approved' if approval.exists() else 'review')
    return state


def run_timeline_action(manager, plan, constraints, clips, action, body):
    if action=='production-listen':
        exact(body,('scene','audio_sha256','opinion'))
        require(any(s['scene_id']==body['scene'] for s in plan['scenes']), 'production_scene_mismatch')
        _,receipt=SceneSpeechReceipts(manager,plan).validated(body['scene'])
        require(receipt['audio_sha256']==body['audio_sha256'], 'timeline_evidence_changed')
        safe_text(body['opinion'],500)
        records=local_records(manager)
        records.root.mkdir(mode=0o700,exist_ok=True)
        name=f'listening-{body["scene"]}.json'
        require(not (records.root/name).exists(), 'timeline_listening_already_recorded')
        note=dict(scene_id=body['scene'], audio_sha256=body['audio_sha256'], audience=manager.contract['input']['audience'],
                  plan_sha256=manager.contract['input']['approved_plan_hash'], opinion=body['opinion'],
                  at=now(), provenance='representative_listening',scope='this_scene_only')
        records._write(name,records._signed(note))
        return note
    rows=measurements(manager,plan,clips)
    require(any(r['min_frames']>r['original_frames'] for r in rows),'timeline_change_unnecessary')
    worker=timeline_worker(manager,plan,constraints,rows)
    require_current_audio(worker,rows)
    jid=draft_id(worker)
    if action=='production-timeline-prepare':
        return prepare_manager_request(worker,jid,body)
    require(jid is not None,'timeline_proposal_missing')
    if action=='production-timeline-consent':
        exact(body,('review_hash','free','policy'))
        key,_=production_keys()
        return worker.approve_consent(jid,body['review_hash'],api_key=key,owner_confirmed=True,
            free_project_confirmed=body['free'],google_data_policy_accepted=body['policy'])
    if action=='production-timeline-run':
        exact(body,())
        key,_=production_keys()
        return worker.ask_ai(jid,api_key=key)
    exact(body,('version','sha256','confirmed'))
    edit=timeline_proposal(worker)
    require(action=='production-timeline-approve' and type(body['version']) is int
            and body['version']==edit['version'] and body['sha256']==edit['sha256']
            and body['confirmed'] is True and edit['decision']['decision']!='hold','timeline_proposal_mismatch')
    require(all(row['clip_max_frames'] is None or change['frames']<=row['clip_max_frames']
                for row,change in zip(rows,edit['decision']['scenes'],strict=True)),
            'clip_too_short_repeat_not_allowed')
    records=local_records(manager)
    records.root.mkdir(mode=0o700,exist_ok=True)
    require(not (records.root/'approved.json').exists(),'timeline_already_approved')
    records._write('approved.json',records._signed(dict(edit=edit,at=now(),owner_confirmed=True)))
    return edit


def approved_clip_timeline(manager, plan, constraints, clips, spec):
    records=local_records(manager)
    if not (records.root/'approved.json').exists():
        return spec,None
    rows=measurements(manager,plan,clips)
    worker=timeline_worker(manager,plan,constraints,rows)
    require_current_audio(worker,rows)
    edit=timeline_proposal(worker)
    signed=records._verified('approved.json')
    require(signed['owner_confirmed'] is True and signed['edit']==edit,'timeline_proposal_mismatch')
    result=deepcopy(spec)
    cursor=0
    for cue,change,row in zip(result['approved_timeline'],edit['decision']['scenes'],rows,strict=True):
        require(row['clip_max_frames'] is None or change['frames']<=row['clip_max_frames'],
                'clip_too_short_repeat_not_allowed')
        cue.update(start=cursor/FPS,end=(cursor+change['frames'])/FPS,
                   caption_seconds=change['caption_frames']/FPS)
        cursor+=change['frames']
    result['total_seconds']=cursor/FPS
    return result,edit['sha256']
