"""Explicit grouped I/O epoch; original scanner/dispatcher callables unchanged."""
import collections,concurrent.futures as cf,hashlib,json,os,time
from pathlib import Path
from . import io as I

MODE='GROUPED_SOURCE_DURABLE_BEFORE_DISPATCH_V1'


def validate(policy):
    I.need(policy['schema']=='ALPHA_COMMON_GROUPED_IO_POLICY_V1' and policy['mode']==MODE,'EXPLICIT_NEW_GROUPED_IO_POLICY')
    I.need(type(policy['checkpoint_bytes']) is int and 1<=policy['checkpoint_bytes']<=8<<20
      and type(policy['checkpoint_seconds']) in (int,float) and 0<policy['checkpoint_seconds']<=2
      and policy['maximum_pending_MIDs']==32,'FINITE_GROUPED_CHECKPOINT_AND_ORIGINAL_PENDING_BOUND')
    for field in ('final_close_flush_fsync','deferred_per_record_durable_requests','source_durable_before_real_worker_submit','full_readback_required'):
        I.need(policy[field] is True,'EXPLICIT_IO_POLICY_'+field)
    I.need(policy['checkpoint_is_resume_authority'] is False,'NO_PARTIAL_PREFIX_AS_SCIENTIFIC_RESUME_AUTHORITY')
    I.need(policy['db_commit_requests_per_group']==32 and policy['db_commit_seconds']==policy['checkpoint_seconds']
      and policy['deferred_SQLite_commit_requests'] is True and policy['SQLite_synchronous_FULL_unchanged'] is True
      and policy['SQLite_partial_is_resume_authority'] is False,'EXPLICIT_NEW_SQLITE_COMMIT_GROUP_POLICY')
    return dict(policy)


class Budget:
    def __init__(self,guard,policy,clock=time.monotonic):self.guard=guard;self.policy=validate(policy);self.writers=[];self.pool=None;self.clock=clock;self.database=None
    def check(self,*args,**kwargs):
        self.guard.check(*args,**kwargs)
        for writer in self.writers:writer.maybe_checkpoint()
        if self.database is not None:self.database.maybe_commit()
        if self.pool is not None:self.pool.dispatch_ready()


class Writer:
    def __init__(self,path,budget):
        self.path=Path(path);self.budget=budget;self.policy=budget.policy;self.stream=self.path.open('xb')
        self.bytes=self.rows=self.committed_bytes=self.committed_rows=0;self.digest=hashlib.sha256()
        self.last_checkpoint=budget.clock();self.checkpoints=0;self.requested_durable_rows=0;self.closed=False
        self.checkpoint_path=self.path.with_name(self.path.name+'.checkpoint.json');budget.writers.append(self)
    def write(self,value,durable=False):
        self.budget.check();raw=I.canonical(value);self.stream.write(raw);self.digest.update(raw)
        self.bytes+=len(raw);self.rows+=1;self.requested_durable_rows+=bool(durable)
        self.maybe_checkpoint()
    def maybe_checkpoint(self):
        if self.closed or self.bytes==self.committed_bytes:return
        if self.bytes-self.committed_bytes>=self.policy['checkpoint_bytes'] or self.budget.clock()-self.last_checkpoint>=self.policy['checkpoint_seconds']:
            self.checkpoint('BYTE_OR_PROGRESS_CLOCK_GROUP')
    def checkpoint(self,reason):
        if self.closed:return
        self.stream.flush();os.fsync(self.stream.fileno())
        self.committed_bytes=self.bytes;self.committed_rows=self.rows;self.checkpoints+=1
        record=dict(schema='ALPHA_COMMON_GROUPED_DURABLE_PREFIX_V1',path=str(self.path),mode=MODE,
          committed_bytes=self.committed_bytes,committed_rows=self.committed_rows,committed_prefix_sha256=self.digest.hexdigest(),
          row_boundary='COMPLETE_CANONICAL_JSON_UTF8_PLUS_LF',reason=reason,checkpoint_ordinal=self.checkpoints,
          requested_per_record_durable_rows=self.requested_durable_rows,per_record_fsync_performed=False,
          partial_prefix_is_not_a_scientific_resume_or_C0=True)
        pending=self.checkpoint_path.with_name(self.checkpoint_path.name+'.pending_%08d'%self.checkpoints)
        with pending.open('xb') as stream:stream.write(I.canonical(record));stream.flush();os.fsync(stream.fileno())
        os.replace(pending,self.checkpoint_path)
        fd=os.open(self.path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
        self.last_checkpoint=self.budget.clock()
    def close(self):
        if not self.closed:
            self.checkpoint('FINAL_CLOSE');self.stream.close();self.closed=True
    def reference(self):I.need(self.closed,'CLOSED_GROUPED_WRITER_ONLY');return I.pin(self.path,self.budget.check)
    def receipt(self):
        return dict(path=str(self.path),mode=MODE,rows=self.rows,bytes=self.bytes,committed_rows=self.committed_rows,
          committed_bytes=self.committed_bytes,requested_per_record_durable_rows=self.requested_durable_rows,
          actual_fsync_groups=self.checkpoints,per_record_fsync_performed=False,
          checkpoint_reference=I.pin(self.checkpoint_path,self.budget.guard.check) if self.checkpoint_path.exists() else None)


class SourceDurablePool:
    """Return ordinary Futures; start work only after its source prefix is durable."""
    def __init__(self,pool,source,budget):
        self.pool=pool;self.source=source;self.budget=budget;self.pending=collections.deque();budget.pool=self
        self.real_submissions=0
    def submit(self,function,*args,**kwargs):
        future=cf.Future();self.pending.append((self.source.bytes,future,function,args,kwargs))
        if len(self.pending)>=self.budget.policy['maximum_pending_MIDs']:self.source.checkpoint('ORIGINAL32_PENDING_DISPATCH_GROUP')
        self.dispatch_ready();return future
    def dispatch_ready(self):
        while self.pending and self.pending[0][0]<=self.source.committed_bytes:
            required,target,function,args,kwargs=self.pending.popleft()
            I.need(self.source.committed_rows>0 or required==0,'SOURCE_PREFIX_DURABLE_BEFORE_WORKER')
            real=self.pool.submit(function,*args,**kwargs);self.real_submissions+=1
            def forward(done,target=target):
                try:target.set_result(done.result())
                except BaseException as exc:target.set_exception(exc)
            real.add_done_callback(forward)


class Connection:
    """Same SQLite connection, SQL and FULL durability; explicit deferred commit I/O."""
    def __init__(self,connection,path,budget):
        self.connection=connection;self.path=Path(path);self.budget=budget;self.closed=False
        I.need(connection.execute('PRAGMA synchronous').fetchone()[0]==2
          and connection.execute('PRAGMA journal_mode').fetchone()[0].lower()=='delete','ORIGINAL_SQLITE_FULL_DELETE_MODE_UNCHANGED')
        self.requests=self.committed_requests=self.actual_commits=0;self.last_commit=budget.clock()
        self.checkpoint_path=self.path.with_name(self.path.name+'.commit_checkpoint.json');budget.database=self
    def __getattr__(self,name):return getattr(self.connection,name)
    def commit(self):
        self.requests+=1
        if self.requests-self.committed_requests>=self.budget.policy['db_commit_requests_per_group']:self.checkpoint('ORIGINAL32_COMMIT_REQUEST_GROUP')
        else:self.maybe_commit()
    def maybe_commit(self):
        if not self.closed and self.requests>self.committed_requests and self.budget.clock()-self.last_commit>=self.budget.policy['db_commit_seconds']:
            self.checkpoint('PROGRESS_CLOCK_COMMIT_GROUP')
    def checkpoint(self,reason):
        if self.closed:return
        self.connection.commit();self.actual_commits+=1;self.committed_requests=self.requests
        value=dict(schema='ALPHA_COMMON_GROUPED_SQLITE_COMMIT_PREFIX_V1',path=str(self.path),reason=reason,
          original_commit_requests=self.requests,confirmed_commit_request_ordinal=self.committed_requests,
          actual_SQLite_commits=self.actual_commits,connection_total_changes_at_commit=self.connection.total_changes,
          synchronous='FULL',journal_mode='DELETE',same_connection_read_your_writes=True,
          intermediate_database_is_not_scientific_resume_or_C0=True,database_binary_equivalence_claimed=False)
        pending=self.checkpoint_path.with_name(self.checkpoint_path.name+'.pending_%08d'%self.actual_commits)
        with pending.open('xb') as stream:stream.write(I.canonical(value));stream.flush();os.fsync(stream.fileno())
        os.replace(pending,self.checkpoint_path);fd=os.open(self.path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
        self.last_commit=self.budget.clock()
    def close(self):
        if not self.closed:self.checkpoint('FINAL_REAL_COMMIT_CLOSE');self.connection.close();self.closed=True
    def receipt(self):
        return dict(original_commit_requests=self.requests,actual_SQLite_commits=self.actual_commits,
          confirmed_commit_request_ordinal=self.committed_requests,synchronous='FULL',journal_mode='DELETE',
          database_binary_equivalence_claimed=False,checkpoint_reference=I.pin(self.checkpoint_path,self.budget.guard.check))
