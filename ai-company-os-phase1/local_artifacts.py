"""Allowlisted local artifact tools. Model text is never executable code or paths."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from autonomous_company import require, exact, text, now, CompanyError

VIDEO_TOOL = 'caption_video_v1'
TOOLS = {VIDEO_TOOL: {'network': False, 'uploads': False, 'audio': 'optional local espeak-ng Korean',
                     'input': 'JSON content: {tool,width,height,audio,scenes:[{text,seconds}]}',
                     'limits': 'even width/height 240..1920; 1..16 scenes; text <=120 chars/scene; duration <=120s'}}
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'


def run_command(args, timeout=180):
    try:
        return subprocess.run(args, check=True, capture_output=True, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        # Never persist process stderr or environment in project/model records.
        raise CompanyError('local_tool_failed') from None


def validate_video(spec):
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
        require(all(len(line)<=28 for line in scene['text'].split('\n')) and len(scene['text'].split('\n'))<=4,'caption_overflow')
        total+=scene['seconds']
    require(total<=120,'video_too_long')
    return total


def render_video(spec, folder):
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
                run_command(['espeak-ng','-v','ko','-s','155','-f',str(caption),'-w',str(wav)])
                voice=json.loads(run_command(['ffprobe','-v','error','-show_format','-of','json',str(wav)]))
                require(float(voice['format']['duration'])<=scene['seconds'],'narration_exceeds_scene')
                audio_args=['-i',str(wav),'-af','apad','-c:a','aac','-ar','44100','-ac','1']
            run_command(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
                f"color=c=0x142139:s={spec['width']}x{spec['height']}:r=24",
                *audio_args,'-vf',f"drawtext=fontfile={FONT}:textfile={caption}:expansion=none:fontcolor=white:fontsize={max(16,spec['width']//30)}:x=(w-text_w)/2:y=(h-text_h)/2",
                '-t',str(scene['seconds']),'-c:v','libx264','-threads','2','-pix_fmt','yuv420p',str(segment)])
        listing=work/'segments.txt';listing.write_text(''.join(f"file '{s.name}'\n" for s in segments))
        staged=work/'result.mp4'
        run_command(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','1','-i',str(listing),
                     '-c','copy','-movflags','+faststart',str(staged)])
        probe=json.loads(run_command(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(staged)]))
        streams=probe['streams'];video=streams[0];duration=float(probe['format']['duration'])
        require(len(streams)==(2 if spec['audio'] else 1) and video['codec_name']=='h264' and video['width']==spec['width']
                and video['height']==spec['height'] and abs(duration-total)<0.2,'video_probe_failed')
        run_command(['ffmpeg','-nostdin','-v','error','-i',str(staged),'-f','null','-'])
        staged.rename(output)
    return {'tool':VIDEO_TOOL,'at':now(),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'duration_seconds':duration,'width':video['width'],'height':video['height'],
            'codec':'h264','audio':spec['audio'],'decoded':True,'frames':int(video['nb_frames'])}


def execute(tool, spec, folder):
    require(tool in TOOLS and spec.get('tool')==tool,'tool_not_allowed')
    return render_video(spec,folder)
