"""Replace zero-work administrator-held follow-on allocations; never touch running models."""
import copy,json,os,socket,subprocess
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/model_v31_20261105')
R=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3')
J=C/'MODEL_V3_C3_MICRO32_CONTINUATION_20261113.json'
P=C/'C3_VIEWS_20261113/plan.json'
WRAP=str(R/'tools/model_v3/v2_run_development.sbatch')
PY='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
APY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='compute-0-20'
os.chdir(R)
def run(argv):
 r=subprocess.run(argv,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(str(argv)+' '+r.stderr)
 return r.stdout.strip()
def save(path,value):
 path=Path(path);tmp=path.with_name(path.name+'.followon_next')
 tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)
def pending(job):
 raw=run(['scontrol','show','job','-o',str(job)])
 assert 'UserId=zixiao(1278)' in raw and 'JobState=PENDING' in raw and 'RunTime=00:00:00' in raw
 return raw
state=json.loads(J.read_text());plan=json.loads(P.read_text())
recpath=C/'MODEL_V3_latent_guard_recovery_20261111.json';rec=json.loads(recpath.read_text())
for row in state['rows']:
 old=row['old']
 for key in ('evaluation_job','archive_job'):pending(old[key])
 if 'replacement_evaluation_job' not in row:
  row['replacement_evaluation_job']=int(run(['sbatch','--hold','--parsable','--partition=all',
   '--nodelist='+old['node'],'--cpus-per-task=16','--time=0',
   '--dependency=afterok:'+str(row['new_job']),
   '--export=ALL,MODEL_V3_FOLLOWON_PLAN='+str(P),'--job-name=v3-dev-C3-'+old['arm']+'-micro32',
   WRAP,'dev',old['evaluation_configuration'],old['gpu'],PY]).split(';')[0])
  save(J,state)
 ev=row['replacement_evaluation_job']
 acpath=Path(old['archive_configuration']);ac=json.loads(acpath.read_text())
 sourcespath=Path(ac['sources_manifest']);sources=json.loads(sourcespath.read_text())
 for source in sources['runs']:
  if source['job']==old['evaluation_job']:
   source['job']=ev
   for d in source['sdk_directories']:d['path']=str(Path(d['path']).parent/str(ev))
 save(sourcespath,sources);ac['jobs']=[row['new_job'],ev];save(acpath,ac)
 if 'replacement_archive_job' not in row:
  row['replacement_archive_job']=int(run(['sbatch','--hold','--parsable','--partition=all',
   '--nodelist=compute-0-20','--cpus-per-task=1','--time=0','--nice=10000',
   '--dependency=afterok:'+str(row['new_job'])+':'+str(ev),
   '--job-name=v3-sdk-C3-'+old['arm']+'-micro32',WRAP,'archive_sdk',
   old['archive_configuration'],'none',APY]).split(';')[0])
  save(J,state)
 arc=row['replacement_archive_job']
 active=next(r for r in plan['runs'] if r['job']==row['new_job'])
 active.update(evaluation_job=ev,archive_job=arc,
  superseded_zero_work_followons=[old['evaluation_job'],old['archive_job']])
 for previous,new in ((old['evaluation_job'],ev),(old['archive_job'],arc)):
  entry=copy.deepcopy(next(r for r in rec['jobs'] if r['job']==previous))
  entry.update(job=new,restarts=0,superseded_zero_work_job=previous)
  if new==ev:entry['training_job']=row['new_job']
  else:
   entry['source_jobs']=[old['job'],row['new_job'],ev]
   entry['successful_dependency_jobs']=[row['new_job'],ev]
  if not any(r['job']==new for r in rec['jobs']):rec['jobs'].append(entry)
save(P,plan);save(recpath,rec)
for row in state['rows']:
 for key in ('evaluation_job','archive_job'):
  pending(row['old'][key]);run(['scancel',str(row['old'][key])])
 for key in ('replacement_evaluation_job','replacement_archive_job'):
  pending(row[key]);run(['scontrol','release',str(row[key])])
state['phase']='MICRO32_CONTINUATION_RELEASED'
state['followon_recovery']='Fresh immutable dependencies replace only four own zero-work JobHeldAdmin allocations'
state['recovery_entries']=len(rec['jobs']);save(J,state)
print(json.dumps(dict(phase=state['phase'],recovery_entries=len(rec['jobs']),rows=[
 dict(train=r['new_job'],evaluation=r['replacement_evaluation_job'],archive=r['replacement_archive_job']) for r in state['rows']])))
