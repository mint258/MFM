"""Fresh CPU/code/quota admission; scheduler and real memory are observations."""
import json,time
from pathlib import Path
from .shared import REPO,PY,load,pin,read_small,query,quota_free,write_new,now
from .contract import (PROOF_SCHEMA,MEMORY_POLICY,need,validate_request,validate_bound_request,
                       validate_fresh_startup_proof,job_identity,fmt)


def create_proof(row):
    need(pin(row['request_reference']['path'])==row['request_reference'],'REGISTERED_REQUEST_CHANGED')
    need(pin(row['receipt_reference']['path'])==row['receipt_reference'],'REGISTERED_SUBMISSION_CHANGED')
    req=load(row['request_reference']['path']);sub=load(row['receipt_reference']['path']);jid=row['job_id']
    need(sub.get('schema')=='CPU_AUTO_MEMORY_SUBMISSION_V1' and sub.get('job_id')==jid and
         sub.get('request')==req and sub.get('sbatch_returncode')==0,'EXACT_NEW_OWN_SUBMISSION_REQUIRED')
    validate_request(req,read_small=read_small);validate_bound_request(req,read_small=read_small)
    raw=query(['scontrol','show','job',jid,'--oneliner']);job=fmt._fields(raw)
    if job.get('JobState')!='RUNNING':return {'job_id':jid,'state':job.get('JobState'),'reason':job.get('Reason'),'ready':False}
    job_identity(req,job,job_id=jid)
    proof_path=Path(req['startup_proof_path']);marker=proof_path.with_suffix('.ready.json')
    if marker.exists():
        ready=load(marker);need(ready['job_id']==jid and ready['proof_reference']==pin(proof_path),'OWN_READY_PROOF_CHANGED')
        return {'job_id':jid,'state':'RUNNING','ready':True}
    dependencies=[]
    for dep in req.get('dependencies',[]):
        text=query(['sacct','-j',dep,'--format=JobIDRaw,State,ExitCode','-n','-P'])
        parents=[line.split('|') for line in text.splitlines() if line.split('|')[0]==dep]
        need(len(parents)==1 and parents[0][1]=='COMPLETED' and parents[0][2]=='0:0','ACTUAL_AFTEROK_C0_REQUIRED')
        dependencies.append({'job_id':dep,'raw_sacct':text})
    node=query(['scontrol','show','node',req['node'],'--oneliner'])
    all_jobs=query(['scontrol','show','job','--oneliner'])
    try:
        jobs=[{'job_id':j['JobId'],'metadata':j['_raw'],'declarations_observation_only':True}
              for j in fmt.parse_scontrol_jobs(all_jobs)]
    except ValueError as exc:
        jobs=[{'metadata':all_jobs,'observation_parse_error':repr(exc),'declarations_observation_only':True}]
    probe=REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v1/probe.py'
    started=time.monotonic()
    observation=json.loads(query(['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
        '-o','ConnectTimeout=15',req['node'],PY+' -B '+str(probe)]))
    need(time.monotonic()-started<=30 and observation['node']==req['node'] and observation['uid']==1278,
         'FRESH_ACTUAL_TARGET_IDENTITY_REQUIRED')
    quota=query(['quota','-v','-u','zixiao']);free=quota_free(quota)
    proof={'schema':PROOF_SCHEMA,'job_id':jid,'uid':1278,'node':req['node'],'boot_id':observation['boot_id'],
        'observed_at':observation['observed_at'],'request_reference':row['request_reference'],'request':req,
        'memory_policy':MEMORY_POLICY,'memory_admission_evaluated':False,'memory_limits_requested':False,
        'job_metadata':raw,'node_metadata':node,'existing_jobs_all_users':jobs,
        'actual_scheduler_memory_fields':{key:job.get(key) for key in ('MinMemoryNode','MinMemoryCPU','TRES')},
        'memory_observation':observation,'account_free_bytes':free,'quota_raw':quota,
        'source_references':req['source_references'],'script_reference':req['script_reference'],
        'queue_authority_reference':req['queue_authority_reference'],'actual_dependency_evidence':dependencies,
        'execution_admission_granted':True,'other_jobs_modified':False,'root_observed_at':now()}
    validate_fresh_startup_proof(proof,req,now_unix=observation['observed_unix_seconds'],
        uid=1278,boot_id=observation['boot_id'],max_age_seconds=120)
    write_new(proof_path,proof);write_new(marker,{'job_id':jid,'proof_reference':pin(proof_path)})
    return {'job_id':jid,'state':'RUNNING','ready':True,'proof_reference':pin(proof_path)}
