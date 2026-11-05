# Exports simulation-time POV frames to H.264, with only the command for 2 seconds.
# Retiming is explicit: --retime 12 changes playback speed, never the action evidence.
import argparse
import bisect
import hashlib
import io
import json
import math
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import numpy as np


def probe(path):
    if not shutil.which('ffprobe'):raise RuntimeError('Install FFmpeg (ffmpeg and ffprobe on PATH)')
    result=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],
                          capture_output=True,text=True,timeout=30,check=True)
    return json.loads(result.stdout)


def video_rules(path,overlay_ok):
    info=probe(path);video=next((s for s in info['streams'] if s['codec_type']=='video'),{})
    duration=float(info['format'].get('duration',0))
    return {'duration':10<=duration<=20.0001,
            'resolution':video.get('width',0)>=1280 and video.get('height',0)>=720,
            'codec':video.get('codec_name')=='h264',
            'audio':not any(s['codec_type']=='audio' for s in info['streams']),
            'overlay':bool(overlay_ok)},duration


def font(size):
    for name in ('C:/Windows/Fonts/segoeui.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(name).exists():return ImageFont.truetype(name,size)
    return ImageFont.load_default(size=size)


def make_frame(source,command,overlay):
    # Preserve the 4:3 camera geometry inside a 16:9 canvas; never stretch perception.
    with Image.open(source) as image:
        if image.size!=(640,480):raise ValueError('Recording contains a non-640x480 frame')
        image=image.convert('RGB').resize((960,720),Image.Resampling.LANCZOS)
    canvas=Image.new('RGB',(1280,720),'black');canvas.paste(image,(160,0))
    if overlay:
        draw=ImageDraw.Draw(canvas)
        lines=textwrap.wrap(command,width=72,replace_whitespace=False) or ['']
        size=min(30,max(14,170//len(lines)))
        face=font(size);line_height=size+8;bottom=16+len(lines)*line_height
        draw.rectangle((0,0,1279,bottom),fill='black')
        for i,line in enumerate(lines):draw.text((24,8+i*line_height),line,font=face,fill='white')
    return canvas


def decoded_frame(path,seconds):
    result=subprocess.run(['ffmpeg','-v','error','-ss',str(seconds),'-i',str(path),
        '-frames:v','1','-f','image2pipe','-vcodec','png','-threads','1','-'],capture_output=True,timeout=30,check=True)
    return Image.open(io.BytesIO(result.stdout)).convert('RGB')


def export(folder,retime=None):
    folder=Path(folder).resolve();source=folder/'pov'
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise RuntimeError('Install FFmpeg and add ffmpeg/ffprobe to PATH; saved raw frames remain available')
    manifest=json.loads((source/'recording.json').read_text())
    if not manifest['complete']:raise ValueError('Recording did not reach Done; refusing a partial clip')
    frames=[json.loads(line) for line in (source/'frames.jsonl').read_text().splitlines()]
    if not frames:raise ValueError('No POV frames')
    for row in frames:
        path=(source/row['frame_path']).resolve()
        if not path.is_relative_to(source) or not path.is_file():raise ValueError('Unsafe or missing POV frame')
    start=manifest['start_sim_seconds'];natural=manifest['end_sim_seconds']-start
    if natural<=0:raise ValueError('No positive simulation duration to record')
    if retime is not None and (not math.isfinite(retime) or not 10<=retime<=20):
        raise ValueError('--retime must be between 10 and 20 seconds')
    duration=retime if retime is not None else natural
    if duration>600:raise ValueError('Recording too long; explicitly choose --retime 10..20')
    summary=json.loads((folder/'summary.json').read_text())
    command=summary['command']
    if not isinstance(command,str) or not command.strip() or len(command)>500:
        raise ValueError('Command must contain 1..500 characters for the readable overlay')
    count=max(1,math.ceil(duration*30-1e-7));times=[r['sim_seconds'] for r in frames]
    def source_at(t):
        index=max(0,bisect.bisect_right(times,start+min(t/duration,1)*natural)-1)
        return source/frames[index]['frame_path']
    output=folder/'clip.mp4';temporary=folder/'clip_pending.mp4'
    with tempfile.TemporaryFile() as errors:
        process=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24',
            '-s','1280x720','-r','30','-i','pipe:0','-an','-c:v','libx264','-threads','2',
            '-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(temporary)],
            stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=errors)
        try:
            for i in range(count):
                process.stdin.write(make_frame(source_at(i/30),command,i<60).tobytes())
            process.stdin.close()
            if process.wait(timeout=90)!=0:raise RuntimeError('FFmpeg H.264 encoder failed')
        except BaseException:
            process.kill();process.wait();temporary.unlink(missing_ok=True);raise
    temporary.replace(output)
    # Compare decoded video pixels with the commanded overlay, not a metadata promise.
    samples=[t for t in (0,1,59/30,61/30) if t<count/30]
    overlay_ok=len(samples)==4
    differences=[]
    for t in samples:
        actual=np.asarray(decoded_frame(output,t),dtype=np.int16)
        clean=np.asarray(make_frame(source_at(t),command,False),dtype=np.int16)
        marked=np.asarray(make_frame(source_at(t),command,True),dtype=np.int16)
        mask=np.max(np.abs(marked-clean),axis=2)>30
        expected=marked if t<2 else clean
        error=float(np.abs(actual-expected)[mask].mean()) if mask.sum()>100 else 999.0
        differences.append(error);overlay_ok &= error<12
    rules,actual_duration=video_rules(output,overlay_ok)
    report={'rules':rules,'duration_seconds':actual_duration,'natural_seconds':natural,
            'retimed':retime is not None,'playback_speed':natural/duration,
            'overlay_pixel_errors':differences,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
            'mode':summary.get('mode','dummy' if summary.get('dummy') else 'claude'),
            'live_claude':'UNVERIFIED'}
    (folder/'clip_check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for name,ok in rules.items():print(f"{'PASS' if ok else 'FAIL'} clip_{name}")
    print(f'Clip duration: {actual_duration:.3f}s; recorded simulation: {natural:.3f}s')
    if not rules['duration']:
        print(f'Optional retiming: python export_clip.py "{folder}" --retime 12')
    print('Branding/content: raw onboard frames only; manual review of the scene and command remains required.')
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('folder');parser.add_argument('--retime',type=float)
    args=parser.parse_args()
    try:return int(not all(export(args.folder,args.retime)['rules'].values()))
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:
        print(f'FAIL clip_export: {exc}');return 1


if __name__=='__main__':raise SystemExit(main())
