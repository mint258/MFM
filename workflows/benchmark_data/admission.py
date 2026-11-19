"""Fresh actual shared-filesystem and UID-quota admission for B0 producers."""
import json
import os
from pathlib import Path
import time
from .acquire import guard,quota_headroom


def protect(root,needed,snapshot,own_concurrent_bytes=1073741824):
    q=json.loads(Path(snapshot).read_text())
    if q['uid']!=os.getuid() or q['generation']!='benchmarkB020261119' or q['returncode']!=0 or not 0<=time.time()-q['observed_epoch']<=90:
        raise RuntimeError('Missing/stale/mismatched quota observation')
    guard(Path(root),needed,quota_headroom(q['raw'],os.getuid()),time.monotonic(),
          114569896448+own_concurrent_bytes)
