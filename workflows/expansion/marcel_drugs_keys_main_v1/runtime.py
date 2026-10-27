"""Fresh allocated-parent resource observations and durable bounded JSONL outputs."""
import hashlib,json,os,socket,stat,time
from pathlib import Path
from . import contract as C
Q=C.Q


class Budget:
    def __init__(self,plan,proof,out):
        self.plan,self.proof,self.out=plan,proof,out;self.cap=plan['output_cap_bytes'];self.start=time.monotonic();self.last=0;self.peak=0;self.minimum=None;self.stop_new=None
        self.pid=os.getpid();self.ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]
        job=Q.fields(proof['job_metadata']) if isinstance(proof['job_metadata'],str) else proof['job_metadata'];t=job['RunTime']
        d,t=t.split('-',1) if '-' in t else ('0',t);h,m,s=map(int,t.split(':'))
        self.elapsed=int(d)*86400+h*3600+m*60+s+max(0,time.time()-proof['memory_observation']['observed_unix_seconds'])
    def used(self):
        total=0
        for path in self.out.rglob('*'):
            try:
                info=path.lstat();Q.need(not stat.S_ISLNK(info.st_mode) and info.st_uid==1278,'OWN_OUTPUT_TREE_ONLY')
                if stat.S_ISREG(info.st_mode):total+=info.st_size
            except FileNotFoundError:
                # Only SQLite's own deleted transaction sidecars may disappear.
                Q.need(path.name.endswith(('-journal','-wal','-shm')),'UNEXPECTED_OUTPUT_DISAPPEARANCE')
        return total
    def check(self,dispatch=True,force=False):
        now=time.monotonic()
        if not force and now-self.last<1:
            if dispatch:Q.need(self.stop_new is None,self.stop_new or 'RESOURCE_STOP')
            return
        self.last=now;req=self.proof['request']
        Q.need(os.getpid()==self.pid and Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]==self.ticks
            and os.getuid()==1278 and socket.gethostname().split('.')[0]==req['node'] and os.environ.get('SLURM_JOB_ID')==str(self.proof['job_id'])
            and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.proof['boot_id'],'SAME_LIVE_ADMITTED_PARENT')
        rss=0
        for pid in [str(self.pid),*Path('/proc/self/task/'+str(self.pid)+'/children').read_text().split()]:
            try:rss+=int(Path('/proc/'+pid+'/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
            except FileNotFoundError:pass
        mem={v.split(':')[0]:int(v.split()[1])*1024 for v in Path('/proc/meminfo').read_text().splitlines() if v.startswith(('MemAvailable:','MemTotal:'))}
        self.peak=max(self.peak,rss);self.minimum=mem['MemAvailable'] if self.minimum is None else min(self.minimum,mem['MemAvailable'])
        used=self.used();v=os.statvfs(Q.ROOT);reserve=(258<<20) if dispatch else (2<<20)
        Q.need(used+reserve<self.cap and v.f_bavail*v.f_frsize-max(0,self.cap-used)>=200000000000,'WHOLE_OUTPUT_OR_CURRENT200GB_STOP')
        if rss>=16<<30 or mem['MemAvailable']<max(4<<30,.15*mem['MemTotal']):self.stop_new=self.stop_new or 'RSS_MEMAVAILABLE_STOP_NEW_DISPATCH'
        if self.elapsed+now-self.start>=self.plan['wall_seconds']-180:self.stop_new=self.stop_new or 'FINITE_WALL_RESERVE_NATURAL_DRAIN'
        if dispatch:Q.need(self.stop_new is None,self.stop_new or 'RESOURCE_STOP')


class Writer:
    def __init__(self,path,budget):self.path=path;self.budget=budget;self.stream=path.open('xb');self.h=hashlib.sha256();self.bytes=0;self.rows=0
    def write(self,value,dispatch=False):
        raw=(json.dumps(value,ensure_ascii=True,separators=(',',':'),allow_nan=False)+'\n').encode();Q.need(len(raw)<=8<<20,'FULL_SOURCE_OR_RESULT_SOFTWARE_CONTAINER_BOUND_NO_TRUNCATION')
        self.budget.check(dispatch);reserve=(258<<20) if dispatch else (2<<20)
        Q.need(self.budget.used()+len(raw)+reserve<self.budget.cap,'EXACT_NEXT_ROW_CAP_AND_DRAIN_RESERVE')
        self.stream.write(raw);self.stream.flush();os.fsync(self.stream.fileno());self.h.update(raw);self.bytes+=len(raw);self.rows+=1
    def close(self):self.stream.close()
    def reference(self):return {'path':str(self.path),'bytes':self.bytes,'sha256':self.h.hexdigest()}
