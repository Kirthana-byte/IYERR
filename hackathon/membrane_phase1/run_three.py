# Runs three independent commands and prints verified pass/fail results.
# With --dummy the same script runs three times and is explicitly not autonomous.
import argparse
from pathlib import Path
import subprocess
import sys

COMMANDS=['Bring the red cube to the green square',
          'Bring the round red thing to the green square',
          'Bring the tallest object to the green square']

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--dummy',action='store_true')
    parser.add_argument('--gui',action='store_true')
    parser.add_argument('--fast',action='store_true')
    parser.add_argument('--model',default='claude-sonnet-5-5')
    args=parser.parse_args()
    results=[]
    for text in COMMANDS:
        cmd=[sys.executable,'run_command.py',text,'--model',args.model]
        for flag in ('dummy','gui','fast'):
            if getattr(args,flag): cmd.append('--'+flag)
        completed=subprocess.run(cmd,cwd=Path(__file__).resolve().parent)
        results.append((text,'PASS' if completed.returncode==0 else 'FAIL / UNVERIFIED / ERROR'))
    print('\nDUMMY RESULTS (not autonomy)' if args.dummy else '\nAUTONOMOUS RESULTS')
    for command,status in results:
        print(f'{status}: {command}')
    raise SystemExit(0 if all(status=='PASS' for _,status in results) else 1)
