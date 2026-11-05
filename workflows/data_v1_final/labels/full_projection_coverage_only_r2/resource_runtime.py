"""Full projection-coverage resource observer only; no DATA IO, invocation or ledger writes."""
import fcntl,hashlib,json,os,pathlib,socket,stat,subprocess,threading,time,traceback,types
from workflows.data_v1_final.execution.cpu_analysis_day_v1 import quota_provider as DAY
from workflows.data_v1_final.execution import finite_quota_observation_guard_v1 as GUARD
from workflows.data_v1_final.labels.normalization_compact_runtime_v2.runtime import wall_clock,remaining_wall
from workflows.data_v1_final.export.pilot_family_D3_local_store_v6 import queued_quota as OLD_LFS
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
MAIN_LEDGER=ROOT/'control/root_current_all_future_ledger_v1.json';MAIN_LOCK=MAIN_LEDGER.with_suffix('.lock')
LFS_LEDGER=ROOT/'control/root_lustre_all_future_ledger_v1.json';LFS_LOCK=LFS_LEDGER.with_suffix('.lock')
KEY='full_projection_coverage_only_v1';FLOOR=100000000000;MAIN_CAP=64<<20;MAX_SCOPE_CAP=32<<30

class ResourceStop(RuntimeError):pass

def need(ok,message):
    if not ok:raise ValueError(message)

def literal(value):
    path=pathlib.Path(value);need(path.is_absolute() and '..' not in path.parts
        and not any(p.is_symlink() for p in (path,*path.parents)),'LITERAL_NONSYMLINK_RESOURCE_PATH');return path

def read(path):
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

# The established Lustre quota parser is the same original code object. Only
# subprocess timeout differs; its real argv/stdout/UID fields remain truthful.
_lfs=types.FunctionType(OLD_LFS.quota.__code__,dict(OLD_LFS.quota.__globals__,run=bounded),
    OLD_LFS.quota.__name__,OLD_LFS.quota.__defaults__,OLD_LFS.quota.__closure__)

def lustre_quota():
    q=_lfs();need(os.getuid()==q['uid']==1278 and 'uid 1278' in q['raw_quota']['stdout'],'ACTUAL_LUSTRE_UID1278')
    need(q['limit_bytes']==2<<40,'ACTUAL_LFSHOME_USER_HARD2TIB_QUOTA');return q

def live_future(path,lock,schema,key,job,output,forecast,domain=None):
    with literal(lock).open('rb') as f:
        fcntl.flock(f,fcntl.LOCK_SH);v=read(path)
        need(v['schema']==schema and v['totals_derived_live_from_entries'] is True and not v['unknown_future_entries'],'KNOWN_LIVE_FUTURE_POINTER')
        if domain is not None:need(v['storage_domain']==domain and v['uid']==1278,'SEPARATE_LUSTRE_FUTURE_DOMAIN')
        n=[e['future_reserved_bytes'] for e in v['entries'].values()]
        need(all(type(x)is int and x>=0 for x in n) and sum(n)==v['known_future_reserved_bytes']==v['total_future_reserved_bytes'],
            'EXACT_ALL_FUTURE_ONCE_SUM')
        own=v['entries'][key];need(str(own['job_id'])==str(job) and own['output_root']==str(output)
            and own['forecast_bytes']==forecast and 0<=own['future_reserved_bytes']<=forecast,'THIS_ACTUAL_SCOPE_PARENT_FUTURE_ENTRY')
        return v['total_future_reserved_bytes']

def ticks(pid):return pathlib.Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19]
def boot():return pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()

class Budget:
    def __init__(self,plan,proof,plan_reference,proof_reference):
        self.plan,self.proof=plan,proof;self.cfg=plan['resource_binding'];r=proof['request'];self.job=str(proof['job_id'])
        need(self.cfg['schema']=='ROOT_BOUND_FULL_PROJECTION_COVERAGE_RESOURCE_V1' and self.cfg['status']=='ROOT_BOUND_REAL_STORAGE_ADMISSION',
            'ACTUAL_ROOT_BOUND_SCOPE_RESOURCE_NOT_UNBOUND_TEMPLATE')
        need(r['scope_key']==KEY and r['kind']=='analysis' and r['node']=='compute-0-18' and r['cpus']==16
            and r['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and r['estimated_peak_output_bytes']==MAIN_CAP,
            'REAL_SCOPE_GENERIC100_NODE18_16CPU_MAIN64MIB_REQUEST')
        need(type(self.cfg['wall_seconds'])is int and 900<self.cfg['wall_seconds']<=86400
            and self.cfg['wall_seconds']==r['wall_seconds'],'ACTUAL_FINITE_SCOPE_WALL')
        self.cap=self.cfg['output_forecast_bytes'];need(type(self.cap)is int and 0<self.cap<=MAX_SCOPE_CAP,'COVERAGE_LUSTRE_AT_MOST32GIB')
        self.output=literal(plan['output_directory']);self.control=literal(plan['control_directory'])
        need(pathlib.Path('/lfshome/zixiao') in self.output.parents and ROOT in self.control.parents,'SEPARATE_REAL_LUSTRE_SCOPE_AND_MAIN_CONTROL')
        pins=r['source_references']
        for ref in (self.cfg['quota_provider_review_reference'],self.cfg['quota_provider_identity_reference'],self.cfg['quota_floor_policy_reference']):
            need(ref in pins,'ACTUAL_GENERIC_PROOF_PINS_BOUND_PROVIDER_AND_POLICY')
        policy=read(ROOT/'control/current_account_quota_floor_policy.json')
        need(policy['account_quota_floor_bytes']==FLOOR and policy['policy_reference']==self.cfg['quota_floor_policy_reference'],'ACTUAL_USER100GB_POLICY')
        # No principal-module inspection or control-only policy restriction.
        need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID')==self.job
            and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and socket.gethostname().split('.')[0]=='compute-0-18','ACTUAL_SCOPE_PARENT_PROCESS')
        actual=[v.decode() for v in pathlib.Path('/proc/self/cmdline').read_bytes().rstrip(b'\0').split(b'\0')]
        need(actual==r['execution_argv'],'SAME_ACTUAL_GENERIC_ADMITTED_SCOPE_ARGV')
        self.parent=dict(pid=os.getpid(),uid=1278,start_ticks=ticks(os.getpid()),boot_id=boot(),job_id=self.job,node='compute-0-18',argv=actual,
            cgroup_sha256=hashlib.sha256(pathlib.Path('/proc/self/cgroup').read_bytes()).hexdigest(),
            plan_reference=plan_reference,proof_reference=proof_reference)
        self.root=self.control/'coverage_resource_observation';need(not self.root.exists(),'FRESH_SCOPE_RESOURCE_METADATA');self.root.mkdir(mode=0o700)
        self.clock=wall_clock(proof,self.cfg['wall_seconds']);self.client=DAY.Client(self.cfg['quota_provider_review_reference'],r)
        self.done=threading.Event();self.stop=None;self.failure=None;self.last=None;self.sequence=0;self.next=0;self.lock=threading.RLock()
        self.local_workspace_cap_bytes=self.cfg['local_workspace_cap_bytes']
        need(type(self.local_workspace_cap_bytes)is int and 0<self.local_workspace_cap_bytes<=32<<30,'LOCAL_DERIVED_WORKSPACE_AT_MOST32GIB')
        self.local_workspace_directory=literal(plan['local_workspace_directory'])
        need(self.local_workspace_directory.parent==pathlib.Path('/dev/shm') and not self.local_workspace_directory.exists(),
            'FRESH_NODE_LOCAL_DEVSHM_WORKSPACE')
        mount=bounded(['findmnt','-n','-T','/dev/shm','-o','TARGET,FSTYPE']).split()
        need(mount==['/dev/shm','tmpfs'],'ACTUAL_DEVSHM_TMPFS_MOUNT')
        fs=os.statvfs('/dev/shm');available=fs.f_bavail*fs.f_frsize
        need(available>=self.local_workspace_cap_bytes+(4<<30),'ACTUAL_LOCAL_CAP_PLUS4GIB_FREE')
        mem=next(int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
        need(mem>=self.local_workspace_cap_bytes+(4<<30),'ACTUAL_RAM_FOR_LOCAL_TMPFS_AND4GIB')
        self.local_workspace_directory.mkdir(mode=0o700)
        local=self.local_workspace_directory.lstat();need(local.st_uid==1278 and stat.S_ISDIR(local.st_mode),'OWN_FRESH_LOCAL_WORKSPACE')
        self.local_identity=(local.st_dev,local.st_ino,local.st_uid)
        self.local_marker=dict(schema='FULL_PROJECTION_COVERAGE_LOCAL_DERIVED_WORKSPACE_V1',parent=self.parent,
            directory=str(self.local_workspace_directory),local_cap_bytes=self.local_workspace_cap_bytes,
            authoritative_output=False,Main_quota_credit_bytes=0)
        save(self.local_workspace_directory/'_coverage_workspace_owner.json',self.local_marker)
        self.local_cleaned=False
        save(self.root/'wall_clock.json',self.clock)
        save(self.root/'local_workspace_start.json',dict(local_workspace_directory=str(self.local_workspace_directory),
            local_available_bytes=available,MemAvailable=mem,local_cap_bytes=self.local_workspace_cap_bytes,
            mount='tmpfs:/dev/shm',authoritative_output=False,Main_quota_credit_bytes=0))
    def local_inventory(self):
        root=self.local_workspace_directory
        need(not self.local_cleaned,'LOCAL_WORKSPACE_ALREADY_CLEANED')
        state=root.lstat();need((state.st_dev,state.st_ino,state.st_uid)==self.local_identity,'SAME_LOCAL_WORKSPACE_INODE_UID')
        # Only the fresh local pure-derived DB/spill tree; never the shared
        # output/catalog/packet trees. Retry the whole small census on FNF only.
        for attempt in range(3):
            try:
                entries=[root,*root.rglob('*')];rows=[]
                for path in entries:
                    current=path.lstat();need(current.st_uid==1278 and not stat.S_ISLNK(current.st_mode)
                        and (stat.S_ISDIR(current.st_mode) or (stat.S_ISREG(current.st_mode) and current.st_nlink==1)),
                        'ONLY_OWN_LOCAL_DERIVED_REGULAR_FILES_AND_DIRECTORIES')
                    rows.append((path,current))
                return rows
            except FileNotFoundError:
                if attempt==2:raise
    def local_bytes(self):
        return sum(s.st_size for path,s in self.local_inventory() if stat.S_ISREG(s.st_mode))
    def cleanup_local_workspace(self):
        # Caller must close its SQLite/DuckDB handles first. Nothing shared is
        # copied or deleted, and no local file can be a final authority.
        if self.local_cleaned:return
        self.finish()
        self.same_parent();root=self.local_workspace_directory
        need(root.parent==pathlib.Path('/dev/shm') and not root.is_symlink(),'EXACT_LOCAL_TMPFS_CLEANUP_ONLY')
        marker=root/'_coverage_workspace_owner.json';need(read(marker)==self.local_marker,'EXACT_OWN_JOB_PLAN_LOCAL_MARKER')
        rows=self.local_inventory()
        for path,state in sorted(rows,key=lambda row:len(row[0].parts),reverse=True):
            need(path==root or root in path.parents,'LOCAL_CLEANUP_STAYS_IN_FRESH_WORKSPACE')
            if stat.S_ISDIR(state.st_mode):path.rmdir()
            else:path.unlink()
        self.local_cleaned=True
        save(self.root/'local_workspace_cleanup.json',dict(directory=str(root),own_derived_workspace_removed=True,
            Main_quota_credit_bytes=0,Lustre_files_deleted=False,source_files_deleted=False))
    def same_parent(self):
        p=self.parent;need(os.getpid()==p['pid'] and os.getuid()==p['uid'] and ticks(p['pid'])==p['start_ticks'] and boot()==p['boot_id']
            and os.environ.get('SLURM_JOB_ID')==self.job,'SAME_SCOPE_PARENT_UID_PID_START_BOOT')
        need(hashlib.sha256(pathlib.Path('/proc/self/cgroup').read_bytes()).hexdigest()==p['cgroup_sha256'],'SAME_SCOPE_PARENT_CGROUP')
    def event(self,value):
        d=self.root/'quota_events';d.mkdir(exist_ok=True);save(d/('%d.json'%time.time_ns()),value)
    def observe(self):
        with self.lock:
            self.sequence+=1
            try:
                need(self.sequence<=6000,'FINITE_SCOPE_RESOURCE_EVENTS');self.same_parent()
                main=GUARD.observe(self.client,expected_identity_reference=self.cfg['quota_provider_identity_reference'],record=self.event)
                need(self.client.identity==self.cfg['quota_provider_identity_reference'],'SAME_BOUND_FINITE_DAY_PROVIDER')
                need(main['publisher_expires_unix_seconds']>=self.clock['cpu_wall_at_anchor']+self.clock['remaining_at_anchor_seconds']+300,
                    'ACTUAL_DAY_PROVIDER_COVERS_SCOPE_ALLOCATION_PLUS300')
                mt=live_future(MAIN_LEDGER,MAIN_LOCK,'ROOT_CURRENT_ALL_FUTURE_METADATA_POINTER_V2',self.cfg['main_future_entry_key'],
                    self.job,self.control,MAIN_CAP)
                lfs=lustre_quota();lt=live_future(LFS_LEDGER,LFS_LOCK,'ROOT_CURRENT_LUSTRE_ALL_FUTURE_METADATA_POINTER_V1',
                    self.cfg['lustre_future_entry_key'],self.job,self.output,self.cap,'LUSTRE:/lfshome')
                if main['free_bytes']-mt<FLOOR:self.stop=self.stop or 'MAIN_ALL_FUTURE100GB_STOP_COVERAGE'
                if lfs['free_bytes']-lt<FLOOR:self.stop=self.stop or 'LUSTRE_ALL_FUTURE100GB_STOP_COVERAGE'
                local=self.local_bytes()
                if local>self.local_workspace_cap_bytes:self.stop=self.stop or 'LOCAL32GIB_WORKSPACE_STOP_COVERAGE'
                fs=os.statvfs('/dev/shm');local_free=fs.f_bavail*fs.f_frsize
                if local_free<4<<30:self.stop=self.stop or 'LOCAL_TMPFS4GIB_MARGIN_STOP_COVERAGE'
                left=remaining_wall(self.clock,time.monotonic())
                if left<=900:self.stop=self.stop or 'WALL_DRAIN_STOP_COVERAGE'
                self.last=dict(schema='FULL_PROJECTION_COVERAGE_REAL_RESOURCE_OBSERVATION_V1',parent=self.parent,observed_unix_seconds=time.time(),sequence=self.sequence,
                    Main_free_bytes=main['free_bytes'],Main_future_bytes=mt,Main_after_future_bytes=main['free_bytes']-mt,
                    Main_snapshot_reference=main['snapshot_reference'],Lustre_quota=lfs,Lustre_future_bytes=lt,Lustre_after_future_bytes=lfs['free_bytes']-lt,
                    Main_control_forecast_bytes=MAIN_CAP,Lustre_coverage_forecast_bytes=self.cap,account_floor_bytes=FLOOR,
                    remaining_wall_seconds=left,local_workspace_bytes=local,local_workspace_available_bytes=local_free,local_bytes_not_used_as_Main_credit=True,actual_free_bytes_not_modified=True,allocation_credit_bytes=0,stop=self.stop,signals_sent=False)
            except Exception as e:
                self.failure=dict(error=repr(e),traceback=traceback.format_exc());self.stop=self.stop or 'RESOURCE_OBSERVATION_UNKNOWN_STOP_COVERAGE'
                self.last=dict(schema='FULL_PROJECTION_COVERAGE_REAL_RESOURCE_OBSERVATION_V1',parent=self.parent,observed_unix_seconds=time.time(),
                    sequence=self.sequence,stop=self.stop,failure=self.failure,signals_sent=False)
            save(self.root/('%06d.json'%self.sequence),self.last);save(self.root/'current.json',self.last)
    def start(self):
        self.observe();self.check()
        def loop():
            while not self.done.wait(30):
                try:self.observe()
                except Exception as e:self.failure=repr(e);self.stop='RESOURCE_METADATA_WRITE_FAILED_STOP_COVERAGE';return
        self.thread=threading.Thread(target=loop,daemon=True);self.thread.start();return self
    def check(self):
        if self.stop is not None:raise ResourceStop(self.stop)
        if time.monotonic()<self.next:return
        self.next=time.monotonic()+30;self.same_parent()
        need(self.last is not None and 0<=time.time()-self.last['observed_unix_seconds']<=120,'FRESH_SCOPE_RESOURCE_OBSERVATION')
    def finish(self):
        self.done.set()
        if hasattr(self,'thread'):self.thread.join()
    def report(self):
        return dict(stop=self.stop,failure=self.failure,last_observation=self.last,observations=self.sequence,
            Main_control_forecast_bytes=MAIN_CAP,Lustre_coverage_forecast_bytes=self.cap,local_workspace_cap_bytes=self.local_workspace_cap_bytes,
            local_workspace_directory=str(self.local_workspace_directory),local_workspace_cleaned=self.local_cleaned,signals_sent=False,
            automatic_provider_renewal=False,allocation_credit_bytes=0,Native_QM_UFF_calls_by_resource_layer=0)

def start(plan,proof,plan_ref=None,proof_ref=None,*,plan_reference=None,proof_reference=None):
    plan_reference=plan_reference if plan_reference is not None else plan_ref
    proof_reference=proof_reference if proof_reference is not None else proof_ref
    need(plan_reference is not None and proof_reference is not None,'ACTUAL_PLAN_AND_PROOF_REFERENCES')
    return Budget(plan,proof,plan_reference,proof_reference).start()