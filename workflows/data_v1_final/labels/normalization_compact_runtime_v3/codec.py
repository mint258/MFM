"""Compact bit-exact D4 numerical views, not native CELL/text reconstruction."""
import collections,hashlib,json,re,struct
from .contract import need
from . import bindings as B
from workflows.data_v1_final.labels.bounded_projection_v1.parts import CappedBuffer,publish_bytes


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def owner_signature(owner):return hashlib.sha256(canonical(owner)).digest()

BINARY_JSON_SCHEMA='COMPACT_TYPED_BINARY_JSON_V3'
ROW_FIELDS=('row_kind','record_ordinal','task_code','record_id','role_code','file_id','physical_row','row_group','row_within_group','owner_sha256',
 'field_ids','lengths','data_f64','present','atom_indices','indexed','index_modes','source_mask','value_mask','reasons_json','compact_mask_json','base_json','base_f64')
BINARY_FIELDS=('owner_sha256','data_f64','present','atom_indices','indexed','source_mask','value_mask','base_f64')


def binary_json_dumps(value):
    """Original explicit typed tree; bytes and float64 pools are never str/f32."""
    tree,pool=B.encode(value)
    return canonical({'schema':BINARY_JSON_SCHEMA,'tree_json':tree,'float64_le_hex':[struct.pack('<d',v).hex() for v in pool]}).decode()


def binary_json_loads(raw):
    need(type(raw) is str,'TYPED_BINARY_JSON_STRING_REQUIRED');body=json.loads(raw)
    need(type(body) is dict and set(body)=={'schema','tree_json','float64_le_hex'} and body['schema']==BINARY_JSON_SCHEMA
      and type(body['tree_json']) is str and type(body['float64_le_hex']) is list,'EXACT_VERSIONED_BINARY_TREE_ENVELOPE')
    need(all(type(v) is str and re.fullmatch('[0-9a-f]{16}',v) for v in body['float64_le_hex']),'EXACT_FLOAT64_BIT_POOL_HEX')
    out=B.decode(body['tree_json'],[struct.unpack('<d',bytes.fromhex(v))[0] for v in body['float64_le_hex']])
    need(binary_json_dumps(out)==raw,'CANONICAL_BINARY_TREE_AND_EXACTLY_OWNED_F64_POOL');return out


def row_chunks(row):
    """One deterministic framed wire representation for both size and SHA."""
    need(set(row)-{'view_sha256'}==set(ROW_FIELDS),'EXACT_TYPED_ROW_COLUMNS_NO_UNKNOWN_SUFFIX')
    for key in ROW_FIELDS:
        value=row[key];raw=value if type(value) is bytes else canonical(value)
        yield key.encode()+b'\0'+struct.pack('<Q',len(raw));yield raw


def row_signature(row):
    h=hashlib.sha256()
    for block in row_chunks(row):h.update(block)
    return h.digest()


def row_wire_bytes(row):return sum(len(block) for block in row_chunks(row))+len(row.get('view_sha256',b''))


def validate_row_buffers(row):
    need(set(row)==set(ROW_FIELDS)|{'view_sha256'},'EXACT_TYPED_ROW_COLUMNS')
    need(all(type(row[k]) is bytes for k in (*BINARY_FIELDS,'view_sha256')),'BINARY_ARROW_COLUMNS_KEEP_NATIVE_BYTES')
    need(len(row['owner_sha256'])==len(row['view_sha256'])==32 and len(row['base_f64'])%8==0,'EXACT_OWNER_VIEW_SHA_AND_BASE_F64_POOL')
    need(all(type(row[k]) is str for k in ('row_kind','record_id','reasons_json','compact_mask_json','base_json')),'EXACT_STRING_ROW_METADATA')
    for key,bits in (('record_ordinal',64),('task_code',8),('role_code',8),('file_id',32),('physical_row',64),('row_group',32),('row_within_group',64)):
        need(type(row[key]) is int and 0<=row[key]<1<<bits,'EXACT_NATIVE_UNSIGNED_ROW_INDEX:'+key)
    need(row['row_kind'] in ('task','base') and row['role_code'] in (0,1,2),'EXACT_ROW_KIND_AND_ROLE')
    need(all(type(row[k]) is list for k in ('field_ids','lengths','index_modes')),'EXACT_OWNED_FIELD_OFFSET_ARRAYS')
    fids,ns,modes=row['field_ids'],row['lengths'],row['index_modes'];reasons=json.loads(row['reasons_json'])
    need(type(reasons) is list and len(set(fids))==len(fids)==len(ns)==len(modes)==len(reasons),'OWNED_FIELD_OFFSET_AND_REASON_MASS')
    need(all(type(fid) is int and 0<=fid<146 for fid in fids) and all(type(n) is int and 0<=n<1<<32 for n in ns)
      and all(type(mode) is int and mode in (0,1) for mode in modes),'EXACT_FIELD_IDS_LENGTHS_AND_INDEX_MODES')
    total=sum(ns);need(len(row['data_f64'])==len(row['atom_indices'])==8*total and all(len(row[k])==total for k in ('present','indexed','source_mask','value_mask')),'OWNED_FLAT_BUFFERS_EXACTLY_EXHAUSTED')
    need(all(v in (0,1) for k in ('present','indexed','source_mask','value_mask') for v in row[k]),'EXACT_BITMAP_BYTES')
    mask=binary_json_loads(row['compact_mask_json']);need(type(mask) is dict,'ORIGINAL_MASK_OBJECT_RECOVERED')
    if row['row_kind']=='base':
        need(row['task_code']==255 and not fids and mask=={},'EXACT_BASE_ROW_SCOPE')
        pool=[struct.unpack_from('<d',row['base_f64'],i)[0] for i in range(0,len(row['base_f64']),8)];B.decode(row['base_json'],pool)
    else:
        need(0<=row['task_code']<14 and row['base_json']=='' and row['base_f64']==b'','EXACT_TASK_ROW_SCOPE')
        need(mask['record_ordinal']==row['record_ordinal'] and mask['task_code']==row['task_code'],'MASK_ORIGINAL_ROW_KEY')
        for key in ('in_scope_fields','source_valid_fields','valid_fields','all_leaves_valid_fields','newly_masked_fields'):B.compact.unpack(mask[key])
        need(B.compact.unpack(mask['in_scope_fields'])==sorted(fids),'MASK_FIELD_SET_AND_OWNED_ENTRIES')
        for key in ('source_reason_groups','new_reason_groups','review_groups'):
            for group in mask[key]:B.compact.unpack(group['fields'])
        offset=0
        for fid,n in zip(fids,ns):
            need(B.compact.restore_mask(mask,fid,n)==[bool(v) for v in row['value_mask'][offset:offset+n]],'PERSISTED_ORIGINAL_SPARSE_MASK_LEAF_PARITY');offset+=n
    return row

def pack_entries(items):
    fids=[];lengths=[];values=bytearray();present=bytearray();indices=bytearray();indexed=bytearray();modes=[];sm=bytearray();vm=bytearray();reasons=[]
    for e in items:
        n=len(e['values_float64']);need(len(e['source_value_mask'])==len(e['value_mask'])==n,'EXACT_ENTRY_MASK_MASS')
        fids.append(e['field_id']);lengths.append(n);idx=e['atom_indices'];modes.append(int(idx is not None))
        need(idx is None or len(idx)==n,'EXACT_NATIVE_INDEX_MASS')
        for j,v in enumerate(e['values_float64']):
            need(v is None or type(v) is float,'ORIGINAL_FLOAT64_OR_NONE_ONLY');present.append(int(v is not None));values.extend(struct.pack('<d',0.0 if v is None else v))
            x=None if idx is None else idx[j];need(x is None or type(x) is int,'NATIVE_OWNED_INDEX_TYPE');indexed.append(int(x is not None));indices.extend(struct.pack('<q',0 if x is None else x))
        need(all(type(v) is bool for v in e['source_value_mask']+e['value_mask']),'EXACT_BOOL_MASKS');sm.extend(e['source_value_mask']);vm.extend(e['value_mask'])
        reasons.append([e['source_reasons'],e['new_reasons'],e['review_reasons'],e.get('structural_review')])
    return dict(field_ids=fids,lengths=lengths,data_f64=bytes(values),present=bytes(present),atom_indices=bytes(indices),indexed=bytes(indexed),index_modes=modes,
      source_mask=bytes(sm),value_mask=bytes(vm),reasons_json=canonical(reasons).decode())


def unpack_entries(row,byid):
    out=[];offset=0;reasons=json.loads(row['reasons_json']);total=sum(row['lengths'])
    need(len(set(row['field_ids']))==len(row['field_ids'])==len(row['lengths'])==len(row['index_modes'])==len(reasons),'EXACT_ONCE_REAL_FIELDS_NO146_DICT_COPIES')
    need(len(row['data_f64'])==len(row['atom_indices'])==8*total and all(len(row[k])==total for k in ('present','indexed','source_mask','value_mask')),'OWNED_FLAT_BUFFERS_EXACTLY_EXHAUSTED')
    need(all(v in (0,1) for key in ('present','indexed','source_mask','value_mask') for v in row[key]),'EXACT_BITMAP_BYTES')
    for fid,n,mode,reason in zip(row['field_ids'],row['lengths'],row['index_modes'],reasons):
        need(fid in byid and type(n) is int and n>=0 and mode in (0,1),'EXACT_REGISTERED_FIELD_OFFSET');f=byid[fid]
        vals=[struct.unpack_from('<d',row['data_f64'],8*j)[0] if row['present'][j] else None for j in range(offset,offset+n)]
        idx=[struct.unpack_from('<q',row['atom_indices'],8*j)[0] if row['indexed'][j] else None for j in range(offset,offset+n)] if mode else None
        sr,nr,rr,extra=reason
        e={'field':f,'field_id':fid,'field_key':f['field_key'],'source_path':f['source_path'],'values_float64':vals,'atom_indices':idx,
          'source_value_mask':[bool(x) for x in row['source_mask'][offset:offset+n]],'value_mask':[bool(x) for x in row['value_mask'][offset:offset+n]],
          'source_reasons':sr,'new_reasons':nr,'review_reasons':rr}
        if extra is not None:e['structural_review']=extra
        out.append(e);offset+=n
    need(offset==total,'NO_UNOWNED_NUMERIC_SUFFIX');return out


def project(row,batch,index,owner,source,provenance,work):
    """Original parser/masks/evaluate; only numerical serialization changes."""
    if work.get('selection') is not None and owner['record_id'] not in work['selection']:return None,{},{}
    family=source['family'];base=family=='base_geometry';items=[];stats=collections.defaultdict(collections.Counter);observed={}
    if base:
        meta={k:row.get(k) for k in ('atomic_numbers','native_atom_order_sha256','source_payload_sha256','geometry_status')};tree,pool=B.encode(meta)
    else:
        task=row.get('calc_type',family);row['total_atoms']=owner['total_atoms'];row['calc_type']=task
        items,obs,issues,raw,scores=B.evaluate(row,family,work['task_fields'][task],work['common'],work['masks'],B.pair_keys,work['calibration'])
        for o in obs:
            observed[o['field_key']]={k:int(o[k]) for k in ('records','numeric_leaves','nonnumeric_or_nonfinite_leaves','zero_leaves','payload_structural_failure')}
        bykey={o['field_key']:o for o in obs}
        for e in items:
            s=stats[str(e['field_id'])];s['records']+=1;s['newly_masked_records']+=any(a and not b for a,b in zip(e['source_value_mask'],e['value_mask']))
            s['new_payload_structural_invalid_records']+=bykey[e['field_key']]['payload_structural_failure']
        tree='';pool=[]
    packed=pack_entries(items);out={'row_kind':'base' if base else 'task','record_ordinal':owner['record_ordinal'],'task_code':255 if base else B.TASKS[task],
      'record_id':owner['record_id'],'role_code':B.ROLES[owner['new_role']],'file_id':source['file_id'],'physical_row':provenance['physical_row_ordinal'],
      'row_group':provenance['row_group'],'row_within_group':provenance['row_within_group'],'owner_sha256':owner_signature(owner),**packed,
      'compact_mask_json':binary_json_dumps({} if base else B.compact.encode(owner['record_ordinal'],B.TASKS[task],items)),
      'base_json':tree,'base_f64':b''.join(struct.pack('<d',v) for v in pool)}
    out['view_sha256']=row_signature(out);return out,{k:dict(v) for k,v in stats.items()},observed


def schema(pa):
    return pa.schema([('row_kind',pa.string()),('record_ordinal',pa.uint64()),('task_code',pa.uint8()),('record_id',pa.string()),('role_code',pa.uint8()),
      ('file_id',pa.uint32()),('physical_row',pa.uint64()),('row_group',pa.uint32()),('row_within_group',pa.uint64()),('owner_sha256',pa.binary(32)),
      ('field_ids',pa.list_(pa.uint16())),('lengths',pa.list_(pa.uint32())),('data_f64',pa.large_binary()),('present',pa.binary()),('atom_indices',pa.large_binary()),
      ('indexed',pa.binary()),('index_modes',pa.list_(pa.uint8())),('source_mask',pa.binary()),('value_mask',pa.binary()),('reasons_json',pa.string()),
      ('compact_mask_json',pa.string()),('base_json',pa.string()),('base_f64',pa.binary()),('view_sha256',pa.binary(32))])


class TypedPart:
    def __init__(self,kind,task,cap,row_cap):
        import pyarrow as pa,pyarrow.parquet as pq
        self.pa=pa;self.kind=kind;self.task=task;self.row_cap=row_cap;self.stream=CappedBuffer(cap);self.writer=pq.ParquetWriter(self.stream,schema(pa),compression='zstd',use_dictionary=True)
        self.buffer=[];self.nbytes=0;self.rows=0;self.digest=hashlib.sha256();self.finished=False
    def add(self,row):
        need(not self.finished,'NO_ROWS_AFTER_PART_FINISHED');validate_row_buffers(row)
        need(row['row_kind']==self.kind and row['task_code']==self.task and row_signature(row)==row['view_sha256'],'EXACT_COMPACT_ROW_BITS_AND_TASK')
        size=row_wire_bytes(row);need(size<=self.row_cap,'UNCHANGED_64MIB_ROW_CAP_BINARY_FRAMED_MEASURE')
        self.buffer.append(row);self.nbytes+=size;self.rows+=1;self.digest.update(row['view_sha256'])
        if len(self.buffer)>=64 or self.nbytes>=8<<20:self.flush()
    def flush(self):
        if self.buffer:self.writer.write_table(self.pa.Table.from_pylist(self.buffer,schema=schema(self.pa)),row_group_size=64);self.buffer=[];self.nbytes=0
    def approximate_bytes(self):return self.stream.tell()+self.nbytes
    def finish(self,path):
        import pyarrow.parquet as pq
        need(not self.finished,'PART_FINISHED_ONCE');self.finished=True
        try:
            self.flush();self.writer.close();ref=publish_bytes(path,self.stream.getvalue());count=0;h=hashlib.sha256();src=pq.ParquetFile(path)
            try:
                for batch in src.iter_batches(batch_size=1,use_threads=False):
                    for row in batch.to_pylist():
                        validate_row_buffers(row);need(row['row_kind']==self.kind and row['task_code']==self.task and row_signature(row)==row['view_sha256'],'REOPEN_NUMERIC_BITS_NONE_INDEX_MASK_ROLE_CHANGED')
                        h.update(row['view_sha256']);count+=1
            finally:src.close()
            need(count==self.rows and h.digest()==self.digest.digest(),'COMPACT_STREAM_REOPEN_MASS_AND_DIGEST')
            return {'reference':ref,'row_kind':self.kind,'task_code':self.task,'rows':count,'typed_stream_sha256':h.hexdigest()}
        finally:self.stream.release()
