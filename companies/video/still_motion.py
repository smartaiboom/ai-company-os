"""Normalize a bounded PNG/JPEG and make clearly labelled illustrative motion."""
from pathlib import Path
import shutil
import struct

from autonomous_company import require
from local_artifacts import run_command
from production_video import portrait_font

MAX_BYTES=8*1024*1024
MAX_PIXELS=12_000_000
MOTIONS=('pan','zoom','cut')


def image_dimensions(path,mime):
    path=Path(path)
    require(path.is_file() and not path.is_symlink() and 16<=path.stat().st_size<=MAX_BYTES,
            'still_image_size_invalid')
    raw=path.read_bytes()
    if mime=='image/png':
        require(raw[:8]==b'\x89PNG\r\n\x1a\n' and raw[8:16]==b'\0\0\0\rIHDR' and len(raw)>=33,
                'still_image_format_invalid')
        width,height=struct.unpack('>II',raw[16:24])
        cursor=8
        ended=False
        while cursor+12<=len(raw):
            size=int.from_bytes(raw[cursor:cursor+4],'big')
            tag=raw[cursor+4:cursor+8]
            cursor+=size+12
            require(cursor<=len(raw) and tag not in (b'acTL',b'fcTL',b'fdAT'),'still_image_format_invalid')
            if tag==b'IEND':
                ended=True
                break
        require(ended and cursor==len(raw),'still_image_format_invalid')
    else:
        require(mime=='image/jpeg' and raw[:2]==b'\xff\xd8' and raw[-2:]==b'\xff\xd9','still_image_format_invalid')
        cursor=2
        width=height=0
        while cursor+4<=len(raw) and raw[cursor]==255:
            cursor+=1
            while cursor<len(raw) and raw[cursor]==255:
                cursor+=1
            if cursor+3>len(raw):
                break
            marker=raw[cursor]
            size=int.from_bytes(raw[cursor+1:cursor+3],'big')
            require(2<=size and cursor+1+size<=len(raw),'still_image_format_invalid')
            if marker in (192,193,194):
                require(size>=8,'still_image_format_invalid')
                height,width=struct.unpack('>HH',raw[cursor+4:cursor+8])
                break
            if marker==218:
                break
            cursor+=1+size
    require(16<=width<=4096 and 16<=height<=4096 and width*height<=MAX_PIXELS,'still_image_pixels_invalid')
    return width,height


def render_stills(images, frames, motion, label, folder):
    require(type(frames) is int and 24<=frames<=2880 and 1<=len(images)<=3 and frames>=len(images)*24
            and motion in MOTIONS and label in ('illustration','reference'),'invalid_source_edit')
    font=portrait_font()
    require(font is not None,'portrait_korean_font_missing')
    shutil.copyfile(font[0],folder/'label-font.ttf')
    (folder/'label.txt').write_text({'illustration':'설명 이미지 · 실제 플레이 영상 아님',
                                    'reference':'참고 이미지 · 실제 플레이 영상 아님'}[label])
    chunks=[]
    cursor=0
    for index,(source,mime) in enumerate(images):
        image_dimensions(source,mime)
        normalized=f'normalized-{index}.png'
        run_command(['ffmpeg','-nostdin','-v','error','-xerror','-max_alloc','96000000','-threads','1',
                     '-protocol_whitelist','file,pipe','-f','png_pipe' if mime=='image/png' else 'jpeg_pipe',
                     '-i',str(source),'-map_metadata','-1','-frames:v','1','-c:v','png',normalized],
                    cwd=folder,stage='ffmpeg_decode',timeout=15)
        boundary=round((index+1)*frames/len(images))
        # One terminal frame lets the existing MP4 importer handle container duration rounding.
        count=boundary-cursor+(index==len(images)-1)
        cursor=boundary
        canvas=('scale=720:1280:force_original_aspect_ratio=decrease:force_divisible_by=2,'
                'pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=0x101820,setsar=1')
        zoom={'cut':'1','zoom':f'1+0.07*on/{count}','pan':'1.07'}[motion]
        xpos=f'(iw-iw/zoom)*on/{count}' if motion=='pan' else 'iw/2-iw/zoom/2'
        draw=('drawbox=x=0:y=104:w=iw:h=70:color=black@0.78:t=fill,'
              'drawtext=fontfile=label-font.ttf:textfile=label.txt:expansion=none:'
              'fontcolor=white:fontsize=30:x=(w-tw)/2:y=124')
        filename=f'segment-{index}.mp4'
        run_command(['ffmpeg','-nostdin','-v','error','-filter_threads','1','-i',normalized,'-vf',
            f"{canvas},zoompan=z='{zoom}':x='{xpos}':y='ih/2-ih/zoom/2':d={count}:s=720x1280:fps=24,{draw}",
            '-frames:v',str(count),'-c:v','libx264','-threads','2','-preset','veryfast',
            '-pix_fmt','yuv420p',filename],cwd=folder,stage='ffmpeg_segment',timeout=45)
        chunks.append(f"file '{filename}'\n")
    (folder/'concat.txt').write_text(''.join(chunks))
    run_command(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','1','-i','concat.txt','-c','copy','motion.mp4'],
                cwd=folder,stage='ffmpeg_segment',timeout=15)
    return folder/'motion.mp4'
