"""Close only the two bound stalled precision attempts, retaining all evidence."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
from precision_quality import identity,read,write,ROOT

if socket.gethostname().split('.')[0]!='compute-0-21':raise RuntimeError('Actual owning node required')
report=[]
for mode in ('tf32_islands','bf16_islands'):
    run='precision_20261115_'+mode+'_G1_3M'
    state=read(ROOT/'control'/(run+'_native.json'))
    expected={k:state[k] for k in ('pid','uid','start_ticks','pgid')}
    if expected['uid']!=os.getuid() or identity(expected['pid'])!=expected:
        raise RuntimeError('Native process identity changed; no signal sent')
    if (ROOT/'control'/(run+'_ack.json')).exists():raise RuntimeError('Cooperative checkpoint exists; resume it instead')
    request=ROOT/'control'/(run+'_request.json')
    if not request.exists() or time.time()-request.stat().st_mtime<30:raise RuntimeError('Allow cooperative save first')
    output=ROOT/'artifacts'/run
    last=(output/'losses.csv').read_text().splitlines()[-1]
    if last.split(',')[0]!='12032':raise RuntimeError('Training has advanced; inspect it before stopping')
    rows=subprocess.check_output(['ps','-eo','pid=,ppid=,pgid=,uid=,stat=,wchan='],text=True).splitlines()
    group=[];blocked=[]
    for row in rows:
        pid,parent,pgid,uid,status,wchan=row.split()[:6]
        if int(pgid)!=expected['pgid']:continue
        if int(uid)!=os.getuid():raise RuntimeError('Foreign process group member; no signals sent')
        bound=identity(int(pid));group.append(bound)
        if status.startswith('D') and wchan=='folio_wait_bit_common':blocked.append(bound)
    if not blocked:raise RuntimeError('Expected kernel input stall is absent; no signals sent')
    record=dict(run=run,reason='ORIGINAL_LUSTRE_LMDB_KERNEL_IO_STALL',last_training_row=last,
        cooperative_request=str(request),checkpoint_available=False,own_group=group,blocked_workers=blocked,
        samples_excluded_from_quality_budget=12032,observed_at=time.time())
    write(ROOT/'control'/(run+'_io_failure.json'),record)
    os.killpg(expected['pgid'],signal.SIGTERM)
    time.sleep(5)
    # Kill only still-identical members of the captured own group. D-state
    # processes can remain until the kernel I/O returns; never touch P workers.
    for bound in group:
        try:
            if identity(bound['pid'])==bound:os.kill(bound['pid'],signal.SIGKILL)
        except ProcessLookupError:pass
        except FileNotFoundError:pass
    report.append(record)
print(json.dumps(report),flush=True)
