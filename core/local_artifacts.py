"""Allowlisted local artifact tools. Model text is never executable code or paths."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from copy import deepcopy
from autonomous_company import digest
from autonomous_company import require, exact, text, now, CompanyError

VIDEO_TOOL = 'caption_video_v1'
TOOLS = {VIDEO_TOOL: {'network': False, 'uploads': False, 'audio': 'optional local espeak-ng Korean',
                     'input': 'JSON content: {tool,width,height,audio,scenes:[{text,seconds}]}',
                     'limits': 'even integer width/height 240..1920; 1..16 scenes; audio boolean; '
                     'nonempty text <=120 chars/scene including newlines; each line <=28 chars; <=4 lines/scene; '
                     'only newline control character allowed; each seconds number 0.5..30; total duration <=120s',
                     'caption_layout': 'Write semantic lines using newline at word boundaries. Renderer may replace ASCII spaces '
                     'with newlines to fit 28 chars/line and 4 lines, without truncating or rewriting words. '
                     'Unbreakable words or too many lines stop the tool; shorten the draft yourself. '
                     'Local TTS must fit each scene duration or narration_exceeds_scene stops rendering.'}}
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'


COMMAND_STAGES=frozenset(('espeak_audio','ffprobe_audio','ffmpeg_segment','ffmpeg_concat','ffprobe_final','ffmpeg_decode'))


class LocalToolError(CompanyError):
    def __init__(self,stage,category,exit_code=None):
        require(stage in COMMAND_STAGES and category in (
            'executable_missing','timeout','exit_nonzero','os_error'),'invalid_local_tool_diagnostics')
        require(exit_code is None or type(exit_code) is int and -255<=exit_code<=255,'invalid_local_tool_exit_code')
        super().__init__('local_tool_failed')
        self.diagnostics={'stage':stage,'category':category,'exit_code':exit_code}


def run_command(args, timeout=180, *, stage, cwd=None):
    require(stage in COMMAND_STAGES,'invalid_local_tool_stage')
    try:
        options={'cwd':cwd} if cwd is not None else {}
        return subprocess.run(args, check=True, capture_output=True, timeout=timeout,**options).stdout
    except FileNotFoundError:
        raise LocalToolError(stage,'executable_missing') from None
    except subprocess.TimeoutExpired:
        raise LocalToolError(stage,'timeout') from None
    except subprocess.CalledProcessError as exc:
        code=exc.returncode if type(exc.returncode) is int and -255<=exc.returncode<=255 else None
        raise LocalToolError(stage,'exit_nonzero',code) from None
    except (OSError,subprocess.SubprocessError):
        # No stderr, command arguments, environment or paths enter diagnostics.
        raise LocalToolError(stage,'os_error') from None


def _validate_video(spec,check_layout):
    exact(spec, ('tool','width','height','audio','scenes'))
    require(spec['tool']==VIDEO_TOOL, 'tool_not_allowed')
    for k in ('width','height'):
        require(type(spec[k]) is int and 240<=spec[k]<=1920 and spec[k]%2==0, 'invalid_video_size')
    require(isinstance(spec['scenes'],list) and 1<=len(spec['scenes'])<=16,'invalid_scenes')
    require(type(spec['audio']) is bool,'invalid_audio')
    total=0
    for scene in spec['scenes']:
        exact(scene,('text','seconds'));text(scene['text'],120)
        require(not any(ord(c)<32 and c!='\n' for c in scene['text']),'invalid_caption')
        require(type(scene['seconds']) in (int,float) and 0.5<=scene['seconds']<=30,'invalid_duration')
        if check_layout:
            require(all(len(line)<=28 for line in scene['text'].split('\n')) and len(scene['text'].split('\n'))<=4,'caption_overflow')
        total+=scene['seconds']
    require(total<=120,'video_too_long')
    return total


def validate_video(spec):
    return _validate_video(spec,True)


def prepare_video(spec):
    """Layout only: replace ASCII spaces by newlines; never split/drop/rewrite words.

    Original spec remains the employee result. Offsets and hashes in the receipt
    reconstruct exactly which spaces were replaced in the rendered copy.
    """
    _validate_video(spec,False)
    rendered=deepcopy(spec);rendered['scenes']=[deepcopy(scene) for scene in spec['scenes']];changes=[]
    for index,scene in enumerate(rendered['scenes']):
        source=scene['text'];chars=list(source);offset=0;replaced=[]
        for line in source.split('\n'):
            start=0
            while len(line)-start>28:
                boundary=line.rfind(' ',start+1,start+29)
                require(boundary>start,'caption_overflow')
                chars[offset+boundary]='\n';replaced.append(offset+boundary)
                start=boundary+1
            offset+=len(line)+1
        scene['text']=''.join(chars)
        if replaced:
            changes.append({'scene_index':index,'space_to_newline_offsets':replaced,
                            'source_line_lengths':[len(v) for v in source.split('\n')],
                            'rendered_line_lengths':[len(v) for v in scene['text'].split('\n')]})
    validate_video(rendered)
    return rendered,{'source_input_hash':digest(spec),'rendered_input_hash':digest(rendered),'changes':changes}


def render_video(spec, folder):
    spec,reflow=prepare_video(spec)
    total=validate_video(spec)
    folder=Path(folder)
    require(folder.is_dir() and not folder.is_symlink(),'invalid_tool_directory')
    output=folder/'video.mp4'
    require(not output.exists() and not output.is_symlink(),'artifact_exists')
    require(Path(FONT).is_file(),'korean_font_missing')
    with tempfile.TemporaryDirectory(dir=folder) as temp:
        work=Path(temp);segments=[]
        for i,scene in enumerate(spec['scenes']):
            caption=work/(str(i)+'.txt');caption.write_text(scene['text'],encoding='utf-8')
            segment=work/(str(i)+'.mp4');segments.append(segment)
            # All filter syntax and paths are application-owned; textfile expansion is disabled.
            audio_args=['-an']
            if spec['audio']:
                wav=work/(str(i)+'.wav')
                # espeak-ng truncates long filename arguments in this build. Keep
                # both names short inside our own work directory; text is unchanged.
                run_command(['espeak-ng','-v','ko','-s','155','-f',caption.name,'-w',wav.name],
                            stage='espeak_audio',cwd=work)
                voice=json.loads(run_command(['ffprobe','-v','error','-show_format','-of','json',str(wav)],stage='ffprobe_audio'))
                require(float(voice['format']['duration'])<=scene['seconds'],'narration_exceeds_scene')
                audio_args=['-i',str(wav),'-af','apad','-c:a','aac','-ar','44100','-ac','1']
            run_command(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
                f"color=c=0x142139:s={spec['width']}x{spec['height']}:r=24",
                *audio_args,'-vf',f"drawtext=fontfile={FONT}:textfile={caption}:expansion=none:fontcolor=white:fontsize={max(16,spec['width']//30)}:x=(w-text_w)/2:y=(h-text_h)/2",
                '-t',str(scene['seconds']),'-c:v','libx264','-threads','2','-pix_fmt','yuv420p',str(segment)],stage='ffmpeg_segment')
        listing=work/'segments.txt';listing.write_text(''.join(f"file '{s.name}'\n" for s in segments))
        staged=work/'result.mp4'
        run_command(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','1','-i',str(listing),
                     '-c','copy','-movflags','+faststart',str(staged)],stage='ffmpeg_concat')
        probe=json.loads(run_command(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(staged)],stage='ffprobe_final'))
        streams=probe['streams'];video=streams[0];duration=float(probe['format']['duration'])
        require(len(streams)==(2 if spec['audio'] else 1) and video['codec_name']=='h264' and video['width']==spec['width']
                and video['height']==spec['height'] and abs(duration-total)<0.2,'video_probe_failed')
        run_command(['ffmpeg','-nostdin','-v','error','-i',str(staged),'-f','null','-'],stage='ffmpeg_decode')
        staged.rename(output)
    return {'tool':VIDEO_TOOL,'at':now(),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'duration_seconds':duration,'width':video['width'],'height':video['height'],
            'codec':'h264','audio':spec['audio'],'decoded':True,'frames':int(video['nb_frames']),
            'caption_reflow':reflow}


def execute(tool, spec, folder):
    require(tool in TOOLS and spec.get('tool')==tool,'tool_not_allowed')
    return render_video(spec,folder)
