"""Registered endpoint diagnostics under the existing Slurm lifecycle guard.

The original layer probes and composition statistics own all numerical work.
These entries are separate from formal layer6 recipe decisions.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path

import snapshot_readouts_20261122 as worker
import terminal_readouts_20261122 as terminal
from storage_20261122 import CONTROL

STAGES=('curve_gpu','curve_cpu','geometry_gpu','geometry_cpu')


def registered(c,samples):
    terminal.registered(c,samples)
    import representations
    representations.registered(c)
    summary=json.loads((Path(c['output'])/'summary.json').read_text())
    if summary['status']!='COMPLETE':
        raise ValueError('Wait for the original formal layer6 statistics before diagnostics')


@contextmanager
def boundaries(module,guard):
    """Legacy admission sites become safe boundaries, without storage polling."""
    original=module.capacity
    module.capacity=lambda:worker.boundary(guard,'descriptive_unit_boundary')
    try:
        yield
    finally:
        module.capacity=original


def work(c,samples,stage,guard):
    if stage not in STAGES:
        raise ValueError('Unregistered diagnostic stage')
    import readouts
    import representations
    import endpoint_readouts
    import s_statistics
    directory=Path(c['output'])/'diagnostic_readouts'
    if stage.endswith('_cpu'):
        prefix=stage.split('_')[0]
        proof=terminal.closed_phase(directory/(prefix+'_gpu_status.json'),c)
        if proof['status']!='GPU_DIAGNOSTIC_COMPLETE_WAITING_CPU':
            raise ValueError('The matching descriptive GPU phase is not closed')
    with (worker.evaluation_scope(readouts,guard), boundaries(representations,guard),
          boundaries(endpoint_readouts,guard), boundaries(s_statistics,guard)):
        worker.boundary(guard,'registered_'+stage)
        if stage=='curve_gpu':
            result=endpoint_readouts.gpu(c)
        elif stage=='curve_cpu':
            result=endpoint_readouts.cpu(c)
        elif stage=='geometry_gpu':
            result=representations.extract(c)
        else:
            result=representations.calculate(c)
    return dict(status=('GPU_DIAGNOSTIC_COMPLETE_WAITING_CPU' if stage.endswith('_gpu') else 'COMPLETE'),
                samples=samples,diagnostic=stage,descriptive_only=True,
                formal_decision_layer=6,original_status=result.get('status','CLOSED_ORIGINAL_MANIFEST'))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--configuration',type=Path,required=True)
    parser.add_argument('--stage',choices=STAGES,required=True)
    args=parser.parse_args()
    c=json.loads(args.configuration.read_text())
    prefix,mode=args.stage.split('_')
    record=json.loads((CONTROL/('deadline_'+os.environ['SLURM_JOB_ID']+'.json')).read_text())
    raise SystemExit(worker.run(c,c['samples'],mode,record,validate=registered,
        unit_work=lambda c,n,mode,guard:work(c,n,args.stage,guard),
        status_output=Path(c['output'])/'diagnostic_readouts',status_prefix=prefix))
