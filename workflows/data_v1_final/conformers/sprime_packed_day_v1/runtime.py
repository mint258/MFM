"""Explicit packed64/24h context and durable IO; no old CLI/global patching."""
import contextlib,fcntl,hashlib,json,os,pathlib,socket,stat,threading,time
from workflows.data_v1_final.labels.normalization_compact_runtime_v2.runtime import wall_clock,remaining_wall
from . import contract as C
from workflows.data_v1_final.execution import finite_quota_observation_guard_v1 as QuotaGuard


def ticks(pid):return pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19]
def frame(info):return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,info.st_uid)


def identity(proof):
    request=proof['request'];C.need(os.getuid()==1278 and socket.gethostname().split('.')[0]==request['node'] and request['node'] in ('compute-0-14','compute-0-18')
        and os.environ.get('SLURM_JOB_ID')==str(proof['job_id']) and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==request['cpus']
        and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==proof['boot_id'],'ACTUAL_PACKED_PARENT_OR_CHILD_CPU_IDENTITY')


def authorized(proof,refs):
    allowed=proof['request']['source_references']+proof['request']['data_references']
    for ref in refs:C.need(C.F.triple(ref) in allowed,'PACKED_INPUT_NOT_IN_EXACT_ROOT_REQUEST:'+ref['path'])


def sha_file(path,limit=None,check=lambda:None):
    path=pathlib.Path(path);before=path.lstat();C.need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and not path.is_symlink(),'OWN_LITERAL_REGULAR_FILE')
    if limit is not None:C.need(before.st_size<=limit,'BOUNDED_SOURCE_OR_PACKET')
    h=hashlib.sha256();size=0
    with path.open('rb') as stream:
        C.need(frame(os.fstat(stream.fileno()))==frame(before),'SAME_SOURCE_FD')
        for raw in iter(lambda:stream.read(1<<20),b''):check();h.update(raw);size+=len(raw)
        C.need(frame(os.fstat(stream.fileno()))==frame(before)==frame(path.lstat()),'CURRENT_SOURCE_FRAME_CHANGED')
    C.need(size==before.st_size,'EXACT_SOURCE_EOF')
    return {'path':str(path),'bytes':size,'sha256':h.hexdigest()}


def verify(ref,check=lambda:None):
    C.reference_shape(ref);actual=sha_file(ref['path'],ref['bytes'],check);C.need(actual==C.F.triple(ref),'ACTUAL_WHOLE_DATA_SHA');return pathlib.Path(ref['path'])


def read_json(ref,limit=2<<20):
    path=verify(ref);C.need(path.stat().st_size<=limit,'EXPLICIT_JSON_CONTAINER_BOUND');return json.loads(path.read_bytes())


def fsync_dir(path):
    fd=os.open(str(path),os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def exclusive(path,raw):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    fsync_dir(path.parent);return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def save(path,value):return exclusive(path,C.F.canonical(value)+b'\n')


def state_read(out):return json.loads((pathlib.Path(out)/'writer_state.json').read_text())
def state_write(out,value):
    path=pathlib.Path(out)/'writer_state.json';tmp=path.with_name(path.name+'.pending-'+str(os.getpid())+'-'+str(time.time_ns()))
    exclusive(tmp,C.F.canonical(value)+b'\n');os.replace(tmp,path);fsync_dir(path.parent)


def workspace_bytes(out):
    total=0
    for name in ('census.sqlite','census.sqlite-journal','census.sqlite-wal','census.sqlite-shm'):
        try:
            info=(pathlib.Path(out)/name).lstat();C.need(stat.S_ISREG(info.st_mode) and info.st_uid==1278,'OWN_DECLARED_SQLITE_WORKSPACE');total+=info.st_size
        except FileNotFoundError:pass
    return total


def write_bounded(out,cap,path,raw,key=None,release=False):
    out=pathlib.Path(out);path=pathlib.Path(path)
    C.need(out in path.parents and not path.exists() and len(raw)<=cap,'FRESH_PACKED_OWN_OUTPUT_PATH')
    with owned_lock(out/'output_storage.lock'):
        state=state_read(out);reservations=state['reservations'];reserved=sum(n for k,n in reservations.items() if k!=key)
        C.need(state['charged_written_bytes']+workspace_bytes(out)+reserved+len(raw)+(64<<20)<=cap,'EXACT_PACKED_OUTPUT_AND_ACTIVE_NATIVE_RESERVATIONS')
        ref=exclusive(path,raw);state['charged_written_bytes']+=len(raw)
        if release and key is not None:reservations.pop(key,None)
        state_write(out,state);return ref


@contextlib.contextmanager
def owned_lock(path):
    path=pathlib.Path(path);fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        info=os.fstat(fd);C.need(stat.S_ISREG(info.st_mode) and info.st_uid==1278 and info.st_nlink==1,'OWN_SINGLE_LINK_LOCK')
        fcntl.flock(fd,fcntl.LOCK_EX);yield fd
    finally:os.close(fd)


def admit(args,plan):
    from workflows.data_v1_final.execution.cpu_packed_day_v2.runtime import require_startup
    argv=[C.PY,'-B','-m',C.MODULE,'--plan',str(args.plan),'--startup-proof',str(args.startup_proof)]
    required=[C.small_pin(args.plan),*(plan[k] for k in ('inputs_review_reference','resource_authority_reference','quota_provider_review_reference',
        'quota_provider_identity_reference','root_carveout_review_reference','original_plan_reference','original_config_reference','source_mapping_review_reference'))]
    proof=require_startup(args.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=C.parameters(plan),expected_execution_argv=argv,
        expected_source=C.HERE/'run.py',expected_kind='conformer',required_references=required)
    req=proof['request'];C.need(req['cpus']==req['requested_cpus']==plan['cpus'] and req['wall_seconds']==86400 and req['node']==plan['node'] and plan['packed_resource_contract_version']==2
        and req['kind']=='conformer' and req['pilot'] is False and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and req['producer_plan_reference']==C.small_pin(args.plan),'REAL_PACKED_RESOURCE_CONTEXT_NOT_OLD16_SCOPE')
    for ref in C.sources():C.need(ref in req['source_references'],'PACKED_AND_UNCHANGED_ORIGINAL_SOURCE_PINS')
    identity(proof);return proof


class Budget:
    def __init__(self,plan,proof,out):
        from workflows.data_v1_final.execution.cpu_packed_day_v2.quota_provider import Client
        self.plan,self.proof,self.out=plan,proof,pathlib.Path(out);self.cap=plan['output_cap_bytes'];self.lock=threading.RLock()
        self.clock=wall_clock(proof,86400);self.pid=os.getpid();self.start_ticks=ticks(self.pid);self.stop=None;self.failure=None
        self.reserved={};self.next=0;self.samples=[];self.client=Client(plan['quota_provider_review_reference'],proof['request'])
        self.carveout=C.metadata_ref(plan['root_carveout_review_reference']);self.last_used=0
        self.quota_event_count=0;self.quota_event_bytes=0;self.quota_event_references=[]
        save(self.out/'wall_clock_budget.json',self.clock)
        initial=sum(p.stat().st_size for p in self.out.iterdir() if p.is_file())
        save(self.out/'writer_state.json',{'schema':'PACKED_PRIVATE_MUTABLE_WRITER_STATE_V1','charged_written_bytes':initial,'reservations':{}})
    def used(self):
        # Immutable writer bytes plus exact declared database sizes. Avoid an
        # O(molecules squared) rglob on a growing shared-filesystem packet tree.
        state=state_read(self.out);total=state['charged_written_bytes']+workspace_bytes(self.out)
        self.last_used=total;return total
    def record_quota_event(self,event):
        value={'schema':'PACKED_PERSISTENT_QUOTA_OBSERVATION_EVIDENCE_V1','actual_single_parent_job_id':str(self.proof['job_id']),
            'uid':os.getuid(),'node':self.proof['node'],'expected_identity_reference':self.plan['quota_provider_identity_reference'],
            'resource_event':event,'native_retry_or_provider_change':False}
        raw=C.F.canonical(value)+b'\n'
        C.need(len(raw)<=256<<10 and self.quota_event_count<6400 and self.quota_event_bytes+len(raw)<=64<<20,
            'FINITE_SMALL_PERSISTENT_QUOTA_EVIDENCE_CAP_STOP_NOT_DROP')
        path=self.out/'resource_quota_events'/('%05d_%d.json'%(self.quota_event_count,time.time_ns()))
        ref=self.write(path,raw);self.quota_event_count+=1;self.quota_event_bytes+=len(raw);self.quota_event_references.append(ref)
        return ref
    def observe(self,children=(),force=False):
        with self.lock:
            if not force and time.monotonic()<self.next:return self.stop
            self.next=time.monotonic()+30
            try:
                identity(self.proof);C.need(os.getpid()==self.pid and ticks(self.pid)==self.start_ticks,'SAME_REAL_PACKED_PARENT')
                direct=pathlib.Path('/proc/self/task',str(self.pid),'children').read_text().split()
                pids={self.pid,*children,*(int(pid) for pid in direct)};rss=0
                for pid in pids:
                    try:rss+=int(pathlib.Path('/proc',str(pid),'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                    except FileNotFoundError:pass
                mem=next(int(r.split()[1])*1024 for r in pathlib.Path('/proc/meminfo').read_text().splitlines() if r.startswith('MemAvailable:'))
                if rss>=self.plan['algorithm_rss_soft_cap_bytes'] or mem<self.plan['minimum_MemAvailable_bytes']:self.stop=self.stop or 'MEMORY_STOP_NEW_NATIVE_TASKS'
                if remaining_wall(self.clock,time.monotonic())<=900:self.stop=self.stop or 'DAY_WALL_STOP_NEW_NATIVE_TASKS_NATURAL_DRAIN'
                quota=QuotaGuard.observe(self.client,expected_identity_reference=self.plan['quota_provider_identity_reference'],record=self.record_quota_event);C.need(self.client.identity==self.plan['quota_provider_identity_reference'],'SAME_EXACT_NEW_FINITE_QUOTA_IDENTITY')
                # This total already includes the packed writer carved from the
                # original reservation. Never add its cap a second time.
                future=self.carveout['total_future_reserved_bytes']
                C.need(type(future) is int and future>=self.cap and self.carveout['future_after_carveout_not_greater_than_before'] is True,
                    'ROOT_ACTUAL_CARVEOUT_TOTAL_NO_DOUBLE_RESERVATION_OR_INCREASE')
                if quota['free_bytes']-future-200000000000<0:self.stop=self.stop or 'ACCOUNT200GB_STOP_NEW_NATIVE_TASKS'
                C.need(quota['publisher_expires_unix_seconds']>=self.clock['cpu_wall_at_anchor']+self.clock['remaining_at_anchor_seconds']+300,
                    'FINITE_PROVIDER_DOES_NOT_COVER_THIS_REAL_PARENT_WALL_PLUS300')
                state=state_read(self.out)
                if self.used()+sum(state['reservations'].values())+(64<<20)>self.cap:self.stop=self.stop or 'OUTPUT_CAP_STOP_NEW_NATIVE_TASKS'
                value={'unix_seconds':time.time(),'rss_bytes':rss,'MemAvailable':mem,'used_bytes':self.last_used,'reserved_bytes':sum(self.reserved.values()),
                    'remaining_wall_seconds':remaining_wall(self.clock,time.monotonic()),'quota':quota,'stop':self.stop}
                self.samples.append(value)
                if len(self.samples)>1024:self.samples=self.samples[-1024:]
            except Exception as exc:
                self.failure={'error':repr(exc),'last_quota_evidence':self.client.last};self.stop=self.stop or 'RESOURCE_OBSERVATION_UNKNOWN_STOP_NEW_NATIVE_TASKS'
            return self.stop
    def reserve(self,key,n):
        with self.lock:
            self.observe();C.need(self.stop is None,self.stop or 'RESOURCE_STOP')
            with owned_lock(self.out/'output_storage.lock'):
                state=state_read(self.out);C.need(key not in state['reservations']
                    and state['charged_written_bytes']+workspace_bytes(self.out)+sum(state['reservations'].values())+n+(64<<20)<=self.cap,'FULL_PACKET_AND_DRAIN_RESERVATION')
                state['reservations'][key]=n;state_write(self.out,state)
    def release(self,key):
        with self.lock,owned_lock(self.out/'output_storage.lock'):
            state=state_read(self.out);state['reservations'].pop(key,None);state_write(self.out,state)
    def write(self,path,raw,key=None):
        # In-flight workers may persist their already reserved full result when
        # stop-new is latched. This never starts another molecule or sends a signal.
        return write_bounded(self.out,self.cap,path,raw,key)
    def report(self):return {'stop_new_native_tasks':self.stop,'observation_failure':self.failure,'last1024_observations':self.samples,
        'observations_are_tail_not_complete_error_log':True,'reserved_packet_bytes':sum(state_read(self.out)['reservations'].values()),'clock':self.clock,
        'quota_observation_event_count':self.quota_event_count,'quota_observation_event_bytes':self.quota_event_bytes,
        'quota_observation_event_references':self.quota_event_references,'original_provider_age_and_expiry_guards_changed':False,
        'signals_sent':False,'provider_auto_renewed':False,'cost_policy':'REPORT_AND_CONTINUE'}


def canonical_source(value,proof,mapping_reference,out,check):
    """Root actual14/18 storage bridge; old13 witnesses remain unmodified."""
    from workflows.data_v1_final.conformers.formal_cpu_auto_prepare_mapping_v1 import mapping as M
    from workflows.data_v1_final.execution.cpu_analysis_day_v1 import quota_provider as QP
    mapping=C.metadata_ref(mapping_reference);authorized(proof,[mapping_reference]);req=proof['request']
    C.need(mapping['schema']=='ROOT_SPRIME_PACKED_MULTINODE_SOURCE_MOUNT_MAPPING_V2' and mapping['status']=='APPROVED_EXACT_CANONICAL_SOURCE_MAPPING'
        and mapping['reviewer']=='root' and mapping['uid']==1278 and mapping['endpoint']=='202.38.247.57:22'
        and mapping['node']==proof['node']==req['node'] and mapping['node'] in ('compute-0-14','compute-0-18')
        and mapping['current_physical_device_is_endpoint_local_not_source_identity']is True,'EXACT_CURRENT_MAPPED_NODE_CANONICAL_AUTHORITY')
    old=C.metadata_ref(mapping['historical_node13_source_mapping_reference'])
    C.need(old['schema']=='ROOT_SPRIME_NODE13_SOURCE_MOUNT_MAPPING_V1' and old['status']=='APPROVED_EXACT_CANONICAL_SOURCE_MAPPING'
        and old['reviewer']=='root' and old['node']=='compute-0-13' and old['uid']==1278 and old['endpoint']=='202.38.247.57:22'
        and old['formal_source_receipt']==mapping['formal_source_receipt']==value['formal_source_receipt']
        and old['prior_cpu_source_validation']==mapping['prior_cpu_source_validation'] and old['historical_frame']==mapping['historical_frame'],
        'UNCHANGED_TRUE_NODE13_ORIGINAL_CANONICAL_WITNESS')
    provider=QP.load_review(req['quota_provider_review_reference'])
    C.need(mapping['same_storage_mapping']==provider['probe_reference'] and mapping['quota_provider_review']==req['quota_provider_review_reference']
        and set(provider['compute_mount_by_node'])=={req['node']},'ACTUAL_THIS_NODE_SHARED_STORAGE_AND_FINITE_PROVIDER')
    receipt=C.metadata_ref(value['formal_source_receipt']);row=next(r for r in receipt['outputs'] if r['name']=='formal_population');ref=row['reference']
    C.need(receipt['status']=='ALL_BOUND_INPUTS_SHA_VERIFIED' and ref==M.EXPECTED and row['after']==mapping['historical_frame'],'ORIGINAL_CLOSED_SOURCE_AND_EXACT_HISTORICAL_FRAME')
    validation=C.metadata_ref(mapping['prior_cpu_source_validation']);prior=[r for r in validation['inputs'] if r.get('reference')==ref]
    C.need(validation['status']=='ALL_ACTUAL_SOURCE_SHA_VERIFIED' and validation['runtime']['job_id']=='4521417' and len(prior)==1
        and prior[0]['actual']==ref and prior[0]['status']=='ACTUAL_FULL_SHA_MATCH' and prior[0]['inode']==row['after']['inode'] and prior[0]['mtime_ns']==row['after']['mtime_ns']
        and prior[0]['uid']==1278,'ACTUAL_OLD_CPU13_SOURCE_FRAME_AND_SHA_AUTHORITY')
    authorized(proof,[ref,mapping['historical_node13_source_mapping_reference'],*[mapping[k] for k in (
        'formal_source_receipt','prior_cpu_source_validation','same_storage_mapping','quota_provider_review')]])
    path=pathlib.Path(ref['path']);before=path.stat()
    C.need(M.source_frame(before)==M.expected_frame(row['after']),'EXACT_ORIGINAL_INODE_SIZE_MTIME_UID')
    verify(ref,check);after=path.stat();C.need(M.stable_frame(before)==M.stable_frame(after),'STABLE_CURRENT_DEVICE_AND_SOURCE_FRAME')
    save(out/'canonical_source_current_mount_identity.json',{'reference':ref,'mapping_reference':mapping_reference,
        'historical_node13_mapping_reference':mapping['historical_node13_source_mapping_reference'],'historical_frame':row['after'],
        'actual_node':proof['node'],'actual_current_frame':dict(zip(('device','inode','size','mtime_ns','uid'),M.stable_frame(after))),
        'whole_SHA_verified_in_this_actual_parent':True,'current_device_not_claimed_equal_to_node13':True})

    return ref
