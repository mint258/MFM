"""Benchmark private MPS using the original trainer and the completed shared control."""
from contextlib import contextmanager
import fcntl
import json
import os

import cpu_perf_concurrency as bench
from cpu_perf_mps import PrivateMPS


@contextmanager
def mps_observer(service):
    """Install explicit MPS-aware hooks only in this benchmark parent process."""
    original_guard, original_stop = bench.require_controlled_contexts, bench.stop_own

    def guard(gpu, background, own=(), *, registered=False):
        active=service.validate_gpu_contexts(bench.compute_pids(gpu),own)
        if not set(background)<=active or active-set(background)-set(own):
            raise RuntimeError('Unexpected context or missing background in MPS comparison')
        for pid,bound in background.items():
            current=bench.capture_process_identity(pid,expected_job=bound['slurm_job_id'])
            if current.get('status')!='ACTIVE' or any(current.get(k)!=bound.get(k) for k in bench.IDENTITY):
                raise RuntimeError('Background identity changed during MPS comparison')
        if registered and not active-set(background)<=bench.registered_model_pids(gpu):
            raise RuntimeError('Unregistered MPS benchmark participant')

    def stop(children, identities):
        if any(child.poll() is None for child in children):
            service.terminate_clients(identities)
        original_stop(children,identities)

    bench.require_controlled_contexts,bench.stop_own=guard,stop
    try:
        yield
    finally:
        bench.require_controlled_contexts,bench.stop_own=original_guard,original_stop


def main():
    quota=bench.capacity()
    if len(bench.GPUS)!=1:
        raise ValueError('One physical GPU must be bound')
    gpu=bench.GPUS[0]
    previous=None
    reuse=os.environ.get('MFM_CPU_REUSE_JOB')
    reused=[]
    if reuse:
        previous=bench.SCRATCH/('concurrency_'+reuse)
        admission=json.loads((previous/'admission.json').read_text())
        if admission['gpu']!=gpu or admission['authorized_background']:
            raise RuntimeError('Reuse requires the same idle card and no background')
        for name in ('ordinary_single','mps_single'):
            bench.measured_rate(previous/name/'task0')
            row=json.loads((previous/name/'summary.json').read_text())
            if row['tasks']!=1 or row['cpus_per_task']!=int(os.environ.get('MFM_CPU_CORES_PER_MODEL','16')):
                raise RuntimeError('Reused phase execution configuration differs')
            reused.append(row)
    background=bench.capture_background(gpu)
    if os.environ.get('MFM_CPU_BASELINE_JOB'):
        previous=bench.SCRATCH/('concurrency_'+os.environ['MFM_CPU_BASELINE_JOB'])
        baseline=json.loads((previous/'summary.json').read_text())
        if baseline['status']!='MEASUREMENTS_COMPLETE' or baseline['gpu']!=gpu:
            raise RuntimeError('The ordinary same-card control must finish successfully first')
        prior=json.loads((previous/'admission.json').read_text())['authorized_background']
        if set(map(int,prior))!=set(background) or any(
                prior[str(pid)].get(k)!=bound.get(k) for pid,bound in background.items() for k in bench.IDENTITY):
            raise RuntimeError('MPS must retain the exact original background process')
    cores=int(os.environ.get('MFM_CPU_CORES_PER_MODEL','16'))
    allocated=bench.allocated_cpus()
    bench.cpu_layout(allocated,2,cores)
    root=bench.SCRATCH/('concurrency_'+os.environ['SLURM_JOB_ID'])
    lock_name=gpu+('.cpu_perf_benchmark.lock' if background else '.lock')
    with (bench.LOCKS/lock_name).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        bench.require_controlled_contexts(gpu,background)
        root.mkdir(exist_ok=False)
        (root/'admission.json').write_text(json.dumps(dict(gpu=gpu,quota=quota,
            cpu_affinity=allocated,model_cores=cores,workers=14,authorized_background=background,
            baseline_job=os.environ.get('MFM_CPU_BASELINE_JOB'),
            reused_completed_phases_from=reuse,
            source_revision=os.environ.get('MFM_CPU_SOURCE_REVISION'),
            numerical_path='ORIGINAL_RECOMPUTATION_RESTORED',execution='PRIVATE_MPS'),indent=2)+'\n')
        results=[row for row in reused if not row['name'].startswith('mps_')]
        if previous is None:
            results.append(bench.phase(root,gpu,'ordinary_single',1,cores,allocated,background))
        mps_results=[row for row in reused if row['name'].startswith('mps_')]
        with PrivateMPS(gpu,root) as service:
            keys=('CUDA_VISIBLE_DEVICES','CUDA_MPS_PIPE_DIRECTORY','CUDA_MPS_LOG_DIRECTORY')
            old={key:os.environ.get(key) for key in keys}
            os.environ.update({key:service.env[key] for key in keys})
            try:
                with mps_observer(service):
                    phases=[] if reuse else [('mps_single',1)]
                    phases.append(('mps_concurrent2',2))
                    if len(allocated)>=3*cores:phases.append(('mps_concurrent3',3))
                    phases.append(('mps_single_final',1))
                    for name,count in phases:
                        result=bench.phase(root,gpu,name,count,cores,allocated,background)
                        records=[json.loads(path.read_text())
                            for path in (root/name).glob('task*.registered.json')]
                        identities={record['pid']:record for record in records}
                        service.confirm_clients(identities)
                        service.wait_closed(identities)
                        mps_results.append(result)
            finally:
                for key,value in old.items():
                    if value is None:os.environ.pop(key,None)
                    else:os.environ[key]=value
        results.extend(mps_results)
        reference=max(mps_results[0]['samples_per_second'][0],mps_results[-1]['samples_per_second'][0])
        eligible=[row['tasks'] for row in mps_results if min(row['samples_per_second'])>=.85*reference]
        summary=dict(status='MEASUREMENTS_COMPLETE',job=os.environ['SLURM_JOB_ID'],gpu=gpu,
            execution='PRIVATE_MPS',baseline_job=os.environ.get('MFM_CPU_BASELINE_JOB'),results=results,
            reused_completed_phases_from=reuse,
            recommended_concurrency=max(eligible),threshold_fraction=.85,
            recommendation_single_reference=reference,
            single_baseline_drift_fraction=mps_results[-1]['samples_per_second'][0]/mps_results[0]['samples_per_second'][0]-1)
        bench.capacity()
        (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(summary),flush=True)


if __name__=='__main__':
    main()
