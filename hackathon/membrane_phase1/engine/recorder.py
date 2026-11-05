# Saves raw onboard-camera frames on the simulation clock, never spectator views.
# These private recording files are not sent to the agent or to Claude.
import json
from pathlib import Path


class POVRecorder:
    def __init__(self,folder):
        self.folder=Path(folder)
        self.active=False
        self.start_time=None
        self.last_time=None
        self.count=0

    def start(self,sim_time,image):
        if self.start_time is not None:return
        self.folder.mkdir(parents=True,exist_ok=True)
        self.active=True;self.start_time=sim_time
        self._manifest(None,False)
        self.capture(image,sim_time)

    def capture(self,image,sim_time):
        if not self.active or image is None:return
        if self.last_time is not None and sim_time<=self.last_time+1e-9:return
        name=f'step_{self.count:06d}.png'
        image.save(self.folder/name,format='PNG',compress_level=1)
        with (self.folder/'frames.jsonl').open('a',encoding='utf-8') as out:
            out.write(json.dumps({'index':self.count,'sim_seconds':sim_time,'frame_path':name})+'\n')
        self.count+=1;self.last_time=sim_time

    def stop(self,sim_time,image):
        if not self.active:return
        self.capture(image,sim_time)
        self.active=False
        self._manifest(sim_time,True)

    def _manifest(self,end,complete):
        (self.folder/'recording.json').write_text(json.dumps({'start_sim_seconds':self.start_time,
            'end_sim_seconds':end,'complete':complete,'frames':self.count,
            'source':'onboard_camera','width':640,'height':480}),encoding='utf-8')
