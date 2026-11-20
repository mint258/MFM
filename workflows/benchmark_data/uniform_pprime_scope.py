"""Use the unchanged P-prime producer on the newly sealed uniform-UFF scope."""
import argparse
import json
import os
from pathlib import Path
import stat
from . import pprime_tmpfs_queue as producer
from .admission import protect
from .uniform_sprime_scope import source_closed,PEER_ENVIRONMENT_RESERVE
from .shared_access import check_access

ORIGINAL_WORKER=producer.worker
BASE_MARKER=('directive19','uniform_Sprime')
CLOSED_SOURCES=set()

def scope_base(scope):
    scope=Path(scope).absolute()
    if tuple(scope.parts[-2:])!=BASE_MARKER:
        raise ValueError('Only the directive19 uniform-Sprime scope is supported')
    return scope.parents[1]

def used_bytes(folder):
    total=0
    for path in Path(folder).glob('*.sqlite'):
        s=path.lstat()
        if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid():
            raise ValueError('Unexpected P-prime output owner/type')
        total+=s.st_size
    return total

def remaining_budget(old_used,new_used,needed,forecast=producer.FORECAST):
    return (max(67108864,forecast-old_used)
            +max(needed,forecast-new_used,67108864)
            +PEER_ENVIRONMENT_RESERVE)

def capacity(scope,snapshot,needed=67108864,workers=0,scratch=None):
    base=scope_base(scope)
    for geometry_root in (base,Path(scope)):
        if str(geometry_root) in CLOSED_SOURCES:continue
        access=check_access(geometry_root/'geometry/shared_v1/queue.sqlite')
        if not access:raise ValueError('Shared source geometry has no access declaration')
        metadata=json.loads(Path(access['source_producer_manifest']).read_text())
        if not source_closed(access,metadata,os.getuid()):
            raise ValueError('Every original/new geometry producer must be natively sealed')
        CLOSED_SOURCES.add(str(geometry_root))
    old_used=used_bytes(base/'labels/Pprime/shared_v1')
    new_used=used_bytes(Path(scope)/'labels/Pprime/shared_v1')
    protect(base,remaining_budget(old_used,new_used,needed),snapshot,
            own_concurrent_bytes=1073741824)
    if scratch is not None:producer.tmpfs_capacity(scratch,workers)

def worker(*args):
    # Spawn imports this module afresh: install the same joint guard inside each
    # worker before calling the original native/parser/queue worker function.
    producer.capacity=capacity
    return ORIGINAL_WORKER(*args)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('command',choices=['prepare','run'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--quota-snapshot',type=Path,required=True)
    p.add_argument('--workers',type=int,default=8)
    p.add_argument('--wall-seconds',type=int,default=86400)
    p.add_argument('--source-producer-job',type=int)
    a=p.parse_args();base=scope_base(a.root)
    producer.capacity=capacity
    producer.worker=worker
    if a.command=='prepare':
        # Original prepare seals the new source using its actual native C0.
        # Capacity is called before that seal, so perform that same source seal
        # first; no scientific records are read back or recomputed.
        if a.source_producer_job is None:p.error('--source-producer-job required')
        protect(base,remaining_budget(used_bytes(base/'labels/Pprime/shared_v1'),
                    used_bytes(a.root/'labels/Pprime/shared_v1'),1048576),
                a.quota_snapshot,own_concurrent_bytes=1073741824)
        from .shared_access import seal_geometry
        seal_geometry(a.root,a.source_producer_job)
        a.source_producer_job=None
        producer.prepare(a)
    else:producer.run(a)

if __name__=='__main__':main()
