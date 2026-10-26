"""Queue one held own CPU job while CPUs are occupied; release still requires actual16 free."""
import argparse,fcntl,os,subprocess
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.shared import ROOT,PROJECT,load,pin,read_small,on_login,query,now,quota_free,write_new
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import (need,validate_request,validate_bound_request,fields,job_identity)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path,required=True)
    p.add_argument('--keep-held',action='store_true');a=p.parse_args();on_login()
    req=load(a.request);validate_request(req,read_small=read_small);validate_bound_request(req,read_small=read_small)
    name=req['job_name'];receipt=ROOT/'control/submissions'/(name+'.json')
    intent=ROOT/'control/submissions'/(name+'.queue_intent.json')
    with (ROOT/'control/submissions/root.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        need(not receipt.exists() and not intent.exists(),'REGISTERED_OR_UNKNOWN_SUBMISSION_NO_RETRY')
        before=query(['squeue','-h','-u','zixiao','-o','%i|%j|%T|%N'])
        need(all(line.split('|')[1]!=name for line in before.splitlines()),'DUPLICATE_OWN_JOB_NAME')
        node_raw=query(['scontrol','show','node',req['node'],'--oneliner'])
        node=fields(node_raw)
        need(node.get('NodeName')==req['node'] and 'cpu' in node.get('Partitions','').split(','),'ACTUAL_CPU_PARTITION_NODE_REQUIRED')
        total,allocated=int(node['CPUTot']),int(node['CPUAlloc'])
        need(0<=allocated<=total,'VALID_ACTUAL_CPU_OBSERVATION_REQUIRED')
        cpu={'node':req['node'],'total_cpus':total,'allocated_cpus':allocated,'free_cpus':total-allocated,
             'raw':node_raw,'memory_admission_evaluated':False,'held_submission_may_wait_for_free_cpus':True,
             'actual16_free_required_before_release_by_unchanged_observer':True}
        quota=query(['quota','-v','-u','zixiao']);free=quota_free(quota)
        need(free-req['estimated_peak_output_bytes']>=200000000000,'WHOLE_CAP_PLUS_200GB_QUOTA_REQUIRED')
        argv=['sbatch','--parsable','--hold','--no-requeue','--chdir='+str(PROJECT)]
        if req.get('dependencies'):argv+=['--dependency=afterok:'+':'.join(req['dependencies'])]
        argv+=[req['script_reference']['path']]
        env={k:v for k,v in os.environ.items() if not k.startswith('SBATCH_')}
        row={'schema':'CPU_AUTO_MEMORY_SUBMISSION_V1','observed_at':now(),'uid':1278,
            'request_reference':pin(a.request),'request':req,'queue_before':before,'cpu_observation':cpu,
            'quota_raw':quota,'account_free_bytes':free,'memory_policy':req['memory_policy'],
            'memory_admission_evaluated':False,'removed_sbatch_environment_keys':sorted(set(os.environ)-set(env)),
            'submission_always_held':True,'other_jobs_modified':False,
            'submission_adapter_reference':pin(Path(__file__).absolute()),
            'queue_authority':'Existing user instruction: submit and wait if the node needs queuing; release/startup CPU checks remain unchanged.'}
        write_new(intent,row)
        try:r=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45,env=env)
        except subprocess.TimeoutExpired:
            row.update(sbatch_argv=argv,status='SUBMISSION_OUTCOME_UNKNOWN_NO_RETRY');write_new(receipt,row);raise
        row.update(sbatch_argv=argv,sbatch_returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
        if r.returncode==0:
            jid=r.stdout.strip().split(';')[0]
            if not jid.isdecimal():
                row.update(status='UNKNOWN_JOB_RESPONSE_NO_RETRY');write_new(receipt,row);raise ValueError('NO_ACTUAL_JOB_ID')
            row.update(job_id=jid,status='SUBMITTED_HELD_WAITING_NEW_OBSERVER')
        else:row.update(status='SUBMISSION_FAILED_NO_RETRY')
        write_new(receipt,row);need(r.returncode==0,'ACTUAL_SBATCH_REJECTED')
        raw=query(['scontrol','show','job',jid,'--oneliner']);job_identity(req,raw,job_id=jid,held=True)
        write_new(ROOT/'control/submissions'/(name+'.verification.json'),{
            'schema':'CPU_AUTO_MEMORY_HELD_VERIFICATION_V1','job_id':jid,'receipt_reference':pin(receipt),
            'held_readback':raw,'memory_fields_are_actual_scheduler_defaults_not_requested':True,
            'status':'EXACT_OWN_HELD_CPU_JOB_NOT_RELEASED'})
        print(__import__('json').dumps({'job_id':jid,'receipt':str(receipt),'status':'SUBMITTED_HELD_AWAITING_NEW_OBSERVER'}),flush=True)


if __name__=='__main__':main()
