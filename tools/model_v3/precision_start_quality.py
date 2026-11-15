"""Launch one independent precision arm without sharing the P study ledger."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess

REPO=Path(__file__).resolve().parents[2]

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--task',required=True);a=p.parse_args()
    path=Path(a.task).resolve();task=json.loads(path.read_text())
    if task['node']=='compute-0-21':raise RuntimeError('User excludes compute-0-21; do not launch here')
    if Path(task['native_state']).exists():raise RuntimeError('Existing native handle; inspect it before any retry')
    old='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
    log=str(REPO/'results/precision_20261115'/('quality_'+path.stem+'.log'))
    command=[old,'-B','-u','tools/model_v3/precision_quality.py','native','--task',str(path)]
    code='import subprocess; f=open('+repr(log)+',"ab",buffering=0); p=subprocess.Popen('+repr(command)+',cwd='+repr(str(REPO))+',stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True); print(p.pid)'
    pid=int(subprocess.check_output(['ssh','-n',task['node'],shlex.join([old,'-B','-c',code])],text=True).strip())
    job=subprocess.check_output(['sbatch','--parsable','--nodelist='+task['node'],
        '--job-name='+path.stem+'-takeover',str(REPO/'tools/model_v3/precision_quality.sbatch'),str(path)],text=True).strip()
    print(json.dumps(dict(wrapper_pid=pid,standby_job_id=job,task=str(path))),flush=True)
