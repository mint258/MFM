"""Actual whole-FD DATA and atomic owned packet/cache operations."""
import gzip,hashlib,io,json,os,pathlib,struct
from workflows.expansion.common_molecular_fp_main_v1.io import Body,seal_closed_output
from workflows.expansion.common_molecular_fp_main_v1.resources import Budget as OriginalBudget,Writer
from workflows.data_v1_final.pprime.strict_numerics15_qa_v1.io import Store,ticks,claim_create
from workflows.data_v1_final.pprime.common import staging_bytes,read_staging
from . import contract as C
Q=C.Q
class Budget:
    """Original actual quota/RSS object plus conservative outside-cache reservations."""
    def __init__(self,plan,proof,out,event):
        self.base=OriginalBudget(plan,proof,out);self.cap=plan['output_cap_bytes'];self.event=event;self.active={};self.settled=0
    def used(self):return self.base.used()+self.settled+sum(self.active.values())
    def check(self,dispatch=True,force=False):
        self.base.check(False,force)
        if self.base.base.stop_new:self.event.set()
        if self.used()+(258<<20 if dispatch else 2<<20)>=self.cap:self.event.set()
        if dispatch:Q.need(not self.event.is_set(),'ACTUAL_QUOTA_RSS_WALL_OR_WHOLE_CACHE_RESERVATION_STOP_NEW_NATURAL_DRAIN')
    def reserve(self,key):
        self.check(True);Q.need(key not in self.active,'ONE_CACHE_RESERVATION');self.active[key]=256<<20;self.check(True)
    def close_role(self,key,size):
        Q.need(key in self.active and type(size)is int and 0<=size<=256<<20,'EXACT_QUIESCENT_NEW_CACHE_BYTES')
        self.active.pop(key);self.settled+=size
    def receipt(self):return {**self.base.receipt(),'new_cache_closed_bytes':self.settled,'unresolved_reserved_cache_keys':list(self.active),
        'outside_stage_cache_accounting':'256MiB per pending molecule,exact quiescent bytes after close','old_cache_bytes_already_in_actual_quota':True}
def read_packet(ref,budget):
    body=Body(C.triple(ref),budget)
    try:
        with gzip.GzipFile(fileobj=body.stream,mode='rb') as z:
            raw=z.read((64<<20)+1);Q.need(len(raw)<=64<<20 and not z.read(1),'BOUNDED_PACKET_GZIP_EOF_CRC_NO_TRUNCATION')
        body.check();return read_staging(raw)
    finally:body.close()
def packet(store,path,value):
    raw=staging_bytes(value)+b'\n';Q.need(len(raw)<=64<<20,'BOUNDED_FULL_MOLECULE_PACKET_NO_CLIP')
    return store.write(path,gzip.compress(raw,compresslevel=3,mtime=0))
def live_parent(session):
    import socket
    Q.need(os.getppid()==session['parent_pid'] and ticks(os.getppid())==session['parent_ticks'] and os.getuid()==1278
        and os.environ.get('SLURM_JOB_ID')==session['job_id'] and socket.gethostname().split('.')[0]==session['node']
        and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==session['boot_id'],'SAME_LIVE_PARENT_JOB_NODE_BOOT_TICKS')
def continuation(session):
    live_parent(session)
    for r in session['sources']:Q.need(Q.pin(r['path'])==r,'FROZEN_SMALL_SOURCE_CHANGED')
    return C.meta(session['plan_reference'])
class Journal:
    """New-owned transient frames,each full gzip/CRC member committed before next native step."""
    def __init__(self,path,limit=128<<20):self.path=path;path.parent.mkdir(parents=True,exist_ok=True);self.f=path.open('xb');self.n=0;self.limit=limit;self.rows=0
    def write(self,value):
        raw=staging_bytes(value)+b'\n';frame=gzip.compress(raw,compresslevel=3,mtime=0);blob=struct.pack('<Q',len(frame))+frame
        Q.need(self.n+len(blob)+(2<<20)<self.limit,'CANDIDATE_JOURNAL_SOFTWARE_CAP_KEEP_PARTIAL_UNKNOWN')
        self.f.write(blob);self.f.flush();os.fsync(self.f.fileno());self.n+=len(blob);self.rows+=1
    def close(self):self.f.close()
class Embedding:
    def __init__(self,journal):self.journal=journal;self.last=None;self.index=0
    def append(self,event):
        self.flush_last();self.last=event;self.journal.write({'phase':'embedding_intent','ordinal':self.index,'event':event});self.index+=1
    def flush_last(self):
        if self.last is not None:self.journal.write({'phase':'embedding_return','ordinal':self.index-1,'event':self.last});self.last=None
