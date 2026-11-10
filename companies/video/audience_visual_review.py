"""Asset-backed audience review, not a finished-film or TTS approval.

Existing Flow clips can be inspected only in labelled unpublished quality studies.
No media download, model loading, provider calls, voice cloning or GUI server.
"""
from html import escape
import math
from pathlib import Path
import shutil
from autonomous_company import require, exact, Store, digest, now, parse
from ai_clip_pipeline import open_input, probe, ClipJob
from local_artifacts import run_command, FONT
from local_melo_tts import file_hash
from production_video import svg_text


def assess(plan, assets, *, asset_root, voice_receipt=None):
    exact(plan,('audience','topic','scenes','card_seconds_limit','card_continuous_limit'))
    require(isinstance(plan['scenes'],list) and bool(plan['scenes']),'invalid_visual_plan')
    require(type(plan['card_seconds_limit']) in (int,float) and 0<=plan['card_seconds_limit']<=6
            and type(plan['card_continuous_limit']) in (int,float) and 0<=plan['card_continuous_limit']<=3,'weak_visual_limits')
    base=Path(asset_root).resolve()
    issues=[];used=set();total=cards=run=longest=0
    for scene in plan['scenes']:
        exact(scene,('id','seconds','kind','asset_id','narration','role'))
        require(type(scene['seconds']) in (int,float) and math.isfinite(scene['seconds']) and scene['seconds']>0,'invalid_duration')
        require(scene['kind'] in ('footage','document_demo','text_card'),'invalid_visual_kind')
        require(all(isinstance(scene[k],str) and bool(scene[k].strip()) for k in ('id','asset_id','narration','role')),'missing_visual_role')
        total+=scene['seconds']
        run=run+scene['seconds'] if scene['kind']=='text_card' else 0
        longest=max(longest,run);cards+=scene['seconds'] if scene['kind']=='text_card' else 0
        asset=assets.get(scene['asset_id'])
        if not asset or not asset.get('available'):
            issues.append(dict(issue='asset_missing',scene=scene['id'],owner='editor'));continue
        relative=asset.get('file','')
        if not isinstance(relative,str):
            issues.append(dict(issue='asset_unverified',scene=scene['id'],owner='editor'));continue
        path=base/relative
        valid=(isinstance(relative,str) and bool(relative) and not Path(relative).is_absolute()
               and '..' not in Path(relative).parts and not any(p.is_symlink() for p in (path,*path.parents))
               and path.resolve().is_relative_to(base) and path.is_file())
        if not valid or file_hash(path)!=asset.get('sha256'):
            issues.append(dict(issue='asset_unverified',scene=scene['id'],owner='editor'));continue
        if scene['seconds']>asset.get('duration',0):issues.append(dict(issue='source_duration_shortfall',scene=scene['id'],owner='editor'))
        if scene['kind']=='footage':
            if scene['asset_id'] in used:issues.append(dict(issue='footage_reused',scene=scene['id'],owner='editor'))
            used.add(scene['asset_id'])
        if scene['kind']=='document_demo' and not asset.get('motion_verified',False):
            issues.append(dict(issue='demo_motion_unverified',scene=scene['id'],owner='editor'))
    require(abs(total-60)<.01,'visual_plan_must_be_60_seconds')
    if cards>plan['card_seconds_limit'] or longest>plan['card_continuous_limit']:
        issues.append(dict(issue='too_much_static_card',owner='editor'))
    if not voice_comparison_ready(voice_receipt,base):issues.append(dict(issue='replacement_voice_pending',owner='voice'))
    return dict(source='deterministic_asset_check',plan_hash=digest(plan),issues=issues,
        text_card_seconds=cards,longest_card_run=longest,render_ready=not issues,publish_ready=False,
        rights_review_pending=[k for k,a in assets.items() if not a.get('rights_verified',False)],
        sensory_quality='unassessed')


def voice_comparison_ready(receipt,root):
    """A technical WAV receipt alone cannot override the user's negative voice review."""
    if not isinstance(receipt,dict) or receipt.get('state')!='user_preferred_B' or receipt.get('evaluator')!='user_listening':return False
    script=receipt.get('script_hash')
    if not isinstance(script,str) or len(script)!=64:return False
    for tag in ('A','B'):
        item=receipt.get(tag,{})
        name=item.get('file')
        if not isinstance(name,str) or Path(name).is_absolute() or '..' in Path(name).parts:return False
        path=Path(root)/name
        if path.is_symlink() or not path.resolve().is_relative_to(Path(root).resolve()) or not path.is_file():return False
        if item.get('script_hash')!=script or file_hash(path)!=item.get('sha256'):return False
    return True


def tts_candidate_gate(*,download_approved,installed,available_memory_bytes,free_disk_bytes):
    # Conservative preparation thresholds, NOT measured inference requirements or speed claims.
    blockers=[]
    if not installed and download_approved is not True:blockers.append('model_download_approval_required')
    if available_memory_bytes<6500000000:blockers.append('insufficient_memory_headroom_for_unbenchmarked_cpu_run')
    if free_disk_bytes<8000000000:blockers.append('insufficient_disk_headroom')
    return dict(status='blocked' if blockers else 'eligible_for_separate_bounded_probe',blockers=blockers,
                actual_model_execution=False,automatic_download=False)


def document_svg(step):
    """Authored counterexample; never represents a tested LLM response."""
    require(type(step) is int and 0<=step<=2,'invalid_demo_step')
    def text(s,x,y,size=32,color='#15283E',budget=34,n=3):return svg_text(s,x,y,size,color,budget,n,600)
    paper='#F7F4EC';accent='#CFFF80';bad='#F28575'
    body=f'<rect width="720" height="1280" fill="#102236"/><rect x="40" y="190" width="640" height="880" rx="24" fill="{paper}"/>'
    body+=text('요약, 그대로 보내기 전',48,94,39,'#FFFFFF',32,1)
    body+=text('가상 오류 예시 · 실제 모델 응답 아님',48,145,22,'#B9D4E9',52,1)
    body+=text('원문 메모',74,260,28)+text('제출: 목요일 오전 열 시',74,344,35)
    body+=text('회의 시간은 아직 미정',74,409,31)
    body+='<path d="M74 460H646" stroke="#A7BAC5" stroke-width="2"/>'
    body+=text('검토할 요약 예시',74,529,28)
    body+=text('제출: 금요일 오전 열 시' if step<2 else '제출: 목요일 오전 열 시',74,609,35)
    if step>=1:
        body+=f'<rect x="67" y="295" width="580" height="67" rx="8" fill="{accent}" fill-opacity=".45"/>'
        body+=f'<rect x="67" y="560" width="580" height="68" rx="8" fill="{bad if step==1 else accent}" fill-opacity=".4"/>'
        body+=text('원문과 날짜 대조' if step==1 else '원문과 맞춘 수정 예시',74,765,35)
        body+=text('미정은 미정으로 남겨요',74,835,30)
    else:body+=text('같은 날짜인가요?',74,765,38)
    body+=text('무음 화면 검토 · 게시 불가',48,1160,25,'#FFFFFF',48,1)
    return '<svg xmlns="http://www.w3.org/2000/svg" width="720" height="1280">'+body+'</svg>'


def render_motion_study(folder, inbox, relative_files):
    """15s silent proof with 8s real footage + 7s progressive original document demo."""
    require(isinstance(relative_files,list) and len(relative_files)==2,'two_local_sources_required')
    root=ClipJob(folder).root;root.mkdir(parents=True,exist_ok=False,mode=0o700)
    guard=ClipJob(root)
    state=dict(mode='audience_motion_study_v1',status='reserved',at=now(),attempts=1,output=None)
    guard.save(state)
    with guard.lock():
        try:
            sources=[];segments=[]
            for i,name in enumerate(relative_files):
                copied=root/f'source-{i}.mp4'
                with open_input(inbox,name) as src,copied.open('xb') as dst:shutil.copyfileobj(src,dst)
                media=probe(copied);require(media['duration']>=4,'source_too_short')
                sha=file_hash(copied);require(sha not in [s['sha256'] for s in sources],'duplicate_source')
                sources.append(dict(file=copied.name,original_file=name,sha256=sha,duration=media['duration'],
                    provenance='user_declared_google_flow',rights_verified=False,watermark='unknown',publish_ready=False))
                label=root/f'label-{i}.txt';label.write_text('무음 화면 검토 · 사용권 미확인 · 게시 불가\n예시: 업무 중 원문을 확인하는 장면')
                segment=root/f'part-{i}.mp4';segments.append(segment)
                filt='scale=720:1000:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x102236,setsar=1,fps=24'
                filt+=f',drawtext=fontfile={FONT}:textfile={label.name}:expansion=none:fontsize=25:fontcolor=white:box=1:boxcolor=black@0.8:x=36:y=48'
                run_command(['ffmpeg','-nostdin','-v','error','-protocol_whitelist','file,pipe','-i',copied.name,'-t','4','-an',
                    '-filter_threads','1','-vf',filt,'-c:v','libx264','-preset','veryfast','-threads','2','-pix_fmt','yuv420p',segment.name],
                    stage='ffmpeg_segment',cwd=root)
            for i in range(3):
                svg=root/f'demo-{i}.svg';svg.write_text(document_svg(i))
                run_command(['ffmpeg','-nostdin','-v','error','-i',svg.name,'-frames:v','1','-threads','1',f'demo-{i}.png'],stage='ffmpeg_segment',cwd=root)
            (root/'demo_frames.txt').write_text("file 'demo-0.png'\nduration 2\nfile 'demo-1.png'\nduration 2\nfile 'demo-2.png'\nduration 3\nfile 'demo-2.png'\n")
            run_command(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','1','-i','demo_frames.txt','-t','7','-an',
                '-filter_threads','1','-vf',"fps=24,zoompan=z='1+0.00006*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=720x1280:fps=24,setsar=1",'-c:v','libx264','-preset','veryfast','-threads','2','-pix_fmt','yuv420p','part-2.mp4'],stage='ffmpeg_segment',cwd=root)
            (root/'parts.txt').write_text("file 'part-0.mp4'\nfile 'part-1.mp4'\nfile 'part-2.mp4'\n")
            run_command(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','1','-i','parts.txt','-c','copy','-movflags','+faststart','visual_motion_study_15s.mp4'],stage='ffmpeg_concat',cwd=root)
            output=root/'visual_motion_study_15s.mp4';m=probe(output)
            require(abs(m['duration']-15)<.1 and not m['audio'] and m['width']==720 and m['height']==1280,'motion_study_contract_failed')
            run_command(['ffmpeg','-nostdin','-v','error','-i',str(output),'-f','null','-'],stage='ffmpeg_decode')
            result=dict(file=output.name,sha256=file_hash(output),duration=m['duration'],audio=False,decoded=True,
                footage_seconds=8,document_demo_seconds=7,looped_footage_seconds=0,sources=sources,
                demo_frame_hashes=[file_hash(root/f'demo-{i}.png') for i in range(3)],
                kind='silent_visual_study_not_completed_short',publish_ready=False,rights_verified=False,
                external_ai_calls=0,incurred_cost=0,actor='Codex authored/offline editorial judgement')
            state.update(status='completed',output=result);guard.save(state);Store.atomic(root/'receipt.json',result)
            return result
        except BaseException:
            state['status']='uncertain';guard.save(state);raise
