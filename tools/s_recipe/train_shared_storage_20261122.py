"""Subsequent S jobs: reuse the validated lifecycle, unified admission once.

No change to the frozen running entry. Each new process replaces only its own
storage callback; telemetry continues without repeated capacity walks.
"""
import argparse
import json
import os
from pathlib import Path
import train_guarded_20261122 as entry
from storage_20261122 import CONTROL, admit


def run(c, *, scheduler_record):
    admitted = False
    original = entry.capacity
    def once():
        nonlocal admitted
        if not admitted:
            admit()
            admitted = True
    entry.capacity = once
    try:
        return entry.run(c, scheduler_record=scheduler_record)
    finally:
        entry.capacity = original


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--configuration', type=Path, required=True)
    args = parser.parse_args()
    deadline = CONTROL/('deadline_'+os.environ['SLURM_JOB_ID']+'.json')
    print(json.dumps(run(json.loads(args.configuration.read_text()),
                         scheduler_record=json.loads(deadline.read_text()))), flush=True)
