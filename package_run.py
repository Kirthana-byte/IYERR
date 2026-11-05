# Copies one finished run into the submission layout without inventing missing evidence.
# Dummy/pixel runs are labelled test-only. Invalid clips must be explicitly retimed first.
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from agent.leak_check import without_images
from export_clip import video_rules

SETTINGS='''# Membrane robot submission

Camera: JPEG 640x480, 90-degree horizontal FOV, front mount 0.5 m high,
10 degrees down. Depth: single camera-centre ray, max 10 m, scalar or null.
Motion: 1 m/s, 90 degrees/s. Pickup: centre distance <=0.5 m, bearing +/-30 degrees.
Collision: stop and request 0.1 m backoff; actual backoff can be obstructed and is logged.
Physics advances only during move/turn. Rear snap attachment keeps the front camera clear.
Recorded camera frames are scaled with preserved aspect ratio into 1280x720 H.264,
no audio. The typed command is the only added text, during the first 2 seconds.
Explicit retiming, if used, is disclosed in clip_check_runN.json.

From the source project in Windows PowerShell:

```powershell
& $robotPython -m pytest -q
& $robotPython run_command.py "YOUR COMMAND" --gui
& $robotPython check_logs.py "logs\\RUN_FOLDER"
& $robotPython export_clip.py "logs\\RUN_FOLDER" --retime 12
& $robotPython package_run.py "logs\\RUN_FOLDER" 1
```

Omit --retime when natural duration is already 10-20 s. Claude requires a local
.env with ANTHROPIC_API_KEY. Never include that file in the submission.
--dummy is scripted plumbing; --pixel is TEST ONLY. Neither proves Claude autonomy.
Full API request traces replace binary images with placeholders; exact original
requests remain in local logs. engine_events files provide the complete state and
recovery trace without changing the required action-log schema.
Live Claude fetching/recognition: UNVERIFIED until independently reviewed.
'''


def package(folder,number,destination='submission'):
    folder=Path(folder).resolve();destination=Path(destination).resolve()
    if not 1<=number<=999:raise ValueError('Run number must be 1..999')
    summary=json.loads((folder/'summary.json').read_text())
    if summary.get('evaluation',{}).get('state')!='Done':raise ValueError('Only finished runs can be packaged')
    clip=folder/'clip.mp4';report=json.loads((folder/'clip_check.json').read_text())
    if hashlib.sha256(clip.read_bytes()).hexdigest()!=report['sha256']:
        raise ValueError('Clip changed after validation; export/check it again')
    rules,_=video_rules(clip,report['rules'].get('overlay',False))
    if not all(rules.values()):raise ValueError('Clip failed checks; optionally run export_clip.py RUN --retime 12 first')
    paths={
        'actions':destination/'logs'/f'command_{number}.jsonl',
        'events':destination/'logs'/f'engine_events_run{number}.jsonl',
        'sensors':destination/'logs'/f'sensor_calls_run{number}.jsonl',
        'trace':destination/'prompts'/f'full_trace_run{number}.json',
        'clip':destination/'clips'/f'command_{number}.mp4',
        'check':destination/'clips'/f'clip_check_run{number}.json',
        'summary':destination/'logs'/f'summary_run{number}.json'}
    if any(p.exists() for p in paths.values()):raise ValueError('Run number already packaged; use a new number/destination')
    requests=[]
    if (folder/'requests.jsonl').exists():
        requests=[json.loads(line) for line in (folder/'requests.jsonl').read_text().splitlines()]
    steps=[json.loads(line) for line in (folder/'steps.jsonl').read_text().splitlines()]
    if not steps:raise ValueError('Missing action evidence')
    if not requests and summary.get('mode')!='pixel':raise ValueError('Missing Claude/dummy request trace')
    copies={}
    for step in steps:
        if step['frame_path']:
            src=(folder/step['frame_path']).resolve()
            if not src.is_relative_to(folder) or not src.is_file():raise ValueError('Unsafe or missing frame path')
            if src not in copies:copies[src]=f'run{number}_step{len(copies):02d}.png'
            step['frame_path']='frames/'+copies[src]
    for p in paths.values():p.parent.mkdir(parents=True,exist_ok=True)
    (destination/'logs'/'frames').mkdir(exist_ok=True)
    for src,name in copies.items():shutil.copy2(src,destination/'logs'/'frames'/name)
    paths['actions'].write_text(''.join(json.dumps(s)+'\n' for s in steps),encoding='utf-8')
    for key,name in [('events','engine_events.jsonl'),('sensors','sensor_calls.jsonl'),('summary','summary.json')]:
        shutil.copy2(folder/name,paths[key])
    paths['trace'].write_text(json.dumps(without_images(requests),indent=2),encoding='utf-8')
    prompt='\n'.join(b['text'] for b in requests[0]['payload']['system']) if requests else 'No Claude requests: TEST ONLY pixel mode.\n'
    # Keep per-run prompts too, since model policy may change between submissions.
    (destination/'prompts'/f'system_prompt_run{number}.txt').write_text(prompt,encoding='utf-8')
    main_prompt=destination/'prompts'/'system_prompt.txt'
    if not main_prompt.exists():main_prompt.write_text(prompt,encoding='utf-8')
    shutil.copy2(clip,paths['clip']);shutil.copy2(folder/'clip_check.json',paths['check'])
    (destination/'README.md').write_text(SETTINGS,encoding='utf-8')
    stretch=destination/'stretch_goal';stretch.mkdir(exist_ok=True)
    from stretch_report import generate
    generate(folder,stretch/f'run{number}.md')
    reports=sorted(stretch.glob('run*.md'))
    (stretch/'report.md').write_text('# Path-planning evidence\n\n'+ '\n\n'.join(p.read_text() for p in reports),encoding='utf-8')
    print(f'PASS packaged {destination}; mode={summary.get("mode","dummy" if summary.get("dummy") else "claude")}; live Claude UNVERIFIED')
    return destination


def main():
    parser=argparse.ArgumentParser();parser.add_argument('folder');parser.add_argument('number',type=int)
    parser.add_argument('--out',default='submission');args=parser.parse_args()
    try:package(args.folder,args.number,args.out);return 0
    except (OSError,ValueError,KeyError) as exc:print(f'FAIL package: {exc}');return 1


if __name__=='__main__':raise SystemExit(main())
