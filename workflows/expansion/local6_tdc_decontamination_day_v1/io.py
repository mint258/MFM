"""Original strict JSONL/same-FD reads and chunked stable output accounting."""
import hashlib,json,os,socket,threading,time
from pathlib import Path
from workflows.expansion.marcel_kraken_decontamination_main_v1.runtime import rows
from workflows.expansion.marcel_kraken_decontamination_main_v1.projection import strict_json,canonical
from workflows.data_v1_final.pprime.strict20_readback_v1.io import held,frame
from workflows.data_v1_final.execution.cpu_analysis_day_v1.quota_provider import Client
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as R
from . import contract as C

def dump(value):return (json.dumps(value,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def equal_json(left,right):return canonical(left)==canonical(right)

class Budget:
    def __init__(self,plan,proof,out):
        self.plan=plan;self.proof=proof;self.req=proof['request'];self.start=time.monotonic();self.last=0.;self.poll=0.;self.written=0;self.lock=threading.Lock();self.observe_lock=threading.Lock()
        self.latest=None;self.observations=0;self.db_paths=[];self.carve=C.meta(plan['root_carveout_review_reference']);self.reason=None
        self.out=Path(out);self.pid=os.getpid();self.ticks=R.process_observation(self.pid)['start_ticks'];self.peak=0;self.minimum=None
        self.samples=(self.out/'resources.samples.jsonl').open('xb');self.sample_bytes=0;self.sample_count=0
        C.Day.carveout(self.carve,{'scope_key':C.KEY,'node':'compute-0-14','resource_authority_reference':plan['resource_authority_reference'],'estimated_peak_output_bytes':C.CAP})
        self.client=Client(plan['quota_provider_review_reference'],self.req)
        j=C.Q.fields(proof['job_metadata']) if isinstance(proof['job_metadata'],str) else proof['job_metadata'];text=j['RunTime']
        days,text=text.split('-',1) if '-' in text else ('0',text);h,m,s=map(int,text.split(':'))
        self.initial=int(days)*86400+h*3600+m*60+s+max(0,time.time()-proof['memory_observation']['observed_unix_seconds'])
    def charge(self,n):
        C.need(type(n)is int and n>=0,'NONNEGATIVE_OUTPUT_BYTES')
        with self.lock:
            C.need(self.written+n+(1<<30)+(256<<20)<C.CAP,'CHUNK_OUTPUT_PLUS_DB_JOURNAL_ADMIN_DRAIN_CEILING');self.written+=n
    def check(self,dispatch=True):
        if dispatch:C.need(self.reason is None,'LATCHED_STOP_NEW_ROWS_PRESERVE_PARTIAL')
        try:
            with self.observe_lock:return self._check(dispatch)
        except BaseException as exc:
            with self.lock:
                if self.reason is None:self.reason={'type':type(exc).__name__,'reason':str(exc)}
            raise
    def _check(self,dispatch):
        now=time.monotonic()
        if now-self.last<1:return
        self.last=now
        if dispatch:C.need(now-self.start+self.initial<C.WALL-300,'STRICT7_FINITE_WALL_STOP_NEW_ROWS_NATURAL_DRAIN')
        C.need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID')==str(self.proof['job_id']) and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
            and socket.gethostname().split('.')[0]=='compute-0-14'
            and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.proof['boot_id'],'SAME_CURRENT_MAIN14_PARENT')
        memory=R.memory_available();tree=R.process_tree(self.pid,self.ticks);self.peak=max(self.peak,tree['tree_rss_bytes'])
        self.minimum=memory['MemAvailable'] if self.minimum is None else min(self.minimum,memory['MemAvailable'])
        raw=dump({'observed_unix_seconds':time.time(),'job_id':str(self.proof['job_id']),'uid':1278,'node':'compute-0-14',**memory,**tree})
        C.need(self.sample_bytes+len(raw)<128<<20,'BOUNDED_RESOURCE_EVIDENCE_SOFT_STOP');self.charge(len(raw));self.samples.write(raw)
        self.sample_bytes+=len(raw);self.sample_count+=1
        if dispatch:C.need(tree['tree_rss_bytes']<8<<30 and memory['MemAvailable']>=max(4<<30,.15*memory['MemTotal']),'RSS_MEMAVAILABLE_STOP_NEW_ROWS_NATURAL_DRAIN')
        db=0
        for p in self.db_paths:
            for q in (p,Path(str(p)+'-journal'),Path(str(p)+'-wal'),Path(str(p)+'-shm')):
                try:db+=q.stat().st_size
                except FileNotFoundError:pass
        C.need(self.written+db+(1<<30)+(256<<20)<C.CAP,'COMPLETE_OWNED_OUTPUT_DB_AND_DRAIN_CAP_NO_TREE_RACE')
        v=os.statvfs(C.ROOT);reserved=self.carve['total_future_reserved_bytes']
        C.need(v.f_bavail*v.f_frsize-reserved>=200000000000,'WHOLE_FUTURE_RESERVE_ONCE_AND_PHYSICAL200GB')
        if not self.observations or now-self.poll>=30:
            self.poll=now;self.latest=self.client.observe();self.observations+=1
            C.need(self.latest['identity_reference']==self.plan['quota_provider_identity_reference'],'EXACT_ROOT_BOUND_FINITE_PROVIDER_IDENTITY')
            if self.observations==1:C.need(self.latest['publisher_expires_unix_seconds']>=time.time()+C.WALL-self.initial+300,'FINITE_PROVIDER_COVERS_REMAINING20H_AND_DRAIN')
            C.need(self.latest['free_bytes']-reserved>=200000000000,'ACTUAL_ACCOUNT_QUOTA_NOT_STATVFS_ONLY')
    def report(self):return {'charged_output_bytes':self.written,'actual_account_observations':self.observations,'last_account_observation':self.latest,
        'total_future_reserved_bytes':self.carve['total_future_reserved_bytes'],'own_cap_subtracted_exactly_once':True,'provider_auto_renewed':False,
        'forced_signals_sent':False,'DB_journal_stat_absence_is_zero_not_recursive_tree_race':True,'stop_reason':self.reason,
        'actual_resource_samples':self.sample_count,'maximum_tree_RSS_bytes':self.peak,'minimum_MemAvailable_bytes':self.minimum}
    def finish(self):
        self.samples.flush();os.fsync(self.samples.fileno());self.samples.close()
        return write(self.out/'resource_closure.json',self.report(),self)

class Lines:
    def __init__(self,path,budget):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700);self.stream=self.path.open('xb',buffering=1<<20)
        self.budget=budget;self.h=hashlib.sha256();self.n=0;self.count=0;self.since=0;self.closed=False;self.fsync_count=0
    def append(self,value):
        self.budget.check();b=dump(value);C.need(len(b)<=8<<20,'BOUNDED_IDENTITY_LINE_RESOURCE_HOLD_NOT_ROW_EXCLUSION')
        self.budget.charge(len(b));self.stream.write(b);self.h.update(b);self.n+=len(b);self.count+=1;self.since+=len(b)
        if self.since>=4<<20 or self.count%4096==0:self.flush()
    def flush(self):self.stream.flush();os.fsync(self.stream.fileno());self.since=0;self.fsync_count+=1
    def close(self):
        if not self.closed:self.flush();self.stream.close();self.closed=True
        return {'path':str(self.path),'bytes':self.n,'sha256':self.h.hexdigest(),'rows':self.count}

def write(path,value,budget):
    b=dump(value);budget.charge(len(b));p=Path(path)
    with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
    return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def readback(ref,required_roles,required_subdatasets,check):
    from workflows.expansion.decontamination import identity_keys,ALLOWED_IDENTITY_FIELDS
    from collections import Counter
    roles=Counter();subs=Counter();n=0
    for row,_ in rows({k:ref[k] for k in ('path','bytes','sha256')},check):
        C.need(set(row)==ALLOWED_IDENTITY_FIELDS,'STRICT_FIVE_FIELDS_NO_ASSAY_OR_FEATURE_COLUMNS');identity_keys(row)
        C.need(row['role'] in required_roles and row['subdataset'] in required_subdatasets,'DECLARED_ORIGINAL_ROLES_AND_SUBDATASETS')
        roles[row['role']]+=1;subs[row['subdataset']]+=1;n+=1
    C.need(n==ref['rows'] and set(roles)==set(required_roles) and set(subs)==set(required_subdatasets),'FULL_OUTPUT_EOF_ROWS_AND_ROLE_CENSUS')
    return {'rows':n,'roles':dict(roles),'subdatasets':dict(subs),'all_rows_reparsed_with_original_identity_keys':True}
