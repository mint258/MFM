"""Queue only the requested cached T0-2 target revision,with original8CPU execution."""
import datetime,json,os,socket,subprocess
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
B=Path('/lfshome/zixiao/model_v31_20261105')
D=C/'RETROSPECTIVE_PANEL_V3_20261113'
J=C/'MODEL_V3_T0_2_PANEL_V3_QUEUE_20261113.json'
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-20'
os.chdir(R)
def read(p):return json.loads(Path(p).read_text())
def save(p,v):
 p=Path(p);temp=p.with_name(p.name+'.stats3_next')
 temp.write_text(json.dumps(v,indent=2)+'\n');temp.replace(p)
def run(a):return subprocess.check_output(a,text=True).strip()
assert not J.exists(),'Recover actual preserved handles;no blind resubmission'
cfg=read(C/'LATENT_V3_20261111/T0_2_configuration.json')
old=cfg['output']
cfg.update(output=str(B/'LATENT_V3_20261111/T0_2_four_statistics_panel_v3'),
 panel='v3',evaluation_scope='retrospective',reuse_four_statistics_output=old,device='cpu')
assert not Path(cfg['output']).exists()
guard=json.loads(run([PY,'-B','tools/model_v3/v2_diagnosis_disk.py','--once','--output',cfg['output'],
 '--node','compute-0-20','--job','0','--state','/dev/null']))
state=dict(phase='ACTUAL_CPU_NODE_ADMITTED',admission=guard,new_training_samples=0)
save(J,state)
cp=D/'T0_2_cached_panel_v3.json';save(cp,cfg)
wrap=str(R/'tools/model_v3/v2_run_development.sbatch')
def submit(mode,configuration,cpus,parent=None):
 a=['sbatch','--hold','--parsable','--partition=all','--nodelist=compute-0-20',
  '--cpus-per-task='+str(cpus),'--time=0','--nice=10000','--job-name=v3-'+mode+'-T0-2-panel3']
 if parent:a.append('--dependency=afterok:'+str(parent))
 a.extend([wrap,mode,str(configuration),'none',PY])
 return int(run(a).split(';')[0])
state['job']=submit('cached_pooling',cp,8);save(J,state)
sp=D/'T0_2_panel_v3_sdk_sources.json'
save(sp,dict(schema='MODEL_V3_CLOSED_SDK_INPUTS_V1',tracking_root=str(B),runs=[
 dict(job=state['job'],sdk_directories=[dict(path=str(Path(cfg['output'])/'offline_wandb'/str(state['job'])),
 marker='sdk_finished.json')])]))
ao=str(B/'WANDB_ARCHIVES_20261111/T0_2_four_statistics_panel_v3_closed')
ac=D/'T0_2_panel_v3_sdk_archive.json'
save(ac,dict(sources_manifest=str(sp),jobs=[state['job']],output=ao,name='T0_2_four_statistics_panel_v3'))
state['archive_job']=submit('archive_sdk',ac,1,state['job']);save(J,state)
plan=read(D/'plan.json')
plan.update(T0_2_output=cfg['output'],T0_2_four_statistics_reassessment='QUEUED_REAL_CPU8_JOB',
 T0_2_job=state['job'],T0_2_configuration=str(cp),T0_2_archive_job=state['archive_job'])
save(D/'plan.json',plan)
rp=C/'MODEL_V3_latent_guard_recovery_20261111.json';rec=read(rp)
rec['jobs'].extend([dict(job=state['job'],node='compute-0-20',gpu='none',python=PY,mode='cached_pooling',
 configuration=str(cp),output=cfg['output'],restarts=0,cpus_per_task=8,selection_use=False),
 dict(job=state['archive_job'],node='compute-0-20',gpu='none',python=PY,mode='archive_sdk',
 configuration=str(ac),output=ao,restarts=0,source_jobs=[state['job']],cpus_per_task=1,selection_use=False)])
save(rp,rec)
state.update(phase='REGISTERED_HELD',recovery_entries=len(rec['jobs']),configuration=str(cp));save(J,state)
for job in (state['job'],state['archive_job']):run(['scontrol','release',str(job)])
state['phase']='T0_2_PANEL_V3_CPU8_QUEUED';save(J,state)
print(json.dumps(state))
