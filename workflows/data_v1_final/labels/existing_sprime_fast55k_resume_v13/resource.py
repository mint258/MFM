"""Private original IO functions all share the existing complete census/retry."""
import inspect,math,pathlib,stat,textwrap,threading,time,types
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v8 import resource as OLD
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I
from . import io as PARQUET_IO
NATIVE=OLD.NATIVE;RC=OLD.RC;QG=OLD.QG
ACTIVE_CENSUS=None
ACCOUNT_FLOOR_BYTES=100000000000

def user_quota_observer(original):
    """Change only the explicitly authorized account-floor constant and reason."""
    source=textwrap.dedent(inspect.getsource(original))
    old="if self.quota['free_bytes']-remaining_future<200000000000:R.mark_stop('COMMON_TRAIN_ACCOUNT_FREE_FUTURE_ONCE_PLUS200GB'"
    new="if self.quota['free_bytes']-remaining_future<100000000000:R.mark_stop('COMMON_TRAIN_ACCOUNT_FREE_FUTURE_ONCE_PLUS100GB'"
    C.need(source.count(old)==1,'ONE_EXACT_ORIGINAL_RESOURCE_FLOOR_GUARD')
    changed=source.replace(old,new,1)
    C.need(changed.replace(new,old,1)==source,'ONLY_USER_AUTHORIZED_FLOOR_RESOURCE_CHANGE')
    namespace=dict(original.__globals__)
    exec(compile(changed,str(C.HERE/'resource.py')+'::user_account_floor100GB','exec'),namespace)
    result=namespace[original.__name__];result.__defaults__=original.__defaults__;result.__kwdefaults__=original.__kwdefaults__
    return result

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

def active_metadata_inventory(path,expected,marker_device,previous):
    """Resource-only lower bound for a currently written file; no data adoption.

    NFS allocation observations and writer preallocation need not be monotonic.
    Credit remains bounded by an earlier quota-covered sample and BOTH current
    lstat allocations. Immutable files retain the original strict inventory.
    """
    p=pathlib.Path(path)
    C.need(not any(q.is_symlink() for q in (p,*p.parents)),'NO_ACTIVE_RESOURCE_SYMLINK')
    first=p.lstat();last=p.lstat()
    for s in (first,last):
        C.need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid==expected['uid']
          and s.st_ino==expected['inode'] and s.st_dev==marker_device,
          'ACTIVE_CURRENT_UID_INODE_AND_VALIDATED_SHARED_MARKER_DEVICE')
        C.need(0<=s.st_blocks*512<=expected['cap_bytes'] and 0<=s.st_size<=expected['cap_bytes'],
          'ACTIVE_ALLOCATED_AND_LOGICAL_BYTES_WITHIN_UNCHANGED_FULL_CAP')
    a,b=first.st_blocks*512,last.st_blocks*512
    return dict(observed_unix_seconds=time.time(),allocated_bytes=min(a,b),
      size=min(first.st_size,last.st_size),device=last.st_dev,inode=last.st_ino,
      uid=last.st_uid,mtime_ns=last.st_mtime_ns,body_opened_or_hashed=False,
      origin='ACTUAL_CPU_ACTIVE_FILE_TWO_LSTAT_LOWER_BOUND',
      observed_first_allocated_bytes=a,observed_last_allocated_bytes=b,
      nonmonotonic_observation=(b<a or min(a,b)<previous.get('allocated_bytes',0)
        or last.st_size<first.st_size or min(first.st_size,last.st_size)<previous.get('size',0)),
      original_earlier_quota_credit_filter_retained=True,scientific_adoption=False)

class SerializationMath:
    """Lstat and original earlier-quota guards; no data adoption or free rewrite."""
    def __init__(self,budget,plan):
        self.budget=budget;self.last_report=None;self.states={}
        carve=C.meta(plan['root_carveout_review_reference'])
        review=C.meta(plan['metadata_recovery_reference'])
        files=review['staged_serialization_files']
        names={pathlib.Path(r['path']).name for r in files}
        C.need(names==set(PARQUET_IO.COMPLETE)|set(PARQUET_IO.PARTIALS) and len(files)==5,
          'ONLY_FIVE_EXPLICIT_CLOSED5494_SERIALIZATION_RESOURCE_FILES')
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
            inventory=active_metadata_inventory if path.name==PARQUET_IO.ACTIVE else I.external_metadata_inventory
            current=inventory(path,wanted,marker['device'],previous)
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
          quota_reserve_bytes=ACCOUNT_FLOOR_BYTES)
        return remaining

def initial_inventory(source,observation):
    C.need(observation['schema']=='ROOT_ACTIVE_OUTPUT_ALLOCATED_BYTES_METADATA_OBSERVATION_V1'
      and observation['database_bodies_read_or_hashed'] is False
      and observation['scientific_adoption_or_C0_claimed'] is False,'CHECKPOINT_ALLOCATION_METADATA_ONLY')
    timestamp=observation['observed_unix_seconds']
    C.need(type(timestamp)in(int,float) and math.isfinite(timestamp) and timestamp>0,'FINITE_INITIAL_INVENTORY_TIME')
    rows=[r for r in observation['files'] if r['path']==source['path']]
    C.need(len(rows)==1,'ONE_CURRENT5478_ALLOCATION');row=rows[0]
    C.need(row['registered_parent']=='metadata_partial5494'
      and all(row[k]==source[k] for k in ('device','inode','uid'))
      and type(row['size'])is int and row['size']>=0
      and type(row['allocated_bytes'])is int and type(row['allocated_bytes_after_quota'])is int
      and 0<=source['initial_credited_allocated_bytes']<=row['allocated_bytes']<=row['allocated_bytes_after_quota']<=source['cap_bytes']
      and row['source_database_body_not_read']is True and row['mutable_not_scientific_adoption']is True,
      'EXACT_CLOSED5494_CHECKPOINT_ALREADY_CHARGED_BLOCKS')
    return dict(observed_unix_seconds=timestamp,allocated_bytes=source['initial_credited_allocated_bytes'],size=row['size'],
      high_water_allocated_bytes=row['allocated_bytes_after_quota'],origin='ROOT_REVIEWED_CHECKPOINT_METADATA_INVENTORY',
      device=row['device'],inode=row['inode'],uid=row['uid'])

class ResourceBudget(I.Budget):
    record_census=NATIVE.ResourceBudget.record_census
    def __init__(self,plan,proof,root):
        global ACTIVE_CENSUS
        self.root=pathlib.Path(root);self.checkpoint_path=self.root/'actual_input_children/geometry.sqlite'
        carve=C.meta(plan['root_carveout_review_reference'])
        policy=C.meta(carve['temporary_account_quota_floor_reference'])
        C.need(carve['account_quota_floor_bytes']==policy['account_quota_floor_bytes']==ACCOUNT_FLOOR_BYTES
          and policy['status']=='USER_AUTHORIZED_TEMPORARY' and policy['scope']=='ACCOUNT_FREE_AFTER_ALL_FUTURES',
          'EXPLICIT_USER_TEMPORARY100GB_FLOOR_NO_FREE_OR_FUTURE_REWRITE')
        C.need(len(carve['registered_external_allocated_credit_sources'])==1,'ONE_CURRENT5494_CHECKPOINT_SOURCE')
        self.initial_credit=carve['registered_external_allocated_credit_sources'][0]['initial_credited_allocated_bytes']
        self.serialization_math=SerializationMath(self,plan)
        self.census_lock=threading.RLock();self.census_sequence=0
        def census(path):
            C.need(pathlib.Path(path)==self.root,'CURRENT_PARENT_OUTPUT_CENSUS_ONLY')
            with self.census_lock:return NATIVE.retry_whole_census(RC.unique_bytes,path,self.record_census)
        self.native_census=census;ACTIVE_CENSUS=census
        safe_save=private(I.save,census);safe_text=private(I.write_text,census)
        old=user_quota_observer(NATIVE.budget_function('_observe',census))
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
    # Same original Source method: decreasing current allocation cannot overcredit.
    sample=[dict(observed_unix_seconds=1,inode=2,uid=1278,allocated_bytes=4),
      dict(observed_unix_seconds=2,inode=2,uid=1278,allocated_bytes=10)]
    current=dict(inode=2,uid=1278,allocated_bytes=8)
    assert I.covered_external_credit(sample,3,current,64)==4
    assert I.covered_external_credit(sample,0.5,current,64)==0
    # Same existing source-object witness, including this resource-only arithmetic.
    assert remaining_with_serialization(424,64,37,8,12,3)==417
    assert remaining_with_serialization(428,64,33,8,8,0)==428
    assert remaining_with_serialization(424,64,37,8,12,100)==405
    assert remaining_with_serialization(432,64,33,0,0,8)==424
    changed=user_quota_observer(I.Budget._observe)
    assert changed.__code__.co_code==I.Budget._observe.__code__.co_code
    assert [(a,b) for a,b in zip(I.Budget._observe.__code__.co_consts,changed.__code__.co_consts) if a!=b]==[(200000000000,ACCOUNT_FLOOR_BYTES),('COMMON_TRAIN_ACCOUNT_FREE_FUTURE_ONCE_PLUS200GB','COMMON_TRAIN_ACCOUNT_FREE_FUTURE_ONCE_PLUS100GB')]
    return dict(original_entire_IO_code_objects_defaults_and_keyword_defaults_retained=True,
      resource_save_text_init_and_quota_event_use_same_bounded_complete_census=True,
      original_parquet_writer_keyword_defaults=PARQUET_IO.proof(),
      serialization_allocated_once_in_used_or_future_never_both=True,
      active_account_floor_bytes=ACCOUNT_FLOOR_BYTES,
      only_explicit_user_resource_floor_changed=True,
      historical_checkpoint_credit_resource_witness=OLD.proof())
