"""Move only the zero-work prescribed H1 pooling cell to a freshly empty GPU."""
import copy,datetime,json,os,socket,subprocess
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
B=Path('/lfshome/zixiao/model_v31_20261105')
H=C/'HEADS_V3_20261113'
J=C/'MODEL_V3_POOLING_EMPTY_GPU_RELOCATION_20261113.json'
PLAN=H/'pooling_plan.json'
node='compute-0-21';gpu='GPU-c35f2434-9137-9723-1af5-dc69b6295243'
PY='/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'
APY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
WRAP=str(R/'tools/model_v3/v2_run_development.sbatch')
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-20'
os.chdir(R)
def run(argv):
 r=subprocess.run(argv,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(str(argv)+' '+r.stderr)
 return r.stdout.strip()
def save(path,value):
 path=Path(path);tmp=path.with_name(path.name+'.pool_relocate_next')
 tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)
def pending(job):
 raw=run(['scontrol','show','job','-o',str(job)])
 assert 'UserId=zixiao(1278)' in raw and 'JobState=PENDING' in raw and 'RunTime=00:00:00' in raw
 return raw
assert not J.exists(),'Recover the preserved actual relocation journal; never resubmit blindly'
plan=json.loads(PLAN.read_text());old=copy.deepcopy(plan['runs'][0])
assert old['job']==4530310 and old['arm']=='learned' and old['condition']=='P'
before={key:pending(old[key]) for key in ('job','evaluation_job','archive_job')}
assert not Path(old['output']).exists()
controller=run(['scontrol','show','node',node,'-o'])
import csv,re
assert int(re.search(r'\bCPUTot=(\d+)',controller)[1])-int(re.search(r'\bCPUAlloc=(\d+)',controller)[1])>=16
devices=run(['ssh','-n',node,'nvidia-smi --query-gpu=uuid,name,memory.total --format=csv,noheader,nounits'])
assert any(row[0].strip()==gpu and '5090' in row[1] and float(row[2])>=30000 for row in csv.reader(devices.splitlines()))
contexts=run(['ssh','-n',node,'nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv,noheader,nounits'])
assert not any(row and row[0].strip()==gpu for row in csv.reader(contexts.splitlines()))
guard=run(['ssh','-n',node,'cd '+str(R)+' && '+PY+' -B tools/model_v3/v2_diagnosis_disk.py --once --output '+old['output']+' --node '+node+' --job 0 --state /dev/null'])
memory=run(['ssh','-n',node,'head -3 /proc/meminfo'])
assert int(re.search(r'MemAvailable:\s+(\d+)',memory)[1])*1024>=64*1024**3+int(re.search(r'MemTotal:\s+(\d+)',memory)[1])*1024*.05
admission=dict(node=node,gpu=gpu,controller=controller,devices=devices,contexts=contexts,
 guard=json.loads(guard),bytes=run(['ssh','-n',node,'df -B1 / /lfshome/zixiao /share/home/zixiao/descriptor_analysis']),
 inodes=run(['ssh','-n',node,'df -Pi / /lfshome/zixiao /share/home/zixiao/descriptor_analysis']),
 mount=run(['ssh','-n',node,'findmnt -T /lfshome/zixiao']),memory=memory)
state=dict(phase='ADMITTED_BEFORE_ZERO_WORK_RELOCATION',
 created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 old=old,old_controller_before=before,admission=admission,
 science_changed=False,sample_budget=6000000,effective_batch=32,
 original_files_retained=True,no_data_transfer=True)
save(J,state)
save(H/'pooling_plan_original_node6_queued_20261113.json',plan)
row=copy.deepcopy(old)
row.update(node=node,gpu=gpu,python=PY,execution_predecessor=None,
 superseded_zero_work_jobs=[old[key] for key in ('job','evaluation_job','archive_job')],
 execution_reason='Freshly empty5090 lane; prescribed independent H1 pooling P6M,science unchanged')
for key in ('job','evaluation_job','archive_job'):row.pop(key,None)
state['new']=row;save(J,state)
def submit(mode,configuration,dependencies,archive=False):
 argv=['sbatch','--hold','--parsable','--partition=all',
  '--nodelist='+('compute-0-20' if archive else node),'--cpus-per-task='+('1' if archive else '16'),
  '--time=0','--job-name=v3-'+('sdk-' if archive else 'dev-' if mode=='dev' else '')+'H1-pool-P-free5090']
 if dependencies:argv.append('--dependency=afterok:'+':'.join(map(str,dependencies)))
 if archive:argv.append('--nice=10000')
 argv.extend([WRAP,mode,configuration,'none' if archive else gpu,APY if archive else PY])
 return int(run(argv).split(';')[0])
row['job']=submit('selected',row['configuration'],[]);save(J,state)
row['evaluation_job']=submit('dev',row['evaluation_configuration'],[row['job']]);save(J,state)
sources=H/'POOL_H1_learned_P_seed0_free5090_sources_20261113.json'
save(sources,dict(schema='MODEL_V3_CLOSED_SDK_INPUTS_V1',tracking_root=str(B),runs=[
 dict(job=job,sdk_directories=[dict(path=str(Path(root)/'offline_wandb'/str(job)),marker='sdk_finished.json')])
 for job,root in ((row['job'],row['output']),(row['evaluation_job'],row['evaluation_output']))]))
acfg=H/'POOL_H1_learned_P_seed0_free5090_archive_20261113.json'
save(acfg,dict(sources_manifest=str(sources),jobs=[row['job'],row['evaluation_job']],
 output=old['archive_output'],name='POOL_H1_learned_P_seed0_train_evaluation_offline_SDK_20261113'))
row['archive_configuration']=str(acfg)
row['archive_job']=submit('archive_sdk',str(acfg),[row['job'],row['evaluation_job']],archive=True);save(J,state)
rp=C/'MODEL_V3_latent_guard_recovery_20261111.json';rec=json.loads(rp.read_text())
rec['jobs'].extend([dict(row),dict(job=row['evaluation_job'],node=node,gpu=gpu,python=PY,
 mode='dev',configuration=row['evaluation_configuration'],output=row['evaluation_output'],
 restarts=0,training_job=row['job'],stage='POOLING',arm='learned',condition='P'),
 dict(job=row['archive_job'],node='compute-0-20',gpu='none',python=APY,mode='archive_sdk',
 configuration=str(acfg),output=row['archive_output'],restarts=0,
 source_jobs=[row['job'],row['evaluation_job']],selection_use=False,cpus_per_task=1)])
save(rp,rec)
plan['runs']=[row];plan['status']='REGISTERED_FREE_GPU_RELOCATION_HELD';save(PLAN,plan)
state['recovery_entries']=len(rec['jobs']);state['phase']='REGISTERED_REPLACEMENTS_HELD';save(J,state)
for key in ('job','evaluation_job','archive_job'):pending(old[key])
for key in ('job','evaluation_job','archive_job'):run(['scancel',str(old[key])])
for key in ('job','evaluation_job','archive_job'):run(['scontrol','release',str(row[key])])
state['phase']='RELEASED_REQUIRED_POOLING_ON_EMPTY_GPU';save(J,state)
plan['status']=state['phase'];save(PLAN,plan)
print(json.dumps(dict(phase=state['phase'],recovery_entries=len(rec['jobs']),
 jobs={key:row[key] for key in ('job','evaluation_job','archive_job')},node=node,gpu=gpu,
 science_changed=False,original_files_retained=True)))
