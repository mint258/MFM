"""Original readonly IO/role accounting, one real day Parent, no mutable-tree scan."""
import json,os,pathlib,socket,time,types
from workflows.data_v1_final.pprime.pilot2000_execution_day_v1 import io as Original
from . import contract as C
Q=C.Q;I=Original.I;Preparation=Original.Preparation
Store=Original.Store;claim_create=Original.claim_create;ticks=Original.ticks;quiescent=Original.quiescent
body=Original.body;value=Original.value

class Roles(Original.Roles):
    def __init__(self):super().__init__();self.export_bytes=0
    def bound(self):return C.PARENT_CAP+self.export_bytes+len(self.active|self.unknown)*C.WORKER_CAP+sum(self.closed.values())
    def can_start(self):return len(self.active)<16 and self.bound()+C.WORKER_CAP<=C.CAP
    def add_export(self,n):
        C.need(type(n)is int and n>=0,'EXACT_CLOSED_EXPORT_BYTES');self.export_bytes+=n
        C.need(self.bound()<=C.CAP,'FULL_CLOSED_EXPORT_PLUS_RESERVED_RAW_ROLES')

class Budget(Preparation.Budget):
    def __init__(self,plan,proof,out,roles,parent_store):
        I.OriginalBudget.__init__(self,plan,proof,out);self.roles=roles;self.parent_store=parent_store
        self.carve=C.meta(plan['root_carveout_review_reference'])
        C.M.carveout(self.carve,{'scope_key':C.KEY,'node':plan['node'],'resource_authority_reference':plan['resource_authority_reference'],'estimated_peak_output_bytes':C.CAP})
        self.total=self.carve['total_future_reserved_bytes'];node=plan['node']
        if node=='compute-0-13':Client=C.M.Client
        elif node=='compute-0-19':
            from workflows.data_v1_final.execution.cpu_analysis_cpu19_v1.quota_provider import Client
        elif node in ('compute-0-14','compute-0-18'):
            from workflows.data_v1_final.execution.cpu_analysis_day_v1.quota_provider import Client
        else:
            from workflows.data_v1_final.execution.cpu_analysis_general_nodes_v1.quota_provider import Client
        self.client=Client(plan['quota_provider_review_reference'],proof['request']);self.next_quota=0;self.quota=None;self.written=0
        self.quota_guard_events=out/'quota_guard_events';self.quota_guard_events.mkdir();self.quota_guard_event_references=[]
        self.quota_guard_store=Store(self.quota_guard_events,64<<20);self.forecast_records=C.MAX_RECORDS
    def record(self,event):
        C.need(len(C.O.canonical(event))<=256<<10 and len(self.quota_guard_event_references)<6400,'FINITE_QUOTA_EVENT')
        ref=self.quota_guard_store.json(self.quota_guard_events/('event_%06d.json'%len(self.quota_guard_event_references)),event)
        self.quota_guard_event_references.append(ref)
    def used(self):
        C.need(self.parent_store.charged<C.PARENT_CAP and self.roles.bound()<=C.CAP,'PREPAID_PREP_METADATA_EXPORT_ACTIVE_UNKNOWN_ROLES')
        return self.roles.bound()
    def check(self,dispatch=True,force=False):
        super().check(dispatch=dispatch,force=force)
        if dispatch and 16*(self.elapsed+time.monotonic()-self.start)>2*self.forecast_records*(9.328+2.144):
            self.stop_new=True;raise ValueError('USER_CONFIRMATION_REQUIRED_ABOVE_TWO_TIMES_ACTUAL_SCOPE_FORECAST')
    def report(self):
        return {'reserved_output_role_bytes':self.roles.bound(),'parent_store_charged_bytes':self.parent_store.charged,
          'bound_is_not_actual_output_measurement':True,'active_output_tree_stat_calls':0,'RSS_peak_bytes':self.peak,
          'RSS_scope':'ORIGINAL_PARENT_AND_DIRECT_CHILD_OBSERVER_NOT_ALL_NATIVE_DESCENDANTS',
          'minimum_MemAvailable_bytes':self.minimum,'stop_new':self.stop_new,'last_actual_quota_observation':self.quota,
          'all_future_bytes_counted_once':self.total,'forecast_records':self.forecast_records,
          'execution_forecast_core_seconds_per_record':9.328,'preparation_Source_forecast_core_seconds_per_record':2.144,'signals_sent':False}

def source_session(plan_reference,plan,proof):
    return {'job_id':str(proof['job_id']),'node':proof['request']['node'],'boot_id':proof['boot_id'],'parent_pid':os.getpid(),
      'parent_ticks':ticks(os.getpid()),'plan_reference':plan_reference,'source_references':plan['source_references'],
      'execution_root_review_reference':proof['request']['scope']['review']}

def continuation(session,*,check_sources=False):
    C.need(os.getuid()==1278 and os.getppid()==session['parent_pid'] and ticks(os.getppid())==session['parent_ticks']
      and os.environ.get('SLURM_JOB_ID')==session['job_id'] and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
      and socket.gethostname().split('.')[0]==session['node'] and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==session['boot_id'],
      'SAME_ACTUAL_LIVE_PARENT_PID_TICKS_BOOT_JOB_NODE')
    if check_sources:
        for r in session['source_references']:C.need(Q.pin(r['path'])==r,'ORIGINAL_AND_NEW_SOURCE_AUTHORITY_PINS')
    return C.meta(session['plan_reference'])
