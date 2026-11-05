"""Explicit resource context;original scientific loader/packet reader objects."""
from __future__ import annotations
import argparse,fcntl,gzip,hashlib,importlib.util,json,os,pathlib,shlex,socket,sys,threading,time,traceback
from contextlib import contextmanager
from . import contract as C
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import runtime_io as ORIGINAL
HERE=C.HERE;FILES=C.FILES;PY=C.Q.PY;OUT=None;PROOF=None;SESSION=None;VALUE=None;ACTIVE_BUDGET=None
common=ORIGINAL.common;load_science=ORIGINAL.load_science;read_packet=ORIGINAL.read_packet;proc_ticks=ORIGINAL.proc_ticks;input_ref=ORIGINAL.input_ref
def output_cap():return C.CAP if PROOF is None else min(C.CAP,PROOF['request']['estimated_peak_output_bytes'])
def authorized(proof,references):
    allowed=proof['request']['source_references']+proof['request']['data_references']
    for ref in references:C.need(C.source_shape(ref) in allowed,'EXACT_REGISTERED_TRANSITIVE_RESOURCE_OR_DATA_REFERENCE')
def quota_reuse(reference,refs):
    from . import edge
    return edge.quota_reuse(reference,refs)
def admit(script,args,stage,options):
    global OUT,PROOF,SESSION,VALUE
    config_ref=input_ref(args.root_preflight,args.config);value=C.config(config_ref);refs=C.sources()
    quota_ref=input_ref(args.root_preflight,args.quota_reuse_review);reuse,edge,parents=quota_reuse(quota_ref,refs)
    argv=[PY,'-B',str(pathlib.Path(script).absolute())]
    if hasattr(args,'mode'):argv.append(args.mode)
    required=[config_ref,quota_ref,*[value[k] for k in ('recipe_config','roles_authority','per_molecule','formal_source_receipt','sprime_manifest')]]
    for name in options:
        item=getattr(args,name.replace('-','_'),None)
        if item is None:continue
        if isinstance(item,pathlib.Path):
            C.need(item.is_absolute() and '..' not in item.parts,'LITERAL_ABSOLUTE_CLI')
            if name not in ('root-preflight','output'):required.append(input_ref(args.root_preflight,item))
        argv.extend(['--'+name,str(item)])
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime
    proof=runtime.require_startup(args.root_preflight,expected_scope_key='sprime_multinode_resource_v1_'+stage,
        expected_scope_parameters=C.scope(stage,config_ref),expected_execution_argv=argv,expected_source=script,
        expected_kind=C.STAGES[stage],required_references=[*required,*C.own_sources(),*refs.values(),*parents])
    request=proof['request'];C.need(request['pilot'] is False and C.node(request['node'])==reuse['compute_node'] and request['cpus']==16
        and request['estimated_peak_output_bytes']==C.CAP and request['wall_seconds']<=172800,'EXACT_ACTUAL_NODE_CPU16_NO_MEM_8G_STAGE')
    edge.execution(reuse,request,active=True)
    os.environ.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS')})
    session={'proof_reference':C.ref(args.root_preflight),'main_source':C.ref(script),'execution_argv':argv,'parent_pid':os.getpid(),
        'parent_start_ticks':proc_ticks(os.getpid()),'boot_id':proof['boot_id'],'job_id':str(proof['job_id']),
        'node':request['node'],'quota_reuse_review_reference':quota_ref}
    PROOF=proof;SESSION=session;VALUE=value;return value,proof,session,config_ref
def continuation(session,check_sources=False):
    proof=C.read(session['proof_reference']);request=proof['request']
    C.need(os.getppid()==session['parent_pid'] and proc_ticks(os.getppid())==session['parent_start_ticks'] and os.getuid()==1278==proof['uid']
        and str(proof['job_id'])==session['job_id']==os.environ.get('SLURM_JOB_ID') and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==session['boot_id']==proof['boot_id']
        and request['node']==session['node']==socket.gethostname().split('.')[0] and C.node(session['node'])==session['node']
        and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('SLURM_JOB_PARTITION')=='cpu'
        and os.environ.get('CUDA_VISIBLE_DEVICES')=='','SAME_LIVE_PARENT_START_BOOT_NODE_JOB_UID_CPU_NO_GPU')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import primary_binding
    main=pathlib.Path(sys.modules['__main__'].__file__).absolute()
    C.need(C.ref(main)==session['main_source'] and request['execution_argv']==session['execution_argv'],'ACTUAL_PRIMARY_UNCHANGED')
    primary_binding(request,main,sys.argv[1:])
    if check_sources:authorized(proof,C.own_sources())
    return proof
def new_output_directory(path,value):
    global OUT
    path=pathlib.Path(path);C.need(path.is_absolute() and C.BASE in path.parents and '..' not in path.parts
        and not path.exists() and not any(p.is_symlink() for p in (path,*path.parents)),'FRESH_SHARED_OWN_OUTPUT_NO_OLD_OVERWRITE')
    path.mkdir(parents=True,exist_ok=False,mode=0o700);OUT=path
    for name in ('packets','dispatch','starts','errors','reservations'):(path/name).mkdir()
    return path
def formal_source(value):
    from . import edge
    reuse=C.read(SESSION['quota_reuse_review_reference']);binding=C.binding(reuse['node_binding_reference'])
    receipt=C.read(value['formal_source_receipt']);row=next(r for r in receipt['outputs'] if r['name']=='formal_population');ref=row['reference']
    C.need(receipt['status']=='ALL_BOUND_INPUTS_SHA_VERIFIED' and ref==binding['canonical_reference'],'ORIGINAL_CANONICAL_REFERENCE_AUTHORITY')
    authorized(PROOF,[ref]);path=pathlib.Path(ref['path']);before=C.frame(path.stat());C.same_source(row['after'],before)
    C.need(before==binding['canonical_expected_frame'],'ACTUAL_NODE_PROBE_CURRENT_CANONICAL_FRAME')
    C.pinned(ref);C.need(C.frame(path.stat())==before,'CPU_WHOLE_SHA_STABLE_CANONICAL_FRAME')
    write_json_new(OUT/'canonical_source_current_mount_identity.json',{'reference':ref,'origin_frame':row['after'],'actual_frame':before,
        'node_binding_reference':reuse['node_binding_reference'],'whole_SHA_verified_on_actual_CPU':True,'device_translation_only':True});return ref
def validate_slot(plan,proof,out):return C.authorize_slot(plan,proof,out)
def validate_terminal_resource(descriptor,request,slot):
    prepared=C.read(descriptor['prepared']);parent=C.read(descriptor['submission']);proof_path=pathlib.Path(request['startup_proof_path'])
    original_proof=C.read(C.ref(proof_path));C.need(str(original_proof['job_id'])==str(parent['job_id']) and original_proof['request']==request,'ACTUAL_TERMINAL_PARENT_STARTUP_NOT_CURRENT_CLOSE_PROOF')
    if request['scope_key']=='sprime_formal_cpu_auto_v3_run':
        C.need(request['node']==slot['node']=='compute-0-13' and request['cpus']==slot['cpus']==16,'ACTUAL_HISTORICAL_NODE13_RESOURCE_IDENTITY_NOT_RELABELED')
        current=C.read(SESSION['quota_reuse_review_reference']);epoch=C.epoch(current['epoch_reference'],active=False);adoption=C.read(epoch['adoption_reference'])
        hits=[r for r in adoption['registrations'] if r['batch_id']==slot['batch_id'] and r['stage']=='run' and str(r['job_id'])==str(parent['job_id'])]
        C.need(len(hits)==1 and hits[0]['registration']['request_reference']==descriptor['request'] and hits[0]['registration']['submission_reference']==descriptor['submission'],
            'EXACT_ROOT_ADOPTION_OF_REAL_HISTORICAL_PARENT_REQUIRED_FOR_NEW_NODE_READBACK')
        return True
    argv=request['execution_argv'];reuse_path=argv[argv.index('--quota-reuse-review')+1];reuse=C.read(C.ref(reuse_path))
    from . import edge
    edge.execution(reuse,request,active=False)
    C.need(request['node']==reuse['compute_node'] and prepared['plan']==descriptor['plan'] and slot['whole_output_cap_bytes']==C.CAP,'ROOT_APPROVED_NODE_MAPPING_SAME_ORIGINAL_PLAN')
    return True
def terminal_primary(request):
    C.need(request['scope_key'] in ('sprime_formal_cpu_auto_v3_run','sprime_multinode_resource_v1_run'),'ONLY_EXACT_ORIGINAL_OR_NEW_RESOURCE_RUN')
    return str((C.ORIGINAL.HERE if request['scope_key']=='sprime_formal_cpu_auto_v3_run' else C.HERE)/'run_batch.py')
def finish_resource_entry(failure):
    """Preserve the first latched resource report even if prepare fails early."""
    if ACTIVE_BUDGET is not None:ACTIVE_BUDGET.close_monitor()
    if OUT is not None and OUT.exists():
        write_json_new(OUT/'resource_entry_observations.json',{'schema':'ACTUAL_MULTINODE_ENTRY_RESOURCE_OBSERVATIONS_V1',
            'budget':ACTIVE_BUDGET.report() if ACTIVE_BUDGET else None,'failure':failure,
            'job_id':str(PROOF['job_id']) if PROOF else None,'observation_failure_is_not_inferred_as_quota_exhaustion':True,
            'latched_stop_cleared':False,'new_signals_sent':0})

# BEGIN ORIGINAL RESOURCE IO REGION
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
        C.need(disk_bytes(root)+len(raw)+reserved_bytes(root,reservation_key)+C.ADMIN<=output_cap(),'WHOLE_STAGE_DISK_RESERVATION_EXCEEDED')
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
        C.need(disk_bytes(root)+reserved_bytes(root)+n+C.ADMIN<=output_cap(),'NO_SPACE_FOR_FULL_FAILED_OR_AUDIT_PACKET')
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


class Budget:
    def __init__(self,proof,session,value,out):
        global ACTIVE_BUDGET
        reuse,Q,_=quota_reuse(session['quota_reuse_review_reference'],C.sources())
        self.client=Q.Client(reuse['node_binding_reference'],proof['request']);self.Q=Q;self.value=value;self.out=out
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
            if managed+reserved+C.ADMIN>output_cap():self.stop=self.stop or 'DISK_CAP_STOP_NEW_DISPATCH'
        except Exception as exc:self.failure={'error':repr(exc),'last_quota_evidence':self.client.last};self.stop=self.stop or 'RESOURCE_OBSERVATION_UNAVAILABLE'
        return self.stop
    def report(self):return {'stop_new_dispatch':self.stop,'actual_memory_observations':self.samples,'actual_quota_observations':self.quota,
        'observation_failure':self.failure,'cost_policy':'REPORT_AND_CONTINUE','full_forecast_core_hours':None,
        'wall_dispatch_cutoff_seconds':self.wall_dispatch_cutoff_seconds,
        'signals_sent_to_science':False,'natural_drain':True,'whole_wave_output_reserved_bytes':self.reserve,'publisher_reserved_bytes':self.Q.CAP}


# END ORIGINAL RESOURCE IO REGION
