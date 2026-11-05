# Implements the room, RGB camera, single range ray, snap carry and collision stops.
# Physics advances in fixed 1/240-second ticks only inside move/turn actions.
# The private report is for the local evaluator; it is never an agent observation.
import io
import json
import math
import time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from PIL import Image
import pybullet as p
from .robot import Robot
from .scene import build, expected_body
from .state_machine import StateMachine


class PyBulletRobot(Robot):
    DT = 1/240

    def __init__(self, gui=False, command='', seed=0, realtime=True, report=None, record_pov=False):
        self.client = p.connect(p.GUI if gui else p.DIRECT)
        self.renderer = p.ER_BULLET_HARDWARE_OPENGL if gui else p.ER_TINY_RENDERER
        p.setRealTimeSimulation(0, physicsClientId=self.client)
        p.setTimeStep(self.DT, physicsClientId=self.client)
        p.setGravity(0,0,-9.81, physicsClientId=self.client)
        self.body, self.objects, self.walls, self.zone = build(self.client,seed)
        self.x = self.y = self.heading = 0.0
        self.held = None
        self.machine = StateMachine(self._transition)
        from .recorder import POVRecorder
        self.recorder=POVRecorder(Path(report).parent/'pov') if record_pov and report else None
        self._pending_collision=None
        self._incident=0
        self.sim_time = 0.0
        self.realtime = realtime
        self.report = Path(report) if report else None
        self.expected = expected_body(command,self.objects)
        self.command = command
        self.delivered = None
        self.last_drop_in_zone = False
        self.camera_frames = 0
        self.camera_render_seconds = 0.0
        self._last_render_tick = -8
        self._ticks = 0
        self._frame = None
        self._command_deadline = None
        if gui:
            p.resetDebugVisualizerCamera(7,45,-60,[0,0,0],physicsClientId=self.client)
            p.configureDebugVisualizer(p.COV_ENABLE_GUI,0,physicsClientId=self.client)
        self._render()
        self._transition(None,'Idle',0)
        self._write_report()

    def close(self):
        if p.isConnected(self.client):
            p.disconnect(self.client)

    def state(self):
        return dict(state=self.machine.name,x=self.x,y=self.y,heading=self.heading,
                    holding=self.held is not None,retries=self.machine.retries)

    def _write_report(self):
        if self.report:
            payload = dict(state=self.machine.name,outcome=self.machine.outcome,
                           verified=self.expected is not None,
                           sim_seconds=self.sim_time,retries=self.machine.retries,
                           pickup_attempts=self.machine.pickup_attempts,
                           transitions=self.machine.transitions,
                           camera_frames=self.camera_frames,
                           camera_render_seconds=self.camera_render_seconds)
            self.report.parent.mkdir(parents=True,exist_ok=True)
            tmp = self.report.with_suffix('.tmp')
            tmp.write_text(json.dumps(payload,indent=2),encoding='utf-8')
            tmp.replace(self.report)

    def finish(self, reason='fail_not_reached'):
        self.machine.finish(reason)
        self._write_report()

    def _start(self):
        if self.machine.name == 'Done':
            raise ValueError('Run is complete; restart the engine for a new run')
        if self.machine.name == 'Idle':
            self.machine.begin()
        self._command_deadline = time.perf_counter()

    def _pose(self):
        angle = math.radians(self.heading)
        p.resetBasePositionAndOrientation(self.body,[self.x,self.y,.22],
            p.getQuaternionFromEuler([0,0,-angle]),physicsClientId=self.client)
        if self.held:
            o = self.held
            p.resetBasePositionAndOrientation(o['body'],
                [self.x-.62*math.cos(angle),self.y+.62*math.sin(angle),o['halfheight']],
                [0,0,0,1],physicsClientId=self.client)

    def _collision(self):
        movers = [self.body]+([self.held['body']] if self.held else [])
        obstacles = self.walls+[o['body'] for o in self.objects if not self.held or o['body']!=self.held['body']]
        for mover in movers:
            for obstacle in obstacles:
                if p.getClosestPoints(mover,obstacle,distance=0,physicsClientId=self.client):
                    return True
        return False

    def _tick(self, dt):
        p.setTimeStep(dt,physicsClientId=self.client)
        p.stepSimulation(physicsClientId=self.client)
        self.sim_time += dt
        self._ticks += 1
        # 240 Hz physics / 8 = 30 camera frames per simulated second.
        if self._ticks-self._last_render_tick >= 8:
            self._render()
        if self.realtime and self._command_deadline is not None:
            self._command_deadline += dt
            delay = self._command_deadline-time.perf_counter()
            if delay > 0:
                time.sleep(delay)

    def _translate(self, distance, monitor=True):
        sign = 1 if distance>=0 else -1
        remaining = abs(distance)
        moved = 0.0
        collision = False
        while remaining > 1e-9:
            step = min(self.DT,remaining) # 1 metre/second
            old = (self.x,self.y)
            a = math.radians(self.heading)
            self.x += sign*step*math.cos(a)
            self.y -= sign*step*math.sin(a)
            self._pose()
            if self._collision():
                self.x,self.y = old
                self._pose()
                self._tick(step)
                collision = True
                break
            self._tick(step)
            actual,_ = p.getBasePositionAndOrientation(self.body,physicsClientId=self.client)
            self.x,self.y = actual[:2]
            travelled = math.hypot(self.x-old[0],self.y-old[1])
            moved += sign*travelled
            remaining -= step
            if monitor:
                self.machine.progress(travelled,step)
                if self.machine.name in ('Blocked','Done'):
                    break
                if self._arrived():
                    self.drop()
                    break
        return moved,collision

    def _rotate(self, degrees):
        sign = 1 if degrees>=0 else -1
        remaining = abs(degrees)
        while remaining > 1e-9:
            step = min(90*self.DT,remaining)
            old = self.heading
            self.heading = (self.heading+sign*step)%360
            self._pose()
            if self._collision():
                self.heading = old
                self._pose()
                self._tick(step/90)
                return False
            self._tick(step/90)
            remaining -= step
            if self._arrived():
                self.drop()
                break
        return True

    def _event(self,event,**fields):
        # Private judge evidence. No added endpoint and no scene metadata.
        if self.report:
            self.report.parent.mkdir(parents=True,exist_ok=True)
            with (self.report.parent/'engine_events.jsonl').open('a',encoding='utf-8') as out:
                out.write(json.dumps(dict(event=event,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    sim_seconds=self.sim_time,**fields))+'\n')

    def _transition(self,before,after,retries):
        self._event('state',from_state=before,to_state=after,retries=retries)
        if self.recorder:
            if before=='Idle':self.recorder.start(self.sim_time,self._frame)
            if after=='Done':
                self._render()
                self.recorder.stop(self.sim_time,self._frame)

    def _contact(self,direction=-1):
        before=self.machine.name
        self.machine.block()
        moved,_=self._translate(direction*.1,monitor=False)
        self._incident+=1
        self._pending_collision=dict(incident=self._incident,from_state=before,
            to_state='Blocked',backoff_requested=.1,backoff_actual=abs(moved),
            recovery_angle=None,retries=self.machine.retries,state_after_recovery=None)
        self._event('collision',**self._pending_collision)
        return moved

    def _recover(self):
        pending=self._pending_collision
        self._pending_collision=None
        angle = self.machine.recovery()
        if angle is None:
            if pending:
                self._event('recovery',**{**pending,'retries':self.machine.retries,
                    'state_after_recovery':self.machine.name})
            return False
        self.machine.enter('Carry' if self.held else 'Go to object')
        ok=self._rotate(angle)
        if not ok:
            self._contact()
        if pending:
            self._event('recovery',**{**pending,'recovery_angle':angle,
                'retries':self.machine.retries,'state_after_recovery':self.machine.name})
        else:
            self._event('recovery',incident=None,recovery_angle=angle,
                retries=self.machine.retries,state_after_recovery=self.machine.name)
        return ok and self.machine.name!='Done'

    def move(self,distance):
        self._start()
        if self.machine.name=='Blocked' and not self._recover():
            self._write_report()
            return dict(collided=self.machine.name!='Done',moved=0.0)
        self.machine.enter('Carry' if self.held else 'Go to object')
        moved,collided = self._translate(distance)
        if collided:
            moved += self._contact(-1 if distance>=0 else 1)
        elif self.machine.name=='Blocked':
            backoff,_=self._translate(-.1 if distance>=0 else .1,monitor=False)
            moved+=backoff
        self._write_report()
        return dict(collided=collided,moved=round(moved,6))

    def turn(self,degrees):
        self._start()
        # In Blocked, the engine performs a deterministic, varying recovery turn
        # before the requested turn. Heading reports the actual result.
        if self.machine.name=='Blocked' and not self._recover():
            self._write_report()
            return dict(ok=self.machine.name=='Done',heading=self.heading)
        ok = self._rotate(degrees)
        if not ok:
            self._contact()
        self._write_report()
        return dict(ok=ok,heading=round(self.heading,6))

    def pickup(self):
        self._start()
        self.machine.pickup_attempts += 1
        # Do not consume pending motion recovery via an attachment request.
        if self.machine.name == 'Blocked' or self.held is not None:
            return self._pickup_result(False)
        candidates = []
        for o in self.objects:
            pos,_ = p.getBasePositionAndOrientation(o['body'],physicsClientId=self.client)
            dx,dy = pos[0]-self.x,pos[1]-self.y
            distance = math.hypot(dx,dy)
            bearing = math.degrees(math.atan2(-dy,dx))
            error = (bearing-self.heading+180)%360-180
            if distance<=.5+1e-9 and abs(error)<=30:
                candidates.append((distance,o))
        if not candidates:
            self.machine.enter('Go to object')
            return self._pickup_result(False)
        self.machine.enter('Pick up')
        o = min(candidates,key=lambda x:x[0])[1]
        old = p.getBasePositionAndOrientation(o['body'],physicsClientId=self.client)
        self.held=o
        self._pose()
        if self._collision():
            self.held=None
            p.resetBasePositionAndOrientation(o['body'],*old,physicsClientId=self.client)
            self.machine.enter('Go to object')
            return self._pickup_result(False)
        self.machine.enter('Carry')
        return self._pickup_result(True)

    def _pickup_result(self, success):
        # Private action evidence; HTTP still returns only success/failure.
        self._event('pickup_attempt',attempt=self.machine.pickup_attempts,
                    success=success,state=self.machine.name,retries=self.machine.retries)
        self._write_report()
        return dict(success=success)

    def _inside_zone(self):
        if not self.held:
            return False
        lower,upper=p.getAABB(self.held['body'],physicsClientId=self.client)
        return all(lower[i]>=self.zone[i]-.8 and upper[i]<=self.zone[i]+.8 for i in (0,1))

    def _arrived(self):
        # Private completion detection, never a target coordinate supplied to Claude.
        return (self.held is not None and self._inside_zone() and
                abs(self.x-self.zone[0])<=.8 and abs(self.y-self.zone[1])<=.8)

    def drop(self):
        # A repeat read-like drop after automatic release does not mutate the scene.
        if self.machine.name == 'Done':
            return dict(in_zone=self.last_drop_in_zone)
        self._start()
        if self.machine.name == 'Blocked':
            # Recovery requires motion; dropping cannot spend that budget.
            return dict(in_zone=False)
        if not self.held:
            self.machine.finish('fail_not_reached')
            self._write_report()
            return dict(in_zone=False)
        self.machine.enter('Drop')
        in_zone=self._inside_zone()
        self.delivered=self.held['body']
        self.held=None
        self.last_drop_in_zone=bool(in_zone)
        if not in_zone:
            # A failed delivery ends the run without pretending motion was blocked.
            self.machine.finish('fail_not_reached')
        elif self.expected is None:
            self.machine.finish(None) # unknown grading remains explicitly unverified
        elif self.delivered!=self.expected:
            self.machine.finish('fail_wrong_object')
        else:
            self.machine.finish('pass')
        self._write_report()
        return dict(in_zone=bool(in_zone))

    def _camera(self):
        a=math.radians(self.heading)
        eye=[self.x+.27*math.cos(a),self.y-.27*math.sin(a),.5]
        direction=[math.cos(a)*math.cos(math.radians(10)),
                   -math.sin(a)*math.cos(math.radians(10)),-math.sin(math.radians(10))]
        return eye,direction

    def _render(self):
        start=time.perf_counter()
        eye,direction=self._camera()
        target=[eye[i]+direction[i] for i in range(3)]
        view=p.computeViewMatrix(eye,target,[0,0,1])
        # Bullet expects vertical FOV; convert the required horizontal 90 degrees.
        vfov=math.degrees(2*math.atan(math.tan(math.radians(45))/(640/480)))
        projection=p.computeProjectionMatrixFOV(vfov,640/480,.02,20)
        data=p.getCameraImage(640,480,view,projection,renderer=self.renderer,
            flags=p.ER_NO_SEGMENTATION_MASK,physicsClientId=self.client)
        self._frame=Image.fromarray(np.ascontiguousarray(np.asarray(data[2],dtype=np.uint8).reshape(480,640,4)[:,:,:3]))
        if self.recorder:self.recorder.capture(self._frame,self.sim_time)
        self._last_render_tick=self._ticks
        self.camera_frames+=1
        self.camera_render_seconds+=time.perf_counter()-start

    def look(self):
        # Rendering does not step simulation. Refresh after instantaneous snap/drop.
        self._render()
        output=io.BytesIO()
        self._frame.save(output,format='JPEG',quality=90)
        return output.getvalue()

    def depth(self):
        eye,direction=self._camera()
        end=[eye[i]+10*direction[i] for i in range(3)]
        hit=p.rayTest(eye,end,physicsClientId=self.client)[0]
        return float(hit[2]*10) if hit[0]>=0 else None
