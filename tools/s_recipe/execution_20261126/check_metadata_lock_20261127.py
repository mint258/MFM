"""Once: actual NFS CPU lock versus the login host's local lock domains."""
import fcntl
import json
from pathlib import Path
import shlex
import subprocess
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C, REPO as R, write

path=C/'metadata_lock_domain_probe_20261127.lock'
results={}
with path.open('a') as stream:
    fcntl.flock(stream, fcntl.LOCK_EX|fcntl.LOCK_NB)
    for method in ('flock','lockf'):
        code=('import fcntl,json,os,socket;from pathlib import Path;'
            'p=Path('+repr(str(path))+');s=p.open("a");blocked=False\n'
            'try:fcntl.'+method+'(s,fcntl.LOCK_EX|fcntl.LOCK_NB)\n'
            'except BlockingIOError:blocked=True\n'
            'print(json.dumps(dict(method='+repr(method)+',blocked=blocked,uid=os.getuid(),host=socket.gethostname())))')
        raw=subprocess.check_output(['/usr/bin/timeout','15s','ssh','-n','-o','BatchMode=yes',
            '-o','ConnectTimeout=3','sonmi',shlex.join([
            '/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python','-B','-c',code])],text=True)
        result=json.loads(raw)
        if result['uid']!=1278: raise ValueError('Metadata lock probe owner differs')
        results[method]=result
if results['flock']['blocked'] or not results['lockf']['blocked']:
    raise ValueError('Actual lock-domain observation differs; inspect before choosing a repair')
value=dict(status='COMPLETE', **execution_fields(), actual_cross_host_lock_observations=results,
    scope='Own empty probe file only; NFS-side flock and login-side POSIX lockf interoperate, local flock alone does not',
    scientific_files_read=False, real_job_controls=False)
write(C/'metadata_lock_check_20261127.json',value)
write(R/'results/s_recipe/metadata_lock_check_20261127.json',value)
print(json.dumps(value),flush=True)
