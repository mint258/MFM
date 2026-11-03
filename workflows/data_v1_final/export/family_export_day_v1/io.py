"""Main allocation-only IO; inherited exact FD/SHA, clock, quota and natural drain."""
from __future__ import annotations
import contextlib,hashlib,json,os,pathlib,stat,time
from workflows.data_v1_final.export.d5_inputs_builder_v1 import io as O
from workflows.data_v1_final.export.d5_inputs_compound_day_v1 import resources as R
from . import contract as C
OBS=O.OBS;Budget=R.Budget;Authority=R.Authority;literal=R.literal;actual_ref=O.actual_ref;held=O.held;body=O.body;json_body=O.json_body;jsonl=O.jsonl
worker_check=O.worker_check


def batches(ref,declared,check,*,columns=None,row_groups=None,batch_size=1):
    import pyarrow.parquet as pq
    C.need(type(batch_size) is int and 1<=batch_size<=16,'BOUNDED_SOURCE_ROWS_NOT_FULL_FAMILY_MATERIALIZATION')
    with O.held(ref,declared,check) as (_,fd,_):
        with os.fdopen(os.dup(fd),'rb') as stream:
            p=pq.ParquetFile(stream)
            try:
                for batch in p.iter_batches(batch_size=batch_size,columns=columns,row_groups=row_groups,use_threads=False):
                    check();C.need(batch.nbytes<=128<<20,'EXACT_SOURCE_BATCH_SOFTWARE_BOUND');yield batch
            finally:p.close()


def source_batched(spec,declared,check,groups=None,columns=None):
    return batches(spec['file'],declared,check,columns=columns,row_groups=groups,batch_size=1)


def data_json_new(path,value):
    raw=(json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n').encode()
    with pathlib.Path(path).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return actual_ref(path)


def guard(path,plan,proof_path):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    proof=require_startup(proof_path,expected_scope_key=C.SCOPE,expected_scope_parameters=C.parameters(plan),
        expected_execution_argv=[C.PY,'-B','-m',C.MODULE,'--plan',str(path),'--startup-proof',str(proof_path)],
        expected_source=C.HERE/'run.py',expected_kind='analysis',required_references=[C.Q.pin(path),*plan['source_references']])
    req=proof['request'];C.need(req['cpus']==16 and req['node']==plan['node'] and req['node'] in ('compute-0-14','compute-0-18') and req['pilot'] is False
        and req['wall_seconds']==86400 and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and req['estimated_peak_output_bytes']==plan['output_cap_bytes'] and req['data_references']==plan['data_references'],
        'GENERIC_CURRENT_ACTUAL_CPU16_DAY_NO_MEM_NOT_GPU_OR_OLD_SCOPE')
    for r in plan['source_references']:C.need(r in req['source_references'] and C.Q.pin(r['path'])==r,'ALL_INSTALLED_SOURCE_AND_SMALL_PARENT_PINS')
    result=C.final_parents(plan);C.need(result[7]==plan['data_references'],'SAME_FINAL_PARENT_DATA_SET_NO_LOGIN_NUMERIC_READ')
    return proof,result


def append(path,value):
    raw=(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    C.need(len(raw)<=1<<20,'BOUNDED_COMPLETE_SHARD_CHECKPOINT_HEADER')
    with pathlib.Path(path).open('ab') as f:f.write(raw);f.flush();os.fsync(f.fileno())


def source_frame(ref):
    p=literal(ref['path']);s=p.lstat();C.need(stat.S_ISREG(s.st_mode) and s.st_uid==1278 and s.st_size==ref['bytes'],'OWN_IMMUTABLE_SOURCE_FRAME')
    return list(R.frame(s))


def hash_inputs(references,budget):
    observed={}
    for r in references:
        with O.held(r,references,budget.check) as (_,_,frame):observed[r['path']]={'reference':C.reference(r),'frame':list(frame)}
    return observed


@contextlib.contextmanager
def same_parent_fd(reference,witness):
    r=C.reference(reference);C.need(witness['reference']==r,'ACTUAL_PARENT_WHOLE_SHA_WITNESS_EXACT_REFERENCE')
    p=literal(r['path']);before=source_frame(r);C.need(before==witness['frame'],'SOURCE_FRAME_CHANGED_SINCE_PARENT_SHA')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        C.need(list(R.frame(os.fstat(fd)))==before,'SOURCE_WORKER_OWN_FD_SAME_ACTUAL_PARENT_FRAME');yield fd
    finally:
        try:C.need(list(R.frame(os.fstat(fd)))==before==source_frame(r),'WORKER_SOURCE_FD_PATH_FRAME_STABLE')
        finally:os.close(fd)


def worker_batches(spec,witness,check,groups,columns):
    import pyarrow.parquet as pq
    with same_parent_fd(spec['file'],witness) as fd:
        with os.fdopen(os.dup(fd),'rb') as raw:
            pf=pq.ParquetFile(raw)
            try:
                for batch in pf.iter_batches(batch_size=1,row_groups=groups,columns=columns,use_threads=False):
                    check();C.need(batch.nbytes<=128<<20,'ONE_COMPLETE_SOURCE_ROW_BOUND_NO_TRUNCATION');yield batch
            finally:pf.close()
