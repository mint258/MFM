"""Explicit Main private-reference spawn workers, no Alpha authority/UID alias."""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
import os
from pathlib import Path
import time
from ..exact_nn_cached_v1.engine import file_frame,current_rss
from ..exact_nn_inverted_cpp_v1 import backend
from .common import need,N

_REFERENCE=None
_BARRIER=None
_STOP=None


def initialize(path,stamp,cap,build,barrier,stop):
    global _REFERENCE,_BARRIER,_STOP
    _BARRIER=barrier;_STOP=stop
    try:
        need(os.getuid()==1278 and not stop.is_set(),'Actual Main worker before full private load')
        _REFERENCE=backend.load_reference(path,stamp,N,cap,build_manifest_reference=build)
        need(_REFERENCE.reference_records_loaded==N and not stop.is_set(),'Full original reference, no subset')
        barrier.wait()
    except BaseException:barrier.abort();raise


def ready():
    _BARRIER.wait()
    return dict(pid=os.getpid(),uid=os.getuid(),reference_records_loaded=_REFERENCE.reference_records_loaded,
        load_wall_seconds=_REFERENCE.load_wall_seconds,load_rss_bytes=_REFERENCE.load_rss_bytes,
        native_statistics=_REFERENCE.native_statistics,implementation=_REFERENCE.implementation)


def batch(rows):
    started=time.monotonic();values=[]
    for text in rows:
        need(not _STOP.is_set(),'Resource stop; retain only already closed parts, no automatic retry')
        value=_REFERENCE.nearest(bytes.fromhex(text));value.pop('searched_popcount_groups')
        values.append((text,value))
    return dict(results=values,pid=os.getpid(),wall_seconds=time.monotonic()-started,rss_bytes=current_rss())


def exact_batches(path,build,batches,plan,stop,ready_callback):
    context=mp.get_context('spawn');barrier=context.Barrier(plan['workers']);stamp=file_frame(path)
    with ProcessPoolExecutor(max_workers=plan['workers'],mp_context=context,initializer=initialize,
        initargs=(str(path),stamp,plan['worker_rss_cap_bytes'],build,barrier,stop))as pool:
        for future in [pool.submit(ready)for _ in range(plan['workers'])]:ready_callback(future.result())
        pending=deque()
        for values in batches:
            need(not stop.is_set(),'Parent resource stop before dispatch')
            pending.append(pool.submit(batch,values))
            if len(pending)>=2*plan['workers']:yield pending.popleft().result()
        while pending:yield pending.popleft().result()
    need(file_frame(path)==stamp,'Full reference changed during rescue')