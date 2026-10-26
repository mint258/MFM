"""Lossless decoded scientific trees; no new masks, pooling or pair key changes."""
from __future__ import annotations
import hashlib, json, struct


def need(value, message):
    if not value: raise ValueError(message)


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def encode(value):
    """Native Python floats remain binary64 bits; all other types are explicit.

    Source Arrow widths/buffer bits are independently checked before this call.
    JSON number floats mean the frozen json.loads binary64 result, NOT native
    program precision. Object member order and every list ordinal are retained.
    """
    floats=[]
    def walk(v):
        if v is None: return ['n']
        if type(v) is bool: return ['b',v]
        if type(v) is int: return ['i',str(v)]
        if type(v) is float:
            i=len(floats);floats.append(v);return ['f64',i]
        if type(v) is str:return ['s',v]
        if type(v) is bytes:return ['bytes',v.hex()]
        if type(v) is list:return ['l',[walk(x) for x in v]]
        if type(v) is tuple:return ['t',[walk(x) for x in v]]
        if type(v) is dict:
            need(all(type(k) is str for k in v),'UNSUPPORTED_NONSTRING_OBJECT_KEY')
            return ['d',[[k,walk(x)] for k,x in v.items()]]
        raise ValueError('UNSUPPORTED_SCIENTIFIC_VALUE_TYPE:'+type(v).__module__+'.'+type(v).__name__)
    return dumps(walk(value)),floats


def decode(template, floats):
    used=[]
    def walk(n):
        tag=n[0]
        if tag=='n':return None
        if tag=='b':return n[1]
        if tag=='i':return int(n[1])
        if tag=='f64':used.append(n[1]);return floats[n[1]]
        if tag=='s':return n[1]
        if tag=='bytes':return bytes.fromhex(n[1])
        if tag in ('l','t'):
            values=[walk(x) for x in n[1]];return values if tag=='l' else tuple(values)
        if tag=='d':
            keys=[x[0] for x in n[1]];need(len(set(keys))==len(keys),'CACHE_OBJECT_DUPLICATE_KEY')
            return {k:walk(v) for k,v in n[1]}
        raise ValueError('UNKNOWN_CACHE_TREE_TAG:'+str(tag))
    result=walk(json.loads(template))
    need(sorted(used)==list(range(len(floats))),'CACHE_F64_POOL_NOT_EXACTLY_OWNED')
    return result


def signature(value):
    tree,values=encode(value);h=hashlib.sha256(tree.encode('utf-8'))
    for v in values:h.update(struct.pack('<d',v))
    return h.hexdigest()


def source_float_signature(batch, index, selected_rids=None):
    """Read original Arrow float buffers, including float32 NaN payloads.

    Does not use to_pylist to determine original width/bits. As-py float64
    equality is checked bitwise. Float32 raw bits are retained separately;
    source width is never inferred from Python float or native print precision.
    """
    import pyarrow as pa
    h=hashlib.sha256();counts={'32':0,'64':0};f32=[]
    def walk(a,i,path):
        if not a[i].is_valid:return
        typ=a.type
        if pa.types.is_floating(typ):
            width=typ.bit_width;need(width in (32,64),'UNSUPPORTED_SOURCE_FLOAT_WIDTH')
            size=width//8;start=(a.offset+i)*size;raw=bytes(memoryview(a.buffers()[1])[start:start+size])
            h.update(dumps([path,width]).encode('utf-8'));h.update(raw);counts[str(width)]+=1
            if width==64:
                need(struct.pack('<d',a[i].as_py())==raw,'ARROW_F64_AS_PY_CHANGED_ORIGINAL_BITS')
            else:f32.append({'path':path,'bits_le_hex':raw.hex(),'width':32})
        elif pa.types.is_struct(typ):
            for k in range(typ.num_fields):walk(a.field(k),i,path+[typ[k].name])
        elif pa.types.is_list(typ) or pa.types.is_large_list(typ):
            lo,hi=a.offsets[i].as_py(),a.offsets[i+1].as_py()
            for ordinal,j in enumerate(range(lo,hi)):
                if path==['values'] and selected_rids is not None:
                    child=a.values
                    if child.field('registry_id')[j].as_py() not in selected_rids:continue
                walk(a.values,j,path+[ordinal])
        elif pa.types.is_fixed_size_list(typ):
            lo=(a.offset+i)*typ.list_size
            for ordinal,j in enumerate(range(lo,lo+typ.list_size)):walk(a.values,j,path+[ordinal])
        elif (pa.types.is_integer(typ) or pa.types.is_boolean(typ) or pa.types.is_string(typ)
              or pa.types.is_large_string(typ) or pa.types.is_binary(typ) or pa.types.is_null(typ)):
            return
        else:raise ValueError('UNSUPPORTED_SOURCE_ARROW_TYPE:'+str(typ))
    for k,name in enumerate(batch.schema.names):walk(batch.column(k),index,[name])
    return {'source_buffer_bits_sha256':h.hexdigest(),'observed_float_width_counts':counts,
            'original_float32_bit_pool':f32,'native_program_precision':'UNKNOWN_NOT_INFERRED_FROM_STORAGE'}


def paths(field,value,atoms):
    """Only explicit existing layouts; keep ordered paths, never canonicalize keys."""
    leaf=field['source_path'].rsplit('.',1)[-1];comp=field['component'];level=field['level']
    if level=='molecule':return [[]]
    if leaf=='dipole_Debye':return [[['x','y','z'].index(comp)]]
    if leaf=='molecular_quadrupole_traceless_au':return [[['xx','xy','yy','xz','yz','zz'].index(comp)]]
    if leaf=='atomic_shell_population_e':return [[i,comp] for i in range(len(value))]
    if leaf=='fukui':return [[i,['f_plus','f_minus','f_radical'].index(comp)] for i in range(len(value))]
    compound={'enpart_one_center_eV':('values',['electron_electron','electron_nuclear','total']),
              'enpart_pairs_eV':('J_K_EE_EN_NN_C_total',['J','K','EE','EN','NN','C','total']),
              'super_heavy_atom_rows':('values',['Dn','De','charge_density_q_minus_Z'])}
    if leaf in compound:
        key,order=compound[leaf];return [[i,key,order.index(comp)] for i in range(len(value))]
    pair={'bond_orders':'value','wiberg_pairs':'value','sigma_pi_entries':'value','mulliken_overlap_population_pairs':'population_e'}
    if leaf in pair:return [[i,pair[leaf]] for i in range(len(value))]
    if level=='atom_vector':
        return ([[i,j] for i in range(atoms) for j in range(3)] if len(value)==atoms and isinstance(value[0],list)
                else [[i] for i in range(len(value))])
    if level=='atom':return [[i] for i in range(len(value))]
    raise ValueError('UNSUPPORTED_COMPONENT_PATH:'+field['field_key'])


def at(value,path):
    for key in path:value=value[key]
    return value


def scientific_cells(row,family,fields,common,extra_registry_ids=()):
    cells=[];decoded={};positions={};duplicates=set();rids={f['registry_id'] for f in fields}|set(extra_registry_ids)
    if family in ('D20','D3'):
        # Original graph scientific columns, not recomputed descriptors.
        keys=(['values_float64','valid_mask','descriptor_names'] if family=='D20' else
              ['PMI1','PMI2','PMI3','PBF_A','volume_A3','SASA_total_A2','SASA_atom_A2','issues'])
        return [{'native_family':family,'columns':{k:row.get(k) for k in keys}}],{}, {},set()
    for ordinal,cell in enumerate(row.get('values') or []):
        if not isinstance(cell,dict):
            cells.append({'original_list_ordinal':ordinal,'unidentified_cell':cell});continue
        rid=cell.get('registry_id')
        if rid not in rids:continue  # Explicit registry-declared scientific-field allowlist.
        item={'registry_id':rid,'original_list_ordinal':ordinal,'kind':cell.get('kind'),'declared_shape':cell.get('shape')}
        if cell.get('kind') in (8,10) and isinstance(cell.get('text'),str):
            def reject_duplicate_json_keys(pairs):
                keys=[k for k,v in pairs]
                if len(keys)!=len(set(keys)):
                    raise RuntimeError('UNSUPPORTED_DUPLICATE_JSON_OBJECT_KEYS_NO_LAST_WINS_CACHE')
                return dict(pairs)
            try:json.loads(cell['text'],object_pairs_hook=reject_duplicate_json_keys)
            except (ValueError,TypeError):pass  # Frozen decoder below retains the actual invalid raw CELL.
        try:
            value=common.decode_cell(cell)
            if value is common.MISSING:item['state']='ABSENT'
            else:item['state']='DECODED';item['decoded_scientific_value']=value
            if cell.get('kind') in (8,10):
                item['source_json_utf8_sha256']=hashlib.sha256(cell['text'].encode('utf-8')).hexdigest()
                item['json_numeric_semantics']='FROZEN_JSON_DECODER;NOT_NATIVE_PRINT_PRECISION'
        except (ValueError,TypeError,KeyError,OverflowError) as exc:
            value=common.MISSING;item.update(state='UNDECODABLE_RAW_CELL_PRESERVED',error=type(exc).__name__+':'+str(exc),raw_cell=cell)
        if rid in decoded:duplicates.add(rid)
        else:decoded[rid]=value;positions[rid]=len(cells)
        cells.append(item)
    return cells,decoded,positions,duplicates


def component_map(row,family,fields,common,decoded,positions,duplicates):
    result=[];native={}
    if family in ('D20','D3'):
        native={f['field_key']:(v,i,r) for f,v,i,r in common.task_components(row,family,fields)}
    for f in fields:
        rid=f['registry_id'];value=decoded.get(rid,common.MISSING)
        if family in ('D20','D3'):
            vals,indices,reason=native[f['field_key']]
            if family=='D20':p=[['columns','values_float64',common.D20_NAMES.index(f['source_path'])]] if vals else []
            else:p=[['columns',f['source_path']]+q for q in paths(f,row.get(f['source_path']),row['total_atoms'])] if vals else []
            cell_position=0
        else:
            vals,indices,reason=common.component_values(f,value,row['total_atoms'])
            if rid in duplicates:vals=[];indices=[];reason='DUPLICATE_SOURCE_CELL_NO_INVENTED_COMPONENT_SELECTION'
            p=[['decoded_scientific_value']+q for q in paths(f,value,row['total_atoms'])] if vals else []
            cell_position=positions.get(rid)
        need(len(p)==len(vals),'COMPONENT_PATH_LEAF_MASS_DIFFERS')
        # Independently verify exact types and binary64 values against frozen extraction.
        if vals:
            source=({'columns':{k:row.get(k) for k in ['values_float64','PMI1','PMI2','PMI3','PBF_A','volume_A3','SASA_total_A2','SASA_atom_A2']}}
                    if family in ('D20','D3') else {'decoded_scientific_value':value})
            need(all(signature(at(source,path))==signature(v) for path,v in zip(p,vals)),'FROZEN_COMPONENT_VALUE_PATH_BITS_DIFFER')
        result.append({'field_key':f['field_key'],'registry_id':rid,'component':f['component'],
                       'declaration':f['status'],'cell_position':cell_position,'ordered_leaf_paths':p,
                       'atom_indices':indices,'layout_reason':reason})
    return result


def cache_row(kind,owner,task_code,payload):
    template,values=encode(payload)
    return {'row_kind':kind,'record_ordinal':owner['record_ordinal'],'task_code':task_code,
            'record_id':owner['record_id'],'molecule_id':owner['molecule_id'],
            'tree_json':template,'values_float64':values,'scientific_signature':signature(payload)}


def verify_cache_row(row):
    value=decode(row['tree_json'],row['values_float64'])
    need(signature(value)==row['scientific_signature'],'CACHE_REOPEN_TYPED_ORDER_OR_BITS_CHANGED')
    return value
