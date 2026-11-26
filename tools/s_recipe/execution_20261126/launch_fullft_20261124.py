"""S fullFT metadata controller: one ready fit on one actually empty0..7 card."""
import datetime
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

ROOT = Path('/share/home/zixiao/descriptor_analysis')
R = ROOT/'MFM_s_recipe'
C = ROOT/'runs/s_recipe_20261120'
sys.path.insert(0, str(R/'tools/s_recipe'))
from storage_20261122 import write, claim_current
from finetune_extension_20261124 import validate, AUTHORITY, PROTOCOL
from extension_output_budget_20261124 import forecast as output_forecast,job_states,GiB
from gpu_writer_admission_20261126 import register_after_admission
from dispatch import OLD,NEW

read = lambda p: json.loads(Path(p).read_text())
def call(*argv):
    return subprocess.check_output(['/usr/bin/timeout','15s',*argv], text=True,
                                   env=dict(os.environ,TZ='UTC')).strip()
def fields(raw):
    return dict(re.findall(r'(?:^| )(\w+)=([^ ]*)',raw))

parser=argparse.ArgumentParser()
parser.add_argument('node')
parser.add_argument('gpu_uuid')
parser.add_argument('--run')
parser.add_argument('--attempt',type=int,default=0)
args=parser.parse_args()
node,uuid=args.node,args.gpu_uuid
if args.attempt<0 or (args.attempt>0 and not args.run):
    raise ValueError('A continuation must name its exact fit and next attempt')
native=node in ('compute-0-20','compute-0-22')
if node not in {'compute-0-'+str(i) for i in (*range(8),20,22)} or os.getuid() != 1278:
    raise ValueError('Ordinary0..7 or explicit mixed20/22 GPU and real owner required')
with (C/'execution.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    fcntl.lockf(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    metadata = read(C/'current_state.json')
    if not metadata.get('extension_registration_published'):
        raise ValueError('Publish the concrete extension registration before first new fit')
    tests = read(C/'cpu_stage_4539778.json')
    if tests.get('exit_code') != 0 or not tests.get('owned_descendants_exited'):
        raise ValueError('New logic check has not closed successfully')
    if native:
        for filename in ('mixed_fullft_runtime_check_20261126.json','mixed_fullft_binding_check_20261126.json'):
            proof=read(C/filename)
            owned=read(proof['native_record'])
            command=read(Path(proof['native_record']).with_name('command_exit.json'))
            if (owned.get('status')!='COMPLETE' or owned.get('exit_code')!=0 or command.get('exit_code')!=0
                    or not owned.get('owned_descendants_exited') or not owned.get('observer_joined')):
                raise ValueError('New mixed fullFT runtime check has not actually closed')
        observed=read(C/'latest_S_gpu_admission_20261122.json')
        if not 0<=time.time()-observed['observed_at']<=60:
            raise ValueError('Refresh both GPU groups before mixed fullFT fallback')
        ordinary=[card for card in observed['cards'] if card['node'] not in ('compute-0-20','compute-0-22')
            and not card['existing_compute_context'] and card['free_cpus']>=16
            and card['total_mib']>=24000 and card['total_mib']-card['used_mib']>=22000]
        if ordinary:
            print(json.dumps(dict(status='USE_QUALIFIED_ORDINARY_FULLFT_CARD_FIRST',cards=ordinary)),flush=True)
            raise SystemExit(0)
    plan = read(C/'finetune_plan_20261124.json')
    ledger = read(C/'execution.json')
    info = fields(call('/usr/bin/scontrol','show','node',node,'-o'))
    if (any(x in info['State'] for x in ('DRAIN','DOWN','NOT_RESPONDING','FAIL'))
            or 'gpu' not in info.get('Partitions','').split(',')
            or (not native and int(info['CPUEfctv'])-int(info['CPUAlloc']) < 16)):
        print(json.dumps(dict(status='WAITING_HEALTHY_16CPU_GPU_SLOT',node=node)),flush=True)
        raise SystemExit(0)
    from dispatch import existing_scheduling
    scheduler = existing_scheduling()
    card = next((c for c in scheduler.observe(node) if c['gpu_uuid']==uuid),None)
    if (card is None or (not native and card['existing_compute_context'])
            or card['total_mib'] < 24000 or card['total_mib']-card['used_mib'] < 22000
            or card['used_mib']/card['total_mib']>.30
            or scheduler.own_gpu_busy(uuid,node)):
        print(json.dumps(dict(status='WAITING_ACTUALLY_EMPTY_FULLFT_CARD',node=node,gpu_uuid=uuid)),flush=True)
        raise SystemExit(0)
    # Bind ownership to the exact UUID, including a pending native fit whose
    # allocator has not created a CUDA context. Whole-node RAM remains covered
    # by prospective admission of all active writers below.
    for row in ledger['statistics'].values():
        if (row.get('node')==node and row.get('gpu_uuid')==uuid
                and row.get('mode') in ('finetune_native','gpu_native') and not row.get('resource_closed')):
            print(json.dumps(dict(status='WAITING_OWN_NATIVE_FIT_CLOSURE',node=node)),flush=True)
            raise SystemExit(0)
        if row.get('node')==node and row.get('gpu_uuid')==uuid and row.get('job_id'):
            states=call('/usr/bin/sacct','-X','-n','-P','-j',str(row['job_id']),'--format=State')
            if any(line.split('|')[0].strip() in ('RUNNING','PENDING','CONFIGURING','COMPLETING')
                   for line in states.splitlines()):
                print(json.dumps(dict(status='WAITING_OWN_GPU_READER',node=node,gpu_uuid=uuid)),flush=True)
                raise SystemExit(0)
    selected = None
    for cell in plan['cells']:
        if args.run and cell['run']!=args.run:continue
        handle = cell['run']+'_attempt'+str(args.attempt)
        if (C/(handle+'_controller.json')).exists():
            continue
        fit_output=C/'finetune_20261124'/cell['run']
        if (fit_output/'summary.json').exists() and read(fit_output/'summary.json').get('status')=='COMPLETE':
            continue
        if args.attempt==0 and fit_output.exists():
            raise ValueError('Inspect an existing fit output; do not restart it as fresh')
        if args.attempt>0:
            previous=ledger['statistics'].get(cell['run']+'_attempt'+str(args.attempt-1),{})
            if not previous.get('resource_closed') or previous.get('status')!='PAUSED_SAFE_CONTINUATION':
                raise ValueError('Close the exact preceding partial fit before continuation')
        source = cell['source']
        summary_path = C/'training'/source['run']/'summary.json'
        if not summary_path.exists() or read(summary_path).get('samples') != source['source_training_budget']:
            continue
        origin = ledger['runs'].get(source['run'],{})
        closure = Path(origin.get('lifecycle_record',str(C/(source['run']+'_producer_exit_evidence.json'))))
        if not closure.exists() or not read(closure).get('owned_descendants_exited'):
            continue
        if not Path(source['checkpoint']).is_file():
            continue
        selected = cell,handle,closure
        break
    if selected is None:
        print(json.dumps(dict(status='NO_UNSUBMITTED_READY_FULLFT_CELL')),flush=True)
        raise SystemExit(0)
    cell,handle,closure = selected
    output_budget=output_forecast(ledger,job_states(ledger,call),incoming_bytes=GiB,incoming_finetune=True)
    if not output_budget['admitted']:
        print(json.dumps(dict(status='WAITING_CPU_SEAL_OR_OUTPUT_HEADROOM',forecast=output_budget)),flush=True)
        raise SystemExit(0)
    source = cell['source']
    binding = dict(source, bytes=Path(source['checkpoint']).stat().st_size,
        producer_exit_evidence=str(closure))
    c = dict(schema='S_REUSED_P_FULLFT_20261124_V1', invoking_authority=AUTHORITY,
        authority=PROTOCOL, kind='F', ready=True, mode='full', run=cell['run'],
        task=cell['task'], seed=cell['seed'], seed_role='finetuning', pretraining_seed=0,
        internal_split_seed=20261112, bootstrap_seed=20261025, source_binding=binding,
        store=read(R/'configs/s_recipe/screening/S-R1.json')['evaluation_store'],
        output=str(C/'finetune_20261124'/cell['run']), output_mount='/share',
        cleanup_seconds=900, work_unit_seconds=120, cpus=16, peak_ram_bytes=64*1024**3,
        minimum_free_gpu_mib=22000, nvidia_smi='/usr/bin/nvidia-smi', node=node,gpu_uuid=uuid,
        providers_sha256=plan['providers_sha256'], unchanged_scientific_provider=True)
    if native:c['execution_backend']='mixed_gpu_native_20261126'
    validate(c)
    if args.attempt>0:
        from fullft_resume_20261126 import require_resume
        previous=ledger['statistics'][cell['run']+'_attempt'+str(args.attempt-1)]
        require_resume(previous,read(previous['lifecycle_record']),read(previous['configuration']),c)
    forecast_path = C/'storage_additional_entries.json'
    forecast = read(forecast_path)
    resource_ids=[]
    extra=[]
    for kind,path,need in (('node_ram',None,64*1024**3),('node_disk','/',32*1024**2)):
        entry=dict(id=handle+'_'+kind,kind=kind,node=node,bytes=need)
        if path is not None: entry['path']=path
        resource_ids.append(entry['id'])
        extra.append(entry)
    claim_current()
    python=NEW if '5090' in card['gpu_name'] else OLD
    admission_code=('import sys,json;sys.path.insert(0,'+repr(str(R/'tools/s_recipe'))+
        ');from gpu_writer_admission_20261126 import prospective_on_actual_node;print(json.dumps(prospective_on_actual_node('+repr(extra)+')))')
    def observe(_):
        return json.loads(call('/usr/bin/ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=3',node,
            shlex.join([python,'-B','-c',admission_code])))
    try:
        c['resource_preflight']=register_after_admission(forecast,extra,observe,
            lambda value:write(forecast_path,value))
    except subprocess.CalledProcessError as error:
        print(json.dumps(dict(status='WAITING_ACTUAL_RESOURCE_OR_OBSERVATION',node=node,
            observation_exit_code=error.returncode,forecast_unchanged=True)),flush=True)
        raise SystemExit(0)
    claim_current()
    config_path=C/(handle+'_configuration.json')
    write(config_path,c)
    state_path=C/(handle+'_controller.json')
    state=dict(phase='SUBMITTING',run=cell['run'],point=cell['point'],task=c['task'],seed=c['seed'],
        node=node,gpu_uuid=uuid,mode='finetune_native' if native else 'finetune',configuration=str(config_path),
        resource_ids=resource_ids,source_binding=binding)
    write(state_path,state)
    job=int(call('/usr/bin/sbatch','--hold','--parsable','--job-name='+handle,
        '--partition=gpu','--nodelist='+node,'--cpus-per-task=16',
        '--output='+str(C/(handle+'_%j.log')),
        str(C/('fullft_native_standby_20261126.sbatch' if native else 'fullft_20261124.sbatch')),
        str(C/(handle+'_fullft_native_task.json') if native else config_path),uuid,
        *([python] if native else [])).split(';')[0])
    state.update(job_id=None if native else job,phase='HELD_SUBMITTED')
    if native:state['standby_job_id']=job
    write(state_path,state)
    actual=fields(call('/usr/bin/scontrol','show','job','-o',str(job)))
    if (actual['UserId']!='zixiao(1278)' or actual['JobName']!=handle
            or actual['JobState']!='PENDING' or actual['Reason']!='JobHeldUser'
            or actual['TimeLimit']!='00:35:00'):
        raise ValueError('Actual held finite allocation does not match')
    if native:
        taskpath=C/(handle+'_fullft_native_task.json')
        task=dict(configuration=str(config_path),native_handle=handle,standby_job_id=job,
            native_record=str(C/(handle+'_fullft_native_record.json')),
            handoff_request=str(C/(handle+'_fullft_handoff_request.json')),
            native_log=str(C/(handle+'_fullft_native.log')),python=python,
            contract=dict(uid=1278,run=c['run'],node=node,created_at=time.time(),duration_seconds=2100))
        write(taskpath,task)
        state.update(lifecycle_record=task['native_record'],native_task=str(taskpath),status='NATIVE_SPAWN_REQUESTED')
        write(state_path,state)
        ledger['statistics'][handle]=dict(state)
        write(C/'execution.json',ledger)
        spawned=json.loads(call('/usr/bin/ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=3',node,
            shlex.join([python,'-B',str(C/'fullft_native_spawn_20261126.py'),str(taskpath)])))
        task['producer']=spawned['producer']
        write(taskpath,task)
        state['producer']=spawned['producer']
        until=time.monotonic()+15
        while not Path(task['native_record']).exists():
            if time.monotonic()>=until:raise RuntimeError('Native fullFT startup uncertain; keep actual standby held')
            time.sleep(.1)
        started=read(task['native_record'])
        if any(started['producer'][key]!=task['producer'][key] for key in ('pid','uid','start_ticks')):
            raise ValueError('Native fullFT startup producer differs')
    state.update(phase='RELEASE_REQUESTED')
    write(state_path,state)
    call('/usr/bin/scontrol','release',str(job))
    state.update(phase='RELEASED',released_at=time.time(),
        lifecycle_record=state['lifecycle_record'] if native else str(C/(cell['run']+'_guarded_'+str(job)+'.json')),
        deadline_basis='explicit native35min/900s closing; genuine same-task standby' if native else 'entry queries and verifies actual RUNNING allocation EndTime')
    write(state_path,state)
    ledger['statistics'][handle]=dict(state,status='RUNNING_NATIVE' if native else 'PENDING')
    write(C/'execution.json',ledger)
    print(json.dumps(state),flush=True)
