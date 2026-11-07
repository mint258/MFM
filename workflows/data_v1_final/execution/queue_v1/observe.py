"""Finite Root metadata observer: fresh admission for registered queued jobs only."""
import argparse,fcntl,json,os,pathlib,socket,subprocess,time,traceback
from .shared import ROOT,REPO,PY,fields,load,need,on_login,pin,query,read_small,uid,write_new,now,quota_free
from .queue_contract import admit_memory,parse_scontrol_jobs,parse_scontrol_node,validate_request,validate_startup_job,validate_fresh_startup_proof

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
        'committed_memory_mib':committed,'account_free_bytes':free,'quota_raw':quotaraw,
        'memory_observation':obs,'live_envelope_admission_passed':True,'strict_declaration_admission':admission,
        'queue_authority_reference':req['queue_authority_reference'],'source_references':req['source_references'],
        'script_reference':req['script_reference'],'actual_dependency_evidence':dependency_evidence,'root_login_observed_at':now(),'execution_admission_granted':True,
        'no_memory_exemption':True,'other_jobs_modified':False}
    validate_fresh_startup_proof(proof,req,now_unix=obs['observed_unix_seconds'],uid=1278,boot_id=obs['boot_id'],max_age_seconds=120)
    write_new(proofpath,proof);write_new(marker,{'job_id':jid,'proof_reference':pin(proofpath)})
    return {'job_id':jid,'state':'RUNNING','ready':True,'proof':pin(proofpath)}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--registry',type=pathlib.Path,required=True)
    p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--max-seconds',type=int,default=86400)
    p.add_argument('--poll-seconds',type=int,default=20);a=p.parse_args();on_login()
    need(1<=a.max_seconds<=86400 and 5<=a.poll_seconds<=60 and not a.output.exists(),'FINITE_NEW_OBSERVER')
    observer_lock=(ROOT/'control/root_queue_observer.lock').open('a');fcntl.flock(observer_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    registry=load(a.registry);need(registry['schema']=='REGISTERED_QUEUED_CPU_JOBS_V1' and registry['jobs'],'EXACT_REGISTERED_JOB_SET')
    a.output.mkdir();stat=pathlib.Path('/proc/self/stat').read_text();identity={'pid':os.getpid(),'uid':os.getuid(),
        'start_ticks':int(stat[stat.rfind(')')+2:].split()[19]),'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'source_reference':pin(pathlib.Path(__file__).absolute()),'registry_reference':pin(a.registry),'started_at':now(),'max_seconds':a.max_seconds}
    write_new(a.output/'identity.json',identity);start=time.monotonic();last=None;iteration=0
    terminal={'COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL'}
    while time.monotonic()-start<a.max_seconds:
        iteration+=1;states=[]
        for row in registry['jobs']:
            try:
                receipt=load(row['receipt_reference']['path']);jid=receipt['job_id']
                need(pin(row['receipt_reference']['path'])==row['receipt_reference'] and jid==row['job_id'],'REGISTERED_RECEIPT_IDENTITY')
                raw=query(['sacct','-j',jid,'--format=JobIDRaw,State,ExitCode,ElapsedRaw,AllocCPUS','-n','-P'])
                parents=[s.split('|') for s in raw.splitlines() if s.split('|')[0]==jid]
                need(len(parents)==1,'ONE_CURRENT_PARENT_REQUIRED');parent=parents[0]
                if parent[1].split()[0] in terminal:
                    states.append({'job_id':jid,'state':parent[1],'exit_code':parent[2],'parent_raw':raw});continue
                states.append(create_proof(row))
            except Exception as exc:states.append({'job_id':row.get('job_id'),'observation_error':repr(exc),'not_terminal':True})
        compact=json.dumps(states,sort_keys=True)
        if compact!=last:
            write_new(a.output/('observation_'+str(iteration)+'.json'),{'observed_at':now(),'states':states});last=compact
        heartbeat={'identity_reference':pin(a.output/'identity.json'),'observed_at':now(),'iteration':iteration,
            'states':states,'elapsed_seconds':time.monotonic()-start,'all_terminal':all(str(s.get('state') or 'UNKNOWN').split()[0] in terminal for s in states)}
        temp=a.output/('heartbeat_'+str(iteration)+'.json');write_new(temp,heartbeat)
        # Atomic rename only updates this observer's explicit mutable pointer, not any evidence snapshot.
        pointer=a.output/'latest.json';link=a.output/('pointer_'+str(iteration)+'.json');write_new(link,{'snapshot':pin(temp)})
        os.replace(link,pointer)
        if heartbeat['all_terminal']:
            write_new(a.output/'closure.json',{'status':'REGISTERED_PHASE_ALL_TERMINAL_NOT_GLOBAL_TASK_COMPLETE','states':states,'observed_at':now()});return
        time.sleep(a.poll_seconds)
    write_new(a.output/'closure.json',{'status':'FINITE_OBSERVER_LEASE_ENDED_JOBS_MUST_BE_REOBSERVED_NOT_RESTARTED','observed_at':now()})
if __name__=='__main__':main()
