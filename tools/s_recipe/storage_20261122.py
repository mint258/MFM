"""Future S admission through the project-owned unified reservation module.

No admission on import, no legacy peer forecasts, no changes to running jobs.
The line-wide remaining reservation is released after all S writing finishes.
"""
import json
import os
from pathlib import Path
import socket
import sys
import time

ROOT = Path('/share/home/zixiao/descriptor_analysis')
REPO = ROOT/'MFM_s_recipe'
CONTROL = ROOT/'runs/s_recipe_20261120'
sys.path.insert(0, str(REPO/'tools'))
import shared_guard

def write(path, value):
    pending = path.with_name(path.name+'.next.'+str(os.getpid()))
    pending.write_text(json.dumps(value, indent=2)+'\n')
    pending.replace(path)

def remaining():
    allocated = 0
    seen = set()
    for path in CONTROL.rglob('*'):
        try:
            value = path.lstat()
        except FileNotFoundError:
            continue
        if path.is_symlink() or not path.is_file():
            continue
        key = value.st_dev, value.st_ino
        if key not in seen:
            allocated += value.st_blocks*512
            seen.add(key)
    if allocated > 64*1024**3:
        raise shared_guard.AdmissionRefused('S output exceeds its existing total forecast')
    return max(0, 64*1024**3-allocated)

def claim_current():
    future = remaining()
    entries = [dict(id='remaining_S_outputs', kind='shared_fs', path='/share', bytes=future),
        dict(id='CPU11_controller_temporary', kind='node_disk', path='/', node='compute-0-11', bytes=16*1024**2),
        dict(id='GPU22_metadata_temporary', kind='node_disk', path='/', node='compute-0-22', bytes=64*1024**2)]
    shared_guard.claim('s-recipe', entries)
    return future

def admit():
    future = claim_current()
    node = socket.gethostname().split('.')[0]
    own_root = 64*1024**2 if node == 'compute-0-22' else 16*1024**2
    quota = json.loads((ROOT/'runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json').read_text())
    if (quota['uid'] != os.getuid() or quota['filesystem'] != '/share' or
            not 0 <= time.time()-quota['observed_time'] <= 5):
        raise shared_guard.AdmissionRefused('No fresh matching UID quota observation')
    shared_guard.check_with_timeout('s-recipe', 'node_disk', own_root, path='/', new_inodes=1000)
    return shared_guard.check_with_timeout('s-recipe', 'shared_fs', future, path='/share',
        new_inodes=20000, quota_available=quota['available_bytes'])

if __name__ == '__main__':
    print(json.dumps(dict(line='s-recipe', remaining_bytes=claim_current())), flush=True)
