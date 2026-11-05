# Measures fresh camera rendering and individual image-processing costs on this host.
# No API calls or simulation motion occur. GPU render and readback are timed together
# because PyBullet exposes them as one getCameraImage operation.
import argparse
import base64
import io
import json
import statistics
import time
import pybullet as p
from PIL import Image
from engine.pybullet_robot import PyBulletRobot


def measure(fn,count):
    samples=[]
    for _ in range(count):
        start=time.perf_counter();fn();samples.append(time.perf_counter()-start)
    return samples


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--gui',action='store_true')
    parser.add_argument('--frames',type=int,default=60)
    parser.add_argument('--profile',action='store_true')
    args=parser.parse_args()
    if args.frames<10:parser.error('Use at least 10 frames')
    robot=PyBulletRobot(gui=args.gui,realtime=False)
    original=p.getCameraImage;render_samples=[]
    def timed_camera(*a,**kw):
        start=time.perf_counter()
        try:return original(*a,**kw)
        finally:render_samples.append(time.perf_counter()-start)
    try:
        for _ in range(3):robot.look()
        before=robot.sim_time
        if args.profile:p.getCameraImage=timed_camera
        samples=measure(robot.look,args.frames)
        assert robot.sim_time==before
        result={'renderer':'OpenGL' if args.gui else 'TinyRenderer',
                'numpy_enabled':bool(p.isNumpyEnabled()),'frames':args.frames,
                'camera_fps':args.frames/sum(samples),
                'mean_frame_ms':statistics.mean(samples)*1000,
                'p95_frame_ms':sorted(samples)[int(.95*(len(samples)-1))]*1000,
                'simulation_clock_unchanged':True}
        p.getCameraImage=original
        if args.profile:
            result['render_and_buffer_transfer_ms']=statistics.mean(render_samples)*1000
            raw=robot.look()
            stages={'jpeg_encode':lambda:robot._frame.save(io.BytesIO(),'JPEG',quality=90),
                    'client_decode_reencode':lambda:Image.open(io.BytesIO(raw)).convert('RGB').save(io.BytesIO(),'JPEG',quality=90),
                    'base64_encode':lambda:base64.b64encode(raw)}
            for name,fn in stages.items():result[name+'_ms']=statistics.mean(measure(fn,args.frames))*1000
        print(json.dumps(result,indent=2))
        print('30 FPS camera target met.' if result['camera_fps']>=30 else 'Below the 30 FPS camera target on this renderer.')
        print('Camera throughput only; this does not measure full motion-loop or Claude latency.')
    finally:
        p.getCameraImage=original
        robot.close()


if __name__=='__main__':main()
