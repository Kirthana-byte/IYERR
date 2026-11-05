<!-- Explains this Phase 1 correction and how to update an existing installation safely. -->
# Historical update: arrival, retries and request auditing

**For the newest repair, follow REPAIR_GUIDE.md first.**

This update does not require a key. It does not change requirements.txt, camera
resolution, FOV, or your installed PyBullet/NumPy build.

## Install into the working Windows project

1. Stop running simulations.
2. Extract this archive into a temporary folder.
3. Copy the CONTENTS of its membrane_phase1 folder into your existing
   C:\Users\mrina\OneDrive\Desktop\hackoven\membrane_phase1 folder.
4. Choose Replace for matching project files. Keep your existing .venv, .env,
   and timestamped logs folders. None of those are included in this archive.
5. In PowerShell in the existing project folder, run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe run_command.py "Bring the red cube to the green square" --dummy --gui
.\.venv\Scripts\python.exe audit_run.py
```

Expected dummy result: PASS. It now normally uses THREE actions because arriving
in the zone automatically releases the item and finishes the run. The reported
reverse distance can be shorter than requested because arrival stops the motion.
Expected audit result: AUDIT PASS, mode dummy_not_sent. No API calls were made.
The camera settings and installed accelerated PyBullet remain unchanged.

## Behaviour choices

- Arriving while carrying an item triggers automatic Drop then Done when the
  robot centre and the entire item's footprint are in the marked zone. This
  implements arrival completion while preserving the brief's Drop -> Done flow.
- Initial failed action plus at most three recovery attempts; the retry budget
  is shared across blocked recovery, failed pickups and failed drops. The counter
  counts attempts after the initial failure, not the initial failure itself.
- A release outside the zone stays recoverable: the object is actually released,
  and the robot can fetch it again. The next recovery uses the same shared budget.
- An early done tool is rejected while an attempt is active and retry budget
  remains. A 60-step stop, API error or user interruption still ends unsuccessfully.
- Private grading remains separate. Unsupported target descriptions still require
  independent grading and are not automatically declared pass.

## Exact outbound request evidence

Each new run creates requests.jsonl. For live runs each line contains the exact
request body immediately before the SDK call, including the real base64 JPEG.
Authentication headers and API keys are not recorded. A row records an ATTEMPT;
an API error may mean it never reached the service. Dummy rows are explicitly
labelled dummy_not_sent. They are never sent to a model.

The guard rejects unexpected engine observation fields, altered tool definitions,
unreviewed system prompts, invalid action results and image metadata. audit_run.py
rechecks those structures and the fresh-image schedule. The command and visual
memory are legitimate user/Claude text, so an audit PASS is not a formal guarantee:
inspect those fields and images before mentor review. Raw request logs can be
large and contain your command and scene images. They are local, not auto-uploaded.

## After the key arrives

If no .env exists yet, copy .env.example to .env and set ANTHROPIC_API_KEY locally.
Do not overwrite an existing .env or paste your key into chat.

```powershell
.\.venv\Scripts\python.exe run_command.py "Bring the red cube to the green square" --gui
.\.venv\Scripts\python.exe audit_run.py
```

Check the first live run before running run_three.py --gui. Live calls cost API
credits. A dummy success is not a live vision success. Three live different-command
successes and mentor sign-off remain outstanding. Phase 2 is not implemented.
