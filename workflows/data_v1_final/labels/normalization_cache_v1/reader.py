"""Exact logical CELL view of an accepted typed cache; no native-text claims."""
from __future__ import annotations
import json,math,struct
from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import decode,at
from workflows.data_v1_final.labels.streaming_v1 import compact

TASK_KEYS={'provenance','task','cells','component_map','source_status_and_precision',
 'original_compact_candidate','field_observations','structural_reviews','raw_counts'}
PARITY_KEYS=('record_ordinal','task_code','in_scope_fields','source_valid_fields','valid_fields',
 'all_leaves_valid_fields','newly_masked_fields','source_reason_groups','new_reason_groups','leaf_exceptions')


class CompatibilityGap(ValueError):pass


def need(ok,code):
    if not ok:raise CompatibilityGap(code)


def equal_bits(a,b):
    if type(a) is not type(b):return False
    if type(a) is float:return struct.pack('<d',a)==struct.pack('<d',b)
    if isinstance(a,dict):return list(a)==list(b) and all(equal_bits(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)):return len(a)==len(b) and all(equal_bits(x,y) for x,y in zip(a,b))
    return a==b


def projected_decode(template,pool,keys=TASK_KEYS,geometry_keys=None):
    """Select tagged subtrees and rebase refs; call the unchanged owned decoder.

    This does not compute the full source scientific signature again. Initial
    whole cache SHA, current file frame, and its accepted producer bit-reopen
    receipt bind the original pool. Rebased selected float objects retain bits.
    """
    top=json.loads(template);need(top[0]=='d','CACHE_ROOT_OBJECT_REQUIRED')
    names=[k for k,v in top[1]];need(len(names)==len(set(names)),'CACHE_TOP_DUPLICATE_KEY')
    selected=[]
    for key,node in top[1]:
        if key not in keys:continue
        if key=='original_geometry' and geometry_keys is not None:
            need(node[0]=='d','GEOMETRY_OBJECT_REQUIRED');node=['d',[[k,v] for k,v in node[1] if k in geometry_keys]]
        selected.append([key,node])
    values=[];indices=set()
    def rebase(node):
        tag=node[0]
        if tag=='f64':
            i=node[1];need(type(i) is int and 0<=i<len(pool) and i not in indices,'SELECTED_FLOAT_POOL_OWNERSHIP')
            indices.add(i);n=len(values);values.append(pool[i]);return ['f64',n]
        if tag in ('l','t'):return [tag,[rebase(v) for v in node[1]]]
        if tag=='d':return ['d',[[k,rebase(v)] for k,v in node[1]]]
        return node
    return decode(json.dumps(rebase(['d',selected]),separators=(',',':')),values)


def base_metadata(template):
    return projected_decode(template,[],{'provenance','original_geometry'},
      {'atomic_numbers','native_atom_order_sha256','source_payload_sha256','geometry_status'})


def cell_view(item,common):
    """Reconstruct only the frozen decoder's logical input, not original text."""
    need('unidentified_cell' not in item,'LEGACY_UNIDENTIFIED_CELL_REQUIRES_SOURCE_REVIEW')
    if item.get('state')=='UNDECODABLE_RAW_CELL_PRESERVED':return item['raw_cell']
    rid=item['registry_id'];kind=item['kind'];out={'registry_id':rid,'kind':kind,'shape':item['declared_shape']}
    if item.get('state')=='ABSENT':
        need(kind==9,'ABSENT_KIND_NOT_RECOVERABLE');return out
    need(item.get('state')=='DECODED' and 'decoded_scientific_value' in item,'MISSING_DECODED_CELL_AUTHORITY')
    value=item['decoded_scientific_value']
    if kind==0:need(value is None,'NULL_CELL_CHANGED')
    elif kind in (1,2,3,4):out[{1:'f64',2:'i64',3:'boolean',4:'text'}[kind]]=value
    elif kind in (5,6,7):
        def flatten(v):
            if isinstance(v,list):
                for x in v:yield from flatten(x)
            else:yield v
        out[{5:'array_f64',6:'array_i64',7:'array_bool'}[kind]]=list(flatten(value))
    elif kind in (8,10):out['text']=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=True)
    else:raise CompatibilityGap('UNSUPPORTED_RECOVERED_CELL_KIND:'+str(kind))
    need(equal_bits(common.decode_cell(out),value),'LOGICAL_CELL_ROUNDTRIP_TYPE_ORDER_OR_BITS_DIFFER')
    return out


def logical_source(payload,common):
    row=dict(payload['source_status_and_precision']);source=payload['provenance']['source_reference'];family=source['family']
    for issue in payload['structural_reviews']:
        need(issue.get('reason') not in {'DUPLICATE_REGISTRY_CELL_REVIEW','NULL_OR_UNIDENTIFIED_CELL_REVIEW'},
          'LEGACY_WOULD_STOP_ON_DUPLICATE_OR_UNIDENTIFIED_CELL')
    if family in ('D20','D3'):
        need(len(payload['cells'])==1 and payload['cells'][0].get('native_family')==family,'NATIVE_GRAPH_CELL_AUTHORITY')
        row.update(payload['cells'][0]['columns'])
    else:
        row['values']=[cell_view(cell,common) for cell in payload['cells']]
        ids=[cell['registry_id'] for cell in row['values']];need(len(ids)==len(set(ids)),'LEGACY_DUPLICATE_REGISTRY_CELL')
    row['calc_type']=payload['task'];row['total_atoms']=payload['provenance']['owner']['total_atoms']
    return row,family


def entries(payload,fields,common,masks,task_code):
    """Same frozen legacy extractor/rules, checked against independent pointers."""
    row,family=logical_source(payload,common);mapping={r['field_key']:r for r in payload['component_map']};items=[]
    need({f['field_key'] for f in fields}<=set(mapping),'CACHED_COMPONENT_MAP_INCOMPLETE')
    for field,values,indices,reason in common.task_components(row,family,fields):
        cm=mapping[field['field_key']];paths=cm['ordered_leaf_paths']
        need(len(paths)==len(values) and equal_bits(indices,cm['atom_indices']),'COMPONENT_LEAF_OR_OWNED_INDEX_MASS_DIFFERS')
        pointed=[] if not paths else [at(payload['cells'][cm['cell_position']],p) for p in paths]
        need(equal_bits(pointed,values),'COMPONENT_POINTER_AND_FROZEN_LEGACY_VALUES_DIFFER')
        _,sm,vm,sr,nr,rr=masks.source_value_mask(field,row,values,reason)
        items.append({'field':field,'field_id':field['field_id'],'field_key':field['field_key'],'source_path':field['source_path'],
          'values_float64':[float(v) if type(v) in (int,float) else None for v in values],
          'source_value_mask':sm,'value_mask':vm,'source_reasons':sr,'new_reasons':nr,'review_reasons':rr,
          'atom_indices':indices})
    masks.add_cross_field_checks(items,row)
    old=payload['original_compact_candidate'];fresh=compact.encode(payload['provenance']['owner']['record_ordinal'],task_code,items)
    for key in PARITY_KEYS:need(old[key]==fresh[key],'CACHED_CANDIDATE_AND_REGENERATED_MASK_DIFFER:'+key)
    return items


def finite_train(item,role,train_values):
    # Direct injected frozen function also makes the Role boundary explicit in fixtures.
    return train_values(role,item['values_float64'],item['value_mask'])
