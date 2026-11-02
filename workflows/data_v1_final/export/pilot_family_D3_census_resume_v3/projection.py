"""Explicit original-CELL IO projection; values, masks and native records survive."""
import ast,base64,copy,hashlib,math,struct
import numpy as np
from . import contract as C
L=C.F.legacy();S=L['pipeline_v1.source'];MASK=L['pipeline_v1.masks']
from workflows.data_v1_final.labels import common as ORIGINAL
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec as K

def same_values(a,b):
    C.need(len(a)==len(b),'ORIGINAL_RAW_TYPED_COMPONENT_LENGTH')
    for x,y in zip(a,b):
        C.need((x is None and y is None) or (type(x)in(int,float) and type(y)in(int,float)
          and struct.pack('<d',float(x))==struct.pack('<d',float(y))),'ORIGINAL_RAW_TYPED_F64_OR_NONE_BITS')

def pairs(records,n):
    """Original ordinary dictionary endpoints, with no sorting or deduplication."""
    C.need(type(records)is list,'ORIGINAL_PAIR_RECORD_LIST')
    result=[]
    for row in records:
        C.need(type(row)is dict and all(type(row.get(k))is int and 0<=row[k]<n for k in ('i','j')),
          'EXACT_ORIGINAL_ORDINARY_I_J_DICTIONARY_LAYOUT')
        result.append([row['i'],row['j']])
    return result

def restored(compact,fid,length):return MASK.restore(compact,fid,length)

def nullable(values,valid):
    C.need(len(values)==len(valid),'EXACT_ORIGINAL_MASK_LEAF_COUNT')
    out=[]
    for value,enabled in zip(values,valid):
        C.need(value is not None or not enabled,'NONE_NEVER_BECOMES_VALID_FINITE_ZERO')
        out.append(np.nan if value is None else value)
    return out

def prepare(entries,compact,recipe,raw,n):
    """Call original component reader before any component index operation."""
    C.need(recipe['input_kind']=='ORIGINAL_REGISTRY_CELL_PARQUET'
      and recipe['projection_adapter']=='ORIGINAL_COMPONENT_READER_EXPLICIT_PAIR_AND_NULL_IO_V1','RAW_CELL_PROJECTION_ONLY')
    fields=[e['field'] for e in entries];byid={e['field_id']:e for e in entries}
    C.need(len(byid)==len(entries),'UNIQUE_ORIGINAL_TYPED_FIELD_IDS')
    cells={}
    for cell in raw.get('values') or []:
        C.need(cell['registry_id'] not in cells,'NO_DUPLICATE_ORIGINAL_REGISTRY_CELL');cells[cell['registry_id']]=cell
    row={};spec=copy.deepcopy(recipe);note={'native_projection':'ORIGINAL_TASK_COMPONENTS_V1_WITH_DIRECTIONAL_PAIR_IO',
      'original_native_cells_binary_json':{},'original_raw_component_reasons':{},'source_None_leaf_indices':{}}
    for f,values,indices,reason in ORIGINAL.task_components(raw,'REGISTRY_CELL',fields):
        fid=f['field_id'];entry=byid[fid];key=f['field_key'];selector=spec['components'][key]
        C.need(selector['compact']['field_id']==fid and selector['native_projection']=='ORIGINAL_TASK_COMPONENTS_V1',
          'EXACT_GENERATED_ORIGINAL_FIELD_SELECTOR_NOT_TASK_NAME_INFERENCE')
        same_values(values,entry['values_float64'])
        C.need(indices==entry['atom_indices'] or (entry['atom_indices'] is None and all(i is None for i in indices)),
          'ORIGINAL_RAW_TYPED_ATOM_INDEX_ORDER_NO_NATIVE_INDEX_DROPPED')
        native=S.decode_cell(cells.get(f['registry_id']))
        # A multi-component tensor/compound cell is retained once per target,
        # not once per member, without dropping any original dictionary item.
        native_key=str(f['registry_id']);native_payload=K.binary_json_dumps(native).encode('utf-8').hex()
        C.need(native_key not in note['original_native_cells_binary_json']
          or note['original_native_cells_binary_json'][native_key]==native_payload,'ONE_NATIVE_CELL_PER_REGISTRY_ID')
        note['original_native_cells_binary_json'][native_key]=native_payload
        note['original_raw_component_reasons'][key]=reason
        value_column='__native_field_'+str(fid);selector['value']={'column':value_column}
        # Ordered r73 uses the entire original parser list, not its numeric leaf projection.
        if f['registry_id']==73:
            C.need(f['component']=='value','R73_ONE_ORIGINAL_RECORD_LIST')
            if native is None:C.need(fid not in MASK.field_ids(compact['valid_fields']),'NULL_R73_CANNOT_BE_VALID')
            row[value_column]=native;continue
        if native is None or not values:
            dimensions=() if f['level']=='sparse_atom_pair' else S.shape(selector['shape'],n)
            count=0 if f['level']=='sparse_atom_pair' else math.prod(dimensions)
            mask=restored(compact,fid,count)
            C.need(fid not in MASK.field_ids(compact['valid_fields']) and not np.any(mask['valid']),
              'ABSENT_EMPTY_NULL_SOURCE_CANNOT_HAVE_VALID_WIRE_LEAF')
            row[value_column]=None;selector.pop('atom_indices',None)
            if f['level']=='sparse_atom_pair':row['__native_pairs_'+str(fid)]=np.empty((0,2),dtype='<i4')
        else:
            mask=restored(compact,fid,len(values));cooked=nullable(values,mask['valid'])
            note['source_None_leaf_indices'][key]=[i for i,v in enumerate(values) if v is None]
            row[value_column]=cooked[0] if f['level']in('molecule','molecule_vector','molecule_tensor') else cooked
            if f['level']=='sparse_atom_pair':
                row['__native_pairs_'+str(fid)]=np.asarray(pairs(native,n),dtype='<i4').reshape((-1,2))
                C.need(len(row['__native_pairs_'+str(fid)])==len(values),'PAIR_ENDPOINT_AND_PHYSICAL_VALUE_ORDINAL_PARITY')
            if selector.get('atom_indices'):
                C.need(all(type(i)is int and 0<=i<n for i in indices),'EXACT_SOURCE_SPARSE_ATOM_INDICES')
                row['__native_indices_'+str(fid)]=indices
    return row,spec,note

def projected_target(entries,typed,recipe,raw,n,target):
    from workflows.data_v1_final.export.family_export_day_v1 import transport as T
    compact=K.binary_json_loads(typed['compact_mask_json']);keys={m['field_key'] for m in target['members']}
    selected=[e for e in entries if e['field_key'] in keys]
    C.need({e['field_key'] for e in selected}==keys,'ALL_ORIGINAL_TARGET_MEMBERS_IN_TYPED_ROW')
    row,spec,note=prepare(selected,compact,recipe,raw,n)
    arrays=T.target_arrays(row,spec,target,n,compact_loader=lambda _:compact,annotations=note)
    return arrays,note

def source_proof():
    witness=C.meta(C.Q.pin(C.HERE/'source_revision2_origin.json'));results=[]
    C.need(witness['schema']=='BOUNDED_PILOT_FAMILY_D3_R2_SOURCE_ORIGIN_V1','EXACT_R2_SOURCE_WITNESS')
    for item in witness['unchanged_R1_modules']:
        raw=(C.HERE/item['file']).read_bytes()
        C.need(len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256'],'UNCHANGED_ENTIRE_R1_WORKER_STORE_VERIFY_OR_DOMAIN_SOURCE')
    for item in witness['exact_module_inverses']:
        raw=(C.HERE/item['file']).read_bytes();old=base64.b64decode(item['original_source_base64'],validate=True)
        C.need(len(raw)==item['new_bytes'] and hashlib.sha256(raw).hexdigest()==item['new_sha256']
          and len(old)==item['old_bytes'] and hashlib.sha256(old).hexdigest()==item['old_sha256'],
          'WHOLE_R1_R2_SOURCE_BYTES:'+item['file'])
        lo,tail=item['prefix_bytes'],item['suffix_bytes'];middle=base64.b64decode(item['old_delta_base64'],validate=True)
        restored=raw[:lo]+middle+raw[len(raw)-tail:]
        C.need(restored==old and ast.dump(ast.parse(restored),include_attributes=False)==ast.dump(ast.parse(old),include_attributes=False),
          'ONLY_EXACT_DECLARED_R2_MODULE_IO_INVERSE_NO_SKIPPED_FUNCTION:'+item['file']);results.append(item['file'])
    for item in witness['new_adapter_sources']:
        raw=(C.HERE/item['file']).read_bytes()
        C.need(len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256'],'EXACT_NEW_R2_CPU_CONFIGURATION_OR_PROJECTION_SOURCE')
    C.need(S is C.F.legacy()['pipeline_v1.source'] and MASK.restore is C.F.legacy()['pipeline_v1.masks'].restore,
      'DIRECT_ORIGINAL_DECODER_MASK_AND_ORDINARY_PAIR_OBJECTS')
    return {'status':'EXACT_R1_MODULE_BYTES_AST_INVERSE_AND_NEW_EXPLICIT_IO_ADAPTERS','modules':results,
      'scientific_functions_or_original_codecs_patched':False,'new_QM_UFF_calls':0}
