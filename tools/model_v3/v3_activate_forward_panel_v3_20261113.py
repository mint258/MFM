"""Apply requested forward atomization/SoM reporting only to zero-work evaluations."""
import copy,datetime,json,os,socket,subprocess
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
B=Path('/lfshome/zixiao/model_v31_20261105')
F=C/'FORWARD_PANEL_V3_20261113'
J=C/'MODEL_V3_FORWARD_PANEL_V3_ACTIVATION_20261113.json'
PY='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
APY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
node='compute-0-6';gpu='GPU-bdb3e139-15a8-755e-2e80-f2b8abaf66ef'
WRAP=str(R/'tools/model_v3/v2_run_development.sbatch')
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-20'
os.chdir(R)
def read(path):return json.loads(Path(path).read_text())
def save(path,value):
 path=Path(path);tmp=path.with_name(path.name+'.panel3_next')
 tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)
def run(argv):
 p=subprocess.run(argv,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(str(argv)+' '+p.stderr)
 return p.stdout.strip()
def pending(job):
 text=run(['scontrol','show','job','-o',str(job)])
 assert 'UserId=zixiao(1278)' in text and 'JobState=PENDING' in text and 'RunTime=00:00:00' in text
 return text
assert not J.exists(),'Recover the actual preserved activation journal,never resubmit blindly'
plans=[C/'C3_VIEWS_20261113/plan.json',C/'HEADS_V3_20261113/plan.json',
 C/'HEADS_V3_20261113/pooling_plan.json']
documents={str(path):read(path) for path in plans}
rows=[row for value in documents.values() for row in value['runs']]
assert len(rows)==9 and {row['evaluation_job'] for row in rows}=={4530281,4530294,4530296,4530290,4530305,4530308,4530321,4530324,4530316}
before={str(row[key]):pending(row[key]) for row in rows for key in ('evaluation_job','archive_job')}
assert all(not Path(row['evaluation_output']).exists() for row in rows)
# Baseline evaluation outputs remain under existing registered C3/HEADS roots.
baselines=[
 dict(condition='S',output=str(B/'C3_VIEWS_20261113/reused_three_S_6M/dev_eval_v3'),
  checkpoint='/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105/S_C1_0_seed0_v2/samples_6000000.pt',
  reuse_predictions=str(B/'DEV_PANEL_V2_20261111/C1-0_S_seed0/predictions.json')),
 dict(condition='P',output=str(B/'HEADS_V3_20261113/reused_H1_P_6M/dev_eval_v3'),
  checkpoint=str(B/'P_C1_0_seed0_micro32_continuation_20261110/samples_6000000.pt'),
  reuse_predictions=str(B/'DEV_PANEL_V2_20261111/C1-0_P_seed0/predictions.json'))]
admission=[]
for row in baselines:
 assert not Path(row['output']).exists()
 admission.append(json.loads(run(['ssh','-n',node,'cd '+str(R)+' && '+PY+' -B tools/model_v3/v2_diagnosis_disk.py --once --output '+row['output']+' --node '+node+' --job 0 --state /dev/null'])))
state=dict(phase='ADMITTED_BEFORE_FORWARD_EVALUATION_CHANGE',
 created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 authority='User20261113 explicitly requested U0 atomization and SoM report-only for current methods',
 retrospective_scope_pending=True,old_controller=before,admission=admission,
 old_plans=copy.deepcopy(documents),changed_files=[],baseline_runs=baselines,
 pretraining_configuration_changed=False,old_scientific_results_preserved=True)
save(J,state);F.mkdir();(F/'original').mkdir()
def snapshot(path):
 path=Path(path)
 name=str(path.relative_to(C)).replace('/','__')
 backup=F/'original'/name
 assert not backup.exists()
 backup.write_bytes(path.read_bytes())
 state['changed_files'].append(dict(path=str(path),backup=str(backup)));save(J,state)
def submit(mode,configuration,dependency,condition,archive=False):
 argv=['sbatch','--hold','--parsable','--partition=all',
  '--nodelist='+('compute-0-20' if archive else node),
  '--cpus-per-task='+('1' if archive else '16'),'--time=0',
  '--job-name=v3-'+('sdk-' if archive else '')+'forward-baseline-'+condition,
  '--dependency=afterok:'+str(dependency)]
 if archive:argv.append('--nice=10000')
 argv.extend([WRAP,mode,str(configuration),'none' if archive else gpu,APY if archive else PY])
 return int(run(argv).split(';')[0])
predecessor=4530290
for row in baselines:
 cfg=dict(checkpoint=row['checkpoint'],output=row['output'],panel='v3',evaluation_scope='forward',
  condition=row['condition'],reuse_predictions=row['reuse_predictions'],
  cache_root=str(B/'LATENT_V3_20261111/readout_cache'))
 cp=F/(row['condition']+'_baseline_dev.json');save(cp,cfg)
 row.update(configuration=str(cp),evaluation_output=row['output'],mode='dev',stage='FORWARD_BASELINE',
  arm='reused_C1_6M',node=node,gpu=gpu,python=PY,restated_original_training_samples=6000000,
  new_training_samples=0,selection_use='future C3/heads/pooling baseline only')
 row['job']=submit('dev',cp,predecessor,row['condition']);save(J,state)
 predecessor=row['job']
 sources=F/(row['condition']+'_baseline_sdk_sources.json')
 save(sources,dict(schema='MODEL_V3_CLOSED_SDK_INPUTS_V1',tracking_root=str(B),runs=[
  dict(job=row['job'],sdk_directories=[dict(path=str(Path(row['output'])/'offline_wandb'/str(row['job'])),marker='sdk_finished.json')])]))
 archive_output=str(B/'WANDB_ARCHIVES_20261111'/('FORWARD_BASELINE_'+row['condition']+'_v3_evaluation_closed'))
 acfg=F/(row['condition']+'_baseline_sdk_archive.json')
 save(acfg,dict(sources_manifest=str(sources),jobs=[row['job']],output=archive_output,
  name='FORWARD_BASELINE_'+row['condition']+'_panel_v3_evaluation'))
 row.update(archive_configuration=str(acfg),archive_output=archive_output)
 row['archive_job']=submit('archive_sdk',acfg,row['job'],row['condition'],archive=True);save(J,state)
eval_updates={}
for row in rows:
 old_output=row['evaluation_output'];new_output=str(Path(old_output).parent/'dev_eval_v3')
 assert not Path(new_output).exists()
 cp=Path(row['evaluation_configuration']);snapshot(cp);cfg=read(cp)
 cfg.update(output=new_output,panel='v3',evaluation_scope='forward',condition=row['condition'])
 save(cp,cfg);row['historical_v2_evaluation_output']=old_output;row['evaluation_output']=new_output
 eval_updates[row['evaluation_job']]=dict(old_output=old_output,new_output=new_output,training_job=row['job'])
 acfg=read(row['archive_configuration']);sp=Path(acfg['sources_manifest']);snapshot(sp);sources=read(sp)
 for run_row in sources['runs']:
  for sdk in run_row['sdk_directories']:
   if sdk['path'].startswith(old_output+'/'):sdk['path']=new_output+sdk['path'][len(old_output):]
 save(sp,sources)
c3=documents[str(plans[0])];heads=documents[str(plans[1])];pool=documents[str(plans[2])]
sbase,pbase=baselines
c3['reused_three_S'].update(historical_v2_panel=c3['reused_three_S']['panel'],
 panel=sbase['output']+'/R3_summary.json',forward_evaluation_job=sbase['job'])
heads['H1_P_reuse']=dict(run_id='original_C1_0_P_6M',output=str(Path(pbase['checkpoint']).parent),
 checkpoint=pbase['checkpoint'],panel=pbase['output']+'/R3_summary.json',
 scientific_samples=6000000,new_samples=0,forward_evaluation_job=pbase['job'])
for path in plans:
 snapshot(path);documents[str(path)].update(development_panel='v3',evaluation_scope='forward',
  historical_C1_T0_T1_reselection='WAITING_USER_SCOPE_REPLY')
 save(path,documents[str(path)])
manifest_path=C/'C3_VIEWS_20261113/decision_manifest.json';snapshot(manifest_path)
manifest=read(manifest_path)
manifest['panels']={'two':{},'three':{'S':sbase['output']+'/R3_summary.json'}}
for row in c3['runs']:manifest['panels'][row['arm']][row['condition']]=row['evaluation_output']+'/R3_summary.json'
manifest['panel']='v3';save(manifest_path,manifest)
manifest_path=C/'HEADS_V3_20261113/pooling_decision_manifest.json';snapshot(manifest_path)
manifest=read(manifest_path);manifest['panel']='v3'
manifest['panels']={'registry':{'P':pbase['output']+'/R3_summary.json'},
 'learned':{'P':pool['runs'][0]['evaluation_output']+'/R3_summary.json'}}
save(manifest_path,manifest)
recovery=C/'MODEL_V3_latent_guard_recovery_20261111.json';snapshot(recovery);rec=read(recovery)
for entry in rec['jobs']:
 if entry['job'] in eval_updates:entry['output']=eval_updates[entry['job']]['new_output']
 for row in rows:
  if entry['job']==row['job']:entry['evaluation_output']=row['evaluation_output']
for row in baselines:
 rec['jobs'].extend([dict(job=row['job'],node=node,gpu=gpu,python=PY,mode='dev',
  configuration=row['configuration'],output=row['output'],restarts=0,stage='FORWARD_BASELINE',condition=row['condition']),
  dict(job=row['archive_job'],node='compute-0-20',gpu='none',python=APY,mode='archive_sdk',
   configuration=row['archive_configuration'],output=row['archive_output'],restarts=0,
   source_jobs=[row['job']],selection_use=False,cpus_per_task=1)])
save(recovery,rec)
save(F/'plan.json',dict(status='FORWARD_PANEL_V3_BASELINES_HELD',runs=baselines,
 new_pretraining_samples=0,retrospective_selection_pending=True,panel='v3'))
state.update(phase='FORWARD_CONFIGURATIONS_REGISTERED_BASELINES_HELD',
 evaluation_updates=eval_updates,recovery_entries=len(rec['jobs']));save(J,state)
for row in baselines:
 run(['scontrol','release',str(row['job'])]);run(['scontrol','release',str(row['archive_job'])])
state['phase']='FORWARD_V3_EVALUATIONS_ACTIVE_BASELINES_QUEUED';save(J,state)
plan=read(F/'plan.json');plan['status']=state['phase'];save(F/'plan.json',plan)
print(json.dumps(dict(phase=state['phase'],zero_work_evaluations_updated=len(rows),
 baseline_evaluation_jobs=[row['job'] for row in baselines],
 baseline_archive_jobs=[row['archive_job'] for row in baselines],
 recovery_entries=len(rec['jobs']),new_pretraining_samples=0,retrospective_scope_pending=True)))
