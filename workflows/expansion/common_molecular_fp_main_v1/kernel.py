"""Existing candidate scientific function objects, bounded selected-MID work."""
import os,time
from pathlib import Path
from . import contract as C
from workflows.expansion.common_molecular_fp_candidate_v1 import worker as W,projection as P
FUN=None
def initialize(barrier,proof_directory):
    global FUN
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    FUN,proof=W.load_kernel()
    C.Q.write_new(Path(proof_directory)/f'worker_{os.getpid()}.json',{'worker_pid':os.getpid(),'job_id':os.environ['SLURM_JOB_ID'],
        'kernel_source_scope_proof':proof,'original_function_objects_checked_in_this_worker':True})
    barrier.wait(timeout=180)
def work(task):
    start=time.process_time();results=[W.derive(value,i,FUN) for i,value in enumerate(task['variants'])]
    reduced=P.reduce_variants(task['molecule_id'],task['effective_role'],task['native_records'],results)
    return {'worker_pid':os.getpid(),'worker_CPU_seconds':time.process_time()-start,'reduction':reduced}
