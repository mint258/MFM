"""D6 index-only Main/Lustre observer. No ledger writes, credit or scientific IO."""
import fcntl,hashlib,json,os,pathlib,socket,stat,subprocess,threading,time,traceback,types
from workflows.data_v1_final.execution.cpu_analysis_day_v1 import quota_provider as DAY
from workflows.data_v1_final.execution import finite_quota_observation_guard_v1 as GUARD
from workflows.data_v1_final.labels.normalization_compact_runtime_v2.runtime import wall_clock,remaining_wall
from workflows.data_v1_final.export.pilot_family_D3_local_store_v6 import queued_quota as OLD_LFS
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
MAIN_LEDGER=ROOT/'control/root_current_all_future_ledger_v1.json';MAIN_LOCK=MAIN_LEDGER.with_suffix('.lock')
LFS_LEDGER=ROOT/'control/root_lustre_all_future_ledger_v1.json';LFS_LOCK=LFS_LEDGER.with_suffix('.lock')
FLOOR=100000000000;MAIN_CAP=64<<20;LFS_CAP=16<<30;KEY='d6_full_original_physical_index_resource_v1'
STATE_SCHEMA='D6_REAL_PARENT_RESOURCE_STATE_V1'
WORKER_CHECK=None

class ResourceStop(RuntimeError):pass

def need(ok,message):
    if not ok:raise ValueError(message)

def literal(value):
    path=pathlib.Path(value);need(path.is_absolute() and '..' not in path.parts
        and not any(p.is_symlink() for p in (path,*path.parents)),'LITERAL_NONSYMLINK_RESOURCE_PATH');return path

def load(path):
    path=literal(path);a=path.stat();need(a.st_uid==1278 and stat.S_ISREG(a.st_mode) and a.st_size<=8<<20,'OWN_SMALL_RESOURCE_METADATA')
    raw=path.read_bytes();b=path.stat();need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'STABLE_RESOURCE_METADATA_FRAME')
    return json.loads(raw)

def save(path,value):
    path=literal(path);raw=(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    temp=path.with_name(path.name+'.tmp_'+str(os.getpid())+'_'+str(time.time_ns()))
    with temp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def bounded(argv):
    p=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=20)
    need(p.returncode==0,repr(dict(argv=argv,returncode=p.returncode,stderr=p.stderr)));return p.stdout

# Original established lfs parsing function/code. Only subprocess timeout is new.
_lfs=types.FunctionType(OLD_LFS.quota.__code__,dict(OLD_LFS.quota.__globals__,run=bounded),
    OLD_LFS.quota.__name__,OLD_LFS.quota.__defaults__,OLD_LFS.quota.__closure__)

def lustre_quota():
    result=_lfs();need(os.getuid()==result['uid']==1278,'ACTUAL_LUSTRE_UID1278')
    need('uid 1278' in result['raw_quota']['stdout'] and result['limit_bytes']==2<<40,'ACTUAL_HARD2TIB_LFSHOME_USER_QUOTA')
    return result

def future(path,lock,schema,entry_key,job,output,forecast,domain=None):
    with literal(lock).open('rb') as f:
        fcntl.flock(f,fcntl.LOCK_SH);value=load(path)
        need(value['schema']==schema and value['totals_derived_live_from_entries'] is True
            and not value['unknown_future_entries'],'ACTUAL_KNOWN_LIVE_FUTURE_POINTER')
        if domain is not None:need(value['storage_domain']==domain and value['uid']==1278,'SEPARATE_LUSTRE_LEDGER_NOT_MAIN')
        entries=value['entries'];numbers=[v['future_reserved_bytes'] for v in entries.values()]
        need(all(type(n)is int and n>=0 for n in numbers)
            and sum(numbers)==value['known_future_reserved_bytes']==value['total_future_reserved_bytes'],'ALL_FUTURE_EXACT_ONCE_SUM')
        own=entries[entry_key];need(str(own['job_id'])==str(job) and own['output_root']==str(output)
            and own['forecast_bytes']==forecast and 0<=own['future_reserved_bytes']<=forecast,'THIS_ACTUAL_PARENT_STORAGE_ENTRY')
        return value['total_future_reserved_bytes']

def ticks(pid):return pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19]
def boot():return pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def binding(plan,proof,plan_ref,proof_ref,state):
    pid=os.getpid();return dict(pid=pid,uid=1278,start_ticks=ticks(pid),boot_id=boot(),job_id=str(proof['job_id']),node='compute-0-18',
        argv=[v.decode() for v in pathlib.Path('/proc/self/cmdline').read_bytes().rstrip(b'\0').split(b'\0')],
        cgroup_sha256=hashlib.sha256(pathlib.Path('/proc/self/cgroup').read_bytes()).hexdigest(),
        plan_reference=plan_ref,proof_reference=proof_ref,state_path=str(state))

def parent_check(value):
    pid=value['pid'];p=pathlib.Path('/proc',str(pid))
    need(os.getuid()==p.stat().st_uid==value['uid']==1278 and ticks(pid)==value['start_ticks'] and boot()==value['boot_id']
        and os.environ.get('SLURM_JOB_ID')==value['job_id'] and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
        and socket.gethostname().split('.')[0]==value['node']=='compute-0-18','SAME_ACTUAL_16CPU18_PARENT_UID_JOB_BOOT_START')
    need([v.decode() for v in (p/'cmdline').read_bytes().rstrip(b'\0').split(b'\0')]==value['argv']
        and hashlib.sha256((p/'cgroup').read_bytes()).hexdigest()==value['cgroup_sha256'],'SAME_ACTUAL_PARENT_ARGV_CGROUP')

def parameters(plan):
    r=plan['resource_binding']
    return dict(stage='FULL_ORIGINAL_WP5_PPRIME_IDENTITY_INDEX_NO_NUMERIC',node='compute-0-18',cpus=16,wall_seconds=r['wall_seconds'],
        drain_seconds=900,output_directory=plan['output_directory'],lustre_output_forecast_bytes=LFS_CAP,
        Main_control_directory=r['control_directory'],Main_control_forecast_bytes=MAIN_CAP,account_floor_bytes=FLOOR,
        Main_future_ledger_path=str(MAIN_LEDGER),Lustre_future_ledger_path=str(LFS_LEDGER),
        numeric_payload_columns_read=False,geometry_positions_read=False,new_QM_UFF_calls=0)

class Check:
    def __init__(self,value):self.value=value;self.next=0
    def __call__(self):
        if time.monotonic()<self.next:return
        self.next=time.monotonic()+30;parent_check(self.value);state=load(self.value['state_path'])
        need(state['schema']==STATE_SCHEMA and state['parent']==self.value and 0<=time.time()-state['observed_unix_seconds']<=120,
            'FRESH_SAME_PARENT_RESOURCE_STATE')
        if state['stop'] is not None:raise ResourceStop(state['stop'])

def worker_initialize(value):
    global WORKER_CHECK
    from workflows.data_v1_final.labels.full_logical_owner_plan_v2.io import opened
    for reference in (value['plan_reference'],value['proof_reference']):
        with opened(reference,hash_content=True) as (f,_):f.read(1)
    WORKER_CHECK=Check(value);WORKER_CHECK()
    import build_index
    build_index.set_resource_check(WORKER_CHECK)

class Monitor:
    def __init__(self,plan,proof,plan_ref,proof_ref):
        self.plan,self.proof=plan,proof;self.cfg=plan['resource_binding'];self.job=str(proof['job_id'])
        need(self.cfg['schema']=='ROOT_BOUND_D6_MAIN_LUSTRE_RESOURCE_V1' and self.cfg['status']=='ROOT_BOUND_REAL_STORAGE_ADMISSION'
            and self.cfg['node']=='compute-0-18' and self.cfg['cpus']==16 and type(self.cfg['wall_seconds'])is int
            and 900<self.cfg['wall_seconds']<=86400,'ACTUAL_ROOT_RESOURCE_BINDING_REQUIRED_NOT_TEMPLATE')
        self.control=literal(self.cfg['control_directory']);need(ROOT/'control' in self.control.parents,'MAIN_CONTROL_ONLY')
        self.root=self.control/'resource_observation';need(not self.root.exists(),'FRESH_RESOURCE_OBSERVATION_ROOT');self.root.mkdir(mode=0o700)
        self.output=literal(plan['output_directory']);need(pathlib.Path('/lfshome/zixiao') in self.output.parents,'INDEX_ONLY_ON_LUSTRE')
        self.state=self.root/'current.json';self.parent=binding(plan,proof,plan_ref,proof_ref,self.state)
        self.clock=wall_clock(proof,self.cfg['wall_seconds']);self.client=DAY.Client(self.cfg['quota_provider_review_reference'],proof['request'])
        self.done=threading.Event();self.stop=None;self.error=None;self.sequence=0;self.next=0
        save(self.root/'wall_clock.json',self.clock)
    def event(self,value):
        # Finite source/provider retry evidence; no DATA contents or free credit.
        directory=self.root/'quota_events';directory.mkdir(exist_ok=True)
        save(directory/('%06d.json'%time.time_ns()),value)
    def observe(self):
        self.sequence+=1
        try:
            parent_check(self.parent)
            main=GUARD.observe(self.client,expected_identity_reference=self.cfg['quota_provider_identity_reference'],record=self.event)
            need(self.client.identity==self.cfg['quota_provider_identity_reference'],'SAME_V5_DAY_PUBLISHER_IDENTITY')
            need(main['publisher_expires_unix_seconds']>=self.clock['cpu_wall_at_anchor']+self.clock['remaining_at_anchor_seconds']+300,
                'FINITE_DAY_PROVIDER_COVERS_ACTUAL_ALLOCATION')
            mt=future(MAIN_LEDGER,MAIN_LOCK,'ROOT_CURRENT_ALL_FUTURE_METADATA_POINTER_V2',self.cfg['main_future_entry_key'],
                self.job,self.control,MAIN_CAP)
            lfs=lustre_quota();lt=future(LFS_LEDGER,LFS_LOCK,'ROOT_CURRENT_LUSTRE_ALL_FUTURE_METADATA_POINTER_V1',
                self.cfg['lustre_future_entry_key'],self.job,self.output,LFS_CAP,'LUSTRE:/lfshome')
            if main['free_bytes']-mt<FLOOR:self.stop=self.stop or 'MAIN_ALL_FUTURE100GB_STOP_NEW_INDEX_BATCHES'
            if lfs['free_bytes']-lt<FLOOR:self.stop=self.stop or 'LUSTRE_ALL_FUTURE100GB_STOP_NEW_INDEX_BATCHES'
            remaining=remaining_wall(self.clock,time.monotonic())
            if remaining<=900:self.stop=self.stop or 'WALL_DRAIN_STOP_NEW_INDEX_BATCHES'
            # Only known own mutable output metadata is observed, never queried
            # as SQL, hashed or used as quota credit. No output-tree recursion.
            names=['identity.sqlite','qc_locations.sqlite',*['locations_%02d.sqlite'%k for k in range(16)]]
            allocated=0
            for name in [*names,*[n+s for n in names for s in ('-journal','-wal','-shm')],'files.json','manifest.json']:
                path=self.output/name
                try:s=path.lstat()
                except FileNotFoundError:continue # exact optional own SQLite sidecar/unfinished file, telemetry only
                need(stat.S_ISREG(s.st_mode) and s.st_uid==1278 and not path.is_symlink(),'OWN_INDEX_STORAGE_METADATA_ONLY');allocated+=s.st_blocks*512
            if allocated>=LFS_CAP:self.stop=self.stop or 'INDEX16GIB_FORECAST_STOP_NEW_BATCHES'
            need(self.sequence<=6000,'FINITE_RESOURCE_EVENT_COUNT')
            value=dict(schema=STATE_SCHEMA,parent=self.parent,observed_unix_seconds=time.time(),sequence=self.sequence,stop=self.stop,
                Main_free_bytes=main['free_bytes'],Main_all_future_bytes=mt,Main_after_all_future_bytes=main['free_bytes']-mt,
                Main_snapshot_reference=main['snapshot_reference'],Lustre_quota=lfs,Lustre_all_future_bytes=lt,
                Lustre_after_all_future_bytes=lfs['free_bytes']-lt,actual_own_Lustre_allocated_metadata_bytes=allocated,
                own_bytes_not_used_as_free_credit=True,Main_control_forecast_bytes=MAIN_CAP,Lustre_forecast_bytes=LFS_CAP,
                account_floor_bytes=FLOOR,remaining_wall_seconds=remaining,signals_sent=False)
        except Exception as e:
            self.error=dict(error=repr(e),traceback=traceback.format_exc());self.stop=self.stop or 'RESOURCE_OBSERVATION_UNKNOWN_STOP_NEW_INDEX_BATCHES'
            value=dict(schema=STATE_SCHEMA,parent=self.parent,observed_unix_seconds=time.time(),sequence=self.sequence,stop=self.stop,error=self.error,signals_sent=False)
        save(self.root/('%06d.json'%self.sequence),value);save(self.state,value)
    def start(self):
        self.observe();self._state_check=Check(self.parent);self.check()
        def loop():
            while not self.done.wait(30):
                try:self.observe()
                except Exception as e:self.stop='RESOURCE_METADATA_WRITE_FAILED';self.error=repr(e);return
        self.thread=threading.Thread(target=loop,daemon=True);self.thread.start()
    def check(self):
        if self.stop is not None:raise ResourceStop(self.stop)
        self._state_check()
    def finish(self):
        self.done.set()
        if hasattr(self,'thread'):self.thread.join()