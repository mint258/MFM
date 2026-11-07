"""Thin single-parent submit/observe/proof; no chemistry, old16 gate or epoch."""
import argparse,fcntl,json,os,socket,subprocess,sys,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from . import contracts as C
fields=Q.fields;duration=Q.duration;ROOT=Q.ROOT;need=Q.need

def job_identity(request,raw,jid,*,held=False):
    job=fields(raw)
    need(job.get('JobId')==str(jid) and job.get('UserId')=='alpha(1264)' and job.get('JobName')==request['job_name'] and
         job.get('Partition')=='cpu' and job.get('NumCPUs')=='32' and job.get('NumTasks')=='1' and job.get('Requeue')=='0' and
         job.get('Command')==request['script_reference']['path'] and job.get('WorkDir')==str(ROOT) and
         duration(job.get('TimeLimit',''))==request['wall_seconds'],'EXACT_OWN_ALPHA_JOB_SCRIPT_CPU_WALL_REQUIRED')
    if held:
        need(job.get('JobState')=='PENDING' and job.get('Reason')=='JobHeldUser' and job.get('Priority')=='0' and
             job.get('ReqNodeList')==request['node'] and job.get('NumNodes') in {'1','1-1'},'EXACT_OWN_HELD_ALPHA_JOB_REQUIRED')
    else:
        need(job.get('JobState')=='RUNNING' and job.get('NodeList')==request['node'] and job.get('NumNodes')=='1','EXACT_OWN_RUNNING_ALPHA_JOB_REQUIRED')
    return job



def request_shape(r):
    Q.need(r['kind']=='analysis' and r['pilot'] is False and type(r['cpus'])is int and r['cpus']==32
      and r['memory_policy']==Q.POLICY and type(r['wall_seconds'])is int and r['wall_seconds']==86400
      and type(r['execution_argv'])is list and len(r['execution_argv'])==8 and r['execution_argv'][2:4]==['-m',C.MODULE],
      'REAL32_EXACT_DAY_PARENT_NOT_OLD16_OR_ARBITRARY_PRIMARY')
    return r

def require_startup(plan_path,proof_path):
    plan=C.validate(Q.load(plan_path));C.parent_review(plan);proof=Q.load(proof_path);Q.need(proof['schema']==C.PROOF and proof['endpoint']==Q.ENDPOINT and proof['uid']==os.getuid()==1264
      and proof['node']==plan['node']==socket.gethostname().split('.')[0] and proof['plan_reference']==Q.ref(plan_path)
      and proof['root_parent_review_reference']==plan['root_parent_review_reference'] and 0<=time.time()-proof['observed_unix_seconds']<=120,'FRESH_TRUE_ALPHA32_DAY_PROOF')
    request_shape(proof['request'])
    Q.need(proof['request']=={'kind':'analysis','pilot':False,'cpus':32,'memory_policy':Q.POLICY,'wall_seconds':86400,'execution_argv':plan['execution_argv']}
      and proof['memory_limits_requested'] is False and proof['exclusive_requested'] is False,'NO_OLD16_PROOF_OR_MEMORY_MASQUERADE')
    env=os.environ;Q.need(env.get('SLURM_JOB_ID')==str(proof['job_id']) and env.get('SLURM_CPUS_PER_TASK')=='32'
      and env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('CUDA_VISIBLE_DEVICES')==''
      and all(env.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'ACTUAL32_CPU_LIBRARY_THREADS_ONE')
    job_identity(proof['submission'],proof['job_metadata'],proof['job_id'])
    j=Q.fields(proof['job_metadata']);Q.need(not any('gpu' in str(j.get(k,'')).lower() for k in ('TRES','Gres','TresPerNode','TresPerTask')),'NO_ACTUAL_GPU_ALLOCATION')
    Q.need(Q.ref(proof['submission']['script_reference']['path'])==proof['submission']['script_reference'],'ACTUAL_SUBMITTED_SCRIPT_SOURCE_SHA')
    actual=Q.self_identity();old=proof['parent_identity']
    for key in ('pid','uid','start_ticks','pgid','sid','cgroup_sha256'):
        Q.need(actual[key]==old[key],'SAME_REAL_PARENT_EXEC:'+key)
    Q.need(actual['boot_id']==proof['boot_id'] and actual['argv']==plan['execution_argv']
      and Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py' and sys.argv==[str(C.HERE/'run.py'),*plan['execution_argv'][4:]],'EXACT_REAL_PRIMARY_SOURCE_AND_ALL_OS_ARGV')
    allowed={r['path']:r for r in proof['verified_source_references']}
    for r in [*plan['source_references'],Q.ref(plan_path)]:Q.need(allowed.get(r['path'])==r,'ACTUAL_TARGET_SOURCE_PIN');Q.verify(r)
    Q.need(proof['controller_identity']['uid']==1264 and proof['controller_identity']['hostname']=='sonmi'
      and proof['storage_observation']['whole_output_caps_reserved_bytes']>=plan['output_cap_bytes']
      and proof['storage_observation']['effective_free_bytes']-proof['storage_observation']['whole_output_caps_reserved_bytes']>=200000000000,'INDEPENDENT_LOGIN_AND_REAL_CURRENT_WHOLE_CAP_STORAGE')
    import pyarrow
    from rdkit import rdBase
    Q.need(sys.version.split()[0]=='3.11.14' and pyarrow.__version__=='17.0.0' and rdBase.rdkitVersion=='2025.09.5','EXACT_ORIGINAL_ALPHA_PYTHON_ARROW_RDKIT')
    return plan,proof

def submit(plan_path):
    Q.login();plan=C.validate(Q.load(plan_path));C.parent_review(plan);directory=Path(plan_path).parent;Q.need(not (directory/'submission.json').exists() and not (directory/'submission_intent.json').exists(),'ONE_OR_UNKNOWN_NO_RESUBMIT')
    free=Q.free_cpus(plan);Q.need(free['free_cpus']>=32,'WAIT_ACTUAL32_FREE_CPU')
    observation=Q.storage_observation();storage=Q.effective_storage(observation,plan['storage_scope_review_reference']['path'],plan['output_cap_bytes'])
    script=directory/'parent.sbatch';text=f'''#!/bin/bash
#SBATCH --job-name={plan['job_name']}
#SBATCH --partition=cpu
#SBATCH --nodelist={plan['node']}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --time=24:00:00
#SBATCH --output={directory}/parent_%j.out
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH={Q.ROOT}/code
cd {Q.ROOT}
exec {plan['python']} -B -m secondary_pubchem_packed_day_alpha_v1.gate --plan {plan_path}
'''
    with script.open('x') as f:f.write(text);f.flush();os.fsync(f.fileno())
    r={'schema':'ALPHA_ONE_DAY32_PARENT_SUBMISSION_V1','plan_reference':Q.ref(plan_path),'node':plan['node'],'job_name':plan['job_name'],
      'wall_seconds':86400,'script_reference':Q.ref(script),'memory_limits_requested':False,'exclusive_requested':False,
      'current_cpu_observation':free,'storage_observation':storage,'source_or_other_jobs_modified':False}
    argv=['sbatch','--parsable','--hold','--no-requeue','--chdir='+str(Q.ROOT),str(script)];Q.write_new(directory/'submission_intent.json',{**r,'argv':argv})
    result=Q.query(argv,timeout=45,allow_failure=True,env={k:v for k,v in os.environ.items() if not k.startswith('SBATCH_')})
    r.update(returncode=result['returncode'],stdout=result['stdout'],stderr=result['stderr'],status='SUBMITTED_HELD' if result['returncode']==0 else 'FAILED_NO_RETRY')
    if result['returncode']==0:
        r['job_id']=result['stdout'].strip().split(';')[0]
        if not r['job_id'].isdecimal():
            Q.write_new(directory/'submission.json',{**r,'status':'UNKNOWN_ID_NO_RETRY'});raise ValueError('UNKNOWN_ID_NO_RETRY')
    ref=Q.write_new(directory/'submission.json',r);Q.need(result['returncode']==0,'SBATCH_FAILED_NO_RETRY')
    job_identity(r,Q.query(['scontrol','show','job',r['job_id'],'--oneliner'])['stdout'],r['job_id'],held=True);return ref

def observe(submission_path,seconds):
    Q.login();Q.need(type(seconds)is int and 1<=seconds<=90000,'FINITE_ROOT_METADATA_OBSERVER_ONLY')
    sub=Q.load(submission_path);Q.need(sub['status']=='SUBMITTED_HELD','EXACT_ACTUAL_HELD_PARENT');plan=C.validate(Q.load_ref(sub['plan_reference']));C.parent_review(plan);jid=sub['job_id'];directory=Path(submission_path).parent;started=time.monotonic()
    while time.monotonic()-started<seconds:
        raw=Q.query(['scontrol','show','job',jid,'--oneliner'])['stdout'];state=Q.fields(raw)['JobState']
        if state not in ('PENDING','RUNNING'):return Q.write_new(directory/'observer_terminal.json',{'job_id':jid,'state':state,'metadata':raw,'no_auto_retry':True})
        if state=='PENDING':
            if (directory/'release_intent.json').exists():
                j=Q.fields(raw);Q.need(j['JobId']==jid and j['UserId']=='alpha(1264)' and j['JobName']==plan['job_name'] and j['NumCPUs']=='32'
                  and j['Partition']=='cpu' and j['Command']==sub['script_reference']['path'] and j['ReqNodeList']==plan['node'],'SAME_ALREADY_RELEASED_PENDING_PARENT')
                time.sleep(5);continue
            job_identity(sub,raw,jid,held=True)
            if Q.free_cpus(plan)['free_cpus']<32:time.sleep(5);continue
            Q.effective_storage(Q.storage_observation(),plan['storage_scope_review_reference']['path'],plan['output_cap_bytes'])
            Q.need(not (directory/'release_intent.json').exists(),'NO_REPEATED_RELEASE_OR_UNKNOWN_OUTCOME');Q.write_new(directory/'release_intent.json',{'job_id':jid,'plan_reference':sub['plan_reference']})
            Q.query(['scontrol','release',jid])
        else:
            job_identity(sub,raw,jid)
            if not (directory/'started.json').exists():time.sleep(1);continue
            ready=Q.load(directory/'started.json');pid=ready['actual_parent_identity']['pid']
            response=Q.query(['ssh','-n',plan['node'],'env','PYTHONPATH='+str(Q.ROOT/'code'),plan['python'],'-B','-m','secondary_pubchem_packed_day_alpha_v1.probe','--plan',sub['plan_reference']['path'],'--job-id',jid,'--pid',str(pid)])
            observed=json.loads(response['stdout']);Q.need(observed['job_id']==jid and observed['plan_reference']==sub['plan_reference'] and 0<=time.time()-observed['observed_unix_seconds']<=120,'ACTUAL_FRESH32_TARGET_PROBE')
            storage=Q.effective_storage(observed['storage'],plan['storage_scope_review_reference']['path'],plan['output_cap_bytes'])
            verified=[*plan['source_references'],sub['plan_reference']]
            for r in verified:Q.verify(r)
            proof={'schema':C.PROOF,'endpoint':Q.ENDPOINT,'uid':1264,'node':plan['node'],'boot_id':observed['boot_id'],'job_id':jid,
              'observed_unix_seconds':observed['observed_unix_seconds'],'request':{'kind':'analysis','pilot':False,'cpus':32,'memory_policy':Q.POLICY,'wall_seconds':86400,'execution_argv':plan['execution_argv']},
              'plan_reference':sub['plan_reference'],'root_parent_review_reference':plan['root_parent_review_reference'],'parent_identity':observed['parent_identity'],
              'controller_identity':Q.self_identity(),'job_metadata':raw,'submission':sub,'verified_source_references':verified,'memory_limits_requested':False,
              'exclusive_requested':False,'storage_observation':storage,'actual_source_index_hash_claimed_by_controller':False,'no_fake_child_Slurm_C0':True}
            ref=Q.write_new(plan['startup_proof_path'],proof);Q.write_new(directory/'proof.ready.json',{'job_id':jid,'proof_reference':ref});return ref
        time.sleep(1)
    return Q.write_new(directory/'observer_ended.json',{'job_id':jid,'no_auto_renewal':True,'no_jobs_signaled':True})

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('submit');a.add_argument('--plan',required=True)
    a=s.add_parser('observe');a.add_argument('--submission',required=True);a.add_argument('--max-seconds',type=int,default=90000);a=p.parse_args()
    print(submit(a.plan) if a.action=='submit' else observe(a.submission,a.max_seconds))
if __name__=='__main__':main()
