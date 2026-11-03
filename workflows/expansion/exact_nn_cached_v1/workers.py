"""Bounded spawn workers; every reference decoded once per worker lifetime."""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import os
import time
from .engine import load_reference,current_rss,file_frame

_REFERENCE=None
_BARRIER=None


def _initialize(path,frame,n,cap,barrier):
    global _REFERENCE,_BARRIER
    try:
        _BARRIER=barrier
        _REFERENCE=load_reference(path,frame,n,cap)
        barrier.wait()
    except BaseException:
        barrier.abort()
        raise


def _ready():
    _BARRIER.wait()
    return {'worker_pid':os.getpid(),'reference_decode_calls':_REFERENCE.decode_calls,
        'reference_load_seconds':_REFERENCE.load_wall_seconds,
        'reference_load_rss_bytes':_REFERENCE.load_rss_bytes}


def _batch(rows):
    start=time.monotonic()
    results=[(identity,raw,_REFERENCE.nearest(raw)) for identity,raw in rows]
    return {'results':results,'worker_pid':os.getpid(),'wall_seconds':time.monotonic()-start,
        'rss_bytes':current_rss(),'reference_decode_calls':_REFERENCE.decode_calls}


def exact_batches(path,n,batches,*,workers,worker_rss_cap_bytes,ready_callback=None):
    """Yield bounded batches; no time limit, reference sampling or result retry.

    Caller validates the complete reference hash first. A frame/same-FD check
    binds each worker to that exact packed reference throughout decoding.
    """
    if type(workers)is not int or not 1<=workers<=192:raise ValueError('DECLARED_WORKER_COUNT_REQUIRED')
    frame=file_frame(path)
    context=multiprocessing.get_context('spawn');barrier=context.Barrier(workers)
    with ProcessPoolExecutor(max_workers=workers,mp_context=context,initializer=_initialize,
            initargs=(str(path),frame,n,worker_rss_cap_bytes,barrier)) as pool:
        # Submitting workers tasks eagerly starts every spawn initializer, even
        # when source-level fingerprint dedup leaves fewer queries than workers.
        warmups=[pool.submit(_ready) for _ in range(workers)]
        for future in warmups:
            ready=future.result()
            if ready_callback is not None:ready_callback(ready)
        waiting=deque()
        for rows in batches:
            waiting.append(pool.submit(_batch,rows))
            if len(waiting)>=workers*2:yield waiting.popleft().result()
        while waiting:yield waiting.popleft().result()
    if file_frame(path)!=frame:raise ValueError('REFERENCE_CHANGED_DURING_EXACT_SEARCH')
