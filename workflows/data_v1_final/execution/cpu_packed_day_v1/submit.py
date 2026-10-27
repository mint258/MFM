"""One held submission only; no automatic requeue/retry/child sbatch."""
import argparse,os,subprocess
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.registry import lock_file
from . import contract as C
Q=C.Q

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path,required=True);a=p.parse_args();Q.on_login()
    r=Q.load(a.request);C.validate(r);root=Path(r['startup_proof_path']).parent
    with lock_file(C.BASE/'packed_submit.lock'):
        C.need(not (root/'submission_intent.json').exists() and not (root/'submission.json').exists(),'ONE_SUBMISSION_OR_UNKNOWN_NO_RETRY')
        before=Q.query(['squeue','-h','-u','zixiao','-o','%i|%j|%T|%N']);C.need(all(line.split('|')[1]!=r['job_name'] for line in before.splitlines()),'NO_DUPLICATE_PACKED_PARENT')
        cpu=C.free_cpu(r,Q.query(['scontrol','show','node',r['node'],'--oneliner']));carve,review,_=C.resources(r,lease=True)
        from .observe import quota as actual_provider
        actual_provider(r,lease=True)
        quota=Q.query(['quota','-v','-u','zixiao'])
        free=C.Provider.parse_quota({'argv':C.Provider.QUOTA_ARGV,'returncode':0,'stderr':'','stdout':quota,'raw_output_complete':True},review['login_quota_device'])['free_bytes']
        C.need(free-carve['total_future_reserved_bytes']>=C.RESERVE,'CURRENT_FUTURE_ONCE_PLUS200GB_NOT_OLD182_AGAIN')
        argv=['sbatch','--parsable','--hold','--no-requeue','--chdir='+str(Q.PROJECT),r['script_reference']['path']]
        env={k:v for k,v in os.environ.items() if not k.startswith('SBATCH_')}
        row={'schema':'CPU_PACKED_DAY_SUBMISSION_V1','request_reference':Q.pin(a.request),'request':r,'cpu_observation':cpu,
            'quota_raw':quota,'account_free_bytes':free,'observed_at':Q.now(),'sbatch_argv':argv,'old_jobs_modified':False,'one_parent_only':True}
        Q.write_new(root/'submission_intent.json',row)
        try:result=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45,env=env)
        except subprocess.TimeoutExpired:
            Q.write_new(root/'submission.json',{**row,'status':'UNKNOWN_SUBMISSION_NO_RETRY'});raise
        row.update(returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,status='SUBMITTED_HELD' if result.returncode==0 else 'FAILED_NO_RETRY')
        if result.returncode==0:
            row['job_id']=result.stdout.strip().split(';')[0]
            if not row['job_id'].isdecimal():
                row['status']='UNKNOWN_SBATCH_ID_NO_RETRY';Q.write_new(root/'submission.json',row);raise ValueError(row['status'])
        ref=Q.write_new(root/'submission.json',row);C.need(result.returncode==0,'SBATCH_REJECTED_RETAIN_ACCOUNT_NO_RETRY')
        raw=Q.query(['scontrol','show','job',row['job_id'],'--oneliner']);C.job_identity(r,raw,row['job_id'],held=True)
        Q.write_new(root/'held_verified.json',{'job_id':row['job_id'],'submission_reference':ref,'held_job_metadata':raw,'other_jobs_modified':False})
        print(ref)
if __name__=='__main__':main()
