"""Disk BLOB fingerprint deduplication and binary64 result cache, scoped to ref."""
from __future__ import annotations
import hashlib
import json
import re
from collections import OrderedDict
from pathlib import Path
import sqlite3
import struct
from .engine import RECIPE,WIDTH,ALGORITHM


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()



def parent_sqlite_runtime(db,cache_bytes=None):
    """Optional session-local main page cache; no schema, transaction or worker change."""
    if cache_bytes is not None:
        if type(cache_bytes)is not int or cache_bytes<1024:
            raise ValueError('sqlite_cache_bytes must be an integer of at least1024 bytes')
        db.execute('PRAGMA main.cache_size=-'+str(cache_bytes//1024))
    return {'requested_main_cache_bytes':cache_bytes,
        'main_cache_size_pragma':db.execute('PRAGMA main.cache_size').fetchone()[0],
        'main_page_size_bytes':db.execute('PRAGMA main.page_size').fetchone()[0],
        'main_cache_spill_pragma':db.execute('PRAGMA main.cache_spill').fetchone()[0],
        'temp_cache_size_pragma':db.execute('PRAGMA temp.cache_size').fetchone()[0],
        'temp_store_pragma':db.execute('PRAGMA temp_store').fetchone()[0],
        'journal_mode':db.execute('PRAGMA main.journal_mode').fetchone()[0],
        'synchronous_pragma':db.execute('PRAGMA main.synchronous').fetchone()[0],
        'session_local_suggested_cache_not_preallocated_RSS':True}


def record_parent_sqlite(root,settings):
    """Close a small operational readback, never a scientific cache-scope input."""
    import uuid
    from ..common import dump_new,reference
    path=Path(root)/('sqlite_runtime_'+uuid.uuid4().hex+'.json')
    dump_new(path,settings);ref=reference(path)
    print(json.dumps({'sqlite_runtime_reference':ref,'sqlite_runtime':settings},sort_keys=True),flush=True)
    return ref

class QueryCache:
    def __init__(self,path,reference_manifest_sha256,reference_molecules,*,sqlite_cache_bytes=None):
        self.path=Path(path);self.n=reference_molecules
        if not isinstance(reference_manifest_sha256,str) or re.fullmatch('[0-9a-f]{64}',reference_manifest_sha256)is None or type(self.n)is not int or self.n<1:
            raise ValueError('ACTUAL_REFERENCE_SCOPE_REQUIRED')
        self.scope={'recipe':RECIPE,'reference_manifest_sha256':reference_manifest_sha256,
            'reference_molecules':self.n,'width_bytes':WIDTH,'result_definition':ALGORITHM}
        self.scope_sha=hashlib.sha256(canonical(self.scope)).hexdigest()
        self.db=sqlite3.connect(self.path,timeout=120)
        self.db.executescript('''PRAGMA journal_mode=DELETE;
          CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
          CREATE TABLE IF NOT EXISTS queries(id INTEGER PRIMARY KEY,fp BLOB UNIQUE,
            first_ordinal INTEGER,status INTEGER DEFAULT 0,score BLOB,reference_ordinal INTEGER,
            numerator INTEGER,denominator INTEGER,evaluated INTEGER,pruned INTEGER,result_sha TEXT);
          CREATE INDEX IF NOT EXISTS pending_queries ON queries(status,id);
          CREATE TABLE IF NOT EXISTS source_ingestions(source_id TEXT PRIMARY KEY,body TEXT);
          CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY,source_key TEXT UNIQUE);
          CREATE TABLE IF NOT EXISTS source_queries(source INTEGER,query INTEGER,PRIMARY KEY(source,query)) WITHOUT ROWID;
        ''')
        old=self.db.execute("SELECT value FROM meta WHERE key='scope'").fetchone()
        encoded=canonical(self.scope).decode()
        if old is None:self.db.execute("INSERT INTO meta VALUES('scope',?)",(encoded,));self.db.commit()
        elif old[0]!=encoded:
            self.db.close();raise ValueError('QUERY_CACHE_REFERENCE_OR_RECIPE_SCOPE_CHANGED')
        self.sqlite_runtime=parent_sqlite_runtime(self.db,sqlite_cache_bytes)
        self.recent=OrderedDict()

    def source(self,source_key):
        self.db.execute('INSERT OR IGNORE INTO sources(source_key) VALUES(?)',(source_key,))
        return self.db.execute('SELECT id FROM sources WHERE source_key=?',(source_key,)).fetchone()[0]

    def add(self,raw,ordinal,source=None):
        if not isinstance(raw,bytes) or len(raw)!=WIDTH or type(ordinal)is not int or ordinal<0:
            raise ValueError('EXACT_QUERY_BYTES_AND_SOURCE_ORDINAL_REQUIRED')
        identity=self.recent.get(raw)
        if identity is None:
            old=self.db.execute('SELECT id FROM queries WHERE fp=?',(raw,)).fetchone()
            identity=old[0] if old else self.db.execute('INSERT INTO queries(fp,first_ordinal) VALUES(?,?)',(raw,ordinal)).lastrowid
            self.recent[raw]=identity
            if len(self.recent)>4096:self.recent.popitem(last=False)
        else:self.recent.move_to_end(raw)
        if source is not None:self.db.execute('INSERT OR IGNORE INTO source_queries VALUES(?,?)',(source,identity))
        return identity

    def count(self):return self.db.execute('SELECT count(*) FROM queries').fetchone()[0]
    def source_count(self,source):return self.db.execute('SELECT count(*) FROM source_queries WHERE source=?',(source,)).fetchone()[0]
    def pending_count(self,source=None):
        if source is None:return self.db.execute('SELECT count(*) FROM queries WHERE status=0').fetchone()[0]
        return self.db.execute('SELECT count(*) FROM queries q JOIN source_queries s ON s.query=q.id WHERE s.source=? AND q.status=0',(source,)).fetchone()[0]

    def pending_batches(self,size,source=None):
        if type(size)is not int or size<1:raise ValueError('POSITIVE_QUERY_BATCH_SIZE')
        last=0
        while True:
            if source is None:rows=self.db.execute('SELECT id,fp FROM queries WHERE status=0 AND id>? ORDER BY id LIMIT ?',(last,size)).fetchall()
            else:rows=self.db.execute('SELECT q.id,q.fp FROM queries q JOIN source_queries s ON s.query=q.id WHERE s.source=? AND q.status=0 AND q.id>? ORDER BY q.id LIMIT ?',(source,last,size)).fetchall()
            if not rows:return
            last=rows[-1][0]
            yield rows

    def _digest(self,raw,result):
        return hashlib.sha256(bytes.fromhex(self.scope_sha)+raw+canonical(result)).hexdigest()

    def store(self,identity,raw,result):
        score=float(result['score']);num=result['score_numerator'];den=result['score_denominator']
        index=result['reference_ordinal'];evaluated=result['evaluated_references'];pruned=result['strictly_bound_pruned_references']
        if (type(index)is not int or not 0<=index<self.n or type(num)is not int or type(den)is not int
                or den<1 or not 0<=num<=den or type(evaluated)is not int or type(pruned)is not int
                or evaluated<0 or pruned<0 or evaluated+pruned!=self.n
                or struct.pack('<d',score)!=struct.pack('<d',num/den)):
            raise ValueError('INVALID_EXACT_NEAREST_RESULT')
        value={'score_hex':struct.pack('<d',score).hex(),'reference_ordinal':index,
            'score_numerator':num,'score_denominator':den,'evaluated_references':evaluated,
            'strictly_bound_pruned_references':pruned,'reference_molecules':self.n}
        digest=self._digest(raw,value)
        old=self.db.execute('SELECT fp,status,result_sha FROM queries WHERE id=?',(identity,)).fetchone()
        if old is None or old[0]!=raw:raise ValueError('QUERY_ID_AND_BYTES_CHANGED')
        if old[1]==1:
            if old[2]!=digest:raise ValueError('CONFLICTING_COMPLETE_EXACT_RESULT')
            return
        self.db.execute('UPDATE queries SET status=1,score=?,reference_ordinal=?,numerator=?,denominator=?,evaluated=?,pruned=?,result_sha=? WHERE id=?',
            (struct.pack('<d',score),index,num,den,evaluated,pruned,digest,identity))

    def lookup(self,raw):
        row=self.db.execute('SELECT status,score,reference_ordinal,numerator,denominator,evaluated,pruned,result_sha FROM queries WHERE fp=?',(raw,)).fetchone()
        if row is None or row[0]!=1:raise ValueError('EXACT_QUERY_RESULT_NOT_COMPLETE')
        status,packed,index,num,den,evaluated,pruned,digest=row
        value={'score_hex':packed.hex(),'reference_ordinal':index,'score_numerator':num,
            'score_denominator':den,'evaluated_references':evaluated,
            'strictly_bound_pruned_references':pruned,'reference_molecules':self.n}
        if self._digest(raw,value)!=digest:raise ValueError('CACHED_EXACT_RESULT_DIGEST_CHANGED')
        return {**value,'score':struct.unpack('<d',packed)[0]}

    def source_ingestion(self,source_id):
        row=self.db.execute('SELECT body FROM source_ingestions WHERE source_id=?',(source_id,)).fetchone()
        return None if row is None else json.loads(row[0])

    def close_ingestion(self,source_id,value):
        self.db.execute('INSERT INTO source_ingestions VALUES(?,?)',(source_id,canonical(value).decode()));self.db.commit()

    def commit(self):self.db.commit()
    def close(self):self.db.commit();self.db.close()
