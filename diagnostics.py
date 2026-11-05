# Runs separate camera, HTTP, API and visual-identification checks.
# Identification uses only a real /look image and the typed command; a person must
# review its answer. It never declares an autonomous delivery or recognition PASS.
import argparse
import io
import json
import os
import statistics
import time
from datetime import datetime
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv
from agent.client import RobotClient
from agent.runner import image_block

ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('test',choices=['camera','http','api','identify'])
    parser.add_argument('--gui',action='store_true')
    parser.add_argument('--base',default='http://127.0.0.1:8080')
    parser.add_argument('--model',default='claude-sonnet-5-5')
    parser.add_argument('--command',default='Bring the red cube to the green square')
    args=parser.parse_args()
    folder=ROOT/'logs'/('diagnostic_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    if args.test=='camera':
        from engine.pybullet_robot import PyBulletRobot
        robot=PyBulletRobot(gui=args.gui,realtime=False)
        try:
            before=robot.sim_time; raw=robot.look()
            with Image.open(io.BytesIO(raw)) as image:
                assert image.size==(640,480) and image.format=='JPEG'
                assert robot.sim_time==before
                folder.mkdir(parents=True); image.save(folder/'step_000.png')
            print('PASS: JPEG 640x480; camera read did not advance simulation.')
            print('Visually inspect:',folder/'step_000.png')
        finally:robot.close()
        return 0
    if args.test=='http':
        client=RobotClient(args.base)
        for endpoint in ('state','look'):
            samples=[]
            for _ in range(10):
                start=time.perf_counter();client.call(endpoint)
                samples.append(time.perf_counter()-start)
            print(f'{endpoint}: {statistics.mean(samples)*1000:.3f} ms mean end-to-end HTTP client time')
        print('Diagnostic reads only; no autonomous actions or Claude calls.')
        return 0
    load_dotenv(ROOT/'.env')
    if not os.environ.get('ANTHROPIC_API_KEY','').strip():
        parser.error('Set ANTHROPIC_API_KEY in the local project .env. Never share the key.')
    from anthropic import Anthropic
    sdk=Anthropic(max_retries=0,timeout=60.0)
    try:
        if args.test=='api':
            # Read-only model lookup verifies authentication and model visibility.
            result=sdk.models.retrieve(args.model)
            print('PASS: authenticated model lookup:',result.id)
            print('This does not test image recognition or a billable generation request.')
            return 0
        client=RobotClient(args.base)
        raw=client.call('look')
        payload={'model':args.model,'max_tokens':1024,
            'system':'Inspect only the supplied camera pixels. State whether the requested item and destination are visible, describe supporting visible evidence and their image-relative directions. If uncertain or outside the view, say so. Do not invent a scene inventory or world coordinates.',
            'messages':[{'role':'user','content':[{'type':'text','text':args.command},image_block(raw)]}]}
        if args.model=='claude-sonnet-5-5':payload['thinking']={'type':'between_tools'}
        folder.mkdir(parents=True)
        Image.open(io.BytesIO(raw)).save(folder/'step_000.png')
        (folder/'identification_request.json').write_text(json.dumps(payload),encoding='utf-8')
        response=sdk.messages.create(**payload)
        answer='\n'.join(b.text for b in response.content if b.type=='text')
        if not answer or response.stop_reason in ('max_tokens','refusal'):
            raise ValueError('Identification did not return a complete answer')
        (folder/'identification_response.txt').write_text(answer,encoding='utf-8')
        print(answer)
        print('REVIEW REQUIRED: compare this answer with',folder/'step_000.png')
        print('One standalone vision diagnostic, not a fetching run. No movement was executed.')
        return 0
    except Exception as exc:
        print(f'ERROR: {type(exc).__name__}. Check key, model access, credits and network. Raw API errors are suppressed.')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
