"""CPU-only finite DATA IO and one real parent resource observer."""
import hashlib,json,os,sqlite3,stat,threading,time
from pathlib import Path
from workflows.data_v1_final.labels.normalization_compact_runtime_v3.runtime import small_ref,save,new_root,unique_bytes,wall_clock,remaining_wall,failed
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import support as S
from . import memory as R
from workflows.data_v1_final.execution.cpu_analysis_day_v1 import quota_provider as QP
from . import contract as C
stop_requested=R.stop_requested;pin=S.ref

def require(ref,content=True):
    C.reference(ref,source=ref.get('bytes')==0);p=Path(ref['path'])
    C.need(not any(q.is_symlink() for q in (p,*p.parents)),'DAY_NO_SYMLINK_INPUT')
    with p.open('rb') as f:
        before=os.fstat(f.fileno());frame=[before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns]
        C.need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_nlink==1 and before.st_size==ref['bytes'],'DAY_CURRENT_FD_SIZE_OWNER_SINGLE_LINK')
        if content:
            h=hashlib.sha256()
            for block in iter(lambda:f.read(1<<20),b''):h.update(block)
            C.need(h.hexdigest()==ref['sha256'],'DAY_WHOLE_SHA_CURRENT_FD')
        after=os.fstat(f.fileno());C.need(frame==[after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns]==S.identity(p),'DAY_FRAME_CHANGED')
    return p

def load(path,limit=512<<20):
    """Only called by admitted CPU; large current projection manifests stay DATA."""
    p=Path(path);before=S.identity(p);C.need(0<before[2]<=limit,'FINITE_DAY_CPU_JSON_CAP')
    with p.open('rb') as f:
        raw=f.read(limit+1);s=os.fstat(f.fileno());C.need(before==[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]==S.identity(p),'DAY_JSON_CURRENT_FD_STABLE')
    C.need(len(raw)==before[2]<=limit,'DAY_JSON_EXACT_BYTES');return json.loads(raw.decode('utf-8-sig'))

def load_data(ref,maximum=64<<20):return load(require(ref),maximum)

class Budget:
    def __init__(self,plan,proof,root):
        self.plan=plan;self.root=Path(root);self.ledger=None;self.done=threading.Event();self.clock=wall_clock(proof,86400)
        save(self.root/'actual_wall_clock.json',self.clock)
        self.client=QP.Client(proof['request']['quota_provider_review_reference'],proof['request'])
        self.next_quota=0;self.quota=None;self.total=C.meta(proof['request']['root_carveout_review_reference'])['total_future_reserved_bytes']
        binding={'resource_evidence_output':str(self.root)+'_resource_observation','memavailable_soft_floor_bytes':4<<30,'resource_evidence_local_cap_bytes':64<<20}
        R.start_observer(proof,binding);self.observe();self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
    def observe(self):
        try:
            if time.monotonic()>=self.next_quota:
                self.quota=self.client.observe();self.next_quota=time.monotonic()+60
            q=self.quota
            if q['free_bytes']-self.total<200000000000:R.mark_stop('DAY_REAL_ACCOUNT_QUOTA_FUTURE_ONCE_PLUS200GB',{'free':q['free_bytes'],'future':self.total})
            if remaining_wall(self.clock,time.monotonic())<=900:R.mark_stop('DAY_SOFTWALL900_STOP_NEW_WORK_NATURAL_DRAIN',{'clock':self.clock})
            if self.ledger is not None:
                db=sqlite3.connect(self.ledger.as_uri()+'?mode=ro',uri=True,timeout=10)
                try:cap,charged=db.execute('SELECT cap,charged FROM budget WHERE id=1').fetchone()
                finally:db.close()
                if charged>=cap:R.mark_stop('DAY_OUTPUT_TICKET_SOFT_STOP',{'charged':charged,'cap':cap})
        except Exception as exc:R.mark_stop('DAY_RESOURCE_OBSERVATION_UNKNOWN',{'error':repr(exc)})
    def loop(self):
        while not self.done.wait(1):self.observe()
    def attach_ledger(self,path):self.ledger=None if path is None else Path(path).absolute()
    def close(self):self.done.set();self.thread.join();R.MONITOR.finish()
