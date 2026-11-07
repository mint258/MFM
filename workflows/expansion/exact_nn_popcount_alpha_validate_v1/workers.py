"""Benchmark-only paired private caches; no production worker or QueryCache seam."""
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import struct
import time
from ..alpha_runtime_v1 import common as Q
from ..exact_nn_cached_v1 import engine as old
from ..exact_nn_popcount_cpp_v1 import backend as new

_STATE=None
_BARRIER=None


def initialize(path,frame,n,cap,build_ref,counter,barrier,source_refs):
    global _STATE,_BARRIER
    _BARRIER=barrier
    try:
        for ref in source_refs:Q.verify(ref)
        Q.need(Q.reference(old.__file__)in source_refs and Q.reference(new.__file__)in source_refs,'Actual imported worker engine sources pinned')
        with counter.get_lock():slot=counter.value;counter.value+=1
        baseline_rss=old.enforce_rss(cap)
        instances={};loads={};load_order=('original','native')if slot%2==0 else('native','original')
        for name in load_order:
            began=time.monotonic();cpu=time.process_time()
            instance=old.load_reference(path,frame,n,cap)if name=='original'else new.load_reference(path,frame,n,cap,build_manifest_reference=build_ref)
            instances[name]=instance
            loads[name]=dict(wall_seconds=time.monotonic()-began,cpu_seconds=time.process_time()-cpu,rss_after=old.enforce_rss(cap))
        Q.need(instances['original'].n==instances['original'].decode_calls==instances['native'].n==instances['native'].reference_records_loaded==n,
            'Every worker loads both complete1196122 private caches')
        _STATE=dict(instances=instances,slot=slot,cap=cap,loads=loads,load_order=load_order,build_ref=build_ref,baseline_rss=baseline_rss)
        barrier.wait()
    except BaseException:barrier.abort();raise


def ready():
    _BARRIER.wait();s=_STATE
    return dict(worker_pid=os.getpid(),slot=s['slot'],uid=os.getuid(),job_id=os.environ.get('SLURM_JOB_ID'),
        reference_molecules=s['instances']['original'].n,original_decode_calls=s['instances']['original'].decode_calls,
        native_records_loaded=s['instances']['native'].reference_records_loaded,loads=s['loads'],load_order=s['load_order'],
        baseline_rss=s['baseline_rss'],native_storage_statistics=s['instances']['native'].native_statistics,
        rss_after_both=old.enforce_rss(s['cap']),original_engine_reference=Q.reference(old.__file__),
        native_wrapper_reference=Q.reference(new.__file__),native_build_reference=s['build_ref'],
        native_kernel_info=s['instances']['native'].kernel.build_info())


def batch(rows):
    try:
        _BARRIER.wait()  # Exactly one4-query task per each of16 ready workers.
        s=_STATE;result=[]
        for ordinal,raw in rows:
            values={};timing={};order=('original','native')if ordinal%2==0 else('native','original')
            for name in order:
                began=time.monotonic();cpu=time.process_time();values[name]=s['instances'][name].nearest(raw)
                timing[name]=dict(wall_seconds=time.monotonic()-began,cpu_seconds=time.process_time()-cpu)
            old_bits=struct.pack('<d',values['original']['score']).hex();new_bits=struct.pack('<d',values['native']['score']).hex()
            Q.need(values['original']==values['native']and old_bits==new_bits,'All8/F64 mismatch query='+str(ordinal)+' '+json.dumps(dict(values=values,original_bits=old_bits,native_bits=new_bits),sort_keys=True))
            result.append(dict(query_ordinal=ordinal,fingerprint_sha256=hashlib.sha256(raw).hexdigest(),
                original=values['original'],native=values['native'],score_bits=old_bits,
                timing=timing,execution_order=order,rss_after=old.enforce_rss(s['cap'])))
        return dict(worker_pid=os.getpid(),slot=s['slot'],results=result)
    except BaseException:_BARRIER.abort();raise
