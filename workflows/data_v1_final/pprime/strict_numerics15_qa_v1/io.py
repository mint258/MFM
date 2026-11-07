"""Stable partitioned writes and observed resources; never scan output trees."""
import hashlib,json,os,pathlib,socket,stat,time,uuid
from . import contract as C
Q=C.Q


class Store:
    def __init__(self,root,limit):self.root=pathlib.Path(root);self.limit=limit;self.charged=0
    def reserve(self,n):self.charged+=n;Q.need(self.charged+(1<<20)<self.limit,'FINITE_PRIVATE_OUTPUT_PARTITION')
    def write(self,path,body):
        p=pathlib.Path(path);Q.need(self.root in p.parents and not p.exists() and not any(v.is_symlink() for v in (p,*p.parents)),'FRESH_OWN_STABLE_FILE')
        self.reserve(len(body)+4096);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_name(p.name+'.partial_'+str(os.getpid())+'_'+uuid.uuid4().hex)
        with temp.open('xb') as f:f.write(body);f.flush();os.fsync(f.fileno())
        os.link(temp,p);temp.unlink();fd=os.open(p.parent,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
        return {'path':str(p),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
    def json(self,path,value):return self.write(path,C.O.canonical(value)+b'\n')


def ticks(pid):return pathlib.Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]


def claim_create(path,value,store):
    body=C.O.canonical(value)+b'\n';store.reserve(len(body)+4096)
    with pathlib.Path(path).open('xb') as f:f.write(body);f.flush();os.fsync(f.fileno())
    fd=os.open(pathlib.Path(path).parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return Q.pin(path)


def continuation(session):
    Q.need(os.getppid()==session['parent_pid'] and ticks(os.getppid())==session['parent_ticks'] and os.getuid()==1278
        and os.environ.get('SLURM_JOB_ID')==session['job_id'] and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
        and socket.gethostname().split('.')[0]==session['node'] and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==session['boot_id'],
        'SAME_LIVE_ADMITTED_PARENT_NOT_FRESHNESS_WAIVER')
    for ref in session['source_references']:Q.need(Q.pin(ref['path'])==ref,'NEW_QA_SOURCES_CHANGED')
    plan=C.meta(session['plan_reference']);C.require_user(plan);return plan


class Budget:
    def __init__(self,plan,proof):
        self.plan,self.proof=plan,proof;self.start=time.monotonic();self.stop=None;self.peak=0;self.minimum=None;self.last=0
        job=Q.fields(proof['job_metadata']) if isinstance(proof['job_metadata'],str) else proof['job_metadata'];t=job['RunTime']
        days,t=t.split('-',1) if '-' in t else ('0',t);h,m,s=map(int,t.split(':'))
        self.initial_elapsed=int(days)*86400+h*3600+m*60+s+max(0,time.time()-proof['memory_observation']['observed_unix_seconds'])
    def observe(self):
        now=time.monotonic()
        if now-self.last<1:return self.stop
        self.last=now;Q.need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID')==str(self.proof['job_id'])
            and socket.gethostname().split('.')[0]==self.proof['request']['node']
            and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.proof['boot_id'],'SAME_ADMITTED_QA_ALLOCATION')
        rss=0;stack=[os.getpid()];seen=set()
        while stack:
            pid=stack.pop()
            if pid in seen:continue
            seen.add(pid);Q.need(len(seen)<=256,'FINITE_OWN_PROCESS_TREE')
            try:
                root=pathlib.Path('/proc/'+str(pid));Q.need(root.stat().st_uid==1278,'OWN_RESOURCE_DESCENDANTS_ONLY')
                rss+=int((root/'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                stack.extend(map(int,(root/'task'/str(pid)/'children').read_text().split()))
            except FileNotFoundError:continue
        mem={v.split(':')[0]:int(v.split()[1])*1024 for v in pathlib.Path('/proc/meminfo').read_text().splitlines() if v.startswith(('MemAvailable:','MemTotal:'))}
        self.peak=max(self.peak,rss);self.minimum=mem['MemAvailable'] if self.minimum is None else min(self.minimum,mem['MemAvailable'])
        free=os.statvfs(Q.ROOT)
        if rss>=64<<30 or mem['MemAvailable']<max(4<<30,.15*mem['MemTotal']):self.stop=self.stop or 'ACTUAL_RSS_MEMAVAILABLE_STOP_NEW_DISPATCH'
        if free.f_bavail*free.f_frsize-C.CAP<200000000000:self.stop=self.stop or 'CURRENT_PHYSICAL_FREE_FULL_CAP_PLUS200GB_STOP'
        if self.initial_elapsed+now-self.start>=self.plan['wall_seconds']-1080:self.stop=self.stop or 'ORIGINAL900_PLUS_DRAIN_STOP_NEW_DISPATCH'
        return self.stop
    def report(self):return {'stop_new_dispatch':self.stop,'observed_own_tree_RSS_peak_bytes':self.peak,'minimum_MemAvailable_bytes':self.minimum,
        'output_accounting':'15*112MiB worker partitions +256MiB parent <2GiB; raw SQLite journals prepaid in each private partition',
        'transient_output_tree_stat_calls':0,'physical_statvfs_is_not_account_quota':True,'fresh_central_account_quota_and_Root_registered_cap_reservations_required':True,'signals_sent':False}
