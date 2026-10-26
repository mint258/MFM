"""Profile/full physical SQL COPY inventory, with identity-only raw projections.

No SQL dump is executed/imported. SQLite below stores only our selected fields;
RDKit normalization belongs to a separately profiled later stage.
"""
import argparse,hashlib,io,json,os,re,sqlite3,stat,tempfile,threading,time,traceback,unittest
from collections import Counter
from pathlib import Path
from secondary_coconut_sql_inventory_v1 import probe as frozen_probe
from . import contracts as c,copy_text

SELECT={
 'molecules':('id','identifier','canonical_smiles','standard_inchi','standard_inchi_key','parent_id','status','active',
              'has_variants','has_stereo','is_tautomer','is_parent','is_placeholder','is_duplicate','has_issues'),
 'entries':('id','canonical_smiles','standardized_canonical_smiles','parent_canonical_smiles','molecule_id','collection_id','status','is_invalid'),
 'structures':('id','molecule_id'),
 'properties':('id','molecule_id','molecular_formula'),
 'collections':('id','identifier','status'),
 'collection_molecule':('id','collection_id','molecule_id'),
 'molecule_related':('id','molecule_id','related_id','type')}

class Sink:
    def __init__(self,root,checkpoint=lambda:None):
        import pyarrow as pa
        self.root=root;self.writers={};self.buffers={};self.buffer_bytes={};self.counts=Counter();self.checkpoint=checkpoint
        self.schema=pa.schema([('source_table',pa.string()),('copy_block',pa.int64()),('source_row_ordinal',pa.int64()),
            ('source_offset',pa.int64()),('source_bytes',pa.int64()),('source_row_sha256',pa.string()),('identity_fields_json',pa.string())])
        scratch=root/'sqlite_tmp';scratch.mkdir();os.environ['SQLITE_TMPDIR']=str(scratch)
        self.db=sqlite3.connect(root/'identity_inventory.sqlite')
        self.db.execute('PRAGMA journal_mode=DELETE');self.db.execute('PRAGMA cache_size=-65536');self.db.execute('PRAGMA temp_store=FILE')
        self.db.execute('PRAGMA temp_store_directory='+"'"+str(scratch).replace("'","''")+"'")
        self.db.execute('CREATE TABLE records(source_table TEXT,copy_block INTEGER,row_ordinal INTEGER,id TEXT,molecule_id TEXT,parent_id TEXT,collection_id TEXT,related_id TEXT,status TEXT,active TEXT,is_invalid TEXT,identity_fields_json TEXT,PRIMARY KEY(source_table,copy_block,row_ordinal))')

    def add(self,table,block,ordinal,row,fields):
        c.need(table in SELECT and set(fields)==set(SELECT[table]),'ONLY_EXACT_IDENTITY_STATE_LINK_FIELDS_ALLOWED')
        encoded=json.dumps(fields,ensure_ascii=False,separators=(',',':'),allow_nan=False)
        record={'source_table':table,'copy_block':block,'source_row_ordinal':ordinal,'source_offset':row['offset'],
            'source_bytes':row['bytes'],'source_row_sha256':row['row_sha256'],'identity_fields_json':encoded}
        self.buffers.setdefault(table,[]).append(record);self.buffer_bytes[table]=self.buffer_bytes.get(table,0)+len(encoded.encode())
        self.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            [table,block,ordinal,*[fields.get(k) for k in ('id','molecule_id','parent_id','collection_id','related_id','status','active','is_invalid')],encoded])
        self.counts[table]+=1
        if len(self.buffers[table])>=4096 or self.buffer_bytes[table]>=16*1024**2:self.flush(table)

    def flush(self,table):
        import pyarrow as pa
        import pyarrow.parquet as pq
        rows=self.buffers.get(table,[])
        if not rows:return
        if table not in self.writers:self.writers[table]=pq.ParquetWriter(self.root/(table+'.raw_identity.parquet'),self.schema,compression='zstd')
        self.writers[table].write_table(pa.Table.from_pylist(rows,schema=self.schema));self.buffers[table]=[];self.buffer_bytes[table]=0
        self.db.commit()
        self.checkpoint()

    def close(self):
        for table in list(self.buffers):self.flush(table)
        for writer in self.writers.values():writer.close()
        self.db.commit()

    def reconcile(self,complete):
        self.checkpoint();db=self.db;db.execute('CREATE INDEX ids ON records(source_table,id)');self.checkpoint()
        rows=dict(db.execute('SELECT source_table,count(*) FROM records GROUP BY source_table').fetchall())
        c.need(rows==dict(self.counts),'SQLITE_PARQUET_PROJECTED_ROW_CONSERVATION')
        duplicates=db.execute('SELECT count(*) FROM (SELECT source_table,id FROM records WHERE id IS NOT NULL GROUP BY source_table,id HAVING count(*)>1)').fetchone()[0]
        nullids=db.execute('SELECT count(*) FROM records WHERE id IS NULL').fetchone()[0]
        links=[]
        for table,column,parent in [('structures','molecule_id','molecules'),('entries','molecule_id','molecules'),
            ('properties','molecule_id','molecules'),('collection_molecule','molecule_id','molecules'),
            ('collection_molecule','collection_id','collections'),('molecule_related','molecule_id','molecules'),
            ('molecule_related','related_id','molecules'),('molecules','parent_id','molecules')]:
            self.checkpoint()
            missing=db.execute('SELECT count(*) FROM records r WHERE r.source_table=? AND r.'+column+' IS NOT NULL AND NOT EXISTS (SELECT 1 FROM records p WHERE p.source_table=? AND p.id=r.'+column+')',[table,parent]).fetchone()[0]
            nulls=db.execute('SELECT count(*) FROM records WHERE source_table=? AND '+column+' IS NULL',[table]).fetchone()[0]
            links.append({'table':table,'column':column,'parent_table':parent,'unmatched_nonnull':missing,'null':nulls,
                          'whole_source_link_scope_complete':complete})
        count=0
        with (self.root/'status_counts.jsonl').open('xb') as out:
            for row in db.execute('SELECT source_table,status,active,is_invalid,count(*) FROM records GROUP BY source_table,status,active,is_invalid'):
                out.write((json.dumps(dict(zip(('table','status','active','is_invalid','records'),row)),ensure_ascii=False)+'\n').encode());count+=1
            out.flush();os.fsync(out.fileno())
        return {'projected_rows_by_table':rows,'duplicate_nonnull_ID_groups':duplicates,'null_ID_records':nullids,
            'link_observations':links,'status_groups':count,'no_status_or_invalid_class_filtered':True,
            'UNKNOWN_preserved_not_dropped':bool(duplicates or nullids or any(x['unmatched_nonnull'] for x in links))}


def header(statement,schemas):
    observed=frozen_probe.inspect_prefix(statement+b'\n')
    c.need(not observed['insert_headers'],'UNSUPPORTED_INSERT_DATA_LAYOUT_STOP_UNKNOWN')
    if not observed['copy_headers']:return None
    c.need(len(observed['copy_headers'])==1 and not observed['unsupported_COPY_headers'],'UNKNOWN_COPY_HEADER')
    value=observed['copy_headers'][0];table=value['table_identifiers']
    c.need(table and table[0]=='public' and len(table)==2 and table[1] in schemas and value['FROM_STDIN'] and not value['header_truncated'],
           'UNKNOWN_COPY_TABLE_OR_LAYOUT')
    c.need(re.fullmatch(rb'\s*COPY\s+.+?\s*\(.*?\)\s+FROM\s+stdin\s*;\s*',statement,re.S|re.I) is not None,
           'ONLY_OBSERVED_DEFAULT_TEXT_STDIN_COPY_SUPPORTED')
    cols=value['columns'];c.need(len(cols)==len(set(cols)) and set(cols)==set(schemas[table[1]]),'COPY_SCHEMA_WIDTH_OR_COLUMNS_DIFFER')
    return table[1],cols


def inventory(stream,plan,schema,sink,checkpoint,progress):
    reader=copy_text.Input(stream,checkpoint);metadata=copy_text.Metadata();schemas={t['table_identifiers'][-1]:[x['name'] for x in t['columns']] for t in schema['tables']}
    blocks=Counter();counts=Counter(dict.fromkeys(schemas,0));endings=Counter();ddl_seen=set();profile=plan['mode']=='profile';limit=plan['scope_parameters']['profile_limit_bytes'];stopped=False
    if profile:reader.maximum_consumed=limit+plan['scope_parameters']['maximum_profile_boundary_overshoot_bytes']
    while True:
        checkpoint();line=reader.line()
        if not line:break
        for statement in metadata.feed(line):
            observed=frozen_probe.inspect_prefix(statement+b'\n')
            for t in observed['tables']:
                table=t['table_identifiers'];c.need(len(table)==2 and table[0]=='public' and table[1] in schemas and
                    [x['name'] for x in t['columns']]==schemas[table[1]],'UNEXPECTED_FULL_SQL_DDL_SCHEMA');ddl_seen.add(table[1])
            c.need(not observed['unsupported_or_incomplete_CREATE_headers'],'UNSUPPORTED_SQL_DDL_LAYOUT')
            item=header(statement,schemas)
            if item is None:
                # INSERT/UPDATE/DELETE/MERGE cannot be silently treated as metadata.
                c.need(not re.match(rb'\s*(INSERT|UPDATE|DELETE|MERGE)\b',statement,re.I),'UNSUPPORTED_DATA_STATEMENT_STOP_UNKNOWN')
                continue
            table,columns=item;blocks[table]+=1;block=blocks[table];wanted={i:col for i,col in enumerate(columns) if col in SELECT.get(table,())};ordinal=0
            c.need(all(name in columns for name in SELECT.get(table,())),'REQUIRED_IDENTITY_COLUMN_ABSENT')
            while True:
                checkpoint();row_start=reader.consumed
                try:row=copy_text.row(reader,len(columns),wanted,plan['scope_parameters']['maximum_selected_field_bytes'])
                except Exception as exc:
                    exc.add_note(json.dumps({'source_table':table,'COPY_block':block,'next_logical_row':ordinal+1,
                        'record_start_offset':row_start,'consumed_before_failure':reader.consumed}))
                    raise
                endings[row['ending']]+=1
                if row['end']:break
                ordinal+=1;counts[table]+=1
                if wanted:sink.add(table,block,ordinal,row,{name:row['fields'][i] for i,name in wanted.items()})
                if ordinal%10000==0:progress({'table':table,'block':block,'complete_rows':ordinal,'consumed_bytes':reader.consumed})
                if profile:c.need(reader.consumed<=limit+plan['scope_parameters']['maximum_profile_boundary_overshoot_bytes'],'PROFILE_BOUNDARY_OVERSHOOT_STOP_UNKNOWN')
                if profile and reader.consumed>=limit:stopped=True;break
            progress({'table':table,'block':block,'complete_rows':ordinal,'COPY_end_marker_seen':not stopped,'consumed_bytes':reader.consumed})
            if stopped:break
        if stopped:break
    sink.close()
    complete=not profile and reader.eof and metadata.complete()
    if not profile:
        c.need(complete and reader.consumed==reader.read_bytes==c.base.SQL_BYTES and reader.sha.hexdigest()==plan['data_references'][0]['sha256'],
               'FULL_SQL_EOF_BYTES_CURRENT_SHA_OR_STATEMENT_INCOMPLETE')
        c.need(ddl_seen==set(schemas),'FULL_SOURCE_DDL_TABLE_SCOPE_INCOMPLETE')
        c.need(b'-- PostgreSQL database dump complete' in reader.tail,'FULL_DUMP_TAIL_MARKER_ABSENT')
    else:c.need(stopped,'BOUNDED_PROFILE_DID_NOT_STOP_AT_A_COMPLETE_RECORD')
    c.need(len(endings)<=1,'MIXED_UNESCAPED_COPY_RECORD_LINE_ENDINGS')
    c.need(len(reader.prefix)==schema['actual_prefix_bytes'] and hashlib.sha256(reader.prefix).hexdigest()==schema['actual_prefix_sha256'],
           'ACTUAL1884767_PREFIX_CHANGED')
    reconciliation=sink.reconcile(complete)
    for table,n in sink.counts.items():c.need(n==counts[table],'PROJECTED_COPY_RECORD_CONSERVATION')
    return {'mode':plan['mode'],'physical_COPY_rows_by_table':dict(counts),'COPY_blocks_by_table':dict(blocks),
        'DDL_tables_seen':sorted(ddl_seen),'source_bytes_consumed_at_record_boundary':reader.consumed,'source_bytes_read_including_read_ahead':reader.read_bytes,
        'tables_without_physical_COPY_blocks':sorted(set(schemas)-set(blocks)),
        'read_ahead_bytes':reader.read_bytes-reader.consumed,'read_region_SHA256':reader.sha.hexdigest(),
        'current_full_SQL_SHA_reverified':complete,'full_EOF_and_all_tables_proven':complete,'reconciliation':reconciliation,
        'profile_identity_tables_actually_exercised':sorted(sink.counts),
        'profile_stream_throughput_is_not_chemical_or_unseen_table_forecast':True}


class KernelFixtures(unittest.TestCase):
    def test_NULL_escapes_and_escaped_physical_separators_across_one_byte_chunks(self):
        raw=b'1\t\\N\t\\\\N\ta\\\tb\\\nc\t\\101\\x42\n\\.\n'
        reader=copy_text.Input(io.BytesIO(raw),lambda:None,chunk=1)
        item=copy_text.row(reader,5,{0:'id',1:'null',2:'literal',3:'text',4:'encoded'})
        self.assertEqual(item['fields'],{0:'1',1:None,2:'\\N',3:'a\tb\nc',4:'AB'})
        self.assertTrue(copy_text.row(reader,5,{})['end'])

    def test_width_mismatch_and_unterminated_COPY_fail_instead_of_dropping(self):
        for raw in (b'1\t2\n',b'1'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                copy_text.row(copy_text.Input(io.BytesIO(raw),lambda:None,chunk=1),3,{})

    def test_same_projection_kernel_physically_preserves_false_invalid_and_raw_variant(self):
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as folder:
            sink=Sink(Path(folder));fields=dict.fromkeys(SELECT['molecules']);fields.update(id='1',canonical_smiles='raw\\stereo',status='inactive',active='f')
            sink.add('molecules',1,1,{'offset':0,'bytes':9,'row_sha256':'a'*64},fields)
            invalid=dict.fromkeys(SELECT['entries']);invalid.update(id='2',canonical_smiles='invalid_original',status='rejected',is_invalid='t')
            sink.add('entries',1,1,{'offset':9,'bytes':9,'row_sha256':'b'*64},invalid);sink.close()
            saved=pq.read_table(Path(folder)/'molecules.raw_identity.parquet').to_pylist()[0]
            self.assertEqual(json.loads(saved['identity_fields_json']),fields)
            self.assertEqual(json.loads(pq.read_table(Path(folder)/'entries.raw_identity.parquet').to_pylist()[0]['identity_fields_json']),invalid)
            sink.db.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True)
    args=p.parse_args();plan,proof,payload,upstream,schema=c.startup(args.plan,args.startup_proof,__file__)
    out=c.literal(plan['output_directory']);c.need(c.ROOT/'artifacts' in out.parents and not out.exists(),'NEW_INVENTORY_OUTPUT_REQUIRED');out.mkdir(parents=True)
    already=c.base.wall(c.base.fields(proof['job_metadata'])['RunTime'])+max(0,time.time()-proof['observed_unix_seconds'])
    remaining=plan['wall_seconds']-already;c.need(remaining>30,'INSUFFICIENT_ACTUAL_PARENT_WALL_REMAINING')
    began=time.monotonic();last=[float('-inf')];peak=[0];avail=[None];lag=[0.];sink=None
    monitor_done=threading.Event();monitor_stop=[];sample_lock=threading.Lock()
    def sample_memory():
        with sample_lock:
            start=time.monotonic();value=frozen_probe.memory();now=time.monotonic();lag[0]=max(lag[0],now-start)
            peak[0]=max(peak[0],value['self_RSS_bytes']);avail[0]=value['MemAvailable'] if avail[0] is None else min(avail[0],value['MemAvailable'])
            if value['self_RSS_bytes']>=2*1024**3 or value['MemAvailable']<value['MemTotal']*.15:monitor_stop.append('REAL_MEMORY_STOP_NEW_WORK')
    def monitor():
        try:
            while not monitor_done.is_set():sample_memory();monitor_done.wait(1)
        except BaseException as exc:monitor_stop.append('INVALID_RUNTIME_MEMORY:'+type(exc).__name__)
    monitor_thread=threading.Thread(target=monitor,name='readonly-inventory-current-memory',daemon=False);last_output=[float('-inf')]
    def checkpoint():
        c.need(not monitor_stop,monitor_stop[0] if monitor_stop else 'MEMORY_OBSERVATIONS_VALID')
        c.need(time.monotonic()-began<remaining-30,'HARD_WALL_MARGIN_STOP_NEW_WORK_NO_SIGNALS')
        if time.monotonic()-last[0]>=1:
            sample_memory();last[0]=time.monotonic();c.need(not monitor_stop,'REAL_MEMORY_STOP_NEW_WORK')
        if time.monotonic()-last_output[0]>=.5:
            last_output[0]=time.monotonic();total=0
            for directory,names,files in os.walk(out,followlinks=False):
                for name in [*names,*files]:
                    path=Path(directory)/name
                    try:value=path.lstat()
                    except FileNotFoundError:
                        c.need(out/'sqlite_tmp' in path.parents,'NON_SCRATCH_OUTPUT_DISAPPEARED');continue
                    c.need(not stat.S_ISLNK(value.st_mode),'OWNED_OUTPUT_SYMLINK_FORBIDDEN');total+=max(value.st_size,value.st_blocks*512)
            c.need(total+64*1024**2<=plan['output_cap_bytes'],'WHOLE_OUTPUT_SCRATCH_RESERVE_STOP_NEW_WORK')
    def progress(value):
        checkpoint()
        with (out/'progress.jsonl').open('ab') as stream:stream.write((json.dumps(value)+'\n').encode());stream.flush();os.fsync(stream.fileno())
        size=sum(max(x.stat().st_size,x.stat().st_blocks*512) for x in out.rglob('*') if x.is_file())
        c.need(size+8*1024**2<=plan['output_cap_bytes'],'WHOLE_OUTPUT_WITH_SCRATCH_CAP_REACHED')
    try:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(KernelFixtures);c.need(suite.countTestCases()==3,'EXACT_THREE_NEW_KERNEL_FIXTURES')
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        tests={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),'before_SQL_body_IO':True}
        c.write_new(out/'kernel_fixtures.json',tests);c.need(result.wasSuccessful() and result.testsRun==3 and not result.skipped,'FIXTURES_BEFORE_REAL_SQL_IO')
        checkpoint();monitor_thread.start();path=c.literal(payload['path']);sink=Sink(out,checkpoint)
        cpu=time.process_time()
        with path.open('rb') as stream:
            before=os.fstat(stream.fileno());c.need(stat.S_ISREG(before.st_mode) and before.st_uid==c.UID and before.st_size==c.base.SQL_BYTES,'CURRENT_FULL_SOURCE_FILE_REQUIRED')
            c.need(all(c.frame(before)[key]==upstream['format_probe_current_frame'][key] for key in ('inode','size','mtime_ns','uid')),
                   'SOURCE_FRAME_CHANGED_SINCE_ACTUAL_FORMAT_PROBE')
            details=inventory(stream,plan,schema,sink,checkpoint,progress);after=os.fstat(stream.fileno())
        c.need(c.frame(before)==c.frame(after)==c.frame(path.stat()),'INPUT_CHANGED_DURING_SQL_INVENTORY')
        expected_counts=dict(sink.counts);expected_schema=sink.schema;sink.db.close();sink=None;progress({'status':'FINAL_SOURCE_FSTAT_STABLE'})
        import pyarrow.parquet as pq
        outputs=[]
        for file in sorted(out.iterdir()):
            if not file.is_file() or file.name=='progress.jsonl':continue
            checkpoint();before_output=file.stat();digest=hashlib.sha256()
            with file.open('rb') as source:
                for block in iter(lambda:source.read(1024**2),b''):checkpoint();digest.update(block)
            c.need(c.frame(file.stat())==c.frame(before_output),'OWNED_OUTPUT_CHANGED_DURING_SHA')
            if file.name.endswith('.raw_identity.parquet'):
                table=file.name[:-len('.raw_identity.parquet')];parquet=pq.ParquetFile(file)
                c.need(parquet.schema_arrow.equals(expected_schema) and parquet.metadata.num_rows==expected_counts[table],'PHYSICAL_PARQUET_FOOTER_ROW_CONSERVATION')
            outputs.append({'path':str(file),'bytes':before_output.st_size,'sha256':digest.hexdigest()})
        monitor_done.set();monitor_thread.join();checkpoint()
        c.write_new(out/'receipt.json',{'schema':'SECONDARY_COCONUT_SQL_IDENTITY_INVENTORY_RECEIPT_V1',
            'status':'BOUNDED_SQL_IDENTITY_PROJECTION_PROFILE_COMPLETE' if plan['mode']=='profile' else 'FULL_SQL_PHYSICAL_IDENTITY_FIELD_INVENTORY_COMPLETE',
            'mode':plan['mode'],'scope_key':c.KEY,'endpoint':c.ENDPOINT,'uid':c.UID,'node':plan['node'],'job_id':str(proof['job_id']),
            'input_reference':payload,'upstream_actual_source':upstream,'plan':c.pin(args.plan),'startup_proof':c.pin(args.startup_proof),
            'kernel_source_references':[c.pin(Path(__file__).parent/name) for name in ('__init__.py','contracts.py','copy_text.py','run.py')],
            'input_before':c.frame(before),'input_after':c.frame(after),'inventory':details,'kernel_fixtures':tests,
            'physical_output_references':outputs,
            'CPU_seconds':time.process_time()-cpu,'wall_seconds_including_fixtures':time.monotonic()-began,
            'actual_scheduler_seconds_before_producer_work':already,'remaining_parent_wall_at_start':remaining,
            'peak_sampled_current_self_RSS_bytes':peak[0],'minimum_sampled_actual_MemAvailable_bytes':avail[0],'maximum_sample_seconds_lag_only':lag[0],
            'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','memory_requested':False,'allocated_cpus':16,'parallel16_parser_claimed':False,
            'source_scope':'EXACT_DOWNLOADED_2026_10_PHYSICAL_SQL_NOT_UNPUBLISHED_HARD_DELETION_HISTORY',
            'all_statuses_classes_invalid_and_NULL_rows_retained':True,'geometry_JSON_decoded':False,'nonidentity_values_decoded_or_persisted':False,
            'downloaded_SQL_executed_or_imported':False,'own_SQLite_contains_only_selected_identity_fields':True,
            'chemical_normalization_completed':False,'RDKit_calls':0,'decontamination_or_pool_UFF_QM_training_release':False,
            'actual_parent_allocation_cost_pending_accounting':True,'signals_sent':False})
    except BaseException as exc:
        if sink is not None:
            try:sink.close();sink.db.close()
            except Exception:pass
        c.write_new(out/'failure.json',{'status':'SQL_IDENTITY_INVENTORY_STOPPED_UNKNOWN_PARTIALS_PRESERVED','type':type(exc).__name__,
            'error':str(exc),'traceback':traceback.format_exc(),'input_untouched':True,'signals_sent':False})
        raise
    finally:
        monitor_done.set()
        if monitor_thread.ident is not None:monitor_thread.join()

if __name__=='__main__':main()
