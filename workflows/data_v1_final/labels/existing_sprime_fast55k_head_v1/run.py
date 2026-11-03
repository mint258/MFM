"""Low-concurrency local D4, original six Source checks and exact TRAIN replays."""
import argparse,concurrent.futures as cf,datetime,json,multiprocessing as mp,os,pathlib,socket,time,traceback,types
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v13 import run as Parent,geometry as G,contract as C
from workflows.data_v1_final.labels.existing_sprime_fast55k_pilot_day_v1 import run as Original
from .resource import LocalBudget
WORKERS=2
REAL_POOL=cf.ProcessPoolExecutor;REAL_CONTEXT=mp.get_context

class LimitedPool(REAL_POOL):
    def __init__(self,*args,**kwargs):
        if args:args=(min(args[0],WORKERS),*args[1:])
        else:kwargs['max_workers']=min(kwargs.get('max_workers',WORKERS),WORKERS)
        super().__init__(*args,**kwargs)

class LocalContext:
    def __init__(self,actual):self.actual=actual
    def __getattr__(self,name):return getattr(self.actual,name)
    def Barrier(self,parties,*args,**kwargs):return self.actual.Barrier(min(parties,WORKERS),*args,**kwargs)

def limited_context(*args,**kwargs):return LocalContext(REAL_CONTEXT(*args,**kwargs))

class HeadIO(Parent.ParentIO):
    def save(self,path,value):
        if isinstance(value,dict) and any(str(value.get(k,'')).startswith('LOCAL_D4_') for k in ('job_id','actual_parent_job_id')):
            value['producer_execution_kind']='LOCAL_HEADNODE';value['Slurm_job_id']=None
            if value.get('workers')==16:value['workers']=WORKERS
            if value.get('status')=='PROVISIONAL55K_FAST_TYPED_NATIVE_RANDOM_AND_TRAIN_D4_COMPLETE_PENDING_ACTUAL_C0_ROOT_SEAL':
                value['status']='PROVISIONAL55K_FAST_TYPED_NATIVE_RANDOM_AND_TRAIN_D4_COMPLETE_PENDING_ACTUAL_LOCAL_EXIT_ZERO'
                value['Root_actual_C0_limited_acceptance_required']=False
                value['Root_actual_local_process_zero_exit_required']=True
        return super().save(path,value)

class Coverage:
    def __getattr__(self,name):return getattr(G.COVERAGE,name)
    def build(self,*args,**kwargs):
        f=G.COVERAGE.build;namespace=dict(f.__globals__,I=HeadIO())
        return types.FunctionType(f.__code__,namespace,f.__name__,f.__defaults__,f.__closure__)(*args,**kwargs)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);args=parser.parse_args()
    envelope=C.meta(C.P.pin(args.plan));plan=envelope['operative_plan'];control=pathlib.Path(envelope['control_directory'])
    authority=C.meta(envelope['headnode_authority_reference'])
    C.need(authority['status']=='USER_AUTHORIZED' and authority['D4_only'] is True
      and authority['node']=='sonmi' and os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
      and not os.environ.get('SLURM_JOB_ID'),'EXPLICIT_REAL_MAIN_HEAD_D4_NOT_SLURM')
    pid=os.getpid();ticks=pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]
    identity='LOCAL_D4_PID'+str(pid)+'_START'+ticks;started=time.time()
    allowed=sorted(os.sched_getaffinity(0));os.sched_setaffinity(0,set(allowed[:WORKERS]));os.nice(10)
    cf.ProcessPoolExecutor=LimitedPool;mp.get_context=limited_context
    marker=control/'head_storage_marker.json';marker.write_text(json.dumps(dict(pid=pid,uid=os.getuid(),execution_id=identity))+'\n')
    qi=control/'local_quota_identity.json';qi.write_text(json.dumps(dict(schema='ACTUAL_LOCAL_DIRECT_QUOTA_CLIENT_IDENTITY_V1',execution_kind='LOCAL_HEADNODE',pid=pid,uid=os.getuid(),start_ticks=ticks,started_unix_seconds=started,expires_unix_seconds=started+90000))+'\n')
    qr=control/'local_quota_review.json';qr.write_text(json.dumps(dict(execution_kind='LOCAL_HEADNODE',storage_marker_path=str(marker),snapshot_root=str(control/'quota_snapshots')))+'\n')
    plan=dict(plan,node='sonmi',workers=WORKERS,pending=2*WORKERS,plan_path=args.plan,
      quota_provider_identity_reference=C.P.pin(qi),quota_provider_review_reference=C.P.pin(qr))
    request=dict(schema='ACTUAL_LOCAL_HEAD_D4_REQUEST_V1',node='sonmi',cpus=WORKERS,wall_seconds=86400,
      memory_policy='OBSERVED_LOCAL_PROCESS_NO_SLURM_ALLOCATION',pilot=False,
      estimated_peak_output_bytes=plan['whole_output_cap_bytes'],data_references=plan['data_references'],
      local_quota_identity_reference=C.P.pin(qi),execution_kind='LOCAL_HEADNODE')
    rq=control/'actual_local_request.json';rq.write_text(json.dumps(request,sort_keys=True)+'\n')
    proof=dict(schema='ACTUAL_USER_AUTHORIZED_HEADNODE_D4_PROCESS_PROOF_V1',execution_kind='LOCAL_HEADNODE',
      execution_id=identity,job_id=identity,legacy_job_id_field_is_local_execution_id=True,Slurm_job_id=None,
      pid=pid,uid=os.getuid(),start_ticks=ticks,node='sonmi',actual_affinity=sorted(os.sched_getaffinity(0)),
      local_started_unix_seconds=started,request=request,request_reference=C.P.pin(rq),
      observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),root_observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    pp=control/'actual_local_process_proof.json';pp.write_text(json.dumps(proof,sort_keys=True)+'\n')
    plan['startup_proof_path']=str(pp)
    plan['source_references']=C.unique([*plan['source_references'],C.P.pin(qi),C.P.pin(qr),C.P.pin(pp)])
    io=HeadIO();io.configure(plan);root=io.new_root(plan['output_directory']);budget=None
    geometry=types.SimpleNamespace(**{name:getattr(G,name)for name in ('schema_header','prepare','cohort','build','metadata_children','ELIGIBILITY','STATISTICS','COVERAGE')})
    geometry.COVERAGE=Coverage();namespace=dict(Original.execute.__globals__,C=C,G=geometry,I=io,V=geometry.COVERAGE)
    execute=types.FunctionType(Original.execute.__code__,namespace,Original.execute.__name__,Original.execute.__defaults__,Original.execute.__closure__)
    try:
        gate=Parent.fixtures(root);io.configure(plan);budget=LocalBudget(plan,proof,root);budget.check(force=True)
        result=execute(plan,proof,root,gate,budget);receipt=io.load_data(result,8<<20)
        C.need(not receipt['held'] and receipt['errors']==[] and receipt['independent_numeric_replay_equal'] is True
          and len(receipt['numeric_repetitions'])==2,'ACTUAL_LOCAL_COMPLETE_D4_TWO_EQUAL_TRAIN_REPLAYS')
        return 0
    except BaseException as error:
        failure=control/'local_failure.json';failure.write_text(json.dumps(dict(error=repr(error),traceback=traceback.format_exc(),execution_id=identity,actual_pid=pid,no_fake_Slurm_job_or_C0=True))+'\n');raise
    finally:
        if budget is not None:budget.close()

if __name__=='__main__':raise SystemExit(main())
