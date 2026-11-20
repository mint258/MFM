"""Fresh actual shared-filesystem and UID-quota admission for B0 producers."""
import json
import os
from pathlib import Path
import socket
import time
from .acquire import guard,quota_headroom
from .shared_storage import current_pool


def protect(root,needed,snapshot,own_concurrent_bytes=1073741824):
    node=socket.gethostname().split('.')[0]
    if node not in {'compute-0-'+str(i) for i in range(8,20)}:
        raise RuntimeError('B0 producer writes require an authorized CPU compute node')
    q=json.loads(Path(snapshot).read_text())
    if q['uid']!=os.getuid() or q['generation']!='benchmarkB020261119' or q['returncode']!=0 or not 0<=time.time()-q['observed_epoch']<=90:
        raise RuntimeError('Missing/stale/mismatched quota observation')
    guard(Path(root),needed,quota_headroom(q['raw'],os.getuid()),time.monotonic(),
          current_pool(root,114569896448+own_concurrent_bytes))
