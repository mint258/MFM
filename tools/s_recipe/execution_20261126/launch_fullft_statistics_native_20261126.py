"""Only when all12 actual fits of one point are C0, launch its CPU producer."""
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
from control_metadata_io_20261127 import write
read=lambda p:json.loads(Path(p).read_text())
def call(*argv):
    return subprocess.check_output(['/usr/bin/timeout','15s',*argv],text=True,
                                   env=dict(os.environ,TZ='UTC')).strip()
def fields(raw):return dict(re.findall(r'(?:^| )(\w+)=([^ ]*)',raw))
point,node=sys.argv[1:3]
core=sys.argv[3] if len(sys.argv)>3 else '54'
attempt=int(sys.argv[4]) if len(sys.argv)>4 else 0
if node not in {'compute-0-'+str(i) for i in (9,11,12,13,19)} or os.getuid()!=1278:
    raise ValueError('Use a healthy supported CPU role')
with (C/'execution.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    plan=read(C/'finetune_plan_20261124.json')
    cells=[row for row in plan['cells'] if row['point']==point]
    if len(cells)!=12:
        raise ValueError('One exact registered four-task x three-seed point')
    handle='S_FT_statistics_'+point+'_attempt'+str(attempt)
    state_path=C/(handle+'_controller.json')
    if state_path.exists():
        print(json.dumps(dict(status='EXISTING_HANDLE',controller=read(state_path))),flush=True)
        raise SystemExit(0)
    ledger=read(C/'execution.json')
    for prior in ledger['statistics'].values():
        if prior.get('node')==node and prior.get('mode') in ('cpu','fullft_cpu') and prior.get('job_id'):
            raw=call('/usr/bin/sacct','-X','-n','-P','-j',str(prior['job_id']),'--format=State')
            if any(row.split('|')[0].strip() in ('PENDING','RUNNING','CONFIGURING','COMPLETING')
                   for row in raw.splitlines()):
                print(json.dumps(dict(status='WAITING_OWN_CPU_READER',node=node)),flush=True)
                raise SystemExit(0)
    groups={task:[] for task in plan['scratch']}
    completed=[]
    summaries=[]
    for cell in cells:
        candidates=[row for row in ledger['statistics'].values()
                    if row.get('run')==cell['run'] and row.get('mode') in ('finetune','finetune_native')]
        if not candidates:
            print(json.dumps(dict(status='WAITING_FULLFT_FITS',point=point)),flush=True)
            raise SystemExit(0)
        source=max(candidates,key=lambda row:row.get('released_at',0))
        if source.get('job_id') is not None:
            actual=call('/usr/bin/sacct','-X','-n','-P','-j',str(source['job_id']),
                        '--format=JobIDRaw,State,ExitCode').splitlines()
            if actual!=[str(source['job_id'])+'|COMPLETED|0:0']:
                print(json.dumps(dict(status='WAITING_ACTUAL_SOURCE_C0',point=point,job_id=source['job_id'])),flush=True)
                raise SystemExit(0)
        elif not source.get('resource_closed'):
            print(json.dumps(dict(status='WAITING_ACTUAL_NATIVE_EXIT_AND_STANDBY_SETTLEMENT',point=point)),flush=True)
            raise SystemExit(0)
        closure=read(source['lifecycle_record'])
        if (closure.get('status')!='COMPLETE' or closure.get('exit_code')!=0
                or not closure.get('owned_descendants_exited') or not closure.get('observer_joined')):
            raise ValueError('Completed allocation is not proof of complete scientific fit/owned exit')
        output=C/'finetune_20261124'/cell['run']
        summary=output/'summary.json'
        from seal_finetune_20261124 import same_execution
        summary_value=read(summary)
        if summary_value.get('status')!='COMPLETE' or not same_execution(summary_value,closure):
            raise ValueError('FullFT summary is missing its actual complete result')
        groups[cell['task']].append((cell['seed'],str(output/'prediction.pt')))
        completed.append(dict(output=str(output),lifecycle_record=source['lifecycle_record']))
        summaries.append(str(summary))
    groups={task:[path for _,path in sorted(values)] for task,values in groups.items()}
    info=fields(call('/usr/bin/scontrol','show','node',node,'-o'))
    if any(x in info['State'] for x in ('DRAIN','DOWN','NOT_RESPONDING','FAIL')):
        raise ValueError('Fault node is excluded')
    # A queue is allowed, but no CPU allocation waits inside for source fits.
    c=dict(run=handle,ready=True,invoking_authority='docs/s_recipe/USER_DIRECTIVE_20261123B.md',
        node=node,output=str(C/'finetune_statistics_20261124'/point),output_mount='/share',
        cleanup_seconds=900,work_unit_seconds=60,peak_ram_bytes=4*1024**3,
        groups={point:groups},scratch=plan['scratch'],reference=plan['reference'],frozen={},
        required_complete_summaries=summaries+plan['scratch_complete_summaries'],
        completed_new_S_fits=completed,providers_sha256=plan['providers_sha256'],
        E1_seed_mean_draws=(point=='S_R1_3M' or point.startswith('S_E1_')))
    forecast_path=C/'storage_additional_entries.json'
    forecast=read(forecast_path)
    for kind,path,need in (('node_ram',None,4*1024**3),('node_disk','/',16*1024**2)):
        existing=sum(row['bytes'] for row in forecast['entries'] if row['kind']==kind
                     and row.get('node')==node and row.get('path')==path)
        if existing<need:
            entry=dict(id=handle+'_'+kind,kind=kind,node=node,bytes=need-existing)
            if path is not None:entry['path']=path
            forecast['entries'].append(entry)
    write(forecast_path,forecast)
    claim_current()
    config=C/(handle+'_configuration.json')
    write(config,c)
    native_handle=handle+'_native'
    launched=json.loads(call('/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python','-B',
        C/'launch_cpu_native_20261126.py','fullft_statistics',native_handle,node,core,config))
    record=C/'native_cpu_20261126'/native_handle/'record.json'
    state=dict(phase='NATIVE_STARTED',run=handle,point=point,mode='fullft_cpu_native',node=node,
        configuration=str(config),job_id=None,native_handle=native_handle,
        lifecycle_record=str(record),native_controller=launched,
        source_fit_jobs=[read(item['lifecycle_record'])['job_id'] for item in completed
            if read(item['lifecycle_record']).get('job_id') is not None],
        source_native_fits=[dict(output=item['output'],lifecycle_record=item['lifecycle_record'])
            for item in completed if read(item['lifecycle_record']).get('job_id') is None],
        retained_prior_safe_pause_jobs=[row['job_id'] for row in ledger['statistics'].values()
            if row.get('run') in {cell['run'] for cell in cells}
            and row.get('status')=='PAUSED_SAFE_CONTINUATION' and row.get('job_id')])
    write(state_path,state)
    ledger['statistics'][handle]=dict(state,status='RUNNING_NATIVE')
    write(C/'execution.json',ledger)
    print(json.dumps(state),flush=True)
