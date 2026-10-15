"""Lossless registry-indexed Arrow family tables; original float64 values retained."""
from __future__ import annotations
import hashlib,json,math,os,struct
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
MISSING=object()
CELL=pa.struct([('registry_id',pa.int16()),('kind',pa.int8()),('f64',pa.float64()),
 ('i64',pa.int64()),('boolean',pa.bool_()),('text',pa.large_string()),
 ('array_f64',pa.large_list(pa.float64())),('array_i64',pa.large_list(pa.int64())),
 ('array_bool',pa.large_list(pa.bool_())),('shape',pa.list_(pa.int32()))])
SCHEMA=pa.schema([('record_id',pa.string()),('molecule_id',pa.string()),('calc_type',pa.string()),
 ('status',pa.string()),('source_status',pa.string()),('failure_code',pa.string()),
 ('total_atoms',pa.int32()),('elapsed_seconds',pa.float64()),('qm_cpu_seconds',pa.float64()),
 ('values',pa.large_list(CELL)),('numeric_issues',pa.list_(pa.int16())),('attempt_id',pa.int8()),('job_id',pa.int64()),('task_id',pa.string()),('lane',pa.int16())])
FAMILIES={'pm7_B':'pm7_neutral','pm7_cation':'pm7_ions','pm7_anion':'pm7_ions',
 'pm7_water':'pm7_solvents','pm7_octanol':'pm7_solvents',
 'xtb_singlepoint':'xtb_singlepoint','xtb_vipea':'xtb_vipea','xtb_vfukui':'xtb_vfukui',
 'xtb_ALPB_water':'xtb_alpb','xtb_ALPB_octanol':'xtb_alpb','xtb_fod':'xtb_fod',
 'xtb_perturbed_gradient':'perturbed'}
def wanted(entry):
    if entry['task'] in {'pm7_ESP','xtb_hessian','xtb_ohess'}:return False
    p=entry.get('source_path','').lower()
    return not(any(s in p for s in
       ('polar_blocks','static_polar_block','static_finite_field_tensors')))
def lookup(detail,path):
    parts=str(path).strip('/').replace('/','.').split('.')
    if parts and parts[0] in {'detail','details'}:parts=parts[1:]
    value=detail
    if parts and parts[0] not in detail and isinstance(detail.get('values'),dict):value=detail['values']
    for key in parts:
        if not isinstance(value,dict) or key not in value:return MISSING
        value=value[key]
    return value
def native(v):
    if hasattr(v,'detach'):return v.detach().cpu().tolist()
    if hasattr(v,'tolist'):return v.tolist()
    if isinstance(v,dict):return {str(k):native(x) for k,x in v.items()}
    if isinstance(v,(tuple,list)):return [native(x) for x in v]
    return v
def nonfinite(v):
    if isinstance(v,float):return not math.isfinite(v)
    if isinstance(v,dict):return any(nonfinite(x) for x in v.values())
    if isinstance(v,list):return any(nonfinite(x) for x in v)
    return False
def encode(registry_id,value):
    c={k:None for k in ('f64','i64','boolean','text','array_f64','array_i64','array_bool','shape')}
    c['registry_id']=int(registry_id)
    if value is MISSING:c['kind']=9;return c
    value=native(value)
    if value is None:c['kind']=0;return c
    if nonfinite(value):
        c['kind']=10;c['text']=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=True)
        return c
    if type(value) is bool:c['kind']=3;c['boolean']=value
    elif type(value) is int:c['kind']=2;c['i64']=value
    elif type(value) is float:c['kind']=1;c['f64']=value
    elif type(value) is str:c['kind']=4;c['text']=value
    elif isinstance(value,list) and value:
        import numpy as np
        try:
            a=np.asarray(value)
            if a.dtype.kind in 'fiub' and a.size:
                # Mixed numeric scalar kinds preserve their exact list types through JSON.
                def kinds(x):
                    return set().union(*(kinds(y) for y in x)) if isinstance(x,list) else {type(x)}
                k=kinds(value)
                if len(k)==1 and k <= {float,int,bool}:
                    typ=next(iter(k));c['kind']={float:5,int:6,bool:7}[typ]
                    c[{float:'array_f64',int:'array_i64',bool:'array_bool'}[typ]]=a.reshape(-1).tolist()
                    c['shape']=list(a.shape);return c
        except (ValueError,TypeError):pass
        c['kind']=8;c['text']=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    else:c['kind']=8;c['text']=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    return c
def decode(c):
    k=c['kind']
    if k==9:return MISSING
    if k==0:return None
    if k in (1,2,3,4):return c[{1:'f64',2:'i64',3:'boolean',4:'text'}[k]]
    if k in (8,10):return json.loads(c['text'])
    if k in (5,6,7):
        import numpy as np
        name={5:'array_f64',6:'array_i64',7:'array_bool'}[k]
        dtype={5:np.float64,6:np.int64,7:np.bool_}[k]
        return np.asarray(c[name],dtype=dtype).reshape(c['shape']).tolist()
    raise ValueError('Unknown registry cell kind')
def exact(a,b):
    if a is MISSING or b is MISSING:
        if a is not b:raise ValueError('Missing changed')
    elif type(a)!=type(b):raise ValueError('Scalar/container type changed')
    elif isinstance(a,dict):
        if a.keys()!=b.keys():raise ValueError('Keys changed')
        for k in a:exact(a[k],b[k])
    elif isinstance(a,list):
        if len(a)!=len(b):raise ValueError('Length changed')
        for x,y in zip(a,b):exact(x,y)
    elif isinstance(a,float):
        if struct.pack('>d',a)!=struct.pack('>d',b):raise ValueError('Float64 bits changed')
    elif a!=b:raise ValueError('Value changed')
def registry(path):
    result=json.loads(Path(path).read_text())
    entries=result['entries']
    ids=[e['registry_id'] for e in entries]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate registry IDs')
    return [e for e in entries if wanted(e)]
def task_row(record_id,molecule_id,calc_type,detail,entries,total_atoms):
    cells=[];issues=[]
    for e in entries:
        if e['task']!=calc_type:continue
        value=lookup(detail,e['source_path']);cell=encode(e['registry_id'],value)
        if cell['kind']!=10:exact(native(value) if value is not MISSING else value,decode(cell))
        else:issues.append(cell['registry_id'])
        cells.append(cell)
    source=detail.get('source_status',detail.get('status'))
    status=detail.get('scope_status',detail.get('status'))
    if issues and status=='SUCCESS':status='PROPERTY_FAILED'
    return {'record_id':str(record_id),'molecule_id':str(molecule_id),'calc_type':calc_type,
       'status':status,'source_status':source,'failure_code':detail.get('failure_code'),
       'total_atoms':int(total_atoms),'elapsed_seconds':detail.get('elapsed',detail.get('elapsed_seconds')),
       'qm_cpu_seconds':detail.get('qm_cpu_seconds'),'values':cells,'numeric_issues':issues}
def write_rows(rows,path,metadata=None):
    path=Path(path)
    if path.exists():raise FileExistsError('Permanent parquet cannot be overwritten: '+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    table=pa.Table.from_pylist(rows,schema=SCHEMA)
    if metadata:table=table.replace_schema_metadata({str(k).encode():str(v).encode() for k,v in metadata.items()})
    pending=path.with_name(path.name+'.pending')
    pq.write_table(table,pending,compression='zstd',compression_level=3,row_group_size=32768)
    with pending.open('rb') as f:os.fsync(f.fileno())
    os.replace(pending,path)
    return {'path':str(path),'bytes':path.stat().st_size,'rows':len(rows),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

# These are non-QM tables specified directly by the WP5 guide. Their schema
# references remain distinct from the 756-ID quantum parser registry.
COMMON=[('record_id',pa.string()),('molecule_id',pa.string()),('file_group',pa.int8()),
 ('attempt_id',pa.int8()),('job_id',pa.int64()),('task_id',pa.string())]
BASE_SCHEMA=pa.schema(COMMON+[
 ('source_path',pa.string()),('real_index',pa.int64()),('source_payload_sha256',pa.string()),
 ('new_role',pa.string()),('member_routine',pa.bool_()),('conformer_id',pa.int64()),
 ('atomic_numbers',pa.large_list(pa.int16())),
 ('positions_A',pa.large_list(pa.list_(pa.float64(),3))),
 ('bond_pairs',pa.large_list(pa.list_(pa.int32(),2))),
 ('bond_order_codes',pa.large_list(pa.int8())),
 ('old_stored_PM7_HOF_kcal_mol',pa.float64()),('new_PM7_HOF_kcal_mol',pa.float64()),
 ('new_PM7_HOF_valid',pa.bool_()),('Q02_delta_HOF_kcal_mol',pa.float64()),
 ('geometry_status',pa.string()),('source_native_geometry_sha256',pa.string()),('native_atom_order_sha256',pa.string()),('stored_bond_graph_sha256',pa.string())])
D20_SCHEMA=pa.schema(COMMON+[('schema_ref',pa.string()),('descriptor_names',pa.list_(pa.string())),
 ('values_float64',pa.list_(pa.float64(),20)),('valid_mask',pa.list_(pa.bool_(),20)),
 ('status',pa.string()),('issues',pa.list_(pa.string()))])
D3_SCHEMA=pa.schema(COMMON+[('schema_ref',pa.string()),('PMI1',pa.float64()),('PMI2',pa.float64()),
 ('PMI3',pa.float64()),('PBF_A',pa.float64()),('volume_A3',pa.float64()),('SASA_total_A2',pa.float64()),
 ('SASA_atom_A2',pa.large_list(pa.float64())),('status',pa.string()),('issues',pa.list_(pa.string()))])
QC_TASK=pa.struct([('calc_type',pa.string()),('status',pa.string()),('source_status',pa.string()),
 ('failure_code',pa.string()),('elapsed_seconds',pa.float64()),('predicted_seconds',pa.float64())])
QC_SCHEMA=pa.schema(COMMON+[('Q01_gradient_norm_kcal_mol_A',pa.float64()),
 ('Q02_delta_HOF_kcal_mol',pa.float64()),('cation_S2_minus_0p75',pa.float64()),
 ('anion_S2_minus_0p75',pa.float64()),('population_QC_json',pa.large_string()),
 ('task_statuses',pa.list_(QC_TASK)),('record_status',pa.string())])

def write_family_rows(rows,path,schema,metadata=None):
    path=Path(path)
    if path.exists():raise FileExistsError('Permanent family parquet cannot be overwritten: '+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    table=pa.Table.from_pylist(rows,schema=schema)
    if metadata:table=table.replace_schema_metadata({str(k).encode():str(v).encode() for k,v in metadata.items()})
    pending=path.with_name(path.name+'.pending')
    pq.write_table(table,pending,compression='zstd',compression_level=3,row_group_size=32768)
    with pending.open('rb') as f:os.fsync(f.fileno())
    os.replace(pending,path)
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):digest.update(block)
    return {'path':str(path),'bytes':path.stat().st_size,'rows':len(rows),'sha256':digest.hexdigest()}
