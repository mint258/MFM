"""First same-FD opaque copy, immutable SQLite and inherited exact raw decoder."""
import hashlib,json,os,pathlib,sqlite3,stat
from urllib.parse import quote
from . import contract as C
from workflows.data_v1_final.pprime.causal15_main_v1.prepare import raw_reader
Parent=raw_reader()


def frame(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid,s.st_mode)
def expected(r):return tuple(r[k] for k in ('dev','ino','bytes','mtime_ns','ctime_ns','uid','mode'))


def verify(row):
    p=pathlib.Path(row['path']);C.Q.need(not any(x.is_symlink() for x in (p,*p.parents)) and frame(p.lstat())==expected(row),'EXACT_OBSERVED_CPU13_SOURCE_FRAME')
    return p


def copy_observed(row,path,output):
    p=verify(row);C.Q.need(stat.S_ISREG(row['mode']),'REGULAR_OBSERVED_SOURCE')
    with p.open('rb') as f:
        C.Q.need(frame(os.fstat(f.fileno()))==expected(row),'SAME_OPEN_OBSERVED_SOURCE_FD');body=f.read(C.O.RAW_CAP+1)
        C.Q.need(len(body)==row['bytes'] and frame(os.fstat(f.fileno()))==expected(row)==frame(p.lstat()),'SAME_FD_FULL_FIRST_SHA_STABLE_FRAME')
    ref=output.write(path,body)
    return body,ref,{'source_path':str(p),'source_observed_frame':row,'first_actual_CPU_sha256':hashlib.sha256(body).hexdigest(),
        'expected_whole_SHA_before_this_CPU':None,'new_byte_identical_snapshot_reference':ref}


class ImmutableReader(Parent):
    """Constructor-only storage seam; get/close are original method objects."""
    def __init__(self,path,archive,max_raw,max_meta):
        self.path=pathlib.Path(path);self.archive=archive;self.max_raw_bytes=max_raw;self.max_metadata_bytes=max_meta;self.max_frame_bytes=max_raw+(1<<20)
        C.Q.need(self.path.is_file() and not self.path.is_symlink(),'STABLE_OPAQUE_COPY_ONLY')
        self.db=sqlite3.connect('file:'+quote(str(self.path),safe='/')+'?mode=ro&immutable=1',uri=True)
        self.db.execute('PRAGMA query_only=ON');self.db.execute('BEGIN')


def keyed_raw(copy,archive,task,qa_id,original_raw=None):
    reader=ImmutableReader(copy,archive,C.O.RAW_CAP,C.O.RESULT_CAP)
    try:
        C.Q.need(reader.db.execute('PRAGMA integrity_check').fetchone()==('ok',),'CLOSED_SQLITE_INTEGRITY_REQUIRED')
        rid=task['case']['row']['record_id'];calc=task['case']['calc_type'];eid='causal15:4521766:'+qa_id
        C.Q.need(reader.db.execute('SELECT count(*) FROM raw').fetchone()==(1,),'EXACT_ONE_ORIGINAL_CALL_ROW')
        found=reader.db.execute('SELECT raw_sha256,raw_bytes FROM raw WHERE record_id=? AND calc_type=? AND execution_id=?',(rid,calc,eid)).fetchone()
        C.Q.need(found is not None,'EXACT_NATIVE_TASK_EXECUTION_KEY')
        if original_raw is not None:C.Q.need(found==(original_raw['raw_sha256'],original_raw['raw_bytes'])
            and original_raw['record_id']==rid and original_raw['calc_type']==calc and original_raw['execution_id']==eid
            and original_raw['raw_call_durable'] is True,'EXACT_ORIGINAL_RESULT_PER_CALL_RAW_PIN')
        retained=reader.get(rid,calc,eid,found[0],found[1])
        return retained,{'record_id':rid,'calc_type':calc,'execution_id':eid,'raw_sha256':found[0],'raw_bytes':found[1],
            'expected_SHA_basis':'ORIGINAL_PINNED_RESULT' if original_raw else 'ACTUAL_COMMITTED_SQLITE_ROW_NOT_MISSING_RESULT',
            'immutable_connection':True,'original_get_method_object':ImmutableReader.get is Parent.get}
    finally:reader.close()
