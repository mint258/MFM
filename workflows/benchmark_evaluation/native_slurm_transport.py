"""Use the actual local Slurm controller for mutations; retry only refused read-only accounting."""
import shlex
import os
from pathlib import Path
import subprocess
import time


DIRECT_ACCOUNTING_CONFIG="/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/native_accounting_slurm_direct_20261122.conf"
DIRECT_ACCOUNTING_FIELDS=dict(ClusterName="sonmi",SlurmctldHost="sonmi",
    AccountingStorageType="accounting_storage/slurmdbd",AccountingStorageHost="10.1.1.1",
    AccountingStoragePort="6819",AuthType="auth/munge")
def direct_accounting_environment(path, *, reader=None):
    """Use only the successfully probed existing cluster's user-owned client override."""
    if path!=DIRECT_ACCOUNTING_CONFIG:raise ValueError("Only the recorded native accounting client configuration")
    if reader is None:
        p=Path(path)
        stat=p.lstat()
        uid,mode,raw,symlink=stat.st_uid,stat.st_mode,p.read_text(),p.is_symlink()
    else:uid,mode,raw,symlink=reader(path)
    if uid!=os.getuid() or mode&0o022 or symlink:raise ValueError("Owned nonwritable nonsymlink accounting configuration required")
    fields={}
    for line in raw.splitlines():
        if not line.strip():continue
        key,separator,value=line.partition("=")
        if not separator or key in fields:raise ValueError("Exact native accounting configuration fields required")
        fields[key]=value
    if fields!=DIRECT_ACCOUNTING_FIELDS:raise ValueError("Do not change the actual sonmi cluster, controller, DBD address/port or Munge authentication")
    return dict(os.environ,SLURM_CONF=path)

def native_control(args, *, runner=None, sleeper=None, accounting_config=None):
    if not isinstance(args,(list,tuple)) or not args or any(not isinstance(value,str) for value in args):
        raise ValueError("Explicit native Slurm argument list required")
    args=list(args);operation=args[0];run_options={}
    selected=accounting_config or os.environ.get("BENCHMARK_NATIVE_SLURM_ACCOUNTING_CONFIG")
    if operation=="sacct":
        if selected:
            command=args;run_options["env"]=direct_accounting_environment(selected)
        else:command=["ssh","-n","-o","BatchMode=yes","-o","ConnectTimeout=10","sonmi",shlex.join(args)]
        attempts=3
    elif operation=="sbatch":
        if "--parsable" not in args or "--hold" not in args:
            raise ValueError("Only held, native-ID-returning submissions are permitted")
        command=args;attempts=1
    elif operation=="scontrol":
        if len(args)!=3 or args[1]!="release" or not args[2].isdigit():
            raise ValueError("Only one recorded native held job may be released")
        command=args;attempts=1
    else:
        raise ValueError("Unregistered native Slurm transport operation")
    runner=subprocess.run if runner is None else runner
    sleeper=time.sleep if sleeper is None else sleeper
    for attempt in range(attempts):
        result=runner(command,text=True,capture_output=True,timeout=60,**run_options)
        if result.returncode==0:return result.stdout.strip()
        error=subprocess.CalledProcessError(result.returncode,command,output=result.stdout,stderr=result.stderr)
        if (operation=="sacct" and (result.returncode==255 or bool(selected))
            and "Connection refused" in (result.stderr or "") and attempt+1<attempts):
            sleeper(attempt+1)
        else:raise error
