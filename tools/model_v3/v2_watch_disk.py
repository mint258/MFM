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
SHARED_RESERVE=_disk.SHARED_RESERVE


def quota_headroom(reference, filesystem, growth_bytes, concurrent_bytes):
    """Use the existing producer's effective timestamp and real UID quota."""
    schemas={'/lfshome':'LUSTRE_USER_QUOTA_AVAILABLE_V1',
             '/share':'XFS_USER_QUOTA_AVAILABLE_V1'}
    try:
        value=json.loads(Path(reference).read_text())
        if (not isinstance(value,dict) or filesystem not in schemas
                or value.get('schema')!=schemas[filesystem]
                or value.get('uid')!=os.getuid()
                or value.get('filesystem')!=filesystem):
            raise ValueError('Quota snapshot identity differs')
        age=time.time()-value['observed_time']
        if not 0<=age<=5:
            raise ValueError('Quota snapshot is future or stale')
        available=value['available_bytes']
        if type(available) is not int or available<0 or min(growth_bytes,concurrent_bytes)<0:
            raise ValueError('Quota byte capacity is unknown')
        required=SHARED_RESERVE+growth_bytes+concurrent_bytes+8*1024**3
        if available<required:
            raise ValueError(f'Insufficient account quota: available={available}, required={required}')
        return dict(filesystem=filesystem,available=available,required=required,age=age)
    except (OSError,ValueError,KeyError,TypeError) as error:
        raise OSError(f'Account quota unavailable: {error}') from error


def check_and_protect(output, jobs, *, node, growth_bytes=5_000_000_000, run=subprocess.run,
                      quota_reference=None, quota_filesystem=None, quota_concurrent_bytes=0):
    if node != socket.gethostname().split('.')[0]:
        raise ValueError('Disk observation must run on the actual target node')
    try:
        root = filesystem_status('/')
        target = filesystem_status(output)
        require_capacity(root, 0, 0)
        require_capacity(target, growth_bytes, 64)
        quota=None
        if quota_reference is not None:
            if quota_filesystem is None or not Path(output).resolve().is_relative_to(Path(quota_filesystem).resolve()):
                raise OSError('Output is outside the bound quota filesystem')
            quota=quota_headroom(quota_reference,quota_filesystem,growth_bytes,quota_concurrent_bytes)
    except OSError as error:
        owner = pwd.getpwuid(os.getuid()).pw_name
        run(['scancel','--signal=STOP','--full','--user',owner,'--nodelist',node,
             *[str(job) for job in jobs]],check=True)
        return dict(status='DISK_PAUSED',reason=str(error),jobs=jobs,node=node)
    return dict(status='OBSERVING',node=node,jobs=jobs,root=root,target=target,
                **({} if quota is None else {'quota':quota}))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--state',required=True)
    parser.add_argument('--node',required=True)
    parser.add_argument('--jobs',nargs='+',type=int,required=True)
    parser.add_argument('--growth-bytes',type=int,default=5_000_000_000)
    parser.add_argument('--quota-reference')
    parser.add_argument('--quota-filesystem',choices=('/share','/lfshome'))
    parser.add_argument('--quota-concurrent-bytes',type=int,default=0)
    args=parser.parse_args()
    if bool(args.quota_reference)!=bool(args.quota_filesystem):
        parser.error('Bind quota-reference and quota-filesystem together')
    while True:
        status=check_and_protect(args.output,args.jobs,node=args.node,growth_bytes=args.growth_bytes,
            quota_reference=args.quota_reference,quota_filesystem=args.quota_filesystem,
            quota_concurrent_bytes=args.quota_concurrent_bytes)
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
