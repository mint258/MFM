"""Bounded data integrity and durable identity evidence before views/count updates."""
import hashlib,json,os
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from .runtime import frame


def pin(path,budget=None):
    path=Q.literal(path);before=frame(path);digest=hashlib.sha256();size=0
    with path.open('rb') as stream:
        Q.need(frame(path)==before,'OPENED_DATA_FRAME_CHANGED')
        while size<=before[2]:
            if budget:budget.check()
            value=stream.read(min(1<<20,before[2]+1-size))
            if not value:break
            digest.update(value);size+=len(value)
        info=os.fstat(stream.fileno())
    Q.need(size==before[2] and frame(path)==before==(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_uid),'FULL_SHA_EXACT_FSTAT_FRAME_CONSERVATION')
    return {'path':str(path),'bytes':size,'sha256':digest.hexdigest()}


def write_json(path,value,budget=None):
    raw=Q.canonical(value)+b'\n';Q.need(len(raw)<=Q.SMALL,'SMALL_REVIEW_METADATA_NOT_A_SCIENTIFIC_ROW_CONTAINER')
    if budget:budget.check(len(raw),drain=True)
    with Path(path).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return pin(path)


def append(stream,value,budget):
    raw=Q.canonical(value)+b'\n';Q.need(len(raw)<=16<<20,'FULL_ROW_EVIDENCE_CONTAINER_STOP_NO_TRUNCATION')
    budget.check(len(raw),drain=True);stream.write(raw);stream.flush();os.fsync(stream.fileno());return len(raw)


def schema():
    import pyarrow as pa
    return pa.schema([('source_id',pa.string()),('source_row_ordinal',pa.int64()),('role',pa.string()),('physical_identity',pa.string()),
        ('source_offset',pa.int64()),('source_record_bytes',pa.int64()),('source_record_sha256',pa.string()),
        ('source_identity_json',pa.string()),('key_observation_json',pa.string()),('full_keys',pa.list_(pa.string())),
        ('WP5_keys',pa.list_(pa.string())),('key_state',pa.string()),('missing_full_key',pa.bool_()),('worker_pid',pa.int64())])


class Writer:
    def __init__(self,out,budget):
        import pyarrow.parquet as pq
        self.out,self.budget=out,budget;self.path=out/'identity_events.jsonl';self.file=self.path.open('xb')
        self.parquet=out/'identity_observations.parquet';self.writer=pq.ParquetWriter(self.parquet,schema(),compression='zstd')
        self.buffer=[];self.buffer_bytes=0;self.closed=False
    def dispatch(self,row):append(self.file,{'event':'ROW_DURABLE_BEFORE_SUBMIT','source':row},self.budget)
    def complete(self,value):
        row=value['observation']['source'];result=value['observation']
        size=append(self.file,{'event':'RESULT_DURABLE_BEFORE_PARQUET_OR_AGGREGATION','value':value},self.budget)
        self.buffer.append({'source_id':row['source_id'],'source_row_ordinal':row['source_row_ordinal'],'role':row['role'],
            'physical_identity':result['physical_identity'],'source_offset':row['source_offset'],'source_record_bytes':row['source_record_bytes'],
            'source_record_sha256':row['source_record_sha256'],'source_identity_json':Q.canonical(row).decode(),
            'key_observation_json':Q.canonical(result).decode(),'full_keys':result['SMILES_derived_full_keys'],'WP5_keys':result['WP5_keys'],
            'key_state':result['key_state'],'missing_full_key':result['missing_full_key'],'worker_pid':value['worker_pid']})
        self.buffer_bytes+=size
        if len(self.buffer)>=64 or self.buffer_bytes>=16<<20:self.flush()
    def flush(self):
        if self.buffer:
            import pyarrow as pa
            self.budget.check(drain=True);self.writer.write_table(pa.Table.from_pylist(self.buffer,schema=schema()));self.buffer=[];self.buffer_bytes=0
    def close(self):
        if self.closed:return
        self.flush();self.writer.close();self.file.flush();os.fsync(self.file.fileno());self.file.close();self.closed=True
        with self.parquet.open('rb') as stream:os.fsync(stream.fileno())
        return {'journal':pin(self.path),'Parquet':pin(self.parquet)}
