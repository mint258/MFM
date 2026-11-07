"""Frozen create_proof plus one honest redundant top-level memory_basis tag.

The tag is copied from the same actual admission before proof and ready writes.
No ready evidence is changed after publication; every original validator runs.
"""
import json,pathlib,time
from ..queue_v1.shared import (ROOT,REPO,PY,fields,load,need,on_login,pin,query,
    read_small,uid,write_new,now,quota_free)
from ..queue_v1.queue_contract import (admit_memory,parse_scontrol_jobs,parse_scontrol_node,
    validate_request,validate_startup_job,validate_fresh_startup_proof)

def create_proof(row):
    reqpath=pathlib.Path(row['request_reference']['path']);need(pin(reqpath)==row['request_reference'],'REGISTERED_REQUEST_CHANGED')
    req=load(reqpath);validate_request(req,read_small=read_small,script_text=read_small(req['script_reference']['path']).decode())
    sub=load(row['receipt_reference']['path']);need(pin(row['receipt_reference']['path'])==row['receipt_reference'],'RECEIPT_CHANGED')
    jid=sub['job_id'];need(sub['request']==req and sub['sbatch_returncode']==0,'SUBMISSION_REQUEST_BINDING')
    jobraw=query(['scontrol','show','job',jid,'--oneliner']);job=fields(jobraw)
    if job.get('JobState')!='RUNNING':return {'job_id':jid,'state':job.get('JobState'),'reason':job.get('Reason'),'ready':False}
    proofpath=pathlib.Path(req['startup_proof_path']);marker=proofpath.with_suffix('.ready.json')
    dependency_evidence=[]
    for dep in req.get('dependencies',[]):
        raw=query(['sacct','-j',dep,'--format=JobIDRaw,State,ExitCode','-n','-P'])
        parents=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==dep]
        need(len(parents)==1 and parents[0][1]=='COMPLETED' and parents[0][2]=='0:0','ACTUAL_AFTEROK_EVIDENCE_REQUIRED')
        dependency_evidence.append({'job_id':dep,'raw_sacct':raw})
    if marker.exists():return {'job_id':jid,'state':'RUNNING','ready':True}
    validate_startup_job(req,job,expected_job_id=jid,uid=1278,script_reference=req['script_reference'],script_text=read_small(req['script_reference']['path']).decode())
    noderaw=query(['scontrol','show','node',req['node'],'--oneliner']);node=parse_scontrol_node(noderaw)
    rawjobs=query(['scontrol','show','job','--oneliner'])
    admission=admit_memory(req,node,parse_scontrol_jobs(rawjobs),own_job_id=jid,uid=1278)
    probe=REPO/'workflows/data_v1_final/execution/cpu_prefix_replay_v1/probe_memory.py'
    before=time.monotonic();raw=query(['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',req['node'],PY+' -B '+str(probe)])
    obs=json.loads(raw);need(time.monotonic()-before<=30 and obs['node']==req['node'] and obs['uid']==1278,'FRESH_TARGET_PROBE')
    capacity=min(int(fields(noderaw)['RealMemory'])*1024**2,obs['total_bytes'])
    committed=admission['committed_memory_mib']
    need((obs['used_bytes']+int(committed*1024**2)+64*1024**3)*100<=capacity*85,'WAIT_LIVE_MEMORY_ENVELOPE')
    quotaraw=query(['quota','-v','-u','zixiao']);free=quota_free(quotaraw)
    need(free-req['estimated_peak_output_bytes']>=200_000_000_000,'WAIT_ACCOUNT_QUOTA_RESERVE')
    proof={'schema':'FRESH_QUEUED_CPU_EXECUTION_ADMISSION_V1','observed_at':obs['observed_at'],'uid':1278,
        'job_id':jid,'boot_id':obs['boot_id'],'request_reference':row['request_reference'],'request':req,
        'job_metadata':jobraw,'node_metadata':noderaw,'existing_jobs_all_users':admission['existing_jobs_all_users'],
        'committed_memory_mib':committed,'memory_basis':admission['memory_basis'],'account_free_bytes':free,'quota_raw':quotaraw,
        'memory_observation':obs,'live_envelope_admission_passed':True,'strict_declaration_admission':admission,
        'queue_authority_reference':req['queue_authority_reference'],'source_references':req['source_references'],
        'script_reference':req['script_reference'],'actual_dependency_evidence':dependency_evidence,'root_login_observed_at':now(),'execution_admission_granted':True,
        'no_memory_exemption':True,'other_jobs_modified':False}
    validate_fresh_startup_proof(proof,req,now_unix=obs['observed_unix_seconds'],uid=1278,boot_id=obs['boot_id'],max_age_seconds=120)
    write_new(proofpath,proof);write_new(marker,{'job_id':jid,'proof_reference':pin(proofpath)})
    return {'job_id':jid,'state':'RUNNING','ready':True,'proof':pin(proofpath)}
