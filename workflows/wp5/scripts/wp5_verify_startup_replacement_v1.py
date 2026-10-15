"""Bounded read-only scheduler verification of the approved actual replacements."""
import collections, hashlib, json, re, subprocess, time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
def run(argv):
    p=subprocess.run(argv,capture_output=True,text=True,stdin=subprocess.DEVNULL,timeout=60)
    return {'argv':argv,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
receipt=ROOT/'submission/startup_replacement_v1/submitted_jobs.json';stage=read(receipt)
assert stage['status']=='ALL_69_MAIN_4_CLEANUP_AND_2_DEPENDENCY_UPDATES_COMPLETE'
obs=read(ROOT/'reports/observation_latest.json');assert time.time()-obs['time']<180
checks=[];errors=[]
rows=stage['main']+stage['cleanup']+stage['existing_cleanup_dependency_updates']
for item in rows:
    jid=item['job_id'];raw=run(['scontrol','show','job','-o',jid])
    if raw['returncode']:
        checks.append({'job_id':jid,'raw':raw,'state':obs['registered_job_states'].get(jid)})
        errors.append('Missing current scheduler job '+jid);continue
    f=dict(re.findall(r'(\w+)=([^\s]+)',raw['stdout']))
    assert f['JobId']==jid
    problems=[]
    if f.get('UserId')!='zixiao(1278)':problems.append('user')
    if f.get('ReqNodeList')!=item['node']:problems.append('node')
    if f.get('NumCPUs')!='24' or f.get('CPUs/Task','24')!='24':problems.append('cpus')
    if f.get('MinMemoryNode')!='32G':problems.append('memory')
    if f.get('TimeLimit')!='2-00:00:00':problems.append('walltime')
    if f.get('Command')!='/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts/wp5_main_v11.sbatch':problems.append('script')
    dep=item.get('dependency')
    actualdep=f.get('Dependency','')
    expected=set(dep.split(':')[1:]) if dep else set()
    actual=set(re.findall(r'(\d+)\((?:un)?fulfilled\)',actualdep))
    missing=expected-actual
    unresolved=[j for j in missing if obs['registered_job_states'].get(j) not in {'COMPLETED','FAILED','CANCELLED','NODE_FAIL','PREEMPTED','BOOT_FAIL'}]
    if dep and (not actualdep.startswith('afterany:') or unresolved or actual-expected):problems.append('dependency')
    if f.get('Reason')=='JobHeldUser':problems.append('still_held')
    checks.append({'job_id':jid,'role':item.get('mode','cleanup'),'node':item['node'],'state':f.get('JobState'),
        'requested_dependency':dep,'actual_dependency':actualdep,'satisfied_dependencies_pruned':sorted(missing),
        'problems':problems,'raw':raw})
    errors.extend(jid+':'+p for p in problems)
result={'schema':'WP5_STARTUP_REPLACEMENT_SCHEDULER_VERIFICATION_V1','status':'PASS' if not errors else 'NOT_PASS',
    'time':time.time(),'submission':{'path':str(receipt),'sha256':digest(receipt)},
    'new_main_count':len(stage['main']),'new_cleanup_count':len(stage['cleanup']),
    'existing_cleanup_updates_count':len(stage['existing_cleanup_dependency_updates']),
    'preserved_original_main':stage['successful_original_main_jobs_preserved'],
    'state_counts':dict(collections.Counter(r.get('state') for r in checks)),'checks':checks,'errors':errors}
path=ROOT/'reports/startup_replacement_actual_scheduler_verification_v1.json'
path.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('status','new_main_count','new_cleanup_count','existing_cleanup_updates_count','state_counts','errors')}))
if errors:raise SystemExit(1)
