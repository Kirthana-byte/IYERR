# Membrane Robot Hackathon: problem statement (summary)

Condensed from the supplied "Membrane Robot Hackathon: Problem Statement" (2 Nov 2026). The organizers' original is authoritative.

## Goal
Type a command; the robot completes a Fetch without human help. Claude finds the object from the robot camera, the robot drives to it, picks it up, carries it to the drop zone and releases it.

## Phases and scoring
| Component | Weight | Measured by |
|---|---|---|
| Phase 1: Fetch works | 40% | Live demo on two judge commands, pass/fail plus directness |
| Phase 1: Image-driven agent | 25% | Judges read tool-call and image logs |
| Phase 2: User verdict | 20% | Crowd pulses on three submitted clips |
| Stretch goal | 15% | Any one listed stretch goal shown working |

Tie-breaker: Phase 1 demo score. Any object-data leakage scores 0 on both Phase 1 components.

## Phase 1 requirements
- Three processes: game engine (scene, physics, camera, `localhost:8080`), Python agent (tool-use loop, logs), Claude API.
- One flat room with four walls, 4-6 coloured primitive shapes (at least two share a colour, at least two share a shape), one marked drop zone, one wheeled robot with a forward camera.
- One plain-language command per run, possibly with reasoning ("Bring the round red thing", "Bring the tallest object").
- States: Idle, Locate, Go to object, Pick up, Carry, Drop, Done, Blocked. Blocked on collision or no movement for 2 seconds; back off, turn, retry; fail after 3 retries.
- Outcomes: pass, fail_wrong_object, fail_not_reached, fail_collision.
- Endpoints: `/state`, `/look`, `/depth` (optional), `/move`, `/turn`, `/pickup`, `/drop`.
- Camera 640x480, 90 degree HFOV, 0.5 m high, tilted 10 degrees down. Move 1 m/s, turn 90 deg/s, pickup reach 0.5 m and +/-30 degrees.
- Object data stops at the engine boundary. Never send names, IDs, colours, shapes, positions, distances to objects, counts, masks or drop-zone coordinates to Claude.
- One Claude call per step, one `/look` after each move or turn, only the latest image. Log every step as JSONL with PNG frames. Soft target 25 steps, hard stop 60.
- Completion check: pass at least 3 different commands with logs showing Claude found each object from `/look` images, no keyboard or mouse input, live demo to a mentor.

## Phase 2
POV clip of each of the three hidden commands: MP4, 720p or higher, 10-20 seconds, command overlay for the first 2 seconds, no team names, logos or code on screen. Upload by hour 20 or Phase 2 scores 0. Crowds answer whether the correct object reached the zone and what went wrong.

## Stretch goals (any one)
Use pulse results to change behaviour with before/after clips; add furniture or walls blocking the straight path; Claude plans the full path with move and turn only (no `go_to`); multi-view reasoning ("the cube farthest from the green square").

## Submission
Public repository with engine and agent code, tool-call log for each hidden-command run, one paragraph on how Claude finds the object from the image, and a booked live demo slot.
