"""Narrow reuse of existing Alpha held sbatch/probe/proof chain, not a queue."""
import argparse,csv,io,json,os,socket,sys,time
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_cpu_queue_v1.probe import process
from . import contract as C

def job_identity(plan,sub,raw,held=False):
    j=Q.fields(raw);Q.need(j.get('JobId')==sub['job_id'] and j.get('UserId')=='alpha(1264)'
      and j.get('JobName')==plan['job_name'] and j.get('Partition')=='cpu' and j.get('NumCPUs')==str(plan['cpus'])
      and j.get('NumTasks')=='1' and j.get('Requeue')=='0' and j.get('WorkDir')==str(Q.ROOT)
      and j.get('Command')==sub['script_reference']['path'] and Q.duration(j.get('TimeLimit',''))==plan['wall_seconds'],'EXACT_OWN_CPU_PARENT')
    Q.need(not any('gpu' in str(j.get(k,'')).lower() for k in ('TRES','Gres','TresPerNode','TresPerTask')),'CPU_ONLY_ACTUAL_ALLOCATION')
    if held:Q.need(j.get('JobState')=='PENDING' and j.get('Reason')=='JobHeldUser' and j.get('Priority')=='0'
      and j.get('ReqNodeList')==plan['node'] and j.get('NumNodes') in ('1','1-1'),'EXACT_OWN_HELD_PARENT')
    else:Q.need(j.get('JobState')=='RUNNING' and j.get('NodeList')==plan['node'] and j.get('NumNodes')=='1','EXACT_OWN_RUNNING_PARENT')
    return j
def old_terminal():
    q=Q.query(['sacct','-X','-j','1885075,1885076','--format=JobIDRaw,UID,State,ExitCode,AllocCPUS,NodeList','-P'])
    rows={r['JobIDRaw']:r for r in csv.DictReader(io.StringIO(q['stdout']),delimiter='|')}
    Q.need(q['returncode']==0 and set(rows)=={'1885075','1885076'},'EXACT_OLD_PARENTS_ACTUAL_ACCOUNT')
    for spec in C.TAILS:
        r=rows[spec['parent']];Q.need(r['UID']=='1264' and r['State']=='FAILED' and r['ExitCode']=='3:0'
          and r['AllocCPUS']=='32' and r['NodeList']==spec['node'],'OLD_FAILED3_RETAINED')
    return q
def submit(plan_path):
    Q.login();plan=C.validate(Q.load(plan_path));C.review(plan);directory=Path(plan_path).parent
    Q.need(not C.INTENT.exists() and not any((directory/k).exists() for k in ('submission_intent.json','submission.json'))
      and not Path(plan['output_directory']).exists(),'NO_TAIL_INTENT_OR_UNKNOWN_SUBMISSION_RETRY')
    old=old_terminal();free=Q.free_cpus(plan);Q.need(free['free_cpus']>=plan['cpus'],'WAIT_REAL_FREE_CPU')
    storage=Q.effective_storage(Q.storage_observation(),plan['storage_scope_review_reference']['path'],plan['output_cap_bytes'])
    script=directory/'parent.sbatch';hours,rem=divmod(plan['wall_seconds'],3600);minutes,seconds=divmod(rem,60)
    text=f"""#!/bin/bash
#SBATCH --job-name={plan['job_name']}
#SBATCH --partition=cpu
#SBATCH --nodelist={plan['node']}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task={plan['cpus']}
#SBATCH --time={hours:02d}:{minutes:02d}:{seconds:02d}
#SBATCH --output={directory}/parent_%j.out
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH={Q.ROOT}/code
cd {Q.ROOT}
exec {plan['python']} -B -m {C.NAME}.gate --plan {plan_path}
"""
    with script.open('x') as f:f.write(text);f.flush();os.fsync(f.fileno())
    sub={'schema':'ALPHA_CONSUMED_TAIL_ACTUAL_SUBMISSION_V1','plan_reference':Q.ref(plan_path),'script_reference':Q.ref(script),
      'current_cpu_observation':free,'storage_observation':storage,'old_failed_parent_actual_query':old,
      'memory_limits_requested':False,'exclusive_requested':False,'status':'SUBMISSION_INTENT'}
    argv=['sbatch','--parsable','--hold','--no-requeue','--chdir='+str(Q.ROOT),str(script)]
    Q.write_new(directory/'submission_intent.json',{**sub,'argv':argv})
    q=Q.query(argv,timeout=45,allow_failure=True,env={k:v for k,v in os.environ.items() if not k.startswith('SBATCH_')})
    sub.update(returncode=q['returncode'],stdout=q['stdout'],stderr=q['stderr'],status='FAILED_NO_RETRY')
    if q['returncode']==0:
        jid=q['stdout'].strip().split(';')[0];Q.need(jid.isdecimal(),'UNKNOWN_ID_NO_RETRY');sub.update(job_id=jid,status='SUBMITTED_HELD')
    ref=Q.write_new(directory/'submission.json',sub);Q.need(q['returncode']==0,'SBATCH_FAILED_NO_RETRY')
    job_identity(plan,sub,Q.query(['scontrol','show','job',sub['job_id'],'--oneliner'])['stdout'],held=True);return ref
def probe(plan_path,jid,pid):
    plan=C.validate(Q.load(plan_path));Q.need(os.getuid()==1264 and socket.gethostname().split('.')[0]==plan['node'],'ACTUAL_ALPHA_TARGET')
    record=process(pid);env=record['selected_environment']
    Q.need(record['argv']==[plan['python'],'-B','-m',C.NAME+'.gate','--plan',plan_path]
      and env.get('SLURM_CPUS_PER_TASK')==str(plan['cpus']) and env.get('SLURM_JOB_ID')==jid
      and env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('CUDA_VISIBLE_DEVICES')=='','REAL_WAITING_PID_ENV_ARGV')
    if ('/job_'+jid+'/') not in record['cgroup'] and ('/job_'+jid+'\n') not in record['cgroup']:
        listing=Q.query(['scontrol','listpids',jid],emit=False)
        Q.need(sum(len(r)>=2 and r[0]==str(pid) and r[1]==jid for r in [s.split() for s in listing['stdout'].splitlines()])==1,'ACTUAL_PID_SLURM_MEMBERSHIP')
        record['actual_slurm_listpids_query']=listing
    return {'job_id':jid,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'observed_unix_seconds':time.time(),
      'plan_reference':Q.ref(plan_path),'parent_identity':record,'storage':Q.storage_observation(quiet=True)}
def observe(sub_path,seconds):
    Q.login();Q.need(type(seconds)is int and 1<=seconds<=90000,'FINITE_METADATA_OBSERVER')
    sub=Q.load(sub_path);Q.need(sub['status']=='SUBMITTED_HELD','SAME_ACTUAL_PARENT')
    plan=C.validate(Q.load_ref(sub['plan_reference']));C.review(plan);directory=Path(sub_path).parent;started=time.monotonic();jid=sub['job_id']
    while time.monotonic()-started<seconds:
        raw=Q.query(['scontrol','show','job',jid,'--oneliner'])['stdout'];j=Q.fields(raw)
        if j['JobState'] not in ('PENDING','RUNNING'):
            return {'job_id':jid,'state':j['JobState'],'no_retry':True}
        if j['JobState']=='PENDING':
            if not (directory/'release_intent.json').exists():
                job_identity(plan,sub,raw,held=True)
                if Q.free_cpus(plan)['free_cpus']<plan['cpus']:time.sleep(5);continue
                old_terminal();Q.effective_storage(Q.storage_observation(),plan['storage_scope_review_reference']['path'],plan['output_cap_bytes'])
                Q.write_new(directory/'release_intent.json',{'job_id':jid,'plan_reference':sub['plan_reference']});Q.query(['scontrol','release',jid])
            else:
                Q.need(j['JobId']==jid and j['UserId']=='alpha(1264)' and j['Command']==sub['script_reference']['path']
                  and j['NumCPUs']==str(plan['cpus']) and j['ReqNodeList']==plan['node'],'SAME_RELEASED_PENDING_PARENT')
            time.sleep(1);continue
        job_identity(plan,sub,raw)
        if not (directory/'started.json').exists():time.sleep(.5);continue
        ready=Q.load(directory/'started.json');pid=ready['actual_parent_identity']['pid']
        q=Q.query(['ssh','-n',plan['node'],'env','PYTHONPATH='+str(Q.ROOT/'code'),plan['python'],'-B','-m',C.NAME+'.resource',
          'probe','--plan',sub['plan_reference']['path'],'--job-id',jid,'--pid',str(pid)])
        target=json.loads(q['stdout']);Q.need(target['job_id']==jid and target['plan_reference']==sub['plan_reference']
          and 0<=time.time()-target['observed_unix_seconds']<=120,'FRESH_ACTUAL_TARGET_PROBE')
        storage=Q.effective_storage(target['storage'],plan['storage_scope_review_reference']['path'],plan['output_cap_bytes'])
        refs=C.merge(plan['source_references'],[sub['plan_reference'],plan['candidate_reference'],plan['root_review_reference']])
        for ref in refs:Q.verify(ref)
        proof={'schema':C.PROOF,'endpoint':Q.ENDPOINT,'uid':1264,'node':plan['node'],'cpus':plan['cpus'],'job_id':jid,
          'boot_id':target['boot_id'],'observed_unix_seconds':target['observed_unix_seconds'],'plan_reference':sub['plan_reference'],
          'parent_identity':target['parent_identity'],'controller_identity':Q.self_identity(),'job_metadata':raw,'submission':sub,
          'verified_source_references':refs,'storage_observation':storage,'memory_limits_requested':False,'exclusive_requested':False}
        ref=Q.write_new(plan['startup_proof_path'],proof);Q.write_new(directory/'proof.ready.json',{'job_id':jid,'proof_reference':ref});return ref
    return {'job_id':jid,'status':'FINITE_OBSERVER_ENDED_SAME_PARENT_NO_RETRY'}
def require_startup(plan_path,proof_path):
    plan=C.validate(Q.load(plan_path));C.review(plan);p=Q.load(proof_path);env=os.environ
    Q.need(p['schema']==C.PROOF and p['endpoint']==Q.ENDPOINT and p['uid']==os.getuid()==1264 and p['node']==plan['node']==socket.gethostname().split('.')[0]
      and p['cpus']==plan['cpus'] and p['plan_reference']==Q.ref(plan_path) and 0<=time.time()-p['observed_unix_seconds']<=120,'FRESH_EXACT_CPU_PROOF')
    Q.need(env.get('SLURM_JOB_ID')==p['job_id'] and env.get('SLURM_CPUS_PER_TASK')==str(plan['cpus'])
      and env.get('SLURM_JOB_PARTITION')=='cpu' and env.get('CUDA_VISIBLE_DEVICES')==''
      and all(env.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),'ACTUAL_CPU_THREADS_ONE')
    job_identity(plan,p['submission'],p['job_metadata']);Q.verify(p['submission']['script_reference'])
    actual=Q.self_identity()
    for k in ('pid','uid','start_ticks','pgid','sid','cgroup_sha256'):Q.need(actual[k]==p['parent_identity'][k],'SAME_EXEC_PARENT:'+k)
    Q.need(actual['boot_id']==p['boot_id'] and actual['argv']==plan['execution_argv']
      and Path(sys.modules['__main__'].__file__).absolute()==C.HERE/'run.py'
      and sys.argv==[str(C.HERE/'run.py'),*plan['execution_argv'][4:]],'EXACT_PRIMARY_SOURCE_AND_ARGV')
    Q.need(p['memory_limits_requested'] is p['exclusive_requested'] is False
      and p['controller_identity']['uid']==1264 and p['controller_identity']['hostname']=='sonmi','REAL_INDEPENDENT_LOGIN_PROOF')
    allowed={r['path']:r for r in p['verified_source_references']}
    for r in C.merge(plan['source_references'],[Q.ref(plan_path),plan['candidate_reference'],plan['root_review_reference']]):
        Q.need(allowed.get(r['path'])==r,'PINNED_SOURCE_AND_PLAN');Q.verify(r)
    Q.need(p['storage_observation']['whole_output_caps_reserved_bytes']>=plan['output_cap_bytes']
      and p['storage_observation']['effective_free_bytes']-p['storage_observation']['whole_output_caps_reserved_bytes']>=200000000000,'ALL_FUTURE_CAPS_PLUS200GB')
    import pyarrow
    from rdkit import rdBase
    Q.need(sys.version.split()[0]=='3.11.14' and pyarrow.__version__=='17.0.0' and rdBase.rdkitVersion=='2025.09.5','UNCHANGED_PYTHON_ARROW_RDKIT')
    return plan,p
def account(sub_path):
    Q.login();sub=Q.load(sub_path);plan=Q.load_ref(sub['plan_reference']);jid=sub['job_id']
    q=Q.query(['sacct','-X','-j',jid,'--format=JobIDRaw,UID,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList,Partition','-P'])
    rows=[r for r in csv.DictReader(io.StringIO(q['stdout']),delimiter='|') if r['JobIDRaw']==jid]
    Q.need(q['returncode']==0 and len(rows)==1 and rows[0]['UID']=='1264' and Q.state(rows[0]['State']) in {'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED'},'ACTUAL_TERMINAL_ACCOUNT_ONLY')
    p=rows[0];Q.need(p['NodeList']==plan['node'] and int(p['AllocCPUS'])==plan['cpus'] and p['Partition']=='cpu','SAME_REAL_PARENT_RESOURCE')
    directory=Path(sub_path).parent;tag=str(time.time_ns());raw=directory/('sacct_'+tag+'.txt')
    with raw.open('x') as f:f.write(q['stdout']);f.flush();os.fsync(f.fileno())
    return Q.write_new(directory/('accounting_'+tag+'.json'),{'schema':'ALPHA_TAIL_ACTUAL_PARENT_ACCOUNT_V1','endpoint':Q.ENDPOINT,'uid':1264,
      'actual_parent':p,'query_returncode':0,'query_argv':q.get('argv'),'raw_sacct_reference':Q.ref(raw),
      'allocated_core_seconds':int(p['ElapsedRaw'])*int(p['AllocCPUS']),'submission_reference':Q.ref(sub_path)})
def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('submit');a.add_argument('--plan',required=True)
    a=s.add_parser('observe');a.add_argument('--submission',required=True);a.add_argument('--max-seconds',type=int,default=90000)
    a=s.add_parser('probe');a.add_argument('--plan',required=True);a.add_argument('--job-id',required=True);a.add_argument('--pid',type=int,required=True)
    a=s.add_parser('account');a.add_argument('--submission',required=True);a=p.parse_args()
    result=submit(a.plan) if a.action=='submit' else observe(a.submission,a.max_seconds) if a.action=='observe' else probe(a.plan,a.job_id,a.pid) if a.action=='probe' else account(a.submission)
    print(Q.canonical(result).decode(),flush=True)
if __name__=='__main__':main()
