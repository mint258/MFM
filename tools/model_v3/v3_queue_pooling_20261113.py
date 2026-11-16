"""Queue only the prescribed H1 learned-pooling P cell; original registry P is reused."""
import copy,datetime,json,os,socket,subprocess
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
B=Path('/lfshome/zixiao/model_v31_20261105')
H=C/'HEADS_V3_20261113'
J=C/'MODEL_V3_POOLING_QUEUE_20261113.json'
PY='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
APY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
WRAP=str(R/'tools/model_v3/v2_run_development.sbatch')
node='compute-0-6'
gpu='GPU-bdb3e139-15a8-755e-2e80-f2b8abaf66ef'
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-20'
os.chdir(R)
def run(argv):
 r=subprocess.run(argv,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(str(argv)+' '+r.stderr)
 return r.stdout.strip()
def save(path,value):
 path=Path(path);tmp=path.with_name(path.name+'.pool_next')
 tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)
assert not J.exists(),'Use the existing queue journal; do not duplicate submissions'
t1=json.loads((R/'results/model_v3_t1.json').read_text())
assert t1['provisional_latent']=='none' and len(t1['rows'])==10
templates={r['name']:r for r in json.loads((R/'configs/model_v3/followon_templates.json').read_text())['trials']}
native=run(['/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025/cpu_git_tools_v1/bin/git','rev-parse','HEAD'])
name='POOL_H1_learned_P_seed0';output=B/'HEADS_V3_20261113'/name
assert not output.exists()
# The already registered common output root and original single100GB forecast cover this cell.
guard=run(['ssh','-n',node,'cd '+str(R)+' && '+PY+' -B tools/model_v3/v2_diagnosis_disk.py --once --output '+str(output)+' --node '+node+' --job 0 --state /dev/null'])
state=dict(phase='PREPARING_REQUIRED_H1_POOLING',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 selected_C1='C1-0',selected_latent='none',original_files_retained=True,science_changed=False,
 admission=json.loads(guard),rows=[],registry_reuse=dict(run_id='P_C1_0_seed0_micro32_continuation_20261110',
 checkpoint=str(B/'P_C1_0_seed0_micro32_continuation_20261110/samples_6000000.pt'),
 panel=str(B/'DEV_PANEL_V2_20261111/C1-0_P_seed0/R3_summary.json'),scientific_samples=6000000,new_samples=0))
save(J,state)
cfg=copy.deepcopy(templates['M3_P_pooling_learned_seed0']['configuration'])
cfg.update(output=str(output),distance_bias='C1-0',views='three',condition='P',
 stage='POOLING',arm='learned',latent='none',latent_spec=None,microbatch_size=32,code_tag='model-v3:'+native)
cfg.pop('resume',None)
cp=H/(name+'.json');save(cp,cfg)
ep=H/(name+'_dev.json');ev=dict(checkpoint=str(output/'samples_6000000.pt'),
 output=str(output/'dev_eval_v2'),panel='v2',cache_root=str(B/'LATENT_V3_20261111/readout_cache'))
save(ep,ev)
row=dict(stage='POOLING',arm='learned',condition='P',node=node,gpu=gpu,python=PY,mode='selected',
 configuration=str(cp),output=str(output),evaluation_configuration=str(ep),evaluation_output=ev['output'],
 restarts=0,taskbook_stage=5,execution_predecessor=4530302,structural_views_scientifically_active=False)
state['rows'].append(row);save(J,state)
def submit(mode,configuration,dependencies,archive=False):
 argv=['sbatch','--hold','--parsable','--partition=all',
  '--nodelist='+('compute-0-20' if archive else node),'--cpus-per-task='+('1' if archive else '16'),
  '--time=0','--job-name=v3-'+('sdk-' if archive else 'dev-' if mode=='dev' else '')+'H1-pool-learned-P',
  '--dependency=afterok:'+':'.join(map(str,dependencies))]
 if archive:argv.append('--nice=10000')
 argv.extend([WRAP,mode,configuration,'none' if archive else gpu,APY if archive else PY])
 return int(run(argv).split(';')[0])
row['job']=submit('selected',str(cp),[row['execution_predecessor']]);save(J,state)
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
plan=dict(status='REGISTERED_HELD',selected_C1='C1-0',selected_latent='none',runs=state['rows'],
 scientific_sample_budget=6000000,effective_batch_size=32,seed=0,registry_reuse=state['registry_reuse'],
 view_metadata='three, scientifically inactive in pure P; H1 fixed by original pooling experiment',
 decision_manifest=str(H/'pooling_decision_manifest.json'))
save(H/'pooling_plan.json',plan)
save(H/'pooling_decision_manifest.json',dict(kind='candidate_set',group='H1 P pooling',comparison='pooling',
 simplicity_order=['registry','learned'],panels=dict(
 registry=dict(P=state['registry_reuse']['panel']),learned=dict(P=str(output/'dev_eval_v2/R3_summary.json'))),
 selection_source=str(R/'results/model_v3_t1.json'),selected_latent='none'))
rp=C/'MODEL_V3_latent_guard_recovery_20261111.json';rec=json.loads(rp.read_text())
rec['jobs'].extend([dict(row),dict(job=row['evaluation_job'],node=node,gpu=gpu,python=PY,
 mode='dev',configuration=str(ep),output=ev['output'],restarts=0,training_job=row['job'],
 stage='POOLING',arm='learned',condition='P'),
 dict(job=row['archive_job'],node='compute-0-20',gpu='none',python=APY,mode='archive_sdk',
 configuration=str(archive),output=str(archive_output),restarts=0,
 source_jobs=[row['job'],row['evaluation_job']],selection_use=False,cpus_per_task=1)])
save(rp,rec)
h=json.loads((C/'MODEL_V3_HANDOFF_20261111.json').read_text())
h['active_development_plans'].append(str(H/'pooling_plan.json'));save(C/'MODEL_V3_HANDOFF_20261111.json',h)
state['recovery_entries']=len(rec['jobs']);state['phase']='REGISTERED_HELD';save(J,state)
for key in ('job','evaluation_job','archive_job'):run(['scontrol','release',str(row[key])])
state['phase']='QUEUED_REQUIRED_H1_POOLING_RELEASED';save(J,state)
plan['status']=state['phase'];save(H/'pooling_plan.json',plan)
print(json.dumps(dict(phase=state['phase'],recovery_entries=len(rec['jobs']),
 jobs={k:row[k] for k in ('job','evaluation_job','archive_job','execution_predecessor')},registry_reused=True)))
