# Audits a finished run without calling Claude or executing simulation code.
# Missing evidence fails; a collision-free run is labelled as having no recovery proof.
import argparse
import json
from pathlib import Path
from agent.leak_check import scan_request,scan_log_keys,scan_frame_filename
from agent.audit import validate_payload


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def check(folder):
    folder=Path(folder)
    results=[]
    def item(name,ok,detail): results.append({'item':name,'status':'PASS' if ok else 'FAIL','detail':detail})
    steps=rows(folder/'steps.jsonl')
    required={'step','timestamp','tool','args','result','frame_path','visual_note'}
    item('step_count',0<len(steps)<=60 and [s.get('step') for s in steps]==list(range(1,len(steps)+1)),str(len(steps)))
    item('step_fields',all(set(s)==required and isinstance(s['visual_note'],str) for s in steps),'including visual_note')
    calls=rows(folder/'sensor_calls.jsonl')
    permitted=True;consecutive=0;looks=0;motions=0
    for call in calls:
        if call['endpoint'] in ('move','turn'):permitted=True;motions+=1
        if call['endpoint']=='look':
            looks+=1
            if not permitted:consecutive+=1
            permitted=False
    item('consecutive_looks',consecutive==0,str(consecutive))
    item('look_schedule',looks==1+motions,f'{looks} looks; {motions} motions')
    events=rows(folder/'engine_events.jsonl')
    trace=[e['to_state'] for e in events if e.get('event')=='state']
    item('state_trace',bool(trace) and trace[0]=='Idle' and trace[-1]=='Done',' -> '.join(trace))
    contacts=[e for e in events if e.get('event')=='collision']
    recovery={e['incident']:e for e in events if e.get('event')=='recovery' and e.get('incident') is not None}
    logged_contacts=sum(c['endpoint']=='move' and c['result'].get('collided',False) or
                        c['endpoint']=='turn' and c['result'].get('ok') is False for c in calls)
    ok=logged_contacts==0 or bool(contacts)
    for contact in contacts:
        follow=recovery.get(contact['incident'])
        terminal=trace[-1:] == ['Done'] and contact['retries']>=3
        ok &= (contact['to_state']=='Blocked' and contact['backoff_requested']==.1
               and 0<=contact['backoff_actual']<=.100001
               and (terminal or bool(follow and follow['recovery_angle'] in (45,-90,135)
                                     and 1<=follow['retries']<=3 and follow['state_after_recovery'])))
    item('collision_handling',bool(ok),f'{len(contacts)} collision records; '+('recovery evidence present' if contacts else 'no collision occurred; live recovery UNVERIFIED'))
    # Strict request validator + text scan; images are masked by scan_request.
    requests=rows(folder/'requests.jsonl') if (folder/'requests.jsonl').exists() else []
    modes={r.get('mode') for r in requests}
    if requests:
        for row in requests:validate_payload(row['payload']);scan_request(row['payload'])
    else:
        summary=json.loads((folder/'summary.json').read_text()) if (folder/'summary.json').exists() else {}
        if summary.get('mode')!='pixel':raise ValueError('Missing requests.jsonl for Claude/dummy mode')
    for file in folder.rglob('*.jsonl'):
        for row in rows(file):scan_log_keys(row,file.name)
    for file in folder.rglob('*.json'):
        scan_log_keys(json.loads(file.read_text()),file.name)
    for file in folder.rglob('*.png'):scan_frame_filename(file.name)
    for step in steps:
        if step['frame_path']:
            scan_frame_filename(step['frame_path'])
            frame=(folder/step['frame_path']).resolve()
            if not frame.is_relative_to(folder.resolve()) or not frame.is_file():
                raise ValueError('Missing or unsafe frame_path')
    item('leak_scan',True,'known command/model-note fields exempt; in_zone boolean permitted')
    item('request_count',not requests or len(requests)==len(steps),f'{len(requests)} requests; modes: {sorted(modes)}')
    return results


def main():
    parser=argparse.ArgumentParser();parser.add_argument('folder',nargs='?');args=parser.parse_args()
    if args.folder:folder=Path(args.folder)
    else:
        candidates=sorted((Path(__file__).parent/'logs').glob('*/steps.jsonl'))
        if not candidates:parser.error('No runs found')
        folder=candidates[-1].parent
    try:results=check(folder)
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print(f'FAIL audit: {exc}');return 1
    for r in results:print(f"{r['status']} {r['item']}: {r['detail']}")
    print('Live Claude recognition and recovery: UNVERIFIED by structural checks.')
    return int(any(r['status']=='FAIL' for r in results))


if __name__=='__main__':raise SystemExit(main())
