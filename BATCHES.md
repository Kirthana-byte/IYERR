<!-- Lists the exact verification commands and honest limits for batches 1–3. -->
# Batches 1–3

Copy the changed source into your existing project, preserving .venv, .env and logs.
Or extract the full updated archive into a new directory and use the same Python.
The changes/ folder contains sequential patches with file paths and changed code.

In PowerShell, from the project directory under KIS:

```powershell
$robotPython = "C:\Users\mrina\OneDrive\Desktop\hackoven\membrane_phase1\.venv\Scripts\python.exe"
```

## Batch 1

```powershell
& $robotPython -m pytest tests/test_agent.py tests/test_batch1.py tests/test_leaks.py -q
& $robotPython run_command.py "Bring the red cube to the green square" --dummy --gui
$run = (Get-ChildItem .\logs -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'steps.jsonl') } | Sort-Object Name | Select-Object -Last 1).FullName
& $robotPython check_logs.py $run
```

Leak errors identify their exact field. User commands and model visual notes are
allowed; a mandatory boolean in_zone and the robot's own x/y pose are also allowed.
Banning those would contradict the required interface. Source code/tests can contain
words used to define a blacklist; the checks examine model-bound data and log keys.
This is an additional regression guard, not a mathematical proof of zero leakage.

steps.jsonl adds visual_note. engine_events.jsonl provides the whole state trace and
collision/recovery details; sensor_calls.jsonl proves the actual /look schedule.
Backoff_requested is 0.1; backoff_actual is the measured displacement, which can be
shorter if another obstacle prevents retreat. No phantom 0.1 m movement is logged.
A collision-free run does not verify recovery. Live Claude is UNVERIFIED.

## Batch 2

FFmpeg and ffprobe must be installed and available in PATH. If missing:

```powershell
winget install --id Gyan.FFmpeg --exact
```

Package reference: https://github.com/microsoft/winget-pkgs/tree/master/manifests/g/Gyan/FFmpeg
Close and reopen PowerShell after installation, then set $robotPython again.
Check in the new terminal:

```powershell
Get-Command ffmpeg, ffprobe
& $robotPython -m pytest tests/test_recording.py -q
& $robotPython export_clip.py $run --retime 12
& $robotPython package_run.py $run 1
```

Every supervised run records raw onboard frames from leaving Idle through Done.
Reads while Claude thinks do not add duplicate simulation-time frames. The default
export uses the natural simulated duration. If outside 10–20 s, it prints FAIL and
the explicit --retime command. Retiming changes playback speed and is disclosed.
`--no-record-pov` is available for quick plumbing tests. Missing FFmpeg does not
lose the raw frames; export after installing it.

Export: H.264 MP4, 1280x720, aspect ratio preserved with side bars, no audio. The
command is drawn for exactly 60 frames at 30 fps. Decoded samples at 0, 1, 1.967 and
2.033 seconds are compared with the expected pixels. No other text is added.
Manual review is still required for any text/logo already present in the scene or
in the typed command; format checks cannot certify human visual judging results.

package_run.py rejects unfinished runs, missing evidence, invalid/changed clips and
an already-used submission number. It preserves original logs and creates:

- logs/command_N.jsonl and logs/frames/runN_stepNN.png
- logs/engine_events_runN.jsonl and sensor_calls_runN.jsonl
- prompts/system_prompt.txt, per-run prompts and full_trace_runN.json
- clips/command_N.mp4 and clip_check_runN.json
- README.md and stretch_goal/report.md

Trace files retain complete request envelopes/messages with image blocks replaced
by placeholders. Exact binary-image requests remain in original local logs.
Phase 2 API upload is not implemented; the organizer's API guide/key is still needed.

## Batch 3

```powershell
& $robotPython -m pip install -r requirements-pixel.txt
& $robotPython -m pytest tests/test_pixel_agent.py -q
& $robotPython run_command.py "Bring the red cube to the green square" --pixel --gui
& $robotPython check_hygiene.py
& $robotPython -m pytest -q
```

Pixel mode is TEST ONLY, independent of the Claude path. It accepts:
Bring the <red|blue|green|yellow|orange|purple> <cube|sphere|round thing> to the <colour> square.
It also accepts “round red thing” adjective order. It rejects tallest/relative
reasoning commands. Masks and geometry estimates use only HTTP camera pixels and
published camera calibration; no object records, IDs, coordinates or counts are read.
The small controller is a diagnostic baseline, not a replacement for Claude.
Default mode still requires Claude; no automatic silent fallback to a test agent.

The key scan reports file and line, never key values. A local .env is ignored, but
tracked credentials fail. Public repository visibility remains UNVERIFIED.
