# Exercises the text boundary, exact failing field, visual notes and private recovery log.
import io
import json
import pytest
from PIL import Image
from agent.leak_check import scan,scan_request,scan_endpoint,scan_log_keys,scan_frame_filename
from agent.policy import SYSTEM,tools
from agent.runner import request_payload
from engine.pybullet_robot import PyBulletRobot
from engine.server import create_app


def test_complete_payload_and_policy():
    scan(SYSTEM,'system');scan(tools(),'tools')
    event={'tool':'pickup','args':{},'result':{'success':True},'visual_memory':'red sphere left of centre'}
    payload=request_payload('Bring the red cube to the green square',[json.dumps(event)],None,None,None,False,1,'test')
    scan_request(payload)
    payload['system'][0]['text']+=' The green square is at x=2.'
    with pytest.raises(ValueError,match=r'\$\.system\[0\]\.text'):scan_request(payload)


@pytest.mark.parametrize('word',['red','sphere','target_x','zone','cube_x','object_id','object_count','object_positions'])
def test_banned_field_is_named(word):
    with pytest.raises(ValueError,match='unexpected'):
        scan({'unexpected':word},'request')
    with pytest.raises(ValueError,match=word):scan_log_keys({word:1},'log')


def test_model_notes_not_allowed_in_engine_results():
    call={'type':'tool_use','id':'1','name':'pickup','input':{'visual_memory':'red sphere'}}
    payload=request_payload('fetch',[],(call,{'success':True,'visual_memory':'red sphere'}),None,None,False,2,'test')
    with pytest.raises(ValueError,match='tool_result|content'):scan_request(payload)


def test_every_endpoint_and_all_frame_names():
    robot=PyBulletRobot(realtime=False)
    try:
        app=create_app(robot).test_client()
        for name in ('state','depth','look'):
            response=app.get('/'+name)
            scan_endpoint(name,response.data if name=='look' else response.json)
        for name,args in [('move',{'distance':.1}),('turn',{'degrees':10}),('pickup',{}),('drop',{})]:
            scan_endpoint(name,app.post('/'+name,json=args).json)
        for name in ('step_007.png','run1_step01.png'):scan_frame_filename(name)
        with pytest.raises(ValueError,match='filename'):scan_frame_filename('red_cube.png')
    finally:robot.close()


def test_recovery_and_complete_state_trace(tmp_path):
    r=PyBulletRobot(realtime=False,report=tmp_path/'evaluation.json')
    try:r.turn(180);r.move(5);r.move(.1);r.finish()
    finally:r.close()
    records=[json.loads(x) for x in (tmp_path/'engine_events.jsonl').read_text().splitlines()]
    contact=next(x for x in records if x['event']=='collision')
    recovery=next(x for x in records if x['event']=='recovery')
    assert contact['to_state']=='Blocked'
    assert contact['backoff_requested']==.1
    assert contact['backoff_actual']==pytest.approx(.1)
    assert recovery['recovery_angle']==45
    assert recovery['retries']==1
    assert recovery['state_after_recovery'] in ('Go to object','Blocked','Done')
    trace=[x['to_state'] for x in records if x['event']=='state']
    assert trace[0]=='Idle' and trace[-1]=='Done' and 'Blocked' in trace


def test_log_checker_rejects_extra_look_and_missing_recovery(tmp_path):
    from check_logs import check
    raw=io.BytesIO();Image.new('RGB',(640,480)).save(raw,'JPEG')
    Image.open(io.BytesIO(raw.getvalue())).save(tmp_path/'step_000.png')
    step={'step':1,'timestamp':'2026-11-05T00:00:00Z','tool':'pickup','args':{},
          'result':{'success':False},'frame_path':'step_000.png','visual_note':''}
    def save(name,records):
        (tmp_path/name).write_text(''.join(json.dumps(r)+'\n' for r in records))
    save('steps.jsonl',[step])
    save('requests.jsonl',[{'step':1,'mode':'dummy_not_sent',
         'payload':request_payload('fetch',[],None,raw.getvalue(),None,False,1,'test')}])
    save('engine_events.jsonl',[{'event':'state','to_state':'Idle'},{'event':'state','to_state':'Done'}])
    save('sensor_calls.jsonl',[{'endpoint':'look','result':{}},{'endpoint':'look','result':{}}])
    result={x['item']:x['status'] for x in check(tmp_path)}
    assert result['consecutive_looks']=='FAIL'
    save('sensor_calls.jsonl',[{'endpoint':'look','result':{}},
         {'endpoint':'move','result':{'collided':True,'moved':.5}},{'endpoint':'look','result':{}}])
    assert next(x for x in check(tmp_path) if x['item']=='collision_handling')['status']=='FAIL'
