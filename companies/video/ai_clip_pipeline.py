"""Offline imported-clip Shorts pipeline. No provider networking or publishing."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from fractions import Fraction
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import uuid
import wave
from typing import Protocol

from autonomous_company import CompanyError, Store, digest, exact, fcntl, now, parse, require
from goal_dialogue import safe_text
from local_artifacts import FONT, run_command, LocalToolError
from local_melo_tts import MeloLocal, file_hash
from production_video import lines

MODE = 'offline_ai_clip_shorts_v1'
PROVIDERS = {name: dict(id=name, adapter_kind='manual_import', manual_import=True,
    automatic_generation_supported=False, api_enabled=False, cost_estimate=None,
    watermark='unknown', commercial_use='unknown', terms_verified=False,
    notice='Web credits are not API credits. User manually generates/downloads; no browser automation.')
    for name in ('google_flow', 'pika', 'kling')}
PROVIDERS['synthetic_test_fixture'] = dict(id='synthetic_test_fixture', adapter_kind='local_fixture',
    manual_import=True, automatic_generation_supported=False, api_enabled=False, cost_estimate=0,
    watermark='absent', commercial_use='allowed', terms_verified=True, notice='Not AI generated.')


class SceneProvider(Protocol):
    def capabilities(self) -> dict: ...
    def generate_scene(self, request: dict) -> dict: ...


class ManualClipProvider:
    def __init__(self, name):
        require(name in PROVIDERS and name != 'synthetic_test_fixture', 'unknown_manual_provider')
        self.name = name
    def capabilities(self): return deepcopy(PROVIDERS[self.name])
    def generate_scene(self, request):
        validate_request(request)
        return dict(status='pending_manual_import', request=deepcopy(request), provider=self.name,
                    estimated_cost=None, actual_cost=None, clip=None, automatic_generation_supported=False)


class DisabledAPIProvider:
    def capabilities(self):
        return dict(adapter_kind='api_adapter', manual_import=False, automatic_generation_supported=False,
                    api_enabled=False, cost_estimate=None, terms_verified=False)
    def generate_scene(self, request):
        validate_request(request)
        raise CompanyError('external_video_api_disabled')


def validate_request(request):
    exact(request, ('prompt', 'aspect_ratio', 'duration_target', 'reference_image'))
    safe_text(request['prompt'], 2400)
    require(request['aspect_ratio'] == '9:16', 'vertical_request_required')
    require(type(request['duration_target']) in (int, float) and math.isfinite(request['duration_target'])
            and 1 <= request['duration_target'] <= 60, 'invalid_clip_duration')
    ref = request['reference_image']
    if ref is not None:
        require(isinstance(ref, str) and not PurePosixPath(ref).is_absolute()
                and '..' not in PurePosixPath(ref).parts and '\\' not in ref, 'invalid_reference_image')
    return request


def validate_plan(plan):
    exact(plan, ('goal', 'decision_source', 'total_seconds', 'fit', 'allow_repeat', 'scenes'))
    safe_text(plan['goal'], 4000); safe_text(plan['decision_source'], 200)
    require(type(plan['total_seconds']) in (int, float) and math.isfinite(plan['total_seconds'])
            and 1 <= plan['total_seconds'] <= 120, 'invalid_total_duration')
    require(plan['fit'] in ('letterbox', 'crop') and type(plan['allow_repeat']) is bool, 'invalid_edit_policy')
    require(isinstance(plan['scenes'], list) and 1 <= len(plan['scenes']) <= 12, 'invalid_scenes')
    ids = set()
    for scene in plan['scenes']:
        exact(scene, ('id', 'request', 'utterances'))
        safe_text(scene['id'], 40)
        require(scene['id'].isascii() and scene['id'].replace('-', '').isalnum()
                and scene['id'] not in ids, 'invalid_scene_id'); ids.add(scene['id'])
        validate_request(scene['request'])
        require(isinstance(scene['utterances'], list) and 1 <= len(scene['utterances']) <= 4, 'invalid_utterances')
        for text in scene['utterances']:
            safe_text(text, 600)
            require(not any(c in text for c in '{}\\'), 'caption_markup_forbidden')
            lines(text, 24, 100)  # Layout rejects long unbreakable words; never drops caption content.
    require(sum(len(s['utterances']) for s in plan['scenes']) <= 24, 'invalid_utterances')
    return plan


def validate_source(source):
    exact(source, ('provider', 'provenance', 'generated_at', 'license', 'terms_url', 'usage_rights',
                   'commercial_use', 'allowed_to_publish', 'watermark', 'rights_verified',
                   'rights_evidence', 'estimated_cost', 'actual_cost'))
    for field in ('provider', 'license', 'terms_url', 'usage_rights', 'rights_evidence'):
        safe_text(source[field], 2000)
    provenance = source['provenance']
    exact(provenance, ('kind', 'evidence'))
    require(provenance['kind'] in ('external_ai_clip', 'synthetic_test_fixture'), 'invalid_provenance')
    safe_text(provenance['evidence'], 2000)
    require((source['provider'] == 'synthetic_test_fixture') == (provenance['kind'] == 'synthetic_test_fixture'), 'invalid_provenance')
    require(source['commercial_use'] in ('allowed', 'prohibited', 'unknown')
            and source['watermark'] in ('present', 'absent', 'unknown')
            and (source['allowed_to_publish'] is None or type(source['allowed_to_publish']) is bool)
            and type(source['rights_verified']) is bool, 'invalid_rights')
    from datetime import datetime, timedelta
    try: valid = datetime.fromisoformat(source['generated_at']).utcoffset() == timedelta(hours=9)
    except (ValueError, TypeError): valid = False
    require(valid, 'kst_timestamp_required')
    for field in ('estimated_cost', 'actual_cost'):
        value = source[field]
        require(value is None or type(value) in (int, float) and math.isfinite(value) and value >= 0, 'invalid_cost')
    return source


def publishable(source):
    return (source['provenance']['kind'] == 'external_ai_clip' and source['rights_verified'] is True
            and source['allowed_to_publish'] is True and source['commercial_use'] == 'allowed'
            and source['license'].lower() not in ('unknown', 'unverified', '미확인')
            and source['usage_rights'].lower() not in ('unknown', 'unverified', '미확인')
            and source['terms_url'].startswith('https://')
            and source['rights_evidence'].lower() not in ('unknown', 'unverified', '미확인')
            and source['watermark'] == 'absent')


def probe(path):
    raw = run_command(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-show_streams',
                       '-show_format', '-of', 'json', str(path)], stage='ffprobe_final')
    data = json.loads(raw)
    videos = [s for s in data['streams'] if s['codec_type'] == 'video']
    audios = [s for s in data['streams'] if s['codec_type'] == 'audio']
    require(len(videos) == 1 and len(audios) <= 1, 'invalid_clip_streams')
    v = videos[0]; duration = float(data['format']['duration'])
    require('mp4' in data['format']['format_name'] or 'mov' in data['format']['format_name'], 'invalid_clip_container')
    require(v['codec_name'] in ('h264', 'hevc', 'mpeg4', 'vp9', 'av1', 'prores')
            and 16 <= v['width'] <= 4096 and 16 <= v['height'] <= 4096
            and math.isfinite(duration) and .1 <= duration <= 120, 'invalid_clip_media')
    fps = float(Fraction(v['avg_frame_rate']))
    require(0 < fps <= 120, 'invalid_clip_frames')
    if v.get('nb_frames') not in (None, 'N/A'):
        require(int(v['nb_frames']) > 0, 'invalid_clip_frames')
    return dict(width=v['width'], height=v['height'], codec=v['codec_name'], fps=fps,
                duration=duration, audio=bool(audios), frames=v.get('nb_frames'), raw=data)


@contextmanager
def open_input(root, relative):
    """Traverse directory fds with O_NOFOLLOW, including every parent component."""
    root = Path(root).absolute()
    for parent in (root, *root.parents): require(not parent.is_symlink(), 'symlink_input_forbidden')
    relative = PurePosixPath(relative)
    require(not relative.is_absolute() and relative.parts and '..' not in relative.parts
            and '\\' not in str(relative) and relative.suffix.lower() in ('.mp4', '.mov'), 'invalid_clip_path')
    descriptors = []
    try:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW); descriptors.append(fd)
        for part in relative.parts[:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd); descriptors.append(fd)
        fd = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd); descriptors.append(fd)
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= 209715200, 'invalid_clip_file')
        with os.fdopen(os.dup(fd), 'rb') as stream: yield stream
    finally:
        for fd in reversed(descriptors): os.close(fd)


class ClipJob:
    def __init__(self, folder):
        p = Path(folder).absolute()
        require(not any(x.is_symlink() for x in (p, *p.parents)), 'invalid_job_path')
        self.root = p

    def create(self, plan):
        validate_plan(plan)
        self.root.mkdir(parents=True, exist_ok=False, mode=0o700)
        (self.root/'assets').mkdir()
        self.save(dict(mode=MODE, created_at=now(), plan=deepcopy(plan), clips=[], status='pending_external_clip',
                       active_operation=None, attempts=[], output=None, external_api_calls=0, incurred_cost=0))
        Store.atomic(self.root/'provider_capabilities.json', PROVIDERS)
        Store.atomic(self.root/'scene_plan.json', plan)
        return self.load()

    def load(self):
        require(not (self.root/'job.json').is_symlink() and not (self.root/'assets').is_symlink(), 'invalid_job_path')
        p = parse((self.root/'job.json').read_text())
        require(p.get('mode') == MODE and p.get('storage_hash') == digest({k:v for k,v in p.items() if k != 'storage_hash'}), 'job_changed')
        return p

    def save(self, state):
        state['updated_at'] = now()
        state['storage_hash'] = digest({k:v for k,v in state.items() if k != 'storage_hash'})
        Store.atomic(self.root/'job.json', state)

    @contextmanager
    def lock(self):
        require(fcntl is not None and not (self.root/'.lock').is_symlink(), 'job_lock_unavailable')
        with (self.root/'.lock').open('a') as lock:
            try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise CompanyError('job_busy') from None
            try: yield
            finally: fcntl.flock(lock, fcntl.LOCK_UN)

    def import_generated_clip(self, inbox, relative, scene_id, source):
        validate_source(source)
        with self.lock():
            p = self.load()
            require(not p['attempts'] and p['output'] is None, 'job_already_started')
            require(scene_id in {s['id'] for s in p['plan']['scenes']}, 'unknown_scene')
            require(not any(c['scene_id'] == scene_id for c in p['clips']), 'scene_already_imported')
            with tempfile.TemporaryDirectory(dir=self.root) as temporary:
                staged = Path(temporary)/'clip.mp4'
                with open_input(inbox, relative) as src, staged.open('xb') as dst:
                    size=0
                    while True:
                        block=src.read(1048576)
                        if not block: break
                        size+=len(block); require(size<=209715200, 'clip_too_large')
                        dst.write(block)
                original_hash = file_hash(staged)
                require(not any(c['sha256'] == original_hash for c in p['clips']), 'duplicate_clip')
                media = probe(staged)
                run_command(['ffmpeg', '-nostdin', '-v', 'error', '-protocol_whitelist', 'file,pipe',
                             '-i', str(staged), '-f', 'null', '-'], stage='ffmpeg_decode')
                asset = self.root/'assets'/(original_hash+'.mp4')
                require(not asset.exists() and not asset.is_symlink(), 'asset_exists')
                staged.rename(asset)
            record = dict(scene_id=scene_id, file=asset.name, original_file=str(relative),
                          sha256=original_hash, media=media, source=deepcopy(source), imported_at=now(),
                          status='validated', source_verification='operator_declared_not_independently_verified',
                          publish_ready=publishable(source))
            p['clips'].append(record); self.save(p)
            return record

    def render(self, synthesizer=None):
        with self.lock():
            p = self.load(); validate_plan(p['plan'])
            require(not p['active_operation'] and not p['attempts'] and p['output'] is None, 'render_not_replayable')
            require(len(p['clips']) == len(p['plan']['scenes']), 'pending_external_clip')
            for clip in p['clips']:
                require(clip['file'] == clip['sha256']+'.mp4' and len(clip['sha256']) == 64
                        and all(c in '0123456789abcdef' for c in clip['sha256'])
                        and not (self.root/'assets'/clip['file']).is_symlink(), 'invalid_asset_path')
                require(file_hash(self.root/'assets'/clip['file']) == clip['sha256'], 'clip_changed')
                if p['plan']['fit'] == 'crop': require(clip['source']['watermark'] == 'absent', 'watermark_crop_forbidden')
            attempt = dict(id=uuid.uuid4().hex, status='reserved', at=now(), plan_hash=digest(p['plan']))
            p['attempts'].append(attempt); p['active_operation'] = attempt['id']; self.save(p)
            try:
                result = self._render(p, synthesizer or MeloLocal())
                attempt['status'] = 'completed'; p['active_operation'] = None
                p['output'] = result
                p['status'] = 'pending_external_clip' if result['synthetic_test_fixture'] else 'rendered_for_review'
                self.save(p); return result
            except Exception as exc:
                attempt['status'] = 'failed'
                if isinstance(exc, LocalToolError): attempt['diagnostics'] = exc.diagnostics
                attempt['reason'] = exc.code if isinstance(exc, CompanyError) else 'local_render_failed'
                p['status'] = 'failed'; self.save(p)
                raise CompanyError(attempt['reason']) from None

    def _render(self, state, synthesizer):
        plan = state['plan']; audio_folder = self.root/'speech'; audio_folder.mkdir()
        texts = [t for s in plan['scenes'] for t in s['utterances']]
        speech = synthesizer.synthesize(texts, audio_folder)
        durations = [x['duration'] for x in speech['utterances']]
        require(all(type(d) in (int, float) and math.isfinite(d) and d > 0 for d in durations), 'invalid_speech_duration')
        minimum = []; index = 0
        for scene in plan['scenes']:
            count = len(scene['utterances'])
            minimum.append(sum(durations[index:index+count]) + .18*(count-1) + .25); index += count
        require(sum(minimum) <= plan['total_seconds'], 'narration_exceeds_target_revise_script')
        # Quantize to 24fps, preserving enough time for every actual audio sample.
        frame_min = [math.ceil(d*24) for d in minimum]
        total_frames = round(plan['total_seconds']*24)
        require(sum(frame_min) <= total_frames, 'narration_exceeds_target_revise_script')
        extra = total_frames-sum(frame_min)
        frames = [n + extra//len(frame_min) + (i < extra%len(frame_min)) for i,n in enumerate(frame_min)]
        allocated = [n/24 for n in frames]
        clip_map = {c['scene_id']:c for c in state['clips']}
        for scene, length in zip(plan['scenes'], allocated):
            require(plan['allow_repeat'] or clip_map[scene['id']]['media']['duration']+.02 >= length, 'clip_too_short_repeat_not_allowed')
        timeline = []; cues = []; offset = 0; index = 0
        track = self.root/'narration.wav'
        with wave.open(str(track), 'wb') as out:
            out.setnchannels(1); out.setsampwidth(2); out.setframerate(44100)
            for scene, length in zip(plan['scenes'], allocated):
                start = offset; scene_samples = 0
                for number, text in enumerate(scene['utterances']):
                    item = speech['utterances'][index]; index += 1
                    voice_file = audio_folder/item['file']
                    require(voice_file.parent == audio_folder and file_hash(voice_file) == item['sha256'], 'voice_changed')
                    with wave.open(str(voice_file), 'rb') as voice:
                        require(voice.getnchannels() == 1 and voice.getsampwidth() == 2 and voice.getframerate() == 44100, 'invalid_speech_format')
                        pcm = voice.readframes(voice.getnframes()); sample_count = len(pcm)//2
                    measured = sample_count/44100
                    require(abs(measured-item['duration']) < .001, 'speech_receipt_mismatch')
                    voice_start = start+scene_samples/44100
                    out.writeframesraw(pcm); scene_samples += sample_count
                    wrapped = lines(text, 24, 100); chunks = ['\n'.join(wrapped[i:i+2]) for i in range(0,len(wrapped),2)]
                    weight = sum(len(t.replace('\n','')) for t in chunks); elapsed = 0
                    for chunk in chunks:
                        duration = measured*len(chunk.replace('\n',''))/weight
                        cues.append(dict(start=voice_start+elapsed, end=voice_start+elapsed+duration, text=chunk))
                        elapsed += duration
                    if number < len(scene['utterances'])-1:
                        out.writeframesraw(b'\0\0'*7938); scene_samples += 7938
                target = round((start+length)*44100)-round(start*44100)
                require(scene_samples <= target, 'narration_exceeds_scene')
                out.writeframesraw(b'\0\0'*(target-scene_samples))
                clip = clip_map[scene['id']]
                timeline.append(dict(scene_id=scene['id'], start=start, end=start+length, width=720, height=1280,
                    speech_seconds=scene_samples/44100, clip_sha256=clip['sha256'], fit=plan['fit'],
                    repeat_count=max(0, math.ceil(length/clip['media']['duration'])-1)))
                offset += length
        write_captions(self.root, cues)
        Store.atomic(self.root/'timeline.json', dict(scenes=timeline, captions=cues, speech=speech,
                     alignment='measured_utterance_boundaries_phrase_timing_estimated', human_listening_verified=False))
        synthetic = any(c['source']['provenance']['kind'] == 'synthetic_test_fixture' for c in state['clips'])
        args = ['ffmpeg','-nostdin','-v','error']
        for scene in plan['scenes']:
            if plan['allow_repeat']: args += ['-stream_loop','-1']
            args += ['-protocol_whitelist','file,pipe','-i',str(self.root/'assets'/clip_map[scene['id']]['file'])]
        args += ['-i', str(track)]
        filters = []
        for i, length in enumerate(allocated):
            fit = ('scale=720:1280:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x101820'
                   if plan['fit'] == 'letterbox' else 'scale=720:1280:force_original_aspect_ratio=increase:force_divisible_by=2,crop=720:1280')
            filters.append(f'[{i}:v]scale=trunc(iw*sar/2)*2:ih,setsar=1,{fit},setsar=1,fps=24,trim=duration={length:.9f},setpts=PTS-STARTPTS[v{i}]')
        filters.append(''.join(f'[v{i}]' for i in range(len(allocated)))+f'concat=n={len(allocated)}:v=1:a=0[joined]')
        overlay = ',drawtext=fontfile='+FONT+':textfile=fixture_notice.txt:expansion=none:fontsize=24:fontcolor=white:box=1:boxcolor=black@0.7:x=48:y=100' if synthetic else ''
        (self.root/'fixture_notice.txt').write_text('기술 시안 · 비AI 테스트 클립' if synthetic else '')
        filters.append("[joined]subtitles=filename=captions.ass:fontsdir=/usr/share/fonts/opentype/noto"+overlay+'[final]')
        args += ['-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map','[final]',
                 '-map',f'{len(allocated)}:a','-t',f'{offset:.9f}','-c:v','libx264','-preset','veryfast',
                 '-threads','2','-crf','23','-pix_fmt','yuv420p','-c:a','aac','-ar','44100','-ac','1',
                 '-movflags','+faststart','preview.mp4']
        run_command(args, stage='ffmpeg_segment', cwd=self.root, timeout=300)
        output = self.root/'preview.mp4'; media = probe(output)
        require(media['width'] == 720 and media['height'] == 1280 and media['audio']
                and media['codec'] == 'h264' and abs(media['fps']-24) < .001
                and media['raw']['streams'][0].get('sample_aspect_ratio') == '1:1'
                and abs(media['duration']-plan['total_seconds']) < .2, 'final_media_contract_failed')
        run_command(['ffmpeg','-nostdin','-v','error','-i',str(output),'-f','null','-'],stage='ffmpeg_decode')
        for i, item in enumerate(timeline):
            run_command(['ffmpeg','-nostdin','-v','error','-ss',str((item['start']+item['end'])/2),'-i',str(output),
                         '-frames:v','1','-threads','1',str(self.root/f'keyframe-{i:02}.png')],stage='ffmpeg_decode')
        result = dict(file='preview.mp4', sha256=file_hash(output), duration=media['duration'], width=720,height=1280,
            audio=True, audio_engine=speech['engine'], decoded=True, external_api_calls=0, incurred_cost=0,
            synthetic_test_fixture=synthetic, ai_generated_clip_used=not synthetic,
            publish_ready=all(c['publish_ready'] for c in state['clips']) and not synthetic,
            human_viewing_verified=False, human_listening_verified=False,
            subtitle_alignment='measured_utterance_boundaries_phrase_timing_estimated',
            source_receipts=state['clips'], media=media)
        Store.atomic(self.root/'receipt.json', result)
        return result


def write_captions(folder, cues):
    header = '[Script Info]\nScriptType: v4.00+\nPlayResX: 720\nPlayResY: 1280\nWrapStyle: 2\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Default,Noto Sans CJK KR,46,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80101010,0,0,0,0,100,100,0,0,1,3,1,2,60,60,180,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n'
    def stamp(value, ass=False):
        n=round(value*(100 if ass else 1000)); scale=100 if ass else 1000
        h=n//(3600*scale);m=n//(60*scale)%60;s=n//scale%60;f=n%scale
        return f'{h}:{m:02}:{s:02}.{f:02}' if ass else f'{h:02}:{m:02}:{s:02},{f:03}'
    ass=[];srt=[]
    for i,cue in enumerate(cues,1):
        caption=cue['text'].replace('\n', r'\N')
        ass.append(f"Dialogue: 0,{stamp(cue['start'],True)},{stamp(cue['end'],True)},Default,,0,0,0,,{caption}\n")
        srt.append(f"{i}\n{stamp(cue['start'])} --> {stamp(cue['end'])}\n{cue['text']}\n")
    (folder/'captions.ass').write_text(header+''.join(ass)); (folder/'captions.srt').write_text('\n'.join(srt))


def baseline_plan(source, goal):
    """Explicit Codex baseline decisions, not an AI manager invocation or fixed model questionnaire."""
    scenes=[]
    concepts=[
        'Vertical 9:16 realistic cinematic close-up of a novice typing on a laptop at a calm desk, natural window light, gentle camera move. Leave central lower safe area clear. No readable text, no fabricated ChatGPT interface, no logos.',
        'Vertical 9:16 cinematic over-shoulder shot of a person planning a friendly library meeting with a blank notebook and laptop, subtle changes of focus. No readable text, no logos, no people identifiable.',
        'Vertical 9:16 calm close-ups of checking a notebook beside a laptop then confidently typing, human-centered beginner tutorial mood. No readable text, no logos. Preserve full subjects and watermark if any.'
    ]
    require(len(source['scenes']) == 6, 'baseline_requires_six_source_scenes')
    for i in range(3):
        scenes.append(dict(id=f'scene-{i+1}', request=dict(prompt=concepts[i],aspect_ratio='9:16',duration_target=20,reference_image=None),
                           utterances=[s['narration'] for s in source['scenes'][2*i:2*i+2]]))
    return validate_plan(dict(goal=goal,decision_source='codex_offline_baseline_no_manager_model_called',total_seconds=60,
                              fit='letterbox',allow_repeat=True,scenes=scenes))


def create_fixtures(folder):
    """Moving codec fixtures, deliberately not AI, stock footage, or a generated-video claim."""
    folder=Path(folder);folder.mkdir(exist_ok=False,parents=True)
    for i,src in enumerate(('testsrc2=size=360x640:rate=24','smptebars=size=640x360:rate=24',
                            'testsrc=size=640x360:rate=24'),1):
        run_command(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',src,'-t','4','-an','-c:v','libx264',
                     '-threads','2','-filter_threads','1','-pix_fmt','yuv420p',str(folder/f'fixture-{i}.mp4')],stage='ffmpeg_segment')
    source=dict(provider='synthetic_test_fixture',provenance=dict(kind='synthetic_test_fixture',evidence='Local FFmpeg test pattern, not AI footage'),
                generated_at=now(),license='local codec test only',terms_url='not applicable',usage_rights='Local technical review',
                commercial_use='unknown',allowed_to_publish=False,watermark='absent',rights_verified=False,
                rights_evidence='Not final content',estimated_cost=0,actual_cost=0)
    Store.atomic(folder/'source.json',source)
    return source


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('create');p.add_argument('job');p.add_argument('plan')
    p=sub.add_parser('import');p.add_argument('job');p.add_argument('inbox');p.add_argument('file');p.add_argument('scene');p.add_argument('source')
    p=sub.add_parser('render');p.add_argument('job');p.add_argument('--melo-root',default='data/tts_korean_review')
    p=sub.add_parser('baseline');p.add_argument('job');p.add_argument('--source',default='data/video_baseline_review/20261109T132912_KST/render_spec.json');p.add_argument('--goal',default='AI 초보자를 위한 ChatGPT 활용법 1분 9:16 유튜브 쇼츠')
    p=sub.add_parser('fixtures');p.add_argument('inbox')
    args=parser.parse_args(argv)
    try:
        if args.command=='fixtures': result=create_fixtures(args.inbox)
        else:
            job=ClipJob(args.job)
            if args.command=='create': result=job.create(parse(Path(args.plan).read_text()))
            elif args.command=='baseline': result=job.create(baseline_plan(parse(Path(args.source).read_text()),args.goal))
            elif args.command=='import': result=job.import_generated_clip(args.inbox,args.file,args.scene,parse(Path(args.source).read_text()))
            else: result=job.render(MeloLocal(args.melo_root))
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (CompanyError,OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps(dict(error=exc.code if isinstance(exc,CompanyError) else 'invalid_local_input_or_media'),ensure_ascii=False));return 2


if __name__=='__main__': raise SystemExit(main())
