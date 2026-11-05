<!-- Explains how to install, verify, run and honestly present the complete Phase 1 project. -->
# Membrane Robot — Phase 1

**Existing installation? Read BATCHES.md first. Preserve your accelerated .venv.**

Windows, Python 3.11, PyBullet. All seven requested build stages are included.
No key is needed for tests or dummy mode. Live Claude operation requires your own
organizer-provided API key. This package has not been verified against live Claude.

## 1. Install

Extract the ZIP, open PowerShell in the `membrane_phase1` folder, and run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

No activation or execution-policy change is required. Python 3.11 must be installed.
The packages include a large PyBullet wheel. `requirements.txt` pins the direct
packages tested. Tests use real Bullet geometry plus separate mock API tests.

## 2. Run without an API key

```powershell
.\.venv\Scripts\python.exe run_command.py "Bring the red cube to the green square" --dummy --gui
```

This opens a simulator window and performs a fixed scripted pickup and delivery.
It checks HTTP, physics, image logging and evaluation. It does NOT understand the
command or use vision. It must never be presented as Claude autonomy.
Expected final outcome for this exact default scene/command: `pass`.
Use `--fast` for unpaced tests and omit `--gui` for a headless run.

```powershell
.\.venv\Scripts\python.exe run_three.py --dummy --fast
```

Expected: first command PASS, other two FAIL (`fail_wrong_object`). This is
intentional: the same dumb script fetches the same item regardless of the command.
Correctly rejecting those runs proves that successful placement alone cannot pass.
The script returns exit code 1 when any run fails.

## 3. Run Claude later

```powershell
Copy-Item .env.example .env
notepad .env
```

Put your key after `ANTHROPIC_API_KEY=` locally. Do not upload or commit `.env`.
Then:

```powershell
.\.venv\Scripts\python.exe run_command.py "Bring the round red thing" --gui
.\.venv\Scripts\python.exe run_command.py "Bring the red cube to the green square" --model claude-haiku-5-5 --gui
.\.venv\Scripts\python.exe run_three.py --gui
```

Default model: `claude-sonnet-5-5`. Model access depends on your key. API errors
stop the run and appear in the local summary; there is no silent fallback to a
fake agent. The SDK has retries disabled to avoid hidden extra requests per step.
The system/tool prefix has cache markers; actual caching depends on the model's
minimum cache length and is measured in `usage.jsonl`, not assumed.

The default command runner starts and stops its own engine on port 8080. Stop any
manually running server before using it. A busy port is an error. Every run starts
fresh. `--seed 1` slightly perturbs object positions for robustness checks.

## 4. Inspect the engine separately

```powershell
.\.venv\Scripts\python.exe -m engine.server --gui --command "Bring the red cube to the green square"
```

In a second PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/state
Invoke-RestMethod http://127.0.0.1:8080/depth
Invoke-WebRequest http://127.0.0.1:8080/look -OutFile "$env:TEMP\step_000.jpg"
Start-Process "$env:TEMP\step_000.jpg"
Invoke-RestMethod http://127.0.0.1:8080/move -Method Post -ContentType 'application/json' -Body '{"distance":1.55}'
Invoke-RestMethod http://127.0.0.1:8080/pickup -Method Post
Invoke-RestMethod http://127.0.0.1:8080/move -Method Post -ContentType 'application/json' -Body '{"distance":-4.17}'
Invoke-RestMethod http://127.0.0.1:8080/drop -Method Post
```

Expected on a fresh scene: successful pickup, in_zone true, state Done.
Ctrl+C stops the standalone server. Restart to reset.
To reproduce Stage 1 only: `python -m engine.server --backend mock`.

## How Claude finds the object from the image

The agent sends the user's command and one robot-camera image. Claude infers the
requested item from pixels, turns to centre it, approaches in small increments,
and calls pickup. It then identifies the marked destination from pixels, carries
and drops. After each move/turn the agent captures exactly one fresh image. The
previous image is removed from the next request. No new or repeated image is sent
after pickup/drop; numeric action results and Claude's own required visual_memory tool field
preserve context. No detector or engine object lookup chooses actions for Claude.

## What is implemented and what still needs verification

- Scene: enclosed flat 8 m room, five primitives, duplicate colours/shapes, marked
  destination, simple cylindrical mobile base (allowed simplified robot).
- Robot: real Bullet collision shapes, discrete collision-checked kinematic motion,
  240 Hz simulation ticks, 1 m/s, 90 deg/s, 0.5 m / 30-degree snap pickup.
- Clock: only motion (including recovery within motion) advances simulation. HTTP
  reads, API latency and snap/release do not advance it. No grasp dynamics required.
- Rendering: camera sampled at 30 frames per simulated second while moving;
  the GUI renderer uses OpenGL, headless uses TinyRenderer. Real wall-clock FPS is
  hardware-dependent; run `python benchmark.py` on your laptop. Paused scenes are
  static. This is not a guarantee of 30 real-time FPS on every machine.
- States, actual-displacement simulation-time stall timer, up to three varied recovery attempts,
  terminal delivery and failure outcomes.
- Claude tool loop, --model, --dummy, caching markers, hard 60-step cap, logs.
- Strict endpoint allowlists and tests against injected metadata.
- Automated checks and Windows instructions. Windows GUI and live API operation
  must still be checked on your laptop; validation here uses Linux Python 3.11.
- POV capture and H.264 export are now included; see BATCHES.md. Membrane API
  upload remains unimplemented because no API guide/key was provided.

## Private evaluation and specification decisions

The engine alone knows the requested test target for grading. It resolves simple
colour/shape phrases, `round`/`ball`, `box`, and `tallest`. It never passes that
identity to the agent or uses it to plan motion. A wrong item delivered in the zone
is `fail_wrong_object`. The entire item's footprint must fit in the zone.

Unsupported/ambiguous semantic commands are explicitly UNVERIFIED (null outcome)
after placement. They need an independent human/mentor verdict. This deliberate
exception prevents a false `pass`; it is not one of the four scored outcomes.
General language cannot be reliably graded by a few string rules. The private
resolver is deliberately limited; no claim of universal automatic judging is made.
Hidden commands may need mentor-provided ground truth. The agent can still attempt
them using pixels. No new scene objects are fabricated to satisfy a command.

On arrival with the robot centre and entire carried footprint inside the zone,
the engine automatically releases the item and finishes via Drop -> Done. Automatic backoff happens on
collision; the next move/turn performs a recovery turn (45, -90, 135 degrees) before
its requested motion. This stays inside move/turn clock advancement and permits a
look at the collision before recovery. The shared budget now covers failed pickups and drops as well as collisions.
After the initial failure there are at most three recovery attempts; continued
failure ends with fail_collision or fail_not_reached as appropriate.

`done` is a local agent stop tool, not an eighth HTTP endpoint. The supervisor asks
the engine to finish through a local stop signal after the agent exits. No target
metadata travels along this path. Only then does the supervisor read evaluation.

## Files and logs

- engine/: interface, mock, scene, physics, state machine, Flask server
- agent/: HTTP client, response guard, prompts/tools, Claude/dummy loop
- tests/: mock contract, physics, agent and leak checks
- run_command.py: one supervised run
- run_three.py: three different commands
- benchmark.py: local render benchmark and physics-clock check
- INTERFACE.md: exact wire formats and trust boundary
- UPDATE.md: update steps and revised arrival/retry semantics
- audit_run.py: inspect the saved outgoing request bodies
- STAGES.md: verification and commit message per stage
- logs/<timestamp>/: step_NNN.png, steps.jsonl, evaluation.json, summary.json,
  engine.log, requests.jsonl, optional usage.jsonl

Every steps.jsonl record has step, timestamp, tool, args, result, frame_path, visual_note. The
frame path identifies the image supplied for that decision; it is null when no
image was sent. A fresh frame after the final motion can exist without a following
decision. Final scores, private reports and engine logs are never sent to Claude.

## Sources

Original project brief supplied by the user and the user's staged specification.
API mechanics: https://platform.claude.com/docs/en/agents-and-tools/tool-use/parallel-tool-use
Model names: https://platform.claude.com/docs/en/models/overview
Bullet: https://github.com/bulletphysics/bullet3/tree/master/docs

## Audited repair

See REPAIR_GUIDE.md for test stages A-G and the current validation limits. The
carry mount is now 0.62 m BEHIND the robot, leaving the fixed front camera usable.
The live request uses auto tool choice, strict schemas and a required model-authored
visual_memory string (maximum 1200 characters, checked locally). This string is
removed before the endpoint call. Numeric bounds are also checked locally because
strict API schemas do not support minimum/maximum. Every response must contain
exactly one valid tool call; a refusal, truncated response, no call or multiple calls
stops safely without executing an action or silently switching to dummy mode.
API retries are disabled and timeout is 60 seconds. Sonnet 5.5 uses between_tools
thinking mode. The request still needs a real API test with your key.

The snapshot of permitted robot state is now included alongside the command, image,
depth, collision flag and history. It contains only robot pose/status, not object data.
Camera settings and requirements.txt are unchanged. The benchmark now supports
--frames and --profile; HTTP timing has a separate diagnostics.py command.

## Batches 1–3

See BATCHES.md for leak checks, explicit recovery/state logs, POV export, submission
packaging and optional TEST ONLY pixel mode. Private evaluation now names its boolean
`verified` rather than `target_verified` so log keys remain neutral. This boolean is
still evaluator bookkeeping, not proof of visual recognition.
