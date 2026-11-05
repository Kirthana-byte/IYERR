# Scans repository text for likely credentials without printing their values.
# A local .env is ignored; a tracked .env is reported as a repository failure.
import argparse
import fnmatch
import re
import subprocess
from pathlib import Path

PATTERNS=[re.compile(r'sk-ant-[A-Za-z0-9_-]{20,}'),
          re.compile(r'sk-(?:proj-)?[A-Za-z0-9_-]{32,}'),
          re.compile(r'(?i)(?:ANTHROPIC_API_KEY|OPENAI_API_KEY)\s*[:=]\s*[\"\']?([A-Za-z0-9_-]{20,})')]


def scan(root):
    root=Path(root).resolve();failures=[];count=0
    try:
        top=subprocess.run(['git','-C',str(root),'rev-parse','--show-toplevel'],capture_output=True,text=True,check=True)
        if Path(top.stdout.strip()).resolve()!=root:raise ValueError('Not the project repository root')
        result=subprocess.run(['git','-C',str(root),'ls-files','-z'],capture_output=True,check=True)
        files=[root/name for name in result.stdout.decode().split('\0') if name]
    except (OSError,ValueError,subprocess.SubprocessError):
        files=[p for p in root.rglob('*') if p.is_file() and not any(x in p.parts for x in
            ('.git','.venv','__pycache__','.pytest_cache','logs','submission'))
            and not p.name.startswith('.env')]
    for path in files:
        if path.name=='.env':failures.append(f'{path.relative_to(root)}: tracked credential file')
        if path.suffix.lower()=='.zip':failures.append(f'{path.relative_to(root)}: archive in repository');continue
        if path.stat().st_size>2_000_000:continue
        try:text=path.read_text(encoding='utf-8')
        except UnicodeError:continue
        count+=1
        for number,line in enumerate(text.splitlines(),1):
            if any(pattern.search(line) for pattern in PATTERNS):
                failures.append(f'{path.relative_to(root)}:{number}: possible API key (value withheld)')
    return count,failures


def main():
    parser=argparse.ArgumentParser();parser.add_argument('folder',nargs='?',default=str(Path(__file__).parent))
    args=parser.parse_args();root=Path(args.folder)
    ignore=(root/'.gitignore').read_text().splitlines() if (root/'.gitignore').exists() else []
    ignored=all(p in ignore for p in ('.env','__pycache__/','logs/*','*.zip'))
    print(('PASS' if ignored else 'FAIL')+' gitignore: .env, caches, logs, ZIPs')
    count,failures=scan(root)
    print(('FAIL' if failures else 'PASS')+f' API-key scan: {count} text files')
    for failure in failures:print('FAIL '+failure)
    print('Public repository visibility: UNVERIFIED; this script does not publish a repository.')
    return int(not ignored or bool(failures))


if __name__=='__main__':raise SystemExit(main())
