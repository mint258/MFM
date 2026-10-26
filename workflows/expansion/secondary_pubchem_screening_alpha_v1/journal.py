"""Append-only dispatch and complete-result evidence before any Parquet flush."""
import json,os,time
from collections import Counter
from . import contracts as C,source,kernel
from secondary_cpu_queue_v1 import common as Q

def append(stream,value,budget,drain=False):
    raw=(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=True)+'\n').encode()
    Q.need(len(raw)<=C.CONTAINER_CAP//32,'FULL_RECORD_CONTAINER_STOP_NO_TRUNCATION');budget.check(len(raw),drain=drain)
    stream.write(raw);stream.flush();os.fsync(stream.fileno());return len(raw)

class Writer:
    def __init__(self,out,group,budget):
        import pyarrow.parquet as pq
        self.out,self.group,self.budget=out,group,budget;self.path=out/(group+'.events.jsonl');self.file=self.path.open('xb')
        self.parquet=out/(group+'.features.parquet');self.writer=pq.ParquetWriter(self.parquet,kernel.output_schema(),compression='zstd')
        self.buffer=[];self.buffer_bytes=0;self.counts=Counter({'accepted':0,'chemReject':0,'technicalUnresolved':0});self.workers=Counter();self.timing=Counter()
        self.dispatched=self.completed=0;self.last_dispatched=self.last_completed=None;self.start=time.monotonic()
    def dispatch(self,original):
        Q.need(self.last_dispatched is None or original['ordinal']>self.last_dispatched,'STRICT_DISPATCH_ORDINAL_ORDER')
        append(self.file,{'event':'DISPATCH_DURABLE_BEFORE_SUBMIT','ordinal':original['ordinal'],'input':original},self.budget)
        self.dispatched+=1;self.last_dispatched=original['ordinal']
    def complete(self,original,value,error=None):
        if value is None:
            value={'input':original,'category':'technicalUnresolved','technical_codes':['WORKER_EXECUTION_UNKNOWN'],
                'audit_parse_succeeded':None,'audit_flags':{},'legacy_dispatcher_result':None,'errors':{'WORKER_EXECUTION_UNKNOWN':error},
                'worker_pid':None,'audit_wall_seconds':0.,'audit_CPU_seconds':0.,
                'dispatcher_wall_seconds_includes_legacy_X_parse':0.,'dispatcher_CPU_seconds_includes_legacy_X_parse':0.}
        Q.need(value['input']['ordinal']==original['ordinal'] and value['category'] in self.counts,'EXACT_RESULT_IDENTITY_AND_THREE_DISJOINT_STATES')
        size=append(self.file,{'event':'COMPLETE_RESULT_DURABLE_BEFORE_PARQUET','ordinal':original['ordinal'],'value':value},self.budget,drain=True)
        self.buffer_bytes+=size
        self.buffer.append(kernel.parquet_row(value,self.group));self.counts[value['category']]+=1;self.completed+=1
        self.last_completed=original['ordinal']
        if value.get('worker_pid') is not None:self.workers[str(value['worker_pid'])]+=1
        for name in ('audit_wall_seconds','audit_CPU_seconds','dispatcher_wall_seconds_includes_legacy_X_parse','dispatcher_CPU_seconds_includes_legacy_X_parse'):
            self.timing[name]+=value[name]
        if len(self.buffer)>=64 or self.buffer_bytes>=16<<20:self.flush()
        return value
    def flush(self):
        if self.buffer:
            import pyarrow as pa
            self.budget.check(drain=True);self.writer.write_table(pa.Table.from_pylist(self.buffer,schema=kernel.output_schema()));self.buffer=[];self.buffer_bytes=0
    def close(self):
        self.flush();self.writer.close();self.file.flush();os.fsync(self.file.fileno());self.file.close()
        with self.parquet.open('rb') as stream:os.fsync(stream.fileno())
        return {'group':self.group,'dispatched_rows':self.dispatched,'completed_rows':self.completed,'counts':dict(self.counts),
            'last_dispatched_ordinal':self.last_dispatched,'last_completed_ordinal':self.last_completed,'worker_records':dict(self.workers),
            'worker_task_phase_sums':dict(self.timing),'phase_wall_seconds':time.monotonic()-self.start,
            'full_dispatch_and_result_journal':source.pin(self.path),'features':source.pin(self.parquet),
            'technical_unknown_is_chemical_exclusion':False,'journal_precedes_parquet':True}
