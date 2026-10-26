"""Finite data/metadata IO and observed-resource controls; no queue or network."""
from __future__ import annotations
import hashlib,json,os,pathlib,stat,time
from .signatures import canonical,sha
MAIN=pathlib.Path('/share/home/zixiao/descriptor_analysis');RUN=MAIN/'runs/data_v1_20261025'
ALPHA=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
CAP=2<<30;RAW_CAP=8<<20;TOTAL_RAW_CAP=32*RAW_CAP;MAP_TOTAL_CAP=1<<30;MAP_ONE_CAP=528<<20
def need(value,message):
    if not value:raise ValueError(message)
def frame(s):return {'device':s.st_dev,'inode':s.st_ino,'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns,'uid':s.st_uid}
def pin(path,small=False):
    path=pathlib.Path(path).absolute();need('..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)),'LITERAL_PATH_WITHOUT_SYMLINK');before=path.stat()
    need(stat.S_ISREG(before.st_mode) and (not small or before.st_size<=2<<20),'REGULAR_BOUNDED_INPUT')
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
        after=os.fstat(stream.fileno())
    need(frame(before)==frame(after)==frame(path.stat()),'INPUT_CHANGED_DURING_HASH')
    return {'path':str(path),'bytes':before.st_size,'sha256':h.hexdigest()}
def require(reference,small=False):
    need(pin(reference['path'],small)==reference,'EXACT_CURRENT_FILE_SHA_REQUIRED');return pathlib.Path(reference['path'])
def load(reference,limit=2<<20):
    need(reference['bytes']<=limit,'BOUNDED_JSON_INPUT');path=require(reference)
    return json.loads(path.read_text(encoding='utf-8-sig'))
def save(path,value):
    raw=canonical(value)+b'\n';need(len(raw)<=2<<20,'BOUNDED_METADATA_OUTPUT')
    path=pathlib.Path(path)
    with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    fd=os.open(path.parent,os.O_DIRECTORY|os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return pin(path,True)
def write_bytes(path,body):
    path=pathlib.Path(path)
    with path.open('xb') as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
    return pin(path)
def usage(root):
    total=0;seen=set()
    for path in (pathlib.Path(root),*pathlib.Path(root).rglob('*')):
        s=path.lstat();need(s.st_uid==os.getuid() and (stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode)),'OWNED_OUTPUT_NO_SYMLINK')
        key=(s.st_dev,s.st_ino)
        if key not in seen:seen.add(key);total+=max(s.st_size,s.st_blocks*512)
    return total
def new_output(path,base):
    path=pathlib.Path(path).absolute();need('..' not in path.parts and base in path.parents and not path.exists() and not any(p.is_symlink() for p in (path,*path.parents)),'NEW_LITERAL_OUTPUT_CHILD')
    path.mkdir(parents=True,mode=0o700);return path
def raw_key(pointer):
    n=pointer['real_index'];need(type(n) is int and 0<=n<1<<63,'ORIGINAL_TYPED_NONNEGATIVE_INT64_INDEX')
    return f'{n:09d}'.encode('ascii')
def execution_pointer(origin,path):
    need(pathlib.Path(path).is_absolute(),'EXPLICIT_ABSOLUTE_EXECUTION_LMDB')
    result=dict(origin,source_path=str(path));need({k:v for k,v in result.items() if k!='source_path'}=={k:v for k,v in origin.items() if k!='source_path'},'SOURCE_PATH_ONLY_RELOCATION')
    return result
def map_size(raw_bytes,page):
    need(type(page) is int and page>0 and 0<=raw_bytes<=TOTAL_RAW_CAP,'FINITE_LMDB_INPUT_BYTES')
    size=((2*raw_bytes+(16<<20)+page-1)//page)*page;need(size<=MAP_ONE_CAP,'PER_ORIGIN_MAP_SOFTWARE_BOUND')
    return size

class Budget:
    def __init__(self,root,proof,quota_client=None):
        self.root=root;self.proof=proof;self.quota=quota_client;self.started=time.monotonic();self.stop=None
        self.samples=[];self.next_quota=0;self.reserved=0;self.maximum_RSS=0;self.minimum_available=None;self.minimum_quota_free=None
    def observe(self,processes=(),reserve=0):
        try:
            available=next(int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
            pids=[os.getpid()]+[p.pid for p in processes if p.pid and p.is_alive()];rss=0
            for pid in pids:
                try:rss+=int(pathlib.Path('/proc',str(pid),'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                except FileNotFoundError:continue
            used=usage(self.root)
            self.maximum_RSS=max(self.maximum_RSS,rss);self.minimum_available=available if self.minimum_available is None else min(self.minimum_available,available)
            if available<4<<30 or rss>32<<30:self.stop=self.stop or 'CURRENT_RSS_OR_MEMAVAILABLE_STOP'
            if used+reserve+(16<<20)>CAP:self.stop=self.stop or 'WHOLE2GIB_OUTPUT_STOP'
            wall=self.proof['request']['wall_seconds']
            if time.monotonic()-self.started>wall-120:self.stop=self.stop or 'WALL_DRAIN_RESERVE_STOP'
            if self.quota is not None and time.monotonic()>=self.next_quota:
                observation=self.quota.observe();need(observation['free_bytes']-CAP-(64<<20)-reserve>=200000000000,'FRESH_MAIN_QUOTA200GB_PLUS_CAPS')
                self.minimum_quota_free=observation['free_bytes'] if self.minimum_quota_free is None else min(self.minimum_quota_free,observation['free_bytes'])
                self.next_quota=time.monotonic()+60
            sample={'unix':time.time(),'actual_tree_RSS':rss,'MemAvailable':available,'output_allocated_bytes':used,'pids':pids}
            if len(self.samples)<4096:self.samples.append(sample)
            else:self.samples[-1]=sample
        except Exception as exc:self.stop=self.stop or 'OBSERVATION_UNAVAILABLE:'+type(exc).__name__+':'+str(exc)
        return self.stop
    def check(self):need(self.observe() is None,self.stop or 'RESOURCE_STOP')
    def report(self):return {'stop':self.stop,'samples':self.samples,'Slurm_memory_requested':False,'RSS_software_bound_bytes':32<<30,
        'MemAvailable_software_floor_bytes':4<<30,'whole_input_output_cap_bytes':CAP,'signals_sent':False,'automatic_retry':False,
        'maximum_observed_RSS':self.maximum_RSS,'minimum_observed_MemAvailable':self.minimum_available,'minimum_observed_Main_quota_free':self.minimum_quota_free,
        'sample_retention':'first4095_plus_latest_with_extrema_over_all_observations'}
