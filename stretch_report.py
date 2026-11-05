# Builds an evidence-based report; API attempts and dummy success never prove autonomy.
import json
from pathlib import Path


def generate(folder,output):
    folder=Path(folder);summary=json.loads((folder/'summary.json').read_text())
    steps=[json.loads(x) for x in (folder/'steps.jsonl').read_text().splitlines()]
    requests=[json.loads(x) for x in (folder/'requests.jsonl').read_text().splitlines()] if (folder/'requests.jsonl').exists() else []
    tool_names=sorted({t['name'] for r in requests for t in r['payload'].get('tools',[])})
    actions=[s['tool'] for s in steps];motion=[x for x in actions if x in ('move','turn','go_to')]
    mode=summary.get('mode','dummy' if summary.get('dummy') else 'claude')
    text=f'''## Run mode: {mode}

Implemented: Claude chooses movement through move and turn; no go_to tool is defined.
Recorded tool names: {', '.join(tool_names) or 'No Claude tool requests recorded'}.
Recorded motion actions: {', '.join(motion) or 'None'}.
go_to absent from recorded tools/actions: {'YES' if 'go_to' not in tool_names+actions else 'NO'}.
Recorded run result: {summary.get('verdict','UNVERIFIED')}.

Live Claude path planning: UNVERIFIED. A live_attempt row proves an attempted
request, not successful vision reasoning. Dummy/pixel results are TEST ONLY.
Mentor review of actual live requests, visual notes, images and successful delivery
is required before awarding this stretch goal. No obstacle scene is claimed.
'''
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(text,encoding='utf-8')
    return text
