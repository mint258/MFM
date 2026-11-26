"""Actual-node GPFS quota/root admission and own-process disk protection."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

HOME=Path('/share/home/202264640132')
ROOT=HOME/'precision_20261115'
PEAK=20_000_000_000


def facts():
    if os.getuid()!=67109:raise RuntimeError('Unexpected school account UID')
    if os.uname().nodename.startswith('login'):raise RuntimeError('Compute node required')
    root=os.statvfs('/')
    if root.f_bavail*root.f_frsize<max(10*1024**3,root.f_blocks*root.f_frsize//10):
        raise OSError('Root filesystem system reserve')
    allocated=sum(p.stat().st_blocks*512 for p in ROOT.rglob('*') if p.is_file()) if ROOT.exists() else 0
    remaining=max(100_000_000,PEAK-allocated)
    raw=subprocess.check_output(['/usr/lpp/mmfs/bin/mmlsquota','-Y','-u','67109','--block-size','1K','dssgdev'],text=True,timeout=10)
    header=None;record=None
    for line in raw.splitlines():
        fields=line.split(':')
        if len(fields)>4 and fields[0]=='mmlsquota' and fields[2]=='HEADER':header=fields
        elif header and fields[0]=='mmlsquota':
            value=dict(zip(header,fields))
            if value.get('id')=='67109' and value.get('filesystemName')=='dssgdev':record=value
    if record is None:raise OSError('Actual user quota unavailable')
    limits=[int(record[k])*1024 for k in ('blockQuota','blockLimit') if int(record[k])>0]
    if not limits:raise OSError('Finite quota limit unavailable')
    available=min(limits)-(int(record['blockUsage'])+int(record['blockInDoubt']))*1024
    disk=os.statvfs(HOME)
    required=100_000_000_000+100_000_000_000+16_000_000_000+remaining
    if min(available,disk.f_bavail*disk.f_frsize)<required or disk.f_favail<100000:
        raise OSError('Insufficient shared quota/bytes/inodes')
    return dict(node=os.uname().nodename,uid=os.getuid(),available_quota_bytes=available,
        shared_free_bytes=disk.f_bavail*disk.f_frsize,free_inodes=disk.f_favail,
        own_allocated_bytes=allocated,own_remaining_bytes=remaining,required_bytes=required)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args()
    print(json.dumps(facts()),file=sys.stderr,flush=True)
    command=a.command[1:] if a.command[:1]==['--'] else a.command
    if command:
        process=subprocess.Popen(command,start_new_session=True);paused=False
        while process.poll() is None:
            try:facts();ok=True
            except (OSError,RuntimeError,ValueError,KeyError,TypeError) as error:
                print('DISK_PROTECTION: '+str(error),file=sys.stderr,flush=True);ok=False
            if ok==paused and process.poll() is None:
                os.killpg(process.pid,signal.SIGCONT if ok else signal.SIGSTOP);paused=not ok
            time.sleep(5)
        raise SystemExit(process.wait())
