"""Private original IO functions all share the existing complete census/retry."""
import math,pathlib,threading,types
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v8 import resource as OLD
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I
from . import io as PARQUET_IO
NATIVE=OLD.NATIVE;RC=OLD.RC;QG=OLD.QG
ACTIVE_CENSUS=None

def private(original,census,**bindings):
    namespace=dict(original.__globals__,unique_bytes=census,**bindings)
    f=types.FunctionType(original.__code__,namespace,original.__name__,original.__defaults__,original.__closure__)
    f.__kwdefaults__=original.__kwdefaults__;return f

class SafeIO:
    def __getattr__(self,name):return getattr(I,name)
    def save(self,*args,**kwargs):
        f=I.save if ACTIVE_CENSUS is None else private(I.save,ACTIVE_CENSUS)
        return f(*args,**kwargs)
    def write_text(self,*args,**kwargs):
        f=I.write_text if ACTIVE_CENSUS is None else private(I.write_text,ACTIVE_CENSUS)
        return f(*args,**kwargs)

class SafeMetadataIO(SafeIO):
    def write_parquet(self,*args,**kwargs):return PARQUET_IO.writer_function()(*args,**kwargs)

def initial_inventory(source,observation):
    C.need(observation['schema']=='ROOT_ACTIVE_OUTPUT_ALLOCATED_BYTES_METADATA_OBSERVATION_V1'
      and observation['database_bodies_read_or_hashed'] is False
      and observation['scientific_adoption_or_C0_claimed'] is False,'CHECKPOINT_ALLOCATION_METADATA_ONLY')
    timestamp=observation['observed_unix_seconds']
    C.need(type(timestamp)in(int,float) and math.isfinite(timestamp) and timestamp>0,'FINITE_INITIAL_INVENTORY_TIME')
    rows=[r for r in observation['files'] if r['path']==source['path']]
    C.need(len(rows)==1,'ONE_CURRENT5478_ALLOCATION');row=rows[0]
    C.need(row['registered_parent']=='metadata_partial5480'
      and all(row[k]==source[k] for k in ('device','inode','uid'))
      and type(row['size'])is int and row['size']>=0
      and type(row['allocated_bytes'])is int and type(row['allocated_bytes_after_quota'])is int
      and 0<=source['initial_credited_allocated_bytes']<=row['allocated_bytes']<=row['allocated_bytes_after_quota']<=source['cap_bytes']
      and row['source_database_body_not_read']is True and row['mutable_not_scientific_adoption']is True,
      'EXACT_CLOSED5480_CHECKPOINT_ALREADY_CHARGED_BLOCKS')
    return dict(observed_unix_seconds=timestamp,allocated_bytes=source['initial_credited_allocated_bytes'],size=row['size'],
      high_water_allocated_bytes=row['allocated_bytes_after_quota'],origin='ROOT_REVIEWED_CHECKPOINT_METADATA_INVENTORY',
      device=row['device'],inode=row['inode'],uid=row['uid'])

class ResourceBudget(I.Budget):
    record_census=NATIVE.ResourceBudget.record_census
    def __init__(self,plan,proof,root):
        global ACTIVE_CENSUS
        self.root=pathlib.Path(root);self.checkpoint_path=self.root/'actual_input_children/geometry.sqlite'
        carve=C.meta(plan['root_carveout_review_reference'])
        C.need(len(carve['registered_external_allocated_credit_sources'])==1,'ONE_CURRENT5480_CHECKPOINT_SOURCE')
        self.initial_credit=carve['registered_external_allocated_credit_sources'][0]['initial_credited_allocated_bytes']
        self.census_lock=threading.RLock();self.census_sequence=0
        def census(path):
            C.need(pathlib.Path(path)==self.root,'CURRENT_PARENT_OUTPUT_CENSUS_ONLY')
            with self.census_lock:return NATIVE.retry_whole_census(RC.unique_bytes,path,self.record_census)
        self.native_census=census;ACTIVE_CENSUS=census
        safe_save=private(I.save,census);safe_text=private(I.write_text,census)
        old=NATIVE.budget_function('_observe',census)
        self.native_observe=private(old,census,QG=QG,C=OLD.BudgetMath(self),
          ALLOWED=OLD.NonDatabaseRefs(self.checkpoint_path),save=safe_save,write_text=safe_text)
        self.native_check=private(NATIVE.budget_function('check',census),census,save=safe_save,write_text=safe_text)
        self.parent_quota_event=private(I.Budget.record_quota_event,census,save=safe_save,write_text=safe_text)
        init=private(I.Budget.__init__,census,save=safe_save,write_text=safe_text,
          external_source_shape=lambda s:OLD.shape(s,self.checkpoint_path),initial_external_inventory=initial_inventory)
        init(self,plan,proof,root)
    _observe=OLD.ResourceBudget._observe
    def check(self,*,force=False,dispatch=True):return self.native_check(self,force=force,dispatch=dispatch)
    def record_quota_event(self,event):return self.parent_quota_event(self,event)

def proof():
    # The required existing Source suite executes this source-object witness.
    census=lambda path:0
    for f in (I.save,I.write_text,I.Budget.__init__,I.Budget._observe,I.Budget.check,I.Budget.record_quota_event):
        g=private(f,census);assert g.__code__ is f.__code__ and g.__defaults__==f.__defaults__
        assert g.__kwdefaults__==f.__kwdefaults__ and g.__globals__['unique_bytes'] is census
    return dict(original_entire_IO_code_objects_defaults_and_keyword_defaults_retained=True,
      resource_save_text_init_and_quota_event_use_same_bounded_complete_census=True,
      original_parquet_writer_keyword_defaults=PARQUET_IO.proof(),
      unchanged_one_checkpoint_credit_and_all_original_resource_thresholds=OLD.proof())
