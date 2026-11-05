# Rechecks saved outbound request bodies and their one-image-after-motion schedule.
# Passing means the structural checks passed, not a formal proof or live success.
import argparse
import json
from pathlib import Path
from agent.audit import validate_payload


def check(folder):
    path=Path(folder)/'requests.jsonl'
    rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    if not rows:raise ValueError('No requests to audit')
    modes=set()
    for index,row in enumerate(rows,1):
        if row['step']!=index:raise ValueError('Request steps are not consecutive')
        validate_payload(row['payload'])
        messages=row['payload']['messages']
        images=sum(block.get('type')=='image' for message in messages for block in message['content'])
        if len(messages)==3:
            content=messages[2]['content'][0]['content']
            images+=sum(block.get('type')=='image' for block in content)
            last_tool=messages[1]['content'][0]['name']
            expected=int(last_tool in ('move','turn'))
        else:expected=1
        if images!=expected:raise ValueError('Image schedule violation')
        modes.add(row['mode'])
    return len(rows),modes


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('folder',nargs='?',help='Defaults to latest run containing requests.jsonl')
    args=parser.parse_args()
    if args.folder:
        folder=Path(args.folder)
    else:
        candidates=sorted((Path(__file__).parent/'logs').glob('*/requests.jsonl'))
        if not candidates:parser.error('No request audit logs yet. Run the updated program first.')
        folder=candidates[-1].parent
    try:
        count,modes=check(folder)
    except (ValueError,KeyError,OSError) as exc:
        parser.exit(1,f'AUDIT FAIL: {exc}\n')
    print(f'AUDIT PASS: {count} requests; modes: {sorted(modes)}; folder: {folder}')
    print('Review text and images too. A dummy audit is not evidence of live Claude behaviour.')
