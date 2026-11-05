# Verifies simulation-clock capture and actual FFmpeg output, including decoded overlay.
import json
import shutil
import pytest
from PIL import Image
from engine.recorder import POVRecorder
from export_clip import export,video_rules


def test_recorder_skips_thinking_time_and_stops_at_done(tmp_path):
    r=POVRecorder(tmp_path/'pov');frame=Image.new('RGB',(640,480),(70,80,90))
    r.capture(frame,0);assert not r.folder.exists()
    r.start(0,frame);r.capture(frame,0);r.capture(frame,.1)
    r.stop(.2,frame);r.capture(frame,1)
    rows=[json.loads(x) for x in (r.folder/'frames.jsonl').read_text().splitlines()]
    assert len(rows)==3
    assert [x['sim_seconds'] for x in rows]==[0,.1,.2]
    assert json.loads((r.folder/'recording.json').read_text())['complete'] is True


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'),reason='FFmpeg tools missing')
def test_real_h264_retime_overlay_and_package(tmp_path):
    from package_run import package
    r=POVRecorder(tmp_path/'pov');frame=Image.new('RGB',(640,480),(70,80,90))
    r.start(0,frame);r.stop(1,frame)
    (tmp_path/'summary.json').write_text(json.dumps({'command':'Bring the red cube to the green square',
        'mode':'dummy','dummy':True,'verdict':'PASS','evaluation':{'state':'Done'}}))
    import io
    from agent.runner import request_payload
    raw=io.BytesIO();frame.save(raw,'JPEG');frame.save(tmp_path/'step_000.png')
    (tmp_path/'steps.jsonl').write_text(json.dumps({'step':1,'timestamp':'2026-11-05T00:00:00Z',
        'tool':'pickup','args':{},'result':{'success':True},'frame_path':'step_000.png','visual_note':''})+'\n')
    payload=request_payload('Bring the red cube to the green square',[],None,raw.getvalue(),None,False,1,'test')
    (tmp_path/'requests.jsonl').write_text(json.dumps({'step':1,'mode':'dummy_not_sent','payload':payload})+'\n')
    (tmp_path/'engine_events.jsonl').write_text('')
    (tmp_path/'sensor_calls.jsonl').write_text('')
    report=export(tmp_path,10)
    assert all(report['rules'].values())
    assert report['retimed'] and report['natural_seconds']==1
    out=package(tmp_path,1,tmp_path/'submission')
    assert (out/'clips'/'command_1.mp4').is_file()
    assert (out/'prompts'/'full_trace_run1.json').is_file()
    with pytest.raises(ValueError,match='already packaged'):package(tmp_path,1,out)
    # A later file change cannot keep the earlier compliance certificate.
    with (tmp_path/'clip.mp4').open('ab') as f:f.write(b'changed')
    with pytest.raises(ValueError,match='changed after'):package(tmp_path,2,out)
