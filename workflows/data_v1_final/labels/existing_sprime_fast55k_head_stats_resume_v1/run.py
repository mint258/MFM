"""Fresh real local process, completed geometry reused, original numeric suffix."""
import argparse,concurrent.futures as cf,datetime,json,multiprocessing as mp,os,pathlib,socket,time,traceback
from workflows.data_v1_final.labels.existing_sprime_fast55k_head_v1 import run as H
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v13 import contract as C,run as P
from . import runtime as R

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);args=parser.parse_args()
    envelope=C.meta(C.P.pin(args.plan));control=pathlib.Path(envelope['control_directory']);plan=dict(envelope['operative_plan'])
    authority=C.meta(envelope['headnode_authority_reference']);origin=C.meta(envelope['statistics_resume_origin_reference'])
    C.need(authority['D4_only'] is True and authority['status']=='USER_AUTHORIZED' and os.getuid()==1278
      and socket.gethostname().split('.')[0]=='sonmi' and not os.environ.get('SLURM_JOB_ID'),'REAL_USER_AUTHORIZED_HEAD_D4')
    prior_exit=C.meta(origin['actual_prior_exit_reference'])
    C.need(prior_exit['exit_code']==1 and not pathlib.Path('/proc/'+str(prior_exit['actual_pid'])).exists(),'CLOSED_REAL_PRIOR_PROCESS_NO_DUPLICATE')
    root=pathlib.Path(plan['output_directory']);admin=root/'statistics_resume_v1_metadata';admin.mkdir()
    R.ROOT=root;R.ADMIN=admin;R.ORIGIN=envelope['statistics_resume_origin_reference']
    os.sched_setaffinity(0,{0,1});os.nice(10);cf.ProcessPoolExecutor=H.LimitedPool;mp.get_context=H.limited_context
    pid=os.getpid();ticks=pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19];started=time.time()
    identity='LOCAL_D4_PID'+str(pid)+'_START'+ticks
    marker=control/'head_storage_marker.json';marker.write_text(json.dumps(dict(pid=pid,uid=os.getuid(),execution_id=identity))+'\n')
    qi=control/'local_quota_identity.json';qi.write_text(json.dumps(dict(schema='ACTUAL_LOCAL_DIRECT_QUOTA_CLIENT_IDENTITY_V1',execution_kind='LOCAL_HEADNODE',pid=pid,uid=os.getuid(),start_ticks=ticks,started_unix_seconds=started,expires_unix_seconds=started+90000))+'\n')
    qr=control/'local_quota_review.json';qr.write_text(json.dumps(dict(execution_kind='LOCAL_HEADNODE',storage_marker_path=str(marker),snapshot_root=str(control/'quota_snapshots')))+'\n')
    plan.update(node='sonmi',workers=2,pending=4,plan_path=args.plan,quota_provider_identity_reference=C.P.pin(qi),quota_provider_review_reference=C.P.pin(qr))
    plan['data_references']=C.unique([*plan['data_references'],*origin['runtime_additional_data_references']])
    request=dict(schema='ACTUAL_LOCAL_HEAD_D4_REQUEST_V1',node='sonmi',cpus=2,wall_seconds=86400,memory_policy='OBSERVED_LOCAL_PROCESS_NO_SLURM_ALLOCATION',pilot=False,estimated_peak_output_bytes=plan['whole_output_cap_bytes'],data_references=plan['data_references'],local_quota_identity_reference=C.P.pin(qi),execution_kind='LOCAL_HEADNODE')
    rq=control/'actual_local_request.json';rq.write_text(json.dumps(request,sort_keys=True)+'\n')
    proof=dict(schema='ACTUAL_USER_AUTHORIZED_HEADNODE_D4_PROCESS_PROOF_V1',execution_kind='LOCAL_HEADNODE',execution_id=identity,job_id=identity,legacy_job_id_field_is_local_execution_id=True,Slurm_job_id=None,pid=pid,uid=os.getuid(),start_ticks=ticks,node='sonmi',actual_affinity=[0,1],local_started_unix_seconds=started,request=request,request_reference=C.P.pin(rq),observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),root_observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    pp=control/'actual_local_process_proof.json';pp.write_text(json.dumps(proof,sort_keys=True)+'\n');plan['startup_proof_path']=str(pp)
    plan['source_references']=C.unique([*plan['source_references'],C.P.pin(qi),C.P.pin(qr),C.P.pin(pp)])
    io=R.ResumeIO();io.configure(plan);budget=None
    try:
        gate=P.fixtures(admin/'source6');io.configure(plan)
        state=io.load_data(origin['actual_checkpoint_reference'],8<<20)
        C.need(state['phase']=='STATISTICS' and state['numeric_repetitions']==[] and state['numeric_state']['pending_group_reports']==[], 'ONLY_REAL_PRE_NUMERIC_COMPLETE_CHECKPOINT')
        geometry=io.load_data(state['geometry_reference'],64<<20);cfg=io.load_data(state['typed_reader_config_reference'],64<<20)
        state['pass_number']=0;state['numeric_state']['pending_group_errors']=[]
        R.bind_worker_memory_metric();budget=R.Budget(plan,proof,root);budget.check(force=True)
        execute=R.continuation_function(io,state,cfg,geometry);receipt_ref=execute(plan,proof,root,gate,budget)
        receipt=io.load_data(receipt_ref,8<<20)
        C.need(not receipt['held'] and receipt['errors']==[] and receipt['independent_numeric_replay_equal'] is True and len(receipt['numeric_repetitions'])==2,'ACTUAL_CONTINUATION_TWO_EQUAL_ORIGINAL_REPLAYS')
        (control/'actual_final_receipt_path.json').write_text(json.dumps(receipt_ref)+'\n')
        return 0
    except BaseException as error:
        (control/'local_failure.json').write_text(json.dumps(dict(error=repr(error),traceback=traceback.format_exc(),actual_pid=pid,execution_id=identity,no_fake_Slurm_job_or_C0=True))+'\n');raise
    finally:
        if budget is not None:budget.close()

if __name__=='__main__':raise SystemExit(main())
