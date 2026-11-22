"""Subsequent S launches: original guarded training with one line-wide admission."""
import argparse
import json
import os
from pathlib import Path
import train_guarded_startup_20261122 as entry
from storage_20261122 import CONTROL
from storage_line_20261122 import admit


def run(c,*,scheduler_record):
    admitted=False
    original=entry.capacity
    def once():
        nonlocal admitted
        if not admitted:
            reports=admit(c)
            admitted=True
            print(json.dumps(dict(S_LINE_RESOURCE_ADMISSION=reports)),flush=True)
    entry.capacity=once
    try:
        return entry.run(c,scheduler_record=scheduler_record)
    finally:
        entry.capacity=original


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--configuration',type=Path,required=True)
    args=parser.parse_args()
    record=json.loads((CONTROL/('deadline_'+os.environ['SLURM_JOB_ID']+'.json')).read_text())
    print(json.dumps(run(json.loads(args.configuration.read_text()),scheduler_record=record)),flush=True)
