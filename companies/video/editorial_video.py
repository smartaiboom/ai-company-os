"""Local educational motion cards with exact narration receipts; no external model or UI server.

Reuse ClipJob storage/locking, MeloLocal, caption writer, media probe and command guards.
All visuals are explicitly labelled illustrative screens, never external AI clips or app recordings.
"""
from copy import deepcopy
from html import escape
import json
import math
from pathlib import Path
import uuid
import wave

from autonomous_company import Store, require, exact, digest, now, parse, CompanyError
from ai_clip_pipeline import ClipJob, write_captions, probe
from local_artifacts import run_command
from local_melo_tts import MeloLocal, file_hash
from production_video import lines, svg_text
from quality_workflow import inspect_plan

MODE='offline_editorial_video_v1'
LAYOUTS=('hook','question','format','audience','clock','three_lines','prompt','structure','check','recap')
AUTHOR='Codex authored/offline editorial judgement'


def validate(plan):
    exact(plan,('message','intro_kind','hook_seconds','author','scenes'))
    require(plan['author']==AUTHOR and isinstance(plan['message'],str),'invalid_editorial_provenance')
    require(plan['intro_kind'] in ('greeting','specific_problem'),'invalid_intro_kind')
    require(type(plan['hook_seconds']) in (int,float) and math.isfinite(plan['hook_seconds']) and plan['hook_seconds']>0,'invalid_hook')
    require(isinstance(plan['scenes'],list) and 2<=len(plan['scenes'])<=12,'invalid_scenes')
    ids=set();total=0
    for s in plan['scenes']:
        exact(s,('id','seconds','source_id','source_seconds','layout','title','label','body','narration'))
        require(isinstance(s['id'],str) and s['id'].isascii() and s['id'].replace('-','').isalnum() and s['id'] not in ids,'invalid_scene_id')
        ids.add(s['id'])
        require(s['layout'] in LAYOUTS and isinstance(s['body'],list) and 1<=len(s['body'])<=4,'invalid_layout')
        for k in ('seconds','source_seconds'):
            require(type(s[k]) in (int,float) and math.isfinite(s[k]) and 0<s[k]<=60,'invalid_duration')
        for text in (s['title'],s['label'],s['narration'],s['source_id'],*s['body']):
            require(isinstance(text,str) and 0<len(text)<=600 and not any(ord(c)<32 and c!='\n' for c in text)
                    and not any(c in text for c in '{}\\'),'invalid_editorial_text')
        total+=s['seconds']
    require(abs(total-60)<.01,'editorial_timeline_must_be_60')
    return plan


def inspect_edit(plan):
    """Measured/declared constraints only. Semantics and voice naturalness remain unassessed."""
    validate(plan)
    checks=inspect_plan('editor',dict(shots=[dict(seconds=s['seconds'],source_seconds=s['source_seconds'],
        source_id=s['source_id'],narration=s['narration'],source_status='planned') for s in plan['scenes']]))
    defects=checks['defects']
    def defect(issue,evidence,owner,correction):
        defects.append(dict(issue=issue,severity='major',owner=owner,evidence=evidence,correction=correction,
                            expected_metric='constraint satisfied in reinspection'))
    if not plan['message'].strip():defect('missing_core_message','message empty','writer','한 가지 사용자 가치를 명시')
    if plan['intro_kind']=='greeting' or plan['hook_seconds']>3:
        defect('opening_needs_revision',f"author-tag={plan['intro_kind']}; declared hook={plan['hook_seconds']}s",'writer','구체적 문제를 첫3초에 제시')
    for s in plan['scenes']:
        try:
            lines(s['title'],20,2)
            for body in s['body']:lines(body,30,3)
            lines(s['label'],38,1)
            lines(s['narration'],24,100)
        except CompanyError:
            defect('caption_or_card_overflow',s['id'],'editor','문구/줄바꿈을 안전한 카드 영역에 맞춤')
    return dict(source='deterministic_plan_check',input_hash=digest(plan),defects=defects,
                semantic_quality='unassessed',voice_naturalness='unassessed',publish_ready=False)


def scene_svg(scene,index,stage=2,total=10):
    """Three build stages with distinct instructional layouts, no application impersonation."""
    bg='#0B1726';ink='#F1F5FA';muted='#A5B6C9';accent='#B2F57B';cyan='#73DCEC';panel='#172B41'
    def text(value,x,y,size=32,color=ink,budget=30,n=3):
        return svg_text(value,x,y,size,color,budget,n,600)
    def rect(x,y,w,h,fill=panel):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="24" fill="{fill}"/>'
    body=scene['body'];shown=min(len(body),stage+1)
    g=''
    kind=scene['layout']
    if kind=='hook':
        g+=text('질문은 한 줄인데',66,485,30,muted)+text('답변은 너무 길다?',66,540,40,cyan)
        for i,w in enumerate([450,400,480,360,420,300]):
            g+=rect(76,590+i*40,w,12,accent if i<3 and stage>0 else '#30475E')
        g+=text('원하는 모양을 알려 주세요',76,925,30,accent)
    elif kind in ('question','prompt'):
        g+=rect(48,430,624,455)
        g+=text('입력 예시 · 실제 전송 없음',76,475,24,muted,42,1)
        y=545
        for value in body[:shown]:
            wrapped=lines(value,30,3)
            g+=text(value,76,y,34,ink if kind=='question' else accent)
            y+=len(wrapped)*46+22
        g+=f'<rect x="76" y="{min(y,844)}" width="3" height="25" fill="{cyan}"/>'
        if kind=='question':g+=text('받는 사람?   말투?   길이?',66,945,26,cyan,40,1)
    elif kind=='clock':
        g+=f'<circle cx="360" cy="610" r="130" fill="{panel}" stroke="{cyan}" stroke-width="5"/>'
        for i in range(12):
            a=math.pi*i/6
            g+=f'<circle cx="{360+112*math.sin(a):.1f}" cy="{610-112*math.cos(a):.1f}" r="4" fill="{muted}"/>'
        g+=f'<path d="M360 516V610H435" fill="none" stroke="{accent}" stroke-width="12" stroke-linecap="round"/>'
        g+=text(body[0],80,825,38,ink)
        if stage>0 and len(body)>1:g+=text(body[1],80,905,30,cyan)
    elif kind=='audience':
        for x,y,r in ((250,560,45),(460,560,45),(355,680,54)):
            g+=f'<circle cx="{x}" cy="{y}" r="{r}" fill="{cyan if x==355 else panel}"/>'
            g+=rect(x-r,y+r+14,r*2,65,panel)
        g+=text(body[0],80,880,44,accent)
    elif kind in ('format','three_lines','structure','check','recap'):
        for i,value in enumerate(body[:shown]):
            y=450+i*138
            g+=rect(48,y,624,118)
            badge='✓' if kind=='check' else str(i+1).zfill(2)
            g+=text(badge,74,y+65,28,accent,5,1)
            g+=text(value,146,y+53,32,ink,28,2)
        if kind=='format':g+=text('길이까지 구체적으로',66,945,30,cyan)
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="720" height="1280" viewBox="0 0 720 1280">
<rect width="720" height="1280" fill="{bg}"/>
<path d="M48 190H672" stroke="#30465B" stroke-width="2"/>
<circle cx="650" cy="230" r="170" fill="{cyan}" fill-opacity=".035"/>
{text('AI 질문 연습',52,86,27,ink,24,1)}
{text('예시 화면 · 실제 앱 녹화 아님',52,138,22,muted,48,1)}
{text(f'{index+1:02} / {total:02}   '+scene['label'],52,237,22,accent,48,1)}
{text(scene['title'],52,325,54,ink,20,3)}
{g}<rect x="38" y="990" width="644" height="180" rx="24" fill="#07111E"/>
<path d="M52 1210H668" stroke="#30465B" stroke-width="3"/>
{text('질문 예시를 설명하는 로컬 편집 시안',52,1250,19,muted,60,1)}
</svg>'''
    return svg


def verify_speech(plan,receipt,folder):
    require(receipt.get('engine') in ('MeloTTS','synthetic_test_tone_not_tts'),'unsupported_speech_engine')
    items=receipt.get('utterances')
    require(isinstance(items,list) and len(items)==len(plan['scenes']),'speech_count_mismatch')
    for s,item in zip(plan['scenes'],items):
        require(item.get('text')==s['narration'],'narration_speech_text_mismatch')
        require(item.get('spoken_text',item['text'])==s['narration'].replace('ChatGPT','챗지피티'),'spoken_text_mismatch')
        name=item.get('file');require(isinstance(name,str) and Path(name).name==name,'invalid_voice_path')
        path=folder/name;require(not path.is_symlink() and file_hash(path)==item['sha256'],'voice_changed')
        with wave.open(str(path),'rb') as f:
            require(f.getnchannels()==1 and f.getsampwidth()==2 and f.getframerate()==44100,'invalid_speech_format')
            measured=f.getnframes()/44100
        require(type(item['duration']) in (int,float) and math.isfinite(item['duration']) and measured>0
                and abs(measured-item['duration'])<.001,'speech_receipt_mismatch')
    return items


def allocate(plan,items):
    minimum=[math.ceil((a['duration']+.18)*24) for a in items]
    require(minimum[0]<=72,'hook_narration_exceeds_three_seconds')
    minimum[0]=72;extra=1440-sum(minimum)
    require(extra>=0,'narration_exceeds_target_revise_script')
    # Keep the opening exactly 3s; distribute remaining reading/pause time over other scenes.
    weights=[max(.1,s['seconds']-m/24) for s,m in zip(plan['scenes'][1:],minimum[1:])]
    for i,w in enumerate(weights,1):minimum[i]+=int(extra*w/sum(weights))
    for i in range(1440-sum(minimum)):minimum[1+i%(len(minimum)-1)]+=1
    return [n/24 for n in minimum]


class EditorialJob:
    def __init__(self,folder):
        self.guard=ClipJob(folder);self.root=self.guard.root

    def load(self):
        p=parse((self.root/'job.json').read_text())
        require(p.get('mode')==MODE and p.get('storage_hash')==digest({k:v for k,v in p.items() if k!='storage_hash'}),'editorial_job_changed')
        return p

    def create(self,plan):
        validate(plan)
        self.root.mkdir(parents=True,exist_ok=False,mode=0o700)
        self.guard.save(dict(mode=MODE,plan=deepcopy(plan),created_at=now(),attempts=[],status='ready',output=None))
        Store.atomic(self.root/'plan.json',plan)
        return self.load()

    def render(self,synthesizer=None):
        with self.guard.lock():
            p=self.load();require(not p['attempts'] and p['output'] is None,'render_not_replayable')
            inspection=inspect_edit(p['plan']);Store.atomic(self.root/'plan_inspection.json',inspection)
            require(not inspection['defects'],'editorial_plan_needs_revision')
            p['attempts'].append(dict(id=uuid.uuid4().hex,status='reserved',at=now(),input_hash=digest(p['plan'])))
            p['status']='rendering';self.guard.save(p)
            try:
                result=self._render(p['plan'],synthesizer or MeloLocal())
                p['output']=result;p['attempts'][0]['status']='completed';p['status']='rendered_for_user_review'
                self.guard.save(p);return result
            except Exception as exc:
                p['attempts'][0].update(status='failed',reason=exc.code if isinstance(exc,CompanyError) else 'local_editorial_render_failed')
                p['status']='failed';self.guard.save(p);raise

    def _render(self,plan,synthesizer):
        speech=self.root/'speech';speech.mkdir()
        receipt=synthesizer.synthesize([s['narration'] for s in plan['scenes']],speech)
        items=verify_speech(plan,receipt,speech);allocated=allocate(plan,items)
        cues=[];timeline=[];offset=0
        with wave.open(str(self.root/'narration.wav'),'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(44100)
            for s,item,length in zip(plan['scenes'],items,allocated):
                with wave.open(str(speech/item['file']),'rb') as src:pcm=src.readframes(src.getnframes())
                out.writeframesraw(pcm)
                target=round((offset+length)*44100)-round(offset*44100)
                require(len(pcm)//2<=target,'narration_exceeds_scene')
                out.writeframesraw(b'\0\0'*(target-len(pcm)//2))
                wrapped=lines(s['narration'],24,100);chunks=['\n'.join(wrapped[i:i+2]) for i in range(0,len(wrapped),2)]
                weights=[len(c.replace('\n','')) for c in chunks];elapsed=0
                for chunk,w in zip(chunks,weights):
                    duration=item['duration']*w/sum(weights)
                    cues.append(dict(start=offset+elapsed,end=offset+elapsed+duration,text=chunk));elapsed+=duration
                timeline.append(dict(id=s['id'],source_id=s['source_id'],start=offset,end=offset+length,
                    narration=s['narration'],speech_duration=item['duration'],source_kind='procedural_explanation',repeat_count=0))
                offset+=length
        require(all(0<=c['start']<c['end']<=60.001 and len(c['text'].split('\n'))<=2 for c in cues),'invalid_subtitle_timeline')
        require(all(a['end']<=b['start']+.001 for a,b in zip(cues,cues[1:])),'overlapping_subtitles')
        write_captions(self.root,cues)
        Store.atomic(self.root/'timeline.json',dict(scenes=timeline,captions=cues,speech=receipt,
            alignment='measured_utterance_boundaries_phrase_timing_estimated'))
        listing=[];assets=[]
        for i,(s,length) in enumerate(zip(plan['scenes'],allocated)):
            frames=round(length*24);parts=[max(1,frames//6),max(1,frames//6)];parts.append(frames-sum(parts))
            for stage,count in enumerate(parts):
                name=f'scene-{i:02}-{stage}'
                svg=self.root/(name+'.svg');png=self.root/(name+'.png')
                svg.write_text(scene_svg(s,i,stage,len(plan['scenes'])))
                run_command(['ffmpeg','-nostdin','-v','error','-i',str(svg),'-frames:v','1','-threads','1',str(png)],stage='ffmpeg_segment')
                assets.append(dict(file=svg.name,sha256=file_hash(svg),kind='procedural_explanation',creator=AUTHOR))
                listing.extend([f"file '{png.name}'",f'duration {count/24:.9f}'])
        listing.append(f"file 'scene-{len(allocated)-1:02}-2.png'")
        (self.root/'frames.txt').write_text('\n'.join(listing)+'\n')
        # Staged instructional builds are illustrative cards, not looped external footage.
        filters="fps=24,drawbox=x=52:y=1207:w=616:h=6:color=0xB2F57B:t=fill,subtitles=filename=captions.ass:fontsdir=/usr/share/fonts/opentype/noto,setsar=1"
        run_command(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','1','-i','frames.txt','-i','narration.wav',
            '-filter_threads','1','-vf',filters,'-t','60','-r','24','-c:v','libx264','-preset','veryfast','-threads','2',
            '-crf','20','-pix_fmt','yuv420p','-c:a','aac','-ar','44100','-ac','1','-movflags','+faststart','preview.mp4'],
            stage='ffmpeg_segment',cwd=self.root,timeout=600)
        output=self.root/'preview.mp4';media=probe(output)
        audios=[s for s in media['raw']['streams'] if s['codec_type']=='audio']
        require(media['width']==720 and media['height']==1280 and media['codec']=='h264' and media['fps']==24
                and abs(media['duration']-60)<.05 and len(audios)==1 and audios[0]['codec_name']=='aac','editorial_media_contract_failed')
        run_command(['ffmpeg','-nostdin','-v','error','-i',str(output),'-f','null','-'],stage='ffmpeg_decode')
        result=dict(file='preview.mp4',sha256=file_hash(output),duration=media['duration'],width=720,height=1280,
            codec='h264',audio_codec='aac',decoded=True,media=media,source_assets=assets,
            external_ai_clip_count=0,external_clip_repeats=0,external_api_calls=0,incurred_cost=0,
            source_kind='procedural_explanation',authorship=AUTHOR,font_license='Noto CJK SIL OFL 1.1',
            voice_engine=receipt['engine'],human_listening_verified=False,human_viewing_verified=False,
            publish_ready=False,publish_blockers=['user_quality_review_pending','voice_model_usage_rights_not_independently_verified'],
            subtitle_alignment='measured_utterance_boundaries_phrase_timing_estimated')
        Store.atomic(self.root/'receipt.json',result)
        return result
