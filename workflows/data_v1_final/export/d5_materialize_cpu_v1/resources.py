"""Actual CPU13 quota Client, cooperative bounded IO and retained partial work."""
from __future__ import annotations
import concurrent.futures as cf,hashlib,multiprocessing as mp,os,stat,threading,time
from pathlib import Path
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as R
from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4 import quota_provider as P
from . import contract as C

RESERVE=16<<30
BATCH_BYTES=8<<20


def frame(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid)


def literal(path):
    p=Path(path);C.need(p.is_absolute() and '..' not in p.parts and not any(s.is_symlink() for s in (p,*p.parents)),'LITERAL_DATA_NO_SYMLINK_PARENT')
    return p


def verify_data(ref):
    ref=C.reference(ref);p=literal(ref['path']);before=p.lstat();h=hashlib.sha256()
    C.need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_size==ref['bytes'],'OWNED_REGULAR_EXACT_DATA')
    with p.open('rb') as f:
        C.need(frame(os.fstat(f.fileno()))==frame(before),'DATA_FD_EQUALS_LITERAL_PATH')
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
        C.need(frame(os.fstat(f.fileno()))==frame(before),'DATA_FD_FRAME_STABLE')
    C.need(frame(p.lstat())==frame(before) and h.hexdigest()==ref['sha256'],'DATA_WHOLE_SHA_AND_PATH_FRAME')
    return list(frame(before))


def unchanged(ref,observed):
    p=literal(ref['path']);s=p.lstat()
    C.need(stat.S_ISREG(s.st_mode) and list(frame(s))==list(observed),'DECLARED_DATA_FRAME_CHANGED')


def used(root):
    total=0;seen=set();root=Path(root)
    for p in Path(root).rglob('*'):
        try:s=p.lstat()
        except FileNotFoundError:
            C.need(p.name.endswith(('-journal','-wal','-shm')),'UNEXPECTED_OUTPUT_DISAPPEARANCE');continue
        C.need(s.st_uid==1278 and not stat.S_ISLNK(s.st_mode),'OWNED_OUTPUT_NO_LINKS')
        if stat.S_ISREG(s.st_mode):
            key=(s.st_dev,s.st_ino)
            if key not in seen:seen.add(key);total+=s.st_size
    # SQLite may unlink an open sort/journal file. Count owned output FDs too,
    # with inode deduplication; do not read any input/output scientific body.
    if R.MONITOR is None:pids=[os.getpid()]
    else:pids=[p['pid'] for p in R.process_tree(R.MONITOR.pid,R.MONITOR.start)['processes']]
    for pid in pids:
        directory=Path('/proc')/str(pid)/'fd'
        try:descriptors=list(directory.iterdir())
        except (FileNotFoundError,ProcessLookupError):continue
        for fd in descriptors:
            try:
                target=os.readlink(fd)
                if target.endswith(' (deleted)'):target=target[:-10]
                if not Path(target).is_relative_to(root):continue
                s=fd.stat()
            except (FileNotFoundError,ProcessLookupError):continue
            if stat.S_ISREG(s.st_mode):
                C.need(s.st_uid==1278,'OWN_SQLITE_OUTPUT_FD_REQUIRED')
                key=(s.st_dev,s.st_ino)
                if key not in seen:seen.add(key);total+=s.st_size
    return total


def worker_check(control,additional=0):
    R.soft_worker_rss(1500000000)
    C.need(not R.stop_requested(),'COOPERATIVE_STOP_BEFORE_NEXT_METADATA_BATCH')
    C.need(used(control['root'])+additional+control.get('reserve',RESERVE)<control['cap'],'WORKER_WHOLE_CAP_AND_ACTIVE_BATCH_RESERVE')


class Budget:
    def __init__(self,plan,proof,out):
        self.plan,self.proof,self.out=plan,proof,Path(out);self.start=time.monotonic();self.last_poll=0;self.observations=0;self.last_quota=None
        self.lock=threading.RLock();self.done=threading.Event();self.thread=None
        self.maximum_observed_output_bytes=0
        review=C.meta(plan['quota_reuse_reference']);self.wave=review['whole_wave_output_reserve_bytes']
        self.identity=review['publisher_identity_reference']
        C.need(proof['request']['node']==review['compute_node']=='compute-0-13','ORIGINAL_PROVIDER_STORAGE_VALIDATION_CPU13_ONLY')
        self.client=P.Client(review['provider_review_reference'],proof['request'])
        self.reserve=RESERVE if plan['mode']=='materialize' else 128<<20
        self.control={'root':str(out),'cap':plan['output_cap_bytes'],'reserve':self.reserve}
        self.check(force=True)
        self.thread=threading.Thread(target=self.poll,name='d5-finite-quota-observer',daemon=True);self.thread.start()

    def check(self,*,force=False,dispatch=True):
        with self.lock:return self._check(force=force,dispatch=dispatch)

    def _check(self,*,force=False,dispatch=True):
        R.soft_worker_rss(3<<30)
        if time.monotonic()-self.start>=self.plan['wall_seconds']-300:
            R.mark_stop('D5_FINITE_WALL_NATURAL_DRAIN',{'elapsed_seconds':time.monotonic()-self.start})
        consumed=used(self.out);remaining=max(0,self.plan['output_cap_bytes']-consumed)
        self.maximum_observed_output_bytes=max(self.maximum_observed_output_bytes,consumed)
        C.need(consumed+self.reserve<self.plan['output_cap_bytes'],'WHOLE_STAGE_OUTPUT_PLUS_DRAIN_ADMIN_RESERVE')
        if force or time.monotonic()-self.last_poll>=60:
            self.last_poll=time.monotonic()
            try:
                obs=self.client.observe();self.last_quota=obs;self.observations+=1
                C.need(obs['identity_reference']==self.identity,'EXACT_ROOT_APPROVED_FINITE_QUOTA_IDENTITY_NO_SWITCH')
                C.need(obs['free_bytes']-self.wave-remaining>=200000000000,'ACTUAL_ACCOUNT_WAVE_OWN_REMAINING_PLUS200GB')
                disk=os.statvfs(C.ROOT);C.need(disk.f_bavail*disk.f_frsize-self.wave-remaining>=200000000000,'ACTUAL_PHYSICAL_WAVE_OWN_REMAINING_PLUS200GB')
            except BaseException as exc:
                R.mark_stop('D5_QUOTA_UNKNOWN_EXPIRED_OR_RESERVE',{'error_type':type(exc).__name__})
                raise
        if dispatch:C.need(not R.stop_requested(),'D5_STOP_NEW_DISPATCH_NATURAL_DRAIN')

    def poll(self):
        while not self.done.wait(60):
            try:self.check(force=True,dispatch=False)
            except BaseException as exc:
                R.mark_stop('D5_BACKGROUND_RESOURCE_OBSERVATION_FAILED',{'error_type':type(exc).__name__});return

    def finish(self):
        self.done.set()
        if self.thread is not None:self.thread.join(timeout=60)
        C.need(self.thread is None or not self.thread.is_alive(),'FINITE_QUOTA_OBSERVER_MUST_CLOSE_NO_SIGNALS')

    def legacy_quota(self,out):
        self.check(force=True)
        # Actual current CPU Client observation, not a fabricated login receipt.
        C.need(self.last_quota is not None and self.observations>0,'ACTUAL_ACCOUNT_OBSERVATION_FIRST')
        ref=C.Q.write_new(Path(out)/'actual_legacy_quota_compatibility.json',{
            'status':'QUOTA_METADATA_VERIFIED','observed_at_epoch':self.last_quota['observed_unix_seconds'],'available_bytes':self.last_quota['free_bytes'],
            'basis':'ACTUAL_ORIGINAL_QUOTA_CLIENT_OBSERVATION','original_observation':self.last_quota,
            'provider_renewed':False,'startup_proof_reference':C.Q.pin(self.plan['_startup_proof_path'])})
        return {'quota_receipt':ref,'total_declared_new_bytes':self.wave+self.plan['output_cap_bytes']}

    def receipt(self):
        return {'original_quota_Client_object':True,'quota_observations':self.observations,'last_actual_quota_observation':self.last_quota,
            'whole_wave_output_reserve_bytes':self.wave,'publisher_renewed':False,'forced_signals_sent':False,
            'whole_output_bytes':used(self.out),'software_drain_reserve_bytes':self.reserve,
            'maximum_observed_output_bytes_including_open_SQLite_temps':self.maximum_observed_output_bytes,
            'quota_monitor_closed':self.thread is None or not self.thread.is_alive()}


def ordered_map(function,tasks,budget):
    """Exactly16 spawn workers, at most32 futures; merge in original task order."""
    iterator=iter(tasks);pending={};next_submit=0;next_take=0
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn')) as pool:
        try:
            while True:
                while len(pending)<32:
                    budget.check()
                    try:task=next(iterator)
                    except StopIteration:break
                    pending[next_submit]=pool.submit(function,task);next_submit+=1
                if not pending:break
                result=pending.pop(next_take).result();next_take+=1
                budget.check();yield result
        except BaseException:
            R.mark_stop('D5_RESOURCE_OR_TASK_FAILURE_NATURAL_DRAIN',{'submitted':next_submit,'consumed':next_take})
            # No signal, retry or deletion. Started workers close at batch guards.
            for f in pending.values():
                try:f.result()
                except BaseException:pass
            raise


def parquet(db,query,path,schema,budget,parameters=()):
    """Original Arrow row conversion/compression; resource checks between batches."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    from pipeline_v1 import io as I
    path=Path(path);C.need(not path.exists(),'NEW_PARQUET_ONLY');n=0
    with pq.ParquetWriter(path,schema,compression='zstd') as writer:
        cursor=db.execute(query,parameters)
        while True:
            budget.check();rows=cursor.fetchmany(I.BATCH)
            if not rows:break
            table=pa.Table.from_pylist([dict(r) for r in rows],schema=schema)
            C.need(table.nbytes<=I.MAX_BATCH_BYTES,'ORIGINAL128MIB_OUTPUT_BATCH_BOUND')
            writer.write_table(table,row_group_size=I.BATCH);n+=len(rows)
    budget.check()
    from wire_v1.store import file_ref
    return {**file_ref(path),'rows':n}
