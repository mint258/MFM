"""Required S snapshots through original P probes and bootstrap, no model train.

GPU produces formal layer6 H/R3; CPU finishes original R1 and paired bootstrap.
Separate status files leave the ongoing3M training summary under its producer.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import resource
import socket
import subprocess
import time

import lifecycle_20261122 as life
from storage_20261122 import CONTROL, REPO, ROOT, admit, shared_guard, write


def boundary(guard, phase):
    guard.phase = phase
    if guard.stopping():
        raise life.StopAtBoundary()


def bind_evaluation(e, guard):
    """Leave original math intact; stop before work or after a committed update."""
    history = e.History
    class BoundaryHistory(history):
        def log(self, row, *, step, commit):
            super().log(row, step=step, commit=commit)
            boundary(guard, 'readout_committed_update')
    e.History = BoundaryHistory
    for name, phase in (('produce_missing_features', 'feature_production'),
                        ('ridge_probe', 'ridge_fit')):
        original = getattr(e, name)
        def wrapped(*args, _original=original, _phase=phase, **kwargs):
            boundary(guard, _phase)
            return _original(*args, **kwargs)
        setattr(e, name, wrapped)
    return e


@contextmanager
def evaluation_scope(readouts, guard):
    original = readouts.existing_evaluation
    readouts.existing_evaluation = lambda: bind_evaluation(original(), guard)
    try:
        yield
    finally:
        readouts.existing_evaluation = original


def registered(c, samples):
    if c['arm'] != 'S-B0' or c['seed'] != 0 or c['samples'] != 3000000:
        raise ValueError('This entry is only the registered B0 budget trend')
    if samples not in (1000000, 2000000) or samples not in c['evaluation_samples']:
        raise ValueError('Unregistered intermediate snapshot')


def require_empty_context(uuid):
    child=subprocess.Popen(['nvidia-smi','--query-compute-apps=gpu_uuid',
        '--format=csv,noheader,nounits'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    saved=life.identity(child.pid)
    try:
        out,error=child.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        if saved is not None:
            life.terminate_once(saved)
        raise RuntimeError('GPU context observation did not close')
    if child.returncode or uuid in [row.strip() for row in out.splitlines()]:
        raise RuntimeError('Small-group GPU context is occupied or could not be observed: '+error)


def work(c, samples, mode, guard):
    import readouts
    settings = readouts.configuration(c, samples)
    output = Path(settings['output'])
    output.mkdir(parents=True, exist_ok=True)
    with evaluation_scope(readouts, guard):
        if mode == 'gpu':
            readouts.gpu(settings)
            return dict(status='GPU_SNAPSHOT_COMPLETE_WAITING_CPU', layer=6,
                        samples=samples, checkpoint=settings['checkpoint'],
                        schedule='snapshot of the same3M cosine run')
        gpu_state = json.loads((output/'snapshot_gpu_status.json').read_text())
        if gpu_state['status'] != 'GPU_SNAPSHOT_COMPLETE_WAITING_CPU' or not gpu_state['owned_descendants_exited']:
            raise ValueError('Original snapshot GPU production/cleanup is not closed')
        scorefile = output/'scores.json'
        if not scorefile.is_file():
            boundary(guard, 'snapshot_cpu_ridge')
            readouts.finish_cpu_ridge(c, samples)
            boundary(guard, 'snapshot_original_bootstrap')
            # Finish the original scoring as one unit. Signals request stopping;
            # they cannot leave a published bootstrap marked complete halfway.
            e = readouts.existing_evaluation()
            statistics = e.score(output/'predictions.json', c['reference_manifest'],
                                 REPO/'results/s_recipe/scores.csv')
        else:
            statistics = json.loads(scorefile.read_text())
        for name in ('R1', 'R3'):
            if not (statistics[name]['complete'] and
                    statistics[name]['bootstrap_samples'] == statistics[name]['bootstrap_defined'] == 1000):
                raise ValueError('The original1000-draw snapshot statistics are incomplete')
        released = readouts.release_closed_feature_cache(dict(c, evaluation_samples=[samples]))
        return dict(status='COMPLETE', samples=samples, layer=6,
                    R1=statistics['R1']['mean_normalized_improvement'],
                    R3=statistics['R3']['mean_normalized_improvement'],
                    schedule='snapshot of the same3M cosine run',
                    descriptive_budget_trend_only=True, feature_cache=released)


def run(c, samples, mode, scheduler_record):
    registered(c, samples)
    node = socket.gethostname().split('.')[0]
    if node != c['node'] or node == 'compute-0-21':
        raise ValueError('Wrong or prohibited node')
    if mode == 'cpu' and (node not in {'compute-0-'+str(i) for i in range(8,20)} or os.environ.get('CUDA_VISIBLE_DEVICES')):
        raise ValueError('Ridge/bootstrap require a CPU8..19 node with CUDA hidden')
    if mode == 'gpu' and os.environ.get('CUDA_VISIBLE_DEVICES') != c['gpu_uuid']:
        raise ValueError('The real GPU UUID is not bound')
    guard = life.Guard.from_slurm(900, scheduler_record=scheduler_record)
    life.enable_subreaper()
    started = time.time()
    state = dict(run=c['run'], samples=samples, mode=mode, node=node,
                 job_id=int(os.environ['SLURM_JOB_ID']), started_at=started,
                 producer=vars(life.identity(os.getpid())), status='PREPARING',
                 closing_reserve_seconds=900, actual_deadline_epoch=guard.end_epoch)
    filename = 'snapshot_gpu_status.json' if mode == 'gpu' else 'snapshot_statistics_status.json'
    output = Path(c['output'])/('readout_'+str(samples))
    lock = None
    admitted = False
    with guard:
        try:
            admit()
            admitted = True
            shared_guard.check_with_timeout('s-recipe', 'node_ram', 16*1024**3)
            if mode == 'gpu':
                from train_guarded_20261122 import query_gpu
                lockpath = ROOT/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(c['gpu_uuid']+'.lock')
                lock = lockpath.open('a')
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                card = query_gpu(c['gpu_uuid'])
                if float(card[2])/float(card[3]) > .30 or float(card[3])-float(card[2]) < 18432:
                    raise RuntimeError('Snapshot GPU admission is no longer available')
                require_empty_context(c['gpu_uuid'])
                state['gpu_metadata_at_start'] = card
            state.update(work(c, samples, mode, guard))
        except life.StopAtBoundary:
            state.update(status='PAUSED_READOUT', reason=guard.reason)
            return 75
        except BaseException as error:
            state.update(status='FAILED', error=type(error).__name__+': '+str(error))
            raise
        finally:
            guard.phase = 'closing'
            life.close_children(180)
            if lock is not None:
                lock.close()
            state.update(ended_at=time.time(), elapsed_seconds=time.time()-started,
                         peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                         owned_descendants_exited=True)
            if admitted:
                output.mkdir(parents=True, exist_ok=True)
                write(output/filename, state)
            print(json.dumps(state), flush=True)
    return 0


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--configuration', type=Path, required=True)
    parser.add_argument('--samples', type=int, required=True)
    parser.add_argument('--mode', choices=('gpu','cpu'), required=True)
    args=parser.parse_args()
    record=json.loads((CONTROL/('deadline_'+os.environ['SLURM_JOB_ID']+'.json')).read_text())
    raise SystemExit(run(json.loads(args.configuration.read_text()), args.samples, args.mode, record))
