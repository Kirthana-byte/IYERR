<!-- Records checks actually executed; no live Claude claims. -->
# Batch validation — 5 November 2026

- Full suite: 84 passed in 86.54 seconds, Python 3.11, Linux CPU rendering.
- Dummy fetch: PASS, 3 steps. Scripted plumbing only.
- Pixel cube: PASS, 22 steps. Pixel sphere: PASS, 33 steps (over 25-step soft target).
- Earlier pixel sphere attempt failed at 60 steps; damped image-bearing turns fixed the observed oscillation.
- Sphere log audit: PASS, zero consecutive looks, complete state trace, no collisions in that run.
- Collision/backoff/recovery and retry exhaustion: covered by automated tests; live Claude recovery UNVERIFIED.
- Actual clip: 12.000 seconds after explicit retiming from 4.304 simulated seconds. Duration, resolution, H.264, no audio and sampled overlay checks PASS.
- Actual dummy submission packaging: PASS. Dummy evidence is not a live submission demonstration.
- Source credential scan: PASS. Public repository visibility UNVERIFIED.
- No new Windows GPU FPS benchmark performed. No 30 FPS claim for this environment.
- Live Claude recognition, fetch performance and mentor readiness: UNVERIFIED. ANTHROPIC_API_KEY must be set locally; never upload it.
- Literal keyword scanning exempts typed commands, model visual notes, mandatory in_zone boolean and robot pose. It does not prove absence of all covert leakage.
