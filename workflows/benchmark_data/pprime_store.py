"""One shared per-lane task/raw container, without result readback or new hashes."""
import json
import math
from pathlib import Path
import sqlite3
import struct
import zlib


def pack(value):
    def convert(x):
        if isinstance(x,float) and not math.isfinite(x):return {'__benchmark_f64__':struct.pack('<d',x).hex()}
        if isinstance(x,dict):return {str(k):convert(v) for k,v in x.items()}
        if isinstance(x,(list,tuple)):return [convert(v) for v in x]
        if hasattr(x,'tolist'):return convert(x.tolist())
        return x
    return zlib.compress(json.dumps(convert(value),separators=(',',':'),allow_nan=False).encode(),3)


def unpack(payload):
    def hook(x):
        if set(x)=={'__benchmark_f64__'}:return struct.unpack('<d',bytes.fromhex(x['__benchmark_f64__']))[0]
        return x
    return json.loads(zlib.decompress(payload),object_hook=hook)


class LaneStore:
    def __init__(self,path):
        self.path=Path(path)
        if self.path.exists():raise FileExistsError('Existing lane store is preserved')
        self.db=sqlite3.connect(self.path,isolation_level=None)
        self.db.execute('PRAGMA journal_mode=DELETE');self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''CREATE TABLE calls(record_id TEXT,calc_type TEXT,scope_status TEXT,
            output_retained INTEGER,detail BLOB,PRIMARY KEY(record_id,calc_type));
            CREATE TABLE outputs(record_id TEXT,calc_type TEXT,name TEXT,raw_bytes INTEGER,frame BLOB,
            PRIMARY KEY(record_id,calc_type,name));''')

    def __call__(self,metadata,files,keep,admit):
        if any(f['name'] in {'input.xyz','input.mop','native.inp'} or f.get('role')!='output' for f in files):
            raise ValueError('Input bodies cannot enter downstream raw containers')
        if files and not keep:raise ValueError('Ordinary success raw files must not be saved')
        encoded=pack(metadata)
        frames=[(f['name'],len(f['data']),zlib.compress(f['data'],3)) for f in files] if keep else []
        admit(2*(len(encoded)+sum(len(frame) for _,_,frame in frames))+1048576)
        rid,calc=metadata['record_id'],metadata['calc_type']
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.db.execute('INSERT INTO calls VALUES(?,?,?,?,?)',(rid,calc,metadata['scope_status'],int(keep),encoded))
            self.db.executemany('INSERT INTO outputs VALUES(?,?,?,?,?)',[(rid,calc,name,n,frame) for name,n,frame in frames])
            self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise
        return {'container_path':str(self.path),'record_id':rid,'calc_type':calc,
            'output_retained':bool(keep),'parsed_call_durable':True,'input_bodies_saved':False,
            'retention_reason':'FAILURE_OR_DETERMINISTIC_RECORD_AUDIT' if keep else 'ORDINARY_SUCCESS_PARSED_ONLY',
            'no_additional_content_hashes':True,'independent_readback':False}

    def close(self):self.db.close()
