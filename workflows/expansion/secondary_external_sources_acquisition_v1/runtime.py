"""Current observations only; no memory allocation claim or forced signals."""
import os,stat,threading,time
from pathlib import Path
from . import contracts as c

class Budget:
    def __init__(self,plan,proof,root):
        self.plan=plan;self.root=root;self.started=time.monotonic();self.stop=None;self.done=threading.Event();self.samples=[];self.lock=threading.Lock()
        self.rss=0;self.available=None;self.lag=0;self.output_peak=0;self.last_output_check=float('-inf');self.first_sample=threading.Event()
        job=c.q.fields(proof['job_metadata']);self.remaining=plan['wall_seconds']-c.q.duration(job.get('RunTime','0:00'))-(time.time()-proof['observed_unix_seconds'])
        self.thread=threading.Thread(target=self.monitor,name='external-acquisition-current-memory',daemon=False)
    def set_stop(self,reason):
        with self.lock:
            if self.stop is None:self.stop=reason
    def monitor(self):
        while not self.done.is_set():
            began=time.monotonic()
            try:
                mem={x.split(':',1)[0]:int(x.split()[1])*1024 for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith(('MemTotal:','MemAvailable:'))}
                rss=int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                c.need(mem['MemTotal']>0 and 0<=mem['MemAvailable']<=mem['MemTotal'] and rss>0,'INVALID_CURRENT_MEMORY')
                self.rss=max(self.rss,rss);self.available=mem['MemAvailable'] if self.available is None else min(self.available,mem['MemAvailable'])
                if rss>48*1024**3 or mem['MemAvailable']<.15*mem['MemTotal']:self.set_stop('CURRENT_MEMORY_STOP')
                if len(self.samples)<4096:self.samples.append({'unix':time.time(),'current_owned_RSS_bytes':rss,'MemAvailable':mem['MemAvailable']})
            except Exception as exc:self.set_stop('INVALID_MEMORY_OBSERVATION:'+type(exc).__name__)
            self.first_sample.set()
            self.lag=max(self.lag,time.monotonic()-began)
            self.done.wait(1)
    def owned(self):
        total=0
        def onerror(exc):
            if not isinstance(exc,FileNotFoundError):raise exc
        for directory,dirs,files in os.walk(self.root,followlinks=False,onerror=onerror):
            for name in dirs+files:
                path=Path(directory)/name
                try:s=path.lstat()
                except FileNotFoundError:continue
                c.need(not stat.S_ISLNK(s.st_mode),'OWNED_OUTPUT_SYMLINK_FORBIDDEN')
                if stat.S_ISREG(s.st_mode):total+=max(s.st_size,s.st_blocks*512)
                else:total+=4096
        self.output_peak=max(self.output_peak,total);return total
    def check(self):
        if not self.first_sample.wait(5):self.set_stop('INITIAL_CURRENT_MEMORY_OBSERVATION_UNAVAILABLE')
        if time.monotonic()-self.started>=max(0,self.remaining-120):self.set_stop('HARD_WALL_DRAIN_RESERVE')
        with self.lock:
            if time.monotonic()-self.last_output_check>=.5:
                self.last_output_check=time.monotonic()
                if self.owned()+(8 if self.plan['mode']=='profile' else 32)*1024**2>self.plan['output_cap_bytes']:
                    if self.stop is None:self.stop='WHOLE_OUTPUT_CAP'
        if self.stop:raise RuntimeError(self.stop)
    def close(self):self.done.set();self.thread.join()
    def receipt(self):return {'maximum_current_RSS_bytes':self.rss,'minimum_actual_MemAvailable_bytes':self.available,'maximum_sample_lag_seconds_observation_only':self.lag,
      'output_peak_bytes':self.output_peak,'stop':self.stop,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','memory_requested':False,
      'algorithm_reference_is_allocation':False,'signals_sent':False,'current_RSS_not_ru_maxrss':True}
