"""Task-local composition of frozen science functions; no new scientific rules."""
from __future__ import annotations
import collections,hashlib,struct
from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import (
 cache_row,component_map,scientific_cells,source_float_signature,signature)
from workflows.data_v1_final.labels.payload_audit_v1.payload import evaluate
from workflows.data_v1_final.labels.streaming_v1 import compact
from workflows.data_v1_final.labels.size_cpu_v2.aggregate import pair_keys
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import TASKS,TASK_FAMILIES,need


def base_observations(row,owner):
    """Observe existing unusable base rows without imposing pilot eligibility."""
    out=[];z=row.get('atomic_numbers');xyz=row.get('positions_A')
    valid=(isinstance(z,list) and len(z)==owner['total_atoms'] and all(type(v) is int and 1<=v<=118 for v in z))
    if not valid:out.append('BASE_ATOMIC_NUMBERS_UNUSABLE_RETAINED_NOT_LABEL_MASK')
    if not(isinstance(xyz,list) and valid and len(xyz)==len(z) and all(isinstance(p,list) and len(p)==3 for p in xyz)):
        out.append('BASE_POSITION_SHAPE_UNUSABLE_RETAINED_NOT_LABEL_MASK')
    if valid:
        atom_sha=hashlib.sha256(b''.join(struct.pack('<q',v) for v in z)).hexdigest()
        if atom_sha!=row.get('native_atom_order_sha256'):out.append('BASE_NATIVE_ATOM_ORDER_SHA_REVIEW')
    if row.get('geometry_status')!='ORIGINAL_PM7_GEOMETRY':out.append('BASE_GEOMETRY_STATUS_REVIEW')
    return out


def project(row,batch,index,owner,source,provenance,work):
    """Exactly one already-canonical source row, never a synthetic 14-task row."""
    family=source['family'];stats=collections.defaultdict(collections.Counter);observed={}
    if family=='base_geometry':
        payload={'provenance':provenance,'original_geometry':row,
          'source_float_bits':source_float_signature(batch,index),
          'source_base_observations':base_observations(row,owner)}
        return cache_row('base',owner,255,payload),{},{}
    quantum=family not in ('D20','D3');task=row['calc_type'] if quantum else family
    need(task in TASKS and TASK_FAMILIES[task]==family,'CANONICAL_TASK_FAMILY_MUST_MATCH')
    row['total_atoms']=owner['total_atoms'];row['calc_type']=task
    fields=work['task_fields'][task];common=work['common'];extras=work['cfg']['extra_geometry_registry_ids'].get(task,[])
    rids={f['registry_id'] for f in fields}|set(extras)
    # All five functions below are direct imports of frozen implementations.
    cells,decoded,positions,duplicates=scientific_cells(row,family,fields,common,extras)
    mapping=component_map(row,family,fields,common,decoded,positions,duplicates)
    items,observations,issues,raw,scores=evaluate(row,family,fields,common,work['masks'],pair_keys,work['calibration'])
    bykey={o['field_key']:o for o in observations}
    for item in items:
        counter=stats[str(item['field_id'])];counter['records']+=1
        counter['source_valid_records']+=bool(any(item['source_value_mask']))
        counter['valid_records']+=bool(any(item['value_mask']))
        counter['newly_masked_records']+=any(a and not b for a,b in zip(item['source_value_mask'],item['value_mask']))
        counter['new_payload_structural_invalid_records']+=bykey[item['field_key']]['payload_structural_failure']
    for o in observations:
        observed[o['field_key']]={k:int(o[k]) for k in ('records','numeric_leaves','nonnumeric_or_nonfinite_leaves','zero_leaves','payload_structural_failure')}
    payload={'provenance':provenance,'task':task,'cells':cells,'component_map':mapping,
      'source_status_and_precision':{k:v for k,v in row.items() if k not in ('values','values_float64','valid_mask','descriptor_names')
        and k not in ('PMI1','PMI2','PMI3','PBF_A','volume_A3','SASA_total_A2','SASA_atom_A2')},
      'source_float_bits':source_float_signature(batch,index,rids if quantum else None),
      'original_compact_candidate':compact.encode(owner['record_ordinal'],TASKS[task],items),
      'field_observations':observations,'structural_reviews':issues,'raw_counts':raw,
      'scientific_values_changed':False,'candidate_masks_frozen':False}
    return cache_row('task',owner,TASKS[task],payload),{k:dict(v) for k,v in stats.items()},observed


def parity_signature(payload,kind):
    """Compare frozen512 values/ordered keys/source+new masks, never provenance.

    Unmatched512 statistical review flags are deliberately not an authority for
    this broader batch. Every other compact field and all scientific keys/bits
    remain in this comparison; raw order and original scalar types are kept.
    """
    if kind=='base':keys=('original_geometry','source_float_bits')
    else:keys=('task','cells','component_map','source_status_and_precision','source_float_bits',
               'field_observations','structural_reviews','raw_counts')
    value={k:payload[k] for k in keys}
    if kind!='base':
        candidate=payload['original_compact_candidate']
        value['source_and_new_mask']={k:v for k,v in candidate.items() if k!='review_groups'}
        statistical={compact.CODE[k] for k in ('ROBUST_Z_GT20_REVIEW_ONLY','ZERO_MAD_UNEQUAL_VALUE_REVIEW_ONLY','TRAIN_SCALE_UNDEFINED_REVIEW_ONLY')}
        value['source_review_groups']=[r for r in candidate['review_groups'] if r['code'] not in statistical]
    return signature(value)
