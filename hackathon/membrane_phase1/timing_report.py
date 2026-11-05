# Summarises measured API, motion, sensor and image times; never sends them to Claude.
import argparse
import json
from pathlib import Path


def report(folder):
    rows=[json.loads(line) for line in (Path(folder)/'timings.jsonl').read_text().splitlines()]
    for phase in ('api','action','sensors','image'):
        values=[r['elapsed_seconds'] for r in rows if r['phase']==phase]
        if values:
            print(f'{phase}: {len(values)} samples, total {sum(values):.2f}s, mean {sum(values)/len(values):.2f}s')
    print('Measured phases only; startup, request serialization and clip export are not included.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder')
    report(parser.parse_args().folder)
