"""Stable new files and quota client; never scan transient SQLite output trees."""
import hashlib,os,pathlib,socket,time
from . import contract as C
Q=C.Q


class Output:
    def __init__(self,out,proof,quota_reference):
        self.out,self.proof=out,proof;self.charged=0;self.peak=0;self.minimum=None;self.start=time.monotonic();self.next=0
        self.pid=os.getpid();self.ticks=C.I.R.proc_ticks(self.pid)
        job=Q.fields(proof['job_metadata']) if isinstance(proof['job_metadata'],str) else proof['job_metadata'];t=job['RunTime']
        days,t=t.split('-',1) if '-' in t else ('0',t);h,m,s=map(int,t.split(':'))
        self.elapsed=int(days)*86400+h*3600+m*60+s+max(0,time.time()-proof['memory_observation']['observed_unix_seconds'])
        reuse,self.provider,_=C.I.R.quota_reuse(quota_reference,C.I.F.sources());self.reserve=reuse['whole_wave_output_reserve_bytes']
        Q.need(reuse['additional_Pprime_readonly_recovery_cap_bytes']==C.CAP
            and self.reserve>=reuse['preserved_previous_reserve_bytes']+C.CAP,'ROOT_EXACT_RECOVERY_RESERVE_WITH_PRIOR_CAPS')
        self.client=self.provider.Client(reuse['provider_review_reference'],proof['request']);self.quota=[]
    def check(self):
        req=self.proof['request'];Q.need(os.getpid()==self.pid and C.I.R.proc_ticks(self.pid)==self.ticks and os.getuid()==1278
            and socket.gethostname().split('.')[0]==req['node']=='compute-0-13' and os.environ.get('SLURM_JOB_ID')==str(self.proof['job_id'])
            and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.proof['boot_id'],'SAME_LIVE_READONLY_PARENT')
        rss=int(pathlib.Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        available=next(int(x.split()[1])*1024 for x in pathlib.Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))
        self.peak=max(self.peak,rss);self.minimum=available if self.minimum is None else min(self.minimum,available)
        Q.need(rss<8<<30 and available>=4<<30,'ACTUAL_MEMORY_SOFT_STOP_NO_SIGNAL')
        Q.need(self.elapsed+time.monotonic()-self.start<req['wall_seconds']-60,'FINITE_READONLY_WALL_RESERVE')
        if time.monotonic()>=self.next:
            value=self.client.observe();self.next=time.monotonic()+30;self.quota.append(value)
            Q.need(value['free_bytes']-self.reserve-self.provider.CAP-(64<<20)>=200000000000,'ACTUAL_CURRENT_ACCOUNT_QUOTA200GB_RESERVE')
    def write(self,path,body):
        self.check();path=pathlib.Path(path);Q.need(self.out in path.parents and not path.exists() and not path.is_symlink(),'NEW_STABLE_LEAF_ONLY')
        self.charged+=len(body)+4096;Q.need(self.charged+(64<<20)<C.CAP,'CUMULATIVE_CHARGED_BYTES_CAP')
        path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.partial')
        with temp.open('xb') as f:f.write(body);f.flush();os.fsync(f.fileno())
        os.link(temp,path);temp.unlink();C.I.R.fsync_dir(path.parent)
        ref=C.I.ref(path);Q.need(ref['bytes']==len(body) and ref['sha256']==hashlib.sha256(body).hexdigest(),'STABLE_FILE_FULL_READBACK')
        return ref
    def json(self,path,value):return self.write(path,C.O.canonical(value)+b'\n')
    def report(self):return {'charged_bytes_including4096_per_write':self.charged,'cap':C.CAP,'RSS_peak_bytes':self.peak,
        'minimum_MemAvailable_bytes':self.minimum,'quota_observations':self.quota,'transient_tree_stat_calls':0,'signals_sent':False}
