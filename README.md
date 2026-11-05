# Membrane Robot Hackathon: Phase 1 Fetch Robot

Team: IYER 

A typed command goes in ("Bring the red cube to the green square"). A simulated wheeled robot finds the object from its camera, drives to it, picks it up, carries it to the drop zone and releases it. Claude is the only decision-maker and sees the world only through camera pixels.

 Architecture

Three processes work together:

| Process | Role |
|---|---|
| Engine (`engine/`) | PyBullet room, robot, physics, camera. Local HTTP server on `localhost:8080`. Owns the state machine. |
| Agent (`agent/`) | Python tool-use loop. Calls the engine over HTTP only and writes logs. |
| Claude API | Receives the command, the latest camera frame, an optional depth reading, the collision flag and short text history. Returns exactly one tool call per step. |

`run_command.py` supervises one run: it starts the engine as a separate process, runs the HTTP-only agent, and reads the private evaluation only after the agent has stopped. The API key is removed from the engine's environment.

 Setup (Windows PowerShell, Python 3.11)

```powershell
python -m venv .venv
$robotPython = "$PWD\.venv\Scripts\python.exe"
& $robotPython -m pip install -r requirements.txt
& $robotPython -m pip install -r requirements-pixel.txt   # only for the optional --pixel test agent
copy .env.example .env                                    # then put your key in .env
```

`.env` contains `ANTHROPIC_API_KEY=...`. It is git-ignored. Never commit it.

Run

```powershell
& $robotPython run_command.py "Bring the red cube to the green square" --gui
```

| Mode / flag | Meaning |
|---|---|
| (default) | Real run: Claude is the agent. Needs `ANTHROPIC_API_KEY`. |
| `--model claude-haiku-5-5` | Cheaper model for plumbing tests. Default is `claude-sonnet-5-5`. |
| `--dummy` | Scripted plumbing test. Does not interpret the command. Not evidence of vision. |
| `--pixel` | Optional TEST-ONLY OpenCV agent using camera pixels, no Claude. Not evidence of the Claude agent. |
| `--gui` | Show the simulator window. |
| `--no-record-pov` | Skip recording the robot-camera clip. |
| `--fast`, `--seed N`, `--port N` | Testing options. |

Do not touch the keyboard or mouse during a run.

 Engine specification

| Item | Value |
|---|---|
| Camera | 640x480 JPEG, 90 degree horizontal FOV, 0.5 m above floor at robot front, tilted 10 degrees down |
| Depth | Single ray from camera centre, float metres, max 10, null if nothing |
| Speeds | Move 1 m/s, turn 90 deg/s |
| Pickup | Within 0.5 m and within +/-30 degrees of heading, snap attach |
| Collision | Stop, back off 0.1 m, `collided=true`, enter Blocked |
| Retries | Fail after 3 Blocked retries |
| Steps | 25 soft target, 60 hard stop |
| Heading | 0 = +x, positive clockwise from above |

HTTP endpoints: `GET /state`, `GET /look`, `GET /depth`, `POST /move`, `POST /turn`, `POST /pickup`, `POST /drop`.
`/state` returns only: state, x, y, heading, holding, retries.

How Claude finds the object from the image

Each step the agent sends Claude the typed command, the latest `/look` frame as an image content block, the optional depth value, the collision flag and one-line text notes of earlier steps (older images are dropped). Claude writes a short note describing what it sees, then returns one tool call: `move`, `turn`, `pickup`, `drop` or `done`. It searches by turning in steps until the target named in the command is visible, centres it in the frame, approaches using the depth reading, picks up when in reach, then looks for the drop zone in the image, carries the object there and drops it. After a collision it uses the Blocked recovery turn and tries again. There is no `go_to` tool, so Claude plans the path with move and turn only. The exact system prompt is in `agent/`.

 No object data reaches Claude

Object names, IDs, colours, shapes, positions, counts, distances to objects, segmentation masks and drop-zone coordinates never cross the engine boundary. Claude's only source is `/look` pixels, plus optional depth and the collision flag. The private evaluation is read only after the agent stops. Frame files use neutral names (`step_007.png`). `tests/test_leaks.py` scans the system prompt, tool schemas, request payloads, endpoint responses and filenames for banned data.

Logs and evidence

Each run writes a folder under `logs/` containing `steps.jsonl` (step, timestamp, tool, args, result, frame_path, visual note, state), PNG frames, `engine.log`, `evaluation.json`, `summary.json` and the POV clip.

```powershell
& $robotPython check_logs.py <run_folder>              # step count, look/move scheduling, collision handling
& $robotPython export_clip.py <run_folder> --retime 12 # compliant POV MP4 (needs ffmpeg)
& $robotPython package_run.py <run_folder> 1           # builds the submission/ layout
& $robotPython check_hygiene.py                        # secrets and archive check
```

See `agent_trace_instructions.md` for the trace layout.

Tests

```powershell
& $robotPython -m pytest -q
```

The suite covers the engine actions, state machine, agent scheduling (with a fake client), leak checks, recording and packaging. These tests do not prove live Claude performance.

 Tools, libraries and AI disclosure

- Python 3.11, PyBullet, Flask, OpenCV and NumPy (pixel test agent only), the Anthropic Python SDK, pytest, ffmpeg.
- The Claude API (`claude-sonnet-5-5`) is the robot's decision-maker at run time.
- AI coding assistants (GPT Astra, Gemini Pro and Claude) were used to help write and review code during the hackathon. Team members reviewed the code and can explain it.
- No project code was taken from another team or from a previous project.
