# Agent trace instructions

This project uses its own harness: `run_command.py` starts the engine, and `agent/runner.py` runs the tool-use loop with the Anthropic Python SDK (messages API with tools). It is not a third-party agent framework, so the traces below are produced by our own code.

## Producing a trace
```powershell
& $robotPython run_command.py "<command>" --gui
```
Each run creates `logs/<timestamp>/` containing:
- `steps.jsonl`: one JSON line per step with step, timestamp, tool, args, result, frame_path, the model's short visual note, and state info
- PNG camera frames beside the log (neutral names like `step_007.png`)
- `evaluation.json`: private grading, written by the engine after the agent stopped
- `summary.json`: verdict (PASS, FAIL, UNVERIFIED or ERROR), outcome, command
- `engine.log` and the POV clip

## Packaging for submission
```powershell
& $robotPython package_run.py <run_folder> <N>
```
This builds the `submission/` layout:
```
submission/
  README.md
  logs/command_N.jsonl
  logs/frames/runN_stepNN.png
  prompts/system_prompt.txt
  prompts/full_trace_runN.json    # full API messages, images replaced by a placeholder
  clips/command_N.mp4
  stretch_goal/report.md
```
Check the actual output of the script and fix any path differences before submitting.

## Checking a trace
```powershell
& $robotPython check_logs.py <run_folder>
```
It reports step count (soft 25, hard 60), any two consecutive `/look` calls without a move or turn, Blocked/recovery entries, and the state trace Idle -> Locate -> Go to object -> Pick up -> Carry -> Drop -> Done.

## What counts as a Claude trace
Only runs with `"mode": "claude"` in `summary.json`. Runs from `--dummy` or `--pixel`, and tests using a fake client, are plumbing or test tools and must not be presented as evidence of Claude finding objects from images.

## What the trace shows
- Claude received an image after every move or turn and described what it saw in its visual note.
- Each decision is a single tool call with its arguments and the engine's result.
- Collisions show the stop, the 0.1 m back-off, the Blocked state, the recovery turn and the retry count.
- The request payloads contain no object data (verified by `tests/test_leaks.py`).
