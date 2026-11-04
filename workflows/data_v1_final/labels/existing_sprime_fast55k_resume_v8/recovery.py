"""Only existing derived SQLite state is continued; original raw inputs stay readonly."""
import ast,hashlib,inspect,json,pathlib,sqlite3,struct,sys
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import geometry as ORIGINAL
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I

TABLES=('base','children','input_views','bindings','seen','unknown')

def transformed_source():
    source=inspect.getsource(ORIGINAL.metadata_children);changed=source;edits=[]
    def replace(old,new):
        nonlocal changed
        C.need(changed.count(old)==1,'ONE_EXACT_METADATA_RECOVERY_LITERAL')
        changed=changed.replace(old,new,1);edits.append((old,new))
    replace('root=pathlib.Path(root);root.mkdir();review=',
            'root=pathlib.Path(root);root.mkdir(exist_ok=True);review=')
    lo=changed.index("    db=sqlite3.connect(root/'geometry.sqlite');")
    hi=changed.index('    selected_catalog=',lo)
    replace(changed[lo:hi],
      '    recovery=Recovery(plan,proof,root,budget,base_result,Wire,RECOVERY_LOOKUP_CONTEXT)\n'
      '    db=recovery.open()\n')
    replace('canonical=sqlite_ro(I.require(plan[\'canonical_index\']));unknown_uuid=0;observations=[];columns=list(Child.COLUMNS)',
      'canonical=sqlite_ro(I.require(plan[\'canonical_index\']));unknown_uuid=recovery.unknown_uuid;observations=[];columns=list(Child.COLUMNS)\n'
      '    recovery.bind_sources(selected)')
    replace('stream.seek(0);parquet=pq.ParquetFile(stream,pre_buffer=False);position=0',
      'stream.seek(0);parquet=pq.ParquetFile(stream,pre_buffer=False);position=recovery.start_position(source)')
    replace('for batch in parquet.iter_batches(batch_size=256,columns=columns,use_threads=False):',
      'for batch in recovery.batches(parquet,source,columns):')
    replace("        db.commit();db.close();db=None;binding_ref=I.allow(I.pin(root/'geometry.sqlite'))",
      "        recovery.finish(db)\n        db.commit();db.close();db=None;binding_ref=I.allow(I.pin(root/'geometry.sqlite'))")
    replace("        result['manifest_reference']=I.save(root/'manifest.json',result);return result",
      "        result['metadata_checkpoint_recovery_reference']=recovery.report_reference\n"
      "        result['manifest_reference']=I.save(root/'manifest.json',result);return result")
    restored=changed
    for old,new in reversed(edits):
        C.need(restored.count(new)==1,'UNIQUE_METADATA_RESOURCE_INVERSE')
        restored=restored.replace(new,old,1)
    C.need(restored==source,'ENTIRE_ORIGINAL_METADATA_TEXT_RESOURCE_INVERSE')
    ast.parse(changed)
    return changed,dict(entire_original_metadata_source_restored=True,
      original_renderer_child_input_hash_and_quality_block_unchanged=True,
      only_checkpoint_initialization_cursor_and_integrity_changes=True,
      original_sha256=hashlib.sha256(source.encode()).hexdigest(),
      continued_sha256=hashlib.sha256(changed.encode()).hexdigest(),literal_changes=len(edits))

def schema_sql():
    tree=ast.parse(inspect.getsource(ORIGINAL.metadata_children))
    calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)
      and isinstance(n.func,ast.Attribute) and n.func.attr=='executescript']
    C.need(len(calls)==1,'ONE_ORIGINAL_SQLITE_SCHEMA')
    return ast.literal_eval(calls[0].args[0])

def _digest_row(digest,row):
    for value in row:
        if value is None:kind,raw=b'N',b''
        elif type(value) is bytes:kind,raw=b'B',value
        elif type(value) is str:kind,raw=b'S',value.encode()
        elif type(value) is int:kind,raw=b'I',str(value).encode()
        elif type(value) is float:kind,raw=b'F',struct.pack('<d',value)
        else:raise ValueError('UNEXPECTED_SQLITE_CHECKPOINT_VALUE')
        digest.update(kind+struct.pack('<Q',len(raw))+raw)

def table_snapshot(db,table,maximum,budget,decode=None):
    digest=hashlib.sha256();count=0;uuid_unknown=0
    for row in db.execute('SELECT rowid,* FROM '+table+' WHERE rowid<=? ORDER BY rowid',(maximum,)):
        _digest_row(digest,row);count+=1
        if decode is not None:
            value=decode(row[-1]);origin=json.loads(value['source_provenance_json'])
            state=origin['original_execution_uuid_state']
            C.need(state in ('ACTUAL_STORED_RAW_LOCATOR','UNKNOWN_NOT_RETAINED'),'ACTUAL_PREFIX_UUID_STATE')
            uuid_unknown+=state=='UNKNOWN_NOT_RETAINED'
        if count%4096==0:budget.check()
    return dict(rows=count,maximum_rowid=maximum,sha256=digest.hexdigest()),uuid_unknown

class Recovery:
    def __init__(self,plan,proof,root,budget,base,codec,context):
        self.plan=plan;self.proof=proof;self.root=root;self.budget=budget
        self.base=base;self.codec=codec;self.context=context
        self.review=C.meta(plan['metadata_recovery_reference']);self.unknown_uuid=0
        self.before={};self.binding_order=[];self.binding_last={}
    def open(self):
        path=self.root/'geometry.sqlite';expected=self.review['staged_checkpoint_file']
        s=path.lstat()
        C.need(s.st_uid==1278 and s.st_nlink==1 and s.st_size==expected['size']
          and s.st_ino==expected['inode'],'EXACT_ROOT_STAGED_CLOSED5455_CHECKPOINT')
        self.db=sqlite3.connect(path,factory=self.context.factory)
        wanted=sqlite3.connect(':memory:');wanted.executescript(schema_sql())
        schema=lambda db:db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').fetchall()
        C.need(schema(self.db)==schema(wanted),'EXACT_ORIGINAL_CHECKPOINT_SCHEMA_NO_NEW_TABLES');wanted.close()
        C.need(self.db.execute('SELECT count(*) FROM unknown').fetchone()[0]==0,
          'ORIGINAL_UNKNOWN_INPUT_BINDINGS_REMAIN_HOLD_NOT_RETRIED')
        counts=[self.db.execute('SELECT count(*) FROM '+name).fetchone()[0]
                for name in ('bindings','seen','children','input_views')]
        C.need(counts[0]==counts[1]==counts[2]+counts[3], 'CLOSED_ATOMIC_PREFIX_BINDING_MASS')
        C.need(self.db.execute('SELECT 1 FROM seen s LEFT JOIN bindings b ON s.rid=b.rid AND s.task=b.task WHERE b.rid IS NULL LIMIT 1').fetchone() is None,
          'EVERY_OLD_SEEN_ROW_HAS_COMMITTED_BINDING')
        for table in TABLES:
            maximum=self.db.execute('SELECT coalesce(max(rowid),0) FROM '+table).fetchone()[0]
            before,missing=table_snapshot(self.db,table,maximum,self.budget,
                self.codec.decode if table in ('children','input_views') else None)
            self.before[table]=before;self.unknown_uuid+=missing
        import pyarrow.parquet as pq
        total=0
        for batch in pq.ParquetFile(I.require(self.base['table_references']['geometries'])).iter_batches(batch_size=512,use_threads=False):
            self.budget.check()
            for value in batch.to_pylist():
                row=sqlite3.Connection.execute(self.db,'SELECT gid,mid,rid,src,row FROM base WHERE gid=?',(value['geometry_id'],)).fetchone()
                expected=(value['geometry_id'],value['molecule_id'],value['native_record_id'],value['geometry_source'],self.codec.encode(value))
                C.need(row==expected,'EVERY_ORIGINAL_F64_BASE_ROW_EXACT_IN_CHECKPOINT');total+=1
                if row[3]=='pm7':
                    rid,raw=row[2],row[4];self.context.rids.add(rid)
                    size=sys.getsizeof(rid)+sys.getsizeof(raw)+160
                    if self.context.blob_bytes+size<=self.context.cap:
                        self.context.blobs[rid]=raw;self.context.blob_bytes+=size;self.context.approved_raw.add(raw)
        C.need(total==self.before['base']['rows'],'ALL_AND_ONLY_ORIGINAL_BASE_ROWS')
        for source,position in self.db.execute('SELECT source,physical_row FROM bindings ORDER BY rowid'):
            if not self.binding_order or source!=self.binding_order[-1]:
                C.need(source not in self.binding_last,'ONE_CONTIGUOUS_SOURCE_PREFIX_BLOCK')
                self.binding_order.append(source);self.binding_last[source]=-1
            C.need(type(position) is int and position>self.binding_last[source],'STRICT_ORIGINAL_SOURCE_ROW_ORDER')
            self.binding_last[source]=position
        C.need(self.binding_order,'NONEMPTY_CLOSED_METADATA_CHECKPOINT')
        I.save(self.root/'old_prefix_logical_snapshot.json',dict(old_job_id='4525455',tables=self.before,
          original_UUID_unknown=self.unknown_uuid,old_values_not_modified=True))
        return self.db
    def bind_sources(self,selected):
        self.sources=selected
        keys=[json.dumps(C.reference(s),sort_keys=True) for s in selected]
        positions={key:index for index,key in enumerate(keys)}
        C.need(all(key in positions for key in self.binding_order),'EXACT_ORIGINAL_SELECTED_SOURCE_REFERENCES')
        order=[positions[key] for key in self.binding_order]
        C.need(order==sorted(order),'CLOSED_SOURCE_SCAN_ORDER_NOT_GUESSED')
        self.last_source=order[-1];self.last_row=self.binding_last[self.binding_order[-1]]+1
        C.need(0<self.last_row<=selected[self.last_source]['rows'],'CONSERVATIVE_COMMITTED_ROW_CURSOR')
        self.source_positions=positions
    def start_position(self,source):
        index=self.source_positions[json.dumps(C.reference(source),sort_keys=True)]
        return source['rows'] if index<self.last_source else self.last_row if index==self.last_source else 0
    def batches(self,parquet,source,columns):
        start=self.start_position(source)
        if start==source['rows']:return
        offset=0;first=0
        while first<parquet.num_row_groups and offset+parquet.metadata.row_group(first).num_rows<=start:
            offset+=parquet.metadata.row_group(first).num_rows;first+=1
        drop=start-offset
        for batch in parquet.iter_batches(batch_size=256,row_groups=list(range(first,parquet.num_row_groups)),columns=columns,use_threads=False):
            if drop>=batch.num_rows:drop-=batch.num_rows;continue
            if drop:batch=batch.slice(drop);drop=0
            yield batch
        C.need(drop==0,'EXACT_RESUMED_PHYSICAL_ROW_OFFSETS')
    def finish(self,db):
        after={}
        for table,expected in self.before.items():
            actual,_=table_snapshot(db,table,expected['maximum_rowid'],self.budget)
            C.need(actual==expected,'ALL_OLD_LOGICAL_CHECKPOINT_ROWS_UNCHANGED:'+table);after[table]=actual
        self.report_reference=I.save(self.root/'checkpoint_resume_integrity.json',dict(
          schema='ACTUAL5455_APPEND_ONLY_METADATA_RECOVERY_INTEGRITY_V1',old_job_id='4525455',
          actual_new_job_id=str(self.proof['job_id']),recovery_review_reference=self.plan['metadata_recovery_reference'],
          all_old_logical_rows_equal_before_after=True,before=self.before,after=after,
          resumed_source_index=self.last_source+1,resumed_physical_row=self.last_row,
          prefix_and_suffix_all_sources_covered=True,no_original_raw_or_LMDB_written=True,
          no_QM_UFF_or_failed_input_retries=True))
