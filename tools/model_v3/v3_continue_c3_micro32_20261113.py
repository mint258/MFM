"""Execution-only C3 SDP microbatch continuation; retain every original segment."""
import argparse,copy,csv,datetime,json,os,shlex,socket,subprocess
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
P=C/'C3_VIEWS_20261113/plan.json'
J=C/'MODEL_V3_C3_MICRO32_CONTINUATION_20261113.json'
PY='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
WRAP=str(R/'tools/model_v3/v2_run_development.sbatch')
arg=argparse.ArgumentParser();arg.add_argument('phase',choices=['prepare','stop','rebind','release'])
phase=arg.parse_args().phase
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-20'
os.chdir(R)
def run(argv):
    r=subprocess.run(argv,capture_output=True,text=True)
    if r.returncode:raise RuntimeError(str(argv)+' '+r.stderr)
    return r.stdout.strip()
def save(path,value):
    path=Path(path);tmp=path.with_name(path.name+'.micro32_next')
    tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)
def current(job):return run(['scontrol','show','job','-o',str(job)])
def own_pending(job):
    raw=current(job)
    assert 'UserId=zixiao(1278)' in raw and 'JobState=PENDING' in raw and 'RunTime=00:00:00' in raw
    return raw
def lastrow(root):
    f=Path(root)/'losses.csv'
    with f.open('rb') as s:
        head=s.readline().decode();s.seek(max(0,f.stat().st_size-65536));data=s.read().decode()
    lines=data.splitlines()
    if not data.endswith('\n'):lines=lines[:-1]
    return next(csv.DictReader([head.rstrip(),lines[-1]]))
if phase=='prepare':
    assert not J.exists(),'Resume existing continuation journal, do not duplicate submissions'
    plan=json.loads(P.read_text())
    state=dict(phase='PREPARING',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        change='microbatch16_to32_only',effective_batch=32,sample_budget=6000000,
        original_files_retained=True,science_changed=False,rows=[])
    save(J,state)
    for old in (r for r in plan['runs'] if r['condition']=='SDP'):
        before=current(old['job'])
        assert 'UserId=zixiao(1278)' in before and 'JobState=RUNNING' in before
        assert 'NodeList='+old['node'] in before and 'Restarts=0' in before
        for key in ('evaluation_job','archive_job'):own_pending(old[key])
        previous=json.loads(Path(old['configuration']).read_text())
        assert previous['microbatch_size']==16 and previous['batch_size']==32 and previous['latent']=='none'
        frozen=Path(old['output'])/'micro32_resume_complete_20261113.pt'
        assert not frozen.exists()
        os.link(Path(old['output'])/'recovery.pt',frozen)
        c=copy.deepcopy(previous)
        c.update(microbatch_size=32,resume=str(frozen),
            output=old['output']+'_micro32_resume_20261113')
        assert not Path(c['output']).exists()
        cp=Path(old['configuration']).with_name(Path(old['configuration']).stem+'_micro32_resume.json')
        save(cp,c)
        admission=run(['ssh','-n',old['node'],'cd '+str(R)+' && '+PY+
            ' -B tools/model_v3/v2_diagnosis_disk.py --once --output '+c['output']+
            ' --node '+old['node']+' --job 0 --state /dev/null'])
        peak=int(lastrow(old['output'])['gpu_peak_bytes'])
        devices=run(['ssh','-n',old['node'],'nvidia-smi --query-gpu=uuid,memory.total --format=csv,noheader,nounits'])
        available={g.strip():int(float(b.strip())*1024**2) for g,b in csv.reader(devices.splitlines())}
        assert peak*2.5<available[old['gpu']],'Conservative observed-peak execution estimate does not fit'
        for key in ('evaluation_job','archive_job'):
            own_pending(old[key]);run(['scontrol','hold',str(old[key])])
        new=int(run(['sbatch','--hold','--parsable','--partition=all','--nodelist='+old['node'],
            '--cpus-per-task=16','--time=0','--dependency=afterany:'+str(old['job']),
            '--job-name=v3-C3-'+old['arm']+'-SDP-micro32',WRAP,'selected',str(cp),old['gpu'],PY]).split(';')[0])
        state['rows'].append(dict(old=old,new_job=new,configuration=str(cp),output=c['output'],
            frozen_resume=str(frozen),admission=json.loads(admission),observed_peak_bytes=peak,
            projected_peak_bytes=peak*2.5,device=devices,before=before))
        save(J,state)
    state['phase']='NEW_EXECUTION_SEGMENTS_HELD_ORIGINALS_RUNNING';save(J,state)
else:
    state=json.loads(J.read_text())
    if phase=='stop':
        assert state['phase']=='NEW_EXECUTION_SEGMENTS_HELD_ORIGINALS_RUNNING'
        for row in state['rows']:
            old=row['old'];raw=current(old['job'])
            assert 'UserId=zixiao(1278)' in raw and 'JobState=RUNNING' in raw and 'NodeList='+old['node'] in raw
            row['last_before_signal']=lastrow(old['output'])
            run(['scancel','--signal=INT','--full','--user=zixiao','--nodelist='+old['node'],str(old['job'])])
            row['stop_signal_sent_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save(J,state)
        state['phase']='ORIGINAL_SEGMENTS_INTERRUPT_REQUESTED';save(J,state)
    elif phase=='rebind':
        assert state['phase']=='ORIGINAL_SEGMENTS_INTERRUPT_REQUESTED'
        plan=json.loads(P.read_text());rp=C/'MODEL_V3_latent_guard_recovery_20261111.json'
        rec=json.loads(rp.read_text())
        partial=[]
        for row in state['rows']:
            old=row['old'];raw=current(old['job'])
            assert 'UserId=zixiao(1278)' in raw and any('JobState='+s in raw for s in ('FAILED','CANCELLED','COMPLETED'))
            marker=Path(old['output'])/'offline_wandb'/str(old['job'])/'sdk_finished.json'
            sdk=json.loads(marker.read_text()) if marker.exists() else dict(sdk_finished=False,interrupted=True,reason='Slurm all-process INT ended SDK before its finish marker')
            assert not marker.exists() or sdk.get('sdk_finished') is True
            contexts=run(['ssh','-n',old['node'],'nvidia-smi --query-compute-apps=gpu_uuid,pid --format=csv,noheader,nounits'])
            assert not contexts,'Wait for actual old GPU context closure'
            row['old_terminal_controller']=raw;row['old_sdk_completion']=sdk
            row['last_native_row']=lastrow(old['output'])
            evpath=Path(old['evaluation_configuration']);ev=json.loads(evpath.read_text())
            save(evpath.with_name(evpath.stem+'_original_micro16.json'),ev)
            ev['checkpoint']=str(Path(row['output'])/'samples_6000000.pt');save(evpath,ev)
            acpath=Path(old['archive_configuration']);ac=json.loads(acpath.read_text())
            sp=Path(ac['sources_manifest']);sources=json.loads(sp.read_text())
            sources['runs']=[r for r in sources['runs'] if r['job']!=old['job']]
            sources['runs'].insert(0,dict(job=row['new_job'],sdk_directories=[
                dict(path=str(Path(row['output'])/'offline_wandb'/str(row['new_job'])),marker='sdk_finished.json')]))
            save(sp,sources);ac['jobs']=[row['new_job'],old['evaluation_job']]
            ac['retained_partial_executions']=[dict(job=old['job'],path=str(marker.parent),
                terminal_controller=raw,original_sdk_completion=sdk,classification='INTERRUPTED_PARTIAL_RAW_SDK')]
            save(acpath,ac)
            run(['scontrol','update','JobId='+str(old['evaluation_job']),'Dependency=afterok:'+str(row['new_job'])])
            run(['scontrol','update','JobId='+str(old['archive_job']),
                'Dependency=afterok:'+str(row['new_job'])+':'+str(old['evaluation_job'])])
            active=next(r for r in plan['runs'] if r['job']==old['job'])
            active.update(job=row['new_job'],configuration=row['configuration'],output=row['output'],
                microbatch_size=32,partial_training_segments=[dict(job=old['job'],output=old['output'],
                    configuration=old['configuration'],state='INTERRUPTED_FOR_EXECUTION_ONLY_CONTINUATION')],
                frozen_complete_resume=row['frozen_resume'])
            entry=copy.deepcopy(next(r for r in rec['jobs'] if r['job']==old['job']))
            entry.update(job=row['new_job'],configuration=row['configuration'],output=row['output'],
                restarts=0,execution_continuation_of=old['job'])
            rec['jobs'].append(entry)
            for existing in rec['jobs']:
                if existing['job']==old['evaluation_job']:existing['training_job']=row['new_job']
                if existing['job']==old['archive_job']:
                    existing['source_jobs']=[old['job'],row['new_job'],old['evaluation_job']]
            p=copy.deepcopy(old);p.update(stage='C3_PARTIAL_EXECUTION',arm=old['arm']+'-micro16-partial',
                execution_status='STOPPED_RAW_SDK_NOT_NORMALLY_FINALIZED')
            partial.append(p)
        save(P,plan);save(rp,rec)
        save(C/'C3_MICRO16_PARTIAL_SEGMENTS_20261113.json',dict(status='RETAINED_PARTIAL_EXECUTIONS',runs=partial))
        state['phase']='SAME_EVALUATIONS_AND_ARCHIVES_REBOUND';state['recovery_entries']=len(rec['jobs']);save(J,state)
    else:
        assert state['phase']=='SAME_EVALUATIONS_AND_ARCHIVES_REBOUND'
        for row in state['rows']:
            for job in (row['new_job'],row['old']['evaluation_job'],row['old']['archive_job']):
                own_pending(job);run(['scontrol','release',str(job)])
        state['phase']='MICRO32_CONTINUATION_RELEASED'
        state['released_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save(J,state)
print(json.dumps(dict(phase=state['phase'],rows=[dict(old_job=r['old']['job'],new_job=r['new_job'],
    node=r['old']['node'],configuration=r['configuration'],output=r['output']) for r in state['rows']],
    recovery_entries=state.get('recovery_entries'))))
