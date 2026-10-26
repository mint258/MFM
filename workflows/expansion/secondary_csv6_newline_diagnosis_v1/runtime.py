"""Actual RSS, current free space and wall observation; stop new work, never signal."""
import os,threading,time
from pathlib import Path
from . import contracts as C
from secondary_cpu_queue_v1 import common as Q
class Stop(RuntimeError):pass

def frame(path):
    path=Q.literal(path);s=path.stat();Q.need(path.is_file() and s.st_uid==1264,'OWNED_ALPHA_REGULAR_FILE_REQUIRED')
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_uid)

def owned_bytes(root):return sum(p.stat().st_size for p in Path(root).rglob('*') if p.is_file())

class Budget:
    def __init__(self,plan,proof,out):
        self.plan,self.proof,self.out=plan,proof,Path(out);self.started=time.monotonic();self.stop=threading.Event();self.closed=threading.Event()
        self.allocation_elapsed_at_start=Q.duration(Q.fields(proof['job_metadata'])['RunTime'])+max(0,time.time()-proof['observed_unix_seconds']);self.reason=None;self.samples=0;self.peak_rss=0;self.minimum_free=None;self.minimum_available=None;self.maximum_output=0;self.pids={os.getpid()};self.output_estimate=0;self.drain_reserve=8<<20
        self.sample();self.check();self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
    def mark(self,reason):
        if self.reason is None:self.reason=reason
        self.stop.set()
    def sample(self):
        alive={os.getpid()};pending=[os.getpid()]
        while pending:
            pid=pending.pop()
            try:children=Path('/proc',str(pid),'task',str(pid),'children').read_text().split()
            except FileNotFoundError:continue
            for child in children:
                value=int(child)
                if value not in alive:alive.add(value);pending.append(value)
        rss=0
        for pid in alive:
            try:rss+=int(Path('/proc',str(pid),'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
            except FileNotFoundError:continue
        mem={line.split(':')[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemAvailable:','MemTotal:'))}
        current=owned_bytes(self.out);space=os.statvfs(C.ROOT);free=space.f_bavail*space.f_frsize
        self.samples+=1;self.peak_rss=max(self.peak_rss,rss);self.maximum_output=max(self.maximum_output,current);self.output_estimate=current
        self.minimum_free=free if self.minimum_free is None else min(self.minimum_free,free)
        self.minimum_available=mem['MemAvailable'] if self.minimum_available is None else min(self.minimum_available,mem['MemAvailable'])
        if rss>=48<<30:self.mark('ACTUAL_CURRENT_OWNED_RSS_AT48GIB_SOFTWARE_REFERENCE_NOT_ALLOCATION')
        if mem['MemAvailable']<.15*mem['MemTotal']:self.mark('ACTUAL_NODE_MEMAVAILABLE_BELOW15PCT')
        if current+self.drain_reserve>=self.plan['output_cap_bytes']:self.mark('OWN_OUTPUT_RESERVE_REACHED')
        remaining=max(0,self.plan['output_cap_bytes']-current)
        others=max(0,self.proof['storage_observation']['whole_output_caps_reserved_bytes']-self.plan['output_cap_bytes'])
        if free-remaining-others<200000000000:self.mark('CURRENT_GFSHOME_FREE_REGISTERED_CAPS_PLUS200GB')
        if self.allocation_elapsed_at_start+time.monotonic()-self.started>=self.plan['wall_seconds']-120:self.mark('WALL_RESERVE_STOP_NEW_TASKS_NATURAL_DRAIN')
    def loop(self):
        while not self.closed.wait(1):
            try:self.sample()
            except BaseException as exc:self.mark('MEMORY_OR_STORAGE_OBSERVATION_UNKNOWN:'+type(exc).__name__)
    def check(self,extra=0,drain=False):
        if self.stop.is_set() and not drain:raise Stop(self.reason)
        reserve=(8<<20) if drain else self.drain_reserve
        if self.output_estimate+extra+reserve>self.plan['output_cap_bytes']:
            self.mark('FINITE_OUTPUT_CAP_STOP_WITH_PARTIALS_RETAINED');raise Stop(self.reason)
        self.output_estimate+=extra
    def receipt(self):return {'samples':self.samples,'peak_current_owned_RSS_bytes':self.peak_rss,'minimum_current_free_bytes':self.minimum_free,
        'minimum_observed_node_MemAvailable_bytes':self.minimum_available,'maximum_owned_output_bytes':self.maximum_output,'first_stop_reason':self.reason,'forced_signals_sent':False,'memory_requested':False,'actual_SLURM_memory_environment':{key:value for key,value in os.environ.items() if key.startswith('SLURM_MEM')},
        'cost_overrun_action':'REPORT_AND_CONTINUE','startup_freshness_checked_once_before_body':True,'observed_allocation_elapsed_seconds_at_budget_start':self.allocation_elapsed_at_start}
    def finish(self):self.closed.set();self.thread.join(timeout=5)
