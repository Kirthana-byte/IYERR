# Checks the exact outgoing request structure and stores it locally for inspection.
# No API key or HTTP headers are included. User commands and Claude-authored visual
# notes may contain appearance descriptions; engine metadata may not.
import base64
import io
import json
from pathlib import Path
from PIL import Image
from .guard import validate_result
from .policy import SYSTEM,tools,tool_choice


def validate_payload(payload):
    from .runner import checked_action,parse_model_action
    if set(payload)!={'model','max_tokens','system','tools','tool_choice','messages'}:
        raise ValueError('Unexpected model request fields')
    if payload['system']!=[{'type':'text','text':SYSTEM,'cache_control':{'type':'ephemeral'}}]:
        raise ValueError('System prompt changed outside reviewed policy')
    if payload['tools']!=tools():
        raise ValueError('Unexpected tool schema')
    if payload['tool_choice']!=tool_choice(payload['model']):
        raise ValueError('Expected one tool per step')
    messages=payload['messages']
    if len(messages) not in (1,3) or messages[0]['role']!='user':
        raise ValueError('Unexpected conversation shape')
    intro=json.loads(messages[0]['content'][0]['text'])
    if set(intro)!={'command','recent_history','depth','collided','robot_state','step','soft_target','hard_stop'}:
        raise ValueError('Unexpected observation fields')
    if not isinstance(intro['command'],str) or type(intro['collided']) is not bool:
        raise ValueError('Invalid command or collision flag')
    validate_result('depth',intro['depth'])
    if intro['robot_state'] is not None:
        validate_result('state',intro['robot_state'])
    for line in intro['recent_history']:
        event=json.loads(line)
        if set(event)!={'tool','args','result','visual_memory'} or not isinstance(event['visual_memory'],str):
            raise ValueError('Unexpected history fields')
        checked_action(event['tool'],event['args'])
        check_tool_result(event['tool'],event['result'])
    blocks=messages[0]['content'][1:]
    if len(messages)==3:
        if messages[1]['role']!='assistant' or messages[2]['role']!='user':
            raise ValueError('Invalid tool conversation roles')
        if len(messages[1]['content'])!=1 or len(messages[2]['content'])!=1:
            raise ValueError('Unexpected tool count')
        call=messages[1]['content'][0]
        if set(call)!={'type','id','name','input'} or call['type']!='tool_use':
            raise ValueError('Invalid tool call fields')
        parse_model_action(call)
        result=messages[2]['content'][0]
        if set(result)!={'type','tool_use_id','content'} or result['type']!='tool_result' or result['tool_use_id']!=call['id']:
            raise ValueError('Invalid tool result fields')
        check_tool_result(call['name'],json.loads(result['content'][0]['text']))
        blocks+=result['content'][1:]
    if len(blocks)>1:
        raise ValueError('More than one image in context')
    for block in blocks:
        if set(block)!={'type','source'} or block['type']!='image':
            raise ValueError('Unexpected extra content')
        source=block['source']
        if set(source)!={'type','media_type','data'} or source['type']!='base64' or source['media_type']!='image/jpeg':
            raise ValueError('Unexpected image fields')
        raw=base64.b64decode(source['data'],validate=True)
        with Image.open(io.BytesIO(raw)) as im:
            if im.format!='JPEG' or im.size!=(640,480) or im.getexif() or 'comment' in im.info:
                raise ValueError('Unexpected image format or metadata')


def check_tool_result(name,result):
    if name=='done':
        if result!={'stopped':True} and result!={'stopped':False,'reason':'Run is active; continue visual search or recovery.'}:
            raise ValueError('Unexpected stop response')
    else:
        validate_result(name,result)


def record_request(folder,step,payload,dummy):
    validate_payload(payload)
    from .leak_check import scan_request
    scan_request(payload)
    with (Path(folder)/'requests.jsonl').open('a',encoding='utf-8') as out:
        out.write(json.dumps({'step':step,'mode':'dummy_not_sent' if dummy else 'live_attempt',
                              'payload':payload})+'\n')
