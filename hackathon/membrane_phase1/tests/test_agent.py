# Tests the real agent loop with an injected API stand-in: no key and no network.
# Verifies one call per step, image scheduling, log fields and the hard stop.
import io
import json
from types import SimpleNamespace
from PIL import Image
import pytest
from agent import runner


class FakeClient:
    instances=[]
    def __init__(self,*args):
        self.calls=[]
        self.__class__.instances.append(self)
    def call(self,name,args=None):
        self.calls.append((name,args))
        if name=='look':
            out=io.BytesIO();Image.new('RGB',(640,480)).save(out,'JPEG');return out.getvalue()
        if name=='state':
            return {'state':'Locate','x':0,'y':0,'heading':0,'holding':False,'retries':0}
        if name=='depth':return None
        return {'move':{'collided':False,'moved':.1},'turn':{'ok':True,'heading':10},
                'pickup':{'success':False},'drop':{'in_zone':False}}[name]


class FakeSDK:
    def __init__(self,actions):
        self.actions=iter(actions)
        self.payloads=[]
        self.messages=self
    def create(self,**kwargs):
        self.payloads.append(kwargs)
        name,args=next(self.actions)
        return SimpleNamespace(content=[SimpleNamespace(type='tool_use',id=str(len(self.payloads)),
                                                       name=name,input={**args,'visual_memory':'Camera observations retained.'})])


def test_image_schedule_and_log(monkeypatch,tmp_path):
    monkeypatch.setattr(runner,'RobotClient',FakeClient)
    sdk=FakeSDK([('move',{'distance':.1}),('pickup',{}),('turn',{'degrees':10}),('drop',{}),('done',{})]+[('done',{})]*55)
    result=runner.run('fetch',tmp_path,sdk=sdk)
    assert result['steps']==60
    assert result['stop']=='step_limit'
    assert len(sdk.payloads)==60
    assert all('thinking' not in payload for payload in sdk.payloads)
    assert [json.dumps(p).count('"type": "image"') for p in sdk.payloads[:5]]==[1,1,0,1,0]
    calls=FakeClient.instances[-1].calls
    assert sum(n=='look' for n,_ in calls)==3
    rows=[json.loads(line) for line in (tmp_path/'steps.jsonl').read_text().splitlines()]
    assert len(rows)==60
    assert rows[4]['result']['stopped'] is False
    assert all(set(row)=={'step','timestamp','tool','args','result','frame_path','visual_note'} for row in rows)
    assert [row['frame_path'] for row in rows[:5]]==['step_000.png','step_001.png',None,'step_003.png',None]
    for payload in sdk.payloads:
        assert payload['tool_choice']=={'type':'auto','disable_parallel_tool_use':True}
        assert payload['system'][0]['cache_control']=={'type':'ephemeral'}
        assert payload['tools'][-1]['cache_control']=={'type':'ephemeral'}


def test_sixty_step_stop(monkeypatch,tmp_path):
    monkeypatch.setattr(runner,'RobotClient',FakeClient)
    sdk=FakeSDK([('pickup',{})]*61)
    result=runner.run('fetch',tmp_path,sdk=sdk)
    assert result['steps']==60 and result['stop']=='step_limit'
    assert len(sdk.payloads)==60


def test_dummy_never_needs_sdk(monkeypatch,tmp_path):
    monkeypatch.setattr(runner,'RobotClient',FakeClient)
    assert runner.run('fetch',tmp_path,dummy=True)['dummy'] is True


@pytest.mark.parametrize('name,args',[('teleport',{}),('move',{'distance':float('nan')}),
                                      ('move',{'distance':True}),('pickup',{'id':2})])
def test_bad_tool_rejected(name,args):
    with pytest.raises(ValueError):runner.checked_action(name,args)


def test_exact_payload_audit_matches_sdk(monkeypatch,tmp_path):
    monkeypatch.setattr(runner,'RobotClient',FakeClient)
    sdk=FakeSDK([('pickup',{})]*60)
    runner.run('fetch',tmp_path,sdk=sdk)
    records=[json.loads(x) for x in (tmp_path/'requests.jsonl').read_text().splitlines()]
    assert [r['payload'] for r in records]==sdk.payloads
    assert all(r['mode']=='live_attempt' for r in records)
    from audit_run import check
    assert check(tmp_path)[0]==60


def test_visual_memory_survives_without_image_and_is_not_an_engine_argument(monkeypatch,tmp_path):
    monkeypatch.setattr(runner,'RobotClient',FakeClient)
    sdk=FakeSDK([('pickup',{})]*60)
    runner.run('fetch',tmp_path,sdk=sdk)
    context=json.loads(sdk.payloads[1]['messages'][0]['content'][0]['text'])
    assert json.loads(context['recent_history'][0])['visual_memory']=='Camera observations retained.'
    assert all('visual_memory' not in (args or {}) for _,args in FakeClient.instances[-1].calls)
    assert sdk.payloads[0]['tool_choice']['type']=='auto'


@pytest.mark.parametrize('stop_reason,blocks',[
    ('end_turn',[]),('max_tokens',[('move',{'distance':1})]),
    ('tool_use',[('move',{'distance':1}),('turn',{'degrees':30})])])
def test_invalid_api_response_never_moves(monkeypatch,tmp_path,stop_reason,blocks):
    monkeypatch.setattr(runner,'RobotClient',FakeClient)
    sdk=SimpleNamespace(messages=SimpleNamespace(create=lambda **kw:SimpleNamespace(
        stop_reason=stop_reason,content=[SimpleNamespace(type='tool_use',id=str(i),name=n,
        input={**a,'visual_memory':'Observed only from pixels.'}) for i,(n,a) in enumerate(blocks)])))
    result=runner.run('fetch',tmp_path,sdk=sdk)
    assert result['stop']=='invalid_response' and result['steps']==0
    assert not any(n in ('move','turn','pickup','drop') for n,_ in FakeClient.instances[-1].calls)


def test_sdk_error_does_not_expose_error_body(monkeypatch,tmp_path):
    monkeypatch.setattr(runner,'RobotClient',FakeClient)
    def fail(**kwargs):raise RuntimeError('sensitive-secret-in-sdk-error')
    sdk=SimpleNamespace(messages=SimpleNamespace(create=fail))
    with pytest.raises(RuntimeError) as error:runner.run('fetch',tmp_path,sdk=sdk)
    assert 'sensitive-secret' not in str(error.value)


def test_latency_logged_without_model_context(monkeypatch,tmp_path):
    monkeypatch.setattr(runner,'RobotClient',FakeClient)
    sdk=FakeSDK([('move',{'distance':.1})]*60)
    runner.run('fetch',tmp_path,sdk=sdk)
    rows=[json.loads(x) for x in (tmp_path/'timings.jsonl').read_text().splitlines()]
    assert len([r for r in rows if r['phase']=='api'])==60
    assert len([r for r in rows if r['phase']=='image'])==60
    assert all(r['elapsed_seconds']>=0 for r in rows)
    assert all('elapsed_seconds' not in json.dumps(p) for p in sdk.payloads)


def test_model_compatible_tool_choice():
    from agent.policy import tool_choice
    assert tool_choice('claude-sonnet-5-5')['type']=='auto'
    assert tool_choice('claude-haiku-5-5')['type']=='any'
