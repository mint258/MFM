"""Reuse actual completed5478 base/prefix proof; inspect only its newly closed tail."""
import hashlib,json,sqlite3,sys
from . import contract as C
from .resource import SafeIO
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v8 import recovery as OLD
I=SafeIO();TABLES=OLD.TABLES

def suffix_snapshot(db,table,lower,upper,budget,decode=None):
    digest=hashlib.sha256();count=0;missing=0
    for row in db.execute('SELECT rowid,* FROM '+table+' WHERE rowid>? AND rowid<=? ORDER BY rowid',(lower,upper)):
        OLD._digest_row(digest,row);count+=1
        if decode is not None:
            state=json.loads(decode(row[-1])['source_provenance_json'])['original_execution_uuid_state']
            C.need(state in ('ACTUAL_STORED_RAW_LOCATOR','UNKNOWN_NOT_RETAINED'),'UNCHANGED_ACTUAL_UUID_STATE')
            missing+=state=='UNKNOWN_NOT_RETAINED'
        if count%4096==0:budget.check()
    return dict(rows=count,lower_rowid_exclusive=lower,maximum_rowid=upper,sha256=digest.hexdigest()),missing

class Recovery(OLD.Recovery):
    def open(self):
        path=self.root/'geometry.sqlite';expected=self.review['staged_checkpoint_file'];s=path.lstat()
        C.need(s.st_uid==1278 and s.st_nlink==1 and s.st_size==expected['size'] and s.st_ino==expected['inode'],
          'EXACT_ROOT_STAGED_CLOSED5478_CHECKPOINT')
        snapshot=C.meta(self.review['prior_closed_prefix_snapshot_reference'])
        C.need(snapshot['old_job_id']=='4525455' and snapshot['old_values_not_modified'] is True,
          'ACTUAL5478_COMPLETED_OLD_PREFIX_SNAPSHOT_NOT_WHOLE_D4')
        self.certified=snapshot['tables'];self.unknown_uuid=snapshot['original_UUID_unknown']
        self.db=sqlite3.connect(path,factory=self.context.factory)
        wanted=sqlite3.connect(':memory:');wanted.executescript(OLD.schema_sql())
        schema=lambda db:db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').fetchall()
        C.need(schema(self.db)==schema(wanted),'EXACT_ORIGINAL_SCHEMA_NO_NEW_TABLES_OR_TRIGGERS');wanted.close()
        C.need(self.db.execute('SELECT count(*) FROM unknown').fetchone()[0]==0,
          'ORIGINAL_UNKNOWN_BINDINGS_REMAIN_HOLD_NOT_RETRIED')
        counts={name:self.db.execute('SELECT count(*) FROM '+name).fetchone()[0] for name in TABLES}
        C.need(counts['bindings']==counts['seen']==counts['children']+counts['input_views'],
          'CLOSED_ATOMIC_PREFIX_BINDING_MASS')
        C.need(counts['base']==self.certified['base']['rows'],'ALL_AND_ONLY_ALREADY_CPU_F64_VERIFIED_BASE_ROWS')
        for table in TABLES:
            old=self.certified[table];maximum=self.db.execute('SELECT coalesce(max(rowid),0) FROM '+table).fetchone()[0]
            C.need(maximum>=old['maximum_rowid'],'CERTIFIED_PREFIX_NOT_TRUNCATED')
            tail,missing=suffix_snapshot(self.db,table,old['maximum_rowid'],maximum,self.budget,
              self.codec.decode if table in ('children','input_views') else None)
            C.need(old['rows']+tail['rows']==counts[table],'CERTIFIED_PREFIX_PLUS_ALL_CURRENT_TAIL_ROWS')
            self.before[table]=tail;self.unknown_uuid+=missing
        # These exact base bytes were fully compared with the closed F64 tables
        # in5478. Original append-only suffix never writes base; final old-prefix
        # hashes below still independently verify that certification at close.
        for rid,raw in self.db.execute("SELECT rid,row FROM base WHERE src='pm7' ORDER BY rowid"):
            self.context.rids.add(rid);size=sys.getsizeof(rid)+sys.getsizeof(raw)+160
            if self.context.blob_bytes+size<=self.context.cap:
                self.context.blobs[rid]=raw;self.context.blob_bytes+=size;self.context.approved_raw.add(raw)
            if len(self.context.rids)%4096==0:self.budget.check()
        for source,position in self.db.execute('SELECT source,physical_row FROM bindings ORDER BY rowid'):
            if not self.binding_order or source!=self.binding_order[-1]:
                C.need(source not in self.binding_last,'ONE_CONTIGUOUS_SOURCE_PREFIX_BLOCK')
                self.binding_order.append(source);self.binding_last[source]=-1
            C.need(type(position)is int and position>self.binding_last[source],'STRICT_ORIGINAL_SOURCE_ROW_ORDER')
            self.binding_last[source]=position
        C.need(self.binding_order,'NONEMPTY_CLOSED_METADATA_CHECKPOINT')
        I.save(self.root/'reused_prefix_and_new_tail_snapshot.json',dict(old_job_id='4525478',
          certified_prefix_reference=self.review['prior_closed_prefix_snapshot_reference'],
          certified_prefix=self.certified,newly_closed_tail=self.before,original_UUID_unknown=self.unknown_uuid,
          full_base_F64_check_reused_from_actual5478=True,no_new_QM_UFF_calls=True))
        return self.db
    def finish(self,db):
        after={}
        for table,expected in self.certified.items():
            actual,_=OLD.table_snapshot(db,table,expected['maximum_rowid'],self.budget)
            C.need(actual==expected,'CERTIFIED5478_OLD_PREFIX_UNCHANGED:'+table)
            tail=self.before[table];actual_tail,_=suffix_snapshot(db,table,tail['lower_rowid_exclusive'],tail['maximum_rowid'],self.budget)
            C.need(actual_tail==tail,'ALL_NEWLY_CLOSED5478_TAIL_ROWS_UNCHANGED:'+table)
            after[table]=dict(certified_prefix=actual,newly_closed_tail=actual_tail)
        self.report_reference=I.save(self.root/'checkpoint_resume_integrity.json',dict(
          schema='ACTUAL5478_APPEND_ONLY_METADATA_RECOVERY_INTEGRITY_V1',old_job_id='4525478',
          actual_new_job_id=str(self.proof['job_id']),recovery_review_reference=self.plan['metadata_recovery_reference'],
          actual_prior_prefix_snapshot_reference=self.review['prior_closed_prefix_snapshot_reference'],
          all_old_logical_rows_equal_before_after=True,after=after,
          resumed_source_index=self.last_source+1,resumed_physical_row=self.last_row,
          prefix_and_suffix_all_sources_covered=True,no_original_raw_or_LMDB_written=True,
          no_QM_UFF_or_failed_input_retries=True,completed_base_F64_check_not_repeated=True))
