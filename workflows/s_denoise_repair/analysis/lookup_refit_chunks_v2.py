"""Exact original lookup recipe, durable independent chunks, zero record cache."""
from concurrent.futures import ProcessPoolExecutor,as_completed
import argparse
import fcntl
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import socket
import sys
import time
import refit_lookup as canonical
from runtime import ROOT,OLD,assert_allocation,save,sha

PLAN=ROOT/'configs/lookup_refit_v2_plan.json'
OUT=ROOT/'diagnostics/lookup_refit_v2'
_PLAN=None


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def validate_plan():
    plan=json.loads(PLAN.read_text())
    for item in plan['sources']:
        if sha(item['path'])!=item['sha256']:
            if not (ROOT/'GUIDE_STOP.json').exists():save(ROOT/'GUIDE_STOP.json',dict(reason='GUIDE_STOP_FROZEN_BASELINE_INPUT_CHANGED',path=item['path']))
            raise AssertionError('GUIDE_STOP_FROZEN_BASELINE_INPUT_CHANGED')
    assert plan['TRAIN_records']==11104772 and plan['chunk_records']==65536 and plan['parts']==3
    assert plan['record_cache_bytes']==0 and plan['recipe']['view_seed']==0 and plan['recipe']['epoch']==0
    return plan


def bounds(number,plan):
    start=number*plan['chunk_records'];end=min(start+plan['chunk_records'],plan['TRAIN_records'])
    assert 0<=start<end<=11104772
    return start,end


def read_chunk(number,plan):
    path=OUT/'chunks'/('chunk_'+str(number).zfill(3)+'.json')
    if not path.exists():return None
    document=json.loads(path.read_text());result=document['result'];start,end=bounds(number,plan)
    assert document['status']=='DURABLE_COMPLETE_CANONICAL_LOOKUP_CHUNK'
    assert document['plan_sha256']==sha(PLAN) and document['result_sha256']==digest(result)
    assert (result['start'],result['end'],result['records'])==(start,end,end-start)
    for key,value in result['stats'].items():
        assert 0<=int(key)<119*119*101 and len(value)==3
        assert type(value[0]) is int and value[0]>0 and all(math.isfinite(v) for v in value)
    return dict(path=str(path),sha256=sha(path),number=number,records=end-start,origin_job_id=document['origin_job_id'])


def initialize():
    global _PLAN
    _PLAN=validate_plan();canonical.initialize_worker('train');canonical._DATASET.cache_bytes=0


def fit_and_commit(number):
    plan=_PLAN;job=os.environ['SLURM_JOB_ID'];folder=OUT/'worker_progress'/('job_'+job);folder.mkdir(parents=True,exist_ok=True)
    lock_path=OUT/'chunks'/('chunk_'+str(number).zfill(3)+'.lock')
    with lock_path.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        existing=read_chunk(number,plan)
        if existing:return dict(**existing,reused_durable_chunk=True)
        start,end=bounds(number,plan)
        progress=folder/('pid_'+str(os.getpid())+'.json')
        save(progress,dict(status='READ_AND_FIT_CANONICAL_CHUNK',chunk=number,start=start,end=end,timestamp=time.time()))
        began=time.monotonic();result=canonical.fit_chunk((start,end))
        assert (result['start'],result['end'],result['records'])==(start,end,end-start)
        document=dict(status='DURABLE_COMPLETE_CANONICAL_LOOKUP_CHUNK',result=result,result_sha256=digest(result),
            plan_sha256=sha(PLAN),origin_job_id=job,host=socket.gethostname(),worker_pid=os.getpid(),
            elapsed_seconds=time.monotonic()-began,record_cache_bytes=0,canonical_fit_function_unchanged=True)
        path=lock_path.with_suffix('.json');pending=path.with_name(path.name+'.'+str(os.getpid())+'.pending')
        with pending.open('x') as stream:
            json.dump(document,stream,sort_keys=True,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        check=json.loads(pending.read_text());assert check['result_sha256']==digest(check['result'])
        pending.replace(path)
        reference=read_chunk(number,plan);assert reference is not None
        save(progress,dict(status='CHUNK_COMMITTED',reference=reference,timestamp=time.time()))
        return dict(**reference,reused_durable_chunk=False)


def cache_control(plan,output):
    pointer=plan['cache_invariance_probe_reference'];assert sha(pointer['path'])==pointer['sha256']
    reference=json.loads(Path(pointer['path']).read_text());assert reference['status']=='EXACT_RECIPE_SMALL_READ_PROBE_COMPLETE'
    assert reference['cache_bytes']==0 and reference['original_recipe_sha256']==sha(canonical.__file__)
    canonical.initialize_worker('train')
    checks=[]
    try:
        for repeat in [0,1]:
            for row in reference['rows']:
                codes,expected,noisy=canonical.pairs(row['logical_index']);check=hashlib.sha256()
                for value in [codes,expected,noisy]:check.update(value.tobytes())
                assert check.hexdigest()==row['arrays_sha256'],'CACHE_OR_CPU_RECIPE_PROBE_ARRAYS_DIFFER'
            checks.append(dict(repeat=repeat,records=len(reference['rows']),arrays_bitexact=True))
        result=dict(status='CACHE_ENABLED_AND_REPEAT_HITS_MATCH_ZERO_CACHE_PROBE_BITEXACT',host=socket.gethostname(),
            checks=checks,source_reference=pointer,cache_bytes=canonical._DATASET.cache_bytes,
            cache_hits=getattr(canonical._DATASET._cache,'hits',None))
        save(output/'cache_control.json',result)
    finally:canonical._DATASET.close()
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--part',type=int);parser.add_argument('--pilot',action='store_true')
    args=parser.parse_args();assert args.pilot != (args.part is not None)
    assert_allocation();assert not (ROOT/'GUIDE_STOP.json').exists()
    plan=validate_plan();OUT.mkdir(exist_ok=True);(OUT/'chunks').mkdir(exist_ok=True)
    count=math.ceil(plan['TRAIN_records']/plan['chunk_records'])
    if args.pilot:numbers=plan['pilot_chunks'];mode='pilot'
    else:
        assert args.part in range(plan['parts']);numbers=list(range(args.part,count,plan['parts']));mode='part'+str(args.part)
    output=OUT/(mode+'_job'+os.environ['SLURM_JOB_ID']);output.mkdir(exist_ok=False)
    started=time.monotonic();control=cache_control(plan,output)
    existing={i:read_chunk(i,plan) for i in numbers};results=[r for r in existing.values() if r]
    pending=[i for i in numbers if existing[i] is None]
    pool=ProcessPoolExecutor(plan['workers_per_job'],mp_context=mp.get_context('spawn'),initializer=initialize)
    try:
        futures={pool.submit(fit_and_commit,i):i for i in pending}
        for future in as_completed(futures):
            results.append(future.result())
            save(output/'progress.json',dict(status='FITTING_CANONICAL_DURABLE_CHUNKS',completed_chunks=len(results),expected_chunks=len(numbers),
                committed_records=sum(r['records'] for r in results),elapsed_seconds=time.monotonic()-started,mode=mode))
    except BaseException as exc:
        save(output/'failure.json',dict(error=repr(exc),completed_chunks=len(results),references=results,
            durable_chunks_remain_valid=True,plan_sha256=sha(PLAN)))
        pool.shutdown(wait=False,cancel_futures=True)
        raise
    else:pool.shutdown(wait=True)
    references=[read_chunk(i,plan) for i in numbers];assert all(references)
    report=dict(status='LOOKUP_V2_PILOT_COMPLETE_NOT_FULL_POPULATION' if args.pilot else 'LOOKUP_V2_TRAIN_PART_COMPLETE',
        job_id=os.environ['SLURM_JOB_ID'],host=socket.gethostname(),part=args.part,mode=mode,
        assigned_chunk_numbers=numbers,references=references,committed_records=sum(r['records'] for r in references),
        expected_part_records=sum(bounds(i,plan)[1]-bounds(i,plan)[0] for i in numbers),
        cache_control=control,plan_sha256=sha(PLAN),elapsed_seconds=time.monotonic()-started,
        original_LMDB_written=False,new_LMDB_created=False)
    save(output/'result.json',report)
    if not args.pilot:save(OUT/(mode+'_latest.json'),dict(path=str(output/'result.json'),sha256=sha(output/'result.json')))
    print(json.dumps(dict(status=report['status'],mode=mode,chunks=len(numbers),records=report['committed_records'])),flush=True)


if __name__=='__main__':main()
