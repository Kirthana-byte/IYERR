<!-- Documents exact HTTP contracts, units, sensor boundaries and control semantics. -->
# Robot HTTP interface

Base http://127.0.0.1:8080. Local only. Exactly seven routes. JSON except /look.
The user's requested response names override the DOCX's name/ok variants.

| Method | Path | Input | Output |
|---|---|---|---|
| GET | /state | none | {state,x,y,heading,holding,retries} |
| GET | /look | none | 640x480 JPEG bytes |
| GET | /depth | none | JSON float metres, maximum 10, or null |
| POST | /move | {distance:number} | {collided:boolean,moved:number} |
| POST | /turn | {degrees:number} | {ok:boolean,heading:number} |
| POST | /pickup | empty or {} | {success:boolean} |
| POST | /drop | empty or {} | {in_zone:boolean} |

Distances in metres. Heading 0=+x, positive clockwise (90 points toward -y).
Move returns signed net displacement along that action's forward axis, including
collision backoff. A blocked recovery can first change that axis. Turn reports
actual heading, including recovery. Limits per request: abs(distance)<=10,
abs(degrees)<=360. Reject non-finite numbers, booleans, strings, extra fields,
malformed JSON and bodies over 4096 bytes. Inputs are validated before mutation.

Robot centre is the origin for pickup distance. Pickup checks planar centre
separation <=0.5 and bearing within +/-30 degrees, then snaps the nearest eligible
item 0.62 metres behind the robot. The item remains on the floor height in the simplified
carry model; grasping and wheel dynamics are not simulated. A snap into another
collider is rejected. Pickups do not disclose identity. Drop tests the whole
AABB footprint inside the marked zone. Successful arrival triggers automatic
release and Done. Failed drop stays recoverable until the retry budget is exhausted.

Camera: front at 0.27 m ahead, 0.5 m high, 10 degrees down, 90 horizontal FOV.
The engine converts horizontal to vertical FOV for Bullet's projection function.
Depth is precisely a camera-centre ray; it can see the floor/carried item and is
not distance to a named target. RGB only: segmentation is disabled and no depth
image or object mask leaves the engine.

State names: Idle, Locate, Go to object, Pick up, Carry, Drop, Done, Blocked.
Transient states are recorded in the private transition report. /state has only
robot pose and status; no scored result or scene inventory. Reads never advance
the simulation clock. Done rejects motion and pickup; a repeated drop returns the stored final zone
status without changing the scene. Restart for a new run.

The agent validates exact JSON schemas before consuming an endpoint. Image bytes
are decoded and re-encoded to remove metadata. Only command, RGB image, depth,
collision flag, validated robot state, tool results and Claude-authored visual memory
enter model requests. Robot coordinates describe only the robot, never an object. The supervisor reads private grading only after the agent
stops. Runtime state filenames are neutral; private scene source is never loaded
into model context. Tests are useful checks, not a formal proof against all leaks.

MockRobot remains explicitly available with --backend mock: no physics, no range
sensor, diagnostic JPEG only, one deterministic test fixture and simplified states.
Its limitations are not used in full PyBullet runs.

See UPDATE.md for the shared initial-attempt-plus-three-retries budget and exact
outbound request logging. These changes do not add any HTTP scene-data endpoint.

Claude tool inputs include visual_memory in addition to physical arguments. This
required string contains Claude's own pixel-derived notes; it is stripped before
HTTP dispatch. Endpoint bodies remain exactly the table above. The latest twelve
action lines carry these notes; each new note should retain useful earlier observations.

## Local evidence (not additional robot endpoints)

steps.jsonl includes visual_note, copied from Claude's visual_memory field and never
sent to the engine. sensor_calls.jsonl records every actual successful HTTP sensor/action
call. engine_events.jsonl records state transitions, collisions, requested/actual backoff,
recovery angle, retries and post-recovery state. An obstructed backoff is honestly
recorded as shorter than 0.1 m. Raw POV recording uses the simulation clock; it never
adds /look requests to Claude's decision schedule.

The text leak scanner exempts only the typed command and known model-note fields.
The mandatory boolean in_zone and permitted robot pose fields remain legal. A blanket
ban of those contract fields would reject valid responses; arbitrary scene fields
are still rejected by endpoint allowlists.
