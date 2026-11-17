"""Thin T process wrapper: real identity, native affinity and shared H/T guard.

The child t_train owns the sole persistent GPU lock and all evaluation.
"""
import argparse,json,os,pathlib,signal,socket,subprocess,time
from h_resources import REPO,CONTROL,guard
import sys
sys.path.insert(0,str(REPO/'tools/p_recipe'))
from native_run import identity
from execution_ledger import write,read

def training_command(python,configuration):
    return [python,'-B','-u',str(REPO/'tools/p_heads/t_train.py'),'--configuration',str(configuration)]

def owned_descendants(pid):
    found={};todo=[pid]
    while todo:
        parent=todo.pop();tasks=pathlib.Path('/proc')/str(parent)/'task'
        try:entries=list(tasks.iterdir())
        except FileNotFoundError:continue
        for task in entries:
            try:children=(task/'children').read_text().split()
            except FileNotFoundError:continue
            for value in children:
                child=int(value)
                if child in found:continue
                try:bound=identity(child)
                except (FileNotFoundError,ProcessLookupError):continue
                if bound['uid']==os.getuid():found[child]=bound;todo.append(child)
    return found

def wait_own_tree(bound,known):
    # After main exit, wait for recorded children and any remaining owned group
    # members. Never signal an unverified/reused PID or another task.
    for path in pathlib.Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:row=identity(int(path.name))
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
        if row['uid']==bound['uid'] and row['pgid']==bound['pgid'] and row['start_ticks']>=bound['start_ticks']:
            known[row['pid']]=row
    while known:
        for pid,old in list(known.items()):
            try:
                live=identity(pid)==old
                if live:live=(pathlib.Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()[0]!='Z'
            except (FileNotFoundError,ProcessLookupError):live=False
            if not live:known.pop(pid)
        if known:time.sleep(1)
def run(c):
    guard(force=True)
    node=socket.gethostname().split('.')[0]
    if node!=c['node'] or node=='compute-0-21':raise ValueError('Wrong or forbidden actual node')
    execution=c.get('execution','native_SSH')
    if execution=='native_SSH' and node not in ('compute-0-20','compute-0-22'):raise ValueError('Native hybrid only on permitted20/22')
    if execution=='Slurm' and not os.environ.get('SLURM_JOB_ID'):raise ValueError('Real Slurm allocation required')
    allowed=set(os.sched_getaffinity(0))
    mask=sorted(set(c.get('native_cpu_mask',sorted(allowed)[:15]))) if execution=='native_SSH' else sorted(allowed)
    if len(mask)!=15 or not set(mask)<=allowed:raise ValueError('Exactly15 actual allowed CPUs required')
    configuration=read(c['configuration'])
    environment=dict(os.environ,CUDA_VISIBLE_DEVICES=c['gpu_uuid'],P_RECIPE_RUN_ID=c['run'],
        PYTHONDONTWRITEBYTECODE='1',PYTORCH_ALLOC_CONF='expandable_segments:True',
        OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',
        PYTHONPATH=str(REPO/'current')+':/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps')
    if execution=='native_SSH':
        for key in list(environment):
            if key.startswith('SLURM_'):environment.pop(key)
    # No outer flock: t_train admits the GPU only after owning its UUID lock.
    child=subprocess.Popen(training_command(c['python'],c['configuration']),cwd=REPO,env=environment,
        start_new_session=True,preexec_fn=(lambda:os.sched_setaffinity(0,mask)) if execution=='native_SSH' else None)
    bound=identity(child.pid)
    record=dict(run=c['run'],execution=execution,node=node,gpu_uuid=c['gpu_uuid'],
        started_at=time.time(),status='RUNNING',cpu_mask=sorted(os.sched_getaffinity(child.pid)),native_affinity_only=execution=='native_SSH',**bound)
    if execution=='Slurm':record['job_id']=int(os.environ['SLURM_JOB_ID'])
    state=pathlib.Path(c['state_path']);write(state,record);paused=False
    print(json.dumps(record),flush=True);known={}
    while child.poll() is None:
        known.update(owned_descendants(child.pid))
        try:guard();ok=True
        except (OSError,ValueError,KeyError,TypeError) as error:ok=False;reason=str(error)
        if ok==paused and child.poll() is None:
            # The fresh child owns this process group; readers inherit it.
            if identity(child.pid)!=bound:raise RuntimeError('Own child identity changed; no signal sent')
            os.killpg(bound['pgid'],signal.SIGCONT if ok else signal.SIGSTOP);paused=not ok
            record.update(status='RUNNING' if ok else 'DISK_PAUSED')
            if not ok:record['disk_reason']=reason
            write(state,record)
        time.sleep(5)
    code=child.wait();wait_own_tree(bound,known);record.update(worker_tree_exited=True,status='COMPLETED' if code==0 else 'FAILED',exit_code=code,
        ended_at=time.time(),elapsed_seconds=time.time()-record['started_at'])
    write(state,record);return code

def main():
    p=argparse.ArgumentParser();p.add_argument('--configuration',required=True);a=p.parse_args()
    return run(read(a.configuration))
if __name__=='__main__':raise SystemExit(main())