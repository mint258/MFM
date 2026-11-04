"""Source transport, not a new physical model: ordered r73 and native S bonds."""
from __future__ import annotations
import hashlib,json,numpy as np
from . import contract as C
L=C.legacy();S=L['pipeline_v1.source'];PAIR=L['pipeline_v1.source_v2'];MASK=L['pipeline_v1.masks'];WIRE=L['wire_v1.mapping']
NATIVE=None


def compile_targets(registry,mapping,*,require_final=True):
    C.need(require_final is True,'NO_CANDIDATE_MAPPING_AS_TRAINING_RELEASE')
    fields={f['field_key']:f for f in registry['fields'] if f['status']=='enabled'};special={};used=set();normal={}
    C.need(len({t['target_id'] for t in mapping['physical_targets']})==len(mapping['physical_targets']),'UNIQUE_TARGET_IDS_ACROSS_PHYSICAL_CONDITIONS')
    for t in mapping['physical_targets']:
        domain=(t['condition'],t['geometry_source'])
        if any(m['registry_id']==73 for m in t['members']):C.need(t.get('wire_kind')=='SOURCE_ORDERED_RECORDS_V1','R73_NEVER_ORDINARY_ATOM_PAIR')
        if t.get('wire_kind')!='SOURCE_ORDERED_RECORDS_V1':normal.setdefault(domain,[]).append(t);continue
        C.need(len(t['members'])==1 and t['members'][0]['registry_id']==73 and t['geometry_source'] in ('pm7','uff_sprime')
            and t['unit_status']=='VERIFIED' and t['unit'] and t['family'],'ONLY_EXPLICIT_FINAL_R73_TRANSPORT')
        if t['condition']=='Pprime':C.need(t['group']=='P' and t['geometry_source']=='uff_sprime' and registry['pprime']['computed_labels_available'] is True,'REAL_INDEPENDENT_PPRIME_R73_NOT_P_SUBSTITUTION')
        m=t['members'][0];f=fields[m['field_key']];key=(domain,m['field_key'])
        C.need(all(f.get(k)==m.get(k) for k in ('source_path','registry_id','component')) and f['family_v1_final']==t['family']
            and f['unit']==t['unit'] and f['group']==t['group'] and (not f.get('reference_frame') or f['reference_frame']['verification']=='VERIFIED')
            and key not in used,'EXACT_FROZEN_R73_DEFINITION_AND_ONCE_PER_CONDITION')
        used.add(key);special[t['target_id']]=t
    targets={};domain_counts={}
    for domain,rows in sorted(normal.items()):
        keys={m['field_key'] for t in rows for m in t['members']};structural=[]
        for t in rows:
            if t['kind'] in ('vector','symmetric_tensor') and t['mask_reduction']!='all_components':
                policy=C.meta(mapping['mask_policy_reference']);C.need(str(policy['status']).endswith('FROZEN') and policy['model_confirmation'] and policy['data_confirmation'],'REAL_JOINT_PARTIAL_POLICY_NOT_EXPORTER_LOSS_RULE')
                structural.append(dict(t,mask_reduction='all_components'))
            else:structural.append(t)
        # Original validation/math runs unchanged for each actual physical
        # condition. Reusing a property in Pprime is not duplicating a P record.
        subset=dict(registry,fields=[f for f in registry['fields'] if f['field_key'] in keys])
        checked=WIRE.preflight_registry(subset,dict(mapping,physical_targets=structural),require_final=True)
        C.need(set(checked['physical_targets'])=={t['target_id'] for t in rows},'ORIGINAL_PREFLIGHT_EXACT_CONDITION_TARGETS')
        for t in rows:
            for m in t['members']:
                key=(domain,m['field_key']);C.need(key not in used,'EACH_COMPONENT_ONCE_IN_ITS_ACTUAL_CONDITION');used.add(key)
            if any(m['registry_id']==674 for m in t['members']):C.need(t['kind']=='symmetric_tensor' and len(t['members'])==6 and tuple(t['component_order'])==WIRE.TENSOR6,'R674_ONE_REAL_TENSOR')
            targets[t['target_id']]=dict(t)
        domain_counts['/'.join(domain)]={'source_components':len(keys),'physical_targets':len(rows)}
    C.need(set(fields)=={key for _,key in used},'ALL_ENABLED_ORIGINAL_COMPONENTS_COVERED_NOT146_SCALAR_HEADS')
    return {'physical_targets':targets,'ordered_record_targets':special,'source_component_count':len(fields),
        'physical_target_count':len(targets)+len(special),'physical_condition_counts':domain_counts,
        'P_D_and_Pprime_values_masks_and_normalization_not_interchanged':True}

def exact_int64(value,shape):
    a=np.asarray(value)
    C.need(a.shape==shape and (a.size==0 or a.dtype.kind in 'iu'),'NATIVE_INDEX_MUST_BE_ORIGINAL_INTEGER_NOT_LOSSY_FLOAT_OR_BOOL')
    out=S.numeric_array(a,'<i8',shape)
    C.need(a.size==0 or np.array_equal(a,out),'INT64_TRANSPORT_EXACT_NO_OVERFLOW_OR_ROUNDING')
    return out

def strings(values):
    chunks=[];offset=[0]
    for value in values:
        C.need(type(value) is str,'ORIGINAL_BASIS_CHANNEL_MUST_BE_STRING');raw=value.encode('utf-8');chunks.append(raw);offset.append(offset[-1]+len(raw))
    return np.frombuffer(b''.join(chunks),dtype='|u1').copy(),np.asarray(offset,dtype='<i8')


def decode_strings(data,offset):
    C.need(data.dtype.str=='|u1' and offset.dtype.str=='<i8' and offset.ndim==1 and len(offset)>=1 and offset[0]==0
        and offset[-1]==len(data) and np.all(offset[1:]>=offset[:-1]),'EXACT_UTF8_OFFSETS_NO_GAP_OR_TRUNCATION')
    raw=data.tobytes();return [raw[int(a):int(b)].decode('utf-8') for a,b in zip(offset[:-1],offset[1:])]


def r73(row,spec,target,n,compact_loader,annotations):
    key=target['members'][0]['field_key'];selector=spec['components'][key];records=S.extract(row,selector['value'])
    state='PRESENT_ORDERED_RECORD_LIST'
    if records is None:
        compact=compact_loader(selector['compact']);fid=selector['compact']['field_id']
        C.need(selector.get('null_value_policy')=='EXPLICIT_NULL_TRANSPORT' and fid not in MASK.field_ids(compact['valid_fields']),
            'ORIGINAL_NULL_TRANSPORT_EXPLICIT_AND_MASKED_NOT_FAKE_EMPTY_VALUE')
        records=[];state='ORIGINAL_NULL_UNKNOWN_LAYOUT_NOT_EMPTY_SOURCE'
    C.need(type(records) is list and selector['record_index_base']==0,'ACTUAL_R73_ORDERED_LIST_ZERO_BASED_NO_REPAIR')
    names=selector['record_fields'];required={'atom_i','basis_i','atom_j','basis_j','value'}
    C.need(set(names)>=required and set(names)<=required|{'channel','onsite'},'EXPLICIT_SOURCE_RECORD_FIELDS_ONLY')
    for r in records:C.need(type(r) is dict and set(r)<=set(names.values()) and all(names[k] in r for k in required),'NO_R73_RECORD_FIELD_SILENT_DROP')
    count=len(records);tid=target['target_id'];prefix='transport/'+tid+'/'
    integer=lambda k:exact_int64([r[names[k]] for r in records],(count,))
    atoms_i,atoms_j=integer('atom_i'),integer('atom_j')
    C.need(np.all(atoms_i>=0) and np.all(atoms_i<n) and np.all(atoms_j>=0) and np.all(atoms_j<n),'R73_ENDPOINT_ATOMS_IN_NATIVE_SEQUENCE')
    values=S.numeric_array([r[names['value']] for r in records],'<f8',(count,))
    cs=selector['compact'];compact=compact_loader(cs);restored=MASK.restore(compact,cs['field_id'],count)
    result={prefix+'atom_i':atoms_i,prefix+'atom_j':atoms_j,prefix+'ordinal':np.arange(count,dtype='<i8'),
        prefix+'values':values,'valid/'+prefix:restored['valid']}
    for name in ('basis_i','basis_j'):
        data,offset=strings([r[names[name]] for r in records]);result[prefix+name+'_utf8']=data;result[prefix+name+'_offsets']=offset
    for name in ('channel','onsite'):
        present=[name in names and names[name] in r for r in records];result[prefix+name+'_present']=np.asarray(present,dtype='|u1')
        if name=='channel':
            data,offset=strings([r[names[name]] if p else '' for r,p in zip(records,present)]);result[prefix+name+'_utf8']=data;result[prefix+name+'_offsets']=offset
        else:
            C.need(all(not p or type(r[names[name]]) is bool for r,p in zip(records,present)),'SOURCE_ONSITE_BOOL_NOT_INFERRED')
            result[prefix+name]=np.asarray([int(r[names[name]]) if p else 0 for r,p in zip(records,present)],dtype='|u1')
    for scope,name in (('source','source_reason_groups'),('new','new_reason_groups'),('review','review_groups')):
        result['reason_fields_'+scope+'/'+key]=np.asarray(restored[name],dtype='<u2')
    result['reason_leaf_index/'+key]=np.asarray([x['leaf_index'] for x in restored['partial_leaf_reason_codes']],dtype='<i4')
    result['reason_leaf_code/'+key]=np.asarray([x['code'] for x in restored['partial_leaf_reason_codes']],dtype='<u2')
    annotations[tid]={'mode':'SOURCE_ORDERED_RECORDS_V1','member':key,'field_id':cs['field_id'],'source_record_count':count if state=='PRESENT_ORDERED_RECORD_LIST' else None,'source_container_state':state,
        'order_and_duplicates_preserved':True,'no_basis_or_atom_sort_no_mirroring_no_dedup':True,'onsite_not_inferred_from_atom_equality':True,
        'optional_absence_is_not_false_source_value':True}
    return result


def target_arrays(row,spec,target,n,*,compact_loader=None,annotations=None):
    if target.get('wire_kind')=='SOURCE_ORDERED_RECORDS_V1':return r73(row,spec,target,n,compact_loader,annotations)
    return PAIR.target_arrays(row,spec,target,n,compact_loader=compact_loader,annotations=annotations)


def native_bonds(pointer,z):
    global NATIVE
    if NATIVE is None:
        from workflows.data_v1_final.export.d5_inputs_builder_v1.geometry import originals
        NATIVE=originals(initialize=True)[0]
    from workflows.data_v1_final.export.d5_inputs_builder_v1.reader import native_record
    _,actual,_=native_record(pointer,NATIVE);raw=NATIVE.read(pointer)
    C.need(actual.tolist()==list(z),'SAME_ORIGINAL_NATIVE_S_ATOM_SEQUENCE')
    idx=NATIVE.plain(NATIVE.field(raw,'rdkit_bond_index'));order=NATIVE.plain(NATIVE.field(raw,'rdkit_bond_order')).reshape(-1)
    C.need(idx.shape==(2,len(order)),'ORIGINAL_NATIVE_S_BOND_SHAPE')
    pairs=exact_int64(idx,idx.shape);codes=exact_int64(order,order.shape)
    C.need(np.all(pairs>=0) and np.all(pairs<len(z)) and np.all(np.isin(codes,[1,2,3,4])),'ACTUAL_STORED_S_BOND_INDEX_AND_CODES')
    # The native reader/graph may deduplicate for RDKit. This transport uses the
    # actual raw arrays, preserving direction, duplicates and stored order.
    return {'native_bond_index':pairs,'native_bond_order':codes}


def family_schema(compiled,family,src,target_ids):
    targets={k:v for k,v in compiled['physical_targets'].items() if v['family']==family and v['geometry_source']==src and k in target_ids}
    transport={k:v for k,v in compiled['ordered_record_targets'].items() if v['family']==family and v['geometry_source']==src and k in target_ids}
    C.need(targets or transport,'NONEMPTY_ACTUAL_FAMILY_SOURCE_PARTITION')
    return {'kind':'labels','family':family,'mask_encoding':'field-set+sparse-leaf-v1',
        'compiled':dict(compiled,physical_targets=targets,ordered_record_targets={},physical_target_count=len(targets),source_component_count=sum(len(t['members']) for t in targets.values())), 'ordered_record_targets':transport}
