"""One admission for all declared S futures on the selected actual node.

The project guard already sums other lines. This adapter also sums our own
concurrent phases; it never changes another line's forecast or a running job.
"""
import json
import os
import socket
import time
import storage_20261122 as storage


def requirements(entries,node,root_paths):
    root=sum(row['bytes'] for row in entries if row['kind']=='node_disk'
             and row.get('node')==node and row.get('path') in root_paths)
    ram=sum(row['bytes'] for row in entries if row['kind']=='node_ram' and row.get('node')==node)
    return root,ram


def admit(configuration):
    future=storage.claim_current()
    node=socket.gethostname().split('.')[0]
    own=json.loads((storage.shared_guard.REGISTRY/'s-recipe.json').read_text())
    paths=storage.shared_guard._same_device('node_disk','/')
    root,ram=requirements(own['entries'],node,paths)
    if root<16*1024**2 or ram<configuration['peak_ram_bytes']:
        raise storage.shared_guard.AdmissionRefused('The incoming S phase has no sufficient declared local/RAM future')
    quota=json.loads((storage.ROOT/'runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json').read_text())
    if (quota['uid']!=os.getuid() or quota['filesystem']!='/share' or
            not 0<=time.time()-quota['observed_time']<=5):
        raise storage.shared_guard.AdmissionRefused('No fresh matching UID quota observation')
    guard=storage.shared_guard
    return dict(root=guard.check_with_timeout('s-recipe','node_disk',root,path='/',new_inodes=1000),
        shared=guard.check_with_timeout('s-recipe','shared_fs',future,path='/share',new_inodes=20000,
            quota_available=quota['available_bytes']),
        ram=guard.check_with_timeout('s-recipe','node_ram',ram))
