"""Bind the existing recipe takeover protocol to T source, ledger and runner.

No training, evaluation or checkpoint/handoff protocol is implemented here.
"""
import argparse,json,os,pathlib,socket,subprocess,sys,time
from h_resources import REPO,CONTROL,guard
sys.path.insert(0,str(REPO/'tools/p_recipe'))
import execution_ledger as ledger
import scheduled_run as protocol
from t_native import run as native_run
HYBRID=CONTROL/'hybrid'

def requested_cpus(configuration,policy):return 15

def guarded_run(launch):
    # Existing main supplies the actual resumed configuration and Slurm identity.
    return native_run(dict(launch,python=launch['command'][0],configuration=launch['command'][-1]))

def bind_protocol():
    ledger.C=HYBRID
    protocol.C=HYBRID;protocol.REPO=REPO
    protocol.requested_cpus=requested_cpus;protocol.guarded_run=guarded_run
    return protocol

def prepare(configuration,node,gpu,python,native_cpu_mask=None):
    guard(force=True);bind_protocol();HYBRID.mkdir(parents=True,exist_ok=True)
    path=pathlib.Path(configuration).resolve();c=ledger.read(path);name=c['run']
    task_path=HYBRID/(name+'_task.json');launch_path=HYBRID/(name+'_launch.json')
    if task_path.exists() or launch_path.exists():raise FileExistsError('Inspect existing same-task handles')
    for key in ('handoff_request','handoff_ack'):
        if not c.get(key) or pathlib.Path(c[key]).exists():raise ValueError('Fresh existing handoff paths required')
    native_state=str(HYBRID/(name+'_native.json'));reservation=name+'_standby';now=time.time()
    task=dict(mode='native_with_standby',node=node,gpu_uuid=gpu,python=python,configuration=str(path),
        submitted_at=now,cpus=15,exclusive=False,minimum_free_gpu_mib=0,reservation_key=reservation,
        native_state=native_state,handoff_state=str(HYBRID/(name+'_handoff_state.json')))
    launch=dict(run=name,execution='native_SSH',node=node,gpu_uuid=gpu,python=python,
        output=c['output'],configuration=str(path),state_path=native_state)
    if native_cpu_mask is not None:launch['native_cpu_mask']=native_cpu_mask
    with ledger.locked_ledger() as book:
        if name in book['runs'] or reservation in book.get('reservations',{}):raise ValueError('Existing task; do not duplicate')
        book['runs'][name]=dict(backend='native_SSH',state='PREPARED',node=node,gpu_uuid=gpu,
            configuration=str(path),submitted_at=now,stage=c['stage'],round=c['round'],native_state=native_state,
            scheduling_task=str(task_path),cpus=15,exclusive=False)
        # No job ID exists before sbatch. main can safely address this reservation.
        book.setdefault('reservations',{})[reservation]=dict(backend='Slurm',state='PREPARED',
            phase='WAITING_FOR_SUBMISSION',native_run=name,node=node,gpu_uuid=gpu)
        ledger.write(task_path,task);ledger.write(launch_path,launch)
    print(json.dumps(dict(task=str(task_path),native_launch=str(launch_path))),flush=True)
    return task_path,launch_path

def register(task_path,job):
    guard(force=True);bind_protocol();task=ledger.read(task_path)
    text=subprocess.check_output(['scontrol','show','job',str(job),'-o'],text=True)
    if 'JobId='+str(job) not in text or 'NodeList='+task['node'] not in text and 'ReqNodeList='+task['node'] not in text:
        raise ValueError('Real Slurm handle/node mismatch')
    with ledger.locked_ledger() as book:
        r=book['reservations'][task['reservation_key']]
        if r.get('job_id') not in (None,job):raise ValueError('Different standby handle already exists')
        r['job_id']=job;r['registered_at']=time.time()
        if r['phase']=='WAITING_FOR_SUBMISSION':r.update(state='SUBMITTED',phase='WAITING_FOR_ALLOCATION')
        c=ledger.read(task['configuration']);book['runs'][r['native_run']]['standby_job_id']=job

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    q=sub.add_parser('prepare');q.add_argument('--configuration',required=True);q.add_argument('--node',required=True)
    q.add_argument('--gpu',required=True);q.add_argument('--python',required=True);q.add_argument('--native-cpus')
    q=sub.add_parser('register');q.add_argument('--task',required=True);q.add_argument('--job',type=int,required=True)
    q=sub.add_parser('takeover');q.add_argument('--task',required=True)
    a=p.parse_args()
    if a.action=='prepare':
        mask=None if a.native_cpus is None else [int(v) for v in a.native_cpus.split(',')]
        prepare(a.configuration,a.node,a.gpu,a.python,mask);return 0
    if a.action=='register':register(a.task,a.job);return 0
    guard(force=True);bind_protocol()
    return protocol.main(a.task)
if __name__=='__main__':raise SystemExit(main())