"""Queue the four prescribed view-inactive H2/H3 P/D trials behind current useful work."""
import copy,datetime,json,os,socket,subprocess
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
B=Path('/lfshome/zixiao/model_v31_20261105')
H=C/'HEADS_V3_20261113'
J=C/'MODEL_V3_HEADS_PD_QUEUE_20261113.json'
PY='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
APY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
WRAP=str(R/'tools/model_v3/v2_run_development.sbatch')
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-20'
os.chdir(R)
def run(argv):
 r=subprocess.run(argv,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(str(argv)+' '+r.stderr)
 return r.stdout.strip()
def save(path,value):
 path=Path(path);tmp=path.with_name(path.name+'.queue_next')
 tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)
assert not J.exists(),'Use the existing native queue journal, not duplicate submissions'
prior=json.loads((R/'results/model_v3_t1.json').read_text())
assert prior['provisional_latent']=='none' and len(prior['rows'])==10
templates={r['name']:r for r in json.loads((R/'configs/model_v3/followon_templates.json').read_text())['trials']}
native=run(['/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/cpu_git_tools_v1/bin/git','rev-parse','HEAD'])
state=dict(phase='PREPARING_REQUIRED_VIEW_INACTIVE_HEADS',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 selected_latent='none',views_metadata='three (inactive in pure P/D)',rows=[],no_new_scientific_candidates=True)
save(J,state)
chains=[('H2','compute-0-6','GPU-bdb3e139-15a8-755e-2e80-f2b8abaf66ef',4530290),
 ('H3','compute-0-0','GPU-a967b766-fb5e-8db3-b09c-4ddc6c02b332',4530281)]
for arm,node,gpu,predecessor in chains:
 for condition in ('P','D'):
  name=arm+'_'+condition+'_seed0';output=B/'HEADS_V3_20261113'/name
  assert not output.exists()
  cfg=copy.deepcopy(templates['M3_'+condition+'_'+arm+'_seed0']['configuration'])
  cfg.update(output=str(output),distance_bias='C1-0',views='three',condition=condition,
   stage='HEADS',arm=arm,latent='none',latent_spec=None,microbatch_size=32,code_tag='model-v3:'+native)
  cfg.pop('resume',None)
  cp=H/(name+'.json');save(cp,cfg)
  ep=H/(name+'_dev.json');ev=dict(checkpoint=str(output/'samples_6000000.pt'),
   output=str(output/'dev_eval_v2'),panel='v2',cache_root=str(B/'LATENT_V3_20261111/readout_cache'))
  save(ep,ev)
  row=dict(stage='HEADS',arm=arm,condition=condition,node=node,gpu=gpu,python=PY,mode='selected',
   configuration=str(cp),output=str(output),evaluation_configuration=str(ep),evaluation_output=ev['output'],
   restarts=0,taskbook_stage=5,execution_predecessor=predecessor,structural_views_scientifically_active=False)
  state['rows'].append(row);save(J,state)
  def submit(mode,configuration,dependencies,archive=False):
   argv=['sbatch','--hold','--parsable','--partition=all',
    '--nodelist='+('compute-0-20' if archive else node),'--cpus-per-task='+('1' if archive else '16'),
    '--time=0','--job-name=v3-'+('sdk-' if archive else 'dev-' if mode=='dev' else '')+arm+'-'+condition,
    '--dependency=afterok:'+':'.join(map(str,dependencies))]
   if archive:argv.append('--nice=10000')
   argv.extend([WRAP,mode,configuration,'none' if archive else gpu,APY if archive else PY])
   return int(run(argv).split(';')[0])
  row['job']=submit('selected',str(cp),[predecessor]);save(J,state)
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
  predecessor=row['evaluation_job']
plan=json.loads((H/'plan.json').read_text());plan['runs'].extend(state['rows'])
plan['queued_independent_P_D_complete']=True
plan['remaining_heads_matrix']='H1/P original C1-0 P6M reuse; H1/SDP actual winning C3 reuse; H2/SDP,H3/SDP await actual C3 views.'
save(H/'plan.json',plan)
rp=C/'MODEL_V3_latent_guard_recovery_20261111.json';rec=json.loads(rp.read_text())
for r in state['rows']:
 rec['jobs'].extend([dict(r),dict(job=r['evaluation_job'],node=r['node'],gpu=r['gpu'],python=PY,
  mode='dev',configuration=r['evaluation_configuration'],output=r['evaluation_output'],restarts=0,
  training_job=r['job'],stage='HEADS',arm=r['arm'],condition=r['condition']),
  dict(job=r['archive_job'],node='compute-0-20',gpu='none',python=APY,mode='archive_sdk',
  configuration=r['archive_configuration'],output=r['archive_output'],restarts=0,
  source_jobs=[r['job'],r['evaluation_job']],selection_use=False,cpus_per_task=1)])
save(rp,rec);state['recovery_entries']=len(rec['jobs']);state['phase']='REGISTERED_HELD';save(J,state)
for row in state['rows']:
 for key in ('job','evaluation_job','archive_job'):run(['scontrol','release',str(row[key])])
state['phase']='QUEUED_REQUIRED_VIEW_INACTIVE_HEADS_RELEASED';save(J,state)
print(json.dumps(dict(phase=state['phase'],recovery_entries=len(rec['jobs']),runs=[
 {k:r[k] for k in ('arm','condition','node','job','evaluation_job','archive_job','execution_predecessor')} for r in state['rows']])))
