"""One CPU consumption of502 immutable fragments; original typed replay and SQL only."""
import argparse,collections,hashlib,io,json,multiprocessing as mp,os,queue,sqlite3,time,traceback
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_pubchem_screening_alpha_v1 import source as S,kernel
from pubchem_consumed_partial_tail_alpha_v2.run import parquet_rows,equal
from . import contract as C
from .runtime import Budget,Stop,frame
from .resource import require_startup

CREATE_CANDIDATES="CREATE TABLE candidates(full_key TEXT PRIMARY KEY,cid INTEGER UNIQUE,wp5_key TEXT,features TEXT NOT NULL)"
CREATE_ALIASES="CREATE TABLE aliases(cid INTEGER PRIMARY KEY,full_key TEXT NOT NULL,source_ordinal INTEGER NOT NULL)"
INSERT_ALIAS="INSERT INTO aliases VALUES(?,?,?)"
SELECT_CID="SELECT cid FROM candidates WHERE full_key=?"
REPLACE_CANDIDATE="INSERT OR REPLACE INTO candidates VALUES(?,?,?,?)"
FACT_FIELDS=('ordinal','part_index','offset_bytes','source_row_bytes','smiles_bytes','source_row_sha256')
class IOStopped(RuntimeError):pass
def fd_frame(f):
    s=os.fstat(f.fileno());return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_uid)
def alive(stop):
    if stop.is_set():raise IOStopped('PARENT_RESOURCE_OR_INPUT_STOP_NO_NEW_ROWS')
def open_input(ref):
    p=Q.literal(ref['path']);before=frame(p);f=p.open('rb',buffering=1<<20)
    Q.need(fd_frame(f)==before and before[2]==ref['bytes'],'SAME_OWNED_REFERENCE_FD_AND_SIZE')
    return f,before
class ParquetDigestReader(io.RawIOBase):
    """One monotone whole-SHA frontier on the same FD used by Arrow seek reads.

    Arrow needs footer/column seeks. Gaps are hashed in bounded sequential chunks
    when the frontier advances; already hashed bytes are never hashed again.
    No second full verify pass, body copy or preflight job exists.
    """
    def __init__(self,f,ref,stop):
        super().__init__();self.f=f;self.ref=ref;self.stop=stop;self.pos=0;self.frontier=0;self.h=hashlib.sha256()
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.pos
    def seek(self,offset,whence=0):
        target=offset if whence==0 else self.pos+offset if whence==1 else self.ref['bytes']+offset
        Q.need(whence in (0,1,2) and target>=0,'VALID_PARQUET_SEEK');self.pos=target;return target
    def _advance(self,target):
        target=min(target,self.ref['bytes'])
        while self.frontier<target:
            alive(self.stop);b=os.pread(self.f.fileno(),min(4<<20,target-self.frontier),self.frontier)
            Q.need(b,'COMPLETE_PARQUET_BYTES_NO_TRUNCATION');self.h.update(b);self.frontier+=len(b)
    def read(self,size=-1):
        alive(self.stop);n=max(0,self.ref['bytes']-self.pos) if size<0 else size
        self.f.seek(self.pos);b=self.f.read(n);start=self.pos;self.pos+=len(b)
        self._advance(start)
        if self.frontier<self.pos:
            begin=max(0,self.frontier-start);self.h.update(b[begin:]);self.frontier=self.pos
        return b
    def readinto(self,b):
        data=self.read(len(b));b[:len(data)]=data;return len(data)
    def finish(self):
        self._advance(self.ref['bytes'])
        Q.need(self.frontier==self.ref['bytes'] and self.h.hexdigest()==self.ref['sha256'],'WHOLE_PARQUET_SHA_ON_SAME_FD')
        return self.h.hexdigest()
def send(out,value,stop,terminal=False):
    while True:
        try:out.put(value,timeout=1);return True
        except queue.Full:
            if stop.is_set() and not terminal:return False
def scan_fragment(spec,part,out,stop):
    alive(stop);pf,pbefore=open_input(spec['Parquet_reference']);jf,jbefore=open_input(spec['journal_reference'])
    reader=ParquetDigestReader(pf,spec['Parquet_reference'],stop);journal_hash=hashlib.sha256()
    pending=collections.deque();counts=collections.Counter({k:0 for k in C.KEYS})
    lo=spec['first_ordinal'];hi=spec['last_ordinal'];next_dispatch=lo;next_complete=lo
    first_offset=last_end=None;packet=[];packet_bytes=0;rows_iter=iter(parquet_rows(reader))
    try:
        while True:
            alive(stop);raw=jf.readline((32<<20)+1)
            if not raw:break
            Q.need(len(raw)<=32<<20 and raw.endswith(b'\n'),'ORIGINAL_COMPLETE_BOUNDED_JOURNAL_LINE')
            journal_hash.update(raw);event=json.loads(raw,object_pairs_hook=Q.pairs_unique)
            if event['event']=='DISPATCH_DURABLE_BEFORE_SUBMIT':
                inp=event['input'];ordinal=event['ordinal']
                Q.need(len(pending)<64 and ordinal==inp['ordinal']==next_dispatch<=hi
                  and inp['part_index']==spec['descriptor_index'] and inp['source_part']==part['reference'],'EXACT_SOURCE_ORDINAL_AND_FROZEN_SOURCE_PART')
                raw_source=inp['cid_source_ascii'].encode('ascii')+b'\t'+inp['source_smiles'].encode('utf-8')+bytes.fromhex(inp['source_terminator_hex'])
                rebuilt=S.record(raw_source,{k:inp[k] for k in FACT_FIELDS},part['reference'])
                Q.need(equal(rebuilt,inp),'ORIGINAL_SOURCE_ROW_SHA_UTF8_BYTES_AND_FIELDS')
                offset=inp['offset_bytes'];end=offset+inp['source_row_bytes']
                Q.need(0<=offset<end<=part['bytes'] and (last_end is None or offset==last_end),'CONTIGUOUS_SOURCE_BYTE_OFFSETS')
                if first_offset is None:first_offset=offset
                last_end=end;pending.append(inp);next_dispatch+=1
            else:
                Q.need(event['event']=='COMPLETE_RESULT_DURABLE_BEFORE_PARQUET' and pending,'ONLY_PAIRED_COMPLETE_EVENTS')
                inp=pending.popleft();v=event['value']
                Q.need(event['ordinal']==inp['ordinal']==next_complete and equal(v['input'],inp) and v['category'] in C.KEYS,'ORIGINAL_RESULT_ORDER_IDENTITY_CATEGORY')
                row=next(rows_iter);Q.need(equal(kernel.parquet_row(v,'full_shard'),row),'EVERY_ORIGINAL_PARQUET_FIELD_TYPED_BINARY64_EQUAL')
                counts[v['category']]+=1;next_complete+=1
                if v['category']=='accepted':
                    f=v['legacy_dispatcher_result'];Q.need(f['reasons']==[] and f['ordinal']==inp['ordinal']
                      and f['cid']==int(inp['cid_source_ascii']),'ORIGINAL_ACCEPTED_FEATURE_IDENTITY')
                    payload=row['full_dispatcher_result_json'];size=len(payload.encode('utf-8'))
                    Q.need(size<=32<<20,'ORIGINAL_FINITE_ACCEPTED_PAYLOAD')
                    if packet and packet_bytes+size>4<<20:
                        if not send(out,('ROWS',packet),stop):raise IOStopped('STOP_AFTER_QUEUED_PREFIX')
                        packet=[];packet_bytes=0
                    packet.append((f['cid'],f['full_key'],f['wp5_key'],f['ordinal'],payload));packet_bytes+=size
                    if len(packet)>=256 or packet_bytes>=4<<20:
                        if not send(out,('ROWS',packet),stop):raise IOStopped('STOP_AFTER_QUEUED_PREFIX')
                        packet=[];packet_bytes=0
        Q.need(not pending and next(rows_iter,None) is None and next_dispatch==next_complete==hi+1
          and dict(counts)==spec['counts'] and sum(counts.values())==spec['rows'],'FRAGMENT_EOF_ROW_MASS_ALL_THREE_CATEGORIES')
        Q.need(journal_hash.hexdigest()==spec['journal_reference']['sha256'] and jf.tell()==spec['journal_reference']['bytes'],'WHOLE_JOURNAL_SHA_SINGLE_FORWARD_CONSUMPTION')
        reader.finish()
        Q.need(fd_frame(pf)==pbefore==frame(spec['Parquet_reference']['path'])
          and fd_frame(jf)==jbefore==frame(spec['journal_reference']['path']),'BOTH_SAME_FDS_UNCHANGED_AT_COMPLETE_EOF')
        if packet and not send(out,('ROWS',packet),stop):raise IOStopped('STOP_AFTER_FINAL_PACKET')
        return {'fragment_id':spec['fragment_id'],'descriptor_index':spec['descriptor_index'],'rows':spec['rows'],'counts':dict(counts),
          'first_ordinal':lo,'last_ordinal':hi,'first_source_offset':first_offset,'last_source_end_offset':last_end,
          'source_part_reference':part['reference'],'Parquet_reference':spec['Parquet_reference'],'journal_reference':spec['journal_reference'],
          'same_FD_whole_input_SHAs_and_typed_rows_verified':True}
    finally:
        rows_iter.close();reader.close();pf.close();jf.close()
def worker(jobs,out,stop,parts):
    try:
        while not stop.is_set():
            try:spec=jobs.get(timeout=2)
            except queue.Empty:continue
            if spec is None:break
            result=scan_fragment(spec,parts[spec['descriptor_index']],out,stop)
            if not send(out,('FRAGMENT_DONE',result),stop):break
    except BaseException as exc:
        send(out,('ERROR',{'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}),stop,terminal=True)
        stop.set()
    finally:send(out,('WORKER_DONE',os.getpid()),stop,terminal=True)
def insert_accepted(db,record,counts):
    """The original screen.screen SQL/selection block, no feature computation."""
    cid,key,wp,ordinal,payload=record
    counts['after_X_and_identity']+=1
    db.execute(INSERT_ALIAS,(cid,key,ordinal))
    old=db.execute(SELECT_CID,(key,)).fetchone()
    if old:counts['pubchem_duplicate_full_key']+=1
    if old is None or cid<old[0]:
        db.execute(REPLACE_CANDIDATE,(key,cid,wp,payload))
def run(plan,proof,out,budget):
    # The five SQL strings are the original screen.py literals. Its scientific
    # functions are never invoked; preserving payload text avoids float rewriting.
    original=(Q.ROOT/'code/pubchem_science_frozen_v1/screen.py').read_text()
    for sql in (CREATE_CANDIDATES,CREATE_ALIASES,INSERT_ALIAS,SELECT_CID,REPLACE_CANDIDATE):
        Q.need(sql in original,'ORIGINAL_SCREEN_SQL_LITERAL:'+sql)
    c,flat,old=C.inputs();Q.need(flat==plan['fragments'] and old['science']==plan['science'],'EXACT_APPROVED502_INPUT_MAPPING')
    inventory,parts=S.load_inventory(plan['science'],budget)
    intent=Q.write_new(C.INTENT,{'schema':'CLOSED500_SINGLE_IO_MATERIALIZATION_INTENT_V1','job_id':proof['job_id'],
      'plan_reference':proof['plan_reference'],'coverage_reference':C.COVERAGE,'no_chemistry_or_new_epoch':True})
    dbpath=out/'screened_candidates.sqlite';db=sqlite3.connect(dbpath)
    db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL')
    db.execute(CREATE_CANDIDATES);db.execute(CREATE_ALIASES);db.commit()
    ctx=mp.get_context('spawn');jobs=ctx.Queue();messages=ctx.Queue(maxsize=2*plan['cpus']);stop=ctx.Event()
    for f in flat:jobs.put(f)
    for unused in range(plan['cpus']):jobs.put(None)
    workers=[];done_workers=set();verified={};sql_counts=collections.Counter();errors=[];pending_rows=0
    try:
        for unused in range(plan['cpus']):
            p=ctx.Process(target=worker,args=(jobs,messages,stop,parts));p.start();workers.append(p)
        while len(done_workers)<len(workers):
            if budget.stop.is_set() and not errors:errors.append({'type':'ResourceStop','message':budget.reason});stop.set()
            try:kind,value=messages.get(timeout=2)
            except queue.Empty:
                if not any(p.is_alive() for p in workers):
                    if len(done_workers)<len(workers):errors.append({'type':'WorkerExitWithoutCompleteMetadata'});stop.set()
                    break
                continue
            if kind=='WORKER_DONE':done_workers.add(value);continue
            if kind=='ERROR':errors.append(value);stop.set();continue
            if errors:continue
            try:
                if kind=='ROWS':
                    for record in value:
                        budget.check(len(record[4].encode('utf-8'))+512)
                        insert_accepted(db,record,sql_counts);pending_rows+=1
                    if pending_rows>=4096:
                        db.commit();pending_rows=0
                        Q.need(sum(p.stat().st_size for p in out.iterdir() if p.is_file())<plan['output_cap_bytes']-(128<<20),'SQLITE_AND_JOURNAL_WHOLE_OUTPUT_CAP')
                else:
                    Q.need(kind=='FRAGMENT_DONE' and value['fragment_id'] not in verified,'ONE_COMPLETE_PER_PHYSICAL_FRAGMENT')
                    verified[value['fragment_id']]=value
            except BaseException as exc:
                errors.append({'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()});stop.set()
        for p in workers:p.join()
        db.commit()
        Q.need(not errors and all(p.exitcode==0 for p in workers),'INPUT_IO_OR_SQL_ERROR_RETAIN_PARTIAL:'+str(errors[:2]))
        Q.need(set(verified)=={f['fragment_id'] for f in flat} and len(verified)==502,'ALL502_PHYSICAL_FRAGMENTS_VERIFIED')
        totals={k:sum(r['counts'][k] for r in verified.values()) for k in C.KEYS}
        Q.need(totals==C.COUNTS and sum(totals.values())==C.N and sql_counts['after_X_and_identity']==C.COUNTS['accepted'],'ALL124857440_STATES_AND_ACCEPTED_ONLY_SQL')
        for i,part in enumerate(parts):
            group=sorted((r for r in verified.values() if r['descriptor_index']==i),key=lambda r:r['first_ordinal'])
            next_ordinal=part['first_ordinal'];next_offset=0
            for r in group:
                Q.need(r['first_ordinal']==next_ordinal and r['first_source_offset']==next_offset,'NO_PREFIX_DUPLICATION_OR_ORDINAL_BYTE_GAP')
                next_ordinal=r['last_ordinal']+1;next_offset=r['last_source_end_offset']
            Q.need(next_ordinal==part['last_ordinal']+1 and next_offset==part['bytes'],'COMPLETE_ORIGINAL_SOURCE_PART_FRAMING')
        aliases=db.execute('SELECT count(*) FROM aliases').fetchone()[0];unique=db.execute('SELECT count(*) FROM candidates').fetchone()[0]
        Q.need(aliases==C.COUNTS['accepted'] and unique>0 and aliases-unique==sql_counts['pubchem_duplicate_full_key'],'ORIGINAL_ALIAS_AND_FULLKEY_DEDUP_ROW_CONSERVATION')
    finally:
        stop.set()
        # Natural drain only. After a Python-side error, consume bounded messages
        # while workers finish; never signal, terminate or touch another process.
        while any(p.is_alive() for p in workers):
            try:messages.get(timeout=1)
            except queue.Empty:pass
        for p in workers:p.join()
        db.close();jobs.close();messages.close()
    Q.need(not any(Path(str(dbpath)+suffix).exists() for suffix in ('-wal','-shm','-journal')),'CLOSED_SQLITE_NO_SIDECARS')
    fragment_manifest=Q.write_new(out/'input_fragments.json',{'schema':'CLOSED502_CONSUMED_INPUT_FRAGMENT_MANIFEST_V1',
      'coverage_reference':C.COVERAGE,'fragments':[verified[f['fragment_id']] for f in flat],
      'source_TSV_bodies_reopened_or_rehashed':False,'source_rows_reconstructed_from_original_journal':True})
    database=S.pin(dbpath,budget)
    return {'status':'MATERIALIZED_UNFILTERED_NO_RELEASE','database':database,'input_fragment_manifest_reference':fragment_manifest,
      'fragment_count':502,'source_rows':C.N,'counts':C.COUNTS,'aliases_rows':aliases,'unique_full_keys':unique,
      'original_SQL_counts':dict(sql_counts),'intent_reference':intent,'database_tables':['candidates','aliases'],
      'database_contract':'ORIGINAL_SCREEN_CANDIDATES_ALIASES_SQL_MINIMUM_CID','original_payload_JSON_text_preserved':True,
      'UNKNOWN_not_chemical_exclusion':True,'chemical_functions_or_RDKit_calls':0,'decontamination_filter_rank_or_training_release':False}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);p.add_argument('--startup-proof',required=True);a=p.parse_args()
    plan,proof=require_startup(a.plan,a.startup_proof);out=Q.literal(plan['output_directory']);Q.need(not out.exists(),'FRESH_SQLITE_OUTPUT')
    out.mkdir(parents=True,mode=0o700);budget=None
    try:
        budget=Budget(plan,proof,out);result=run(plan,proof,out,budget)
        result.update(schema='ALPHA_CLOSED500_UNFILTERED_MATERIALIZATION_RECEIPT_V1',endpoint=Q.ENDPOINT,uid=1264,
          job_id=proof['job_id'],node=plan['node'],cpus=plan['cpus'],plan_reference=proof['plan_reference'],
          startup_proof_reference=Q.ref(a.startup_proof),coverage_reference=C.COVERAGE,cost_gate_reference=plan['cost_gate_reference'],
          runtime_budget=budget.receipt(),new_parent_terminal_accounting_pending=True)
        ref=Q.write_new(out/'receipt.json',result);print(Q.canonical({'receipt_reference':ref,'status':result['status']}).decode());return 0
    except BaseException as exc:
        Q.write_new(out/'failure.json',{'schema':'CLOSED500_MATERIALIZATION_FAILURE_V1','job_id':proof['job_id'],
          'error':type(exc).__name__+': '+str(exc),'no_auto_retry':True,'partial_new_SQLite_retained_no_release':True,
          'original_inputs_modified':False,'runtime_budget':budget.receipt() if budget else None})
        raise
    finally:
        if budget:budget.finish()
if __name__=='__main__':raise SystemExit(main())
