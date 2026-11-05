# Runs the Claude tool loop or a clearly labelled scripted dummy with no API calls.
# Saves each image seen and every action; sends only validated results to the model.
import base64
import io
import json
import math
import time
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image
from .client import RobotClient
from .guard import validate_frame_name
from .policy import SYSTEM,tools,tool_choice
from .audit import record_request

DUMMY=[('move',{'distance':1.55}),('pickup',{}),('move',{'distance':-4.17}),('drop',{})]


def checked_action(name,args):
    schemas={t['name']:t['input_schema'] for t in tools()}
    if name not in schemas or not isinstance(args,dict) or set(args)!=(set(schemas[name]['properties'])-{'visual_memory'}):
        raise ValueError('Invalid model tool call')
    for key,value in args.items():
        limit=10 if key=='distance' else 360
        if type(value) not in (int,float) or not math.isfinite(value) or not -limit<=value<=limit:
            raise ValueError('Invalid model action argument')


def parse_model_action(call):
    # Visual notes are model-authored; only physical arguments reach the engine.
    args=dict(call['input'])
    memory=args.pop('visual_memory',None)
    if not isinstance(memory,str) or len(memory)>1200:
        raise ValueError('Missing or invalid visual memory')
    checked_action(call['name'],args)
    return call['name'],args,memory


def image_block(jpeg):
    return {'type':'image','source':{'type':'base64','media_type':'image/jpeg',
                                   'data':base64.b64encode(jpeg).decode('ascii')}}


def request_payload(command,history,previous,frame,depth,collision,step,model,robot_state=None):
    # Rebuild a small valid tool conversation. No earlier image survives.
    intro={'role':'user','content':[{'type':'text','text':json.dumps({
        'command':command,'recent_history':history[-12:], 'depth':depth,
        'collided':collision,'robot_state':robot_state,'step':step,'soft_target':25,'hard_stop':60})}]}
    if previous is None:
        if frame is not None:
            intro['content'].append(image_block(frame))
        messages=[intro]
    else:
        call,result=previous
        content=[{'type':'text','text':json.dumps(result)}]
        if frame is not None:
            content.append(image_block(frame))
        messages=[intro,{'role':'assistant','content':[call]},
            {'role':'user','content':[{'type':'tool_result','tool_use_id':call['id'],'content':content}]}]
    payload = dict(model=model,max_tokens=2048,
        system=[{'type':'text','text':SYSTEM,'cache_control':{'type':'ephemeral'}}],
        tools=tools(),tool_choice=tool_choice(model),messages=messages)
    # Keep model-compatible tool selection; reject anything other than one valid action.
    return payload


def run(command,folder,base='http://127.0.0.1:8080',dummy=False,model='claude-sonnet-5-5',sdk=None):
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    client=RobotClient(base)
    client.log_path=folder/'sensor_calls.jsonl'
    if not dummy and sdk is None:
        from anthropic import Anthropic
        sdk=Anthropic(max_retries=0, timeout=60.0) # no hidden extra billable calls per step
    frame=client.call('look')
    frame_path='step_000.png'
    def save_frame(name,data):
        validate_frame_name(name)
        with Image.open(io.BytesIO(data)) as im:
            im.save(folder/name,format='PNG')
    save_frame(frame_path,frame)
    def timing(step,phase,started):
        seconds=time.perf_counter()-started
        with (folder/'timings.jsonl').open('a',encoding='utf-8') as out:
            out.write(json.dumps({'step':step,'phase':phase,'elapsed_seconds':seconds})+'\n')
        return seconds
    history=[]
    previous=None
    collision=False
    with (folder/'steps.jsonl').open('w',encoding='utf-8') as log:
        for step in range(1,61):
            started=time.perf_counter()
            observation=client.call('state')
            if observation['state']=='Done':
                return {'steps':step-1,'stop':'engine_done','dummy':dummy}
            depth=client.call('depth')
            timing(step,'sensors',started)
            memory=''
            usage={}
            payload=request_payload(command,history,previous,frame,depth,collision,step,model,observation)
            record_request(folder,step,payload,dummy)
            if dummy:
                if step>len(DUMMY):
                    name,args='done',{}
                else:
                    name,args=DUMMY[step-1]
                call={'type':'tool_use','id':f'dummy_{step}','name':name,'input':{**args,'visual_memory':''}}
            else:
                api_started=time.perf_counter()
                try:
                    response=sdk.messages.create(**payload)
                except Exception:
                    # SDK error bodies can contain sensitive request details.
                    raise RuntimeError('Claude API request failed; check key, access, credit and network') from None
                finally:
                    elapsed=timing(step,'api',api_started)
                    print(f'Claude wait: {elapsed:.2f}s',flush=True)
                if getattr(response,'stop_reason',None) in ('max_tokens','refusal','pause_turn'):
                    return {'steps':step-1,'stop':'invalid_response','dummy':False}
                calls=[b for b in response.content if b.type=='tool_use']
                if len(calls)!=1:
                    return {'steps':step-1,'stop':'invalid_response','dummy':False}
                b=calls[0]
                call={'type':'tool_use','id':b.id,'name':b.name,'input':b.input}
                try:
                    name,args,memory=parse_model_action(call)
                except (ValueError,TypeError,KeyError):
                    return {'steps':step-1,'stop':'invalid_response','dummy':False}
                usage=response.usage.model_dump() if hasattr(response,'usage') else {}
            checked_action(name,args)
            action_started=time.perf_counter()
            if name=='done':
                stopped=observation['state']=='Done' or observation['retries']>=3
                result=({'stopped':True} if stopped else
                        {'stopped':False,'reason':'Run is active; continue visual search or recovery.'})
            else:
                result=client.call(name,args)
            timing(step,'action',action_started)
            record=dict(step=step,timestamp=datetime.now(timezone.utc).isoformat(),tool=name,
                        args=args,result=result,frame_path=frame_path if frame is not None else None,
                        visual_note=memory)
            log.write(json.dumps(record)+'\n');log.flush()
            print(f'{step:02d} {name} {json.dumps(args)} -> {json.dumps(result)}',flush=True)
            if usage:
                with (folder/'usage.jsonl').open('a',encoding='utf-8') as out:
                    out.write(json.dumps({'step':step,**usage})+'\n')
            history.append(json.dumps({'tool':name,'args':args,'result':result,'visual_memory':memory}))
            if name=='done' and result['stopped']:
                return {'steps':step,'stop':'agent_done','dummy':dummy}
            previous=(call,result)
            collision=result.get('collided', not result.get('ok',True))
            if name in ('move','turn'):
                # Exactly one /look after each executed motion; never after pickup/drop.
                image_started=time.perf_counter()
                frame=client.call('look')
                frame_path=f'step_{step:03d}.png'
                save_frame(frame_path,frame)
                timing(step,'image',image_started)
            else:
                frame=None
                frame_path=None
            if step==25:
                print('Soft target reached; continuing up to hard limit 60.',flush=True)
        return {'steps':60,'stop':'step_limit','dummy':dummy}
