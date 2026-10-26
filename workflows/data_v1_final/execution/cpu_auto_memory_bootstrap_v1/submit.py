"""Root prepares and submits only a finite no-data synthetic CPU bootstrap."""
import argparse,fcntl,os,pathlib,re,subprocess
from ..queue_v1.shared import ROOT,REPO,PROJECT,PY,load,pin,write_new,need,on_login,now,query,fields,uid,quota_free

def main():
    p=argparse.ArgumentParser();p.add_argument('--node',required=True);p.add_argument('--job-name',required=True);a=p.parse_args();on_login()
    authority_path=REPO/'configs/data_v1/user_cpu_auto_memory_20261026_v1.json';authority=load(authority_path)
    need(authority['schema']=='USER_AUTHORIZED_CPU_AUTO_MEMORY_DECISION_V1' and authority['status']=='USER_AUTHORIZED','LATEST_USER_RESOURCE_AUTHORITY')
    need(a.node.startswith('compute-0-') and int(a.node.rsplit('-',1)[1]) in authority['allowed_nodes']['analysis'] and re.fullmatch(r'dv1_q_[a-z0-9_]+',a.job_name),'SAFE_ALLOWED_CPU_NAME')
    rawnode=query(['scontrol','show','node',a.node,'--oneliner']);node=fields(rawnode)
    need('cpu' in node['Partitions'].split(',') and int(node['CPUTot'])-int(node['CPUAlloc'])>=16,'CURRENT_FREE_CPU16_REQUIRED')
    free=quota_free(query(['quota','-v','-u','zixiao']));need(free-(16<<20)>=200000000000,'QUOTA_RESERVE')
    stem=ROOT/'control/auto_mem_bootstrap'/a.job_name;context=stem.with_suffix('.context.json');script=stem.with_suffix('.sbatch');receipt=ROOT/'control/submissions'/(a.job_name+'.json');intent=ROOT/'control/submissions'/(a.job_name+'.queue_intent.json')
    for path in (context,script,receipt,intent):need(not path.exists(),'NEW_BOOTSTRAP_DESTINATION')
    source_paths=[*pathlib.Path(__file__).parent.glob('*.py')]
    for directory in ('execution/queue_v1','conformers/recovery_v1','pprime/queued_retention_v1','labels/source_status_v1'):
        source_paths.extend((REPO/'workflows/data_v1_final'/directory).glob('*.py'))
    source_paths += [REPO/'workflows/data_v1_final/pprime/retention_v1/prepare_cpu_queued_v2.py']
    refs=list({str(path):pin(path) for path in source_paths}.values());script.parent.mkdir(parents=True,exist_ok=True)
    text=f'''#!/bin/bash
#SBATCH --job-name={a.job_name}
#SBATCH --partition=cpu
#SBATCH --nodelist={a.node}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=00:10:00
#SBATCH --output={ROOT}/control/{a.job_name}_%j.out
set -euo pipefail
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH={REPO}:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
cd {PROJECT}
exec {PY} -B -m workflows.data_v1_final.execution.cpu_auto_memory_bootstrap_v1.run --context {context}
'''
    directives=[line for line in text.splitlines() if line.startswith('#SBATCH')]
    need(all(not any(word in line for word in ('--mem','--exclusive','--gres','--gpus','--oversubscribe','--overcommit')) for line in directives),'NO_MEMORY_OR_EXCLUSIVE_OR_GPU_DIRECTIVES')
    with script.open('x',encoding='utf-8') as f:f.write(text)
    c={'schema':'SOURCE_BOUND_CPU_NO_MEMORY_BOOTSTRAP_CONTEXT_V1','node':a.node,'job_name':a.job_name,'resource_authority':pin(authority_path),'source_references':refs+[pin(script)],'science_calls':0,'synthetic_test_cases':30};write_new(context,c)
    request={'schema':'CPU_AUTO_MEMORY_BOOTSTRAP_REQUEST_V1','kind':'analysis','pilot':True,'partition':'cpu','node':a.node,'job_name':a.job_name,'cpus':16,'wall_seconds':600,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','estimated_peak_output_bytes':16<<20,'resource_authority':pin(authority_path),'source_references':refs+[pin(context),pin(script)],'data_references':[],'execution_argv':[PY,'-B','-m','workflows.data_v1_final.execution.cpu_auto_memory_bootstrap_v1.run','--context',str(context)],'script_reference':pin(script),'scope_key':'auto_memory_original22_and_source_status8_synthetic','old_scientific_gates_unchanged':True}
    with (ROOT/'control/submissions/root.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        before=query(['squeue','-h','-u','zixiao','-o','%i|%j|%T']);need(all(line.split('|')[1]!=a.job_name for line in before.splitlines()),'UNIQUE_OWN_BOOTSTRAP_NAME')
        record={'schema':'CPU_AUTO_MEMORY_BOOTSTRAP_SUBMISSION_V1','uid':1278,'request':request,'observed_at':now(),'node_metadata_before':rawnode,'queue_before':before,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED'};write_new(intent,record)
        env={k:v for k,v in os.environ.items() if not k.startswith('SBATCH_')};argv=['sbatch','--parsable','--hold','--no-requeue','--chdir='+str(PROJECT),str(script)]
        r=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,env=env,timeout=45)
        record.update(sbatch_argv=argv,sbatch_returncode=r.returncode,stdout=r.stdout,stderr=r.stderr,removed_inherited_sbatch_keys=sorted(k for k in os.environ if k.startswith('SBATCH_')))
        if r.returncode==0:record['job_id']=r.stdout.strip().split(';')[0]
        write_new(receipt,record);need(r.returncode==0 and record['job_id'].isdecimal(),'ACTUAL_BOOTSTRAP_SUBMISSION_NO_RETRY')
        jid=record['job_id'];raw=query(['scontrol','show','job',jid,'--oneliner']);job=fields(raw)
        need(uid(job)==1278 and job['JobState']=='PENDING' and job['JobName']==a.job_name and job['ReqNodeList']==a.node and job['Partition']=='cpu' and job['NumCPUs']=='16' and job['Requeue']=='0' and job['Command']==str(script),'ACTUAL_OWN_CPU16_BOOTSTRAP_HELD_BINDING')
        release=query(['scontrol','release',jid]);after=query(['scontrol','show','job',jid,'--oneliner'])
        verified=stem.with_suffix('.activation.json');write_new(verified,{'schema':'ACTUAL_CPU_AUTO_MEMORY_BOOTSTRAP_RELEASE_V1','job_id':jid,'receipt':pin(receipt),'before':raw,'release_stdout':release,'after':after,'no_memory_directive':True,'no_exclusive_requested':True,'observed_at':now(),'other_jobs_modified':False})
    print({'job_id':jid,'node':a.node,'submission':pin(receipt),'activation':pin(verified),'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','science_calls':0})
if __name__=='__main__':main()