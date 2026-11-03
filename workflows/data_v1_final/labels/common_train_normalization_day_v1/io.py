"""Admitted CPU strict whole-FD IO; metadata never opens numeric DATA."""
import hashlib,json,os,sqlite3,stat,threading,time
from pathlib import Path
from workflows.data_v1_final.labels.normalization_compact_runtime_v3.runtime import new_root,unique_bytes,wall_clock,remaining_wall,failed
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import support as S
from workflows.data_v1_final.labels.streaming_v1.support import sqlstr,path_list
from workflows.data_v1_final.execution.cpu_analysis_day_v1 import quota_provider as QP
from . import contract as C,memory as R
stop_requested=R.stop_requested;pin=S.ref;ref=S.ref
ALLOWED={};ORIGINS={};ROOT=None;CAP=None

def configure(cfg):
    global ALLOWED,ORIGINS,ROOT,CAP
    ALLOWED={r['path']:r for r in cfg['source_references']+cfg['data_references']}
    ORIGINS={o['manifest_reference']['path']:o for o in cfg['cache_transitive_output_origins']}
    ROOT=Path(cfg['output_directory']);CAP=cfg['whole_output_cap_bytes']
    for old in cfg.get('accepted_prior_output_roots',[]):ORIGINS[old['manifest_reference']['path']]=old

def local(path):return ROOT is not None and ROOT in Path(path).parents

def register_prior(reference):
    reference=C.reference(reference);p=Path(reference['path'])
    C.need(any(Path(o['output_root']) in p.parents for o in ORIGINS.values()),'EXACT_ROOT_ACCEPTED_PREVIOUS_C0_OUTPUT_ONLY')
    C.need(reference['path'] not in ALLOWED or ALLOWED[reference['path']]==reference,'NO_PRIOR_DATA_REBIND')
    ALLOWED[reference['path']]=reference

def register_part(reference,parent):
    """Only refs actually read from the whole-SHA closed catalog; never scan roots."""
    reference=C.reference(reference);o=ORIGINS.get(parent['path']);C.need(o is not None and o['manifest_reference']==parent,'EXACT_CLOSED_CACHE_PARENT_AUTHORITY')
    p=Path(reference['path']);C.need(Path(o['output_root']) in p.parents and p.suffix=='.parquet','CATALOG_PART_UNDER_EXACT_ACTUAL_ORIGIN')
    C.need(reference['path'] not in ALLOWED or ALLOWED[reference['path']]==reference,'NO_TRANSITIVE_REFERENCE_REBIND');ALLOWED[reference['path']]=reference

def require(reference,content=True):
    reference=C.reference(reference,source=reference.get('bytes')==0);p=Path(reference['path'])
    C.need(ALLOWED.get(str(p))==reference or local(p),'ONLY_DECLARED_OR_CURRENT_CPU_PRODUCED_INPUT')
    C.need(not any(q.is_symlink() for q in (p,*p.parents)),'NO_SYMLINK_INPUT')
    with p.open('rb') as f:
        s=os.fstat(f.fileno());before=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
        C.need(stat.S_ISREG(s.st_mode) and s.st_uid==1278 and s.st_nlink==1 and s.st_size==reference['bytes'],'REAL_FD_UID_REGULAR_SINGLE_LINK_SIZE')
        if content:
            h=hashlib.sha256()
            for b in iter(lambda:f.read(1<<20),b''):h.update(b)
            C.need(h.hexdigest()==reference['sha256'],'WHOLE_CURRENT_FD_SHA256')
        t=os.fstat(f.fileno());C.need(before==[t.st_dev,t.st_ino,t.st_size,t.st_mtime_ns,t.st_ctime_ns]==S.identity(p),'CURRENT_DEVICE_AND_FD_FRAME_STABLE')
    return p

def load(path,limit=512<<20):
    p=Path(path);before=S.identity(p);C.need(0<before[2]<=limit,'BOUNDED_CPU_JSON_DATA')
    with p.open('rb') as f:
        raw=f.read(limit+1);s=os.fstat(f.fileno());C.need(before==[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]==S.identity(p),'JSON_FD_STABLE')
    C.need(len(raw)==before[2]<=limit,'JSON_NOT_TRUNCATED');return json.loads(raw.decode('utf-8-sig'))

def load_data(reference,maximum=64<<20):
    r=C.reference(reference,source=reference.get('bytes')==0)
    if r['path'] not in ALLOWED and not local(r['path']):register_prior(r)
    return load(require(r),maximum)
def semantic_sha(value):return hashlib.sha256((json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()).hexdigest()
def small_ref(path):return pin(path)

def save(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode();p=Path(path)
    C.need(local(p),'NEW_OUTPUT_ONLY');p.parent.mkdir(parents=True,exist_ok=True)
    C.need(unique_bytes(ROOT)+len(raw)+(64<<20)<=CAP,'WHOLE_OUTPUT_WITH_OBSERVER_AND_ADMIN_RESERVE')
    with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    r=pin(p);ALLOWED[str(p)]=r;return r

def write_text(path,value):
    raw=value.encode('utf-8');p=Path(path);C.need(local(p),'NEW_CPU_REPORT_ONLY')
    C.need(unique_bytes(ROOT)+len(raw)+(64<<20)<=CAP,'WHOLE_OUTPUT_TEXT_CAP')
    with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    r=pin(p);ALLOWED[str(p)]=r;return r

class Budget:
    def __init__(self,plan,proof,root):
        self.plan=plan;self.root=Path(root);self.done=threading.Event();self.clock=wall_clock(proof,86400)
        save(self.root/'actual_wall_clock.json',self.clock)
        self.client=QP.Client(proof['request']['quota_provider_review_reference'],proof['request'])
        self.total=C.meta(proof['request']['root_carveout_review_reference'])['total_future_reserved_bytes'];self.next_quota=0;self.quota=None
        R.start_observer(proof,{'resource_evidence_output':str(root)+'_resource_observation','memavailable_soft_floor_bytes':4<<30,'resource_evidence_local_cap_bytes':64<<20})
        self.observe();self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
    def observe(self):
        try:
            if time.monotonic()>=self.next_quota:self.quota=self.client.observe();self.next_quota=time.monotonic()+60
            if self.quota['free_bytes']-self.total<200000000000:R.mark_stop('COMMON_TRAIN_ACCOUNT_FREE_FUTURE_ONCE_PLUS200GB',self.quota)
            if remaining_wall(self.clock,time.monotonic())<=900:R.mark_stop('COMMON_TRAIN_WALL900_NATURAL_DRAIN',self.clock)
            if unique_bytes(self.root)+(256<<20)>=self.plan['whole_output_cap_bytes']:R.mark_stop('COMMON_TRAIN_WHOLE_OUTPUT_SOFT_CAP',{})
        except Exception as e:R.mark_stop('COMMON_TRAIN_RESOURCE_OBSERVATION_UNKNOWN',{'error':repr(e)})
    def loop(self):
        while not self.done.wait(60):self.observe()
    def close(self):self.done.set();self.thread.join();R.MONITOR.finish()
