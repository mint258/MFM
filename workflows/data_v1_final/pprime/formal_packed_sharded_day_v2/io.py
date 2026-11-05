"""Private local staging IO; unchanged scientific worker gets no global patches."""
import fcntl,hashlib,json,os,pathlib,socket,stat,time,uuid
from workflows.data_v1_final.pprime.formal_packed_day_v1 import io as Old
from . import contract as C
Q=C.Q;I=Old.I;Preparation=Old.Preparation
Store=Old.Store;claim_create=Old.claim_create;ticks=Old.ticks;quiescent=Old.quiescent
source_session=Old.source_session;continuation=Old.continuation

def stamp(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid,s.st_mode,s.st_nlink)
def pin(path,roots):
    p=pathlib.Path(path).absolute();C.need(any(r==p or pathlib.Path(r) in p.parents for r in roots)
      and not any(x.is_symlink() for x in (p,*p.parents)),'EXACT_OWN_LOCAL_OR_SHARED_ROOT')
    before=p.lstat();C.need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_nlink==1,'OWN_SINGLE_LINK_CLOSED_REGULAR')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);h=hashlib.sha256();n=0
    with os.fdopen(fd,'rb') as f:
        C.need(stamp(os.fstat(f.fileno()))==stamp(before),'SAME_CLOSED_FD_BEFORE_SHA')
        while block:=f.read(1<<20):h.update(block);n+=len(block)
        C.need(stamp(os.fstat(f.fileno()))==stamp(before)==stamp(p.lstat()) and n==before.st_size,'STABLE_CLOSED_FD_EOF_FULL_SHA')
    return {'path':str(p),'bytes':n,'sha256':h.hexdigest()}
def body(ref,declared,budget):
    C.need(ref in declared,'EXACT_DECLARED_DATA_BEFORE_OPEN')
    if pathlib.Path('/tmp') not in pathlib.Path(ref['path']).parents:return Old.body(ref,declared,budget)
    root=getattr(budget,'local_root',None);C.need(root is not None and pathlib.Path(root) in pathlib.Path(ref['path']).parents,'OWN_EXPLICIT_LOCAL_STAGE_ONLY')
    C.need(pin(ref['path'],[root])==ref,'LOCAL_CLOSED_FULL_SHA')
    fd=os.open(ref['path'],os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        first=stamp(os.fstat(f.fileno()));raw=f.read();C.need(first==stamp(os.fstat(f.fileno())) and len(raw)==ref['bytes']
          and hashlib.sha256(raw).hexdigest()==ref['sha256'],'LOCAL_BODY_SAME_FD_SHA')
    budget.check(dispatch=False);return raw
def value(ref,declared,budget):return C.O.read_staging(body(ref,declared,budget))

class Roles:
    def __init__(self,cap,mode):self.cap=cap;self.mode=mode;self.active=set();self.closed={};self.unknown=set();self.published=0;self.local_closed=0
    def bound(self):return (C.PARENT_CAP if self.mode=='SHARED_PREPARE' else C.ADMIN_CAP)+self.published
    def can_start(self):return len(self.active)<16 and self.bound()+(64<<20)<self.cap and self.local_closed+(len(self.active|self.unknown)+1)*C.WORKER_CAP<C.LOCAL_CAP
    def start(self,key):C.need(self.can_start() and key not in self.active|self.unknown|set(self.closed),'UNCLAIMED_LOCAL_ROLE');self.active.add(key)
    def settle(self,key,n,valid):
        C.need(key in self.active and type(n)is int and 0<=n<=C.WORKER_CAP,'CLOSED_LOCAL_RECORD_ROLE');self.active.remove(key);self.local_closed+=n
        if valid:self.closed[key]=n
        else:self.unknown.add(key)
    def add_export(self,n):C.need(type(n)is int and n>=0,'ACTUAL_CLOSED_EXPORT_BYTES');self.local_closed+=n
    def add_publish(self,n):C.need(self.bound()+n<=self.cap,'KNOWN_ACTUAL_PUBLICATION_WITHIN_PARENT_CAP');self.published+=n

class Budget(Old.Budget):
    def __init__(self,plan,proof,out,roles,parent_store):
        I.OriginalBudget.__init__(self,plan,proof,out);self.roles=roles;self.parent_store=parent_store;self.plan=plan
        self.carve=C.meta(plan['root_carveout_review_reference']);self.cap=plan['output_cap_bytes']
        C.M.carveout(self.carve,{'scope_key':C.MODES[plan['mode']],'node':plan['node'],'resource_authority_reference':plan['resource_authority_reference'],'estimated_peak_output_bytes':self.cap})
        self.total=self.carve['total_future_reserved_bytes'];node=plan['node']
        if node=='compute-0-13':Client=C.M.Client
        elif node=='compute-0-19':
            from workflows.data_v1_final.execution.cpu_analysis_cpu19_v1.quota_provider import Client
        elif node in ('compute-0-14','compute-0-18'):
            from workflows.data_v1_final.execution.cpu_analysis_day_v1.quota_provider import Client
        else:
            from workflows.data_v1_final.execution.cpu_analysis_general_nodes_v1.quota_provider import Client
        self.client=Client(plan['quota_provider_review_reference'],proof['request']);self.next_quota=0;self.quota=None;self.written=0
        self.quota_guard_events=out/'quota_guard_events';self.quota_guard_events.mkdir();self.quota_guard_event_references=[]
        self.quota_guard_store=Store(self.quota_guard_events,64<<20);self.forecast_records=max(1,plan.get('maximum_assigned_records',C.MAX_RECORDS));self.scope_forecast_records=self.forecast_records;self.local_root=None;self.node_book=None
    def used(self):
        C.need(self.parent_store.charged<C.ADMIN_CAP and self.roles.bound()<=self.cap,'ACTUAL_SHARED_PUBLISH_AND_FINITE_ADMIN_CAP')
        return self.roles.bound()
    def check(self,dispatch=True,force=False):
        # Original observation/expiry/quota/RSS methods; this namespace overrides
        # only role accounting and local free-space admission, not validators.
        Preparation.Budget.check(self,dispatch=dispatch,force=force)
        if self.local_root is not None:
            v=os.statvfs(self.local_root);free=v.f_bavail*v.f_frsize
            if self.node_book is None:self.node_book=NodeBook(self.plan,self.proof,self.local_root)
            needed=self.node_book.observe(len(self.roles.active|self.roles.unknown),self.plan['mode']=='SHARED_PREPARE')
            if dispatch and free<needed:self.stop_new=True;raise ValueError('ACTUAL_NODE_TMP_FREE_SHARED_SOFT_DRAIN_STOP_NEW_KEEP_ALL_STARTED')
        if dispatch and 16*(self.elapsed+time.monotonic()-self.start)>2*self.scope_forecast_records*(9.328+2.144):
            self.stop_new=True;raise ValueError('USER_CONFIRMATION_REQUIRED_ABOVE_TWO_TIMES_ACTUAL_SCOPE_FORECAST')
    def report(self):
        return {'shared_parent_role_bound_bytes':self.roles.bound(),'shared_parent_cap_bytes':self.cap,'local_closed_bytes':self.roles.local_closed,
          'local_active_or_unknown_full1GiB_roles':len(self.roles.active|self.roles.unknown),'local_cap_is_soft_not_scratch_hard_limit':True,
          'peak_RSS_bytes':self.peak,'RSS_scope':'original_parent_and_direct_workers_not_native_grandchildren',
          'minimum_MemAvailable_bytes':self.minimum,'last_actual_quota_observation':self.quota,
          'all_future_reserved_bytes':self.total,'shared_pools_counted_once_by_Root':True,'stop_new':self.stop_new,'signals_sent':False}

def local_stage(proof):
    import tempfile
    p=pathlib.Path(tempfile.mkdtemp(prefix='pprime_sharded_'+str(proof['job_id'])+'_',dir='/tmp'));p.chmod(0o700);return p

class NodeBook:
    """All-own-task node soft pressure; no reserved hard disk guarantee."""
    def __init__(self,plan,proof,root):
        self.plan=plan;self.proof=proof;self.root=root;self.key=str(proof['job_id'])+':'+str(os.getpid())+':'+ticks(os.getpid())
        self.dir=pathlib.Path('/tmp/pprime_sharded_node_1278_v2');self.dir.mkdir(exist_ok=True,mode=0o700)
        C.need(self.dir.stat().st_uid==1278 and not self.dir.is_symlink(),'OWN_NODE_RESOURCE_BOOK');self.state=self.dir/'state.json';self.lock=self.dir/'state.lock'
    def observe(self,active,preparing,closed=False):
        with self.lock.open('a+b') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX);state=json.loads(self.state.read_bytes()) if self.state.exists() else {}
            C.need(len(state)<4096,'FINITE_NODE_RESOURCE_HISTORY')
            state[self.key]={'uid':1278,'pid':os.getpid(),'start_ticks':ticks(os.getpid()),'boot_id':self.proof['boot_id'],
              'job_id':str(self.proof['job_id']),'node':self.plan['node'],'local_root':str(self.root),'active_or_unknown':active,
              'preparing':bool(preparing and not closed),'observed_at':time.time(),'parent_locally_closed_not_Slurm_C0':closed}
            # Unknown/dead identities are retained conservatively, never cleared.
            relevant=[r for r in state.values() if r['boot_id']==self.proof['boot_id'] and not r['parent_locally_closed_not_Slurm_C0']]
            # Stale records stay as UNKNOWN pressure; no time/PID assumption
            # authorizes deleting local files or retrying their physical once.
            C.need(all(r['uid']==1278 and r['node']==self.plan['node'] for r in relevant),'NODE_RESOURCE_IDENTITIES')
            needed=(4<<30)+sum(r['active_or_unknown']*(128<<20)+(11<<30 if r['preparing'] else 0) for r in relevant)
            payload=C.O.canonical(state)+b'\n';C.need(len(payload)<2<<20,'BOUNDED_NODE_SOFT_BOOK')
            tmp=self.dir/('state.partial_'+uuid.uuid4().hex)
            with tmp.open('xb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
            os.replace(tmp,self.state)
            return needed

def recover_terminal(review):
    account=C.meta(review['accounting_reference']);raw_ref=review['raw_sacct_reference'];raw=C.Q.read_small(raw_ref['path'])
    C.need(hashlib.sha256(raw).hexdigest()==raw_ref['sha256'] and len(raw)==raw_ref['bytes'],'ACTUAL_TERMINAL_RAW_ACCOUNT_SHA')
    lines=raw.decode().splitlines();C.need(lines and 'JobIDRaw' in lines[0],'SACCT_HEADER_REQUIRED');keys=lines[0].split('|')
    rows=[dict(zip(keys,line.split('|'))) for line in lines[1:] if line]
    matches=[r for r in rows if r.get('JobIDRaw')==review['actual_parent']['JobIDRaw']]
    C.need(len(matches)==1 and all(matches[0].get(k)==str(v) for k,v in review['actual_parent'].items() if k in keys)
      and matches[0]['State'] in ('COMPLETED','FAILED','TIMEOUT','CANCELLED'),'TRUE_ORIGINAL_TERMINAL_PARENT_NOT_CHILD_C0')
    return {'accounting_reference':review['accounting_reference'],'raw_sacct_reference':raw_ref,'actual_parent':matches[0]}
