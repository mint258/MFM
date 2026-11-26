"""Registered readout controller: qualified ordinary GPU or mixed native fallback."""
import argparse
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
from storage_20261122 import claim_current,write
from gpu_writer_admission_20261126 import register_after_admission
from extension_output_budget_20261124 import forecast as output_forecast,job_states,GiB
from dispatch import existing_scheduling,OLD,NEW
from readout_task_20261126 import binding,EXTENSIONS
read=lambda path:json.loads(Path(path).read_text())
def call(*args):return subprocess.check_output(['/usr/bin/timeout','15s',*map(str,args)],text=True).strip()
def fields(raw):return dict(re.findall(r'(?:^| )(\w+)=([^ ]*)',raw))
parser=argparse.ArgumentParser()
parser.add_argument('role',choices=('budget','terminal'))
parser.add_argument('run')
parser.add_argument('samples',type=int)
parser.add_argument('node')
parser.add_argument('gpu_uuid')
parser.add_argument('--attempt',type=int,default=0)
args=parser.parse_args()
if (os.getuid()!=1278 or args.node not in {'compute-0-'+str(i) for i in (*range(8),20,22)}
        or args.attempt<0 or not re.fullmatch(r'GPU-[a-fA-F0-9-]+',args.gpu_uuid)
        or args.run not in (*EXTENSIONS,'S_B0_s0_9M','S_final_s0_9M')):
    raise ValueError('Explicit registered readout identity/node/UUID required')
native=args.node in ('compute-0-20','compute-0-22')
handle=args.run+'_readout_'+args.role+'_'+str(args.samples)+'_attempt'+str(args.attempt)
controller=C/(handle+'_controller.json')
configuration=C/(handle+'_configuration.json')
taskpath=C/(handle+'_task.json')
with (C/'execution.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if controller.exists():
        print(json.dumps(read(controller)),flush=True)
        raise SystemExit(0)
    metadata=read(C/'current_state.json')
    if not metadata.get('extension_registration_published'):raise ValueError('Original extension registration must be published')
    for filename in ('readout_runtime_check_20261126.json',):
        proof=read(C/filename)
        owned=read(proof['native_record'])
        command=read(Path(proof['native_record']).with_name('command_exit.json'))
        if (owned['status']!='COMPLETE' or owned['exit_code']!=0 or command['exit_code']!=0
                or not owned['owned_descendants_exited'] or not owned['observer_joined']):
            raise ValueError('New readout adapter check must actually close')
    ledger=read(C/'execution.json')
    c=read(C/'training'/args.run/'configuration.json')
    c.update(training_closure_record=ledger['runs'][args.run]['lifecycle_record'],
        node=args.node,gpu_uuid=args.gpu_uuid,peak_ram_bytes=16*GiB,evaluation_peak_ram_bytes=16*GiB)
    if args.role=='budget':c['readout_authority']='docs/s_recipe/USER_DIRECTIVE_20261123C.md'
    task=dict(handle=handle,run=args.run,role=args.role,samples=args.samples,native=native,
        configuration=str(configuration),native_record=str(C/(handle+'_native_record.json')),
        handoff_request=str(C/(handle+'_handoff_request.json')))
    output,phase=binding(task,c)
    # Metadata-only prerequisite functions; never import a model on login.
    if args.role=='budget':
        from budget_readouts_extension_20261124 import registered
    else:
        from terminal_readouts_20261122 import registered
    registered(c,args.samples)
    if (output/phase).exists():
        old=read(output/phase)
        if old.get('status') in ('GPU_SNAPSHOT_COMPLETE_WAITING_CPU','GPU_TERMINAL_COMPLETE_WAITING_CPU') and old.get('owned_descendants_exited'):
            print(json.dumps(dict(status='GPU_ALREADY_CLOSED_WAITING_CPU',run=args.run,samples=args.samples)),flush=True)
            raise SystemExit(0)
    if args.role=='terminal' and read(Path(c['output'])/'summary.json').get('status')=='COMPLETE':
        print(json.dumps(dict(status='ALREADY_COMPLETE',run=args.run)),flush=True)
        raise SystemExit(0)
    if args.attempt>0:
        previous_handle=handle.rsplit('_attempt',1)[0]+'_attempt'+str(args.attempt-1)
        previous=ledger['statistics'][previous_handle]
        closure=read(previous['lifecycle_record'])
        if (not previous.get('resource_closed') or closure.get('status')!='PAUSED_READOUT'
                or closure.get('exit_code')!=75 or not closure.get('owned_descendants_exited')
                or not closure.get('observer_joined') or not closure.get('ended_at')):
            raise ValueError('The exact preceding partial readout must close before continuation')
        old=read(previous['configuration'])
        from checkpoint_binding import validate_resume
        validate_resume(c,old)
    elif (output/phase).exists():
        raise ValueError('Inspect the existing phase; do not restart it as fresh')
    info=fields(call('/usr/bin/scontrol','show','node',args.node,'-o'))
    if (any(flag in info['State'] for flag in ('DRAIN','DOWN','NOT_RESPONDING','FAIL'))
            or 'gpu' not in info.get('Partitions','').split(',')
            or (not native and int(info['CPUEfctv'])-int(info['CPUAlloc'])<16)):
        print(json.dumps(dict(status='WAITING_HEALTHY_DEMAND_BASED_GPU_SLOT',node=args.node)),flush=True)
        raise SystemExit(0)
    if native:
        observed=read(C/'latest_S_gpu_admission_20261122.json')
        if not 0<=time.time()-observed['observed_at']<=60:raise ValueError('Refresh both GPU groups before fallback')
        preferred=[card for card in observed['cards'] if card['node'] not in ('compute-0-20','compute-0-22')
            and not card['existing_compute_context'] and card['free_cpus']>=16
            and card['total_mib']-card['used_mib']>=18432 and card['used_mib']/card['total_mib']<=.30]
        if preferred:
            print(json.dumps(dict(status='USE_QUALIFIED_ORDINARY_READOUT_CARD_FIRST',cards=preferred)),flush=True)
            raise SystemExit(0)
    scheduler=existing_scheduling()
    card=next((row for row in scheduler.observe(args.node) if row['gpu_uuid']==args.gpu_uuid),None)
    if (card is None or (not native and card['existing_compute_context'])
            or card['used_mib']/card['total_mib']>.30 or card['total_mib']-card['used_mib']<18432
            or scheduler.own_gpu_busy(args.gpu_uuid,args.node)):
        print(json.dumps(dict(status='WAITING_ACTUAL_READOUT_CARD',node=args.node)),flush=True)
        raise SystemExit(0)
    lockpath=ROOT/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(args.gpu_uuid+'.lock')
    with lockpath.open('a') as probe:
        try:fcntl.flock(probe,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps(dict(status='WAITING_GPU_UUID_MUTEX',node=args.node)),flush=True)
            raise SystemExit(0)
    points=[args.samples] if args.role=='budget' else c['evaluation_samples']
    budget=output_forecast(ledger,job_states(ledger,call),incoming_bytes=len(points)*GiB)
    if not budget['admitted']:
        print(json.dumps(dict(status='WAITING_OUTPUT_HEADROOM',forecast=budget)),flush=True)
        raise SystemExit(0)
    extra=[dict(id=handle+'_node_ram',kind='node_ram',node=args.node,bytes=16*GiB),
        dict(id=handle+'_node_disk',kind='node_disk',node=args.node,path='/',bytes=16*1024**2)]
    forecast=read(C/'storage_additional_entries.json')
    claim_current()
    python=NEW if '5090' in card['gpu_name'] else OLD
    source=('import sys,json;sys.path.insert(0,'+repr(str(R/'tools/s_recipe'))+
        ');from gpu_writer_admission_20261126 import prospective_on_actual_node;print(json.dumps(prospective_on_actual_node('+repr(extra)+')))')
    def observe(_):return json.loads(call('ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=3',args.node,
        shlex.join([python,'-B','-c',source])))
    try:
        c['resource_preflight']=register_after_admission(forecast,extra,observe,
            lambda value:write(C/'storage_additional_entries.json',value))
    except subprocess.CalledProcessError as error:
        print(json.dumps(dict(status='WAITING_ACTUAL_RESOURCE_OR_OBSERVATION',forecast_unchanged=True,
            node=args.node,observation_exit_code=error.returncode)),flush=True)
        raise SystemExit(0)
    claim_current()
    write(configuration,c)
    state=dict(run=args.run,role=args.role,samples=args.samples,mode='gpu_native' if native else 'gpu',
        phase='SUBMITTING',node=args.node,gpu_uuid=args.gpu_uuid,configuration=str(configuration),
        native_task=str(taskpath),resource_ids=[row['id'] for row in extra],readout_points=points,
        lifecycle_record=task['native_record'])
    write(controller,state)
    job=int(call('/usr/bin/sbatch','--hold','--parsable','--job-name='+handle,'--partition=gpu',
        '--nodelist='+args.node,'--cpus-per-task=16','--output='+str(C/(handle+'_%j.log')),
        C/'readout_execution_20261126.sbatch',taskpath,args.gpu_uuid,python,'standby' if native else 'ordinary').split(';')[0])
    actual=fields(call('/usr/bin/scontrol','show','job',job,'-o'))
    if (actual.get('UserId')!='zixiao(1278)' or actual.get('JobName')!=handle
            or actual.get('JobState')!='PENDING' or actual.get('Reason')!='JobHeldUser'
            or actual.get('TimeLimit')!='02:00:00'):
        raise ValueError('Actual own held readout allocation differs')
    task.update(job_id=None if native else job,standby_job_id=job if native else None,
        contract=dict(uid=1278,run=args.run,node=args.node,role=args.role,samples=args.samples,
            created_at=time.time(),duration_seconds=7200))
    state.update(job_id=task['job_id'],standby_job_id=task['standby_job_id'],phase='HELD_SUBMITTED')
    if not native:state['lifecycle_record']=str(C/(handle+'_guarded_'+str(job)+'.json'))
    write(taskpath,task)
    write(controller,state)
    ledger['statistics'][handle]=dict(state,status='NATIVE_SPAWN_REQUESTED' if native else 'PENDING')
    write(C/'execution.json',ledger)
    if native:
        spawned=json.loads(call('ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=3',args.node,
            shlex.join([python,'-B',str(C/'readout_native_spawn_20261126.py'),str(taskpath),python])))
        task['producer']=spawned['producer']
        write(taskpath,task)
        state['producer']=spawned['producer']
        until=time.monotonic()+15
        while not Path(task['native_record']).exists():
            if time.monotonic()>=until:raise RuntimeError('Readout startup uncertain; keep its own standby held')
            time.sleep(.1)
        started=read(task['native_record'])
        if any(started['producer'][key]!=task['producer'][key] for key in ('pid','uid','start_ticks')):
            raise ValueError('Readout startup belongs to another producer')
    call('/usr/bin/scontrol','release',job)
    state.update(phase='RELEASED',released_at=time.time())
    write(controller,state)
    ledger['statistics'][handle]=dict(state,status='RUNNING_NATIVE' if native else 'PENDING')
    write(C/'execution.json',ledger)
    print(json.dumps(state),flush=True)
