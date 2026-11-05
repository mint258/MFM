"""Storage view of approved F64 r73 sums; no new aggregation or registry rows."""
import copy
import numpy as np


def augment_schema(schema):
    raw=[(tid,layout) for tid,layout in schema['target_layout'].items() if layout['array_name']=='r73_ordered']
    if len(raw)!=1:raise ValueError('ONE_ORIGINAL_R73_TARGET_REQUIRED')
    raw_tid,original=raw[0];field=next(f for f in schema['fields'] if f.get('registry_id')==73)
    schema['derived_r73_pair_targets']={};schema['derived_training_fields']=[]
    for name,fid in (('sigma',146),('pi',147)):
        tid='derived_r73_'+name+'_same_symmetry_pair_sum_v1';column=len(schema['columns']['pair_labels']);key=field['field_key']+'.'+name
        descriptor=dict(field,field_key=key,field_id=fid,target_id=tid,component=name+'_pair_sum',
            storage_precision='original F64 pure-block sum then one F32 cast',normalization_view_only=True,registry_unchanged=True)
        schema['columns']['pair_labels'].append(descriptor);schema['derived_training_fields'].append(descriptor)
        target=copy.deepcopy(original.get('mapping_target',{}));target.update(target_id=tid,kind='scalar',level='sparse_atom_pair',wire_kind='DERIVED_TRAINING_VIEW_ONLY')
        target['members']=[{k:descriptor[k] for k in ('field_key','registry_id','component','source_path') if k in descriptor}]
        schema['target_layout'][tid]={'array_name':'pair_labels','column_indices':[column],'target_id':tid,'kind':'scalar','level':'sparse_atom_pair','mapping_target':target}
        schema['derived_r73_pair_targets'][name]={'target_id':tid,'field_id':fid,'field_key':key,'column_index':column,'raw_target_id':raw_tid}
    schema['array_definitions']=copy.deepcopy(schema['array_definitions'])
    schema['array_definitions']['27']['shape'][-1]=len(schema['columns']['pair_labels'])
    schema['r73_training_target_precision']='Prefer pair_labels preaggregated original F64 pure-block sums (once F32); historical stores without these columns can only aggregate stored raw F32 K entries.'
    return schema


def bind_cached_pairs(arrays,entries,definitions):
    """Bind cached F64 values to exact directed pairs from the same raw K row."""
    cached={e['field_id']:e for e in entries if e['field_id']in(146,147)}
    if not cached:return
    if set(cached)!={146,147}:raise ValueError('BOTH_APPROVED_R73_DERIVED_FIELDS_REQUIRED')
    raw_tid=definitions['sigma']['raw_target_id'];prefix='transport/'+raw_tid+'/'
    if prefix+'atom_i' not in arrays:raise ValueError('DERIVED_R73_REQUIRES_THE_SAME_ORIGINAL_RAW_K_PAIR_ROWS')
    seen=set();pairs=[]
    for i,j in zip(arrays[prefix+'atom_i'],arrays[prefix+'atom_j']):
        pair=(int(i),int(j))
        if pair not in seen:seen.add(pair);pairs.append(pair)
    for name,definition in definitions.items():
        entry=cached[definition['field_id']];tid=definition['target_id']
        if len(entry['values_float64'])!=len(pairs) or len(entry['value_mask'])!=len(pairs):raise ValueError('CACHED_R73_F64_SUM_AND_ORIGINAL_PAIR_ORDER_MASS')
        if entry.get('pair_indices') is not None and entry['pair_indices']!=[list(p) for p in pairs]:raise ValueError('CACHED_R73_DIRECTED_PAIR_ORDER_DIFFERS')
        arrays['pairs/'+tid]=np.asarray(pairs,dtype='<i8').reshape((-1,2))
        arrays['values/'+tid]=np.asarray([np.nan if v is None else v for v in entry['values_float64']],dtype='<f8')
        arrays['valid/'+tid]=np.asarray(entry['value_mask'],dtype='u1')