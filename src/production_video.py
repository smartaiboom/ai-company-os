"""Versioned offline vector film tool. No URLs, user paths, shell or cloud TTS."""
import hashlib
from html import escape
import json
from pathlib import Path
import re
import tempfile
import unicodedata
from autonomous_company import require,exact,text,now,digest
from local_artifacts import run_command,FONT

TOOL='production_video_v2'
CATALOG={TOOL:{'network':False,'uploads':False,
    'input':'JSON {tool,width,height,series,palette:{background,surface,accent,text},audio_mode,scenes:[{title,subtitle,narration,seconds,graphic:{kind,labels},camera,transition}]}',
    'visuals':'generated vector illustrations only: conversation,target,workflow,comparison; labels 1..3; no source paths/URLs',
    'choices':'AI selects concept, palette #RRGGBB, graphics, wording, durations, camera hold/push_in/pan_right, transition cut/fade',
    'limits':'16:9 even 640..1920 width; 1..12 scenes; each 1..20 seconds, total <=120; title <=80/subtitle <=160/narration <=300 chars; labels <=40; text must fit measured layout estimate',
    'audio':'none or espeak_reference (robotic technical reference only, NOT natural neural Korean); external TTS disabled',
    'review':'scene keyframes, timestamps, narration duration, source hashes/licenses and full decode receipt; metadata is not human/model viewing'}}


def safe_text(value,limit):
    text(value,limit)
    require(not any(ord(c)<32 and c!='\n' for c in value),'invalid_caption')


def validate(spec):
    exact(spec,('tool','width','height','series','palette','audio_mode','scenes'))
    require(spec['tool']==TOOL,'tool_not_allowed')
    w,h=spec['width'],spec['height']
    require(type(w) is int and type(h) is int and 640<=w<=1920 and w%2==h%2==0 and w*9==h*16,'invalid_video_size')
    safe_text(spec['series'],40)
    exact(spec['palette'],('background','surface','accent','text'))
    require(all(isinstance(c,str) and re.fullmatch('#[0-9A-Fa-f]{6}',c) for c in spec['palette'].values()),'invalid_palette')
    require(spec['audio_mode'] in ('none','espeak_reference'),'external_tts_consent_required')
    require(isinstance(spec['scenes'],list) and 1<=len(spec['scenes'])<=12,'invalid_scenes')
    total=0
    for scene in spec['scenes']:
        exact(scene,('title','subtitle','narration','seconds','graphic','camera','transition'))
        for field,limit in (('title',80),('subtitle',160),('narration',300)):safe_text(scene[field],limit)
        require(type(scene['seconds']) in (int,float) and 1<=scene['seconds']<=20,'invalid_duration')
        exact(scene['graphic'],('kind','labels'))
        require(scene['graphic']['kind'] in ('conversation','target','workflow','comparison'),'invalid_graphic')
        labels=scene['graphic']['labels'];require(isinstance(labels,list) and 1<=len(labels)<=3,'invalid_graphic')
        for label in labels:safe_text(label,40)
        require(scene['camera'] in ('hold','push_in','pan_right') and scene['transition'] in ('cut','fade'),'invalid_motion')
        total+=scene['seconds']
    require(total<=120,'video_too_long')
    return total


def units(value):return sum(2 if unicodedata.east_asian_width(c) in ('W','F') else 1 for c in value)


def lines(value,budget,max_lines):
    output=[]
    for paragraph in value.split('\n'):
        current=''
        for word in paragraph.split(' '):
            require(units(word)<=budget,'caption_overflow')
            trial=current+' '+word if current else word
            if units(trial)>budget:output.append(current);current=word
            else:current=trial
        output.append(current)
    require(len(output)<=max_lines,'caption_overflow')
    return output


def svg_text(value,x,y,size,color,budget,max_lines=2,weight=400):
    return '<text font-family="Noto Sans CJK KR" font-weight="'+str(weight)+'" font-size="'+str(size)+'" fill="'+color+'">'+''.join(
        f'<tspan x="{x}" y="{y+i*size*1.35}">{escape(line)}</tspan>' for i,line in enumerate(lines(value,budget,max_lines)))+'</text>'


def scene_svg(spec,scene,index):
    c=spec['palette'];bg,surface,accent,ink=(c[k] for k in ('background','surface','accent','text'))
    labels=scene['graphic']['labels'];kind=scene['graphic']['kind']
    graphic=f'<g transform="translate(620,142)"><rect width="580" height="382" rx="32" fill="{surface}"/>'
    if kind=='conversation':
        graphic+=f'<rect x="36" y="32" width="508" height="306" rx="20" fill="{bg}"/><circle cx="62" cy="54" r="6" fill="{accent}"/><path d="M85 54H220" stroke="{ink}" stroke-opacity=".25" stroke-width="8"/>'
        for i,label in enumerate(labels):
            x=64 if i%2==0 else 118;y=86+i*76
            graphic+=f'<rect x="{x}" y="{y}" width="368" height="62" rx="16" fill="{accent if i%2==0 else surface}"/>'
            graphic+=svg_text(label,x+18,y+39,23,bg if i%2==0 else ink,28,1,600)
        graphic+=f'<path d="M472 294L500 310L480 316Z" fill="{accent}"/>'
    elif kind=='target':
        for radius,opacity in ((135,'.12'),(96,'.25'),(56,'.6')):
            graphic+=f'<circle cx="290" cy="177" r="{radius}" fill="{accent}" fill-opacity="{opacity}"/>'
        graphic+=f'<path d="M288 176L410 62M385 62H410V87" fill="none" stroke="{ink}" stroke-width="12" stroke-linecap="round"/>'
        graphic+=svg_text(labels[0],54,343,25,ink,36,1,600)
    elif kind=='workflow':
        for i,label in enumerate(labels):
            x=32+i*180
            graphic+=f'<rect x="{x}" y="105" width="158" height="150" rx="20" fill="{bg}"/><circle cx="{x+79}" cy="150" r="24" fill="{accent}"/>'
            graphic+=svg_text(str(i+1),x+70,159,24,bg,4,1,700)
            graphic+=svg_text(label,x+16,211,21,ink,12,2,500)
            if i<len(labels)-1:graphic+=f'<path d="M{x+161} 178H{x+177}M{x+169} 170L{x+177} 178L{x+169} 186" stroke="{accent}" stroke-width="4" fill="none"/>'
    else:
        for i,label in enumerate(labels[:2]):
            x=34+i*267
            graphic+=f'<rect x="{x}" y="52" width="245" height="274" rx="20" fill="{bg}"/>'
            for j,length in enumerate((132,168,110)):
                graphic+=f'<rect x="{x+28}" y="{100+j*32}" width="{length}" height="12" rx="6" fill="{accent}" fill-opacity="{.25+i*.5}"/>'
            graphic+=svg_text(label,x+26,247,22,ink,16,2,600)
            graphic+=f'<circle cx="{x+197}" cy="286" r="14" fill="{accent}" fill-opacity="{.25+i*.6}"/>'
    graphic+='</g>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{spec['width']}" height="{spec['height']}" viewBox="0 0 1280 720">
<defs><linearGradient id="g" x2="1" y2="1"><stop stop-color="{bg}"/><stop offset="1" stop-color="{surface}"/></linearGradient></defs>
<rect width="1280" height="720" fill="url(#g)"/><circle cx="1180" cy="40" r="260" fill="{accent}" fill-opacity=".07"/>
<path d="M0 500Q320 300 620 600T1280 440" stroke="{accent}" stroke-opacity=".09" stroke-width="70" fill="none"/>
<rect x="64" y="58" width="8" height="28" rx="4" fill="{accent}"/>
{svg_text(spec['series'],88,81,19,ink,42,1,500)}
{svg_text(str(index+1).zfill(2),64,165,24,accent,4,1,700)}
{svg_text(scene['title'],64,244,48,ink,20,3,700)}
<path d="M64 472H460" stroke="{accent}" stroke-opacity=".3" stroke-width="2"/>
<circle cx="80" cy="514" r="12" fill="{accent}"/><path d="M110 514H246" stroke="{ink}" stroke-opacity=".3" stroke-width="6"/>
{graphic}<rect x="52" y="580" width="1176" height="100" rx="22" fill="{bg}" fill-opacity=".93"/>
{svg_text(scene['subtitle'],82,620,27,ink,76,2,500)}
</svg>'''


def render(spec,folder):
    total=validate(spec);folder=Path(folder)
    require(folder.is_dir() and not folder.is_symlink(),'invalid_tool_directory')
    require(all(not (folder/name).exists() and not (folder/name).is_symlink()
                for name in ('video.mp4','receipt.json')),'artifact_exists')
    timeline=[];sources=[];offset=0
    with tempfile.TemporaryDirectory(dir=folder) as temporary:
        work=Path(temporary);segments=[]
        for i,scene in enumerate(spec['scenes']):
            svg=folder/f'source-{i:02}.svg';png=work/f'graphic-{i:02}.png'
            require(not svg.exists() and not svg.is_symlink(),'artifact_exists');svg.write_text(scene_svg(spec,scene,i),encoding='utf-8')
            run_command(['ffmpeg','-nostdin','-v','error','-i',str(svg),'-frames:v','1','-threads','1',str(png)],stage='ffmpeg_segment')
            audio=['-an'];speech=0
            if spec['audio_mode']=='espeak_reference':
                script=work/f'speech-{i}.txt';wav=work/f'speech-{i}.wav';script.write_text(scene['narration'],encoding='utf-8')
                run_command(['espeak-ng','-v','ko','-s','155','-f',script.name,'-w',wav.name],stage='espeak_audio',cwd=work)
                probe=json.loads(run_command(['ffprobe','-v','error','-show_format','-of','json',str(wav)],stage='ffprobe_audio'))
                speech=float(probe['format']['duration']);require(speech<=scene['seconds'],'narration_exceeds_scene')
                audio=['-i',str(wav),'-af','apad','-c:a','aac','-ar','44100','-ac','1']
            motion={'hold':"z=1:x=0:y=0",'push_in':"z='1+0.0002*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2'",
                    'pan_right':"z=1.04:x='min(on*0.18,iw-iw/zoom)':y='ih/2-ih/zoom/2'"}[scene['camera']]
            filters=f"zoompan={motion}:d=1:s={spec['width']}x{spec['height']}:fps=24"
            if scene['transition']=='fade':filters+=f",fade=t=in:d=0.2,fade=t=out:st={scene['seconds']-0.2}:d=0.2"
            segment=work/f'segment-{i}.mp4';segments.append(segment)
            run_command(['ffmpeg','-nostdin','-v','error','-loop','1','-i',str(png),*audio,'-filter_threads','1',
                         '-vf',filters,'-t',str(scene['seconds']),'-c:v','libx264','-threads','2','-pix_fmt','yuv420p',str(segment)],stage='ffmpeg_segment')
            frame=folder/f'keyframe-{i:02}.png'
            require(not frame.exists() and not frame.is_symlink(),'artifact_exists')
            run_command(['ffmpeg','-nostdin','-v','error','-ss',str(scene['seconds']/2),'-i',str(segment),'-frames:v','1','-threads','1',str(frame)],stage='ffmpeg_decode')
            timeline.append({'scene_index':i,'start_seconds':offset,'end_seconds':offset+scene['seconds'],
                             'subtitle_start_seconds':offset,'subtitle_end_seconds':offset+scene['seconds'],
                             'narration_duration_seconds':speech,'graphic':scene['graphic']['kind'],
                             'keyframe':frame.name,'keyframe_sha256':hashlib.sha256(frame.read_bytes()).hexdigest()})
            sources.append({'file':svg.name,'sha256':hashlib.sha256(svg.read_bytes()).hexdigest(),
                            'kind':'procedural_vector','creator':'AI Company OS renderer','license':'CC0-1.0'})
            offset+=scene['seconds']
        listing=work/'segments.txt';listing.write_text(''.join(f"file '{s.name}'\n" for s in segments))
        staged=work/'video.mp4'
        run_command(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','1','-i',str(listing),'-c','copy','-movflags','+faststart',str(staged)],stage='ffmpeg_concat')
        probe=json.loads(run_command(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(staged)],stage='ffprobe_final'))
        videos=[s for s in probe['streams'] if s['codec_type']=='video'];audios=[s for s in probe['streams'] if s['codec_type']=='audio']
        duration=float(probe['format']['duration'])
        require(len(videos)==1 and videos[0]['codec_name']=='h264' and videos[0]['width']==spec['width']
                and videos[0]['height']==spec['height'] and abs(duration-total)<.2,'video_probe_failed')
        require(len(audios)==(1 if spec['audio_mode']=='espeak_reference' else 0),'video_probe_failed')
        if audios:require(audios[0]['codec_name']=='aac' and abs(float(audios[0]['duration'])-total)<.2,'video_probe_failed')
        run_command(['ffmpeg','-nostdin','-v','error','-i',str(staged),'-f','null','-'],stage='ffmpeg_decode')
        staged.rename(folder/'video.mp4')
    receipt={'tool':TOOL,'at':now(),'input_hash':digest(spec),'sha256':hashlib.sha256((folder/'video.mp4').read_bytes()).hexdigest(),
             'duration_seconds':duration,'width':spec['width'],'height':spec['height'],'decoded':True,
             'audio':bool(audios),'audio_mode':spec['audio_mode'],'natural_korean_voice_verified':False,
             'review_material':timeline,'source_licenses':sources,'font_license':'Noto CJK SIL OFL 1.1',
             'model_visual_review_performed':False,'model_audio_review_performed':False,'subtitle_sync':'scene_level_only'}
    (folder/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    return receipt
