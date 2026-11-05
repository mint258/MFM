"""P-prime scope-freeze resource observer only; no DATA IO, invocation or ledger writes."""
import fcntl,hashlib,json,os,pathlib,socket,stat,subprocess,threading,time,traceback,types
from workflows.data_v1_final.execution.cpu_analysis_day_v1 import quota_provider as DAY
from workflows.data_v1_final.execution import finite_quota_observation_guard_v1 as GUARD
from workflows.data_v1_final.labels.normalization_compact_runtime_v2.runtime import wall_clock,remaining_wall
from workflows.data_v1_final.export.pilot_family_D3_local_store_v6 import queued_quota as OLD_LFS
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
MAIN_LEDGER=ROOT/'control/root_current_all_future_ledger_v1.json';MAIN_LOCK=MAIN_LEDGER.with_suffix('.lock')
LFS_LEDGER=ROOT/'control/root_lustre_all_future_ledger_v1.json';LFS_LOCK=LFS_LEDGER.with_suffix('.lock')
KEY='pprime_fill_scope_only_v1';FLOOR=100000000000;MAIN_CAP=64<<20;MAX_SCOPE_CAP=8<<30

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
        need(self.cfg['schema']=='ROOT_BOUND_PPRIME_FILL_SCOPE_RESOURCE_V1' and self.cfg['status']=='ROOT_BOUND_REAL_STORAGE_ADMISSION',
            'ACTUAL_ROOT_BOUND_SCOPE_RESOURCE_NOT_UNBOUND_TEMPLATE')
        need(r['scope_key']==KEY and r['kind']=='analysis' and r['node']=='compute-0-18' and r['cpus']==16
            and r['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and r['estimated_peak_output_bytes']==MAIN_CAP,
            'REAL_SCOPE_GENERIC100_NODE18_16CPU_MAIN64MIB_REQUEST')
        need(type(self.cfg['wall_seconds'])is int and 900<self.cfg['wall_seconds']<=86400
            and self.cfg['wall_seconds']==r['wall_seconds'],'ACTUAL_FINITE_SCOPE_WALL')
        self.cap=self.cfg['output_forecast_bytes'];need(type(self.cap)is int and 0<self.cap<=MAX_SCOPE_CAP,'SCOPE_LUSTRE_AT_MOST8GIB_NOT_INDEX16GIB')
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
        self.root=self.control/'scope_resource_observation';need(not self.root.exists(),'FRESH_SCOPE_RESOURCE_METADATA');self.root.mkdir(mode=0o700)
        self.clock=wall_clock(proof,self.cfg['wall_seconds']);self.client=DAY.Client(self.cfg['quota_provider_review_reference'],r)
        self.done=threading.Event();self.stop=None;self.failure=None;self.last=None;self.sequence=0;self.next=0;self.lock=threading.RLock()
        save(self.root/'wall_clock.json',self.clock)
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
                if main['free_bytes']-mt<FLOOR:self.stop=self.stop or 'MAIN_ALL_FUTURE100GB_STOP_SCOPE'
                if lfs['free_bytes']-lt<FLOOR:self.stop=self.stop or 'LUSTRE_ALL_FUTURE100GB_STOP_SCOPE'
                left=remaining_wall(self.clock,time.monotonic())
                if left<=900:self.stop=self.stop or 'WALL_DRAIN_STOP_SCOPE'
                self.last=dict(schema='PPRIME_SCOPE_REAL_RESOURCE_OBSERVATION_V1',parent=self.parent,observed_unix_seconds=time.time(),sequence=self.sequence,
                    Main_free_bytes=main['free_bytes'],Main_future_bytes=mt,Main_after_future_bytes=main['free_bytes']-mt,
                    Main_snapshot_reference=main['snapshot_reference'],Lustre_quota=lfs,Lustre_future_bytes=lt,Lustre_after_future_bytes=lfs['free_bytes']-lt,
                    Main_control_forecast_bytes=MAIN_CAP,Lustre_scope_forecast_bytes=self.cap,account_floor_bytes=FLOOR,
                    remaining_wall_seconds=left,actual_free_bytes_not_modified=True,allocation_credit_bytes=0,stop=self.stop,signals_sent=False)
            except Exception as e:
                self.failure=dict(error=repr(e),traceback=traceback.format_exc());self.stop=self.stop or 'RESOURCE_OBSERVATION_UNKNOWN_STOP_SCOPE'
                self.last=dict(schema='PPRIME_SCOPE_REAL_RESOURCE_OBSERVATION_V1',parent=self.parent,observed_unix_seconds=time.time(),
                    sequence=self.sequence,stop=self.stop,failure=self.failure,signals_sent=False)
            save(self.root/('%06d.json'%self.sequence),self.last);save(self.root/'current.json',self.last)
    def start(self):
        self.observe();self.check()
        def loop():
            while not self.done.wait(30):
                try:self.observe()
                except Exception as e:self.failure=repr(e);self.stop='RESOURCE_METADATA_WRITE_FAILED_STOP_SCOPE';return
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
            Main_control_forecast_bytes=MAIN_CAP,Lustre_scope_forecast_bytes=self.cap,signals_sent=False,
            automatic_provider_renewal=False,allocation_credit_bytes=0,Native_QM_UFF_calls_by_resource_layer=0)

def start(plan,proof,*,plan_reference,proof_reference):
    return Budget(plan,proof,plan_reference,proof_reference).start()