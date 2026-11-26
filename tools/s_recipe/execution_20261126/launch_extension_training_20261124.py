"""Explicit registered E1/subset submission via unchanged finite S providers."""
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

ROOT=Path('/share/home/zixiao/descriptor_analysis')
R=ROOT/'MFM_s_recipe'
C=ROOT/'runs/s_recipe_20261120'
sys.path.insert(0,str(R/'tools/s_recipe'))
from runtime import write
from dispatch import authorized, gate, existing_scheduling, OLD, NEW
from storage_20261122 import claim_current
from extension_training_20261124 import validate as validate_extension
from gpu_writer_admission_20261126 import register_after_admission

def read(path):
    return json.loads(Path(path).read_text())
def call(*args):
    return subprocess.check_output(['/usr/bin/timeout','15s',*args],text=True,env=dict(os.environ,TZ='UTC')).strip()
def fields(value):
    return dict(re.findall(r'(?:^| )(\w+)=([^ ]*)',value))
def waiting(reason,**extra):
    print(json.dumps(dict(status=reason,**extra)),flush=True)
    raise SystemExit(0)

if len(sys.argv)!=4 or sys.argv[1] not in ('k1','k2','k5','T5','T6') or sys.argv[2] not in {'compute-0-'+str(i) for i in (*range(8),20,22)}:
    raise ValueError('Use registered CELL NODE GPU')
name,node,gpu=sys.argv[1:]
if os.getuid()!=1278 or gate():
    raise ValueError('Wrong owner or unmet registration/P prerequisite')
with (C/'execution.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    best=read(R/'configs/s_recipe/CURRENT_BEST.json')
    metadata=read(C/'current_state.json')
    if best['status']!='FROZEN' or not metadata.get('extension_registration_published'):
        raise ValueError('Original frozen recipe and published extension registration required')
    proof=read(C/'cpu_stage_4539778.json')
    if proof['exit_code']!=0 or not proof['owned_descendants_exited']:
        raise ValueError('New extension logic tests are not closed')
    source=R/'configs/s_recipe/extensions_20261124'/(name+'_training.json')
    c=read(source)
    baseline=read(R/'configs/s_recipe'/('screening/S-R1.json' if name.startswith('k') else 'confirmation/S-final.json'))
    validate_extension(c,baseline,read(c['population']))
    if name in ('T5','T6'):
        existing=read(C/'execution.json')['runs']
        for k in (1,2,5):
            pending='S_E1_k'+str(k)+'_s0_3M'
            unresolved=metadata.get('extension_groups',{}).get('k'+str(k),{}).get('status')=='UNRESOLVED'
            if pending not in existing and not unresolved:
                waiting('WAITING_E1_PRIORITY',unassigned_E1=pending)
    authorized(c)
    if c['samples']!=(3000000 if name.startswith('k') else 9000000) or c['seed']!=0 or c.get('resume') or c['initialization']!=str(C/'initialization_seed0.pt'):
        raise ValueError('Only the registered fresh seed0 own-budget initialization')
    if not Path(c['initialization']).is_file():
        raise ValueError('Wrong arm or missing original random initialization')
    statepath=C/(c['run']+'_extension_controller.json')
    config=C/(c['run']+'_extension_configuration.json')
    taskpath=C/(c['run']+'_extension_task.json')
    ledger=read(C/'execution.json')
    if statepath.exists():
        old=read(statepath)
        if not old.get('job_id'):
            raise RuntimeError('Inspect the uncertain original submission; never retry blindly')
        print(json.dumps(old),flush=True)
        raise SystemExit(0)
    if c['run'] in ledger['runs'] or Path(c['output']).exists():
        raise ValueError('An existing extension producer/output must not be duplicated')
    n=fields(call('/usr/bin/scontrol','show','node',node,'-o'))
    if any(value in n['State'] for value in ('DRAIN','DOWN','NOT_RESPONDING','FAIL')):
        waiting('WAITING_HEALTHY_NODE',node=node,state=n['State'])
    scheduler=existing_scheduling()
    cards=[card for card in scheduler.observe(node) if card['gpu_uuid']==gpu]
    if len(cards)!=1:
        waiting('WAITING_ACTUAL_CARD_IDENTITY')
    card=cards[0]
    minimum=30720 if '5090' in card['gpu_name'] else 36864
    if (card['used_mib']/card['total_mib']>.30 or card['total_mib']-card['used_mib']<minimum or scheduler.own_gpu_busy(gpu,node)
            or (node not in ('compute-0-20','compute-0-22') and card['existing_compute_context'])):
        waiting('WAITING_GPU_MEMORY_OR_UUID_MUTEX',card=card)
    for job in (4538696,4539050):
        proof=read(C/('cpu_stage_'+str(job)+'.json'))
        if proof['exit_code']!=0 or not proof['owned_descendants_exited']:
            raise ValueError('Reused entry tests have not closed')
    quota=read(ROOT/'runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json')
    if quota['uid']!=1278 or quota['filesystem']!='/share' or not 0<=time.time()-quota['observed_time']<=5:
        waiting('WAITING_FRESH_UID_QUOTA')
    free=int(n['CPUEfctv'])-int(n['CPUAlloc'])
    native=node in ('compute-0-20','compute-0-22')
    if native and node not in ('compute-0-20','compute-0-22'):
        waiting('WAITING_ORDINARY_SMALL_GROUP_CPUS')
    workers=14 if native or free>=16 else 2
    cpus=workers+2
    ram=(64 if workers==14 else 16)*1024**3
    mode='native_with_standby' if native else 'Slurm'
    python=NEW if '5090' in card['gpu_name'] else OLD
    budget=read(C/'storage_additional_entries.json')
    extra=[]
    for kind,path,amount in (('node_disk','/',64*1024**2),('node_ram',None,ram)):
        identifier=c['run']+'_'+kind
        if any(row['id']==identifier for row in budget['entries']):
            raise ValueError('Existing writer forecast needs inspection')
        row=dict(id=identifier,kind=kind,node=node,bytes=amount)
        if path is not None:
            row['path']=path
        extra.append(row)
    # Refresh only the existing live forecast before checking a proposal.
    claim_current()
    c.update(node=node,gpu_uuid=gpu,workers=workers,peak_ram_bytes=ram,mode=mode,
        minimum_free_gpu_mib=minimum,
        handoff_request=str(C/(c['run']+'_extension_handoff_request.json')),
        handoff_ack=str(C/(c['run']+'_extension_handoff_ack.json')))
    # Check the aggregate resident/root/shared future on the actual target
    # before creating a standby allocation or starting another GPU writer.
    admission_code=("import sys,json;sys.path.insert(0,"+repr(str(R/'tools/s_recipe'))+
        ");from gpu_writer_admission_20261126 import prospective_on_actual_node;print(json.dumps(prospective_on_actual_node("+
        repr(extra)+")))")
    def observe_proposal(_):
        return json.loads(call('/usr/bin/ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=3',node,
            shlex.join([python,'-B','-c',admission_code])))
    try:
        preflight=register_after_admission(budget,extra,observe_proposal,
            lambda prospective:write(C/'storage_additional_entries.json',prospective))
    except subprocess.CalledProcessError as error:
        waiting('WAITING_ACTUAL_RESOURCE_OR_OBSERVATION',node=node,run=c['run'],
            observation_exit_code=error.returncode,forecast_unchanged=True)
    claim_current()
    c['resource_preflight']=preflight
    if any(Path(c[key]).exists() for key in ('handoff_request','handoff_ack')):
        raise ValueError('Inspect existing request/ack before any launch')
    write(config,c)
    state=dict(phase='SUBMITTING',run=c['run'],node=node,gpu_uuid=gpu,mode=mode,
        configuration=str(config),task=str(taskpath),workers=workers,cpus=cpus,
        gpu_preflight=card,fresh_random_initialization=True,scientific_budget=c['samples'])
    write(statepath,state)
    job=int(call('/usr/bin/sbatch','--hold','--parsable','--job-name='+c['run']+'_extension',
        '--nodelist='+node,'--cpus-per-task='+str(cpus),'--output='+str(C/(c['run']+'_extension_%j.log')),
        str(C/'extension_guarded_20261124.sbatch'),str(taskpath if native else config),gpu,python,mode).split(';')[0])
    actual=fields(call('/usr/bin/scontrol','show','job','-o',str(job)))
    if actual['UserId']!='zixiao(1278)' or actual['JobState']!='PENDING' or actual['Reason']!='JobHeldUser':
        raise ValueError('The new allocation is not an actual held own job')
    match=re.fullmatch(r'(?:(\d+)-)?(\d+):(\d+):(\d+)',actual['TimeLimit'])
    if not match:
        raise ValueError('Actual finite TimeLimit required')
    day,hour,minute,second=(int(value or 0) for value in match.groups())
    limit=day*86400+hour*3600+minute*60+second
    if limit!=48*3600:
        raise ValueError('Unexpected real48h submission contract')
    anchor=datetime.datetime.fromisoformat(actual['SubmitTime']).replace(tzinfo=datetime.timezone.utc).timestamp()
    deadline=dict(schema='S_REAL_SLURM_LIMIT_V1',source='scontrol_show_job_utc',job_id=job,uid=1278,
        node=node,observed_time=time.time(),time_limit_seconds=limit,anchor_epoch=anchor,deadline_basis='submit_lower_bound')
    write(C/('deadline_'+str(job)+'.json'),deadline)
    state.update(job_id=job,phase='HELD_SUBMITTED',deadline=deadline,
        lifecycle_record=str(C/(c['run']+('_native_extension_20261123.json' if native else '_guarded_'+str(job)+'.json'))))
    write(statepath,state)
    ledger['runs'][c['run']]=dict(state,status='NATIVE_SPAWN_REQUESTED' if native else 'PENDING')
    write(C/'execution.json',ledger)
    if native:
        task=dict(configuration=c,python=python,standby_job_id=job,lifecycle_record=state['lifecycle_record'],
            spawn_record=str(C/(c['run']+'_extension_spawn.json')),
            native_log=str(C/(c['run']+'_extension_native.log')),
            contract=dict(schema='S_FINITE_NATIVE_V1',uid=1278,run=c['run'],node=node,
                created_at=time.time(),duration_seconds=limit))
        write(taskpath,task)
        spawn=json.loads(call('/usr/bin/ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=3',node,
            shlex.join([python,'-B',str(C/'extension_native_spawn_20261124.py'),str(taskpath)])))
        task['producer']=spawn['producer']
        write(taskpath,task)
        state['producer']=spawn['producer']
        write(statepath,state)
        until=time.monotonic()+15
        while not Path(state['lifecycle_record']).is_file():
            if time.monotonic()>=until:
                raise RuntimeError('Native startup unconfirmed; inspect this producer and keep standby held')
            time.sleep(.1)
        started=read(state['lifecycle_record'])
        if started.get('run')!=c['run'] or not all(started['producer'][key]==spawn['producer'][key] for key in ('pid','uid','start_ticks')):
            raise ValueError('Native startup has a different producer identity')
    call('/usr/bin/scontrol','release',str(job))
    state.update(phase='RELEASED',released_at=time.time())
    write(statepath,state)
    ledger['runs'][c['run']]=dict(state,status='RUNNING_NATIVE' if native else 'PENDING')
    write(C/'execution.json',ledger)
    print(json.dumps(state),flush=True)
