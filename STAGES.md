<!-- Provides separate verification commands and commit messages for the seven requested stages. -->
# Stage checkpoints

Run from the project folder. In PowerShell use `.\.venv\Scripts\python.exe`
in place of `python` below. The full package is cumulative; do not run multiple
servers at once. No API key is needed until the live Stage 5 command.

| Stage | Verify | Expected | One-line git commit message |
|---|---|---|---|
| 1 | python -m pytest tests/test_stage1.py -q | Mock/API checks pass | Add robot interface, MockRobot and Flask endpoints |
| 2 | python -m engine.server --gui | Room appears; GET /look gives JPEG; GET /depth gives range | Add PyBullet room and isolated camera sensors |
| 3 | python -m pytest tests/test_physics.py -q | Reach, timing, collision and delivery tests pass | Implement collision-aware motion and snap pickup |
| 4 | python -m pytest tests/test_physics.py -k "recoveries or stall or progress" -q | Three-retry and simulated-time checks pass | Add fetch lifecycle and bounded blocked recovery |
| 5 | python run_command.py "Bring the red cube to the green square" --dummy --gui | Scripted delivery passes, no API used | Add Claude tool loop, dummy mode and step logging |
| 6 | python -m pytest tests/test_leaks.py -q | Allowlists and injected metadata checks pass | Guard model inputs against engine scene metadata |
| 7 | python -m pytest -q | Entire suite passes | Add end-to-end run scripts and verification documentation |

After obtaining a key, Stage 5's actual autonomy check is:
`python run_command.py "Bring the round red thing" --gui`.
Then run `python run_three.py --gui`. Three live command successes and mentor
sign-off remain necessary; a dummy pass is not a substitute.
