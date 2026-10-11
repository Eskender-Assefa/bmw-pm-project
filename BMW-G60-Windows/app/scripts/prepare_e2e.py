"""Create a new isolated browser-rehearsal database from the imported demo."""
import argparse
import json
import sqlite3
from pathlib import Path

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--name',default='e2e')
args=parser.parse_args()
if not args.name.replace('-','').replace('_','').isalnum():raise SystemExit('Use a simple directory name.')
target=root/'.local'/args.name
if (target/'cockpit.sqlite').exists():raise SystemExit('This rehearsal already exists. Choose a new --name to preserve its history.')
target.mkdir(exist_ok=True)
with sqlite3.connect(f'file:{(root/".local"/"cockpit.sqlite").as_posix()}?mode=ro',uri=True) as source,sqlite3.connect(target/'cockpit.sqlite') as dest:
    source.backup(dest)
print(json.dumps({'BMWPM_DATA_DIR':str(target),'note':'Source paths point to retained read-only originals; decisions and exports are isolated.'},indent=2))
