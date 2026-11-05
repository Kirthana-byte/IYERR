# Checks actual endpoint schemas and rejects injected scene data before model input.
# Generic visual instructions and user-supplied descriptions are not engine leaks.
import json
import pytest
from agent.guard import validate_result,validate_frame_name
from agent.policy import SYSTEM,tools
from agent.runner import request_payload
from engine.server import create_app
from engine.pybullet_robot import PyBulletRobot

BANNED_KEYS=['objects','object_ids','object_count','target_position','drop_zone_coordinates',
             'segmentation','colour','shape','distance_to_target','object_name']


def test_endpoint_allowlist():
    r=PyBulletRobot(realtime=False)
    try:
        c=create_app(r).test_client()
        for endpoint in ('state','depth'):
            validate_result(endpoint,c.get('/'+endpoint).json)
        for endpoint,args in [('move',{'distance':.1}),('turn',{'degrees':10}),('pickup',{}),('drop',{})]:
            validate_result(endpoint,c.post('/'+endpoint,json=args).json)
        image=c.get('/look')
        assert image.content_type=='image/jpeg'
        for key in BANNED_KEYS:
            assert key.encode() not in image.data
    finally:r.close()


@pytest.mark.parametrize('key',BANNED_KEYS)
def test_engine_metadata_injection_rejected(key):
    with pytest.raises(ValueError):validate_result('move',{'collided':False,'moved':1,key:'secret'})


def test_prompt_tools_and_names():
    # Reject concrete scene facts, not the word "object" needed to explain the task.
    serialized=SYSTEM+'\n'+json.dumps(tools())
    for fact in ('red cube','blue sphere','yellow cylinder','green square','objects','target_position','segmentation'):
        assert fact not in serialized.lower()
    for t in tools():
        assert set(t['input_schema']['properties'])<= {'distance','degrees','visual_memory'}
    validate_frame_name('step_007.png')
    with pytest.raises(ValueError):validate_frame_name('red_cube.png')


def test_tool_result_image_and_no_earlier_images():
    call={'type':'tool_use','id':'t1','name':'move','input':{'distance':.1}}
    payload=request_payload('fetch',[],(call,{'collided':False,'moved':.1}),b'pixels',None,False,2,'test')
    block=payload['messages'][-1]['content'][0]
    assert block['type']=='tool_result'
    assert [x['type'] for x in block['content']]==['text','image']
    assert json.dumps(payload).count('"type": "image"')==1
    no_image=request_payload('fetch',[],(call,{'success':True}),None,None,False,3,'test')
    assert '"type": "image"' not in json.dumps(no_image)


def test_outgoing_audit_rejects_injected_engine_field():
    from agent.audit import validate_payload
    payload=request_payload('fetch',[],None,None,None,False,1,'test')
    intro=json.loads(payload['messages'][0]['content'][0]['text'])
    intro['objects']=[{'colour':'red','position':[2,0]}]
    payload['messages'][0]['content'][0]['text']=json.dumps(intro)
    with pytest.raises(ValueError):validate_payload(payload)


def test_outgoing_audit_rejects_modified_tools():
    from agent.audit import validate_payload
    payload=request_payload('fetch',[],None,None,None,False,1,'test')
    payload['tools'][0]['description']='The target is at a hidden position'
    with pytest.raises(ValueError):validate_payload(payload)


def test_outgoing_audit_rejects_history_metadata():
    from agent.audit import validate_payload
    event={'tool':'move','args':{'distance':1},'result':{'collided':False,'moved':1,'target_position':[2,0]},'visual_memory':''}
    payload=request_payload('fetch',[json.dumps(event)],None,None,None,False,1,'test')
    with pytest.raises(ValueError):validate_payload(payload)
