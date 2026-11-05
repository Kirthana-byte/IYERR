# Supervises one isolated run: starts the engine process, runs the HTTP-only agent,
# and reads the private evaluation only AFTER the agent has stopped.
# Dummy mode is a fixed plumbing test, never evidence of language/vision autonomy.
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from agent.runner import run

ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command')
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--dummy',action='store_true')
    modes.add_argument('--pixel',action='store_true',help='TEST ONLY: HTTP pixel controller; never Claude')
    parser.add_argument('--model',default='claude-sonnet-5-5')
    parser.add_argument('--gui',action='store_true',help='Show the simulator spectator window')
    parser.add_argument('--fast',action='store_true',help='Disable real-time pacing for tests')
    parser.add_argument('--seed',type=int,default=0)
    parser.add_argument('--port',type=int,default=8080)
    parser.add_argument('--no-record-pov',action='store_true',help='Skip recording for quick plumbing tests')
    args=parser.parse_args()
    load_dotenv(ROOT/'.env')
    if not args.dummy and not args.pixel and not os.environ.get('ANTHROPIC_API_KEY','').strip():
        parser.error('No ANTHROPIC_API_KEY. Use --dummy/--pixel now, or set it in your local .env later.')
    # Never attach to a previously running scene by accident.
    with socket.socket() as check:
        try:
            check.bind(('127.0.0.1',args.port))
        except OSError:
            parser.error(f'Port {args.port} is in use. Stop the existing engine first.')
    folder=ROOT/'logs'/datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    folder.mkdir(parents=True)
    report=folder/'evaluation.json'
    stop=folder/'stop.signal'
    command=[sys.executable,'-m','engine.server','--command',args.command,
             '--seed',str(args.seed),'--report',str(report),'--stop-file',str(stop),
             '--port',str(args.port)]
    if not args.no_record_pov: command.append('--record-pov')
    if args.gui: command.append('--gui')
    if args.fast: command.append('--fast')
    env=os.environ.copy()
    env.pop('ANTHROPIC_API_KEY',None) # engine never needs the key
    result={}
    error=None
    with (folder/'engine.log').open('w',encoding='utf-8') as engine_log:
        process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=engine_log,stderr=engine_log)
        try:
            for _ in range(300):
                if process.poll() is not None:
                    raise RuntimeError(f'Engine failed to start; see {folder / "engine.log"}')
                with socket.socket() as sock:
                    if sock.connect_ex(('127.0.0.1',args.port))==0:
                        break
                time.sleep(.1)
            else:
                raise RuntimeError('Engine startup timed out')
            if args.dummy:
                print('DUMMY: fixed script; command is NOT interpreted. This is NOT a vision demo.',flush=True)
            if args.pixel:
                print('PIXEL AGENT: TEST ONLY. OpenCV pixels, no Claude/API calls.',flush=True)
                from agent.pixel_agent import run as pixel_run
                result=pixel_run(args.command,folder,base=f'http://127.0.0.1:{args.port}')
            else:
                result=run(args.command,folder,base=f'http://127.0.0.1:{args.port}',
                           dummy=args.dummy,model=args.model)
        except Exception as exc:
            error=f'{type(exc).__name__}: {exc}'
        finally:
            stop.write_text('finish',encoding='utf-8')
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate();process.wait(timeout=10)
    # Preserve completed action count even if the API returned an invalid response.
    action_log=folder/'steps.jsonl'
    result.setdefault('steps',sum(bool(line.strip()) for line in action_log.read_text().splitlines()) if action_log.exists() else 0)
    evaluation=json.loads(report.read_text()) if report.exists() else {}
    outcome=evaluation.get('outcome')
    # Unsupported language isn't silently called correct or a measured failure.
    verdict='ERROR' if error else ('PASS' if outcome=='pass' else 'UNVERIFIED' if outcome is None else 'FAIL')
    summary={**result,'mode':'pixel' if args.pixel else 'dummy' if args.dummy else 'claude','verdict':verdict,'outcome':outcome,'error':error,
             'evaluation':evaluation,'command':args.command}
    (folder/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
    print(f'Logs: {folder}')
    if not args.no_record_pov:
        try:
            from export_clip import export
            export(folder)
        except (ValueError,OSError,RuntimeError,subprocess.SubprocessError) as exc:
            print(f'FAIL clip export: {exc}')
    return 0 if verdict=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
