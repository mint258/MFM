"""Register held jobs, start their finite observer, then release verified own jobs."""
import argparse,os,pathlib,subprocess,time
from .shared import ROOT,REPO,PY,fields,load,need,on_login,pin,query,read_small,uid,write_new,now,memory_mib
from .queue_contract import validate_request

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job-name',action='append',required=True)
    p.add_argument('--registry',type=pathlib.Path,required=True);p.add_argument('--observer-output',type=pathlib.Path,required=True)
    a=p.parse_args();on_login();need(not a.registry.exists() and not a.observer_output.exists(),'NEW_ACTIVATION_ONLY')
    rows=[]
    for name in a.job_name:
        rp=ROOT/'control/requests'/(name+'.json');sp=ROOT/'control/submissions'/(name+'.json');req=load(rp);sub=load(sp)
        need(sub['request']==req and sub['sbatch_returncode']==0,'ACTUAL_OWNED_SUBMISSION')
        validate_request(req,read_small=read_small,script_text=read_small(req['script_reference']['path']).decode())
        raw=query(['scontrol','show','job',sub['job_id'],'--oneliner']);j=fields(raw)
        need(uid(j)==1278 and j['JobState']=='PENDING' and j['JobName']==name and j['OverSubscribe']=='USER' and j['Requeue']=='0','HELD_OWN_USER_ISOLATED_JOB')
        need(int(j['NumCPUs'])==16 and memory_mib(j['MinMemoryNode'])==65536 and j['Command']==req['script_reference']['path'],'EXACT_ACTUAL_QUEUED_RESOURCES')
        rows.append({'job_id':sub['job_id'],'request_reference':pin(rp),'receipt_reference':pin(sp),'held_readback':raw})
    write_new(a.registry,{'schema':'REGISTERED_QUEUED_CPU_JOBS_V1','observed_at':now(),'jobs':rows,
        'all_required_deliverables_still_pending':True,'other_jobs_modified':False})
    logpath=a.observer_output.with_suffix('.log')
    with logpath.open('xb') as log:
        child=subprocess.Popen([PY,'-B','-m','workflows.data_v1_final.execution.queue_v1.observe','--registry',str(a.registry),
            '--output',str(a.observer_output),'--max-seconds','86400','--poll-seconds','20'],
            cwd=REPO,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    identity=None;deadline=time.monotonic()+30
    while identity is None and time.monotonic()<deadline:
        need(child.poll() is None,'OBSERVER_EXITED_BEFORE_RELEASE')
        try:identity=load(a.observer_output/'identity.json')
        except (OSError,ValueError):time.sleep(.2)
    need(identity and identity['pid']==child.pid and identity['uid']==1278,'ACTUAL_OBSERVER_IDENTITY_REQUIRED')
    releases=[]
    for row in rows:
        jid=row['job_id'];req=load(row['request_reference']['path'])
        validate_request(req,read_small=read_small,script_text=read_small(req['script_reference']['path']).decode())
        raw=query(['scontrol','show','job',jid,'--oneliner']);j=fields(raw)
        need(uid(j)==1278 and j['JobState']=='PENDING' and j['OverSubscribe']=='USER','REVALIDATE_OWN_PENDING_JOB')
        release=query(['scontrol','release',jid]);after=query(['scontrol','show','job',jid,'--oneliner'])
        releases.append({'job_id':jid,'before':raw,'release_stdout':release,'after':after})
    path=a.registry.with_suffix('.activation.json');write_new(path,{'schema':'ACTUAL_QUEUED_PHASE_ACTIVATION_V1',
        'registry_reference':pin(a.registry),'observer_identity_reference':pin(a.observer_output/'identity.json'),
        'observer_pid':child.pid,'releases':releases,'observed_at':now(),'other_jobs_modified':False,
        'status':'RELEASED_TO_SCHEDULER_RESOURCE_QUEUE_FRESH_EXECUTION_PROOF_STILL_REQUIRED'})
    print(__import__('json').dumps({'activation':pin(path),'job_ids':[r['job_id'] for r in rows],
        'observer_pid':child.pid,'observer_output':str(a.observer_output),'status':'ACTUAL_QUEUE_LIVE_NOT_SCIENCE_COMPLETE'}),flush=True)
if __name__=='__main__':main()
