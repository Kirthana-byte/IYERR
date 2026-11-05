# Builds the private physical world. Nothing in this module is imported by the agent.
# Primitive colliders are real Bullet bodies; pickup uses a permitted rigid snap.
import math
import random
import pybullet as p


def build(client, seed=0):
    def body(kind, position, colour, size):
        if kind == 'cube':
            args = dict(shapeType=p.GEOM_BOX, halfExtents=[size]*3)
            v = p.createVisualShape(**args, rgbaColor=colour, physicsClientId=client)
            c = p.createCollisionShape(**args, physicsClientId=client)
            halfheight = size
        elif kind == 'sphere':
            args = dict(shapeType=p.GEOM_SPHERE, radius=size)
            v = p.createVisualShape(**args, rgbaColor=colour, physicsClientId=client)
            c = p.createCollisionShape(**args, physicsClientId=client)
            halfheight = size
        else:
            height = size * 3
            v = p.createVisualShape(p.GEOM_CYLINDER, radius=size, length=height,
                                    rgbaColor=colour, physicsClientId=client)
            c = p.createCollisionShape(p.GEOM_CYLINDER, radius=size, height=height,
                                       physicsClientId=client)
            halfheight = height/2
        b = p.createMultiBody(0, c, v, [*position, halfheight], physicsClientId=client)
        return b, halfheight

    floor_v = p.createVisualShape(p.GEOM_BOX, halfExtents=[4,4,.05],
                                  rgbaColor=[.74,.75,.77,1], physicsClientId=client)
    floor_c = p.createCollisionShape(p.GEOM_BOX, halfExtents=[4,4,.05], physicsClientId=client)
    p.createMultiBody(0, floor_c, floor_v, [0,0,-.05], physicsClientId=client)
    walls = []
    for pos, size in [([4.1,0,1],[.1,4.2,1]),([-4.1,0,1],[.1,4.2,1]),
                      ([0,4.1,1],[4,.1,1]),([0,-4.1,1],[4,.1,1])]:
        c = p.createCollisionShape(p.GEOM_BOX, halfExtents=size, physicsClientId=client)
        v = p.createVisualShape(p.GEOM_BOX, halfExtents=size, rgbaColor=[.86,.86,.83,1], physicsClientId=client)
        walls.append(p.createMultiBody(0,c,v,pos,physicsClientId=client))
    zone = (-2.0,0.0)
    v = p.createVisualShape(p.GEOM_BOX, halfExtents=[.8,.8,.002],
                            rgbaColor=[.06,.65,.15,1], physicsClientId=client)
    p.createMultiBody(0,-1,v,[*zone,.003],physicsClientId=client)
    records = [('red','cube',(2,0),.18,[.9,.04,.04,1]),
               ('red','sphere',(1.8,2),.20,[.9,.04,.04,1]),
               ('blue','cube',(-.5,2.2),.18,[.04,.15,.95,1]),
               ('yellow','cylinder',(-1,-2.1),.28,[.95,.78,.03,1]),
               ('blue','sphere',(2,-2),.20,[.04,.15,.95,1])]
    rng = random.Random(seed)
    objects = []
    for colour, shape, pos, size, rgba in records:
        if seed:
            pos = (pos[0]+rng.uniform(-.25,.25), pos[1]+rng.uniform(-.25,.25))
        b, halfheight = body(shape,pos,rgba,size)
        objects.append(dict(body=b, colour=colour, shape=shape, halfheight=halfheight, radius=size))
    # A smaller body leaves approach clearance inside the unchanged 0.5 m reach.
    # Visual and collision radii match; no invisible pass-through geometry.
    c = p.createCollisionShape(p.GEOM_CYLINDER, radius=.16, height=.44, physicsClientId=client)
    v = p.createVisualShape(p.GEOM_CYLINDER, radius=.16, length=.44,
                            rgbaColor=[.15,.17,.2,1], physicsClientId=client)
    robot = p.createMultiBody(0,c,v,[0,0,.22],physicsClientId=client)
    return robot, objects, walls, zone


def expected_body(command, objects):
    # Private evaluator only. It never chooses actions or returns data to Claude.
    # Restrict recognition instead of silently guessing unsupported semantics.
    import re
    text = command.lower().split(' to ')[0]
    words = set(re.findall(r'[a-z]+', text))
    if words.intersection({'not','except','other','farthest','nearest','left','right','smallest','second'}):
        return None
    candidates = list(objects)
    colours = words.intersection({'red','blue','yellow','green'})
    if colours:
        candidates = [o for o in candidates if o['colour'] in colours]
    shapes = words.intersection({'cube','sphere','cylinder'})
    if 'round' in words or 'ball' in words:
        shapes.add('sphere')
    if 'box' in words:
        shapes.add('cube')
    if shapes:
        candidates = [o for o in candidates if o['shape'] in shapes]
    if 'tallest' in words and candidates:
        height = max(o['halfheight'] for o in candidates)
        candidates = [o for o in candidates if o['halfheight'] == height]
    if not (colours or shapes or 'tallest' in words):
        return None
    return candidates[0]['body'] if len(candidates) == 1 else None
