"""Current parent/owned-worker RSS and output observations; natural drain only."""
import os,stat,threading,time
from pathlib import Path
from . import contracts as c

class Budget:
    def __init__(self,plan,proof,root):
        self.plan=plan;self.root=root;self.started=time.monotonic();self.stop=None;self.workers=[];self.done=threading.Event()
        self.peak=0;self.available=None;self.lag=0;self.output_peak=0;self.samples=[];self.last_output=float('-inf');self.lock=threading.Lock();self.first_sample=threading.Event()
        self.remaining=plan['wall_seconds']-c.q.duration(c.q.fields(proof['job_metadata']).get('RunTime','0:00'))-(time.time()-proof['observed_unix_seconds'])
        self.thread=threading.Thread(target=self.monitor,name='norm-profile-owned-current-memory',daemon=False)
    def set_stop(self,reason):
        with self.lock:
            if self.stop is None:self.stop=reason
    def monitor(self):
        while not self.done.is_set():
            began=time.monotonic()
            try:
                mem={x.split(':',1)[0]:int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith(('MemTotal:','MemAvailable:'))}
                rss=int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                for p in list(self.workers):
                    if not p.is_alive():continue
                    proc=Path('/proc')/str(p.pid)
                    try:
                        tail=(proc/'stat').read_text().rsplit(')',1)[1].split();owner=proc.stat()
                        c.need(owner.st_uid==c.UID and int(tail[1])==os.getpid(),'ONLY_CURRENT_OWNED_CHILD_RSS')
                        rss+=int((proc/'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                    except FileNotFoundError:continue
                c.need(rss>0 and mem['MemTotal']>0 and 0<=mem['MemAvailable']<=mem['MemTotal'],'INVALID_CURRENT_MEMORY')
                self.peak=max(self.peak,rss);self.available=mem['MemAvailable'] if self.available is None else min(self.available,mem['MemAvailable'])
                if rss>48*1024**3 or mem['MemAvailable']<.15*mem['MemTotal']:self.set_stop('CURRENT_MEMORY_STOP_NEW_DISPATCH')
                if len(self.samples)<4096:self.samples.append({'unix':time.time(),'owned_current_RSS_bytes':rss,'MemAvailable_bytes':mem['MemAvailable']})
            except Exception as exc:self.set_stop('INVALID_MEMORY_OBSERVATION:'+type(exc).__name__)
            self.first_sample.set()
            self.lag=max(self.lag,time.monotonic()-began);self.done.wait(1)
    def owned(self):
        size=0
        def onerror(exc):
            if not isinstance(exc,FileNotFoundError):raise exc
        for folder,dirs,files in os.walk(self.root,followlinks=False,onerror=onerror):
            for name in dirs+files:
                try:s=(Path(folder)/name).lstat()
                except FileNotFoundError:continue
                c.need(not stat.S_ISLNK(s.st_mode),'OWNED_OUTPUT_SYMLINK_FORBIDDEN')
                size+=max(s.st_size,s.st_blocks*512) if stat.S_ISREG(s.st_mode) else 4096
        self.output_peak=max(self.output_peak,size);return size
    def dispatch_check(self):
        if not self.first_sample.wait(5):self.set_stop('INITIAL_CURRENT_MEMORY_OBSERVATION_UNAVAILABLE')
        if time.monotonic()-self.started>=max(0,self.remaining-120):self.set_stop('HARD_WALL_DRAIN_RESERVE')
        if time.monotonic()-self.last_output>=.5:
            self.last_output=time.monotonic()
            # Pending32 plus buffered16 reserve two physical copies, JSONL+Parquet.
            if self.owned()+(32+16)*8*1024**2*2+32*1024**2>self.plan['output_cap_bytes']:self.set_stop('OUTPUT_STOP_NEW_DISPATCH')
        if self.stop:raise RuntimeError(self.stop)
    def capacity(self,extra=0):c.need(self.owned()+extra+8*1024**2<=self.plan['output_cap_bytes'],'ACTUAL_WHOLE_OUTPUT_CEILING')
    def close(self):self.done.set();self.thread.join()
    def receipt(self):return {'peak_current_parent_and_owned_worker_RSS_bytes':self.peak,'minimum_current_MemAvailable_bytes':self.available,
      'maximum_sample_lag_seconds_observation_only':self.lag,'actual_output_peak_bytes':self.output_peak,'stop_new_dispatch':self.stop,
      'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','memory_requested':False,'algorithm_reference_is_allocation':False,'signals_sent':False}
