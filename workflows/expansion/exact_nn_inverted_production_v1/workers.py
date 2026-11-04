"""Explicit inverted-only spawn worker API; no scientific retries/subsets/debug IPC."""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import os
from pathlib import Path
import time
from ..alpha_runtime_v1 import common as Q
from ..exact_nn_cached_v1.engine import file_frame,enforce_rss,current_rss
from ..exact_nn_inverted_cpp_v1 import backend
from . import authority

_REFERENCE=None
_BARRIER=None
_ADOPTION=None


def _initialize(path,frame,n,cap,barrier,adoption_ref):
    global _REFERENCE,_BARRIER,_ADOPTION
    _BARRIER=barrier
    try:
        _ADOPTION,packed=authority.adopted(adoption_ref)
        Q.need(n==authority.N and str(Path(path))==packed['fingerprints']['path'],'Same accepted complete reference path/cardinality')
        _REFERENCE=backend.load_reference(path,frame,n,cap,build_manifest_reference=_ADOPTION['build_manifest_reference'])
        Q.need(_REFERENCE.reference_records_loaded==n,'Native worker loaded every reference record')
        barrier.wait()
    except BaseException:barrier.abort();raise


def _ready():
    _BARRIER.wait()
    return dict(worker_pid=os.getpid(),reference_records_loaded=_REFERENCE.reference_records_loaded,
        reference_load_seconds=_REFERENCE.load_wall_seconds,reference_load_rss_bytes=_REFERENCE.load_rss_bytes,
        backend_implementation=_REFERENCE.implementation,backend_build_reference=_ADOPTION['build_manifest_reference'],
        backend_binary_reference=_ADOPTION['binary_reference'],runtime_popcount_backend=_REFERENCE.kernel.build_info()['runtime_popcount_backend'],
        intersection_backend=_REFERENCE.kernel.build_info()['intersection_backend'])


def fixed_result(reference,rows):
    result=[]
    for identity,raw in rows:
        value=reference.nearest(raw);value.pop('searched_popcount_groups')
        result.append((identity,raw,value))
    return result


def _batch(rows):
    began=time.monotonic();results=fixed_result(_REFERENCE,rows)
    return dict(results=results,worker_pid=os.getpid(),wall_seconds=time.monotonic()-began,
        rss_bytes=current_rss(),reference_records_loaded=_REFERENCE.reference_records_loaded,
        backend_implementation=_REFERENCE.implementation)


def exact_batches(path,n,batches,*,workers,worker_rss_cap_bytes,ready_callback=None,backend_adoption_reference):
    Q.need(type(workers)is int and 1<=workers<=192 and type(worker_rss_cap_bytes)is int and worker_rss_cap_bytes>0,
        'Actual explicit worker count/cap required')
    adoption,packed=authority.adopted(backend_adoption_reference)
    Q.need(n==authority.N and str(Path(path).absolute())==packed['fingerprints']['path'],'No reference change/subset/augmentation')
    Q.verify(packed['fingerprints']);frame=file_frame(path)
    context=multiprocessing.get_context('spawn');barrier=context.Barrier(workers)
    with ProcessPoolExecutor(max_workers=workers,mp_context=context,initializer=_initialize,
            initargs=(str(path),frame,n,worker_rss_cap_bytes,barrier,backend_adoption_reference))as pool:
        warmups=[pool.submit(_ready)for i in range(workers)]
        for future in warmups:
            value=future.result()
            if ready_callback is not None:ready_callback(value)
        waiting=deque()
        for rows in batches:
            waiting.append(pool.submit(_batch,rows))
            if len(waiting)>=workers*2:yield waiting.popleft().result()
        while waiting:yield waiting.popleft().result()
    Q.need(file_frame(path)==frame,'Reference changed during compiled search')
