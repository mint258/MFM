"""Private admission for new CPU continuations; keep running modules untouched."""
import json
import os
from pathlib import Path
import time
import types
from .consumer_lifecycle import authorized_cpu_nodes


def fresh_quota(snapshot, *, reader=None, clock=None, uid=None):
    """Retry only a stale atomic snapshot once, preserving the exact90s/UID checks."""
    read=(lambda:json.loads(Path(snapshot).read_text())) if reader is None else reader
    now=time.time if clock is None else clock
    owner=os.getuid() if uid is None else uid
    for attempt in range(2):
        q=read()
        if (q.get("uid")!=owner or q.get("generation")!="benchmarkB020261119"
                or q.get("returncode")!=0):
            raise RuntimeError("Missing/stale/mismatched quota observation")
        epoch=q.get("observed_epoch")
        if not isinstance(epoch,(int,float)) or isinstance(epoch,bool):
            raise RuntimeError("Missing/stale/mismatched quota observation")
        age=now()-epoch
        if 0<=age<=90:
            return q
        if not age>90:
            raise RuntimeError("Missing/stale/mismatched quota observation")
    raise RuntimeError("Missing/stale/mismatched quota observation")


def frozen_cpu_protect(original_source, authorized_node):
    """Adapt only a private node gate and snapshot read; retain original reserve math."""
    authorized_cpu_nodes((authorized_node,))
    old_gate="if node not in {'compute-0-'+str(i) for i in range(8,20)}:"
    old_read="q=json.loads(Path(snapshot).read_text())"
    if original_source.count(old_gate)!=1 or original_source.count(old_read)!=1:
        raise ValueError("Exact frozen original admission source required")
    adapted=original_source.replace(old_gate,"if node != "+repr(authorized_node)+":",1)
    adapted=adapted.replace(old_read,"q=_fresh_quota(snapshot)",1)
    private=types.ModuleType("_benchmark_private_frozen_cpu_admission")
    private.__package__="workflows.benchmark_data"
    private.__dict__["_fresh_quota"]=fresh_quota
    exec(compile(adapted,"<private-frozen-cpu-admission>","exec"),private.__dict__)
    return private.protect
