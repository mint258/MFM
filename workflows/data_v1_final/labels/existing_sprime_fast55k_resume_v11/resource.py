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
    def __init__(self,context):self.context=context
    def write_parquet(self,*args,**kwargs):return self.context.write_parquet(*args,**kwargs)

class CoveredOutputRefs:
    def __init__(self,budget):
        self.excluded={str(budget.checkpoint_path),*budget.serialization_math.paths}
    def values(self):return [r for r in list(I.ALLOWED.values()) if r['path'] not in self.excluded]

def remaining_with_serialization(total,cap,external,initial,credited,closed):
    C.need(all(type(v)is int and v>=0 for v in (total,cap,external,initial,credited,closed))
      and external+credited<=cap,'OWN_ALLOCATED_OUTPUT_CREDIT_WITHIN_FULL_CAP')
    return I.C.remaining_future(total+initial-credited,cap-external-credited,closed)

class SerializationMath:
    """Lstat and original earlier-quota guards; no data adoption or free rewrite."""
    def __init__(self,budget,plan):
        self.budget=budget;self.last_report=None;self.states={}
        carve=C.meta(plan['root_carveout_review_reference'])
        review=C.meta(plan['metadata_recovery_reference'])
        files=review['staged_serialization_files']
        names={pathlib.Path(r['path']).name for r in files}
        C.need(names==set(PARQUET_IO.COMPLETE)|{PARQUET_IO.PARTIAL} and len(files)==6,
          'ONLY_SIX_EXPLICIT_CLOSED5481_SERIALIZATION_RESOURCE_FILES')
        source=carve['registered_external_allocated_credit_sources'][0]
        inventory=C.meta(source['initial_observation_reference'])
        self.initial=carve['initial_already_charged_serialization_allocated_bytes']
        C.need(self.initial==sum(r['allocated_bytes'] for r in files),
          'INITIAL_SERIALIZATION_ALLOCATIONS_SUBTRACTED_FROM_ROOT_TOTAL_ONCE')
        for row in files:
            p=pathlib.Path(row['path']);C.need(p.parent==budget.checkpoint_path.parent,
              'EXACT_CURRENT_PARENT_SERIALIZATION_RESOURCE_PATH')
            entries=[r for r in inventory['files'] if r['path']==str(p)]
            C.need(len(entries)==1,'ONE_INITIAL_SERIALIZATION_ALLOCATION_METADATA_ROW')
            sample=entries[0]
            C.need(all(sample[k]==row[k] for k in ('inode','uid','size','allocated_bytes','mtime_ns'))
              and row['uid']==1278 and row['allocated_bytes']<=sample['allocated_bytes_after_quota'],
              'EXACT_ROOT_STAGED_FILE_METADATA_BEFORE_AND_AFTER_QUOTA')
            initial=dict(observed_unix_seconds=inventory['observed_unix_seconds'],
              allocated_bytes=sample['allocated_bytes'],size=sample['size'],inode=sample['inode'],
              uid=sample['uid'],high_water_allocated_bytes=sample['allocated_bytes_after_quota'])
            self.states[str(p)]=dict(samples=[initial],last=initial)
        active=str(budget.checkpoint_path.parent/PARQUET_IO.ACTIVE)
        C.need(active not in self.states,'FULL_NEW_INPUT_VIEW_PATH_DISTINCT_FROM_OLD_PARTIAL')
        self.states[active]=dict(samples=[],last=None)
        self.paths=set(self.states)
    def __getattr__(self,name):return getattr(I.C,name)
    def remaining_future(self,total,cap,closed):
        external=self.budget.total+self.budget.external_initial_credit-total
        credit=0;observations=[];marker=self.budget.quota['cpu_marker']['stat']
        C.need(marker['uid']==1278,'ORIGINAL_VALIDATED_SHARED_STORAGE_MARKER_UID')
        observed=self.budget.quota['observed_unix_seconds']
        for name,state in self.states.items():
            path=pathlib.Path(name)
            if not path.exists():
                C.need(state['last'] is None,'COVERED_SERIALIZATION_FILE_DISAPPEARED')
                continue
            current_frame=path.lstat();previous=state['last'] or dict(allocated_bytes=0,size=0)
            wanted=dict(uid=1278,inode=current_frame.st_ino if state['last'] is None else previous['inode'],cap_bytes=cap)
            current=I.external_metadata_inventory(path,wanted,marker['device'],previous)
            covered=I.covered_external_credit(state['samples'],observed,current,cap)
            state['last']=current;state['samples'].append(current)
            state['samples']=I.retain_external_samples(state['samples'],observed)
            credit+=covered;observations.append(dict(path=name,current_metadata=current,credited_allocated_bytes=covered))
        remaining=remaining_with_serialization(total,cap,external,self.initial,credit,closed)
        self.last_report=dict(schema='CURRENT_PARENT_SERIALIZATION_ALLOCATED_RESOURCE_CREDIT_V1',
          initial_serialization_credit_added_back_bytes=self.initial,
          earlier_quota_covered_serialization_allocated_bytes=credit,
          external_checkpoint_credit_bytes=external,separate_closed_allocated_bytes=closed,
          remaining_future_reserved_bytes=remaining,original_full_parent_cap_bytes=cap,
          quota_snapshot_reference=self.budget.quota['snapshot_reference'],
          observations=observations,excluded_from_second_immutable_credit=True,
          file_bodies_opened_or_hashed=False,scientific_adoption=False,free_bytes_rewritten=False,
          quota_reserve_bytes=200000000000)
        return remaining

def initial_inventory(source,observation):
    C.need(observation['schema']=='ROOT_ACTIVE_OUTPUT_ALLOCATED_BYTES_METADATA_OBSERVATION_V1'
      and observation['database_bodies_read_or_hashed'] is False
      and observation['scientific_adoption_or_C0_claimed'] is False,'CHECKPOINT_ALLOCATION_METADATA_ONLY')
    timestamp=observation['observed_unix_seconds']
    C.need(type(timestamp)in(int,float) and math.isfinite(timestamp) and timestamp>0,'FINITE_INITIAL_INVENTORY_TIME')
    rows=[r for r in observation['files'] if r['path']==source['path']]
    C.need(len(rows)==1,'ONE_CURRENT5478_ALLOCATION');row=rows[0]
    C.need(row['registered_parent']=='metadata_partial5481'
      and all(row[k]==source[k] for k in ('device','inode','uid'))
      and type(row['size'])is int and row['size']>=0
      and type(row['allocated_bytes'])is int and type(row['allocated_bytes_after_quota'])is int
      and 0<=source['initial_credited_allocated_bytes']<=row['allocated_bytes']<=row['allocated_bytes_after_quota']<=source['cap_bytes']
      and row['source_database_body_not_read']is True and row['mutable_not_scientific_adoption']is True,
      'EXACT_CLOSED5481_CHECKPOINT_ALREADY_CHARGED_BLOCKS')
    return dict(observed_unix_seconds=timestamp,allocated_bytes=source['initial_credited_allocated_bytes'],size=row['size'],
      high_water_allocated_bytes=row['allocated_bytes_after_quota'],origin='ROOT_REVIEWED_CHECKPOINT_METADATA_INVENTORY',
      device=row['device'],inode=row['inode'],uid=row['uid'])

class ResourceBudget(I.Budget):
    record_census=NATIVE.ResourceBudget.record_census
    def __init__(self,plan,proof,root):
        global ACTIVE_CENSUS
        self.root=pathlib.Path(root);self.checkpoint_path=self.root/'actual_input_children/geometry.sqlite'
        carve=C.meta(plan['root_carveout_review_reference'])
        C.need(len(carve['registered_external_allocated_credit_sources'])==1,'ONE_CURRENT5481_CHECKPOINT_SOURCE')
        self.initial_credit=carve['registered_external_allocated_credit_sources'][0]['initial_credited_allocated_bytes']
        self.serialization_math=SerializationMath(self,plan)
        self.census_lock=threading.RLock();self.census_sequence=0
        def census(path):
            C.need(pathlib.Path(path)==self.root,'CURRENT_PARENT_OUTPUT_CENSUS_ONLY')
            with self.census_lock:return NATIVE.retry_whole_census(RC.unique_bytes,path,self.record_census)
        self.native_census=census;ACTIVE_CENSUS=census
        safe_save=private(I.save,census);safe_text=private(I.write_text,census)
        old=NATIVE.budget_function('_observe',census)
        self.native_observe=private(old,census,QG=QG,C=self.serialization_math,
          ALLOWED=CoveredOutputRefs(self),save=safe_save,write_text=safe_text)
        self.native_check=private(NATIVE.budget_function('check',census),census,save=safe_save,write_text=safe_text)
        self.parent_quota_event=private(I.Budget.record_quota_event,census,save=safe_save,write_text=safe_text)
        init=private(I.Budget.__init__,census,save=safe_save,write_text=safe_text,
          external_source_shape=lambda s:OLD.shape(s,self.checkpoint_path),initial_external_inventory=initial_inventory)
        init(self,plan,proof,root)
    _observe=OLD.ResourceBudget._observe
    def check(self,*,force=False,dispatch=True):return self.native_check(self,force=force,dispatch=dispatch)
    def record_quota_event(self,event):return self.parent_quota_event(self,event)
    def close(self):
        I.Budget.close(self)
        if self.serialization_math.last_report is not None:
            SafeIO().save(self.root/'serialization_output_resource_credit.json',self.serialization_math.last_report)

def proof():
    # The required existing Source suite executes this source-object witness.
    census=lambda path:0
    for f in (I.save,I.write_text,I.Budget.__init__,I.Budget._observe,I.Budget.check,I.Budget.record_quota_event):
        g=private(f,census);assert g.__code__ is f.__code__ and g.__defaults__==f.__defaults__
        assert g.__kwdefaults__==f.__kwdefaults__ and g.__globals__['unique_bytes'] is census
    # Same existing source-object witness, including this resource-only arithmetic.
    assert remaining_with_serialization(424,64,37,8,12,3)==417
    assert remaining_with_serialization(428,64,33,8,8,0)==428
    assert remaining_with_serialization(424,64,37,8,12,100)==405
    assert remaining_with_serialization(432,64,33,0,0,8)==424
    return dict(original_entire_IO_code_objects_defaults_and_keyword_defaults_retained=True,
      resource_save_text_init_and_quota_event_use_same_bounded_complete_census=True,
      original_parquet_writer_keyword_defaults=PARQUET_IO.proof(),
      serialization_allocated_once_in_used_or_future_never_both=True,
      unchanged_one_checkpoint_credit_and_all_original_resource_thresholds=OLD.proof())
