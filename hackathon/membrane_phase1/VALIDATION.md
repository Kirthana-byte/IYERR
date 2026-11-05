<!-- Records actual checks for the audited repair; no live Claude results are claimed. -->
# Audited repair validation — 5 November 2026 (India)

Environment: Linux, Python 3.11.17, PyBullet 3.2.7, NumPy enabled, TinyRenderer.
No ANTHROPIC_API_KEY was configured; no live Claude call was made.

- Full repaired suite: 65 passed in 64.97 seconds.
- After including the validated robot-state snapshot in requests, the affected
  agent/leak suite: 29 passed in 0.85 seconds.
- New regression coverage: carried cylinder leaves a usable camera view and remains
  attached during movement; failed actuation triggers the integrated stall detector;
  visual memory survives no-image steps but never enters endpoint arguments;
  incomplete/missing/multiple tool responses execute no action; SDK error text is suppressed.
- Fresh separate-process run_three.py --dummy --fast: red cube PASS; round red thing
  and tallest object both fail_wrong_object. The two failures are intentional controls.
  All three runs made three scripted actions. Each outgoing audit passed with three
  dummy_not_sent requests. They are NOT live vision successes.
- The successful dummy took 4.3041667 simulation seconds. Rear carrying caused
  automatic arrival release after -2.754167 m of the requested reverse move.
- diagnostics.py camera: PASS for JPEG dimensions and frozen clock. The frame and
  the repaired carried-cylinder view were visually inspected.
- diagnostics.py api: stopped with the expected missing-key message. Authentication
  and model access were NOT tested.

## Actual camera benchmark

60 fresh frames after three warm-up reads, no concurrent test workload:

| Metric | Result |
|---|---:|
| Camera throughput | 16.95 FPS |
| Mean frame | 58.98 ms |
| P95 frame | 63.10 ms |
| Bullet rendering plus buffer transfer | 55.77 ms |
| JPEG encoding, separately sampled | 0.525 ms |
| Client JPEG decode/re-encode, separately sampled | 1.277 ms |
| Base64 encoding, separately sampled | 0.0085 ms |

The clock remained unchanged. The CPU renderer on this host does not meet 30 FPS.
Rendering plus returned-buffer transfer is the dominant measured cost. PyBullet
exposes these together, so GPU rendering and readback were not separately timed.
The prior audited headless baseline was 15.25 FPS, but workload variation means this
small difference should not be treated as a guaranteed improvement.
The user's historical Windows OpenGL measurement was 47.6 FPS; rebenchmark this build
on that laptop. No fresh Windows FPS or full-motion-loop FPS was measured here.

## Remaining acceptance gates

Actual API server acceptance, image recognition, three distinct autonomous deliveries,
live recovery and mentor approval remain unverified. Unknown-command private grading
still needs a mentor. Phase 2 recording/upload is not implemented.

---
# Historical validation below (previous builds)

<!-- Records the updated Phase 1 verification without claiming live Claude success. -->
# Current update validation

Python 3.11.17, Linux. No API key used.

- Behaviour/agent suite: 55 passed in 76.02 seconds.
- After adding three further outbound-leak tests, the 16-test leak suite passed.
- All 58 distinct tests passed across those runs; collection confirms 58 tests.
- Real separate-process Flask/PyBullet dummy fetch: PASS in three actions.
  Arrival automatically released the object and ended via Carry -> Drop -> Done.
- Exact outbound-request log audit: AUDIT PASS, three dummy_not_sent requests.
- Source compiles successfully. Windows-specific runtime not available here.
- No dependency, camera, renderer or FPS changes were made in this update.
- User reported the previous accelerated build at 47.6 camera FPS and 51 tests
  passing on Windows. The new 58-test suite must be run on that laptop.

Live Claude behaviour, three autonomous command successes and mentor sign-off
remain outstanding. Phase 2 recording/upload remains out of scope. Unknown
command semantics still require independent grading; see UPDATE.md.

## Earlier version validation (historical only)

<!-- Records observed verification results and explicitly lists unverified requirements. -->
# Validation record

Environment: Linux, CPython 3.11.17, PyBullet 3.2.7, Anthropic SDK 0.125.0.
No Anthropic API key was supplied or used.

## Automated checks

- Full initial suite: 50 passed in 115.70 seconds.
- Added a physical trapped-scene test and reran it with the seven agent tests:
  8 passed in 0.72 seconds. Total distinct tests verified: 51.
- All source files compile. Pytest collection confirms 51 tests.
- A manually inspected camera JPEG shows the scene, not a blank frame.
- Missing-key CLI check exits with a clear message before starting the engine.

## Separate-process HTTP integration

Executed `python run_three.py --dummy --fast`. Each run starts a fresh engine.
The same fixed action sequence executes four actions without API calls or input:
move 1.55, pickup, move -4.17, drop.

| Requested command | Observed result |
|---|---|
| Bring the red cube to the green square | PASS / pass |
| Bring the round red thing to the green square | FAIL / fail_wrong_object |
| Bring the tallest object to the green square | FAIL / fail_wrong_object |

The two failures are expected and desirable: the dummy does not interpret the
command and always delivers the same item. All three placements were inside the
zone; only the correct requested item passed. These are NOT autonomous Claude
successes and do not qualify for mentor sign-off.

## Performance and limitations

The software renderer measured approximately 8–10 camera FPS on this shared CPU
host, below the 30 real-time FPS target. Physics runs fixed simulated ticks and
samples 30 camera frames per simulated second, which can take longer than real
time. Windows GUI mode uses OpenGL; actual target-machine FPS must be measured
with `python benchmark.py --gui`. No claim of measured Windows performance is made.

Live Claude performance, model access for the eventual key, and three autonomous
fetch successes remain unverified. Windows GUI has not been run here.
The private automatic evaluator supports simple colour/shape, round/ball, box,
and tallest descriptions. Ambiguous or unsupported commands are UNVERIFIED after
placement, not silently passed. Mentor/manual grading is required for those cases.
Phase 2 video recording and feedback submission are out of scope.
