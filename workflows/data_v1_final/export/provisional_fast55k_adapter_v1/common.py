"""Exact references and local immutable handles for the bounded real payload."""
from __future__ import annotations
import hashlib,json,os,sqlite3,stat
import csv,io
from pathlib import Path

HERE=Path(__file__).absolute().parent
DATA_REPO=HERE.parents[3]
VERSION='v1-pilot-provisional'
FAMILY='actual_pilot_provisional_fast55k_v1'
EVIDENCE=('joint_contract','release','registry','physical_mapping','provisional_population',
          'effective_train','heldout_exclusion','d4_statistics','geometry','codebook')

def need(ok,message):
    if not ok:raise ValueError(message)

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def digest(value):return hashlib.sha256(canonical(value)).hexdigest()

def rawref(value):
    need(type(value)is dict and set(value)=={'path','bytes','sha256'} and Path(value['path']).is_absolute()
      and type(value['bytes'])is int and value['bytes']>0 and type(value['sha256'])is str
      and len(value['sha256'])==64,'EXACT_NONEMPTY_REFERENCE_REQUIRED')
    return dict(value)

def frame(path):
    p=Path(path);s=p.lstat();need(stat.S_ISREG(s.st_mode) and not p.is_symlink()
      and s.st_uid==1278,'ACTUAL_MAIN_OWNED_REGULAR_INPUT')
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_uid)

def reference(path):
    p=Path(path).absolute();before=frame(p);h=hashlib.sha256()
    with p.open('rb')as f:
        for block in iter(lambda:f.read(4<<20),b''):h.update(block)
    need(frame(p)==before,'INPUT_CHANGED_DURING_SHA')
    return {'path':str(p),'bytes':before[2],'sha256':h.hexdigest()}

def read(reference_value,limit=256<<20):
    r=rawref(reference_value);p=Path(r['path']);need(r['bytes']<=limit,'BOUNDED_ACTUAL_DOCUMENT')
    before=frame(p);raw=p.read_bytes()
    need(len(raw)==r['bytes'] and hashlib.sha256(raw).hexdigest()==r['sha256'] and frame(p)==before,
      'EXACT_ACTUAL_DOCUMENT_SHA_AND_IDENTITY')
    value=json.loads(raw)
    # The producer's ordinary save() is JSON. Its explicit bit-pool envelope,
    # when present, is decoded by the original codec, never float32/string.
    if isinstance(value,dict) and value.get('schema')=='COMPACT_TYPED_BINARY_JSON_V3':
        from workflows.data_v1_final.labels.normalization_compact_runtime_v3.codec import binary_json_loads
        return binary_json_loads(raw.decode())
    return value

def write(path,value):
    p=Path(path);raw=canonical(value)+b'\n'
    with p.open('xb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return reference(p)

def local(path,root):
    p=Path(path).absolute();r=Path(root).absolute()
    need(str(r).startswith('/tmp/') and r in p.parents and p.resolve()==p
      and not any(q.is_symlink()for q in (p,*p.parents)),'ACTUAL_LOCAL_COPY_LOCATOR_ONLY')
    frame(p);return p

def sqlite_local(reference_value,root):
    r=rawref(reference_value);p=local(r['path'],root);need(frame(p)[2]==r['bytes'],'LOCAL_DATABASE_SIZE')
    db=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True);db.row_factory=sqlite3.Row
    return db

def compute_context():
    need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID') and
      int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=16,'REAL_MAIN_ALLOCATION_REQUIRED_NOT_LOGIN_OR_WINDOWS')

def binding_for(request):
    r=request['provisional_fast55k_binding'];rawref(r);b=read(r)
    need(b['schema']=='ACTUAL_PROVISIONAL_FAST55K_MODEL_BINDING_V1' and b['version']==VERSION,
      'EXACT_ACTUAL_PROVISIONAL_BINDING')
    return r,b

def actual_parent(account_reference,job_id):
    account=read(account_reference);r=account['raw_sacct_reference']
    need(account['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1'
      and account['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'and account['endpoint']=='202.38.247.57:22'
      and account['uid']==1278 and account['query_returncode']==0,'ACTUAL_MAIN_TERMINAL_ACCOUNTING')
    need(reference(r['path'])==r,'ACTUAL_RAW_ACCOUNTING_SHA')
    rows=[v for v in csv.DictReader(io.StringIO(Path(r['path']).read_text()),delimiter='|')if v['JobIDRaw']==str(job_id)]
    need(len(rows)==1 and all(rows[0][k]==v for k,v in{'UID':'1278','State':'COMPLETED','ExitCode':'0:0','AllocCPUS':'16'}.items()),
      'ACTUAL_EXACT_PARENT_C0_NOT_PRODUCER_BOOLEAN')
    declared=[v for v in account['parents']if str(v['job_id'])==str(job_id)]
    need(len(declared)==1 and declared[0]['state']=='COMPLETED'and declared[0]['exit_code']=='0:0'
      and declared[0]['alloc_cpus']==int(rows[0]['AllocCPUS'])
      and declared[0]['elapsed_raw_seconds']==int(rows[0]['ElapsedRaw']),'SAME_REAL_DECLARED_AND_RAW_PARENT')
    return account
