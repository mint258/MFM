"""Publish a new writer forecast only after its prospective admission passes."""
import copy
import json
import os
import socket
import time


def register_after_admission(current, extra, observe, persist):
    prospective=copy.deepcopy(current)
    existing={row['id'] for row in prospective['entries']}
    if any(row['id'] in existing for row in extra):
        raise ValueError('Inspect an existing resource handle before replacing it')
    prospective['entries'].extend(copy.deepcopy(extra))
    report=observe(extra)
    persist(prospective)
    return report


def prospective_on_actual_node(extra):
    """Read/check only: rejected proposals never appear in the live registry."""
    import storage_20261122 as storage
    from storage_line_20261122 import requirements
    guard=storage.shared_guard
    node=socket.gethostname().split('.')[0]
    if os.getuid()!=1278 or any(row.get('node')!=node for row in extra):
        raise ValueError('Prospective writer must match the actual owning node')
    own=json.loads((guard.REGISTRY/'s-recipe.json').read_text())
    entries=own['entries']+extra
    root,ram=requirements(entries,node,guard._same_device('node_disk','/'))
    future=sum(row['bytes'] for row in entries if row['kind']=='shared_fs' and row.get('path')=='/share')
    quota=json.loads((storage.ROOT/'runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json').read_text())
    if (quota['uid']!=os.getuid() or quota['filesystem']!='/share'
            or not 0<=time.time()-quota['observed_time']<=5):
        raise guard.AdmissionRefused('No fresh actual UID quota observation')
    return dict(root=guard.check_with_timeout('s-recipe','node_disk',root,path='/',new_inodes=1000),
        shared=guard.check_with_timeout('s-recipe','shared_fs',future,path='/share',new_inodes=20000,
            quota_available=quota['available_bytes']),
        ram=guard.check_with_timeout('s-recipe','node_ram',ram))
