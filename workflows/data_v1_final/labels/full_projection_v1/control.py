"""Small cross-batch authority; no label decoding or statistical calculations."""
from __future__ import annotations
import json,sqlite3

SCOPE='labels_full_typed_projection_batch_v1'
CLOSE_SCOPE='labels_full_typed_projection_coverage_v1'
CALIBRATION='PENDING_MATCHED_FULL_TRAIN_NO_512_SCALE_REUSE'
SCHEMA='FULL_LABEL_PROJECTION_MASTER_V1'


def need(ok,code):
    if not ok:raise ValueError(code)


def source_contract(files):
    ids=[r['file_id'] for r in files];paths=[r['path'] for r in files]
    need(len(ids)==len(set(ids))==2208 and len(paths)==len(set(paths)),'ALL2208_DISTINCT_SOURCE_IDS_AND_PATHS')
    labels=[r for r in files if r['source_kind']=='label'];base=[r for r in files if r['source_kind']=='base']
    need(len(labels)==2024 and len(base)==184,'EXACT2024_LABEL184_BASE_SCOPE')
    need(sum(r['rows'] for r in labels)==157254650 and sum(r['rows'] for r in base)==11232475,'ACTUAL_FOOTER_PHYSICAL_MASS')
    need(all(type(r['rows']) is int and r['rows']>0 for r in files),'FINITE_POSITIVE_SOURCE_ROWS')
    return {'files':2208,'label_files':2024,'base_files':184,
      'label_physical_rows':157254650,'label_canonical_task_rows':157245956,'label_shadow_rows':8694,
      'base_physical_rows':11232475,'base_canonical_rows':11231854,'base_noncanonical_rows':621,
      'canonical_records':11231854,'canonical_molecules':1220466,'task_slots':14}


def partition_sources(files):
    """Fixed file ownership; independent of cache batch size or completion order."""
    out=[[] for _ in range(16)];weights=[0]*16
    for r in sorted(files,key=lambda r:(-r['rows'],r['file_id'])):
        i=min(range(16),key=lambda i:(weights[i],i));out[i].append(r['file_id']);weights[i]+=r['rows']
    return [{'partition_id':i,'file_ids':sorted(v),'physical_rows':weights[i]} for i,v in enumerate(out)]


def review_contract(master,review,master_reference):
    """Root writes this separately after actual profile and fresh storage review."""
    need(master['schema']==SCHEMA and master['executable'] is False,'CANDIDATE_MASTER_IS_NOT_FULL_AUTHORIZATION')
    need(review['schema']=='FULL_LABEL_PROJECTION_ROOT_REVIEW_V1' and review['status']=='ROOT_APPROVED_FULL_SOURCE_CACHE'
      and review['reviewer']=='root' and bool(review['reason'].strip()),'INDEPENDENT_EXPLICIT_ROOT_FULL_REVIEW')
    need(review['master_reference']==master_reference
      and review['bounded_evidence_references']==master['bounded_evidence_references'],'REVIEW_BINDS_ACTUAL_BOUNDED_EVIDENCE')
    need(review['bounded_C0_parity_and_cost_accepted'] is True and review['Sprime_reservations_released_or_fully_accounted'] is True,
      'ACTUAL_BOUNDED_C0_PARITY_COST_AND_SPRIME_STORAGE_REVIEW')
    for key in ('storage_review_reference','Sprime_reservation_closure_reference','resource_authority_reference'):
        need(isinstance(review[key],dict) and set(('path','bytes','sha256'))<=set(review[key]),'ACTUAL_REVIEW_PIN_REQUIRED:'+key)
    need(type(review['approved_whole_cache_cap_bytes']) is int and review['approved_whole_cache_cap_bytes']>0
      and type(review['approved_whole_cache_inode_cap']) is int and review['approved_whole_cache_inode_cap']>0,'ROOT_SUPPLIED_CAP_NOT_LINEAR_FORECAST')
    need(type(review['other_storage_scope_unwritten_cap_upper_bound_bytes']) is int
      and review['other_storage_scope_unwritten_cap_upper_bound_bytes']>=0,'ALL_OTHER_PENDING_STORAGE_UPPER_BOUND_REQUIRED')
    need(review['quota_reserve_bytes']==200000000000 and review['final_common_D4_authorized'] is False
      and review['final_masks_authorized'] is False,'NO_QUOTA_MASK_OR_NORM_EXCEPTION')
    return review


class DispatchBook:
    """Persistent exclusive dispatch intent. UNKNOWN is never automatically freed.

    This is the cross-allocation authority. The frozen bounded Ledger remains
    the independent in-allocation ticket/atomic-part authority.
    """
    def __init__(self,path,create=False,*,files=(),cap=None,inodes=None,master_reference=None,review_reference=None):
        self.db=sqlite3.connect(path,timeout=120,isolation_level=None)
        self.db.execute('PRAGMA busy_timeout=120000');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA cache_size=-4096');self.db.execute('PRAGMA max_page_count=16384')
        if create:
            self.db.executescript('''PRAGMA journal_mode=DELETE;
            CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
            CREATE TABLE source(file_id INTEGER PRIMARY KEY,cursor INTEGER,stop INTEGER,lease TEXT);
            CREATE TABLE batch(name TEXT PRIMARY KEY,state TEXT,cap INTEGER,inodes INTEGER,config TEXT,receipt TEXT);
            CREATE TABLE assignment(name TEXT,file_id INTEGER,lo INTEGER,hi INTEGER,PRIMARY KEY(name,file_id));''')
            for key,value in (('master',master_reference),('review',review_reference),('cap',cap),('inodes',inodes)):
                self.db.execute('INSERT INTO meta VALUES(?,?)',(key,json.dumps(value,sort_keys=True)))
            self.db.executemany('INSERT INTO source VALUES(?,0,?,NULL)',[(r['file_id'],r['rows']) for r in files])

    def close(self):self.db.close()

    def metadata(self):return {k:json.loads(v) for k,v in self.db.execute('SELECT key,value FROM meta')}

    def pending(self,partition):
        out=[]
        for fid in partition['file_ids']:
            row=self.db.execute('SELECT cursor,stop,lease FROM source WHERE file_id=?',(fid,)).fetchone()
            need(row is not None,'SOURCE_IN_FROZEN_MASTER')
            if row[0]<row[1] and row[2] is None:out.append({'file_id':fid,'physical_row_lo':row[0],'physical_row_hi':row[1]})
        return out

    def claim(self,name,selectors,cap,inodes,config_reference):
        need(type(cap) is int and cap>0 and type(inodes) is int and inodes>0 and selectors,'POSITIVE_BOUNDED_BATCH_TICKET')
        need(len({r['file_id'] for r in selectors})==len(selectors),'ONE_RANGE_PER_SOURCE_IN_NEW_BATCH')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            need(self.db.execute("SELECT count(*) FROM batch WHERE state<>'ACTUAL_C0_CLOSED'").fetchone()[0]==0,
              'ROOT_SERIAL_BATCH_CHAIN_NO_NEW_JOB_BEFORE_ACTUAL_ACCEPT')
            meta=self.metadata();used,used_inodes=self.db.execute('SELECT coalesce(sum(cap),0),coalesce(sum(inodes),0) FROM batch').fetchone()
            need(used+cap<=meta['cap'] and used_inodes+inodes<=meta['inodes'],'FULL_CUMULATIVE_CAP_INCLUDING_UNKNOWN_AND_ACTIVE')
            self.db.execute('INSERT INTO batch VALUES(?,?,?,?,?,NULL)',(name,'DISPATCH_INTENT',cap,inodes,json.dumps(config_reference,sort_keys=True)))
            for s in selectors:
                current=self.db.execute('SELECT cursor,stop,lease FROM source WHERE file_id=?',(s['file_id'],)).fetchone()
                need(current is not None and current[2] is None and current[0]==s['physical_row_lo']<s['physical_row_hi']<=current[1],
                  'EXCLUSIVE_SOURCE_LEASE_AT_ACTUAL_CLOSED_CURSOR')
                self.db.execute('INSERT INTO assignment VALUES(?,?,?,?)',(name,s['file_id'],s['physical_row_lo'],s['physical_row_hi']))
                self.db.execute('UPDATE source SET lease=? WHERE file_id=?',(name,s['file_id']))
            self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise

    def assert_claim(self,name,config_reference,selectors):
        row=self.db.execute('SELECT state,config FROM batch WHERE name=?',(name,)).fetchone()
        need(row is not None and row[0]=='DISPATCH_INTENT' and json.loads(row[1])==config_reference,'EXACT_UNCONSUMED_BATCH_INTENT')
        actual=[{'file_id':fid,'physical_row_lo':lo,'physical_row_hi':hi} for fid,lo,hi in
          self.db.execute('SELECT file_id,lo,hi FROM assignment WHERE name=? ORDER BY file_id',(name,))]
        need(actual==sorted(selectors,key=lambda r:r['file_id']),'EXACT_DISPATCH_SOURCE_RANGE_SET')

    def accept(self,name,config_reference,cursors,receipt,actual_bytes,actual_inodes):
        """Caller must first validate actual C0 + all closed-receipt hashes.

        Incomplete cursor is legal; omitted files, UNKNOWN tickets, quality HOLD
        and failed jobs are not legal caller inputs. No second dispatch here.
        """
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT state,cap,inodes,config FROM batch WHERE name=?',(name,)).fetchone()
            need(row is not None and row[0]=='RUNNING' and json.loads(row[3])==config_reference,'ONE_ACTUAL_BATCH_ACCEPT')
            need(0<actual_bytes<=row[1] and 0<actual_inodes<=row[2],'ACTUAL_OUTPUT_WITHIN_PRECLAIMED_FULL_TICKET')
            expected={fid:(lo,hi) for fid,lo,hi in self.db.execute('SELECT file_id,lo,hi FROM assignment WHERE name=?',(name,))}
            need(len(cursors)==len(expected) and {r['file_id'] for r in cursors}==set(expected),'ALL_LEASED_SOURCE_CURSORS_REQUIRED')
            for c in cursors:
                lo,hi=expected[c['file_id']];position=c['next_physical_row']
                current=self.db.execute('SELECT cursor,stop,lease FROM source WHERE file_id=?',(c['file_id'],)).fetchone()
                need(current[0]==lo and current[2]==name and lo<=position<=hi,'MONOTONE_EXACT_SOURCE_CURSOR')
                self.db.execute('UPDATE source SET cursor=?,lease=NULL WHERE file_id=?',(position,c['file_id']))
            self.db.execute('UPDATE batch SET state=?,cap=?,inodes=?,receipt=? WHERE name=?',
              ('ACTUAL_C0_CLOSED',actual_bytes,actual_inodes,json.dumps(receipt,sort_keys=True),name))
            self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise

    def running(self,name):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            cur=self.db.execute("UPDATE batch SET state='RUNNING' WHERE name=? AND state='DISPATCH_INTENT'",(name,))
            need(cur.rowcount==1,'ONCE_ONLY_CPU_BATCH_DISPATCH');self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise

    def snapshot(self):
        return {'metadata':self.metadata(),'sources':[{'file_id':i,'next_physical_row':c,'physical_row_hi':e,'lease':l}
          for i,c,e,l in self.db.execute('SELECT * FROM source ORDER BY file_id')],
          'batches':[{'name':n,'state':s,'charged_bytes':b,'charged_inodes':i,'config_reference':json.loads(c),
            'receipt':json.loads(r) if r else None} for n,s,b,i,c,r in self.db.execute('SELECT * FROM batch ORDER BY name')]}
