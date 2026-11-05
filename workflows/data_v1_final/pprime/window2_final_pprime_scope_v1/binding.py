"""Physical geometry identity at producer boundaries; no content hashes."""
import json,math,sqlite3,zlib
from pathlib import Path

def binding(row,raw):
    return {'molecule_id':row['molecule_id'],'sprime_conf_idx':row['sprime_conf_idx'],
        'geometry_id':row['geometry_id'],'source_record_id':raw['source_record_id'],
        'atomic_numbers':raw.get('atomic_numbers',raw.get('z')),
        'positions_A':raw['coordinates'],'native_atom_order_sha256':raw.get('atom_order_sha256'),
        'uff_geometry_sha256':raw.get('geometry_sha256'),
        'source_path':row['source_path'],'source_row_index':row['source_row_index'],
        'source_format':row['source_format'],'source_member':row.get('source_member')}

def same_geometry(left,right):
    """Return (matched, evidence), using existing witnesses before F64 arrays.

    1e-12 abs/rel is a numeric alignment tolerance on original F64 coordinates,
    not a geometry deduplication criterion. Original labels remain unchanged.
    """
    if left.get('source_record_id')!=right.get('source_record_id'):
        return False,'NATIVE_ANCHOR_DIFFERS'
    for name in ('uff_geometry_sha256','uff_coordinate_sha256'):
        a,b=left.get(name),right.get(name)
        if a and b:return (a==b,'EXISTING_'+name.upper())
    a,b=left.get('native_atom_order_sha256'),right.get('native_atom_order_sha256')
    if a and b and a!=b:return False,'EXISTING_ATOM_ORDER_WITNESS_DIFFERS'
    z1,z2=left.get('atomic_numbers'),right.get('atomic_numbers')
    if z1 is not None and z2 is not None:
        if list(z1)!=list(z2):return False,'ORDERED_ATOMIC_NUMBERS_DIFFER'
    elif not (a and b and a==b):return None,'INSUFFICIENT_ORDER_EVIDENCE'
    xyz1,xyz2=left.get('positions_A'),right.get('positions_A')
    if xyz1 is None or xyz2 is None:return None,'NEED_EXISTING_BASE_F64_COORDINATES'
    if len(xyz1)!=len(xyz2):return False,'ATOM_COORDINATE_COUNT_DIFFERS'
    for p,q in zip(xyz1,xyz2):
        if len(p)!=3 or len(q)!=3:return False,'COORDINATE_SHAPE_DIFFERS'
        if any(not math.isfinite(float(v)) for v in (*p,*q)):return False,'COORDINATE_NONFINITE'
        if any(not math.isclose(float(x),float(y),rel_tol=1e-12,abs_tol=1e-12) for x,y in zip(p,q)):
            return False,'SOURCE_F64_COORDINATES_DIFFER'
    return True,'ORIGINAL_ORDERED_Z_OR_WITNESS_AND_F64_COORDINATES'

class BindingStore:
    """Necessary producer geometry bindings and same-pass original base cache."""
    def __init__(self,filename):
        self.db=sqlite3.connect(filename)
        self._decoded_base_file=None;self._decoded_base_rows=None
        self.db.executescript('''CREATE TABLE IF NOT EXISTS selected(mid TEXT,conf INTEGER,locator TEXT,raw TEXT,PRIMARY KEY(mid,conf));
            CREATE TABLE IF NOT EXISTS bases(path TEXT PRIMARY KEY,rows BLOB);
            CREATE TABLE IF NOT EXISTS candidates(gid TEXT PRIMARY KEY,mid TEXT,conf INTEGER,locator TEXT);
            CREATE INDEX IF NOT EXISTS candidate_key ON candidates(mid,conf);
            CREATE TABLE IF NOT EXISTS progress(stage TEXT PRIMARY KEY,value TEXT);''')
    def freeze_inputs(self,inputs):
        saved=self.db.execute("SELECT value FROM progress WHERE stage='frozen_inputs'").fetchone()
        if saved:
            if json.loads(saved[0])!=inputs:raise ValueError('SAME_FROZEN_BINDING_INPUTS_REQUIRED')
        else:
            if self.db.execute('SELECT 1 FROM selected LIMIT 1').fetchone():
                raise ValueError('UNBOUND_OLD_BINDINGS_REQUIRE_FRESH_OUTPUT')
            self.db.execute('INSERT INTO progress VALUES(?,?)',('frozen_inputs',json.dumps(inputs,sort_keys=True,separators=(',',':'))))
            self.db.commit()
    def selected_complete(self):
        return self.db.execute("SELECT 1 FROM progress WHERE stage='selected_complete'").fetchone() is not None
    def close_selected(self,records):
        # The marker and all selected bindings become durable in one commit.
        self.db.execute('INSERT INTO progress VALUES(?,?)',('selected_complete',json.dumps({'records':records})))
        self.db.commit()
    def candidate_ref_complete(self,ordinal,reference):
        saved=self.db.execute('SELECT value FROM progress WHERE stage=?',('candidate_ref:'+str(ordinal),)).fetchone()
        if saved:
            if json.loads(saved[0])!=reference:raise ValueError('SAME_FROZEN_CANDIDATE_REFERENCE_REQUIRED')
            return True
        return False
    def close_candidate_ref(self,ordinal,reference):
        self.db.execute('INSERT INTO progress VALUES(?,?)',('candidate_ref:'+str(ordinal),json.dumps(reference,sort_keys=True,separators=(',',':'))))
        self.db.commit()
    def candidate(self,row):
        previous=self.db.execute('SELECT locator FROM candidates WHERE gid=?',(row['geometry_id'],)).fetchone()
        value=json.dumps(row,allow_nan=False,separators=(',',':'))
        if previous:
            old=json.loads(previous[0])
            if any(old.get(k)!=row.get(k) for k in ('molecule_id','sprime_conf_idx','source_path','source_row_index','source_format')):
                raise ValueError('REGISTERED_GID_PHYSICAL_SOURCE_CONFLICT')
        else:self.db.execute('INSERT INTO candidates VALUES(?,?,?,?)',(row['geometry_id'],row['molecule_id'],row['sprime_conf_idx'],value))
    def add(self,row,raw):
        value=binding(row,raw)
        self.candidate(row)
        self.db.execute('INSERT INTO selected VALUES(?,?,?,?)',(row['molecule_id'],row['sprime_conf_idx'],json.dumps(row,allow_nan=False,separators=(',',':')),json.dumps(raw,separators=(',',':'))))
        return value
    def get(self,k):
        locator,raw=self.db.execute('SELECT locator,raw FROM selected WHERE mid=? AND conf=?',k).fetchone()
        return binding(json.loads(locator),json.loads(raw))
    def raw(self,k):return json.loads(self.db.execute('SELECT raw FROM selected WHERE mid=? AND conf=?',k).fetchone()[0])
    def base_rows(self,filename):
        if filename==self._decoded_base_file:return self._decoded_base_rows
        # All callers only inspect these rows. Drop the previous whole-file
        # decode before loading another; retain at most one decoded publication.
        self._decoded_base_file=None;self._decoded_base_rows=None
        found=self.db.execute('SELECT rows FROM bases WHERE path=?',(filename,)).fetchone()
        if found:values=json.loads(zlib.decompress(found[0]))
        else:
            import pyarrow.parquet as pq
            values=pq.read_table(filename).to_pylist()
            self.db.execute('INSERT INTO bases VALUES(?,?)',(filename,zlib.compress(json.dumps(values,allow_nan=False,separators=(',',':')).encode())))
        self._decoded_base_file=filename;self._decoded_base_rows=values
        return values
    def close(self):self.db.commit();self.db.close()

def cached_base_rows(database,filename):
    """None means this base has not previously been scientifically consumed."""
    found=database.execute('SELECT rows FROM bases WHERE path=?',(filename,)).fetchone()
    return None if found is None else json.loads(zlib.decompress(found[0]))
