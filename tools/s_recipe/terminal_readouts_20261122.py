"""Formal S endpoints, reusing original probes/statistics under the same guard.

No training on import or in this entry. Layer curves remain separate registered
descriptive work; only B0/G1 retain their known terminal intermediate caches.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import time

import snapshot_readouts_20261122 as worker
from checkpoint_binding import validate_resume
from storage_20261122 import CONTROL, write


def closed_phase(path, c):
    value=json.loads(Path(path).read_text())
    consumed=value.get('samples',value.get('result',{}).get('samples'))
    if (value.get('run')!=c['run'] or consumed!=c['samples'] or
            not value.get('owned_descendants_exited') or not value.get('ended_at')):
        raise ValueError('The exact producer budget and owned-process exit are not closed')
    return value


def registered(c,samples):
    if samples!=c['samples'] or samples not in (3000000,9000000):
        raise ValueError('Only registered full3M/9M endpoints')
    from dispatch import authorized
    authorized(c)
    summary=json.loads((Path(c['output'])/'summary.json').read_text())
    if summary.get('samples')!=samples or summary.get('status') not in (
            'TRAINING_COMPLETE_READOUT_PENDING',
            'GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS','COMPLETE'):
        raise ValueError('The training producer has not closed its full budget')
    if not (Path(c['output'])/('samples_'+str(samples)+'.pt')).is_file():
        raise ValueError('The producer-published final checkpoint is unavailable')
    # Bind once to the producer's existing metadata. The original evaluator
    # still owns the single required checkpoint/model load for its forward.
    producer_configuration=json.loads((Path(c['output'])/'configuration.json').read_text())
    validate_resume(c,producer_configuration)
    # The controller names the actual producer record after native exit and
    # scheduler closure, including the separately verified legacy B0 group.
    closed_phase(c['training_closure_record'],c)


@contextmanager
def admitted_legacy_scope(module):
    """Reuse math while replacing legacy peer-budget callbacks after admission."""
    original=module.capacity
    module.capacity=lambda: None
    try:
        yield
    finally:
        module.capacity=original


def work(c,samples,mode,guard):
    import readouts
    output=Path(c['output'])
    summary=json.loads((output/'summary.json').read_text())
    if summary['status']=='COMPLETE':
        return dict(status='COMPLETE',already_closed=True,layer=6,samples=samples)
    with worker.evaluation_scope(readouts,guard):
        if mode=='gpu':
            started=time.monotonic()
            # These are the two pre-registered descriptive points known before
            # final selection. Other arms produce only formal layer6 here.
            if samples==3000000 and c['seed']==0 and c['arm'] in ('S-B0','S-G1'):
                import endpoint_readouts
                with admitted_legacy_scope(endpoint_readouts):
                    endpoint_readouts.capture(c)
            for checkpoint_samples in c['evaluation_samples']:
                worker.boundary(guard,'formal_checkpoint_readout')
                readouts.gpu(readouts.configuration(c,checkpoint_samples))
            summary.update(status='GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS',
                gpu_readout_seconds_this_process=time.monotonic()-started,
                gpu_readout_job=os.environ['SLURM_JOB_ID'],
                gpu_readout_node=socket.gethostname().split('.')[0])
            write(output/'summary.json',summary)
            return dict(status='GPU_TERMINAL_COMPLETE_WAITING_CPU',layer=6,samples=samples)
        # New guarded GPU workers write this themselves. Legacy B0 must supply
        # its actual phase/group-exit observation, not just a batch exit code.
        proof=output/'readout/terminal_gpu_status.json'
        if not proof.is_file():
            proof=Path(c['gpu_phase_exit_evidence'])
        phase=closed_phase(proof,c)
        if phase['status'] not in ('GPU_TERMINAL_COMPLETE_WAITING_CPU',
                                  'GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS'):
            raise ValueError('The formal GPU phase is not closed')
        worker.boundary(guard,'original_formal_cpu_statistics')
        import s_statistics
        with admitted_legacy_scope(s_statistics):
            result=s_statistics.finalize(c)
        return dict(status=result['status'],samples=samples,layer=6,
                    original_statistics=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--configuration',type=Path,required=True)
    parser.add_argument('--mode',choices=('gpu','cpu'),required=True)
    args=parser.parse_args()
    c=json.loads(args.configuration.read_text())
    record=json.loads((CONTROL/('deadline_'+os.environ['SLURM_JOB_ID']+'.json')).read_text())
    raise SystemExit(worker.run(c,c['samples'],args.mode,record,validate=registered,
        unit_work=work,status_output=Path(c['output'])/'readout',status_prefix='terminal'))
