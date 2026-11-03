"""Original live guards, with one declared already-allocated checkpoint credit."""
import fcntl,math,pathlib,stat,threading,types
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I
from workflows.data_v1_final.labels.existing_sprime_native_pilot_day_v1 import geometry as NATIVE
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v3 import resource_census as RC
from workflows.data_v1_final.execution import finite_quota_observation_guard_v2 as QG

class NonDatabaseRefs:
    def __init__(self,path):self.path=str(path)
    def values(self):return [r for r in list(I.ALLOWED.values()) if r['path']!=self.path]

def shape(source,path):
    C.need(source['path']==str(path) and source['cap_bytes']==56<<30 and source['uid']==1278
      and all(type(source[k])is int and source[k]>=0 for k in ('cap_bytes','uid','device','inode','initial_credited_allocated_bytes'))
      and source['inode']>0 and 0<source['initial_credited_allocated_bytes']<=source['cap_bytes']
      and source['device_identity_is_endpoint_local_not_compared_across_login_and_NFS'] is True
      and source['same_storage_as_validated_provider_marker'] is True,
      'ONE_DECLARED5455_CHECKPOINT_STORAGE_CREDIT_NO_DATA_ADOPTION')
    return C.reference(source['initial_observation_reference'])

def initial_inventory(source,observation):
    C.need(observation['schema']=='ROOT_ACTIVE_OUTPUT_ALLOCATED_BYTES_METADATA_OBSERVATION_V1'
      and observation['database_bodies_read_or_hashed'] is False
      and observation['scientific_adoption_or_C0_claimed'] is False,'CHECKPOINT_ALLOCATION_METADATA_ONLY')
    timestamp=observation['observed_unix_seconds']
    C.need(type(timestamp) in (int,float) and math.isfinite(timestamp) and timestamp>0,
      'FINITE_ACTUAL_INITIAL_INVENTORY_TIME')
    rows=[r for r in observation['files'] if r['path']==source['path']]
    C.need(len(rows)==1,'ONE_CHECKPOINT_ALLOCATION_OBSERVATION');row=rows[0]
    C.need(row['registered_parent']=='metadata_partial5455'
      and all(row[k]==source[k] for k in ('device','inode','uid'))
      and type(row['size']) is int and row['size']>=0
      and type(row['allocated_bytes']) is int and type(row['allocated_bytes_after_quota']) is int
      and 0<=source['initial_credited_allocated_bytes']<=row['allocated_bytes']<=row['allocated_bytes_after_quota']<=source['cap_bytes']
      and row['source_database_body_not_read'] is True and row['mutable_not_scientific_adoption'] is True,
      'EXACT_CLOSED_CHECKPOINT_ALLOCATED_BLOCKS_ALREADY_CHARGED')
    return dict(observed_unix_seconds=timestamp,
      allocated_bytes=source['initial_credited_allocated_bytes'],size=row['size'],
      high_water_allocated_bytes=row['allocated_bytes_after_quota'],
      origin='ROOT_REVIEWED_CHECKPOINT_METADATA_INVENTORY',
      device=row['device'],inode=row['inode'],uid=row['uid'])

class BudgetMath:
    def __init__(self,budget):self.budget=budget
    def __getattr__(self,name):return getattr(I.C,name)
    def remaining_future(self,total,cap,closed):
        external=self.budget.total+self.budget.external_initial_credit-total
        C.need(type(external)is int and 0<=external<=cap,'EXACT_CHECKPOINT_CREDIT_IN_CURRENT_FULL_CAP')
        return I.C.remaining_future(total,cap-external,closed)

class CurrentFuture:
    def __init__(self,budget):self.budget=budget
    def __enter__(self):
        self.stream=(C.RUN/'control/root_current_all_future_ledger_v1.lock').open('rb')
        fcntl.flock(self.stream,fcntl.LOCK_SH)
        try:
            p=C.meta(C.P.pin(C.RUN/'control/root_current_all_future_ledger_v1.json'))
            r=C.meta(p['review_reference'])
            C.need(p['schema']=='ROOT_CURRENT_ALL_FUTURE_METADATA_POINTER_V1'
              and r['reviewer']=='root' and r['status'].startswith('APPROVED')
              and r['total_future_reserved_bytes']==p['total_future_reserved_bytes'],
              'CURRENT_SIGNED_ALL_FUTURES_NOT_STALE_INITIAL_TOTAL')
            C.need(len(self.budget.external)==1
              and self.budget.external[0]['source']['path']==str(self.budget.checkpoint_path)
              and self.budget.external_initial_credit==self.budget.initial_credit,
              'ONLY_THIS_EXPLICIT_CHECKPOINT_CREDIT')
            self.budget.total=p['total_future_reserved_bytes'];return self
        except BaseException:
            self.stream.close();raise
    def __exit__(self,*args):self.stream.close()

class ResourceBudget(I.Budget):
    record_census=NATIVE.ResourceBudget.record_census
    def __init__(self,plan,proof,root):
        self.root=pathlib.Path(root);self.checkpoint_path=self.root/'actual_input_children/geometry.sqlite'
        carve=C.meta(plan['root_carveout_review_reference'])
        C.need(len(carve['registered_external_allocated_credit_sources'])==1,'ONE_CURRENT_CHECKPOINT_SOURCE')
        self.initial_credit=carve['registered_external_allocated_credit_sources'][0]['initial_credited_allocated_bytes']
        self.census_lock=threading.RLock();self.census_sequence=0
        def census(path):
            C.need(pathlib.Path(path)==self.root,'CURRENT_PARENT_OUTPUT_CENSUS_ONLY')
            with self.census_lock:return NATIVE.retry_whole_census(RC.unique_bytes,path,self.record_census)
        self.native_census=census
        old=NATIVE.budget_function('_observe',census)
        g=dict(old.__globals__,QG=QG,C=BudgetMath(self),ALLOWED=NonDatabaseRefs(self.checkpoint_path))
        self.native_observe=types.FunctionType(old.__code__,g,old.__name__,old.__defaults__,old.__closure__)
        self.native_check=NATIVE.budget_function('check',census)
        init=I.Budget.__init__
        namespace=dict(init.__globals__,external_source_shape=lambda s:shape(s,self.checkpoint_path),
          initial_external_inventory=initial_inventory)
        types.FunctionType(init.__code__,namespace,init.__name__,init.__defaults__,init.__closure__)(self,plan,proof,root)
    def _observe(self):
        with CurrentFuture(self):self.native_observe(self)
        monitor=I.R.MONITOR
        if monitor is not None:
            try:
                observed=I.R.process_tree(monitor.pid,monitor.start)
                if observed['tree_rss_bytes']>64<<30:I.R.mark_stop('FAST55K_TREE_RSS64GIB_SOFT_CAP',observed)
            except Exception as error:I.R.mark_stop('FAST55K_TREE_RSS_OBSERVATION_UNKNOWN',{'error':repr(error)})
    def check(self,*,force=False,dispatch=True):return self.native_check(self,force=force,dispatch=dispatch)

def proof():
    class State:total=436;external_initial_credit=33
    m=BudgetMath(State())
    # Other405 + full64 - baseline33. Current DB37 + separately closed8
    # must leave other405 +19, without crediting the same DB twice.
    assert m.remaining_future(432,64,8)==424
    assert m.remaining_future(432,64,100)==405
    assert m.remaining_future(436,64,0)==436
    return dict(original_live_quota_RSS_wall_and_floor_functions_retained=True,
      one_checkpoint_lstat_only_with_original_timestamp_and_no_shrink_guards=True,
      checkpoint_excluded_from_second_closed_output_credit=True,
      full_cap_and_already_charged_baseline_not_double_counted=True)
