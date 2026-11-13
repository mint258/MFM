"""Advance only both zero-work required H2 P/D cells to a freshly empty5090 lane."""
import copy,datetime,json,os,socket,subprocess,csv,re
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
B=Path('/lfshome/zixiao/model_v31_20261105')
H=C/'HEADS_V3_20261113'
J=C/'MODEL_V3_H2_EMPTY_GPU_RELOCATION_20261113.json'
PLAN=H/'plan.json'
node='compute-0-22';gpu='GPU-9b6008d0-35dd-4bff-f69a-0927b04b7eef'
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
 path=Path(path);tmp=path.with_name(path.name+'.h2_relocate_next')
 tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)
def pending(job):
 raw=run(['scontrol','show','job','-o',str(job)])
 assert 'UserId=zixiao(1278)' in raw and 'JobState=PENDING' in raw and 'RunTime=00:00:00' in raw
 return raw
assert not J.exists(),'Recover the preserved actual journal; never resubmit blindly'
plan=json.loads(PLAN.read_text())
original=[copy.deepcopy(row) for row in plan['runs'] if row['arm']=='H2']
assert len(original)==2 and {row['condition'] for row in original}=={'P','D'}
original.sort(key=lambda row:0 if row['condition']=='P' else 1)
assert [row['job'] for row in original]==[4530298,4530301]
old_jobs=[row[key] for row in original for key in ('job','evaluation_job','archive_job')]
before={str(job):pending(job) for job in old_jobs}
assert all(not Path(row['output']).exists() and not Path(row['evaluation_output']).exists() for row in original)
controller=run(['scontrol','show','node',node,'-o'])
assert int(re.search(r'\bCPUTot=(\d+)',controller)[1])-int(re.search(r'\bCPUAlloc=(\d+)',controller)[1])>=16
devices=run(['ssh','-n',node,'nvidia-smi --query-gpu=uuid,name,memory.total --format=csv,noheader,nounits'])
assert any(row[0].strip()==gpu and '5090' in row[1] and float(row[2])>=30000 for row in csv.reader(devices.splitlines()))
contexts=run(['ssh','-n',node,'nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv,noheader,nounits'])
assert not any(row and row[0].strip()==gpu for row in csv.reader(contexts.splitlines()))
guards=[]
for row in original:
 guards.append(json.loads(run(['ssh','-n',node,'cd '+str(R)+' && '+PY+' -B tools/model_v3/v2_diagnosis_disk.py --once --output '+row['output']+' --node '+node+' --job 0 --state /dev/null'])))
memory=run(['ssh','-n',node,'head -3 /proc/meminfo'])
assert int(re.search(r'MemAvailable:\s+(\d+)',memory)[1])*1024>=64*1024**3+int(re.search(r'MemTotal:\s+(\d+)',memory)[1])*1024*.05
admission=dict(node=node,gpu=gpu,controller=controller,devices=devices,contexts=contexts,
 guards=guards,bytes=run(['ssh','-n',node,'df -B1 / /lfshome/zixiao /share/home/zixiao/descriptor_analysis']),
 inodes=run(['ssh','-n',node,'df -Pi / /lfshome/zixiao /share/home/zixiao/descriptor_analysis']),
 mount=run(['ssh','-n',node,'findmnt -T /lfshome/zixiao']),memory=memory)
state=dict(phase='ADMITTED_BEFORE_ZERO_WORK_H2_RELOCATION',
 created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),old=original,
 old_controller_before=before,admission=admission,science_changed=False,
 sample_budget_each=6000000,effective_batch=32,original_files_retained=True,
 no_data_transfer=True,new=[])
save(J,state);save(H/'H2_plan_original_node6_queued_20261113.json',plan)
def submit(mode,configuration,dependencies,condition,archive=False):
 argv=['sbatch','--hold','--parsable','--partition=all',
  '--nodelist='+('compute-0-20' if archive else node),
  '--cpus-per-task='+('1' if archive else '16'),'--time=0',
  '--job-name=v3-'+('sdk-' if archive else 'dev-' if mode=='dev' else '')+'H2-'+condition+'-free5090']
 if dependencies:argv.append('--dependency=afterok:'+':'.join(map(str,dependencies)))
 if archive:argv.append('--nice=10000')
 argv.extend([WRAP,mode,configuration,'none' if archive else gpu,APY if archive else PY])
 return int(run(argv).split(';')[0])
predecessor=None
for old in original:
 row=copy.deepcopy(old);condition=row['condition']
 row.update(node=node,gpu=gpu,python=PY,execution_predecessor=predecessor,
  superseded_zero_work_jobs=[old[key] for key in ('job','evaluation_job','archive_job')],
  execution_reason='Freshly empty5090 lane; same prescribed H2 P/D6M cells and scientific outputs')
 for key in ('job','evaluation_job','archive_job'):row.pop(key,None)
 state['new'].append(row);save(J,state)
 row['job']=submit('selected',row['configuration'],[] if predecessor is None else [predecessor],condition);save(J,state)
 row['evaluation_job']=submit('dev',row['evaluation_configuration'],[row['job']],condition);save(J,state)
 sources=H/('H2_'+condition+'_seed0_free5090_sources_20261113.json')
 save(sources,dict(schema='MODEL_V3_CLOSED_SDK_INPUTS_V1',tracking_root=str(B),runs=[
  dict(job=job,sdk_directories=[dict(path=str(Path(root)/'offline_wandb'/str(job)),marker='sdk_finished.json')])
  for job,root in ((row['job'],row['output']),(row['evaluation_job'],row['evaluation_output']))]))
 acfg=H/('H2_'+condition+'_seed0_free5090_archive_20261113.json')
 save(acfg,dict(sources_manifest=str(sources),jobs=[row['job'],row['evaluation_job']],
  output=old['archive_output'],name='H2_'+condition+'_seed0_train_evaluation_offline_SDK_20261113'))
 row['archive_configuration']=str(acfg)
 row['archive_job']=submit('archive_sdk',str(acfg),[row['job'],row['evaluation_job']],condition,archive=True);save(J,state)
 predecessor=row['evaluation_job']
rp=C/'MODEL_V3_latent_guard_recovery_20261111.json';rec=json.loads(rp.read_text())
for row in state['new']:
 rec['jobs'].extend([dict(row),dict(job=row['evaluation_job'],node=node,gpu=gpu,python=PY,
  mode='dev',configuration=row['evaluation_configuration'],output=row['evaluation_output'],
  restarts=0,training_job=row['job'],stage='HEADS',arm='H2',condition=row['condition']),
  dict(job=row['archive_job'],node='compute-0-20',gpu='none',python=APY,mode='archive_sdk',
   configuration=row['archive_configuration'],output=row['archive_output'],restarts=0,
   source_jobs=[row['job'],row['evaluation_job']],selection_use=False,cpus_per_task=1)])
save(rp,rec)
replacement={row['condition']:row for row in state['new']}
plan['runs']=[replacement[row['condition']] if row['arm']=='H2' else row for row in plan['runs']]
plan['status']='REGISTERED_H2_FREE_GPU_RELOCATION_HELD';save(PLAN,plan)
state['recovery_entries']=len(rec['jobs']);state['phase']='REGISTERED_REPLACEMENTS_HELD';save(J,state)
for job in old_jobs:pending(job)
for job in old_jobs:run(['scancel',str(job)])
for row in state['new']:
 for key in ('job','evaluation_job','archive_job'):run(['scontrol','release',str(row[key])])
state['phase']='RELEASED_REQUIRED_H2_P_D_ON_EMPTY_GPU';save(J,state)
plan['status']=state['phase'];save(PLAN,plan)
print(json.dumps(dict(phase=state['phase'],recovery_entries=len(rec['jobs']),
 jobs=[{key:row[key] for key in ('condition','job','evaluation_job','archive_job')} for row in state['new']],
 node=node,gpu=gpu,science_changed=False,original_files_retained=True)))
