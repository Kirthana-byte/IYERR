# TEST ONLY: HTTP-only colour/shape controller, independent of the Claude agent.
# Supported: "Bring the <colour> cube/sphere/round thing to the <colour> square".
# Colours: red, blue, green, yellow, orange, purple. No tallest/relative reasoning.
# Geometry estimates come from camera pixels and the published camera calibration.
import io
import json
import math
import re
from datetime import datetime,timezone
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from .client import RobotClient

COLOURS={
    'red':[(0,10),(170,179)],'orange':[(11,24)],'yellow':[(25,35)],
    'green':[(36,85)],'blue':[(90,135)],'purple':[(136,169)]}
SUPPORTED='Bring the <red|blue|green|yellow|orange|purple> <cube|sphere|round thing> to the <colour> square'


def parse(command):
    match=re.fullmatch(r"\s*(?:bring|fetch)\s+(?:the\s+)?(red|blue|green|yellow|orange|purple)\s+(cube|sphere|round thing)\s+to\s+(?:the\s+)?(red|blue|green|yellow|orange|purple)\s+square[.!]?\s*",command.lower())
    # Also accept the ordinary adjective order "round red thing".
    if not match:
        command=re.sub(r'round (red|blue|green|yellow|orange|purple) thing',r'\1 round thing',command.lower())
        match=re.fullmatch(r"\s*(?:bring|fetch)\s+(?:the\s+)?(red|blue|green|yellow|orange|purple)\s+(cube|sphere|round thing)\s+to\s+(?:the\s+)?(red|blue|green|yellow|orange|purple)\s+square[.!]?\s*",command)
    if not match:raise ValueError('TEST ONLY supported command: '+SUPPORTED)
    colour,shape,destination=match.groups()
    return colour,('sphere' if shape=='round thing' else shape),destination


def detect(jpeg,colour,shape=None,allow_clipped=False):
    image=cv2.imdecode(np.frombuffer(jpeg,dtype=np.uint8),cv2.IMREAD_COLOR)
    if image is None or image.shape[:2]!=(480,640):raise ValueError('Invalid camera pixels')
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV);mask=np.zeros(hsv.shape[:2],dtype=np.uint8)
    for low,high in COLOURS[colour]:
        mask |= cv2.inRange(hsv,np.array([low,80,45]),np.array([high,255,255]))
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    found=[]
    for contour in contours:
        area=cv2.contourArea(contour)
        if area<60:continue
        length=cv2.arcLength(contour,True)
        polygon=cv2.approxPolyDP(contour,.025*length,True)
        circularity=4*math.pi*area/max(length*length,1)
        x,y,w,h=cv2.boundingRect(contour)
        clipped=x<=1 or y<=1 or x+w>=639 or y+h>=479
        if shape and clipped and not allow_clipped:continue
        if shape=='sphere' and not clipped and (len(polygon)<6 or circularity<.75):continue
        if shape=='cube' and not clipped and len(polygon)>6:continue
        found.append({'area':area,'cx':x+w/2,'cy':y+h/2,'box':(x,y,w,h),
                      'polygon':polygon[:,0,:].tolist(),'clipped':clipped})
    return max(found,key=lambda item:item['area']) if found else None


def ground(u,v):
    # Ray/ground intersection from the documented 90-degree HFOV and 0.5 m height.
    vertical=(240-v)/320;side=(u-320)/320;pitch=math.radians(10)
    down=math.sin(pitch)-vertical*math.cos(pitch)
    if down<=.01:return None
    scale=.5/down
    return (.27+scale*(math.cos(pitch)+vertical*math.sin(pitch)),scale*side)


def distance_from_pixels(item,shape):
    x,y,w,h=item['box']
    if item['clipped']:return None
    if shape=='sphere':
        elevation=math.atan((240-item['cy'])/320)-math.radians(10)
        alpha=math.atan(w/640)
        denominator=math.sin(alpha)-math.sin(elevation)
        return .27+.5*math.cos(elevation)/denominator if denominator>.01 else None
    point=ground(item['cx'],y+h)
    if point is None:return None
    # Estimate the cube half-width from its projected width at the visible floor edge.
    return point[0]+w*max(point[0]-.27,0)/640


def decide(frame,holding,colour,shape,destination,estimate,travelled):
    item=detect(frame,destination if holding else colour,None if holding else shape,allow_clipped=estimate is not None)
    if item is None:return 'turn',{'degrees':45},'TEST ONLY: requested appearance is outside the current view.',None
    bearing=math.degrees(math.atan((item['cx']-320)/320))
    note=f"TEST ONLY: {destination if holding else colour} {'floor marking' if holding else shape}, horizontal offset {bearing:.1f} degrees from image centre."
    # The camera sits ahead of the turn centre: a full image bearing overshoots
    # nearby items. Use a damped correction and observe again after turning.
    if estimate is not None:estimate=max(0,estimate-travelled)
    if abs(bearing)>7:return 'turn',{'degrees':round(max(-45,min(45,bearing*.5)),1)},note,estimate
    if not holding:
        measured=distance_from_pixels(item,shape)
        estimate=measured if measured is not None else estimate
        if estimate is not None and estimate<=.52:return 'pickup',{},note,estimate
        if estimate is None:return 'move',{'distance':.1},note,None
        return 'move',{'distance':round(max(.05,min(.6,estimate-.45)),3)},note,estimate
    points=[ground(u,v) for u,v in item['polygon']]
    points=[p for p in points if p is not None]
    if not item['clipped'] and len(points)>=4:
        forward=sum(p[0] for p in points)/len(points);right=sum(p[1] for p in points)/len(points)
        heading=math.degrees(math.atan2(right,forward))
        if abs(heading)>7:return 'turn',{'degrees':round(heading,1)},note,forward
        return 'move',{'distance':round(max(.1,min(.5,forward)),3)},note,forward
    # Continue slowly into a partially visible floor marking; the engine verifies arrival.
    return 'move',{'distance':.25},note,estimate


def run(command,folder,base='http://127.0.0.1:8080'):
    colour,shape,destination=parse(command)
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    client=RobotClient(base);client.log_path=folder/'sensor_calls.jsonl'
    frame=client.call('look');frame_name='step_000.png'
    Image.open(io.BytesIO(frame)).save(folder/frame_name)
    estimate=None;travelled=0;have_fresh=True
    with (folder/'steps.jsonl').open('w',encoding='utf-8') as log:
        for step in range(1,61):
            state=client.call('state')
            if state['state']=='Done':return {'steps':step-1,'stop':'engine_done','dummy':False,'mode':'pixel'}
            if state['state']=='Blocked':
                # Existing engine recovery chooses a different angle per retry; do not double it.
                name,args,note='turn',{'degrees':0},'TEST ONLY: request engine recovery and a fresh view.'
                estimate=None
            elif not have_fresh:
                name,args,note='turn',{'degrees':45},'TEST ONLY: refresh the view after attachment/release.'
                estimate=None
            else:
                name,args,note,estimate=decide(frame,state['holding'],colour,shape,destination,estimate,travelled)
            result=client.call(name,args)
            row={'step':step,'timestamp':datetime.now(timezone.utc).isoformat(),'tool':name,
                 'args':args,'result':result,'frame_path':frame_name if have_fresh else None,'visual_note':note}
            log.write(json.dumps(row)+'\n');log.flush()
            print(f"PIXEL TEST {step:02d} {name} {args} -> {result}",flush=True)
            travelled=abs(result.get('moved',0))
            if name in ('move','turn'):
                frame=client.call('look');frame_name=f'step_{step:03d}.png'
                Image.open(io.BytesIO(frame)).save(folder/frame_name);have_fresh=True
            else:have_fresh=False;frame_name=None
        return {'steps':60,'stop':'step_limit','dummy':False,'mode':'pixel'}
