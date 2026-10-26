"""Actual owned RSS/MemAvailable observation; software soft limits, no signals."""
from __future__ import annotations
import gzip,json,os,pathlib,threading,time


def need(ok,message):
    if not ok:raise ValueError(message)


def proc_stat(pid):
    raw=pathlib.Path('/proc',str(pid),'stat').read_text()
    tail=raw[raw.rfind(')')+2:].split()
    return {'pid':pid,'ppid':int(tail[1]),'start_ticks':int(tail[19])}


def actual_sample(identity):
    boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    need(boot==identity['boot_id'] and proc_stat(identity['pid'])['start_ticks']==identity['start_ticks'],'OWN_PROCESS_LIFETIME_CHANGED')
    owned=[];todo=[(identity['pid'],None)];seen=set();gone=0
    while todo:
        pid,parent=todo.pop()
        if pid in seen:continue
        seen.add(pid);need(len(seen)<=32768,'OWNED_PROCESS_TREE_LIMIT')
        try:
            before=proc_stat(pid)
            need(parent is None or before['ppid']==parent,'DESCENDANT_REPARENTED_BEFORE_OBSERVATION')
            status=pathlib.Path('/proc',str(pid),'status').read_text()
            uid_line=next(line for line in status.splitlines() if line.startswith('Uid:'))
            need(int(uid_line.split()[1])==identity['uid'],'DESCENDANT_REAL_UID_DIFFERS')
            pages=int(pathlib.Path('/proc',str(pid),'statm').read_text().split()[1])
            children=set()
            for thread in pathlib.Path('/proc',str(pid),'task').iterdir():
                try:children.update(int(value) for value in (thread/'children').read_text().split())
                except (FileNotFoundError,ProcessLookupError):gone+=1
            after=proc_stat(pid)
            need((after['ppid'],after['start_ticks'])==(before['ppid'],before['start_ticks']),'OWNED_PID_REUSED_DURING_SAMPLE')
            owned.append(dict(before,rss_bytes=pages*os.sysconf('SC_PAGE_SIZE')))
            todo.extend((child,pid) for child in children)
        except (FileNotFoundError,ProcessLookupError):
            need(pid!=identity['pid'],'OWN_ROOT_PROCESS_DISAPPEARED');gone+=1
    memory={line.split(':',1)[0]:int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines()
            if line.startswith(('MemAvailable:','MemTotal:'))}
    need(identity['pid'] in {p['pid'] for p in owned} and memory['MemAvailable']>0,'ACTUAL_RSS_AND_AVAILABLE_REQUIRED')
    need(proc_stat(identity['pid'])['start_ticks']==identity['start_ticks'],'OWN_ROOT_IDENTITY_CHANGED_AFTER_SAMPLE')
    return {'observed_unix_seconds':time.time(),'observed_monotonic_seconds':time.monotonic(),
        'root_identity':identity,'owned_processes':owned,'owned_rss_sum_bytes':sum(p['rss_bytes'] for p in owned),
        'rss_sum_shared_pages_may_be_counted_multiple_times':True,
        'MemAvailable_bytes':memory['MemAvailable'],'MemTotal_bytes':memory['MemTotal'],
        'gone_during_observation':gone,'metrics_available':True}

def soft_denial(sample,limits):
    if not sample.get('metrics_available'):return 'ACTUAL_MEMORY_OBSERVATION_UNAVAILABLE'
    if sample['owned_rss_sum_bytes']>limits['algorithm_rss_soft_cap_bytes']:return 'ALGORITHM_OWNED_RSS_SOFT_CAP'
    if sample['MemAvailable_bytes']<limits['minimum_mem_available_bytes']:return 'ACTUAL_MEMAVAILABLE_LOW'
    return None


class MemoryObserver:
    def __init__(self,limits,stop_path,*,sampler=None):
        need(limits['algorithm_limits_are_slurm_requests'] is False and limits['sample_seconds']==1
            and limits['maximum_sample_age_seconds']==3,'EXACT_SOFT_OBSERVATION_POLICY_REQUIRED')
        self.limits=limits;self.stop_path=pathlib.Path(stop_path);self.identity=dict(proc_stat(os.getpid()),uid=os.getuid(),
            boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip())
        self.sampler=sampler or (lambda:actual_sample(self.identity))
        self.samples=[];self.evidence_bytes=0;self.dropped_samples=0;self.first_stop=None;self._last=None;self._lock=threading.Lock();self._stop=threading.Event()
        self.thread=threading.Thread(target=self._loop,name='pprime-actual-memory-observer',daemon=True)
    def latch(self,reason):
        with self._lock:
            if self.first_stop is None:self.first_stop={'reason':reason,'observed_unix_seconds':time.time(),'observed_monotonic_seconds':time.monotonic()}
    def observe(self):
        try:row=self.sampler()
        except Exception as exc:row={'observed_unix_seconds':time.time(),'observed_monotonic_seconds':time.monotonic(),
            'metrics_available':False,'observation_error':repr(exc)}
        denial=soft_denial(row,self.limits)
        row_bytes=len(json.dumps(row,separators=(',',':'),allow_nan=False).encode())
        with self._lock:
            if len(self.samples)>=self.limits['max_samples'] or self.evidence_bytes+row_bytes>self.limits['max_evidence_uncompressed_bytes']:
                denial='FINITE_MEMORY_EVIDENCE_LIMIT';self.dropped_samples+=1
            else:self.samples.append(row);self.evidence_bytes+=row_bytes
            self._last=row
        if denial:self.latch(denial)
        return row
    def _loop(self):
        while not self._stop.wait(1):self.observe()
    def start(self):self.observe();self.thread.start()
    def allow_new_dispatch(self):
        if self.stop_path.exists():self.latch('EXPLICIT_STAGE_STOP_MARKER')
        with self._lock:last=self._last;first=self.first_stop
        if first is not None:return False
        if last is None or not 0<=time.monotonic()-last['observed_monotonic_seconds']<=3:
            self.latch('ACTUAL_MEMORY_OBSERVATION_STALE');return False
        return True
    def close(self,path):
        self._stop.set();self.thread.join(timeout=3)
        if self.thread.is_alive():self.latch('MEMORY_OBSERVER_NOT_CLOSED')
        payload={'schema':'PPRIME_ACTUAL_MEMORY_SOFT_LIMIT_EVIDENCE_V1','memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
            'slurm_memory_requested_by_adapter':False,'algorithm_soft_limits':self.limits,
            'actual_slurm_memory_environment':{k:os.environ.get(k) for k in ('SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU','SLURM_MEM_PER_GPU')},
            'root_identity':self.identity,'samples':self.samples,'first_stop':self.first_stop,
            'evidence_bytes_before_pretty_print':self.evidence_bytes,'dropped_samples_after_limit':self.dropped_samples,'last_actual_observation':self._last,
            'monitor_thread_closed':not self.thread.is_alive(),'signals_sent':False}
        raw=(json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
        with pathlib.Path(path).open('xb') as f:f.write(gzip.compress(raw,compresslevel=3,mtime=0))
        return {'samples':len(self.samples),'first_stop':self.first_stop,'thread_closed':not self.thread.is_alive(),'signals_sent':False}
