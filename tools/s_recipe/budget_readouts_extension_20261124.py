"""Explicit original9M trajectory snapshots through the original S/P probes."""
import argparse
import json
import os
from pathlib import Path

import snapshot_readouts_20261122 as original
from storage_20261122 import CONTROL
from storage_line_20261122 import admit


def registered(c,samples):
    if (c.get('readout_authority')!='docs/s_recipe/USER_DIRECTIVE_20261123C.md'
            or c.get('samples')!=9000000 or c.get('seed')!=0
            or c.get('run') not in ('S_B0_s0_9M','S_final_s0_9M')
            or type(samples) is not int or samples not in range(1000000,9000000,1000000)):
        raise ValueError('Only the eight new original9M trajectory points per run')
    if Path(c['output'])!=CONTROL/'training'/c['run']:
        raise ValueError('Use the original owned9M producer output')
    summary=json.loads((Path(c['output'])/'summary.json').read_text())
    if summary.get('samples')!=9000000 or summary.get('status')!='COMPLETE':
        raise ValueError('Original full9M and its primary endpoint must close first')
    closure=json.loads(Path(c['training_closure_record']).read_text())
    if not closure.get('owned_descendants_exited'):
        raise ValueError('The original9M producer has not closed its owned subtree')
    if not (Path(c['output'])/('samples_'+str(samples)+'.pt')).is_file():
        raise ValueError('Only an actually saved original1M checkpoint may be read')


def work(c,samples,mode,guard):
    result=original.work(c,samples,mode,guard)
    result.update(schedule='snapshot of this same9M cosine trajectory',
        descriptive_budget_trend_only=True,independent_budget=False,
        screening3M_comparison=False,layer=6)
    return result


def run(c,samples,mode,record):
    # Override resource admission in this isolated invocation only. Running
    # original9M producers and their loaded modules are untouched.
    legacy=original.admit
    c=dict(c,evaluation_peak_ram_bytes=16*1024**3,peak_ram_bytes=16*1024**3)
    original.admit=lambda:admit(c)
    try:
        return original.run(c,samples,mode,record,validate=registered,unit_work=work)
    finally:
        original.admit=legacy


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--configuration',type=Path,required=True)
    p.add_argument('--samples',type=int,required=True)
    p.add_argument('--mode',choices=('gpu','cpu'),required=True)
    args=p.parse_args()
    c=json.loads(args.configuration.read_text())
    record=json.loads((CONTROL/('deadline_'+os.environ['SLURM_JOB_ID']+'.json')).read_text())
    raise SystemExit(run(c,args.samples,args.mode,record))
