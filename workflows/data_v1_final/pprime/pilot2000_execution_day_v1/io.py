"""Stable records, explicit role reservations and one actual live Parent."""
import json,os,pathlib,socket,stat,time
from workflows.data_v1_final.pprime.strict_numerics15_qa_v1.io import Store,claim_create,ticks
from workflows.data_v1_final.pprime.pilot2000_prepare_day_v1 import prepare as Preparation
from . import contract as C
Q=C.Q;I=C.M.I
class Budget(Preparation.Budget):
    def __init__(self,plan,proof,out,roles,parent_store):
        # Preparation's initializer binds its own scope. Reuse the ORIGINAL
        # observation methods, with this scope's actual carveout and Client.
        I.OriginalBudget.__init__(self,plan,proof,out);self.roles=roles;self.parent_store=parent_store;self.carve=C.meta(plan['root_carveout_review_reference'])
        C.M.carveout(self.carve,{'scope_key':C.KEY,'node':proof['request']['node'],'resource_authority_reference':plan['resource_authority_reference'],'estimated_peak_output_bytes':self.cap})
        self.total=self.carve['total_future_reserved_bytes'];C.parameters(plan['node'],plan['precision_mode'])
        if plan['node']=='compute-0-13':client=C.M.Client
        elif plan['node']=='compute-0-19':
            from workflows.data_v1_final.execution.cpu_analysis_cpu19_v1.quota_provider import Client
            client=Client
        else:
            from workflows.data_v1_final.execution.cpu_analysis_day_v1.quota_provider import Client
            client=Client
        self.client=client(plan['quota_provider_review_reference'],proof['request']);self.next_quota=0;self.quota=None;self.written=0
        self.quota_guard_events=out/'quota_guard_events';self.quota_guard_events.mkdir(mode=0o700);self.quota_guard_event_references=[]
        self.quota_guard_store=Store(self.quota_guard_events,64<<20)
        cost=C.meta(plan['cost_decision_reference'])
        self.user_pilot_estimate=cost.get('pilot_estimated_allocated_core_seconds')
        self.prior_pilot_core_seconds=cost['prior_preparation_and_source_allocated_core_seconds']
        C.need(type(self.prior_pilot_core_seconds)is int and self.prior_pilot_core_seconds>=0,'REAL_PRIOR_PILOT_COSTS_RETAINED')
        C.need(type(self.user_pilot_estimate) in (int,float) and self.user_pilot_estimate>0 and cost.get('confirmation_required_above_estimate_multiple')==2,'EXPLICIT_USER_TWO_TIMES_COMPUTE_POLICY')
    def check(self,dispatch=True,force=False):
        super().check(dispatch=dispatch,force=force)
        if dispatch and self.prior_pilot_core_seconds+16*(self.elapsed+time.monotonic()-self.start)>2*self.user_pilot_estimate:
            self.stop_new=True
            raise ValueError('USER_CONFIRMATION_REQUIRED_COMPUTE_ABOVE_TWO_TIMES_PILOT_ESTIMATE_NO_NEW_DISPATCH')
    def record(self,event):
        C.need(len(C.O.canonical(event))<=256<<10 and len(self.quota_guard_event_references)<6400,
          'FINITE_PERSISTENT_QUOTA_EVIDENCE_NOT_RECORD_ONLY_SUCCESS')
        ref=self.quota_guard_store.json(self.quota_guard_events/('event_%06d.json'%len(self.quota_guard_event_references)),event)
        self.quota_guard_event_references.append(ref)
    def used(self):
        # The original resource observer calls this IO seam. Charge full active
        # and UNKNOWN roles; never stat a concurrently mutating output tree.
        C.need(self.parent_store.charged<C.PARENT_CAP and self.roles.bound()<=C.CAP,'EXACT_PREPAID_PRIVATE_AND_PARENT_ROLES')
        return self.roles.bound()
    def report(self):
        return {'reserved_output_role_bytes':self.roles.bound(),'parent_store_charged_bytes':self.parent_store.charged,
          'bound_is_not_actual_output_measurement':True,'active_output_tree_stat_calls':0,
          'RSS_scope':'ORIGINAL_PARENT_AND_DIRECT_CHILD_OBSERVER_NOT_ALL_NATIVE_DESCENDANTS',
          'RSS_peak_bytes':self.peak,'minimum_MemAvailable_bytes':self.minimum,'stop_new':self.stop_new,
          'last_actual_quota_observation':self.quota,'all_future_bytes_counted_once':self.total,
          'resource_event_passed_to_original_native':False,'signals_sent':False}
class Roles:
    def __init__(self):self.active=set();self.closed={};self.unknown=set()
    def bound(self):return C.PARENT_CAP+len(self.active|self.unknown)*C.WORKER_CAP+sum(self.closed.values())
    def can_start(self):return len(self.active)<16 and self.bound()+C.WORKER_CAP<=C.CAP
    def start(self,key):
        C.need(self.can_start() and key not in self.active|self.unknown|set(self.closed),'ONLY_UNCLAIMED_FITTING_RECORD_ROLE');self.active.add(key)
    def settle(self,key,actual,valid):
        C.need(key in self.active and type(actual)is int and 0<=actual<=C.WORKER_CAP,'EXACT_RECORD_ROLE_SETTLEMENT')
        self.active.remove(key)
        if valid:self.closed[key]=actual
        else:self.unknown.add(key)
        C.need(self.bound()<=C.CAP,'PRESERVE_UNKNOWN_FULL_PARTITION_WITHIN_CAP')
def source_session(plan_reference,plan,proof):
    return {'job_id':str(proof['job_id']),'node':proof['request']['node'],'boot_id':proof['boot_id'],'parent_pid':os.getpid(),
      'parent_ticks':ticks(os.getpid()),'plan_reference':plan_reference,'source_references':plan['source_references'],
      'execution_root_review_reference':proof['request']['scope']['review']}
def continuation(session,*,check_sources=False):
    C.need(os.getuid()==1278 and os.getppid()==session['parent_pid'] and ticks(os.getppid())==session['parent_ticks']
      and os.environ.get('SLURM_JOB_ID')==session['job_id'] and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
      and socket.gethostname().split('.')[0]==session['node'] and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==session['boot_id'],
      'SAME_LIVE_ADMITTED_PARENT_NOT_FAKE_FRESHNESS_OR_CHILD_AUTHORITY')
    if check_sources:
        for ref in session['source_references']:C.need(Q.pin(ref['path'])==ref,'EXACT_FROZEN_WORKER_SOURCE_AND_AUTHORITY')
    return C.meta(session['plan_reference'])
def body(ref,declared,budget):
    with I.held(C.P.triple(ref),[Q.ROOT/'artifacts'],declared) as (stream,_):budget.check(dispatch=False);return stream.read()
def value(ref,declared,budget):return C.O.read_staging(body(ref,declared,budget))
def prepared_body(plan,header,declared,budget):
    value=json.loads(body(plan['prepared2000_reference'],declared,budget))
    C.need(value['schema']=='PPRIME_ORIGINAL2000_ZERO_INVOKE_PREPARED_V1'
      and value['status']=='ACTUAL2000_INPUTS_CLOSED_NOT_QM_AUTHORITY','CPU_ACTUAL_PREPARED_BODY')
    for key in ('job_id','uid','node','plan_reference','startup_proof_reference','fixtures_reference','MIDs','UFF_geometries',
      'maximum_formal_native_calls','all12_tasks','original_protocol_reference','candidate_protocol_reference','original_pairs_reference',
      'orders_and_lineage_reference','record_input_hashes_reference','audit_membership_reference','stable_source_audit_reference',
      'execution_assets_whole_SHA_count','software_original_count','original_initialize_calls','candidate_initialize_calls',
      'native_invoke_attempts','new_QM_UFF_calls','production_once_written','production_precision_choice_approved','scientific_PASS'):
        C.need(value[key]==header[key],'CPU_PREPARED_BODY_EQUALS_PURE_PRODUCER_HEADER:'+key)
    C.need(value['ordinary_Body_asset_count']==432,'CPU_PREPARED_R2_432_ORDINARY_ASSETS')
    return value
def quiescent(folder):
    n=0
    for p in pathlib.Path(folder).rglob('*'):
        st=p.lstat();C.need(st.st_uid==1278 and not stat.S_ISLNK(st.st_mode),'OWN_STABLE_PRIVATE_OUTPUT')
        if stat.S_ISREG(st.st_mode):C.need(not p.name.endswith(('-journal','-wal','-shm')),'NO_LIVE_SQLITE_SIDECAR_AT_SETTLEMENT');n+=st.st_size
    return n
def record_hashes(records):
    expected={}
    for row in records:
        rid=row['record_id'];C.need(rid not in expected and len(row['hashes'])==12,'ALL2000_UNIQUE_INPUT_HASH_ROWS');expected[rid]=row
    C.need(len(expected)==2000,'EXACT_PREPARED_INPUT_HASH_RECORD_CENSUS');return expected
