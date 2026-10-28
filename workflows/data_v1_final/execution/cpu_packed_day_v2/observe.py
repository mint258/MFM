"""Finite single-parent metadata observer; release exact held job, admit real PID."""
import argparse,json,time
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.registry import lock_file,process_identity
from . import contract as C
Q=C.Q

def quota(r,*,lease):
    carve,review,identity=C.resources(r,lease=lease);root=Path(review['publisher_output_dir'])
    latest,_=C.Provider.small(root/'latest.json');latest=json.loads(latest)
    C.need(latest['review_reference']==r['quota_provider_review_reference'] and latest['identity_reference']==r['quota_provider_identity_reference'],
        'SAME_ACTUAL_FROZEN_NEW_PUBLISHER_NOT_EPOCH2')
    value=C.Provider.pinned(latest['snapshot_reference']);parsed=C.Provider.validate_observation(value,identity,r['quota_provider_identity_reference'],review,r['quota_provider_review_reference'],time.time())
    live=process_identity(identity['pid']);C.need(live['pid']==identity['pid'] and live['start_ticks']==identity['start_ticks']
        and live['boot_id']==identity['boot_id'] and live['argv']==identity['execution_argv'],'ACTUAL_OWN_LOGIN_PUBLISHER_PROCESS_STILL_LIVE')
    C.need(parsed['free_bytes']-carve['total_future_reserved_bytes']>=C.RESERVE,'CURRENT_FUTURE_CAPS_WITHIN_ACCOUNT_QUOTA_PLUS200GB')
    return parsed,latest,identity,carve

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--submission',type=Path,required=True);p.add_argument('--max-seconds',type=int,default=90000);a=p.parse_args();Q.on_login()
    C.need(1<=a.max_seconds<=90000,'FINITE_SINGLE_METADATA_OBSERVER_ONLY');sub=Q.load(a.submission);r=sub['request'];C.validate(r)
    C.need(sub['schema']=='CPU_PACKED_DAY_SUBMISSION_V2' and sub['returncode']==0 and sub['status']=='SUBMITTED_HELD','ACTUAL_ONE_HELD_PARENT_SUBMISSION')
    jid=sub['job_id'];root=Path(r['startup_proof_path']).parent;started=time.monotonic();iteration=0
    with lock_file(root/'observer.lock'):
        while time.monotonic()-started<a.max_seconds:
            iteration+=1;raw=Q.query(['scontrol','show','job',jid,'--oneliner']);job=C.fields(raw);state=job['JobState']
            if state not in ('PENDING','RUNNING'):
                print(Q.write_new(root/'observer_terminal.json',{'job_id':jid,'job_metadata':raw,'state':state,'no_retry':True,'not_scientific_acceptance':True}));return
            if (root/'proof.ready.json').exists():print(Q.pin(root/'proof.json'));return
            try:
                if state=='PENDING':
                    C.job_identity(r,raw,jid,held=True);C.free_cpu(r,Q.query(['scontrol','show','node',r['node'],'--oneliner']));quota(r,lease=True)
                    C.need(not (root/'release_intent.json').exists(),'RELEASE_OUTCOME_ALREADY_RECORDED_NO_REPEAT')
                    Q.write_new(root/'release_intent.json',{'job_id':jid,'request_reference':sub['request_reference'],'observed_at':Q.now(),'one_exact_own_held_job':True})
                    Q.query(['scontrol','release',jid]);Q.write_new(root/'released.json',{'job_id':jid,'observed_at':Q.now(),'old_jobs_modified':False})
                else:
                    C.job_identity(r,raw,jid);ready=Q.load(root/'started.json');obs=ready['memory_observation'];now=time.time()
                    C.need(ready['job_id']==jid and ready['request_reference']==sub['request_reference'] and ready['actual_cpus']==r['cpus']
                        and obs['uid']==1278 and obs['node']==r['node'] and 0<=now-obs['observed_unix_seconds']<=120,
                        'ACTUAL_CPU_PARENT_HANDSHAKE_FRESH120')
                    parsed,latest,identity,carve=quota(r,lease=True);allraw=Q.query(['scontrol','show','job','--oneliner'])
                    jobs=C.parse_scontrol_jobs(allraw)
                    proof={'schema':C.PROOF,'request':r,'request_reference':sub['request_reference'],'job_id':jid,'uid':1278,'node':r['node'],
                        'boot_id':obs['boot_id'],'parent_identity':ready['parent_identity'],'observed_at':obs['observed_at'],'root_observed_at':Q.now(),
                        'memory_observation':obs,'job_metadata':raw,'existing_jobs_all_users':[{'metadata':j['_raw'],'job_id':j['JobId']} for j in jobs],
                        'memory_policy':C.MEMORY,'memory_admission_evaluated':False,'memory_limits_requested':False,
                        'actual_cpus':r['cpus'],'account_free_bytes':parsed['free_bytes'],'quota_observation_reference':latest['snapshot_reference'],
                        'quota_provider_identity_reference':r['quota_provider_identity_reference'],'quota_provider_review_reference':r['quota_provider_review_reference'],
                        'root_carveout_review_reference':r['root_carveout_review_reference'],'lease_coverage_checked_unix_seconds':now,
                        'publisher_expires_unix_seconds':identity['expires_unix_seconds'],'source_references':r['source_references'],
                        'producer_plan_reference':r['producer_plan_reference'],'execution_admission_granted':True,'one_real_parent_no_child_Slurm':True}
                    ref=Q.write_new(root/'proof.json',proof);Q.write_new(root/'proof.ready.json',{'job_id':jid,'proof_reference':ref});print(ref);return
            except Exception as exc:
                Q.write_new(root/('wait_%06d.json'%iteration),{'job_id':jid,'observed_at':Q.now(),'state':state,'wait_reason':repr(exc),
                    'other_jobs_modified':False,'no_auto_renew_or_resubmit':True})
            time.sleep(5)
        Q.write_new(root/'observer_lease_ended.json',{'job_id':jid,'no_resubmission':True,'old_jobs_modified':False,'finite_observer_ended':True})
if __name__=='__main__':main()
