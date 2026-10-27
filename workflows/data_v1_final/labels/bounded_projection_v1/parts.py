"""Durable whole-ticket and closed-window cursors; no scientific calculations."""
from __future__ import annotations
import hashlib,io,json,os,sqlite3,uuid
from pathlib import Path


def need(ok,code):
    if not ok:raise ValueError(code)


class TicketStop(RuntimeError):pass


def pin(path):
    p=Path(path);h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return {'path':str(p.absolute()),'bytes':p.stat().st_size,'sha256':h.hexdigest()}


def fsync_directory(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def publish_bytes(path,raw):
    """Fresh names only. A renamed but uncommitted file remains unpublished."""
    p=Path(path);temporary=Path(str(p)+'.partial');need(not p.exists(),'NO_PART_OVERWRITE')
    with temporary.open('xb') as f:need(f.write(raw)==len(raw),'SHORT_PRIVATE_PART_WRITE');f.flush();os.fsync(f.fileno())
    os.rename(temporary,p);fsync_directory(p.parent);reference=pin(p)
    need(reference['bytes']==len(raw) and reference['sha256']==hashlib.sha256(raw).hexdigest(),'PUBLISHED_PRIVATE_BYTES_DIFFER')
    return reference


class Ledger:
    def __init__(self,path,create=False,*,data_cap=None,inode_cap=None,ranges=()):
        self.db=sqlite3.connect(path,timeout=120,isolation_level=None)
        self.db.execute('PRAGMA busy_timeout=120000');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA cache_size=-4096');self.db.execute('PRAGMA max_page_count=16384')
        if create:
            self.db.executescript('''
            PRAGMA journal_mode=DELETE;
            CREATE TABLE budget(id INTEGER PRIMARY KEY CHECK(id=1),cap INTEGER,inodes INTEGER,charged INTEGER,charged_inodes INTEGER);
            CREATE TABLE ranges(range_id TEXT PRIMARY KEY,cursor INTEGER NOT NULL,stop INTEGER NOT NULL);
            CREATE TABLE tickets(ticket TEXT PRIMARY KEY,range_id TEXT,lo INTEGER,amount INTEGER,inodes INTEGER,status TEXT,receipt TEXT);
            CREATE TABLE windows(range_id TEXT,lo INTEGER,hi INTEGER,receipt TEXT,PRIMARY KEY(range_id,lo));
            ''')
            self.db.execute('INSERT INTO budget VALUES(1,?,?,0,0)',(data_cap,inode_cap))
            self.db.executemany('INSERT INTO ranges VALUES(?,?,?)',[(r['range_id'],r['physical_row_lo'],r['physical_row_hi']) for r in ranges])

    def close(self):self.db.close()

    def cursor(self,key):
        row=self.db.execute('SELECT cursor,stop FROM ranges WHERE range_id=?',(key,)).fetchone()
        need(row is not None,'KNOWN_RANGE_REQUIRED');return row

    def reserve(self,key,lo,amount,inodes):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            need(type(amount) is int and amount>0 and type(inodes) is int and inodes>0,'FINITE_POSITIVE_TICKET')
            need(self.cursor(key)[0]==lo,'TICKET_START_IS_CLOSED_CURSOR')
            need(self.db.execute("SELECT count(*) FROM tickets WHERE range_id=? AND status<>'CLOSED'",(key,)).fetchone()[0]==0,
              'NO_SECOND_DISPATCH_OR_AUTOMATIC_UNKNOWN_RETRY')
            cap,limit,used,n=self.db.execute('SELECT cap,inodes,charged,charged_inodes FROM budget').fetchone()
            if used+amount>cap or n+inodes>limit:raise TicketStop('WHOLE_OUTPUT_OR_INODE_TICKET_CAP')
            ticket=uuid.uuid4().hex
            self.db.execute('INSERT INTO tickets VALUES(?,?,?,?,?,?,NULL)',(ticket,key,lo,amount,inodes,'RESERVED'))
            self.db.execute('UPDATE budget SET charged=charged+?,charged_inodes=charged_inodes+?',(amount,inodes))
            self.db.execute('COMMIT');return ticket
        except BaseException:self.db.execute('ROLLBACK');raise

    def commit(self,ticket,hi,receipt,actual_bytes,actual_inodes):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT range_id,lo,amount,inodes,status FROM tickets WHERE ticket=?',(ticket,)).fetchone()
            need(row is not None and row[4]=='RESERVED','ONE_COMMIT_PER_TICKET')
            key,lo,amount,n,_=row;cursor,stop=self.cursor(key)
            need(cursor==lo and lo<hi<=stop,'EXACT_NONOVERLAPPING_CLOSED_PHYSICAL_INTERVAL')
            need(0<actual_bytes<=amount and 0<actual_inodes<=n,'ACTUAL_PARTS_INSIDE_RESERVED_TICKET')
            encoded=json.dumps(receipt,sort_keys=True,separators=(',',':'))
            self.db.execute('INSERT INTO windows VALUES(?,?,?,?)',(key,lo,hi,encoded))
            self.db.execute('UPDATE ranges SET cursor=? WHERE range_id=?',(hi,key))
            self.db.execute('UPDATE tickets SET status=?,amount=?,inodes=?,receipt=? WHERE ticket=?',('CLOSED',actual_bytes,actual_inodes,encoded,ticket))
            self.db.execute('UPDATE budget SET charged=charged-?,charged_inodes=charged_inodes-?',(amount-actual_bytes,n-actual_inodes))
            self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise

    def abandon(self,ticket):
        # No reclaim: a failed write/rename may have consumed all reserved bytes.
        self.db.execute("UPDATE tickets SET status='UNKNOWN_UNPUBLISHED' WHERE ticket=? AND status='RESERVED'",(ticket,))

    def snapshot(self):
        cap,n,charged,inodes=self.db.execute('SELECT cap,inodes,charged,charged_inodes FROM budget').fetchone()
        return {'data_cap_bytes':cap,'charged_bytes_including_unknown':charged,'charged_inodes':inodes,'data_inode_cap':n,
          'ranges':[{'range_id':r,'next_physical_row':c,'physical_row_hi':e,'complete':c==e} for r,c,e in self.db.execute('SELECT * FROM ranges ORDER BY range_id')],
          'closed_windows':[{'range_id':r,'lo':lo,'hi':hi,'receipt':json.loads(p)} for r,lo,hi,p in self.db.execute('SELECT * FROM windows ORDER BY range_id,lo')],
          'unpublished_tickets':[{'ticket':t,'range_id':r,'lo':lo,'reserved_bytes':b,'status':s} for t,r,lo,b,s in self.db.execute("SELECT ticket,range_id,lo,amount,status FROM tickets WHERE status<>'CLOSED'")]}


class CappedBuffer(io.BytesIO):
    def __init__(self,cap):super().__init__();self.cap=cap
    def write(self,raw):
        need(self.tell()+len(raw)<=self.cap,'ONE_TYPED_PART_SERIALIZED_CAP_NO_TRUNCATION')
        return super().write(raw)
    def close(self):pass  # Arrow may close its wrapper; the owner retains bytes for verification.
    def release(self):super().close()


class TypedPart:
    """Only Arrow IO. Scientific encoding and schema remain frozen imports."""
    def __init__(self,kind,task,cap,row_cap):
        import pyarrow as pa
        import pyarrow.parquet as pq
        from workflows.data_v1_final.labels.lossless_projection_pilot_v1.run import schema
        self.kind=kind;self.task=task;self.pa=pa;self.schema=schema(pa);self.row_cap=row_cap
        self.stream=CappedBuffer(cap);self.writer=pq.ParquetWriter(self.stream,self.schema,compression='zstd',use_dictionary=True)
        self.buffer=[];self.buffer_bytes=0;self.rows=0;self.digest=hashlib.sha256();self.finished=False

    def add(self,row):
        need(row['row_kind']==self.kind and row['task_code']==self.task,'ONE_FAMILY_TASK_PER_TYPED_PART')
        size=len(row['tree_json'].encode('utf-8'))+8*len(row['values_float64'])
        need(size<=self.row_cap,'UNCHANGED_64MIB_SCIENTIFIC_ROW_CAP')
        self.buffer.append(row);self.buffer_bytes+=size;self.rows+=1
        self.digest.update((row['row_kind']+'|'+str(row['record_ordinal'])+'|'+str(row['task_code'])+'|'+row['scientific_signature']).encode())
        if len(self.buffer)>=64 or self.buffer_bytes>=8<<20:self.flush()

    def flush(self):
        if self.buffer:
            self.writer.write_table(self.pa.Table.from_pylist(self.buffer,schema=self.schema),row_group_size=64)
            self.buffer=[];self.buffer_bytes=0

    def approximate_bytes(self):return self.stream.tell()+self.buffer_bytes

    def finish(self,path):
        import pyarrow.parquet as pq
        from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import verify_cache_row
        need(not self.finished,'PART_FINISHED_ONCE');self.finished=True;self.flush();self.writer.close()
        raw=self.stream.getvalue();reference=publish_bytes(path,raw);del raw
        count=0;digest=hashlib.sha256();source=pq.ParquetFile(path)
        try:
            for batch in source.iter_batches(batch_size=16,use_threads=False):
                for row in batch.to_pylist():
                    verify_cache_row(row)
                    need(row['row_kind']==self.kind and row['task_code']==self.task,'REOPEN_TYPED_TASK_CHANGED')
                    digest.update((row['row_kind']+'|'+str(row['record_ordinal'])+'|'+str(row['task_code'])+'|'+row['scientific_signature']).encode());count+=1
        finally:source.close()
        need(count==self.rows and digest.digest()==self.digest.digest(),'PART_REOPEN_LOGICAL_ORDER_BITS_MASS')
        self.stream.release()
        return {'reference':reference,'row_kind':self.kind,'task_code':self.task,'rows':count,'typed_stream_sha256':digest.hexdigest()}


def slices(groups,lo,hi):
    """Actual footer directory: skip complete RGs; only a boundary prefix repeats."""
    need(type(lo) is int and type(hi) is int and 0<=lo<hi,'VALID_HALFOPEN_PHYSICAL_RANGE')
    covered=lo
    for group in groups:
        a,b=group['physical_row_lo'],group['physical_row_hi']
        if b<=lo or a>=hi:continue
        start,stop=max(lo,a),min(hi,b)
        need(start==covered and start<stop,'ACTUAL_RG_DIRECTORY_GAP_OR_OVERLAP')
        yield dict(group,selected_lo=start,selected_hi=stop);covered=stop
    need(covered==hi,'ACTUAL_RG_DIRECTORY_INCOMPLETE_FOR_REQUEST')
