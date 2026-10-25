"""Root submits held jobs, verifies user isolation, then releases to the scheduler."""
import argparse,fcntl,pathlib,subprocess
from .shared import ROOT,PROJECT,fields,load,need,on_login,pin,query,read_small,uid,write_new,now,quota_free,memory_mib
from .queue_contract import validate_request

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=pathlib.Path,required=True);p.add_argument('--keep-held',action='store_true');a=p.parse_args();on_login()
    req=load(a.request);validate_request(req,read_small=read_small,script_text=read_small(req['script_reference']['path']).decode())
    name=req['job_name'];receipt=ROOT/'control/submissions'/(name+'.json');initial=ROOT/'control/submissions'/(name+'.queue_intent.json')
    with (ROOT/'control/submissions/root.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        need(not receipt.exists() and not initial.exists(),'ALREADY_REGISTERED_NO_RESUBMISSION')
        before=query(['squeue','-h','-u','zixiao','-o','%i|%j|%T|%N']);need(all(line.split('|')[1]!=name for line in before.splitlines()),'DUPLICATE_NAME')
        quota=query(['quota','-v','-u','zixiao']);free=quota_free(quota)
        need(free-req['estimated_peak_output_bytes']>=200_000_000_000,'QUOTA_RESERVE')
        record={'schema':'QUEUED_CPU_SUBMISSION_V1','observed_at':now(),'uid':1278,'request_reference':pin(a.request),
            'request':req,'queue_before':before,'quota_raw':quota,'account_free_bytes':free,
            'execution_admission_granted':False,'held_submission_before_readback':True}
        write_new(initial,record)
        argv=['sbatch','--parsable','--hold','--no-requeue','--chdir='+str(PROJECT)]
        if req.get('dependencies'):argv+=['--dependency=afterok:'+':'.join(req['dependencies'])]
        argv+=[req['script_reference']['path']]
        try:
            r=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45)
            record.update(sbatch_argv=argv,sbatch_returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
        except subprocess.TimeoutExpired:
            record.update(sbatch_argv=argv,status='SUBMISSION_OUTCOME_UNKNOWN_NO_RETRY');write_new(receipt,record);raise
        if r.returncode==0:
            jid=r.stdout.strip().split(';')[0]
            if not jid.isdecimal():
                record.update(status='UNRECOGNIZED_SUBMISSION_RESPONSE_NO_RETRY');write_new(receipt,record);raise ValueError('UNRECOGNIZED_JOB_ID')
            record.update(job_id=jid,status='SUBMITTED_HELD_NOT_EXECUTION_ADMITTED')
        else:record.update(status='SUBMISSION_FAILED_NO_RETRY')
        write_new(receipt,record);need(r.returncode==0,'SBATCH_REJECTED_SEE_RECEIPT')
        raw=query(['scontrol','show','job',jid,'--oneliner']);j=fields(raw)
        need(uid(j)==1278 and j['JobState']=='PENDING' and j['JobName']==name and j['Partition']=='cpu','HELD_JOB_IDENTITY')
        need(j['ReqNodeList']==req['node'] and int(j['NumCPUs'])==16 and memory_mib(j['MinMemoryNode'])==65536,'EXACT_QUEUED_RESOURCES')
        need(j['OverSubscribe']=='USER' and j['Requeue']=='0' and j['WorkDir']==str(PROJECT) and j['Command']==req['script_reference']['path'],'USER_ISOLATION_AND_SCRIPT_REQUIRED')
        validate_request(req,read_small=read_small,script_text=read_small(req['script_reference']['path']).decode())
        if a.keep_held:
            write_new(ROOT/'control/submissions'/(name+'.verification.json'),{'schema':'QUEUED_CPU_HELD_BINDING_V1',
                'job_id':jid,'receipt_reference':pin(receipt),'held_readback':raw,
                'status':'HELD_BINDING_VERIFIED_WAITING_FOR_REGISTERED_OBSERVER_BEFORE_RELEASE',
                'exclusive_user_verified':True,'other_jobs_modified':False})
            print(__import__('json').dumps({'job_id':jid,'receipt':str(receipt),'status':'SUBMITTED_HELD_AWAITING_OBSERVER','node':req['node']}),flush=True);return
        release=query(['scontrol','release',jid]);after=query(['scontrol','show','job',jid,'--oneliner'])
        write_new(ROOT/'control/submissions'/(name+'.verification.json'),{'schema':'QUEUED_CPU_RELEASE_V1','job_id':jid,
            'receipt_reference':pin(receipt),'held_readback':raw,'release_stdout':release,'released_readback':after,
            'status':'RELEASED_TO_REAL_RESOURCE_QUEUE_EXECUTION_GUARD_STILL_REQUIRED','other_jobs_modified':False,
            'exclusive_user_verified':True,'full_node_exclusive_not_requested':True})
        print(__import__('json').dumps({'job_id':jid,'receipt':str(receipt),'status':'QUEUED_FOR_RESOURCES_NOT_SCIENCE_STARTED','node':req['node']}),flush=True)
if __name__=='__main__':main()
