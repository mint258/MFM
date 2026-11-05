"""Observe actual compute-node disks without restarting active model jobs."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import pwd
import socket
import subprocess
import time

# Keep the observer stdlib-only: package __init__ imports the full model.
_path=Path(__file__).resolve().parents[2]/'current/phychem_mfm/phase1/v2_disk.py'
_spec=importlib.util.spec_from_file_location('model_checkpoint_disk_capacity',_path)
_disk=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_disk)
filesystem_status=_disk.filesystem_status
require_capacity=_disk.require_capacity


def check_and_protect(output, jobs, *, node, growth_bytes=5_000_000_000, run=subprocess.run):
    if node != socket.gethostname().split('.')[0]:
        raise ValueError('Disk observation must run on the actual target node')
    try:
        root = filesystem_status('/')
        target = filesystem_status(output)
        require_capacity(root, 0, 0)
        require_capacity(target, growth_bytes, 64)
    except OSError as error:
        owner = pwd.getpwuid(os.getuid()).pw_name
        run(['scancel','--signal=STOP','--full','--user',owner,'--nodelist',node,
             *[str(job) for job in jobs]],check=True)
        return dict(status='DISK_PAUSED',reason=str(error),jobs=jobs,node=node)
    return dict(status='OBSERVING',node=node,jobs=jobs,root=root,target=target)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--state',required=True)
    parser.add_argument('--node',required=True)
    parser.add_argument('--jobs',nargs='+',type=int,required=True)
    args=parser.parse_args()
    while True:
        status=check_and_protect(args.output,args.jobs,node=args.node)
        status.update(pid=os.getpid(),observed_at=time.time())
        pending=Path(args.state+'.next')
        pending.write_text(json.dumps(status)+'\n')
        pending.replace(args.state)
        if status['status']=='DISK_PAUSED':
            print(json.dumps(status),flush=True)
            return
        time.sleep(5)


if __name__=='__main__':
    main()