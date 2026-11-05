# AGENTS.md

Guidance for AI coding agents and contributors working in this repository.

## What this project is
Phase 1 of the Membrane Robot Hackathon: a PyBullet scene with a wheeled robot, a local HTTP API, and a Claude tool-use agent that fetches an object from camera pixels only. See `README.md`.

## Layout
- `engine/`: PyBullet scene, robot actions, state machine, HTTP server (`engine/server.py`)
- `agent/`: Claude tool-use loop (`agent/runner.py`), optional test-only pixel agent
- `run_command.py`: supervises one run (engine process + agent + logs)
- `check_logs.py`, `export_clip.py`, `package_run.py`, `check_hygiene.py`, `audit_run.py`: evidence tools
- `tests/`: pytest suite

## Commands (Windows PowerShell)
```powershell
$robotPython = "$PWD\.venv\Scripts\python.exe"
& $robotPython -m pytest -q
& $robotPython run_command.py "Bring the red cube to the green square" --pixel --gui   # no API key needed
& $robotPython run_command.py "Bring the red cube to the green square" --gui           # real Claude run
```

## Hard rules (breaking these disqualifies the team)
1. Never send object data to Claude. That means names, IDs, colours, shapes, positions, distances to objects, counts, segmentation masks or drop-zone coordinates, in any of: `/state`, system prompt, tool descriptions, tool results, message history, log keys, filenames. Claude's only source is `/look` pixels, optional `/depth` and the collision flag.
2. `/state` returns only: state, x, y, heading, holding, retries.
3. One tool call per step, and one `/look` after every move or turn. Never two images in a row without a move or turn between them.
4. Keep `--dummy` and `--pixel` code separate from the Claude code path. They are test tools, never evidence of Claude's autonomy.
5. Never commit `.env`, API keys, `.venv/`, zips or raw `logs/`.
6. Do not add `go_to` or any tool that identifies objects.
7. Do not fake or backdate commits. Commit small, with real messages.
8. Do not claim live results that were not run. Mark them UNVERIFIED.

## Before finishing any change
- Run the full test suite, including `tests/test_leaks.py`.
- Keep code simple and commented in plain language. Every team member must be able to explain it to judges.
- If a change touches the agent prompt or tool schemas, re-run the leak tests.
