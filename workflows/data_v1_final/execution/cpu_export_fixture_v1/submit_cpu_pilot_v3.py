"""CPU test submitter v3: bind runtime freshness to the target node observation clock."""
from __future__ import annotations
import argparse,datetime,fcntl,importlib.util,json,os,pathlib,socket,subprocess,time
from workflows.data_v1_final.execution.cpu_export_fixture_v1 import policy,runtime
ROOT=policy.ROOT
LEGACY=policy.REPO/'workflows/data_v1_final/execution/submit_reviewed.py'
policy.require(policy.ref(LEGACY)['sha256']=='6d1e3f5623bcdf04351d50710ccc81b5ca50f23d3b19051cba29f6fee173ee7f','ORIGINAL_CONTROLLER_CHANGED')
spec=importlib.util.spec_from_file_location('_original_root_controller',LEGACY);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)

def validate_request(r):
    policy.scope(r);name=policy.job_name(r)
    policy.require(policy.ref(pathlib.Path(__file__)) in r['source_references'],'ACTUAL_SUBMITTER_NOT_PINNED')
    policy.require(policy.ref(LEGACY) in r['source_references'],'ORIGINAL_CONTROL_HELPERS_NOT_PINNED')
    return name

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=pathlib.Path,required=True);a=p.parse_args()
    policy.require(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi','ROOT_METADATA_ON_LOGIN_ONLY')
    request=policy.load(a.request);name=validate_request(request);node_name=request['node']
    submissions=ROOT/'control/submissions';receipt=submissions/(name+'.json');intent=submissions/(name+'.intent.json')
    with (submissions/'root.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        policy.require(not receipt.exists() and not intent.exists(),'SUBMISSION_ALREADY_REGISTERED_AUDIT_NO_RETRY')
        queue=old.query(['squeue','-h','-u','zixiao','-o','%i|%j|%N|%T'])
        policy.require(all(line.split('|')[1]!=name for line in queue.splitlines()),'DUPLICATE_ACTIVE_JOB')
        quota=old.query(['quota','-v','-u','zixiao']);free=old.quota_available_bytes(quota)
        policy.require(free-request['estimated_peak_output_bytes']>=200_000_000_000,'200GB_RESERVE_REQUIRED')
        sinfo=old.query(['sinfo','--Node','--nodes='+node_name,'--noheader','--format=%N|%P|%t|%C|%m'])
        node_raw=old.query(['scontrol','show','node',node_name,'--oneliner']);node=old.fields(node_raw)
        policy.require('cpu' in node['Partitions'].split(','),'ACTUAL_NODE_IS_NOT_IN_CPU_PARTITION')
        policy.require(int(node['CPUTot'])-int(node['CPUAlloc'])>=16,'WAIT_FOR_REAL_FREE_CPUS')
        ids=old.query(['squeue','-h','-w',node_name,'-t','RUNNING,COMPLETING','-o','%i'])
        positive=0.;jobs=[]
        for jid in ids.split():
            metadata=old.query(['scontrol','show','job',jid,'--oneliner']);job=old.fields(metadata)
            if 'MinMemoryNode' in job:mem=old.memory_mib(job['MinMemoryNode'])
            elif 'MinMemoryCPU' in job:mem=old.memory_mib(job['MinMemoryCPU'])*int(job['NumCPUs'])
            else:raise ValueError('EXISTING_MEMORY_DECLARATION_UNKNOWN')
            if mem>0:positive+=mem
            jobs.append({'job_id':jid,'memory_declaration_mib':mem,'zero_means_unbounded_not_zero_use':mem==0,'metadata':metadata})
        probe=policy.REPO/'workflows/data_v1_final/execution/cpu_export_fixture_v1/probe_memory.py'
        command='/share/home/zixiao/.conda/envs/chemprop/bin/python -B '+str(probe)
        argv=['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',node_name,command]
        probe_started=time.monotonic()
        observation=json.loads(old.query(argv))
        probe_age=time.time()-observation['observed_unix_seconds'];probe_elapsed=time.monotonic()-probe_started
        policy.require(observation['node']==node_name and observation['uid']==1278,'REAL_CPU_MEMORY_PROBE_IDENTITY_REQUIRED')
        policy.require(0<=probe_elapsed<=30 and abs(probe_age)<=30,'REAL_FRESH_CPU_MEMORY_PROBE_REQUIRED')
        limit=int(node['RealMemory'])*1024**2;reserved=int(max(float(node['AllocMem']),positive)*1024**2)
        denial=runtime.memory_denial(observation,limit,reserved,request['memory_gib']*1024**3,0)
        policy.require(denial is None,'WAIT_FOR_MEASURED_SMALL_TEST_MEMORY:'+str(denial))
        record={'observed_at':observation['observed_at'],'root_login_observed_at':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'preflight_timestamp_basis':'TARGET_NODE_ACTIVE_MEMORY_PROBE_CLOCK','uid':1278,'request_reference':policy.ref(a.request),'request':request,'queue_before':queue,'quota_raw':quota,'account_free_bytes':free,'sinfo':sinfo,'node_metadata':node_raw,'existing_jobs_all_users':jobs,'memory_basis':policy.BASIS,'actual_memory_admission_passed':True,'memory_observation':observation,'memory_probe_wall_age_seconds':probe_age,'memory_probe_monotonic_roundtrip_seconds':probe_elapsed,'memory_probe_argv':argv,'node_memory_limit_bytes':limit,'reserved_positive_other_bytes':reserved,'zero_memory_declarations_treated_as_explicitly_unbounded':True,'small_test_exception_not_formal':True}
        validate_request(request);old.write_new(intent,record)
        argv=['sbatch','--parsable','--chdir='+str(ROOT.parent.parent),request['script_reference']['path']]
        try:
            result=subprocess.run(argv,cwd=ROOT.parent.parent,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45)
            record.update(sbatch_argv=argv,sbatch_returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
        except subprocess.TimeoutExpired:
            record.update(sbatch_argv=argv,status='SUBMISSION_OUTCOME_UNKNOWN_NO_AUTOMATIC_RETRY');old.write_new(receipt,record);raise
        if result.returncode==0:
            jid=result.stdout.strip().split(';')[0]
            if not jid.isdecimal():
                record['status']='UNRECOGNIZED_SUBMISSION_RESPONSE_NO_AUTOMATIC_RETRY';old.write_new(receipt,record);raise ValueError('UNRECOGNIZED_JOB_ID')
            record.update(job_id=jid,status='SUBMITTED_NOT_COMPLETED')
        else:record['status']='SUBMISSION_FAILED_NO_AUTOMATIC_RETRY'
        old.write_new(receipt,record)
        if result.returncode:raise RuntimeError('SLURM_REJECTED_SEE_IMMUTABLE_RECEIPT')
        verification={'job_id':jid,'receipt_reference':policy.ref(receipt)}
        try:
            raw=old.query(['scontrol','show','job',jid,'--oneliner']);actual=old.fields(raw)
            verification['actual_job_metadata']=raw
            policy.require(actual['WorkDir']==str(ROOT.parent.parent) and actual['ReqNodeList']==node_name and actual['Partition']=='cpu' and int(actual['NumCPUs'])>=16,'POST_SUBMISSION_ALLOCATION_DIFFERS')
            verification['status']='SUBMITTED_CPU_JOB_METADATA_VERIFIED'
        except Exception as e:
            verification.update(status='POST_SUBMISSION_VERIFICATION_FAILED_NO_AUTOMATIC_RETRY',error=repr(e));old.write_new(submissions/(name+'.verification.json'),verification);raise
        old.write_new(submissions/(name+'.verification.json'),verification)
        print(json.dumps({'receipt':str(receipt),'job_id':jid,'status':record['status'],'node':node_name,'formal_generation_authorized':False}))
if __name__=='__main__':main()
