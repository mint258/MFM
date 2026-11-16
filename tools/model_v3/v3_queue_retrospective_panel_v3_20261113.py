"""Register the user-requested historical panel-v3 readouts,with no new pretraining."""
import copy,datetime,json,os,socket,subprocess
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
B=Path('/lfshome/zixiao/model_v31_20261105')
D=C/'RETROSPECTIVE_PANEL_V3_20261113'
J=C/'MODEL_V3_RETROSPECTIVE_PANEL_V3_QUEUE_20261113.json'
PY='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
APY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
node='compute-0-6';gpu='GPU-bdb3e139-15a8-755e-2e80-f2b8abaf66ef'
WRAP=str(R/'tools/model_v3/v2_run_development.sbatch')
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-20'
os.chdir(R)
def read(p):return json.loads(Path(p).read_text())
def save(p,v):
 p=Path(p);tmp=p.with_name(p.name+'.retro_next')
 tmp.write_text(json.dumps(v,indent=2)+'\n');tmp.replace(p)
def run(a):
 r=subprocess.run(a,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(str(a)+' '+r.stderr)
 return r.stdout.strip()
assert not J.exists(),'Recover existing actual queue journal;never blindly resubmit'
scope=read(R/'configs/dev_panel_v3.json')['authority']['retrospective_scope']
assert scope=='REEVALUATE_C1_T0_T1'
hold_before={}
for job in (4530304,4530307,4530323):
 raw=run(['scontrol','show','job','-o',str(job)])
 assert 'UserId=zixiao(1278)' in raw and 'JobState=PENDING' in raw and 'RunTime=00:00:00' in raw
 hold_before[str(job)]=raw
specs=[]
for candidate in ('C1-a','C1-b'):
 for condition in ('S','P'):
  old=B/'DEV_PANEL_V2_20261111'/(candidate+'_'+condition+'_seed0')
  manifest=read(old/'predictions.json')
  specs.append(dict(stage='C1',arm=candidate,condition=condition,
   checkpoint=manifest['checkpoint'],reuse_predictions=str(old/'predictions.json'),
   output=str(B/'LATENT_V3_20261111/reevaluation_panel_v3'/(candidate+'_'+condition))))
original=read(C/'LATENT_V3_20261111/plan.json')
for old in sorted(original['runs'],key=lambda r:(r['stage'],r['arm'],r['condition'])):
 cfg=read(old['evaluation_configuration'])
 specs.append(dict(stage=old['stage'],arm=old['arm'],condition=old['condition'],
  checkpoint=cfg['checkpoint'],reuse_predictions=old['evaluation_output']+'/predictions.json',
  output=str(Path(old['output'])/'dev_eval_v3')))
assert len(specs)==18 and all(Path(s['checkpoint']).is_file() for s in specs)
assert all(not Path(s['output']).exists() for s in specs)
state=dict(phase='INPUTS_BOUND_BEFORE_SUBMISSION',at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 user_scope=scope,pretraining_samples_added=0,original_results_preserved=True,
 old_pretraining_to_hold=hold_before,rows=specs)
save(J,state)
D.mkdir()
budget_path=C/'model_output_budget.json';budget=read(budget_path)
save(D/'model_output_budget_before.json',budget)
budget['total_peak_bytes']+=2000000000
budget['retrospective_v3_additional_peak_bytes']=2000000000
budget['retrospective_v3_scope']='one global additional forecast,not per GPU'
save(budget_path,budget)
guard=run(['ssh','-n',node,'cd '+str(R)+' && '+PY+' -B tools/model_v3/v2_diagnosis_disk.py --once --output '+str(B/'LATENT_V3_20261111/reevaluation_panel_v3')+' --node '+node+' --job 0 --state /dev/null'])
state['admission']=json.loads(guard);save(J,state)
for job in hold_before:run(['scontrol','hold',job])
state['phase']='OLD_ZERO_WORK_FOLLOWON_TRAININGS_HELD';save(J,state)
predecessor=4530328
def submit(mode,configuration,parent,label,archive=False):
 args=['sbatch','--hold','--parsable','--partition=all',
  '--nodelist='+('compute-0-20' if archive else node),
  '--cpus-per-task='+('1' if archive else '16'),'--time=0',
  '--dependency=afterok:'+str(parent),'--job-name=v3-'+('sdk-' if archive else '')+'reval-'+label]
 if archive:args.append('--nice=10000')
 args.extend([WRAP,mode,str(configuration),'none' if archive else gpu,APY if archive else PY])
 return int(run(args).split(';')[0])
for row in specs:
 name=row['stage']+'_'+row['arm']+'_'+row['condition']
 cp=D/(name+'_dev.json')
 cfg={k:row[k] for k in ('checkpoint','output','condition','reuse_predictions')}
 cfg.update(panel='v3',evaluation_scope='retrospective',
  cache_root=str(B/'LATENT_V3_20261111/readout_cache'))
 save(cp,cfg);row['configuration']=str(cp)
 row['job']=submit('dev',cp,predecessor,name);row['execution_predecessor']=predecessor;save(J,state)
 predecessor=row['job']
 sp=D/(name+'_sdk_sources.json')
 save(sp,dict(schema='MODEL_V3_CLOSED_SDK_INPUTS_V1',tracking_root=str(B),runs=[
  dict(job=row['job'],sdk_directories=[dict(path=str(Path(row['output'])/'offline_wandb'/str(row['job'])),marker='sdk_finished.json')])]))
 ac=D/(name+'_sdk_archive.json');ao=str(B/'WANDB_ARCHIVES_20261111'/('REEVAL_V3_'+name))
 save(ac,dict(sources_manifest=str(sp),jobs=[row['job']],output=ao,name='REEVAL_V3_'+name))
 row.update(archive_configuration=str(ac),archive_output=ao)
 row['archive_job']=submit('archive_sdk',ac,row['job'],name,archive=True);save(J,state)
base=read(C/'FORWARD_PANEL_V3_20261113/plan.json')
c1zero=[dict(stage='C1',arm='C1-0',condition=r['condition'],checkpoint=r['checkpoint'],
 output=r['output'],configuration=r['configuration'],job=r['job'],archive_job=r['archive_job'])
 for r in base['runs']]
plan=dict(status='RETROSPECTIVE_V3_REGISTERED_HELD',panel='v3',
 runs=c1zero+specs,C1_order=['C1-0','C1-a','C1-b'],
 actual_new_evaluation_jobs=18,reused_already_queued_C1_zero_evaluations=2,
 source_C1_for_existing_T0_T1='C1-0',new_pretraining_samples=0,
 T0_2_four_statistics_reassessment='REQUIRED_SEPARATE_CACHED_CPU_CONFIGURATION',
 new_results=dict(C1=str(R/'results/model_v3_c1_panel_v3.json'),
  T0=str(R/'results/model_v3_t0_panel_v3.json'),T1=str(R/'results/model_v3_t1_panel_v3.json')),
 old_results_never_overwritten=True,held_followon_trainings=list(map(int,hold_before)))
save(D/'plan.json',plan)
rp=C/'MODEL_V3_latent_guard_recovery_20261111.json';rec=read(rp)
for row in specs:
 rec['jobs'].extend([dict(job=row['job'],node=node,gpu=gpu,python=PY,mode='dev',
  configuration=row['configuration'],output=row['output'],restarts=0,
  stage='RETROSPECTIVE_'+row['stage'],arm=row['arm'],condition=row['condition']),
  dict(job=row['archive_job'],node='compute-0-20',gpu='none',python=APY,mode='archive_sdk',
   configuration=row['archive_configuration'],output=row['archive_output'],restarts=0,
   source_jobs=[row['job']],selection_use=False,cpus_per_task=1)])
save(rp,rec);state.update(phase='ALL_ACTUAL_HANDLES_REGISTERED_HELD',recovery_entries=len(rec['jobs']));save(J,state)
for row in specs:
 run(['scontrol','release',str(row['job'])]);run(['scontrol','release',str(row['archive_job'])])
state['phase']='RETROSPECTIVE_V3_READOUT_QUEUE_RELEASED';save(J,state)
plan['status']=state['phase'];save(D/'plan.json',plan)
print(json.dumps(dict(phase=state['phase'],new_evaluation_jobs=[r['job'] for r in specs],
 recovery_entries=len(rec['jobs']),old_training_held=list(map(int,hold_before)),
 running_training_cancelled=False,new_pretraining_samples=0)))
