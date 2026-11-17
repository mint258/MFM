"""Bind the existing recipe takeover protocol to T source, ledger and runner.

No training, evaluation or checkpoint/handoff protocol is implemented here.
"""
import argparse,json,os,pathlib,re,socket,subprocess,sys,time
from h_resources import REPO,CONTROL,guard
sys.path.insert(0,str(REPO/'tools/p_recipe'))
import execution_ledger as ledger
import scheduled_run as protocol
from t_native import run as native_run,identity
from collect_execution import TERMINAL
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
    control=CONTROL.resolve();parents=set()
    for key in ('handoff_request','handoff_ack'):
        if not c.get(key):raise ValueError('Fresh handoff paths required')
        target=pathlib.Path(c[key]).resolve()
        try:target.relative_to(control)
        except ValueError:raise ValueError('Handoff paths must remain inside this task CONTROL')
        if target.exists():raise ValueError('Fresh handoff paths required')
        parents.add(target.parent)
    # Validate both owned paths before creating either parent; this is future
    # prepare only and does not mutate requests for already-running sources.
    guard(force=True)
    for parent in parents:parent.mkdir(parents=True,exist_ok=True)
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

def terminal_observation(job):
    result=subprocess.run(['scontrol','show','job',str(job),'-o'],text=True,capture_output=True,timeout=15)
    if result.returncode:
        error=(result.stderr or '')+' '+(result.stdout or '')
        if re.search(r'\binvalid\s+job\s+id\b',error,re.I):
            return dict(job_id=job,status='CONTROLLER_CONFIRMED_MISSING',controller_error=error.strip(),observed_at=time.time())
        raise RuntimeError('Old handle state is uncertain; no replacement: '+error.strip())
    fields=dict(re.findall(r'(\w+)=([^\s]+)',result.stdout))
    if fields.get('JobId')!=str(job) or fields.get('JobState') not in TERMINAL:
        raise ValueError('Old handle is not an exact confirmed terminal job')
    return dict(job_id=job,status='CONFIRMED_TERMINAL',state=fields['JobState'],observed_at=time.time())

def check_unrequested_live_source(task):
    configuration=ledger.read(task['configuration'])
    for key in ('handoff_request','handoff_ack'):
        if not configuration.get(key) or pathlib.Path(configuration[key]).exists():
            raise ValueError('Source has an existing or unknown handoff request/ack')
    if pathlib.Path(task['handoff_state']).exists():raise ValueError('Handoff already began')
    source=ledger.read(task['native_state'])
    if source.get('status')!='RUNNING' or 'exit_code' in source:raise ValueError('Source is not running')
    bound={key:source[key] for key in ('pid','uid','start_ticks','pgid')}
    if bound['uid']!=os.getuid() or identity(bound['pid'])!=bound:raise ValueError('Actual source identity changed')
    state=(pathlib.Path('/proc')/str(bound['pid'])/'stat').read_text().rsplit(')',1)[1].split()[0]
    if state in ('Z','X','T','t'):raise ValueError('Actual source is not a live running worker')
    return bound

def register(task_path,job,replace_terminal_job=None):
    guard(force=True);bind_protocol();task=ledger.read(task_path)
    text=subprocess.check_output(['scontrol','show','job',str(job),'-o'],text=True,timeout=15)
    fields=dict(re.findall(r'(\w+)=([^\s]+)',text))
    if fields.get('JobId')!=str(job) or task['node'] not in (fields.get('NodeList'),fields.get('ReqNodeList')):
        raise ValueError('Real Slurm handle/node mismatch')
    with ledger.locked_ledger() as book:
        r=book['reservations'][task['reservation_key']]
        if replace_terminal_job is not None:
            if r.get('job_id')!=replace_terminal_job or job==replace_terminal_job:
                raise ValueError('Replacement must exactly identify the old bound handle')
            observed=terminal_observation(replace_terminal_job)
            source=check_unrequested_live_source(task)
            previous=dict(r);previous.pop('terminal_replacements',None)
            r.setdefault('terminal_replacements',[]).append(dict(old_job_id=replace_terminal_job,new_job_id=job,
                observed=observed,source_identity=source,previous_binding=previous,replaced_at=time.time()))
            r.update(state='SUBMITTED',phase='WAITING_FOR_ALLOCATION')
        elif r.get('job_id') not in (None,job):raise ValueError('Different standby handle already exists')
        r['job_id']=job;r['registered_at']=time.time()
        if r['phase']=='WAITING_FOR_SUBMISSION':r.update(state='SUBMITTED',phase='WAITING_FOR_ALLOCATION')
        book['runs'][r['native_run']]['standby_job_id']=job
def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    q=sub.add_parser('prepare');q.add_argument('--configuration',required=True);q.add_argument('--node',required=True)
    q.add_argument('--gpu',required=True);q.add_argument('--python',required=True);q.add_argument('--native-cpus')
    q=sub.add_parser('register');q.add_argument('--task',required=True);q.add_argument('--job',type=int,required=True);q.add_argument('--replace-terminal-job',type=int)
    q=sub.add_parser('takeover');q.add_argument('--task',required=True)
    a=p.parse_args()
    if a.action=='prepare':
        mask=None if a.native_cpus is None else [int(v) for v in a.native_cpus.split(',')]
        prepare(a.configuration,a.node,a.gpu,a.python,mask);return 0
    if a.action=='register':register(a.task,a.job,a.replace_terminal_job);return 0
    guard(force=True);bind_protocol()
    return protocol.main(a.task)
if __name__=='__main__':raise SystemExit(main())