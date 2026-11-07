"""Small immutable metadata, strict queued startup, and bounded audit outputs."""
from __future__ import annotations
import hashlib, json, math, os, resource, socket, sqlite3, stat, time
from pathlib import Path

from .relocation import ROOT as PROJECT,resolved_path,resolved_reference,relocated_adapter_config
RUN = PROJECT
TASK_FAMILIES = {
 'pm7_B':'pm7_neutral','pm7_cation':'pm7_ions','pm7_anion':'pm7_ions',
 'pm7_water':'pm7_solvents','pm7_octanol':'pm7_solvents',
 'xtb_singlepoint':'xtb_singlepoint','xtb_vipea':'xtb_vipea','xtb_vfukui':'xtb_vfukui',
 'xtb_ALPB_water':'xtb_alpb','xtb_ALPB_octanol':'xtb_alpb','xtb_fod':'xtb_fod',
 'xtb_perturbed_gradient':'perturbed','D20':'D20','D3':'D3'}
TASKS = {name:i for i,name in enumerate(sorted(TASK_FAMILIES))}
ROLES = {'TRAIN':0,'VAL':1,'FULL':2}
OWNER = ('record_id','molecule_id','attempt_id','job_id','task_id')
RECORD_COLUMNS = ('record_ordinal','record_id','molecule_id','attempt_id','job_id',
                  'task_id','lane','total_atoms','new_role')
BOUNDARY = {
 'population_scope':'original_source_all_roles_no_common_filter',
 'new_masks_created':False,'labels_modified':False,'normalization_completed':False,
 'final_common_population_frozen':False,'guide_1_5_completed':False,
 'array_payload_length_checked':False,'json_payload_shape_checked':False,
 'native_program_print_precision_verified':False,
 'units_and_actual_frame_audit':'PENDING_SOURCE_EVIDENCE'}

def need(condition, message):
    if not condition: raise ValueError(message)

def load(path, limit=2<<20):
    p=resolved_path(path); need(p.stat().st_size<=limit,'SMALL_METADATA_LIMIT:'+str(p))
    return json.loads(p.read_text(encoding='utf-8-sig'))

def sha(path):
    h=hashlib.sha256()
    with resolved_path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def ref(path):
    p=resolved_path(path);return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)}

def identity(path):
    s=resolved_path(path).lstat();need(stat.S_ISREG(s.st_mode) and s.st_uid==os.getuid(),'REGULAR_OWNED_INPUT_REQUIRED')
    return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]

def require(pin, content=True):
    pin=resolved_reference(pin);p=Path(pin['path']);need(p.is_absolute(),'ABSOLUTE_INPUT_REQUIRED')
    st=identity(p);need(st[2]==pin['bytes'],'INPUT_SIZE_DIFFERS:'+str(p))
    if content:need(sha(p)==pin['sha256'],'INPUT_SHA_DIFFERS:'+str(p))
    return p

def small_ref(path):
    need(resolved_path(path).stat().st_size<=2<<20,'SMALL_PIN_LIMIT');return ref(path)

def new_root(path):
    p=Path(path).absolute();allowed=RUN/'artifacts/labels_payload512_readonly_v1'
    need(allowed in p.parents and not any(q.is_symlink() for q in (p,*p.parents)),'OWNED_EXTERNAL_NEW_OUTPUT_REQUIRED')
    p.mkdir(parents=True,exist_ok=False,mode=0o700);return p

def unique_bytes(root):
    seen=set();total=0;links={};counts={}
    for p in (Path(root),*Path(root).rglob('*')):
        s=p.lstat();need(s.st_uid==os.getuid() and (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)),'OUTPUT_OWNER_OR_TYPE')
        key=(s.st_dev,s.st_ino)
        if key not in seen:total+=s.st_size;seen.add(key)
        if stat.S_ISREG(s.st_mode):links[key]=s.st_nlink;counts[key]=counts.get(key,0)+1
    need(all(counts[k]==v for k,v in links.items()),'OUTPUT_EXTERNAL_HARDLINK');return total

def budget(root, cap, additional=0):
    used=unique_bytes(root);need(used+additional+(2<<20)<=cap,'OUTPUT_CAP_EXCEEDED');return used

def save(path, value, root=None, cap=None):
    raw=(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    if root is not None:budget(root,cap,len(raw))
    with Path(path).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return ref(path)

def sqlite_ro(path):
    p=resolved_path(path);db=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True)
    db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-16384');return db

def lookup_batch(db, ids):
    unique=list(dict.fromkeys(ids));result={}
    for start in range(0,len(unique),256):
        part=unique[start:start+256]
        sql='SELECT '+','.join(RECORD_COLUMNS)+' FROM records WHERE record_id IN ('+','.join('?' for _ in part)+')'
        for row in db.execute(sql,part):result[row[1]]=dict(zip(RECORD_COLUMNS,row))
    return result

def classify_owner(row, owner, quantum):
    if owner is None:return 'RECORD_NOT_IN_AUTHORITY'
    if any(row[k]!=owner[k] for k in OWNER):return 'NONLATEST_OWNER_TUPLE'
    if quantum:
        need(row.get('lane')==owner['lane'] and row.get('total_atoms')==owner['total_atoms'],'CANONICAL_LANE_OR_NATOM_DIFFERS')
    return 'CANONICAL'

def declared_shape(cell, atoms):
    kind=cell.get('kind')
    if kind in (0,9):return 'NULL' if kind==0 else 'ABSENT'
    if kind in (8,10):return 'UNOBSERVED_JSON_PAYLOAD'
    if kind not in (5,6,7):return 'SCALAR_CARRIER'
    shape=cell.get('shape')
    if not isinstance(shape,list) or len(shape)>8 or any(type(x) is not int or x<0 for x in shape):return 'INVALID_DECLARED_SHAPE'
    # Exact common fixed/N axes; other varying pair dimensions are not mislabeled N.
    axes=['N' if x==atoms else str(x) if x in (0,1,2,3,6,9) else 'OTHER' for x in shape]
    return '['+','.join(axes)+'];PAYLOAD_LENGTH_UNOBSERVED'

def scf_state(value):
    if value is None:return 'NULL'
    if type(value) is not int:return 'NONINTEGER'
    return 'POSITIVE' if value>0 else 'ZERO' if value==0 else 'NEGATIVE'

def compact_key(*parts):return json.dumps(parts,separators=(',',':'),ensure_ascii=False)

def report_flags(row):
    # Review-only observations; NONE of these bits is an invalid-label mask.
    flags=0
    if row.get('status')=='SUCCESS' and row.get('converged') is None:flags|=1
    if row.get('status')=='SUCCESS' and row.get('scf_iterations') is None:flags|=2
    if row.get('converged') is False:flags|=4
    if scf_state(row.get('scf_iterations')) in ('ZERO','NEGATIVE','NONINTEGER'):flags|=8
    if row.get('source_status') is not None and row.get('source_status')!=row.get('status'):flags|=16
    if row.get('numeric_issues'):flags|=32
    return flags
def legacy(config):
    """Delegate frozen function with only declared adapter locator relocation."""
    from workflows.data_v1_final.labels.streaming_v1.support import legacy as frozen_legacy
    return frozen_legacy(relocated_adapter_config(config))