"""Declared DATA FD IO and original finite CPU13 resource orchestration."""
from __future__ import annotations
import contextlib,hashlib,json,os,pathlib,stat,time
from workflows.data_v1_final.export.d5_materialize_cpu_v1 import resources as R
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as OBS
from . import contract as C
ROW_CAP=256<<20;BATCH_ROWS=64
NEXT_WORKER_POLL=0.0


class Budget(R.Budget):
    def __init__(self,plan,proof,out):
        # Resource-only mode selection reuses the original 16GiB reserve and
        # exact original Client/200GB/60s/120s/identity/node13 constraints.
        resource_plan=dict(plan,mode='materialize')
        super().__init__(resource_plan,proof,out)

    def check(self,*,force=False,dispatch=True):
        if not force and time.monotonic()<getattr(self,'next_full_resource_poll',0):
            if dispatch:C.need(not OBS.stop_requested(),'COOPERATIVE_BOUNDED_RESOURCE_STOP')
            return
        value=super().check(force=force,dispatch=dispatch)
        self.next_full_resource_poll=time.monotonic()+1;return value


def worker_check(control,additional=0):
    global NEXT_WORKER_POLL
    OBS.soft_worker_rss(1500000000);C.need(not OBS.stop_requested(),'NATURAL_DRAIN_BEFORE_NEXT_ORIGINAL_DISTANCE_OR_ROW')
    if additional or time.monotonic()>=NEXT_WORKER_POLL:
        R.worker_check(control,additional);NEXT_WORKER_POLL=time.monotonic()+1


@contextlib.contextmanager
def held(ref,declared,check):
    ref=C.reference(ref);C.need(ref in declared,'SCIENTIFIC_DATA_DECLARED_BEFORE_OPEN')
    path=R.literal(ref['path']);before=path.lstat();frame=R.frame(before)
    C.need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_size==ref['bytes'],'REAL_SOURCE_FRAME_UID_SIZE')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        C.need(R.frame(os.fstat(fd))==frame,'EXACT_SOURCE_FD_PATH_IDENTITY');h=hashlib.sha256();n=0
        while True:
            check();block=os.read(fd,1<<20)
            if not block:break
            h.update(block);n+=len(block)
        C.need(n==ref['bytes'] and h.hexdigest()==ref['sha256'],'WHOLE_DECLARED_DATA_SHA_BEFORE_PARSE')
        os.lseek(fd,0,os.SEEK_SET);yield path,fd,frame
    finally:
        try:C.need(R.frame(os.fstat(fd))==frame==R.frame(path.lstat()),'SOURCE_FD_AND_PATH_STABLE_AT_CLOSE')
        finally:os.close(fd)


def body(ref,declared,check,cap):
    C.need(ref['bytes']<=cap,'EXPLICIT_BODY_SOFTWARE_CAP_NOT_SMALL_METADATA_LIMIT')
    with held(ref,declared,check) as (_,fd,_):
        result=bytearray()
        while True:
            check();v=os.read(fd,1<<20)
            if not v:break
            result.extend(v);C.need(len(result)<=cap,'COMPLETE_BODY_NO_TRUNCATION')
        return bytes(result)


def json_body(ref,declared,check,cap=ROW_CAP):
    from workflows.data_v1_final.export.native_availability_v1.reader import no_duplicates
    def bad(value):raise ValueError('NONSTANDARD_JSON_NUMBER:'+value)
    return json.loads(body(ref,declared,check,cap),object_pairs_hook=no_duplicates,parse_constant=bad)


def jsonl(ref,declared,check):
    from workflows.data_v1_final.export.native_availability_v1.reader import no_duplicates
    def bad(value):raise ValueError('NONSTANDARD_JSON_NUMBER:'+value)
    with held(ref,declared,check) as (_,fd,_):
        with os.fdopen(os.dup(fd),'rb') as f:
            for raw in f:
                check();C.need(0<len(raw)<=ROW_CAP,'BOUNDED_COMPLETE_JSONL_RECORD')
                yield json.loads(raw,object_pairs_hook=no_duplicates,parse_constant=bad)


def batches(ref,declared,check,columns=None):
    import pyarrow.parquet as pq
    with held(ref,declared,check) as (_,fd,_):
        with os.fdopen(os.dup(fd),'rb') as stream:
            p=pq.ParquetFile(stream)
            try:
                for batch in p.iter_batches(batch_size=BATCH_ROWS,columns=columns,use_threads=False):
                    check();C.need(batch.nbytes<=ROW_CAP,'COMPLETE_PARQUET_BATCH_SOFTWARE_CAP');yield batch
            finally:p.close()


def rows(ref,declared,check,columns=None):
    for batch in batches(ref,declared,check,columns):yield from batch.to_pylist()


def actual_ref(path):
    path=pathlib.Path(path);s=path.lstat();h=hashlib.sha256()
    C.need(stat.S_ISREG(s.st_mode) and s.st_uid==1278 and not path.is_symlink(),'OWN_COMPLETE_OUTPUT_FILE')
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
        C.need(R.frame(os.fstat(f.fileno()))==R.frame(s),'OUTPUT_FD_STABLE')
    C.need(R.frame(path.lstat())==R.frame(s),'OUTPUT_PATH_STABLE')
    return {'path':str(path),'bytes':s.st_size,'sha256':h.hexdigest()}


def bytes_new(path,raw,budget):
    budget.check();C.need(len(raw)<=ROW_CAP,'BOUNDED_COMPLETE_NEW_DATA_RECORD')
    R.worker_check(budget.control,len(raw))
    with pathlib.Path(path).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return actual_ref(path)


def parquet_rows(path,rows0,schema,budget):
    import pyarrow as pa
    import pyarrow.parquet as pq
    C.need(not pathlib.Path(path).exists(),'NEW_TYPED_TABLE_ONLY');pending=[];count=0
    with pq.ParquetWriter(path,schema,compression='zstd') as w:
        def flush():
            nonlocal count
            if not pending:return
            budget.check();table=pa.Table.from_pylist(pending,schema=schema)
            C.need(table.nbytes<=ROW_CAP,'COMPLETE_TYPED_BATCH_NO_TRUNCATION');R.worker_check(budget.control,table.nbytes)
            w.write_table(table,row_group_size=BATCH_ROWS);count+=len(pending);pending.clear()
        for row in rows0:
            pending.append(row)
            if len(pending)==BATCH_ROWS:flush()
        flush()
    budget.check();return {**actual_ref(path),'rows':count}
