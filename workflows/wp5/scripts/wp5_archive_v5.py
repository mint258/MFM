"""WP5 output-only failures/record-audit archive. Durable calls, atomic SCI receipts.
Historical archive_v4 remains immutable. No input body can enter this format.
"""
from __future__ import annotations
import argparse,ast,hashlib,json,os,pickle,sqlite3,threading,time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote
import wp5_archive_v4 as A
ROOT=A.ROOT;CALC_TYPES=A.CALC_TYPES
POLICY='FAILURES_PLUS_STRATIFIED_RECORD_AUDIT_NO_INPUT'
FORBIDDEN_INPUT_NAMES={'input.xyz','input.mop','native.inp','input_recipe.json'}
digest,canonical,file_sha,bundle,unbundle,Zstd,load_dictionaries=A.digest,A.canonical,A.file_sha,A.bundle,A.unbundle,A.Zstd,A.load_dictionaries

def retention(record,policy=POLICY,seed=None):
    if policy!=POLICY:raise ValueError('Only user-authorized no-input failure/record-audit policy supported')
    if record.get('audit_selected') is True:return True,'STRATIFIED_RECORD_AUDIT_ALL_TASKS'
    if record['scope_status'] in {'CALCULATION_FAILED','PROPERTY_FAILED','TIMEOUT'}:return True,'FAILED_CALCULATION_COMPLETE_OUTPUT'
    if record['scope_status']=='SUCCESS':return False,'ORDINARY_SUCCESS_NO_SHARED_RAW'
    raise ValueError('UNKNOWN_CANONICAL_STATUS_NOT_SILENTLY_RETAINED_OR_DROPPED:'+record['scope_status'])

class ArchiveWriter(A.ArchiveWriter):
    def __init__(self,path,dictionary_manifest,recipe_manifest=None,policy=POLICY,audit_seed=20261010,level=3,resume=False,reproduction_package=None,audit_membership=None):
        self.path=Path(path).absolute()
        if not self.path.is_relative_to(ROOT):raise ValueError('Only current WP5 root')
        if self.path.exists() and not resume:raise FileExistsError(self.path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        if policy!=POLICY:raise ValueError('Legacy ALL/SELECTIVE policy forbidden in new production archive')
        self.pid=os.getpid();self.thread=threading.get_ident();self.active_molecule=None;self.last_vacuum_reserve_bytes=0
        self.policy=policy;self.seed=audit_seed;self.dicts=load_dictionaries(dictionary_manifest);self.zstd=Zstd(level=level)
        self.db=sqlite3.connect(self.path,timeout=60,isolation_level=None)
        self.db.execute('PRAGMA journal_mode=DELETE');self.db.execute('PRAGMA synchronous=FULL');self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS dictionaries(dict_id TEXT PRIMARY KEY,calc_type TEXT UNIQUE NOT NULL,sha256 TEXT NOT NULL,path TEXT NOT NULL) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS molecules(molecule_id TEXT PRIMARY KEY,rows INTEGER NOT NULL,completed INTEGER NOT NULL) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS records(
          record_id TEXT NOT NULL,calc_type TEXT NOT NULL,execution_id TEXT NOT NULL,molecule_id TEXT NOT NULL,
          dict_id TEXT NOT NULL,source_status TEXT NOT NULL,scope_status TEXT NOT NULL,retention_reason TEXT NOT NULL,
          input_bundle_sha256 TEXT,raw_sha256 BLOB NOT NULL,raw_bytes INTEGER NOT NULL,metadata_bytes INTEGER NOT NULL,
          raw_frame BLOB NOT NULL,metadata_frame BLOB NOT NULL,PRIMARY KEY(record_id,calc_type,execution_id)) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS parsed_molecules(molecule_id TEXT PRIMARY KEY,record_count INTEGER NOT NULL,wire_sha256 TEXT NOT NULL,uncompressed_bytes INTEGER NOT NULL,dict_id TEXT NOT NULL,wire_frame BLOB NOT NULL) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS completion_receipts(molecule_id TEXT PRIMARY KEY,record_count INTEGER NOT NULL,raw_calls INTEGER NOT NULL,wire_sha256 TEXT,receipt_json TEXT NOT NULL,export_id TEXT) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS parquet_exports(export_id TEXT PRIMARY KEY,references_json TEXT NOT NULL,verified_epoch REAL NOT NULL) WITHOUT ROWID;
        ''')
        meta={'format':'WP5_OUTPUT_ONLY_DICT_ZSTD_V2','policy':policy,'audit_seed':str(audit_seed),'input_bodies_saved':'false',
              'dictionary_manifest_sha256':file_sha(dictionary_manifest),'recipe_manifest_sha256':file_sha(recipe_manifest) if recipe_manifest else 'NONE',
              'reproduction_package_sha256':file_sha(reproduction_package) if reproduction_package else 'NONE',
              'audit_membership_sha256':file_sha(audit_membership) if audit_membership else 'NONE',
              'compression_level':str(level),'zstd_version':self.zstd.version,'raw_commit_boundary':'one retained call; scientific stage+receipt one completed molecule'}
        self.db.execute('BEGIN IMMEDIATE')
        try:
            for k,v in meta.items():
                old=self.db.execute('SELECT value FROM metadata WHERE key=?',(k,)).fetchone()
                if old and old[0]!=v:raise ValueError('Frozen archive metadata differs on resume')
                self.db.execute('INSERT OR IGNORE INTO metadata VALUES(?,?)',(k,v))
            for d in self.dicts.values():self.db.execute('INSERT OR IGNORE INTO dictionaries VALUES(?,?,?,?)',(d['dict_id'],d['calc_type'],d['sha256'],d['path']))
            self.db.execute('COMMIT')
        except Exception:self.db.execute('ROLLBACK');raise
    def begin_molecule(self,molecule_id):
        self.identity()
        if self.active_molecule is not None:raise RuntimeError('Nested SCI molecule context')
        self.active_molecule=str(molecule_id)
    def commit_molecule(self):
        self.identity()
        if self.active_molecule is None:raise RuntimeError('No active molecule')
        self.active_molecule=None
    def rollback_molecule(self):
        self.identity()
        if self.db.in_transaction:self.db.execute('ROLLBACK')
        # Committed failure/audit outputs stay as explicit partial-attempt evidence.
        self.active_molecule=None
    def put_record(self,record,keep_output=None):
        self.identity()
        if self.active_molecule!=str(record['molecule_id']):raise RuntimeError('Owning molecule context required')
        execution=str(record.get('execution_id') or '')
        if not execution:raise ValueError('Explicit execution_id required; never fall back to RID/task partial raw')
        keep,reason=retention(record,self.policy)
        if keep_output is not None and bool(keep_output)!=keep:raise ValueError('Retention differs from record audit/failure rule')
        for f in record.get('files',[]):
            if f.get('role')!='output' or f['name'] in FORBIDDEN_INPUT_NAMES:raise ValueError('Input body forbidden in new archive')
        ref={'container_path':str(self.path) if keep else None,'record_id':record['record_id'],'calc_type':record['calc_type'],
             'execution_id':execution,'output_retained':keep,'retention_reason':reason,'input_bundle_sha256':record.get('input_bundle_sha256'),
             'input_file_sha256':record.get('input_file_sha256'),'ordinary_success_shared_insert':False}
        if not keep:return ref
        calc=record['calc_type'];d=self.dicts[calc];raw,manifest=bundle(record.get('files',[]))
        meta={k:v for k,v in record.items() if k!='files'};meta['output_file_manifest']=manifest;meta['input_bodies_saved']=False
        encoded=canonical(meta);frame=self.zstd.compress(raw,d['data']);mf=self.zstd.compress(encoded,d['data'])
        values=(record['record_id'],calc,execution,self.active_molecule,d['dict_id'],record['source_status'],record['scope_status'],reason,
                record.get('input_bundle_sha256'),bytes.fromhex(digest(raw)),len(raw),len(encoded),frame,mf)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            old=self.db.execute('SELECT * FROM records WHERE record_id=? AND calc_type=? AND execution_id=?',values[:3]).fetchone()
            if old and tuple(old)!=values:raise ValueError('Retained raw execution key differs')
            if not old:self.db.execute('INSERT INTO records VALUES('+','.join('?' for _ in values)+')',values)
            self.db.execute('INSERT OR IGNORE INTO molecules VALUES(?,?,0)',(self.active_molecule,0))
            self.db.execute('COMMIT')
        except Exception:self.db.execute('ROLLBACK');raise
        # FULL-synchronous COMMIT has returned before local scratch may be deleted.
        ref.update(dict_id=d['dict_id'],raw_sha256=digest(raw),raw_frame_bytes=len(frame),metadata_frame_bytes=len(mf),
                   logical_raw_bytes=len(raw),raw_call_durable=True,input_bodies_saved=False)
        return ref
    def stage_molecule(self,molecule_id,payload,record_count,completion_receipt=None):
        self.identity();mid=str(molecule_id)
        if self.active_molecule!=mid:raise RuntimeError('SCI stage must use owning molecule context')
        if payload.get('result',{}).get('raw_records'):raise ValueError('Raw bodies cannot be duplicated in SCI stage')
        receipt=dict(completion_receipt or {});context=receipt.get('context',payload.get('context',{}));execution=context.get('execution_id')
        if not execution:raise ValueError('Completed SCI receipt requires explicit execution_id')
        calls=self.db.execute('SELECT count(*) FROM records WHERE molecule_id=? AND execution_id=?',(mid,execution)).fetchone()[0]
        receipt.update(execution_id=execution,retained_raw_calls=calls,requested_outcomes=12*int(record_count),raw_policy=self.policy)
        wire=pickle.dumps(payload,protocol=5);key=digest(wire);d=self.dicts['pm7_B'];frame=self.zstd.compress(wire,d['data'])
        if digest(self.zstd.decompress(frame,d['data'],len(wire)))!=key:raise ValueError('SCI wire roundtrip differs')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            old=self.db.execute('SELECT wire_sha256,record_count FROM parsed_molecules WHERE molecule_id=?',(mid,)).fetchone()
            if old and tuple(old)!=(key,int(record_count)):raise ValueError('Existing completed SCI stage differs')
            self.db.execute('INSERT OR IGNORE INTO parsed_molecules VALUES(?,?,?,?,?,?)',(mid,int(record_count),key,len(wire),d['dict_id'],frame))
            prior=self.completion(mid)
            if prior and (prior['wire_sha256']!=key or prior['record_count']!=int(record_count)):raise ValueError('SCI completion differs')
            self.db.execute('INSERT OR IGNORE INTO completion_receipts VALUES(?,?,?,?,?,NULL)',(mid,int(record_count),calls,key,canonical(receipt).decode()))
            self.db.execute('INSERT OR REPLACE INTO molecules VALUES(?,?,1)',(mid,calls));self.db.execute('COMMIT')
        except Exception:self.db.execute('ROLLBACK');raise
        return {'molecule_id':mid,'record_count':int(record_count),'wire_sha256':key,'uncompressed_wire_bytes':len(wire),
                'compressed_wire_bytes':len(frame),'dict_id':d['dict_id'],'raw_call_count':calls,'requested_outcomes':12*int(record_count)}

class ArchiveReader(A.ArchiveReader):
    def get(self,record_id,calc_type,execution_id=None):
        if execution_id is None:
            # Resolve only from a completed SCI receipt. Partial raw is never latest.
            candidates=self.db.execute('SELECT DISTINCT molecule_id FROM records WHERE record_id=? AND calc_type=?',(record_id,calc_type)).fetchall()
            if len(candidates)!=1:raise KeyError((record_id,calc_type,'NO_UNAMBIGUOUS_COMPLETED_SCI'))
            complete=self.completion(candidates[0][0])
            execution_id=complete['receipt'].get('execution_id') if complete else None
            if not execution_id:raise KeyError((record_id,calc_type,'PARTIAL_RAW_NOT_LATEST_SCI'))
        row=self.db.execute('SELECT * FROM records WHERE record_id=? AND calc_type=? AND execution_id=?',(record_id,calc_type,str(execution_id))).fetchone()
        if row is None:raise KeyError((record_id,calc_type,str(execution_id)))
        d=self.dicts[calc_type]
        raw=self.zstd.decompress(row['raw_frame'],d['data'],row['raw_bytes'])
        if hashlib.sha256(raw).digest()!=row['raw_sha256']:raise ValueError('Raw SHA differs')
        outputs,manifest=unbundle(raw);meta=json.loads(self.zstd.decompress(row['metadata_frame'],d['data'],row['metadata_bytes']))
        if meta.get('output_file_manifest')!=manifest or any(f['name'] in FORBIDDEN_INPUT_NAMES for f in outputs):raise ValueError('Output manifest/input omission differs')
        return {'record_id':record_id,'calc_type':calc_type,'execution_id':str(execution_id),'molecule_id':row['molecule_id'],
                'input_files':[],'input_bodies_saved':False,'input_file_sha256':meta.get('input_file_sha256'),
                'input_bundle_sha256':row['input_bundle_sha256'],'output_files':outputs,'original_output_manifest':manifest,
                'output_retained':True,'raw_sha256':bytes(row['raw_sha256']).hex(),'source_status':row['source_status'],
                'scope_status':row['scope_status'],'retention_reason':row['retention_reason'],'metadata':meta}

def consolidate_archives(lane_paths,output_path,dictionary_manifest,recipe_manifest=None,policy=POLICY,verify_raw=True,reproduction_package=None,audit_membership=None):
    """Preserve explicit executions, including partial raw evidence; never inputs."""
    target=Path(output_path).absolute();pending=target.with_name(target.name+'.pending')
    if target.exists() or pending.exists():raise FileExistsError('Immutable new archive required')
    paths=[Path(p).absolute() for p in lane_paths]
    if len(paths)!=len(set(paths)) or any(not p.is_relative_to(ROOT) for p in paths):raise ValueError('Unique current-round lane paths required')
    writer=ArchiveWriter(pending,dictionary_manifest,recipe_manifest,policy=policy,reproduction_package=reproduction_package,audit_membership=audit_membership);source_refs=[];meta_first=None
    try:
        for path in paths:
            reader=ArchiveReader(path,dictionary_manifest)
            try:
                if reader.db.execute('SELECT count(*) FROM parsed_molecules').fetchone()[0]:raise ValueError('Retire verified SCI stage before consolidation')
                meta=dict(reader.db.execute('SELECT key,value FROM metadata'))
                if meta.get('policy')!=POLICY or meta.get('input_bodies_saved')!='false':raise ValueError('Output-only policy mismatch')
                if meta_first is None:
                    meta_first=meta
                    writer.db.execute('BEGIN IMMEDIATE')
                    for k,v in meta.items():writer.db.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',(k,v))
                    writer.db.execute('COMMIT')
                elif meta!=meta_first:raise ValueError('Frozen lane metadata differs')
                writer.db.execute('BEGIN IMMEDIATE')
                try:
                    for row in reader.db.execute('SELECT * FROM records ORDER BY record_id,calc_type,execution_id'):
                        if verify_raw:reader.get(row['record_id'],row['calc_type'],row['execution_id'])
                        values=tuple(row);writer.db.execute('INSERT INTO records VALUES('+','.join('?' for _ in values)+')',values)
                        actual=writer.db.execute('SELECT * FROM records WHERE record_id=? AND calc_type=? AND execution_id=?',values[:3]).fetchone()
                        if tuple(actual)!=values:raise ValueError('Copied raw bytes differ')
                    for row in reader.db.execute('SELECT * FROM molecules'):
                        old=writer.db.execute('SELECT rows,completed FROM molecules WHERE molecule_id=?',(row['molecule_id'],)).fetchone()
                        if old and old[1] and row['completed']:raise ValueError('Duplicate completed SCI molecule across lanes')
                        if old is None or row['completed']:writer.db.execute('INSERT OR REPLACE INTO molecules VALUES(?,?,?)',tuple(row))
                    for row in reader.db.execute('SELECT * FROM completion_receipts'):
                        writer.db.execute('INSERT INTO completion_receipts VALUES(?,?,?,?,?,?)',tuple(row))
                    for row in reader.db.execute('SELECT * FROM parquet_exports'):
                        old=writer.db.execute('SELECT references_json FROM parquet_exports WHERE export_id=?',(row['export_id'],)).fetchone()
                        if old and old[0]!=row['references_json']:raise ValueError('Parquet export binding differs')
                        writer.db.execute('INSERT OR IGNORE INTO parquet_exports VALUES(?,?,?)',tuple(row))
                    writer.db.execute('COMMIT')
                except Exception:writer.db.execute('ROLLBACK');raise
                source_refs.append({'path':str(path),'bytes':path.stat().st_size,'sha256':file_sha(path)})
            finally:reader.close()
        records=writer.db.execute('SELECT count(*) FROM records').fetchone()[0]
        molecules=writer.db.execute('SELECT count(*) FROM completion_receipts').fetchone()[0]
        complete_calls=0;partial_calls=0
        for row in writer.db.execute('SELECT molecule_id,execution_id,count(*) AS n FROM records GROUP BY molecule_id,execution_id'):
            completion=writer.completion(row[0])
            if completion and completion['receipt'].get('execution_id')==row[1]:complete_calls+=row[2]
            else:partial_calls+=row[2]
        writer.db.execute('INSERT INTO metadata VALUES(?,?)',('consolidation_source_catalog',canonical(source_refs).decode()))
        if writer.db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Archive integrity failed')
        writer.close();reader=ArchiveReader(pending,dictionary_manifest)
        try:
            if verify_raw:
                for rid,calc,execution in reader.db.execute('SELECT record_id,calc_type,execution_id FROM records'):reader.get(rid,calc,execution)
        finally:reader.close()
        with pending.open('rb') as stream:os.fsync(stream.fileno())
        os.rename(pending,target)
        return {'path':str(target),'bytes':target.stat().st_size,'sha256':file_sha(target),'raw_records':records,
            'molecules':molecules,'completed_SCI_retained_raw_calls':complete_calls,'partial_attempt_retained_raw_calls':partial_calls,
            'source_paths':source_refs,'sources_deleted':False,'parsed_wire_present':False,'raw_member_roundtrip_checked':verify_raw,
            'input_bodies_saved':False,'policy':POLICY,'new_old_coexistence_measured_bytes':target.stat().st_size+sum(p['bytes'] for p in source_refs)}
    except Exception:
        if writer.db is not None:writer.close()
        raise

def check():
    """Small storage fixture: no QM, source LMDB, or historical artifacts."""
    import tempfile,shutil,stat
    ast.parse(Path(__file__).read_text())
    assert retention({'scope_status':'SUCCESS','audit_selected':False})==(False,'ORDINARY_SUCCESS_NO_SHARED_RAW')
    assert not retention({'scope_status':'SUCCESS','is_minimum':True,'audit_selected':False})[0]
    dictionaries=ROOT/'dictionaries/job_4513894/dictionary_manifest.json'
    base=ROOT/'tests';base.mkdir(exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='output_only_fixture_'+str(os.getuid())+'_',dir=base));lane=folder/'lane.sqlite'
    writer=None;reader=None
    try:
        writer=ArchiveWriter(lane,dictionaries)
        def record(mid,calc,execution,status='SUCCESS',audit=False):
            body=(mid+' '+calc+' output').encode()
            return {'record_id':mid+'_record','molecule_id':mid,'calc_type':calc,'execution_id':execution,
                    'source_status':status,'scope_status':status,'audit_selected':audit,'input_bundle_sha256':digest(b'hash-only-input'),
                    'input_file_sha256':[{'name':'input.xyz','sha256':digest(b'NEVER_PERSIST_INPUT_BODY')}],
                    'files':[{'name':'process.out','role':'output','data':body,'sha256':digest(body),'byte_count':len(body)}]}
        for mid,status,audit in (('ordinary','SUCCESS',False),('audited','SUCCESS',True),('failed','CALCULATION_FAILED',False)):
            execution=mid+':complete'
            with writer.molecule(mid):
                for calc in CALC_TYPES:
                    ref=writer.put_record(record(mid,calc,execution,status,audit))
                    assert ref['output_retained']==(audit or status!='SUCCESS')
                    if ref['output_retained']:assert ref['raw_call_durable']
                context={'execution_id':execution,'attempt_id':0,'job_id':0,'task_id':'fixture','lane':0}
                payload={'context':context,'result':{'raw_records':[],'record_results':[]},'population_rows':[]}
                writer.stage_molecule(mid,payload,1,{'context':context,'molecule_id':mid,'records':1})
        assert writer.db.execute("SELECT count(*) FROM records WHERE molecule_id='ordinary'").fetchone()[0]==0
        try:
            with writer.molecule('partial'):
                writer.put_record(record('partial','pm7_B','partial:interrupted','TIMEOUT'))
                raise InterruptedError('fixture interruption after durable retained call')
        except InterruptedError:pass
        assert writer.completion('partial') is None
        with writer.molecule('forbidden'):
            raw=record('forbidden','pm7_B','forbidden:input','TIMEOUT');raw['files'][0]['role']='input'
            try:writer.put_record(raw);raise AssertionError('Input body accepted')
            except ValueError as error:assert 'Input body forbidden' in str(error)
        assert writer.db.execute('SELECT count(*) FROM records').fetchone()[0]==25
        writer.close();writer=None;reader=ArchiveReader(lane,dictionaries)
        assert reader.get('audited_record','xtb_fod')['input_files']==[]
        assert reader.get('audited_record','xtb_fod')['output_files'][0]['data']==b'audited xtb_fod output'
        try:reader.get('partial_record','pm7_B');raise AssertionError('Partial fallback accepted')
        except KeyError:pass
        assert reader.get('partial_record','pm7_B','partial:interrupted')['scope_status']=='TIMEOUT'
        assert len(list(reader.iter_staged()))==3
        reader.close();reader=None
        # Retire only fixture staging after a genuine SHA-bound small export reference.
        fixture=folder/'fixture_verified.txt';fixture.write_bytes(b'archive-fixture-export-proof')
        writer=ArchiveWriter(lane,dictionaries,resume=True)
        writer.retire_staged_after_verified_parquet([{'path':str(fixture),'bytes':fixture.stat().st_size,'sha256':file_sha(fixture)}],vacuum=True)
        writer.close();writer=None
        result=consolidate_archives([lane],folder/'final.sqlite',dictionaries)
        assert result['molecules']==3 and result['raw_records']==25 and result['completed_SCI_retained_raw_calls']==24 and result['partial_attempt_retained_raw_calls']==1
        reader=ArchiveReader(folder/'final.sqlite',dictionaries)
        assert reader.get('failed_record','pm7_B')['input_bodies_saved'] is False
        assert reader.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not any('input_frame' in row[1] for row in reader.db.execute('PRAGMA table_info(records)'))
        print(json.dumps({'status':'OUTPUT_ONLY_DURABLE_CALL_SCI_RECEIPT_PARTIAL_READBACK_FIXTURE_PASS',
             'ordinary_success_raw_rows':0,'retained_raw_rows':25,'complete_SCI_molecules':3,'partial_evidence_rows':1,'input_bodies_saved':False,'QM_started':False,'LMDB_opened':False}))
    finally:
        if reader is not None:reader.close()
        if writer is not None:writer.close()
        checked=folder.resolve()
        if checked.parent!=base.resolve() or not folder.name.startswith('output_only_fixture_'+str(os.getuid())+'_'):raise ValueError('Fixture cleanup scope differs')
        for item in [folder,*folder.rglob('*')]:
            info=item.lstat()
            if info.st_uid!=os.getuid() or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):raise ValueError('Fixture cleanup owner/type differs')
        shutil.rmtree(folder)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
    if args.check:check()
