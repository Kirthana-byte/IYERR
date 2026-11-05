# CLAUDE.md

Read `AGENTS.md` first. Its rules apply to you in full.

## Quick context
- This repo is a PyBullet robot fetch task. Claude (the model called by `agent/runner.py`) controls the robot through HTTP tools: `move`, `turn`, `pickup`, `drop`, `done`.
- The robot-side model never receives object information from the engine. Do not add any.
- The default model is `claude-sonnet-5-5`. Use `claude-haiku-5-5` (`--model`) for cheap plumbing tests.

## Working style
- Make small, focused edits and show only what changed.
- After any change to prompts, tool schemas or the observation payload, run `tests/test_leaks.py`.
- Prefer fixing root causes (for example, the real pickup distance versus the depth reading) over adding workarounds.
- Keep failed pickups separate from collision/stall retries. Blocked is only for a collision or no movement for 2 sim seconds.
- Do not touch `.env`. Never print or log API keys.
