# Exercises real Bullet geometry, camera, timing, pickup and private scoring.
# Direct fixture changes are test-only and never available through the HTTP API.
import io
import math
import time
import pytest
import pybullet as p
from PIL import Image
from engine.pybullet_robot import PyBulletRobot
from engine.state_machine import StateMachine

@pytest.fixture
def robot():
    r=PyBulletRobot(command='Bring the red cube to the green square',realtime=False)
    yield r
    r.close()


def place_target(robot,distance,angle=0):
    a=math.radians(angle)
    o=robot.objects[0]
    p.resetBasePositionAndOrientation(o['body'],[distance*math.cos(a),-distance*math.sin(a),o['halfheight']],
                                      [0,0,0,1],physicsClientId=robot.client)


@pytest.mark.parametrize('distance,angle,success',[(.4,0,True),(.6,0,False),(.4,40,False)])
def test_pickup_geometry(robot,distance,angle,success):
    place_target(robot,distance,angle)
    assert robot.pickup()=={'success':success}


def test_camera_depth_and_pause(robot):
    start=robot.sim_time
    image=robot.look()
    assert Image.open(io.BytesIO(image)).size==(640,480)
    assert Image.open(io.BytesIO(image)).format=='JPEG'
    ray=robot.depth()
    assert ray is None or 0<=ray<=10
    robot.state();time.sleep(.02);robot.look();robot.depth()
    assert robot.sim_time==start


def test_clock_and_heading(robot):
    robot.turn(90)
    assert robot.sim_time==pytest.approx(1)
    robot.move(.5)
    assert robot.y==pytest.approx(-.5)
    assert robot.sim_time==pytest.approx(1.5)
    assert robot.camera_frames>=45


def test_wall_collision(robot):
    robot.turn(180)
    result=robot.move(5)
    assert result['collided'] is True
    assert -3.8<robot.x<-3.5
    assert robot.machine.name=='Blocked'
    assert robot.state()['retries']==0
    robot.move(.1)
    assert robot.state()['retries']==1


def test_fetch_and_wrong_object(robot):
    robot.move(1.55)
    assert robot.pickup()['success']
    robot.move(-4.17)
    assert robot.drop()['in_zone']
    assert robot.machine.outcome=='pass'
    assert robot.machine.name=='Done'
    with pytest.raises(ValueError): robot.move(1)


def test_wrong_delivery(robot):
    robot.expected=robot.objects[1]['body']
    robot.move(1.55);robot.pickup();robot.move(-4.17);robot.drop()
    assert robot.machine.outcome=='fail_wrong_object'


def test_drop_outside(robot):
    robot.move(1.55);robot.pickup()
    assert robot.drop()=={'in_zone':False}
    assert robot.machine.name=='Done'
    assert robot.machine.outcome=='fail_not_reached'


def test_unrecognized_command_not_pass():
    r=PyBulletRobot(command='Bring something to drink',realtime=False)
    try:
        r.move(1.55);r.pickup();r.move(-4.17);r.drop()
        assert r.machine.name=='Done'
        assert r.machine.outcome is None
    finally: r.close()


def test_three_failed_recoveries():
    f=StateMachine();f.begin();f.block()
    angles=[]
    for _ in range(3):
        angles.append(f.recovery());f.block()
    assert len(set(angles))==3
    assert f.retries==3 and f.name=='Done' and f.outcome=='fail_collision'


def test_stall_uses_sim_seconds():
    f=StateMachine();f.begin()
    f.progress(0,1.9);assert f.name!='Blocked'
    f.progress(0,.1);assert f.name=='Blocked'


def test_successful_progress_resets_stall():
    f=StateMachine();f.begin();f.progress(0,1.9);f.progress(.1,.1)
    f.progress(0,1.9);assert f.name!='Blocked'


def test_three_retries_in_physically_trapped_scene(robot):
    # Four close test-only barriers prevent both backing off and recovery turns.
    for position,extent in [([.23,0,.3],[.03,.4,.3]),([-.23,0,.3],[.03,.4,.3]),
                            ([0,.23,.3],[.4,.03,.3]),([0,-.23,.3],[.4,.03,.3])]:
        shape=p.createCollisionShape(p.GEOM_BOX,halfExtents=extent,physicsClientId=robot.client)
        robot.walls.append(p.createMultiBody(0,shape,-1,position,physicsClientId=robot.client))
    assert robot.move(.2)['collided']
    for _ in range(3):robot.move(.2)
    assert robot.state()['retries']==3
    assert robot.state()['state']=='Done'
    assert robot.machine.outcome=='fail_collision'


def test_arrival_releases_without_explicit_drop(robot):
    robot.move(1.55);assert robot.pickup()['success']
    result=robot.move(-4.17)
    assert abs(result['moved'])<4.17
    assert robot.machine.name=='Done'
    assert robot.held is None
    assert robot.machine.outcome=='pass'
    assert robot.machine.transitions[-2:]==['Drop','Done']


def test_failed_pickups_do_not_spend_motion_retries(robot):
    for attempt in range(5):
        assert robot.pickup()=={'success':False}
        assert robot.machine.retries==0
        assert robot.machine.pickup_attempts==attempt+1
        assert robot.machine.name=='Go to object'
    assert 'Blocked' not in robot.machine.transitions
    place_target(robot,.4)
    assert robot.pickup()=={'success':True}
    assert robot.machine.pickup_attempts==6
    assert robot.machine.retries==0


def test_pickup_does_not_consume_pending_collision_recovery(robot):
    robot.machine.block()
    assert robot.pickup()=={'success':False}
    assert robot.machine.retries==0
    assert robot.machine.name=='Blocked'
    assert robot.machine.recovery()==45
    assert robot.machine.retries==1


def test_failed_drop_does_not_spend_motion_retries(robot):
    assert robot.drop()=={'in_zone':False}
    assert robot.machine.retries==0
    assert robot.machine.name=='Done'
    assert robot.machine.outcome=='fail_not_reached'


def test_carried_tall_object_leaves_camera_clear(robot):
    import numpy as np
    # Private placement is only a test fixture, never a source for agent decisions.
    robot.x=-1.45;robot.y=-2.1;robot._pose()
    assert robot.pickup()['success']
    image=np.asarray(Image.open(io.BytesIO(robot.look())))
    assert image.reshape(-1,3).std(axis=0).max()>20
    held=robot.held['body']
    robot.turn(90);robot.move(.2)
    pos,_=p.getBasePositionAndOrientation(held,physicsClientId=robot.client)
    assert pos[0]==pytest.approx(robot.x)
    assert pos[1]==pytest.approx(robot.y+.62)
    assert robot.held['body']==held


def test_controller_detects_actual_translation_stall(robot,monkeypatch):
    # Simulate failed actuation: requested coordinates never reach Bullet's body.
    monkeypatch.setattr(robot,'_pose',lambda:None)
    result=robot.move(3)
    assert result['moved']==pytest.approx(0)
    assert not result['collided']
    assert robot.machine.name=='Blocked'
    assert 2<=robot.sim_time<2.2


@pytest.mark.parametrize('index',range(5))
@pytest.mark.parametrize('seed',[0,1])
def test_every_item_has_collision_free_pickup_approach(index,seed):
    # Private fixture positions are used only by the physics test, never the agent.
    r=PyBulletRobot(realtime=False,seed=seed)
    try:
        item=r.objects[index]
        pos,_=p.getBasePositionAndOrientation(item['body'],physicsClientId=r.client)
        r.x,r.y,r.heading=pos[0]-.8,pos[1],0
        r._pose()
        assert not r._collision()
        result=r.move(.35)
        assert not result['collided']
        assert result['moved']==pytest.approx(.35,abs=.005)
        assert r.pickup()=={'success':True}
        assert r.held['body']==item['body']
        assert r.machine.retries==0
    finally:r.close()
