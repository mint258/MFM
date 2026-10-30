"""Observed memory, latched new-dispatch STOP and natural drain; never signals."""
from __future__ import annotations
import atexit, concurrent.futures, hashlib, json, os, resource, shutil, tempfile, threading, time
from pathlib import Path
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import RUN, need, ref
ENV='DATA_V1_SOURCE_STATUS_AUTO_MEMORY_CONTROL'
MONITOR=None

class SourceStatusSoftStop(RuntimeError):pass

def memory_available():
    values={}
    for line in Path('/proc/meminfo').read_text().splitlines():
        parts=line.split()
        if parts[0] in ('MemTotal:','MemAvailable:'):values[parts[0][:-1]]=int(parts[1])*1024
    need(set(values)=={'MemTotal','MemAvailable'},'ACTUAL_MEMAVAILABLE_NOT_OBSERVED')
    return values

def process_observation(pid):
    directory=Path('/proc')/str(pid);raw=(directory/'stat').read_text();tail=raw[raw.rfind(')')+2:].split()
    status={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in (directory/'status').read_text().splitlines() if ':' in line}
    uid=int(status['Uid'].split()[0]);need(uid==os.getuid(),'OWN_MEMORY_OBSERVATION_UID_DIFFERS')
    return {'pid':pid,'uid':uid,'ppid':int(tail[1]),'start_ticks':int(tail[19]),
      'rss_bytes':int(status.get('VmRSS','0 kB').split()[0])*1024,
      'high_water_bytes':int(status.get('VmHWM','0 kB').split()[0])*1024}

def process_tree(root_pid,root_start):
    root=process_observation(root_pid);need(root['start_ticks']==root_start,'OWN_ROOT_PROCESS_IDENTITY_CHANGED')
    result=[root];pending=[root];seen={root_pid};races=0
    while pending:
        parent=pending.pop()
        try:children=(Path('/proc')/str(parent['pid'])/'task'/str(parent['pid'])/'children').read_text().split()
        except (FileNotFoundError,ProcessLookupError):races+=1;continue
        for value in children:
            pid=int(value)
            if pid in seen:continue
            try:child=process_observation(pid)
            except (FileNotFoundError,ProcessLookupError):races+=1;continue
            if child['ppid']!=parent['pid']:races+=1;continue
            seen.add(pid);result.append(child);pending.append(child)
    return {'processes':result,'tree_rss_bytes':sum(p['rss_bytes'] for p in result),'vanished_process_races':races}

def control():
    value=os.environ.get(ENV);return Path(value) if value else None

def mark_stop(reason,observation):
    directory=control()
    if directory is None:return
    raw=(json.dumps({'reason':reason,'observation':observation,'pid':os.getpid(),'uid':os.getuid(),
          'monotonic_seconds':time.monotonic(),'forced_signals_sent':False},sort_keys=True)+'\n').encode()
    try:
        with (directory/'STOP.json').open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    except FileExistsError:pass

def stop_requested():
    directory=control();return directory is not None and (directory/'STOP.json').exists()

def soft_worker_rss(cap):
    high=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    if high>cap:
        mark_stop('SCAN_WORKER_SOFTWARE_RSS_CAP',{'software_cap_bytes':cap,'worker':process_observation(os.getpid()),'ru_maxrss_bytes':high})
    return high

class MemoryObserver:
    def __init__(self,proof,binding):
        self.proof=proof;self.binding=binding;self.done=threading.Event();self.lock=threading.Lock()
        self.local=Path(tempfile.mkdtemp(prefix='dv1_source_status_mem_'+str(os.getuid())+'_'+str(proof['job_id'])+'_',dir='/tmp'))
        os.chmod(self.local,0o700);os.environ[ENV]=str(self.local)
        self.pid=os.getpid();self.start=process_observation(self.pid)['start_ticks'];self.boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        self.count=0;self.bytes=0;self.max_rss=0;self.minimum_available=None;self.finished=False
        self.output=Path(binding['resource_evidence_output']).absolute()
        need((RUN/'artifacts/labels/source_status_v1') in self.output.parents and not self.output.exists(),'NEW_RESOURCE_EVIDENCE_OUTPUT_REQUIRED')
        self.sample()
        self.thread=threading.Thread(target=self.loop,name='source-status-memory-observer',daemon=True);self.thread.start()
        atexit.register(self.finish)
    def sample(self):
        try:
            mem=memory_available();tree=process_tree(self.pid,self.start)
            item={'observed_unix_seconds':time.time(),'monotonic_seconds':time.monotonic(),'boot_id':self.boot,
                  'job_id':str(self.proof['job_id']),'root_pid':self.pid,'root_start_ticks':self.start,**mem,**tree}
            self.max_rss=max(self.max_rss,tree['tree_rss_bytes'])
            self.minimum_available=mem['MemAvailable'] if self.minimum_available is None else min(self.minimum_available,mem['MemAvailable'])
            if mem['MemAvailable']<self.binding['memavailable_soft_floor_bytes']:mark_stop('NODE_MEMAVAILABLE_SOFT_PRESSURE',item)
        except Exception as exc:
            item={'observed_unix_seconds':time.time(),'monotonic_seconds':time.monotonic(),'observation_error':str(exc)}
            mark_stop('ACTUAL_MEMORY_OBSERVATION_UNAVAILABLE',item)
        raw=(json.dumps(item,sort_keys=True)+'\n').encode()
        with self.lock:
            if self.bytes+len(raw)>self.binding['resource_evidence_local_cap_bytes']-(2<<20):
                mark_stop('RESOURCE_EVIDENCE_SOFT_CAP',{'bytes':self.bytes});return
            with (self.local/'samples.jsonl').open('ab') as stream:stream.write(raw);stream.flush()
            self.bytes+=len(raw);self.count+=1
    def loop(self):
        while not self.done.wait(60):self.sample()
    def finish(self):
        if self.finished:return
        self.finished=True;self.done.set();self.thread.join(timeout=5)
        with self.lock:
            self.output.mkdir(parents=True,exist_ok=False,mode=0o700);exports=[]
            for path in sorted(self.local.iterdir()):
                need(path.is_file() and not path.is_symlink(),'OWN_LOCAL_RESOURCE_FILE_TYPE')
                target=self.output/path.name
                with path.open('rb') as source,target.open('xb') as destination:shutil.copyfileobj(source,destination)
                need(ref(path)==dict(ref(target),path=str(path)),'RESOURCE_EVIDENCE_COPY_DIFFERS');exports.append(ref(target))
            result={'schema':'SOURCE_STATUS_AUTO_MEMORY_OBSERVATION_V1','status':'RESOURCE_OBSERVATION_CLOSED' if not self.thread.is_alive() else 'RESOURCE_OBSERVATION_THREAD_NOT_CLOSED',
              'job_id':str(self.proof['job_id']),'startup_proof_request_reference':self.proof['request_reference'],
              'producer_resource_binding':self.binding,'root_pid':self.pid,'root_start_ticks':self.start,'boot_id':self.boot,
              'sample_count':self.count,'maximum_observed_tree_rss_bytes':self.max_rss,'minimum_observed_memavailable_bytes':self.minimum_available,
              'soft_stop_requested':(self.local/'STOP.json').exists(),'forced_signals_sent':False,'memory_requested_by_this_producer':False,
              'actual_slurm_memory_environment':{k:v for k,v in os.environ.items() if k.startswith('SLURM_MEM')},
              'node_local_evidence_directory':str(self.local),'exports':exports}
            with (self.output/'closure.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,sort_keys=True,indent=2);stream.write('\n')
            need(sum(p.stat().st_size for p in self.output.iterdir())<=self.binding['resource_evidence_local_cap_bytes'],'RESOURCE_DURABLE_CAP')

def start_observer(proof,binding):
    global MONITOR
    need(MONITOR is None,'ONE_RESOURCE_OBSERVER_PER_STAGE');MONITOR=MemoryObserver(proof,binding)

def drain_submit(items,executor,worker,receipts,stop_fn,peer_stop):
    """At most16 in flight. Pressure stops new files and waits for running files."""
    iterator=iter(items);pending={};dispatched=0;completed=0
    # The first16 are an atomic wave because the inherited barrier needs16 workers.
    if stop_fn():raise SourceStatusSoftStop('SOFT_STOP_BEFORE_FIRST_SOURCE_WAVE_NO_IO')
    for _ in range(min(16,len(items))):
        item=next(iterator);pending[executor.submit(worker,item)]=item;dispatched+=1
    try:
        while pending:
            done,_=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                pending.pop(future);receipts.append(future.result());completed+=1
            if not stop_fn():
                while len(pending)<16:
                    try:item=next(iterator)
                    except StopIteration:break
                    pending[executor.submit(worker,item)]=item;dispatched+=1
        if dispatched<len(items):
            raise SourceStatusSoftStop('SOFT_STOP_NATURAL_DRAIN_COMPLETED:'+str(completed)+'_FILES_OF_'+str(len(items)))
    except SourceStatusSoftStop:raise
    except BaseException:
        peer_stop.set()
        for future in pending:future.cancel()
        raise

def run_file_pool(items,cfg,index,raw,names,stop,barrier,receipts,initialize,worker):
    import multiprocessing
    ctx=multiprocessing.get_context('spawn')
    with concurrent.futures.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,
            initargs=(cfg,index,raw,names,stop,barrier)) as pool:
        drain_submit(items,pool,worker,receipts,stop_requested,stop)