"""Actual CPU, immutable source and shared real-quota runtime; no wall timer."""
import hashlib,json,os,socket,stat,threading,time,sys
from pathlib import Path


def need(ok,message):
    if not ok:raise ValueError(message)


def stamp(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid)


def pin(path,check=lambda:None):
    path=Path(path).absolute();need(path.is_file() and not path.is_symlink(),'REGULAR_ACTUAL_INPUT_REQUIRED:'+str(path))
    with path.open('rb') as f:
        first=os.fstat(f.fileno());h=hashlib.sha256()
        for block in iter(lambda:f.read(1<<20),b''):h.update(block);check()
        need(stamp(first)==stamp(os.fstat(f.fileno()))==stamp(path.stat()),'IMMUTABLE_WHOLE_FD_INPUT_CHANGED')
    return dict(path=str(path),bytes=first.st_size,sha256=h.hexdigest())


def verify(ref,check=lambda:None):
    value=pin(ref['path'],check);need(all(value[k]==ref[k] for k in ('path','bytes','sha256')),'INPUT_PIN_CHANGED:'+ref['path']);return Path(ref['path'])


def read(ref,limit=2<<20):
    need(ref['bytes']<=limit,'SMALL_METADATA_LIMIT_NOT_DATA_TRUNCATION')
    return json.loads(verify(ref).read_text())


def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    return pin(path)


def admit(plan,proof,plan_path,proof_path,module):
    req=proof['request'];node=socket.gethostname().split('.')[0]
    need(os.getuid()==1278 and node==plan['node']==req['node']==proof['node'],'ACTUAL_MAIN_CPU_NODE_UID')
    need(str(proof['job_id'])==os.environ.get('SLURM_JOB_ID') and str(proof['job_id']).isdecimal(),'ACTUAL_SLURM_PARENT_REQUIRED')
    need(int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==plan['cpus']==req['cpus'] and plan['cpus']>=16,'ACTUAL_ALLOCATED_CPUS')
    need(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==proof['boot_id'],'ACTUAL_BOOT')
    need(req['scope_key']=='expansion_common_reference_v1' and req['producer_plan_reference']==pin(plan_path),'EXACT_COMPONENT_PLAN_SCOPE')
    need(req['execution_argv']==[plan['python'],'-B','-m',module,'--plan',str(plan_path),'--startup-proof',str(proof_path)],'ORDERED_FULL_ARGV')
    need(plan['schema']=='EXPANSION_COMMON_REFERENCE_PLAN_V1' and plan['mode'] in ('membership','projection','all'),'EXACT_COMMON_COMPONENT_PLAN')
    need(req.get('memory_policy')=='SLURM_DEFAULT_UNSPECIFIED','NO_FIXED_SLURM_MEMORY_CLAIM')
    need(sys.version_info[:3]==(3,11,14),'ORIGINAL_MAIN_PYTHON31114')
    need(plan.get('partition','cpu') in ('cpu','all') and os.environ.get('SLURM_JOB_PARTITION')==plan.get('partition','cpu'),'ACTUAL_APPROVED_CPU_ALLOCATION_PARTITION_REQUIRED')
    declared={r['path']:r for r in req['source_references']}
    for source in Path(__file__).parent.glob('*.py'):
        need(declared.get(str(source.absolute()))==pin(source),'CURRENT_COMPONENT_SOURCE_PINS_REQUIRED')
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[key]='1'


class Budget:
    def __init__(self,plan,proof,out):
        self.plan,self.proof,self.out=plan,proof,Path(out);self.lock=threading.RLock();self.next=0;self.samples=0;self.last=None;self.peak=0;self.minimum=None;self.check(force=True)
    def used(self):
        total=0;seen=set()
        for root,dirs,files in os.walk(self.out):
            need(all(not (Path(root)/d).is_symlink() for d in dirs),'NO_OUTPUT_DIRECTORY_SYMLINK')
            for name in files:
                s=(Path(root)/name).lstat();need(stat.S_ISREG(s.st_mode) and s.st_uid==1278,'OWN_REGULAR_OUTPUT_ONLY')
                if (s.st_dev,s.st_ino) not in seen:total+=s.st_size;seen.add((s.st_dev,s.st_ino))
        return total
    def check(self,dispatch=True,force=False):
        with self.lock:
            if not force and time.monotonic()<self.next:return
            self.next=time.monotonic()+5
            need(str(self.proof['job_id'])==os.environ.get('SLURM_JOB_ID') and os.getuid()==1278,'SAME_ACTUAL_CPU_PARENT')
            from workflows.expansion.completion_runtime_v1.quota import budget_check
            used=self.used();q=budget_check(self.plan,used,self.out);pids={os.getpid()}
            for thread in Path('/proc/self/task').iterdir():
                try:pids.update(int(v) for v in (thread/'children').read_text().split())
                except FileNotFoundError:pass
            rss=0
            for pid in pids:
                try:rss+=int(Path('/proc',str(pid),'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                except FileNotFoundError:pass
            available=next(int(r.split()[1])*1024 for r in Path('/proc/meminfo').read_text().splitlines() if r.startswith('MemAvailable:'))
            need(rss<self.plan['algorithm_rss_soft_cap_bytes'] and available>=self.plan['minimum_MemAvailable_bytes'],'ACTUAL_MEMORY_RESOURCE_HOLD')
            self.peak=max(self.peak,rss);self.minimum=available if self.minimum is None else min(self.minimum,available)
            self.last=dict(unix_seconds=time.time(),own_bytes=used,rss_bytes=rss,MemAvailable_bytes=available,quota=q);self.samples+=1
    def receipt(self):return dict(peak_parent_children_RSS_bytes=self.peak,minimum_MemAvailable_bytes=self.minimum,last=self.last,observations=self.samples,no_wall_timeout=True,no_STOP2=True)


class Writer:
    def __init__(self,path,budget):
        self.path=Path(path);self.budget=budget;self.path.parent.mkdir(parents=True,exist_ok=True);self.stream=self.path.open('xb');self.bytes=0;self.rows=0
    def write(self,value,durable=False):
        self.budget.check();raw=json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()+b'\n'
        self.stream.write(raw);self.bytes+=len(raw);self.rows+=1
        if durable:self.stream.flush();os.fsync(self.stream.fileno())
    def append(self,value):return self.write(value,True)
    def close(self):
        if not self.stream.closed:self.stream.flush();os.fsync(self.stream.fileno());self.stream.close()
    def reference(self):need(self.stream.closed,'CLOSED_WRITER_REFERENCE_REQUIRED');return pin(self.path)
