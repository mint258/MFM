"""Original finite day Budget/IO objects with explicit closed-parent roots."""
import copy,json,os,pathlib,sqlite3,threading,time,types
from workflows.data_v1_final.execution import finite_quota_observation_guard_v2 as QG2
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as B
from workflows.data_v1_final.export.family_export_day_v1 import io as F
from workflows.data_v1_final.labels.existing_sprime_pilot_general_cpu_day_v1 import run as General
from workflows.data_v1_final.labels.existing_sprime_native_pilot_day_v1 import geometry as NativeCensus
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v3 import resource_census as ResourceCensus
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v13.resource import user_quota_observer
identity=B.S.identity;pin=B.pin;require=B.require;load_data=B.load_data;allow=B.allow
ACTIVE_CENSUS=None
READER_CONTEXT=None
class CensusContext:
    """One actual parent; original complete inventory, bounded FNF rereads only."""
    record_census=NativeCensus.ResourceBudget.record_census
    def __init__(self,root):
        self.root=pathlib.Path(root);self.census_lock=threading.RLock();self.census_sequence=0
    def __call__(self,path):
        C.need(pathlib.Path(path)==self.root,'ONLY_ACTUAL_CURRENT_PARENT_OUTPUT_CENSUS')
        with self.census_lock:return NativeCensus.retry_whole_census(ResourceCensus.unique_bytes,path,self.record_census)
def private_io_function(original,census,save_function=None,write_text_function=None,*,stop_evidence=False):
    """Original entire function code/defaults; explicit private IO bindings only."""
    namespace=dict(original.__globals__);namespace['unique_bytes']=census
    # Same deployed D4 correction: durable census/fsync precedes the 1.1s wait.
    # Only the private observation binding changes; original Client guards stay.
    if 'QG' in namespace:namespace['QG']=QG2
    if save_function is not None:namespace['save']=save_function
    if write_text_function is not None:namespace['write_text']=write_text_function
    if stop_evidence:namespace['R']=NativeCensus.ResourceStopEvidence(namespace['R'])
    function=types.FunctionType(original.__code__,namespace,original.__name__,original.__defaults__,original.__closure__)
    function.__kwdefaults__=original.__kwdefaults__;return function
def save(path,value):
    # Source3 precedes the resource Budget and parallel scientific writers.
    # Once Budget starts, ordinary reports use the same bounded full census.
    return (B.save if ACTIVE_CENSUS is None else private_io_function(B.save,ACTIVE_CENSUS))(path,value)
def write_text(path,value):
    return (B.write_text if ACTIVE_CENSUS is None else private_io_function(B.write_text,ACTIVE_CENSUS))(path,value)
class Budget(B.Budget):
    """Original quota/wall/immutable checks, private complete-census IO seam."""
    def __init__(self,plan,proof,root):
        global ACTIVE_CENSUS
        carve=C.meta(plan['root_carveout_review_reference']);policy_ref=carve.get('temporary_account_quota_floor_reference')
        self.account_floor_bytes=200000000000
        if policy_ref is not None:
            policy=C.meta(policy_ref)
            C.need(policy['status']=='USER_AUTHORIZED_TEMPORARY' and policy['scope']=='ACCOUNT_FREE_AFTER_ALL_FUTURES'
              and policy['account_quota_floor_bytes']==carve['account_quota_floor_bytes']==100000000000,'EXPLICIT_USER100GB_ACCOUNT_POLICY')
            self.account_floor_bytes=100000000000
        self.census_context=CensusContext(root);ACTIVE_CENSUS=self.census_context;self.next_row_census=0.
        safe_save=private_io_function(B.save,self.census_context);safe_text=private_io_function(B.write_text,self.census_context)
        self.parent_observe=private_io_function(B.Budget._observe,self.census_context,safe_save,safe_text,stop_evidence=True)
        if self.account_floor_bytes==100000000000:self.parent_observe=user_quota_observer(self.parent_observe)
        self.active_domain_math=ActiveDomainMath(self,self.parent_observe.__globals__['C'])
        self.parent_observe.__globals__['C']=self.active_domain_math
        self.parent_observe.__globals__['ALLOWED']=DomainExcludedRefs(self.active_domain_math.path)
        self.parent_check=private_io_function(B.Budget.check,self.census_context,safe_save,safe_text)
        self.parent_quota_event=private_io_function(B.Budget.record_quota_event,self.census_context,safe_save,safe_text)
        original_init=private_io_function(B.Budget.__init__,self.census_context,safe_save,safe_text)
        if plan.get('queue_startup_mode')=='QUEUED_REAL_ALLOCATION_ROOT_PROVIDER_ON_START':
            from workflows.data_v1_final.execution.cpu_analysis_general_nodes_v1 import quota_provider as queued_provider
            original_init.__globals__['QP']=queued_provider
        original_init(self,plan,proof,root)
    def _observe(self):
        with ResourceCensus.current_root_future(self):return self.parent_observe(self)
    def check(self,*,force=False,dispatch=True):
        if force:self.observe()
        if dispatch:C.need(not B.stop_requested(),'SOFT_RESOURCE_STOP_PILOT_NO_NEW_WORK_NATURAL_DRAIN')
        if force or time.monotonic()>=self.next_row_census:
            C.need(self.census_context(self.root)+(256<<20)<self.plan['whole_output_cap_bytes'],'FINITE_PILOT_WHOLE_OUTPUT_CAP')
            self.next_row_census=time.monotonic()+1.
    def record_quota_event(self,event):return self.parent_quota_event(self,event)
    def close(self):
        super().close()
        save(self.root/'domain_output_resource_credit.json',self.active_domain_math.report())
def configure(plan,old):
    global ACTIVE_CENSUS,READER_CONTEXT
    ACTIVE_CENSUS=None
    READER_CONTEXT={'producer_plan':copy.deepcopy(old),'bounded_review_reference':plan['bounded_export_review_reference'],
      'actual_parent_manifest_reference':plan['pilot_parent_manifest_reference'],'source_references':plan['source_references']}
    cfg=copy.deepcopy(plan);cfg['cache_transitive_output_origins']=[]
    cfg['accepted_prior_output_roots']=[{'manifest_reference':plan['pilot_parent_manifest_reference'],'output_root':old['output_directory']}]
    B.configure(cfg)
    if plan.get('queue_startup_mode')=='USER_UNLIMITED_CPU21_D3_20261103':
        from .unlimited_budget import enable_unlimited_worker_resources
        enable_unlimited_worker_resources()
def add(r,root=None):return B.allow(C.reference(r),origin=root) if root is not None else B.allow(C.reference(r))
def derived(r,root):add(r,root);return r
def data(ref,root=None,limit=512<<20):
    if root is not None:add(ref,root)
    return load_data(ref,limit)
def batches(ref,check,columns=None):
    import pyarrow.parquet as pq
    p=require(ref);before=identity(p);f=p.open('rb');pf=pq.ParquetFile(f,pre_buffer=False)
    try:
        for batch in pf.iter_batches(batch_size=256,columns=columns,use_threads=False):check();C.need(batch.nbytes<=128<<20,'BOUNDED_ACTUAL_PILOT_TABLE_BATCH');yield batch
    finally:pf.close();f.close();C.need(identity(p)==before,'PILOT_TABLE_CURRENT_STABLE_FD_FRAME')
def append(path,value):
    raw=(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode();C.need(len(raw)<=2<<20,'BOUNDED_DURABLE_OPERATION_EVENT')
    with pathlib.Path(path).open('ab') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def connect(path,readonly=False):
    db=sqlite3.connect(pathlib.Path(path).absolute().as_uri()+'?mode=ro&immutable=1',uri=True) if readonly else sqlite3.connect(path)
    db.row_factory=sqlite3.Row
    if not readonly:db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA cache_size=-16384')
    return db
def fast_parts_root(coverage,producer_root,reviewed_roots,job_id):
    root=pathlib.Path(producer_root);parts=root/'typed_coverage'
    oldroot=C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_fast55k_pilot_day_v1/day01_cpu17_v1_pilot_provisional'
    C.need(root.parent in (C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_fast55k_resume_v1',
      C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_fast55k_resume_v2',
      C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_fast55k_resume_v3')
      and type(reviewed_roots)is list and str(root)in reviewed_roots and str(oldroot)in reviewed_roots
      and all(type(r)is str and pathlib.Path(r).is_absolute()and '..'not in pathlib.Path(r).parts for r in reviewed_roots),
      'BOTH_EXACT_NEW_COMPLETE_RESUME_AND_OLD5232_PARTIAL_ROOTS_REVIEWED')
    C.need(str(coverage['job_id'])==str(job_id)and str(job_id)not in ('4525232','4525251')and coverage['mode']=='bounded_pilot55k'
      and coverage['fast_IO_not_new_science']is True and coverage['workers']==16 and coverage['source_batch_rows']==16
      and coverage['old_cache_written']is False and type(coverage['readback_closed_parts'])is int and coverage['readback_closed_parts']>=0
      and pathlib.Path(C.reference(coverage['parts_catalog'])['path']).parent==parts
      and pathlib.Path(C.reference(coverage['current_parent_typed_origin_reference'])['path'])==parts/'current_parent_typed_origin.json'
      and pathlib.Path(C.reference(coverage['readonly_old_typed_origin_reference'])['path'])==parts/'readback_old_selected_typed_origin.json'
      and pathlib.Path(C.reference(coverage['readonly_old_catalog_reference'])['path'])==oldroot/'typed_coverage/numeric_catalog.sqlite'
      and pathlib.Path(C.reference(coverage['readonly_old_selected_owner_reference'])['path'])==oldroot/'typed_coverage/selected_owner.sqlite'
      and 'original_parts_output_root'not in coverage,'NEW_COMPLETE_RESUME_TWO_ORIGINS_NOT_OLD_PARTIAL_OR_FAILED_SOURCE_PARENT')
    return str(parts)
def configure_reader(cfg,coverage,oldroot):
    cfg=copy.deepcopy(cfg);C.need(READER_CONTEXT is not None,'EXACT_ADMITTED_FAST55K_READER_CONTEXT_REQUIRED')
    producer=READER_CONTEXT['producer_plan'];review=C.meta(READER_CONTEXT['bounded_review_reference'])
    actual=C.meta(READER_CONTEXT['actual_parent_manifest_reference'])
    C.need(producer['schema']=='EXISTING_SPRIME_FAST55K_RESUME_PLAN_V1'and producer['output_directory']==str(oldroot)
      and actual['schema']=='EXISTING_SPRIME_FAST55K_PILOT_DAY_RECEIPT_V1'
      and actual['status']=='PROVISIONAL55K_FAST_TYPED_NATIVE_RANDOM_AND_TRAIN_D4_COMPLETE_PENDING_ACTUAL_C0_ROOT_SEAL',
      'SAME_ACTUAL_COMPLETE_RESUME_PARENT_NOT_OLD5232_PARTIAL')
    parts_root=fast_parts_root(coverage,oldroot,review['transitive_closed_output_roots'],actual['job_id'])
    for k in ('canonical_index','eligibility_reference','source_inventory_reference','field_map_reference','logical_group_plan_reference','coverage_reference'):
        if k in cfg and cfg[k]['path']not in B.ALLOWED:add(cfg[k],oldroot)if pathlib.Path(oldroot)in pathlib.Path(cfg[k]['path']).parents else C.need(False,'STATIC_READER_REF_MUST_BE_DECLARED:'+k)
    add(coverage['parts_catalog'],oldroot);add(coverage['current_parent_typed_origin_reference'],parts_root)
    B.ORIGINS[coverage['current_parent_typed_origin_reference']['path']]={'manifest_reference':coverage['current_parent_typed_origin_reference'],'output_root':parts_root}
    require(coverage['current_parent_typed_origin_reference']);require(coverage['parts_catalog'])
    ro=coverage['readonly_old_typed_origin_reference'];add(ro,parts_root);body=load_data(ro,8<<20)
    C.need(body['schema']=='CURRENT_PARENT_SELECTED_TYPED_ORIGIN_V1'and body['status']=='ACTUAL_CLOSED_SUBSET_WITHIN_PARENT_NOT_CHILD_C0'
      and str(body['job_id'])==str(actual['job_id'])and body['readonly_C0_parent_job_id']=='4525232'and body['closed_old_parts_written']is False
      and body['old_catalog_reference']==coverage['readonly_old_catalog_reference']
      and body['old_selected_owner_reference']==coverage['readonly_old_selected_owner_reference']
      and body['readback_closed_parts']==coverage['readback_closed_parts'],'EXACT_CURRENT_RESUME_READBACK_CERTIFICATE_NOT_OLD_D4_ACCEPTANCE')
    old_parts=str(C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_fast55k_pilot_day_v1/day01_cpu17_v1_pilot_provisional/typed_coverage')
    B.ORIGINS[ro['path']]={'manifest_reference':ro,'output_root':old_parts}
    declared={r['manifest_reference']['path']:(r['manifest_reference'],r['output_root'])for r in cfg['cache_transitive_output_origins']}
    required={ro['path']:(ro,old_parts),coverage['current_parent_typed_origin_reference']['path']:(coverage['current_parent_typed_origin_reference'],parts_root)}
    C.need(all(declared.get(k)==v for k,v in required.items()),'SAVED_CPU_READER_CONFIG_RETAINS_BOTH_ACTUAL_CLOSED_CACHE_ORIGINS')
    cfg['catalog_frame']=identity(coverage['parts_catalog']['path']);return cfg

class DomainExcludedRefs:
    """This one mutable DB must not also receive immutable-output credit."""
    def __init__(self,path):self.path=str(path)
    def values(self):return [r for r in list(B.ALLOWED.values()) if r['path']!=self.path]

def remaining_with_own_credit(original,total,cap,credit,closed):
    C.need(all(type(v)is int and v>=0 for v in (total,cap,credit,closed))
      and credit<=cap and total>=cap,'OWN_ACTIVE_DOMAIN_CREDIT_WITHIN_ORIGINAL_FULL_CAP')
    return original.remaining_future(total-credit,cap-credit,closed)

class ActiveDomainMath:
    """Original resource metadata/timestamps, for this parent's exact domain.sqlite."""
    def __init__(self,budget,original):
        self.budget=budget;self.original=original
        self.path=budget.census_context.root/'domain.sqlite'
        self.samples=[];self.last=None;self.last_report=None
    def __getattr__(self,name):return getattr(self.original,name)
    def remaining_future(self,total,cap,closed):
        if not self.path.exists():
            C.need(self.last is None,'CURRENT_DOMAIN_DB_DISAPPEARED_NO_CREDIT_OR_RETRY')
            return self.original.remaining_future(total,cap,closed)
        frame=self.path.lstat();marker=self.budget.quota['cpu_marker']['stat']
        C.need(marker['uid']==1278,'ORIGINAL_VALIDATED_SHARED_STORAGE_MARKER_UID')
        expected=dict(uid=1278,inode=frame.st_ino if self.last is None else self.last['inode'],cap_bytes=cap)
        previous=dict(allocated_bytes=0,size=0) if self.last is None else self.last
        current=B.external_metadata_inventory(self.path,expected,marker['device'],previous)
        observed=self.budget.quota['observed_unix_seconds']
        credit=B.covered_external_credit(self.samples,observed,current,cap)
        self.last=current;self.samples.append(current)
        self.samples=B.retain_external_samples(self.samples,observed)
        remaining=remaining_with_own_credit(self.original,total,cap,credit,closed)
        self.last_report=dict(schema='CURRENT_PARENT_ACTIVE_DOMAIN_ALLOCATED_RESOURCE_CREDIT_V1',
          path=str(self.path),current_file_metadata=current,quota_observed_unix_seconds=observed,
          quota_snapshot_reference=self.budget.quota['snapshot_reference'],
          total_future_reserved_bytes=total,original_full_parent_cap_bytes=cap,
          earlier_quota_covered_domain_allocated_bytes=credit,
          separate_closed_output_allocated_bytes=closed,remaining_future_reserved_bytes=remaining,
          database_excluded_from_second_immutable_credit=True,free_bytes_rewritten=False,
          SQL_or_database_body_read=False,scientific_adoption=False,quota_reserve_bytes=self.budget.account_floor_bytes)
        self.emit_priority_progress(total,remaining,observed)
        return remaining
    def emit_priority_progress(self,total,remaining,observed):
        root=self.budget.census_context.root
        if root.parent!=C.OUTPUT:return
        jid=os.environ.get('SLURM_JOB_ID','');C.need(jid.isdigit() and os.getuid()==1278,'ACTUAL_D3_RESOURCE_STATUS_PARENT')
        value=dict(schema='PRIORITY_WRITER_NET_FUTURE_RESOURCE_OBSERVATION_V1',job_id=jid,uid=1278,
          quota_observed_unix_seconds=observed,quota_snapshot_reference=self.budget.quota['snapshot_reference'],
          root_total_future_bytes=total,remaining_future_bytes=remaining,free_bytes_rewritten=False,
          scientific_adoption=False,account_quota_floor_bytes=self.budget.account_floor_bytes)
        raw=(json.dumps(value,sort_keys=True)+'\n').encode();C.need(len(raw)<4096,'SMALL_RESOURCE_STATUS_ONLY')
        with self.budget.census_context.census_lock:
            target=root/'priority_writer_resource_progress.json';temp=root/('.priority_resource_'+str(time.time_ns())+'.pending')
            with temp.open('xb')as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            os.replace(temp,target)
    def report(self):
        return self.last_report or dict(schema='CURRENT_PARENT_ACTIVE_DOMAIN_ALLOCATED_RESOURCE_CREDIT_V1',
          path=str(self.path),domain_not_created=True,earlier_quota_covered_domain_allocated_bytes=0,
          SQL_or_database_body_read=False,scientific_adoption=False)
def resource_admission(r,plan):
    if plan.get('queue_startup_mode')=='USER_UNLIMITED_CPU21_D3_20261103':
        C.need(r['cpus']==16 and r['node']==plan['node'] and r['node'] in (*C.ANALYSIS_NODES,'compute-0-21')and r['partition']=='all'and r['wall_seconds']is None
          and r['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'and r['data_references']==plan['data_references']
          and r['estimated_peak_output_bytes']==plan['estimated_future_output_bytes'],'USER_CPU21_NO_TIME_OR_MEMORY_STOP_SCOPE')
        return
    C.need(type(r['cpus'])is int and r['cpus']==16 and r['node']==plan['node'] and r['node'] in C.ANALYSIS_NODES
      and r['wall_seconds']==86400 and r['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and r['data_references']==plan['data_references']
      and r['estimated_peak_output_bytes']==plan['whole_output_cap_bytes'],'EXACT_SINGLE_GENERIC_CPU16_DAY')
    C.need(B.Budget is General.I.Budget and Budget.__bases__==(B.Budget,)
      and CensusContext.record_census is NativeCensus.ResourceBudget.record_census,
      'ORIGINAL_GENERAL_BUDGET_WITH_EXACT_NATIVE_COMPLETE_CENSUS_IO_ONLY')

def guard(path,proof_path,plan):
    if plan.get('queue_startup_mode') in ('QUEUED_REAL_ALLOCATION_ROOT_PROVIDER_ON_START','USER_UNLIMITED_CPU21_D3_20261103'):
        from .queued_runtime import validate
        proof=validate(path,proof_path,plan,scope_key=C.KEY,parameters=C.parameters(plan))
    else:
        from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
        expected=[C.PY,'-B','-m',C.MODULE,'--plan',str(path),'--startup-proof',str(proof_path)]
        proof=require_startup(proof_path,expected_kind='analysis',expected_scope_key=C.KEY,expected_scope_parameters=C.parameters(plan),expected_execution_argv=expected,
          expected_source=C.HERE/'run.py',required_references=[C.Q.pin(path),*plan['source_references']])
    resource_admission(proof['request'],plan)
    return proof

def fast_parts_root(coverage,producer_root,reviewed_roots,job_id):
    root=pathlib.Path(producer_root)
    if root.parent not in (C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_fast55k_resume_v4',C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_fast55k_resume_v5',C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_fast55k_resume_v6',C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_fast55k_resume_v7',C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_fast55k_resume_v8',C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_fast55k_resume_v9',C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_fast55k_resume_v10',C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_fast55k_resume_v11',C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_fast55k_resume_v12',C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_fast55k_resume_v13'):
        return _original_fast_parts_root(coverage,producer_root,reviewed_roots,job_id)
    from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v4 import contract as Producer
    prior=Producer.PHASE_ROOT;old=Producer.OLDROOT;parts=root/'typed_coverage';closed=prior/'typed_coverage'
    from . import local_parent
    C.need(type(reviewed_roots)is list and all(str(p)in reviewed_roots for p in (root,prior,old)), 'THREE_EXPLICIT_ACTUAL_CLOSED_CACHE_ROOTS')
    C.need(str(coverage['job_id'])==str(job_id)and str(job_id)not in ('4525232','4525251','4525337')
      and coverage['reused_C0_parent_job_id']=='4525337' and coverage['typed_parts_reencoded']==0
      and coverage['mode']=='bounded_pilot55k' and coverage['fast_IO_not_new_science']is True
      and coverage['workers']==local_parent.workers(coverage,job_id) and coverage['source_batch_rows']==16 and coverage['old_cache_written']is False
      and pathlib.Path(C.reference(coverage['parts_catalog'])['path'])==closed/'numeric_catalog.sqlite'
      and pathlib.Path(C.reference(coverage['current_parent_typed_origin_reference'])['path'])==parts/'current_parent_typed_origin.json'
      and pathlib.Path(C.reference(coverage['reused_current_typed_origin_reference'])['path'])==closed/'current_parent_typed_origin.json'
      and pathlib.Path(C.reference(coverage['readonly_old_typed_origin_reference'])['path'])==closed/'readback_old_selected_typed_origin.json'
      and pathlib.Path(C.reference(coverage['readonly_old_catalog_reference'])['path'])==old/'typed_coverage/numeric_catalog.sqlite'
      and pathlib.Path(C.reference(coverage['readonly_old_selected_owner_reference'])['path'])==old/'typed_coverage/selected_owner.sqlite'
      and 'original_parts_output_root'not in coverage,'EXACT_REUSED_COMPLETE_TYPED_CATALOG_AND_ALL_THREE_PRODUCER_ORIGINS')
    return str(parts)

def configure_reader(cfg,coverage,oldroot):
    if coverage.get('reused_C0_parent_job_id')!='4525337':return _original_configure_reader(cfg,coverage,oldroot)
    from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v4 import contract as Producer
    cfg=copy.deepcopy(cfg);C.need(READER_CONTEXT is not None,'EXACT_ADMITTED_CLOSED_PHASE_READER_CONTEXT')
    producer=READER_CONTEXT['producer_plan'];review=C.meta(READER_CONTEXT['bounded_review_reference']);actual=C.meta(READER_CONTEXT['actual_parent_manifest_reference'])
    from . import local_parent
    C.need(producer['output_directory']==str(oldroot) and actual['status']==local_parent.status(actual),
      'ACTUAL_COMPLETE_NEW_D4_NOT_CLOSED5337_PARTIAL')
    actual=local_parent.geometry_producer(coverage,actual)
    C.need(actual['job_id']==coverage['job_id'],'ACTUAL_CLOSED_GEOMETRY_READER_PRODUCER')
    _,_,_,closed_receipt=Producer.phase_authority(producer)
    C.need(closed_receipt['coverage_reference']==coverage['reused_complete_coverage_reference'],'EXACT_PRIOR_ACTUAL_C0_COVERAGE_REFERENCE')
    parts=fast_parts_root(coverage,oldroot,review['transitive_closed_output_roots'],actual['job_id'])
    closed=Producer.PHASE_ROOT/'typed_coverage';old_parts=Producer.OLDROOT/'typed_coverage'
    rr=coverage['reused_complete_coverage_reference'];add(rr,Producer.PHASE_ROOT);prior=load_data(rr,8<<20)
    for key in ('field_stats','selected_group_record_counts','quality_hold_fields','errors','parts_catalog','base_rows','task_rows','records','molecules','all14task_and_base_exact_once','readback_closed_parts','new_selected_parts'):
        C.need(coverage[key]==prior[key],'UNCHANGED_CLOSED_COVERAGE_SCIENTIFIC_CONTENT:'+key)
    for k in ('canonical_index','eligibility_reference','source_inventory_reference','field_map_reference','logical_group_plan_reference','coverage_reference'):
        if k in cfg and cfg[k]['path']not in B.ALLOWED:
            p=pathlib.Path(cfg[k]['path']);origin=next((v for v in (pathlib.Path(oldroot),Producer.PHASE_ROOT,Producer.OLDROOT)if v in p.parents),None)
            C.need(origin is not None,'DECLARED_READER_STATIC_AUTHORITY_OR_EXACT_CLOSED_ORIGIN');add(cfg[k],origin)
    add(coverage['parts_catalog'],Producer.PHASE_ROOT);require(coverage['parts_catalog'])
    origins=((coverage['readonly_old_typed_origin_reference'],old_parts,closed),
             (coverage['reused_current_typed_origin_reference'],closed,closed),
             (coverage['current_parent_typed_origin_reference'],pathlib.Path(parts),pathlib.Path(parts)))
    declared={r['manifest_reference']['path']:(r['manifest_reference'],r['output_root'])for r in cfg['cache_transitive_output_origins']}
    for ref,output,location in origins:
        add(ref,location);require(ref)
        C.need(declared.get(ref['path'])==(ref,str(output)),'SAVED_READER_CONFIG_EXACT_ORIGINAL_AND_REUSED_AND_CURRENT_ORIGINS')
        B.ORIGINS[ref['path']]={'manifest_reference':ref,'output_root':str(output)}
    ro=load_data(coverage['readonly_old_typed_origin_reference'],8<<20)
    C.need(ro['schema']=='CURRENT_PARENT_SELECTED_TYPED_ORIGIN_V1'and ro['job_id']=='4525337'and ro['readonly_C0_parent_job_id']=='4525232'
      and ro['closed_old_parts_written']is False and ro['old_catalog_reference']==coverage['readonly_old_catalog_reference']
      and ro['old_selected_owner_reference']==coverage['readonly_old_selected_owner_reference']
      and ro['readback_closed_parts']==coverage['readback_closed_parts'],'ORIGINAL5337_READBACK_CERTIFICATE_5232_HISTORY_PRESERVED')
    body=load_data(coverage['current_parent_typed_origin_reference'],8<<20)
    C.need(body['job_id']==actual['job_id'] and body['prior_actual_C0_job_id']=='4525337'and body['parts_written_here']==0
      and body['prior_complete_coverage_reference']==rr,'NEW_ORIGIN_HONESTLY_DECLARES_REUSE_NO_NEW_PARTS')
    cfg['catalog_frame']=identity(coverage['parts_catalog']['path']);return cfg
