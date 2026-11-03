"""Original finite day Budget/IO objects with explicit closed-parent roots."""
import copy,json,os,pathlib,sqlite3,threading,types
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as B
from workflows.data_v1_final.export.family_export_day_v1 import io as F
from workflows.data_v1_final.labels.existing_sprime_pilot_general_cpu_day_v1 import run as General
from workflows.data_v1_final.labels.existing_sprime_native_pilot_day_v1 import geometry as NativeCensus
from . import contract as C
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
        with self.census_lock:return NativeCensus.retry_whole_census(B.unique_bytes,path,self.record_census)
def private_io_function(original,census,save_function=None,write_text_function=None,*,stop_evidence=False):
    """Original entire function code/defaults; explicit private IO bindings only."""
    namespace=dict(original.__globals__);namespace['unique_bytes']=census
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
        self.census_context=CensusContext(root);ACTIVE_CENSUS=self.census_context
        safe_save=private_io_function(B.save,self.census_context);safe_text=private_io_function(B.write_text,self.census_context)
        self.parent_observe=private_io_function(B.Budget._observe,self.census_context,safe_save,safe_text,stop_evidence=True)
        self.parent_check=private_io_function(B.Budget.check,self.census_context,safe_save,safe_text)
        self.parent_quota_event=private_io_function(B.Budget.record_quota_event,self.census_context,safe_save,safe_text)
        original_init=private_io_function(B.Budget.__init__,self.census_context,safe_save,safe_text)
        original_init(self,plan,proof,root)
    def _observe(self):return self.parent_observe(self)
    def check(self,*,force=False,dispatch=True):return self.parent_check(self,force=force,dispatch=dispatch)
    def record_quota_event(self,event):return self.parent_quota_event(self,event)
def configure(plan,old):
    global ACTIVE_CENSUS,READER_CONTEXT
    ACTIVE_CENSUS=None
    READER_CONTEXT={'producer_plan':copy.deepcopy(old),'bounded_review_reference':plan['bounded_export_review_reference'],
      'actual_parent_manifest_reference':plan['pilot_parent_manifest_reference'],'source_references':plan['source_references']}
    cfg=copy.deepcopy(plan);cfg['cache_transitive_output_origins']=[]
    cfg['accepted_prior_output_roots']=[{'manifest_reference':plan['pilot_parent_manifest_reference'],'output_root':old['output_directory']}]
    B.configure(cfg)
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
def resumed_parts_root(coverage,newroot,reviewed_roots,resume,original,oldjob,newjob):
    """Only the exact old typed root authorized by this exact NativeV2 resume."""
    newroot=pathlib.Path(newroot);original_root=pathlib.Path(resume['original_output_root'])
    C.need(resume['schema']=='ROOT_REVIEWED_NATIVE55K_TERMINAL_STAGE_RESUME_V2'
      and resume['status']=='APPROVED_READONLY_COMPLETE_STAGES_NOT_OLD_D4_COMPLETE' and resume['reviewer']=='root'
      and resume['old_full_D4_complete'] is False and resume['new_parent_full_stage_revalidation_required'] is True
      and original['output_directory']==str(original_root)
      and original_root.parent==C.ROOT/'artifacts/labels/source_status_v1/existing_sprime_pilot_day_v1',
      'EXACT_ROOT_REVIEWED_ORIGINAL_TERMINAL_NATIVE_OUTPUT_NOT_GENERIC_ROOT')
    C.need(type(reviewed_roots)is list and all(type(r)is str and pathlib.Path(r).is_absolute()
      and '..'not in pathlib.Path(r).parts and str(pathlib.Path(r))==r for r in reviewed_roots)
      and str(newroot)in reviewed_roots and str(original_root)in reviewed_roots,
      'BOTH_EXACT_NEW_AND_ORIGINAL_OUTPUT_ROOTS_MUST_BE_EXPLICITLY_REVIEWED')
    expected=original_root/'typed_coverage'
    C.need(coverage['original_parts_output_root']==str(expected)
      and C.reference(coverage['original_coverage_reference'])['path']==resume['deferred_stage_locators']['coverage_manifest']==str(expected/'manifest.json')
      and pathlib.Path(C.reference(coverage['parts_catalog'])['path']).parent==newroot/'typed_coverage'
      and pathlib.Path(C.reference(coverage['current_parent_typed_origin_reference'])['path']).parent==expected
      and str(coverage['original_actual_parent_job_id'])==str(oldjob)
      and str(coverage['new_current_parent_technical_adoption_job_id'])==str(coverage['job_id'])==str(newjob),
      'NEW_CATALOG_OLD_ORIGIN_AND_PARTS_EXACT_AUTHORITY_JOB_LINEAGE_NOT_CATALOG_PARENT_GUESS')
    return str(expected)
def configure_reader(cfg,coverage,oldroot):
    cfg=copy.deepcopy(cfg)
    C.need(READER_CONTEXT is not None,'EXACT_ADMITTED_NATIVE_RESUME_READER_CONTEXT_REQUIRED')
    producer=READER_CONTEXT['producer_plan'];review=C.meta(READER_CONTEXT['bounded_review_reference'])
    actual=C.meta(READER_CONTEXT['actual_parent_manifest_reference']);origin=producer['resume_origin_review_reference']
    C.need(producer['schema']=='EXISTING_SPRIME_NATIVE_PILOT_RESUME_PLAN_V2' and producer['output_directory']==str(oldroot)
      and review['resume_origin_review_reference']==actual['resume_origin_review_reference']==origin
      and origin in producer['source_references'] and origin in READER_CONTEXT['source_references'],
      'SAME_ACTUAL_RESUME_AUTHORITY_DECLARED_IN_PRODUCER_AND_BOUNDED_CONSUMER')
    from workflows.data_v1_final.labels.existing_sprime_native_pilot_resume_v2 import contract as Resume
    resume,original,oldproof=Resume.resume_authority(producer)
    parts_root=resumed_parts_root(coverage,oldroot,review['transitive_closed_output_roots'],resume,original,oldproof['job_id'],actual['job_id'])
    for k in ('canonical_index','eligibility_reference','source_inventory_reference','field_map_reference','logical_group_plan_reference','coverage_reference'):
        if k in cfg and cfg[k]['path'] not in B.ALLOWED:add(cfg[k],oldroot) if pathlib.Path(oldroot) in pathlib.Path(cfg[k]['path']).parents else C.need(False,'STATIC_READER_REF_MUST_BE_DECLARED:'+k)
    add(coverage['parts_catalog'],oldroot);add(coverage['current_parent_typed_origin_reference'],parts_root)
    B.ORIGINS[coverage['current_parent_typed_origin_reference']['path']]={'manifest_reference':coverage['current_parent_typed_origin_reference'],'output_root':parts_root}
    require(coverage['current_parent_typed_origin_reference'])
    require(coverage['parts_catalog']);cfg['catalog_frame']=identity(coverage['parts_catalog']['path'])
    return cfg
def resource_admission(r,plan):
    C.need(type(r['cpus'])is int and r['cpus']==16 and r['node']==plan['node'] and r['node'] in C.ANALYSIS_NODES
      and r['wall_seconds']==86400 and r['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and r['data_references']==plan['data_references']
      and r['estimated_peak_output_bytes']==plan['whole_output_cap_bytes'],'EXACT_SINGLE_GENERIC_CPU16_DAY')
    C.need(B.Budget is General.I.Budget and Budget.__bases__==(B.Budget,)
      and CensusContext.record_census is NativeCensus.ResourceBudget.record_census,
      'ORIGINAL_GENERAL_BUDGET_WITH_EXACT_NATIVE_COMPLETE_CENSUS_IO_ONLY')

def guard(path,proof_path,plan):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    expected=[C.PY,'-B','-m',C.MODULE,'--plan',str(path),'--startup-proof',str(proof_path)]
    proof=require_startup(proof_path,expected_kind='analysis',expected_scope_key=C.KEY,expected_scope_parameters=C.parameters(plan),expected_execution_argv=expected,
      expected_source=C.HERE/'run.py',required_references=[C.Q.pin(path),*plan['source_references']])
    resource_admission(proof['request'],plan)
    return proof
