"""Queue prescribed H2/H3 SDP cells only after the actual complete C3 selection."""
import argparse,copy,datetime,json,os,socket,subprocess
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
B=Path('/lfshome/zixiao/model_v31_20261105')
H=C/'HEADS_V3_20261113'
J=C/'MODEL_V3_HEADS_SDP_QUEUE_20261113.json'
PY='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
APY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
WRAP=str(R/'tools/model_v3/v2_run_development.sbatch')
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-20'
os.chdir(R)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--completion-job',type=int)
args=parser.parse_args()
def run(argv):
 result=subprocess.run(argv,capture_output=True,text=True)
 if result.returncode:raise RuntimeError(str(argv)+' '+result.stderr)
 return result.stdout.strip()
def save(path,value):
 path=Path(path);tmp=path.with_name(path.name+'.heads_sdp_next')
 tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)
# A preserved partial submission requires coordinator recovery,never blind resubmission.
if J.exists():
 prior=json.loads(J.read_text())
 if prior['phase']=='QUEUED_REQUIRED_HEADS_SDP_RELEASED':
  print(json.dumps(dict(phase=prior['phase'],jobs=[r['job'] for r in prior['rows']])));raise SystemExit(0)
 raise RuntimeError('Retain existing SDP queue journal and recover its actual job handles')
decision_path=R/'results/model_v3_c3_views.json'
if not decision_path.exists():raise SystemExit(0)
decision=json.loads(decision_path.read_text())
if decision.get('status')!='CANDIDATE_GROUP_SELECTED' or decision.get('comparison')!='views':
 raise ValueError('Require the actual completed registered C3 comparison')
views=decision['selected']
if views not in ('two','three'):raise ValueError('No implicit view winner')
t1=json.loads((R/'results/model_v3_t1_panel_v3.json').read_text())
assert t1['provisional_latent']=='none' and len(t1['rows'])==10
c3=json.loads((C/'C3_VIEWS_20261113/plan.json').read_text())
assert c3['selected_C1']=='C1-0' and c3['selected_latent']=='none'
if not all((Path(row['evaluation_output'])/'producer_complete.json').exists() for row in c3['runs']):
 raise ValueError('All actual C3 evaluations must have completed')
winner=next(row for row in c3['runs'] if row['arm']==views and row['condition']=='SDP')
dependencies=[]
if args.completion_job is not None:
 assert args.completion_job in [row['evaluation_job'] for row in c3['runs']]
 actual=run(['scontrol','show','job','-o',str(args.completion_job)])
 assert 'UserId=zixiao(1278)' in actual and ('JobState=RUNNING' in actual or 'JobState=COMPLETED' in actual)
 dependencies=[args.completion_job]
heads=json.loads((H/'plan.json').read_text())
assert not any(row['condition']=='SDP' for row in heads['runs'])
templates={row['name']:row for row in json.loads((R/'configs/model_v3/followon_templates.json').read_text())['trials']}
native=run(['/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/cpu_git_tools_v1/bin/git','rev-parse','HEAD'])
specs=[('H2','compute-0-5','GPU-dac07d74-6269-c7db-8832-340dd3c0b377'),
       ('H3','compute-0-7','GPU-9db54192-dd3f-3177-e56f-dcd161ff932c')]
# Admission is on each actual future target; the existing wrapper rechecks at job start.
admission={}
for arm,node,gpu in specs:
 output=B/'HEADS_V3_20261113'/(arm+'_SDP_seed0')
 assert not output.exists()
 guard=run(['ssh','-n',node,'cd '+str(R)+' && '+PY+' -B tools/model_v3/v2_diagnosis_disk.py --once --output '+str(output)+' --node '+node+' --job 0 --state /dev/null'])
 admission[node]=dict(guard=json.loads(guard),
  mount=run(['ssh','-n',node,'findmnt -T /lfshome/zixiao']),
  bytes=run(['ssh','-n',node,'df -B1 / /lfshome/zixiao /share/home/zixiao/descriptor_analysis']),
  inodes=run(['ssh','-n',node,'df -Pi / /lfshome/zixiao /share/home/zixiao/descriptor_analysis']))
state=dict(phase='PREPARING_REQUIRED_SELECTED_VIEW_SDP_HEADS',
 created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),selected_C1='C1-0',
 selected_latent='none',selected_views=views,selection_source=str(decision_path),
 rows=[],admission=admission,original_files_retained=True,
 H1_P_reuse=dict(run_id='P_C1_0_seed0_micro32_continuation_20261110',
  checkpoint=str(B/'P_C1_0_seed0_micro32_continuation_20261110/samples_6000000.pt'),
  panel=str(B/'HEADS_V3_20261113/reused_H1_P_6M/dev_eval_v3/R3_summary.json'),scientific_samples=6000000,new_samples=0),
 H1_SDP_reuse=dict(job=winner['job'],checkpoint=str(Path(winner['output'])/'samples_6000000.pt'),
  panel=winner['evaluation_output']+'/R3_summary.json',scientific_samples=6000000,new_samples=0))
save(J,state)
for arm,node,gpu in specs:
 name=arm+'_SDP_seed0';output=B/'HEADS_V3_20261113'/name
 cfg=copy.deepcopy(templates['M3_SDP_'+arm+'_seed0']['configuration'])
 cfg.update(output=str(output),distance_bias='C1-0',views=views,condition='SDP',
  stage='HEADS',arm=arm,latent='none',latent_spec=None,microbatch_size=32,code_tag='model-v3:'+native)
 cfg.pop('resume',None)
 cp=H/(name+'.json');save(cp,cfg)
 ep=H/(name+'_dev.json');ev=dict(checkpoint=str(output/'samples_6000000.pt'),
  output=str(output/'dev_eval_v3'),panel='v3',evaluation_scope='forward',cache_root=str(B/'LATENT_V3_20261111/readout_cache'))
 save(ep,ev)
 row=dict(stage='HEADS',arm=arm,condition='SDP',node=node,gpu=gpu,python=PY,mode='selected',
  configuration=str(cp),output=str(output),evaluation_configuration=str(ep),evaluation_output=ev['output'],
  restarts=0,taskbook_stage=5,execution_predecessors=dependencies,
  structural_views_scientifically_active=True,selected_views=views)
 state['rows'].append(row);save(J,state)
 def submit(mode,configuration,parents,archive=False):
  argv=['sbatch','--hold','--parsable','--partition=all',
   '--nodelist='+('compute-0-20' if archive else node),'--cpus-per-task='+('1' if archive else '16'),
   '--time=0','--job-name=v3-'+('sdk-' if archive else 'dev-' if mode=='dev' else '')+arm+'-SDP']
  if parents:argv.append('--dependency=afterok:'+':'.join(map(str,parents)))
  if archive:argv.append('--nice=10000')
  argv.extend([WRAP,mode,configuration,'none' if archive else gpu,APY if archive else PY])
  return int(run(argv).split(';')[0])
 row['job']=submit('selected',str(cp),dependencies);save(J,state)
 row['evaluation_job']=submit('dev',str(ep),[row['job']]);save(J,state)
 source=H/(name+'_closed_sdk_sources.json')
 save(source,dict(schema='MODEL_V3_CLOSED_SDK_INPUTS_V1',tracking_root=str(B),runs=[
  dict(job=job,sdk_directories=[dict(path=str(Path(root)/'offline_wandb'/str(job)),marker='sdk_finished.json')])
  for job,root in ((row['job'],row['output']),(row['evaluation_job'],row['evaluation_output']))]))
 archive=H/(name+'_archive.json');archive_output=B/'WANDB_ARCHIVES_20261111'/(name+'_train_evaluation_closed')
 save(archive,dict(sources_manifest=str(source),jobs=[row['job'],row['evaluation_job']],
  output=str(archive_output),name=name+'_train_evaluation_offline_SDK_20261113'))
 row['archive_configuration']=str(archive);row['archive_output']=str(archive_output)
 row['archive_job']=submit('archive_sdk',str(archive),[row['job'],row['evaluation_job']],archive=True);save(J,state)
heads['runs'].extend(state['rows'])
heads.update(selected_views=views,view_selection_source=str(decision_path),
 H1_P_reuse=state['H1_P_reuse'],H1_SDP_reuse=state['H1_SDP_reuse'],
 remaining_heads_matrix='All prescribed independent P/D and selected-view SDP cells queued; H1/P and H1/SDP exactly reused.')
save(H/'plan.json',heads)
panels={'H1':dict(P=state['H1_P_reuse']['panel'],SDP=state['H1_SDP_reuse']['panel'])}
for row in heads['runs']:
 panels.setdefault(row['arm'],{})[row['condition']]=row['evaluation_output']+'/R3_summary.json'
save(H/'decision_manifest.json',dict(kind='candidate_set',group='H1 H2 H3 heads',comparison='heads',
 simplicity_order=['H1','H2','H3'],panels=panels,selection_source=str(decision_path),
 selected_latent='none',selected_views=views))
rp=C/'MODEL_V3_latent_guard_recovery_20261111.json';rec=json.loads(rp.read_text())
for row in state['rows']:
 rec['jobs'].extend([dict(row),dict(job=row['evaluation_job'],node=row['node'],gpu=row['gpu'],python=PY,
  mode='dev',configuration=row['evaluation_configuration'],output=row['evaluation_output'],
  restarts=0,training_job=row['job'],stage='HEADS',arm=row['arm'],condition='SDP'),
  dict(job=row['archive_job'],node='compute-0-20',gpu='none',python=APY,mode='archive_sdk',
  configuration=row['archive_configuration'],output=row['archive_output'],restarts=0,
  source_jobs=[row['job'],row['evaluation_job']],selection_use=False,cpus_per_task=1)])
save(rp,rec)
state['recovery_entries']=len(rec['jobs']);state['phase']='REGISTERED_HELD';save(J,state)
for row in state['rows']:
 for key in ('job','evaluation_job','archive_job'):run(['scontrol','release',str(row[key])])
state['phase']='QUEUED_REQUIRED_HEADS_SDP_RELEASED';save(J,state)
print(json.dumps(dict(phase=state['phase'],selected_views=views,recovery_entries=len(rec['jobs']),
 runs=[{k:row[k] for k in ('arm','condition','node','job','evaluation_job','archive_job')} for row in state['rows']])))
