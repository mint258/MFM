"""Exact diagnostic comparisons only; no graph choice, tolerance or chemistry."""
import collections
import json
import struct


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def describe(value):
    result={'value':value,'python_type':type(value).__name__}
    if type(value)is float:result.update(binary64_hex=struct.pack('>d',value).hex(),float_hex=value.hex())
    return result


def diagnose(events):
    reductions=[e for e in events if e['phase']=='MID_REDUCTION']
    if len(reductions)!=1:raise ValueError('Exactly one original reduction required')
    reduction=reductions[0]
    variants=[e for e in events if e['phase']=='GRAPH_RESULT']
    complete=[v for v in variants if v.get('status')=='FEATURES_DERIVED']
    identities=sorted({(v['features'].get('isomeric_smiles'),v['features'].get('full_key')) for v in complete},key=canonical)
    fields=sorted(set().union(*(set(v['features']) for v in complete))) if complete else []
    differences={}
    for key in fields:
        if key in ('source_smiles','ordinal','cid'):continue
        values=[dict(variant_id=v['variant_id'],present=key in v['features'],
          **describe(v['features'].get(key))) for v in complete]
        distinct={canonical([row['present'],row['value']]) for row in values}
        if len(distinct)>1:
            detail={'variants':values}
            if key=='generic_ring_systems' and all(type(row['value'])is list for row in values):
                detail['same_set_presence_despite_list_difference']=len({canonical(sorted(set(row['value']))) for row in values})==1
                detail['same_multiset_despite_order_difference']=len({canonical(sorted(collections.Counter(row['value']).items())) for row in values})==1
            differences[key]=detail
    return dict(original_reduction=reduction,graph_variant_results=variants,
      complete_variants=len(complete),unresolved_variants=len(variants)-len(complete),
      distinct_canonical_isomeric_SMILES_fullkey_pairs=[list(x) for x in identities],
      same_canonical_pair=len(identities)==1,exact_feature_field_differences=differences,
      reduced_projection_remains_HOLD=reduction['status']=='HOLD',
      graph_selected=False,tolerance_introduced=False,strict5_projection_created=False)
