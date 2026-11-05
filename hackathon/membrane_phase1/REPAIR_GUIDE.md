<!-- Explains the audited repairs, safe Windows update, tests A-G and remaining proof. -->
# Audited repair — 5 November 2026

This build preserves the engine and HTTP interface. No live Claude fetching success
has been verified. An API key is still required for tests C, D and E.

## What changed

- Sonnet 5.5 now uses `tool_choice: auto`, not the rejected `any` setting.
  Strict tools enforce input shape. Unsupported numeric/string bounds stay in
  local validation and descriptions rather than strict API schemas.
- Every tool call includes Claude-authored `visual_memory`. It is carried forward
  in text history and stripped before the physical endpoint call. This avoids
  depending on text emitted before a forced tool call. Notes must come from pixels.
- The carry mount is 0.62 metres behind the robot. The fixed camera remains 0.27 m
  forward, 0.5 m high, tilted 10 degrees down, with 90-degree horizontal FOV.
  The tallest object previously covered the whole view; now it is behind the camera.
  Rear footprint collision checks remain active. Snap grasping is a simplified
  attachment, not an articulated gripper or dynamic lifting simulation.
- The stall timer now uses displacement read from Bullet. A regression test
  simulates failed actuation and verifies the Blocked transition after two sim seconds.
- Robot state is included through the existing strict allowlist. No object data,
  private target identity, evaluation or zone coordinates are sent to Claude.
- Incomplete responses, missing/multiple calls and API failures stop safely.
  No automatic API retry or fallback to dummy occurs. SDK timeout is 60 seconds;
  raw API error bodies are suppressed to avoid printing sensitive contents.
- Redundant end-of-action rendering was removed; /look still freshly renders after
  each move/turn. RGB array conversion now uses a contiguous buffer.
- benchmark.py separates render/readback, encoding and client image processing.
  diagnostics.py adds camera, HTTP, authenticated model lookup and image recognition checks.

## Install without disturbing the working Python environment

Extract the new ZIP into a NEW folder:
`C:\Users\mrina\OneDrive\Desktop\IYER\MembraneFixed`

The resulting project should be:
`C:\Users\mrina\OneDrive\Desktop\IYER\MembraneFixed\membrane_phase1`

Keep the old project, logs and environment. No dependency reinstall is required.
In PowerShell:

```powershell
Set-Location "C:\Users\mrina\OneDrive\Desktop\IYER\MembraneFixed\membrane_phase1"
$robotPython = "C:\Users\mrina\OneDrive\Desktop\hackoven\membrane_phase1\.venv\Scripts\python.exe"
Test-Path $robotPython
& $robotPython -m pytest -q
```

Test-Path must return True. Use that same `$robotPython` in each new PowerShell
window. If your interpreter has moved, update this variable to its actual path.

## A — Dummy execution (no API)

```powershell
& $robotPython run_command.py "Bring the red cube to the green square" --dummy --gui
& $robotPython audit_run.py
```

Expect PASS for the default scene and `dummy_not_sent` in the audit. The reverse
movement is shorter now because the rear carry mount reaches completion earlier.
This test never demonstrates visual recognition. Optional negative controls:

```powershell
& $robotPython run_three.py --dummy --fast
```

Expected: first PASS; other two fail_wrong_object. Exit code 1 is expected because
this deliberately requests two different targets while reusing the same dummy route.

## B — Camera rendering

```powershell
& $robotPython diagnostics.py camera --gui
& $robotPython -m pytest tests/test_physics.py -k "camera or carried" -v
```

Open the printed step_000.png and inspect it. Automated image validity is not
proof that Claude recognizes its contents. The carried-object regression test is
an internal physics fixture, not an agent that is given object positions.

## C — API connection

Create .env only if it does not exist:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Enter your key after ANTHROPIC_API_KEY= locally. Never paste it in chat or commit it.
Then:

```powershell
& $robotPython diagnostics.py api --model claude-sonnet-5-5
```

This authenticates and checks model visibility using a model lookup. It does not
prove that image generation requests have credit or that robot actions work.

## D — Real image identification (uses API credits)

In the first window, start a standalone engine:

```powershell
& $robotPython -m engine.server --gui
```

In a second PowerShell window, set the same project folder and $robotPython, then:

```powershell
& $robotPython diagnostics.py identify --command "Bring the red cube to the green square"
```

This sends a real /look JPEG to Claude. Compare its saved answer to the saved frame.
It prints REVIEW REQUIRED, never an automatic recognition PASS. At the initial
heading the destination is out of view; a correct answer should acknowledge that.
To inspect another view, turn first, then run a new standalone diagnostic:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/turn -Method Post -ContentType 'application/json' -Body '{"degrees":180}'
& $robotPython diagnostics.py identify --command "Bring the red cube to the green square"
```

These manual checks are not autonomous runs. Stop the standalone engine with Ctrl+C
before test E so the supervisor can own port 8080.

## E — Autonomous delivery (uses API credits)

```powershell
& $robotPython run_command.py "Bring the red cube to the green square" --gui
& $robotPython audit_run.py
```

There must be no DUMMY label. Check summary.json, steps.jsonl, requests.jsonl and
frames. `live_attempt` records an attempted API request, not proof the request
succeeded. A PASS must come from the evaluator after actual delivery.
Then run the three commands independently without keyboard intervention:

```powershell
& $robotPython run_three.py --gui
```

Commands: red cube; round red thing; tallest object. Audit EACH new run folder:

```powershell
& $robotPython audit_run.py "logs\THE_EXACT_RUN_FOLDER"
```

Use `--seed 1` on run_command.py for a slightly perturbed scene as a robustness
check. Three successful live runs, reviewed evidence and mentor sign-off remain
required. A stopped or failed run must never be counted as a live success.

## F — Collision, carry and recovery

```powershell
& $robotPython -m pytest tests/test_physics.py -k "collision or recoveries or trapped or stall or retries or carried" -v
```

These are automated physics/controller checks. Also observe and audit recovery
in a live Claude run before claiming autonomous collision recovery.

## G — Camera FPS and HTTP processing

```powershell
& $robotPython benchmark.py --gui --frames 60 --profile
```

Require >=30 camera_fps on the target laptop. This times 60 fresh 640x480 frames
following warm-up. It reports p95 frame time and confirms the clock stays frozen.
Render and pixel-buffer readback remain one combined PyBullet call. Other timings
are separate samples, not an exact additive breakdown. It is not a full moving-scene
FPS or Claude-latency guarantee.

With a standalone engine running, optionally measure the HTTP client path:

```powershell
& $robotPython diagnostics.py http
```

This benchmark intentionally samples repeated frames without moving; it sends
nothing to Claude and is not an autonomous run.

## Outstanding limits

- No live key was available during this repair. API server acceptance, recognition,
  three autonomous successes and live collision recovery are NOT verified.
- The private evaluator recognizes a limited set of phrases. Unknown/ambiguous
  target descriptions are UNVERIFIED, not automatically PASS, and need independent
  mentor grading. That null outcome is an explicit exception to the four scored labels.
- Arrival automatically releases and ends the run when the robot centre and entire
  held footprint are inside the zone. The engine decides completion, not the route.
- Strict tools cannot guarantee the model makes a call. A response without exactly
  one valid tool action ends safely instead of consuming an extra hidden API call.
- Visual-memory notes can be mistaken. They are model interpretations, not ground truth.
- No automated 120-development-run cutoff is implemented; track your development runs.
- Phase 2 video capture/upload is not implemented. 640x480 reasoning frames are not
  compliant 720p submission clips.

Suggested git commit: Fix visual agent requests, rear carry visibility and stall recovery; add diagnostics
