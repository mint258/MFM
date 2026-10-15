"""WP5 lossless dictionary-zstd SQLite archive; no LMDB or scientific execution.

One writer per shard/process. DELETE journal (not WAL) is used on shared storage.
Whole-molecule transactions are the checkpoint boundary. Dictionary/recipe SHA
and per-file SHA are checked; missing output and an actual empty file differ.
Stable zstd C APIs: https://github.com/facebook/zstd/blob/dev/lib/zstd.h
SQLite WAL limitation: https://www.sqlite.org/wal.html
"""
from __future__ import annotations
import argparse, ast
from contextlib import contextmanager
import ctypes, ctypes.util
import hashlib, json, os, pickle, time
from pathlib import Path, PurePosixPath
import sqlite3, struct, threading
from urllib.parse import quote

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
MAGIC=b'WP5BUNDLE1\0'
CALC_TYPES=('pm7_B','pm7_cation','pm7_anion','pm7_water','pm7_octanol',
 'xtb_singlepoint','xtb_vipea','xtb_vfukui','xtb_ALPB_water','xtb_ALPB_octanol',
 'xtb_fod','xtb_perturbed_gradient')

def digest(data):return hashlib.sha256(data).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def safe_name(name):
    p=PurePosixPath(str(name))
    if p.is_absolute() or '..' in p.parts or not p.parts or '\0' in str(name):
        raise ValueError('Unsafe archive relative filename')
    return str(p)

def bundle(files):
    """Canonical envelope preserves every filename, original file byte and SHA."""
    normalized=[]
    for value in files:
        name=safe_name(value['name']);data=value['data']
        if not isinstance(data,bytes):raise TypeError('Archive input must be bytes')
        actual=digest(data)
        if value.get('sha256') is not None and value['sha256']!=actual:raise ValueError('File SHA mismatch')
        if value.get('byte_count') is not None and value['byte_count']!=len(data):raise ValueError('File bytes mismatch')
        normalized.append((name,data,actual))
    normalized.sort(key=lambda v:v[0])
    if len({v[0] for v in normalized})!=len(normalized):raise ValueError('Duplicate filename within bundle')
    manifest=[{'name':name,'bytes':len(data),'sha256':sha} for name,data,sha in normalized]
    header=canonical(manifest)
    return MAGIC+struct.pack('<Q',len(header))+header+b''.join(data for _,data,_ in normalized),manifest

def unbundle(data):
    if not data.startswith(MAGIC) or len(data)<len(MAGIC)+8:raise ValueError('Bundle header mismatch')
    start=len(MAGIC)+8;length=struct.unpack('<Q',data[len(MAGIC):start])[0]
    manifest=json.loads(data[start:start+length]);position=start+length;files=[]
    for item in manifest:
        name=safe_name(item['name']);part=data[position:position+item['bytes']]
        if len(part)!=item['bytes'] or digest(part)!=item['sha256']:raise ValueError('Readback file SHA mismatch')
        files.append({'name':name,'byte_count':len(part),'sha256':item['sha256'],'data':part})
        position+=item['bytes']
    if position!=len(data):raise ValueError('Bundle trailing bytes')
    return files,manifest

class Zstd:
    """Stable libzstd dictionary APIs, with one compression context per instance."""
    def __init__(self,library=None,level=3):
        candidates=[library] if library else [
          str(Path(os.environ.get('CONDA_PREFIX','/nonexistent'))/'lib/libzstd.so.1'),
          str(Path(os.sys.executable).absolute().parent.parent/'lib/libzstd.so.1'),
          ctypes.util.find_library('zstd'),'libzstd.so.1']
        self.lib=None
        for name in candidates:
            if not name:continue
            try:self.lib=ctypes.CDLL(name);self.library=name;break
            except OSError:pass
        if self.lib is None:raise RuntimeError('libzstd unavailable')
        definitions={
         'ZSTD_versionString':([],ctypes.c_char_p),
         'ZSTD_compressBound':([ctypes.c_size_t],ctypes.c_size_t),
         'ZSTD_isError':([ctypes.c_size_t],ctypes.c_uint),
         'ZSTD_getErrorName':([ctypes.c_size_t],ctypes.c_char_p),
         'ZSTD_createCCtx':([],ctypes.c_void_p),'ZSTD_freeCCtx':([ctypes.c_void_p],ctypes.c_size_t),
         'ZSTD_createDCtx':([],ctypes.c_void_p),'ZSTD_freeDCtx':([ctypes.c_void_p],ctypes.c_size_t),
         'ZSTD_createCDict':([ctypes.c_void_p,ctypes.c_size_t,ctypes.c_int],ctypes.c_void_p),
         'ZSTD_freeCDict':([ctypes.c_void_p],ctypes.c_size_t),
         'ZSTD_createDDict':([ctypes.c_void_p,ctypes.c_size_t],ctypes.c_void_p),
         'ZSTD_freeDDict':([ctypes.c_void_p],ctypes.c_size_t),
         'ZSTD_compress_usingCDict':([ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p],ctypes.c_size_t),
         'ZSTD_decompress_usingDDict':([ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p],ctypes.c_size_t),
         'ZSTD_getDictID_fromDict':([ctypes.c_void_p,ctypes.c_size_t],ctypes.c_uint),
         'ZDICT_trainFromBuffer':([ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.POINTER(ctypes.c_size_t),ctypes.c_uint],ctypes.c_size_t)}
        for name,(args,result) in definitions.items():
            f=getattr(self.lib,name);f.argtypes=args;f.restype=result
        self.level=level;self.cctx=self.lib.ZSTD_createCCtx();self.dctx=self.lib.ZSTD_createDCtx()
        if not self.cctx or not self.dctx:raise MemoryError('zstd context allocation failed')
        self.dicts={};self.version=self.lib.ZSTD_versionString().decode()
    def check(self,result):
        if self.lib.ZSTD_isError(result):raise RuntimeError(self.lib.ZSTD_getErrorName(result).decode())
        return result
    def train(self,samples,capacity=65536):
        if len(samples)<8:raise ValueError('Insufficient real samples to train dictionary')
        joined=b''.join(samples);sizes=(ctypes.c_size_t*len(samples))(*map(len,samples))
        output=ctypes.create_string_buffer(capacity)
        result=self.check(self.lib.ZDICT_trainFromBuffer(output,capacity,ctypes.c_char_p(joined),sizes,len(samples)))
        dictionary=output.raw[:result]
        if not self.lib.ZSTD_getDictID_fromDict(ctypes.c_char_p(dictionary),len(dictionary)):raise ValueError('Dictionary has no native ID')
        return dictionary
    def register(self,dictionary):
        key=digest(dictionary)
        if key not in self.dicts:
            c=self.lib.ZSTD_createCDict(ctypes.c_char_p(dictionary),len(dictionary),self.level)
            d=self.lib.ZSTD_createDDict(ctypes.c_char_p(dictionary),len(dictionary))
            if not c or not d:raise MemoryError('zstd dictionary allocation failed')
            self.dicts[key]=(c,d)
        return key
    def compress(self,data,dictionary):
        key=self.register(dictionary);capacity=self.check(self.lib.ZSTD_compressBound(len(data)))
        output=ctypes.create_string_buffer(capacity)
        result=self.check(self.lib.ZSTD_compress_usingCDict(self.cctx,output,capacity,ctypes.c_char_p(data),len(data),self.dicts[key][0]))
        return output.raw[:result]
    def decompress(self,data,dictionary,size):
        if size<0 or size>2**31:raise ValueError('Invalid stored uncompressed size')
        key=self.register(dictionary);output=ctypes.create_string_buffer(max(1,size))
        result=self.check(self.lib.ZSTD_decompress_usingDDict(self.dctx,output,max(1,size),ctypes.c_char_p(data),len(data),self.dicts[key][1]))
        if result!=size:raise ValueError('Readback uncompressed size mismatch')
        return output.raw[:result]
    def close(self):
        if self.cctx:
            for c,d in self.dicts.values():self.lib.ZSTD_freeCDict(c);self.lib.ZSTD_freeDDict(d)
            self.dicts.clear();self.lib.ZSTD_freeCCtx(self.cctx);self.lib.ZSTD_freeDCtx(self.dctx)
            self.cctx=self.dctx=None

def load_dictionaries(manifest):
    source=Path(manifest);data=json.loads(source.read_text());result={}
    entries=data['dictionaries']
    for entry in entries:
        p=Path(entry['path']);p=p if p.is_absolute() else source.parent/p
        raw=p.read_bytes()
        if digest(raw)!=entry['sha256'] or len(raw)!=entry['bytes']:raise ValueError('Dictionary binding mismatch')
        if entry['calc_type'] in result:raise ValueError('Duplicate calc_type dictionary')
        result[entry['calc_type']]={**entry,'path':str(p),'data':raw,'dict_id':entry.get('dict_id',entry['sha256'])}
    if set(result)!=set(CALC_TYPES):raise ValueError('Exactly frozen12 calc_type dictionaries required')
    return result

def audit_selected(record_id,calc_type,seed=20261011):
    return int.from_bytes(hashlib.sha256(f'{seed}|{record_id}|{calc_type}'.encode()).digest()[:8],'big')<(2**64//100)

def retention(record,policy,seed=20261011):
    if policy=='ALL':return True,'ALL'
    if policy!='SELECTIVE':raise ValueError('Unknown archive policy')
    if record['scope_status']!='SUCCESS':return True,'NON_SUCCESS_ALL'
    if record.get('is_minimum'):return True,'SUCCESS_MOLECULAR_MINIMUM'
    if audit_selected(record['record_id'],record['calc_type'],seed):return True,'SEEDED_1_PERCENT_SUCCESS_AUDIT'
    return False,'PARSED_LABELS_ONLY_INPUT_ALWAYS'

class ArchiveWriter:
    def __init__(self,path,dictionary_manifest,recipe_manifest=None,policy='ALL',audit_seed=20261011,level=3,resume=False):
        self.path=Path(path).absolute()
        if not self.path.is_relative_to(ROOT):raise ValueError('Archive writes only inside this WP5 root')
        if self.path.exists() and not resume:raise FileExistsError(self.path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.pid=os.getpid();self.thread=threading.get_ident();self.active_molecule=None
        self.policy=policy;self.seed=audit_seed;self.last_vacuum_reserve_bytes=0;self.dicts=load_dictionaries(dictionary_manifest);self.zstd=Zstd(level=level)
        self.db=sqlite3.connect(self.path,timeout=60,isolation_level=None)
        self.db.execute('PRAGMA journal_mode=DELETE');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS dictionaries(dict_id TEXT PRIMARY KEY,calc_type TEXT UNIQUE NOT NULL,sha256 TEXT NOT NULL,path TEXT NOT NULL) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS molecules(molecule_id TEXT PRIMARY KEY,rows INTEGER NOT NULL,completed INTEGER NOT NULL) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS records(
          record_id TEXT NOT NULL,calc_type TEXT NOT NULL,molecule_id TEXT NOT NULL,
          dict_id TEXT NOT NULL REFERENCES dictionaries(dict_id),
          source_status TEXT NOT NULL,scope_status TEXT NOT NULL,retention_reason TEXT NOT NULL,
          input_origin TEXT NOT NULL,input_sha256 BLOB NOT NULL,raw_sha256 BLOB NOT NULL,
          input_bytes INTEGER NOT NULL,raw_bytes INTEGER NOT NULL,metadata_bytes INTEGER NOT NULL,
          input_frame BLOB NOT NULL,raw_frame BLOB,metadata_frame BLOB NOT NULL,
          output_manifest TEXT NOT NULL,
          PRIMARY KEY(record_id,calc_type)) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS parsed_molecules(
          molecule_id TEXT PRIMARY KEY,record_count INTEGER NOT NULL,wire_sha256 TEXT NOT NULL,
          uncompressed_bytes INTEGER NOT NULL,dict_id TEXT NOT NULL,wire_frame BLOB NOT NULL
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS completion_receipts(
          molecule_id TEXT PRIMARY KEY,record_count INTEGER NOT NULL,raw_calls INTEGER NOT NULL,
          wire_sha256 TEXT,receipt_json TEXT NOT NULL,export_id TEXT
        ) WITHOUT ROWID;
        CREATE TABLE IF NOT EXISTS parquet_exports(
          export_id TEXT PRIMARY KEY,references_json TEXT NOT NULL,verified_epoch REAL NOT NULL
        ) WITHOUT ROWID;

        """)
        metadata={'format':'WP5_SQLITE_DICT_ZSTD_V1','policy':policy,'audit_seed':str(audit_seed),
            'dictionary_manifest_sha256':file_sha(dictionary_manifest),
            'recipe_manifest_sha256':file_sha(recipe_manifest) if recipe_manifest else 'NONE',
            'compression_level':str(level),'zstd_version':self.zstd.version}
        self.db.execute('BEGIN IMMEDIATE')
        try:
            for key,value in metadata.items():
                old=self.db.execute('SELECT value FROM metadata WHERE key=?',(key,)).fetchone()
                if old and old[0]!=value:raise ValueError('Archive frozen metadata differs on resume')
                self.db.execute('INSERT OR IGNORE INTO metadata VALUES(?,?)',(key,value))
            for entry in self.dicts.values():
                self.db.execute('INSERT OR IGNORE INTO dictionaries VALUES(?,?,?,?)',(entry['dict_id'],entry['calc_type'],entry['sha256'],entry['path']))
            self.db.execute('COMMIT')
        except Exception:self.db.execute('ROLLBACK');raise
    def identity(self):
        if os.getpid()!=self.pid or threading.get_ident()!=self.thread:raise RuntimeError('Archive writer must stay in one owning process/thread')
    def begin_molecule(self,molecule_id):
        self.identity()
        if self.active_molecule is not None:raise RuntimeError('Nested molecule transaction')
        self.db.execute('BEGIN IMMEDIATE');self.active_molecule=str(molecule_id)
    def commit_molecule(self):
        self.identity()
        if self.active_molecule is None:raise RuntimeError('No active molecule')
        molecule=self.active_molecule
        count=self.db.execute('SELECT count(*) FROM records WHERE molecule_id=?',(molecule,)).fetchone()[0]
        self.db.execute('INSERT OR REPLACE INTO molecules VALUES(?,?,1)',(molecule,count))
        self.db.execute('COMMIT');self.active_molecule=None
    def rollback_molecule(self):
        self.identity()
        if self.active_molecule is not None:self.db.execute('ROLLBACK');self.active_molecule=None
    @contextmanager
    def molecule(self,molecule_id):
        self.begin_molecule(molecule_id)
        try:yield self;self.commit_molecule()
        except Exception:self.rollback_molecule();raise
    def completion(self,molecule_id):
        row=self.db.execute('SELECT record_count,raw_calls,wire_sha256,receipt_json,export_id FROM completion_receipts WHERE molecule_id=?',(str(molecule_id),)).fetchone()
        if row is None:return None
        return {'molecule_id':str(molecule_id),'record_count':row[0],'raw_calls':row[1],
            'wire_sha256':row[2],'receipt':json.loads(row[3]),'export_id':row[4]}
    def is_completed(self,molecule_id):return self.completion(molecule_id) is not None
    def stage_molecule(self,molecule_id,payload,record_count,completion_receipt=None):
        self.identity()
        if self.active_molecule!=str(molecule_id):raise RuntimeError('Staging must share the whole-molecule raw transaction')
        wire=pickle.dumps(payload,protocol=5);key=digest(wire);d=self.dicts['pm7_B']
        frame=self.zstd.compress(wire,d['data'])
        if digest(self.zstd.decompress(frame,d['data'],len(wire)))!=key:raise ValueError('Staged pickle wire roundtrip differs')
        old=self.db.execute('SELECT wire_sha256,record_count FROM parsed_molecules WHERE molecule_id=?',(str(molecule_id),)).fetchone()
        if old and old!=(key,int(record_count)):raise ValueError('Existing staged molecule differs')
        self.db.execute('INSERT OR IGNORE INTO parsed_molecules VALUES(?,?,?,?,?,?)',
            (str(molecule_id),int(record_count),key,len(wire),d['dict_id'],frame))
        calls=self.db.execute('SELECT count(*) FROM records WHERE molecule_id=?',(str(molecule_id),)).fetchone()[0]
        receipt=completion_receipt if completion_receipt is not None else {'status':'MOLECULE_COMPLETE','molecule_id':str(molecule_id),'record_count':int(record_count)}
        encoded=canonical(receipt).decode();existing=self.completion(molecule_id)
        if existing and (existing['wire_sha256']!=key or existing['record_count']!=int(record_count)):
            raise ValueError('Existing completion receipt differs')
        self.db.execute('INSERT OR IGNORE INTO completion_receipts VALUES(?,?,?,?,?,NULL)',
            (str(molecule_id),int(record_count),calls,key,encoded))
        return {'molecule_id':str(molecule_id),'record_count':int(record_count),
            'wire_sha256':key,'uncompressed_wire_bytes':len(wire),'compressed_wire_bytes':len(frame),
            'dict_id':d['dict_id'],'raw_call_count':calls}
    def iter_staged(self):
        self.identity()
        if self.active_molecule is not None:raise RuntimeError('Read staging after molecule commit')
        for row in self.db.execute('SELECT molecule_id,record_count,wire_sha256,uncompressed_bytes,dict_id,wire_frame FROM parsed_molecules ORDER BY molecule_id'):
            d=self.dicts['pm7_B']
            if row[4]!=d['dict_id']:raise ValueError('Staging dictionary ID differs')
            wire=self.zstd.decompress(row[5],d['data'],row[3])
            if digest(wire)!=row[2]:raise ValueError('Staging wire SHA differs')
            yield {'molecule_id':row[0],'record_count':row[1],'wire_sha256':row[2],
                'uncompressed_wire_bytes':row[3],'compressed_wire_bytes':len(row[5]),
                'payload':pickle.loads(wire)}
    def retire_staged_after_verified_parquet(self,references,molecule_ids=None,vacuum=False,preverified=False):
        self.identity()
        if self.active_molecule is not None:raise RuntimeError('Retire only after molecule commit')
        if not references:raise ValueError('Permanent parquet references required before retiring temporary wire')
        for ref in references:
            p=Path(ref['path']).absolute()
            if not p.is_relative_to(ROOT) or not p.is_file() or p.stat().st_size!=ref['bytes']:
                raise ValueError('Permanent parquet path/bytes binding differs')
            if not preverified and file_sha(p)!=ref['sha256']:raise ValueError('Permanent parquet SHA differs')
        # preverified is only for the owning exporter after its single complete
        # bitwise/row-count/SHA readback. Avoid re-hashing identical family files
        # once per lane; it never permits skipping exporter validation.
        export_id=digest(canonical(references))
        selected=[r[0] for r in self.db.execute('SELECT molecule_id FROM parsed_molecules')] if molecule_ids is None else list(map(str,molecule_ids))
        before=self.path.stat().st_size;self.db.execute('BEGIN IMMEDIATE')
        try:
            self.db.execute('INSERT OR IGNORE INTO parquet_exports VALUES(?,?,?)',(export_id,canonical(references).decode(),time.time()))
            for molecule in selected:
                if self.completion(molecule) is None:raise ValueError('Staged molecule lacks permanent completion receipt')
                self.db.execute('UPDATE completion_receipts SET export_id=? WHERE molecule_id=?',(export_id,molecule))
                self.db.execute('DELETE FROM parsed_molecules WHERE molecule_id=?',(molecule,))
            self.db.execute('COMMIT')
        except Exception:self.db.execute('ROLLBACK');raise
        self.last_vacuum_reserve_bytes=before if vacuum else 0
        if vacuum:self.db.execute('VACUUM')
        return {'temporary_molecules_retired':len(selected),'archive_bytes_before':before,
            'archive_bytes_after':self.path.stat().st_size,'vacuum_parallel_extra_reserve_per_lane_bytes':self.last_vacuum_reserve_bytes,
            'permanent_raw_and_completion_preserved':True,'permanent_parquet_touched':False,'export_id':export_id}
    def put_record(self,record,keep_output=None):
        self.identity()
        if self.active_molecule!=str(record['molecule_id']):raise RuntimeError('put_record requires owning whole-molecule transaction')
        calc=record['calc_type'];dictionary=self.dicts[calc];inputs=[];outputs=[]
        for f in record['files']:
            if f.get('role')=='input':inputs.append(f)
            elif f.get('role')=='output':outputs.append(f)
            else:raise ValueError('Explicit input/output file role required')
        if not inputs and not record.get('input_missing_reason'):raise ValueError('Complete input files or explicit source-input failure required')
        inp,inp_manifest=bundle(inputs);raw,raw_manifest=bundle(outputs)
        meta={k:v for k,v in record.items() if k!='files'}
        meta['input_file_manifest']=inp_manifest;meta['output_file_manifest']=raw_manifest
        metadata=canonical(meta);keep,reason=retention(record,self.policy,self.seed)
        if keep_output is not None:
            if bool(keep_output)!=keep:raise ValueError('Requested output retention differs from frozen policy')
        input_frame=self.zstd.compress(inp,dictionary['data']);raw_frame=self.zstd.compress(raw,dictionary['data']) if keep else None
        metadata_frame=self.zstd.compress(metadata,dictionary['data'])
        fingerprint=(bytes.fromhex(digest(inp)),bytes.fromhex(digest(raw)),record['source_status'],record['scope_status'],reason,digest(metadata))
        old=self.db.execute('SELECT input_sha256,raw_sha256,source_status,scope_status,retention_reason,metadata_frame,metadata_bytes FROM records WHERE record_id=? AND calc_type=?',(record['record_id'],calc)).fetchone()
        if old:
            old_meta=self.zstd.decompress(old[5],dictionary['data'],old[6])
            if tuple(old[:5])+(digest(old_meta),)!=fingerprint:raise ValueError('Completed archive key differs on resume')
        else:
            self.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
              record['record_id'],calc,self.active_molecule,dictionary['dict_id'],record['source_status'],record['scope_status'],reason,
              record.get('input_origin','ORIGINAL'),fingerprint[0],fingerprint[1],len(inp),len(raw),len(metadata),
              input_frame,raw_frame,metadata_frame,canonical(raw_manifest).decode()))
        return {'container_path':str(self.path),'record_id':record['record_id'],'calc_type':calc,'dict_id':dictionary['dict_id'],
            'input_sha256':digest(inp),'raw_sha256':digest(raw),'retention_reason':reason,'output_retained':keep,
            'input_frame_bytes':len(input_frame),'raw_frame_bytes':len(raw_frame) if raw_frame is not None else 0,
            'metadata_frame_bytes':len(metadata_frame),'logical_input_bytes':len(inp),'logical_raw_bytes':len(raw)}
    def append_molecule(self,molecule_id,raw_records):
        with self.molecule(molecule_id):return [self.put_record(record) for record in raw_records]
    def close(self):
        if self.active_molecule is not None:raise RuntimeError('Cannot close unfinished molecule transaction')
        if self.db is not None:self.db.close();self.db=None;self.zstd.close()

class ArchiveReader:
    def __init__(self,path,dictionary_manifest):
        self.path=Path(path).absolute();self.dicts=load_dictionaries(dictionary_manifest);self.zstd=Zstd()
        self.db=sqlite3.connect('file:'+quote(str(self.path))+'?mode=ro',uri=True)
        self.db.row_factory=sqlite3.Row;self.db.execute('PRAGMA query_only=ON')
        meta=dict(self.db.execute('SELECT key,value FROM metadata'))
        if meta['dictionary_manifest_sha256']!=file_sha(dictionary_manifest):raise ValueError('Reader dictionary manifest differs')
    def completion(self,molecule_id):
        row=self.db.execute('SELECT record_count,raw_calls,wire_sha256,receipt_json,export_id FROM completion_receipts WHERE molecule_id=?',(str(molecule_id),)).fetchone()
        if row is None:return None
        return {'molecule_id':str(molecule_id),'record_count':row[0],'raw_calls':row[1],
            'wire_sha256':row[2],'receipt':json.loads(row[3]),'export_id':row[4]}
    def iter_staged(self):
        for row in self.db.execute('SELECT molecule_id,record_count,wire_sha256,uncompressed_bytes,dict_id,wire_frame FROM parsed_molecules ORDER BY molecule_id'):
            d=self.dicts['pm7_B']
            if row[4]!=d['dict_id']:raise ValueError('Read-only staging dictionary ID differs')
            wire=self.zstd.decompress(row[5],d['data'],row[3])
            if digest(wire)!=row[2]:raise ValueError('Read-only staging wire SHA differs')
            yield {'molecule_id':row[0],'record_count':row[1],'wire_sha256':row[2],
                'uncompressed_wire_bytes':row[3],'compressed_wire_bytes':len(row[5]),'payload':pickle.loads(wire)}
    def get(self,record_id,calc_type):
        row=self.db.execute('SELECT * FROM records WHERE record_id=? AND calc_type=?',(record_id,calc_type)).fetchone()
        if row is None:raise KeyError((record_id,calc_type))
        d=self.dicts[calc_type]
        if row['dict_id']!=d['dict_id']:raise ValueError('Record dictionary ID differs')
        inp=self.zstd.decompress(row['input_frame'],d['data'],row['input_bytes'])
        if hashlib.sha256(inp).digest()!=row['input_sha256']:raise ValueError('Input bundle SHA differs')
        input_files,_=unbundle(inp);output_files=None
        if row['raw_frame'] is not None:
            raw=self.zstd.decompress(row['raw_frame'],d['data'],row['raw_bytes'])
            if hashlib.sha256(raw).digest()!=row['raw_sha256']:raise ValueError('Raw bundle SHA differs')
            output_files,manifest=unbundle(raw)
            if manifest!=json.loads(row['output_manifest']):raise ValueError('Output manifest differs')
        metadata=json.loads(self.zstd.decompress(row['metadata_frame'],d['data'],row['metadata_bytes']))
        return {'record_id':record_id,'calc_type':calc_type,'molecule_id':row['molecule_id'],
            'input_files':input_files,'output_files':output_files,'original_output_manifest':json.loads(row['output_manifest']),
            'output_retained':row['raw_frame'] is not None,'input_sha256':bytes(row['input_sha256']).hex(),
            'raw_sha256':bytes(row['raw_sha256']).hex(),'source_status':row['source_status'],'scope_status':row['scope_status'],
            'retention_reason':row['retention_reason'],'input_origin':row['input_origin'],'metadata':metadata}
    def close(self):self.db.close();self.zstd.close()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
    if args.check:
        ast.parse(Path(__file__).read_text());print(json.dumps({'status':'AST_PASS','LMDB_used':False,'QM_started':False}));return
    p.error('Import ArchiveWriter/ArchiveReader; no standalone scientific computation')
if __name__=='__main__':main()

