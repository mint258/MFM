"""Central-v2 admission and durable bounded IO; no scheduler/controller copy."""
from __future__ import annotations
import argparse,fcntl,gzip,hashlib,importlib.util,json,os,pathlib,shlex,socket,sys,threading,time,traceback
from contextlib import contextmanager
from . import contract as C

HERE=C.HERE;OUT=None;PROOF=None;SESSION=None;VALUE=None;_SOURCES=None;_COMMON=None;ACTIVE_BUDGET=None
_MODULE_LOCK=threading.RLock()
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
FILES=('__init__.py','contract.py','runtime_io.py','plan.py','prepare_batch.py','run_batch.py','finalize.py',
    'identity.py','close_index.py','test_contract.py','README.md','frozen_sources.json','root_review_schemas.json')


def frozen_sources():
    global _SOURCES
    if _SOURCES is None:_SOURCES=C.sources()
    return _SOURCES


def common():
    global _COMMON
    with _MODULE_LOCK:
        if _COMMON is None:_COMMON=C.module('common',frozen_sources()['io'])
    return _COMMON


def input_ref(proof_path,path):
    proof=json.loads(pathlib.Path(proof_path).read_text());want=str(pathlib.Path(path))
    hits=[p for group in ('source_references','data_references') for p in proof['request'].get(group,[]) if p['path']==want]
    C.need(hits and all(p==hits[0] for p in hits),'LITERAL_INPUT_NOT_IN_REGISTERED_REQUEST:'+want)
    return hits[0]


def authorized(proof,references):
    allowed=[p for group in ('source_references','data_references') for p in proof['request'].get(group,[])]
    for value in references:C.need(C.triple(value) in allowed,'TRANSITIVE_INPUT_NOT_AUTHORIZED:'+value['path'])


def quota_reuse(reference,refs):
    review=C.read(reference)
    C.need(review['schema']=='SPRIME_MAIN_ACCOUNT_QUOTA_REUSE_ROOT_REVIEW_V3'
        and review['status']=='APPROVED_RESOURCE_FACT_REUSE_ONLY' and review['reviewer']=='root'
        and review['uid']==1278 and review['endpoint']=='202.38.247.57:22' and review['compute_node']=='compute-0-13'
        and review['provider_source_reference']==refs['quota_provider']
        and review['scientific_authority_is_separate'] is True and review['N1_population_authority_is_not_Sprime_authority'] is True,
        'SEPARATE_ROOT_REVIEW_OF_RESOURCE_METADATA_ONLY_REUSE_REQUIRED')
    from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4 import quota_provider as Q
    C.need(C.ref(Q.__file__)==refs['quota_provider'],'FROZEN_READONLY_QUOTA_CLIENT_CHANGED')
    provider_review=review['provider_review_reference'];resources=Q.references(provider_review)
    if review.get('provider_actual_launch_reference') is not None:
        C.read(review['provider_actual_launch_reference']);resources.append(review['provider_actual_launch_reference'])
    C.need(type(review['whole_wave_output_reserve_bytes']) is int and review['whole_wave_output_reserve_bytes']>=C.CAP,
        'WHOLE_WAVE_OUTPUT_PLUS_PROVIDER_RESERVE_REQUIRED')
    return review,Q,[reference,*resources]


def admit(script,args,stage,options):
    global PROOF,SESSION,VALUE
    config_ref=input_ref(args.root_preflight,args.config);value=C.config(config_ref);refs=C.sources()
    quota_ref=input_ref(args.root_preflight,args.quota_reuse_review)
    reuse,Q,quota_refs=quota_reuse(quota_ref,refs)
    script=pathlib.Path(script).absolute();argv=[PY,'-B',str(script)]
    if hasattr(args,'mode'):argv.append(args.mode)
    required=[config_ref,quota_ref,*[value[name] for name in
        ('recipe_config','roles_authority','per_molecule','formal_source_receipt','sprime_manifest')]]
    for name in options:
        item=getattr(args,name.replace('-','_'),None)
        if item is None:continue
        if isinstance(item,pathlib.Path):
            C.need(item.is_absolute() and '..' not in item.parts,'LITERAL_ABSOLUTE_CLI_REQUIRED')
            if name not in {'root-preflight','output'}:required.append(input_ref(args.root_preflight,item))
        argv.extend(['--'+name,str(item)])
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime
    own=[C.ref(HERE/name) for name in FILES]
    proof=runtime.require_startup(args.root_preflight,expected_scope_key='sprime_formal_cpu_auto_v3_'+stage,
        expected_scope_parameters=C.scope(stage,config_ref),expected_execution_argv=argv,expected_source=script,
        expected_kind=C.STAGES[stage],required_references=(*required,*own,*refs.values(),*quota_refs))
    C.need(proof['request']['pilot'] is False and proof['request']['node']=='compute-0-13'
        and proof['request']['cpus']==16 and proof['request']['estimated_peak_output_bytes']>=C.CAP,
        'EXACT_MAIN_NODE13_CPU16_FORMAL_STAGE_REQUIRED')
    os.environ.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
    session={'proof_reference':C.ref(args.root_preflight),'main_source':C.ref(script),'execution_argv':argv,
        'parent_pid':os.getpid(),'parent_start_ticks':proc_ticks(os.getpid()),'boot_id':proof['boot_id'],
        'job_id':str(proof['job_id']),'quota_reuse_review_reference':quota_ref}
    PROOF=proof;SESSION=session;VALUE=value
    return value,proof,session,config_ref


def proc_ticks(pid):return int(pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])


def continuation(session,check_sources=False):
    proof=C.read(session['proof_reference']);request=proof['request']
    C.need(os.getppid()==session['parent_pid'] and proc_ticks(session['parent_pid'])==session['parent_start_ticks']
        and os.getuid()==1278==proof['uid'] and str(proof['job_id'])==session['job_id']==os.environ.get('SLURM_JOB_ID')
        and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==session['boot_id']==proof['boot_id']
        and request['node']==socket.gethostname().split('.')[0]=='compute-0-13'
        and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('SLURM_JOB_PARTITION')=='cpu'
        and os.environ.get('CUDA_VISIBLE_DEVICES')=='','SAME_LIVE_ADMITTED_CPU16_PARENT_ALLOCATION_REQUIRED')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import primary_binding
    main=pathlib.Path(sys.modules['__main__'].__file__).absolute()
    C.need(C.ref(main)==session['main_source'] and request['execution_argv']==session['execution_argv'],'SAME_ACTUAL_MAIN_SOURCE_ARGV_REQUIRED')
    primary_binding(request,main,sys.argv[1:])
    if check_sources:authorized(proof,[C.ref(HERE/name) for name in FILES])
    return proof


def new_output_directory(path,value):
    global OUT
    path=pathlib.Path(path);C.need(path.is_absolute() and C.BASE in path.parents
        and not path.exists() and not any(p.is_symlink() for p in (path,*path.parents)),'NEW_OWN_V3_OUTPUT_REQUIRED')
    path.mkdir(parents=True,exist_ok=False,mode=0o700);OUT=path
    for name in ('packets','dispatch','starts','errors','reservations'): (path/name).mkdir()
    return path


def disk_bytes(root):
    total=0
    for item in (root,*root.rglob('*')):
        C.need(not item.is_symlink() and item.stat().st_uid==1278,'OWN_REGULAR_OUTPUT_TREE_REQUIRED')
        total+=item.stat().st_size
    return total


@contextmanager
def lock(root):
    with (root/'storage.lock').open('a+b') as stream:
        fcntl.flock(stream.fileno(),fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def reserved_bytes(root,excluding=None):
    total=0
    for path in (root/'reservations').glob('*.json'):
        if path.stem!=excluding:total+=json.loads(path.read_text())['bytes']
    return total


def fsync_dir(path):
    fd=os.open(str(path),os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def exclusive_raw(path,raw):
    fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    fsync_dir(path.parent)


def atomic_bytes(path,raw,*,reservation_key=None):
    path=pathlib.Path(path);root=OUT
    C.need(root is not None and root in path.parents and not path.exists(),'NEW_BOUNDED_STAGE_OUTPUT_REQUIRED')
    if ACTIVE_BUDGET is not None:
        ACTIVE_BUDGET.observe()
        if path.name in {'manifest.json','plan.json','prepared.json'}:
            C.need(ACTIVE_BUDGET.stop is None,'RESOURCE_STOP_NO_NEW_AUTHORITY_OR_READY_MANIFEST')
    with lock(root):
        C.need(disk_bytes(root)+len(raw)+reserved_bytes(root,reservation_key)+C.ADMIN<=C.CAP,'WHOLE_STAGE_DISK_RESERVATION_EXCEEDED')
        temp=path.with_name(path.name+'.pending-'+str(os.getpid()));exclusive_raw(temp,raw)
        C.need(not path.exists(),'IMMUTABLE_FINAL_OUTPUT_ALREADY_EXISTS');os.rename(temp,path);fsync_dir(path.parent)
        if reservation_key is not None:
            reservation=root/'reservations'/(reservation_key+'.json')
            if reservation.exists():reservation.unlink();fsync_dir(reservation.parent)
    return C.ref(path)


def write_json_new(path,value):return atomic_bytes(path,C.canonical(value)+b'\n')


def write_parquet_new(path,table):
    import pyarrow as pa
    import pyarrow.parquet as pq
    sink=pa.BufferOutputStream();pq.write_table(table,sink,compression='zstd',row_group_size=4096)
    return atomic_bytes(path,sink.getvalue().to_pybytes())


def reserve(root,key,n):
    with lock(root):
        C.need(disk_bytes(root)+reserved_bytes(root)+n+C.ADMIN<=C.CAP,'NO_SPACE_FOR_FULL_FAILED_OR_AUDIT_PACKET')
        exclusive_raw(root/'reservations'/(key+'.json'),C.canonical({'task_key':key,'bytes':n})+b'\n')


def import_once(row):
    path=C.ledger_path(row['task_key']);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if path.exists():C.need(json.loads(path.read_text())==row,'HISTORICAL_ONCE_LEDGER_CONFLICT_NO_UPGRADE_OR_DELETE')
    else:exclusive_raw(path,C.canonical(row)+b'\n')
    return C.ref(path)


def dispatch(task,prepared_reference,plan_reference,proof,out):
    meta=task['meta'];key=meta['task_key'];C.need(key==C.task_key(meta['molecule_id'],meta['cohort']),'ORIGINAL_TASK_KEY_REQUIRED')
    reserve(out,key,VALUE['packet_compressed_limit_bytes']+(1<<20))
    row={'schema':'SPRIME_DISPATCH_INTENT_V3','task_key':key,'molecule_id':meta['molecule_id'],'cohort':meta['cohort'],
        'task_sha256':C.sha_value(task),'seed':C.seed_for(meta['molecule_id'],meta['cohort']=='retry_once'),
        'kernel_sha256':C.KERNEL_SHA,'recipe_config':VALUE['recipe_config'],'prepared_reference':prepared_reference,
        'plan_reference':plan_reference,'job_id':str(proof['job_id']),'uid':os.getuid(),'node':socket.gethostname().split('.')[0],
        'parent_pid':os.getpid(),'parent_start_ticks':proc_ticks(os.getpid()),'boot_id':proof['boot_id'],
        'observed_unix_seconds':time.time(),'worker_started':False,'science_result_observed':False}
    ledger=C.ledger_path(key);ledger.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    exclusive_raw(ledger,C.canonical(row)+b'\n') # before submit: uncertain submission is consumed
    ref=C.ref(ledger);write_json_new(out/'dispatch'/(key+'.json'),{'ledger_reference':ref,'record':row})
    return ref


def load_science(value):
    refs=frozen_sources();old_io=common();C.module('selection',refs['selection'])
    science=C.module('science',refs['science']);science.worker_init(value['recipe_config']['path'])
    return old_io,science


def read_packet(reference,value):
    path=C.pinned(reference,value['packet_compressed_limit_bytes'])
    with gzip.open(path,'rb') as stream:raw=stream.read(value['packet_uncompressed_limit_bytes']+1)
    C.need(len(raw)<=value['packet_uncompressed_limit_bytes'],'BOUNDED_PACKET_DECOMPRESSION_REQUIRED')
    packet=json.loads(raw);mid=packet['summary']['molecule_id'];old_io=common()
    import numpy as np
    numbers=None;candidates=set()
    for position,row in enumerate(packet['conformers']):
        C.need(type(row['sprime_conf_idx']) is int and row['sprime_conf_idx']==position
            and type(row['below_dedup_threshold']) is bool and row['status']=='SUCCESS' and row['converged'] is True
            and all(type(z) is int and 1<=z<=118 for z in row['atomic_numbers']),
            'ORIGINAL_V2_STRICT_PACKET_ROW_INDEX_STATUS_AND_ATOM_TYPES_REQUIRED')
        atom_sha=hashlib.sha256(np.asarray(row['atomic_numbers'],dtype='<i8').tobytes()).hexdigest()
        C.need(row['molecule_id']==mid and atom_sha==row['atom_order_sha256']==packet['summary']['atom_order_sha256']
            and row['source_record_id']==packet['summary']['source_record_id']
            and old_io.geometry_sha(row['atomic_numbers'],row['coordinates'])==row['geometry_sha256']
            and np.isfinite(float(row['uff_energy_kcal_mol'])),
            'REAL_FLOAT64_GEOMETRY_ATOM_ORDER_ANCHOR_AND_FINITE_ENERGY_READBACK_REQUIRED')
        C.need(numbers is None or numbers==row['atomic_numbers'],'PACKET_ATOM_SEQUENCE_CHANGED');numbers=row['atomic_numbers']
        if row['origin']=='accepted_sprime':C.need(row['original_sprime_conf_idx'] is not None,'OLD_PHYSICAL_SOURCE_INDEX_REQUIRED')
        else:
            key=(row['seed'],row['candidate_id'])
            C.need(row['origin'] in {'data_v1_fill_10N','data_v1_fill_retry1'} and type(row['candidate_id']) is int
                and row['candidate_id']>=0 and key not in candidates,'ORIGINAL_V2_GENERATED_PROVENANCE_AND_UNIQUENESS_REQUIRED')
            candidates.add(key)
    return packet


class Budget:
    def __init__(self,proof,session,value,out):
        global ACTIVE_BUDGET
        reuse,Q,_=quota_reuse(session['quota_reuse_review_reference'],C.sources())
        self.client=Q.Client(reuse['provider_review_reference'],proof['request']);self.Q=Q;self.value=value;self.out=out
        self.reserve=reuse['whole_wave_output_reserve_bytes'];self.started=time.monotonic();self.next=0
        self.stop=None;self.samples=[];self.quota=[];self.failure=None;self.proof=proof
        wall=proof['request']['wall_seconds']
        reserve_seconds=value['stop_dispatch_before_wall_seconds'] if proof['request']['kind']=='conformer' else min(600,max(1,wall//10))
        C.need(reserve_seconds<wall,'REQUEST_WALL_MUST_EXCEED_THE_EXPLICIT_DISPATCH_RESERVE')
        self.wall_dispatch_cutoff_seconds=wall-reserve_seconds
        self.workers={};self.mutex=threading.RLock();self.finished=threading.Event();self.monitor=None;ACTIVE_BUDGET=self
    def start_monitor(self):
        def monitor():
            while not self.finished.wait(30):self.observe()
        self.monitor=threading.Thread(target=monitor,daemon=True,name='owned-formal-quota-memory-observer');self.monitor.start()
    def close_monitor(self):
        self.finished.set()
        if self.monitor is not None:self.monitor.join(timeout=40)
    def observe(self,processes=()):
        with self.mutex:
            for process in processes:
                try:
                    pid=process.pid
                    if pid and process.is_alive():self.workers[pid]=proc_ticks(pid)
                except (ValueError,FileNotFoundError):pass
            return self._observe()
    def _observe(self):
        try:
            children=pathlib.Path('/proc/self/task',str(os.getpid()),'children')
            for text in children.read_text().split():
                pid=int(text)
                try:
                    if pathlib.Path('/proc',str(pid)).stat().st_uid==1278:self.workers.setdefault(pid,proc_ticks(pid))
                except FileNotFoundError:pass
            rss=0;pids=[os.getpid()]
            for pid,ticks in self.workers.items():
                try:
                    if pathlib.Path('/proc',str(pid)).stat().st_uid==1278 and proc_ticks(pid)==ticks:pids.append(pid)
                except FileNotFoundError:pass
            for pid in pids:
                try:rss+=int(pathlib.Path('/proc',str(pid),'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                except FileNotFoundError:pass
            available=next(int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
            with lock(self.out):managed=disk_bytes(self.out);reserved=reserved_bytes(self.out)
            sample={'unix':time.time(),'rss_bytes':rss,'MemAvailable':available,'managed_output_bytes':managed,'pids':pids}
            if len(self.samples)<1024:self.samples.append(sample)
            else:self.samples[-1]=sample
            if rss>self.value['algorithm_rss_soft_cap_bytes'] or available<self.value['minimum_MemAvailable_bytes']:self.stop=self.stop or 'MEMORY_STOP_NEW_DISPATCH'
            if time.monotonic()-self.started>=self.wall_dispatch_cutoff_seconds:self.stop=self.stop or 'WALL_STOP_NEW_DISPATCH'
            prior=self.client.last
            if prior and (time.time()-prior.get('observed_unix_seconds',0)>120 or time.time()>=prior.get('publisher_expires_unix_seconds',0)):self.next=0
            if time.monotonic()>=self.next:
                row=self.client.observe();self.next=time.monotonic()+60
                if len(self.quota)<1024:self.quota.append(row)
                else:self.quota[-1]=row
                if row['free_bytes']-self.reserve-self.Q.CAP-C.ADMIN<200000000000:self.stop=self.stop or 'ACCOUNT_QUOTA200GB_STOP_NEW_DISPATCH'
            if managed+reserved+C.ADMIN>C.CAP:self.stop=self.stop or 'DISK_CAP_STOP_NEW_DISPATCH'
        except Exception as exc:self.failure={'error':repr(exc),'last_quota_evidence':self.client.last};self.stop=self.stop or 'RESOURCE_OBSERVATION_UNAVAILABLE'
        return self.stop
    def report(self):return {'stop_new_dispatch':self.stop,'actual_memory_observations':self.samples,'actual_quota_observations':self.quota,
        'observation_failure':self.failure,'cost_policy':'REPORT_AND_CONTINUE','full_forecast_core_hours':None,
        'wall_dispatch_cutoff_seconds':self.wall_dispatch_cutoff_seconds,
        'signals_sent_to_science':False,'natural_drain':True,'whole_wave_output_reserved_bytes':self.reserve,'publisher_reserved_bytes':self.Q.CAP}


# Explicit adapter used by the copied physical-ID finalizer, without mutating old modules.
class IO:
    reference=staticmethod(C.ref);require_pin=staticmethod(C.pinned);digest=staticmethod(lambda p:C.ref(p)['sha256'])
    new_output_directory=staticmethod(new_output_directory);write_json_new=staticmethod(write_json_new)
    write_parquet_new=staticmethod(write_parquet_new)
    @staticmethod
    def geometry_sha(numbers,coordinates):return common().geometry_sha(numbers,coordinates)


def authority_roles(value):
    authority=C.read(value['roles_authority']);manifest_ref=authority['source_role_manifest'];authorized(PROOF,[manifest_ref]);manifest=C.read(manifest_ref)
    C.need(authority['validation_source']=='ROUTINE' and manifest['status']=='ROUTINE_MOLECULE_VAL_ROLES_FROZEN','FROZEN_ROUTINE_ROLES_REQUIRED')
    refs=[C.triple(p) for p in manifest['outputs'] if '/molecule_roles/' in p['path']]
    C.need(len(refs)==16,'ALL16_ROLE_PARTS_REQUIRED');authorized(PROOF,refs)
    for reference in refs:C.pinned(reference)
    return manifest_ref,refs


def formal_source(value):
    receipt=C.read(value['formal_source_receipt']);C.need(receipt['status']=='ALL_BOUND_INPUTS_SHA_VERIFIED','CLOSED_CANONICAL_SOURCE_REQUIRED')
    outputs=[row for row in receipt['outputs'] if row['name']=='formal_population'];C.need(len(outputs)==1,'UNIQUE_CANONICAL_SOURCE_REQUIRED')
    row=outputs[0];reference=row['reference'];authorized(PROOF,[reference]);info=pathlib.Path(reference['path']).stat();expected=row['after']
    C.need((info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_uid)==
        (expected['device'],expected['inode'],expected['size'],expected['mtime_ns'],expected['uid']),'CANONICAL_SOURCE_PHYSICAL_IDENTITY_CHANGED')
    C.pinned(reference);return reference


def input_locators(config_path,quota_reuse_review_path,pilot_review_path=None):
    """Small Root helper: enumerate actual refs, never read a scientific body."""
    config_ref=C.ref(config_path);value=C.config(config_ref);refs=C.sources()
    quota_ref=C.ref(quota_reuse_review_path);_,_,quota_refs=quota_reuse(quota_ref,refs)
    authority=C.read(value['roles_authority']);roles_ref=authority['source_role_manifest'];roles=C.read(roles_ref)
    formal=C.read(value['formal_source_receipt']);sprime=C.read(value['sprime_manifest'])
    inputs=[config_ref,quota_ref,*quota_refs,roles_ref,authority['actual_closure'],
        *[value[k] for k in ('recipe_config','roles_authority','per_molecule','formal_source_receipt','sprime_manifest')]]
    inputs.extend(C.triple(r) for r in roles['outputs'] if '/molecule_roles/' in r['path'])
    inputs.extend(r['reference'] for r in formal['outputs'] if r['name']=='formal_population')
    inputs.extend(C.triple(r) for r in sprime['references'] if r['kind']=='conformers')
    if pilot_review_path is not None:
        pilot_ref=C.ref(pilot_review_path);pilot=C.read(pilot_ref);report=C.read(pilot['closure_report']);terminals=C.read(pilot['terminal_outcomes'])
        inputs.extend([pilot_ref,*[pilot[k] for k in ('closure_report','terminal_outcomes','pilot_tasks','actual_accounting')]])
        inputs.append(C.read(pilot['actual_accounting'])['raw_sacct_reference'])
        inputs.extend(C.triple(row['package_reference']) for row in terminals if row['package_reference'] is not None)
    sources=[C.ref(HERE/name) for name in FILES]+list(refs.values())
    unique={}
    for row in inputs:
        row=C.triple(row);C.need(row['path'] not in unique or unique[row['path']]==row,'CONFLICTING_TRANSITIVE_INPUT_PINS');unique[row['path']]=row
    source_paths={p['path'] for p in sources}
    return {'schema':'SPRIME_FORMAL_CPU_INPUT_LOCATORS_V3','source_references':sources,'input_references':[p for p in unique.values() if p['path'] not in source_paths],
        'scientific_bodies_read':False,'LMDB_read':False,'new_UFF_QM_calls':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Small exact refs only; no scientific body or startup')
    parser.add_argument('--config',type=pathlib.Path,required=True);parser.add_argument('--quota-reuse-review',type=pathlib.Path,required=True)
    parser.add_argument('--pilot-review',type=pathlib.Path)
    args=parser.parse_args();print(json.dumps(input_locators(args.config,args.quota_reuse_review,args.pilot_review),ensure_ascii=False))
