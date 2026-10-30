"""Exposure/eligibility and exact recovery; original values/masks never changed."""
import hashlib,json,math,numpy as np
from workflows.data_v1_final.export.family_export_day_v1 import contract as F,transport as T,store as Original
L=F.legacy();S=L['pipeline_v1.source'];CODEC=L['wire_v1.codec'];need=F.need
DISABLED='LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE'
def ordered_entries(arrays,tid,n,field_key=None):
    p='transport/'+tid+'/';count=len(arrays[p+'values']);i=arrays[p+'atom_i'];j=arrays[p+'atom_j'];ordinal=arrays[p+'ordinal']
    need(i.dtype.str==j.dtype.str==ordinal.dtype.str=='<i8' and np.array_equal(ordinal,np.arange(count,dtype='<i8'))
      and np.all(i>=0) and np.all(i<n) and np.all(j>=0) and np.all(j<n),'EXACT_ORDERED_ATOMS_AND_RETAINED_ORDINAL')
    a=T.decode_strings(arrays[p+'basis_i_utf8'],arrays[p+'basis_i_offsets']);b=T.decode_strings(arrays[p+'basis_j_utf8'],arrays[p+'basis_j_offsets'])
    channel=T.decode_strings(arrays[p+'channel_utf8'],arrays[p+'channel_offsets'])
    need(len(a)==len(b)==len(channel)==count,'BOTH_ORIGINAL_CHANNELS_NO_ALIAS_COLLAPSE')
    if field_key is None:
        keys=[k.split('/',1)[1] for k in arrays if k.startswith('reason_fields_source/')];need(len(keys)==1,'EXPLICIT_ORDERED_FIELD_KEY_WHEN_FAMILY_HAS_MULTIPLE_FIELDS');field_key=keys[0]
    reasons={scope:[int(v) for v in arrays['reason_fields_'+scope+'/'+field_key]] for scope in ('source','new','review')}
    indices=arrays['reason_leaf_index/'+field_key];codes=arrays['reason_leaf_code/'+field_key]
    return [{'src_atom':int(i[k]),'dst_atom':int(j[k]),'src_channel':a[k],'dst_channel':b[k],'entry_ordinal':k,
      'onsite':bool(i[k]==j[k]),'onsite_definition':'SAME_ATOM_ENDPOINTS_NOT_NATIVE_VALENCY_INFERENCE',
      'source_onsite_present':bool(arrays[p+'onsite_present'][k]),'source_onsite':bool(arrays[p+'onsite'][k]) if arrays[p+'onsite_present'][k] else None,
      'direction':[int(i[k]),a[k],int(j[k]),b[k]],'channel_present':bool(arrays[p+'channel_present'][k]),
      'source_channel':channel[k] if arrays[p+'channel_present'][k] else None,'value':arrays[p+'values'][k],
      'validity':bool(arrays['valid/'+p][k]),'reasons':dict(reasons,original_sparse_leaf_codes=[int(c) for ix,c in zip(indices,codes) if int(ix)==k])} for k in range(count)]
def batch_ordered(items):
    """Provider utility only: offset atoms, keep channels/entries/ordinals exact."""
    rows=[];offset=0;segments=[]
    for index,(n,entries) in enumerate(items):
        need(type(n) is int and n>0,'ACTUAL_RECORD_ATOM_COUNT');start=len(rows)
        for ordinal,entry in enumerate(entries):
            need(entry['entry_ordinal']==ordinal and 0<=entry['src_atom']<n and 0<=entry['dst_atom']<n,'ORIGINAL_LOCAL_ORDERED_ENTRY_ENDPOINTS')
            r=dict(entry);r.update(src_atom=entry['src_atom']+offset,dst_atom=entry['dst_atom']+offset)
            r['direction']=[r['src_atom'],entry['src_channel'],r['dst_atom'],entry['dst_channel']];rows.append(r)
        segments.append({'record_index':index,'atom_offset':offset,'n_atoms':n,'entry_start':start,'entry_stop':len(rows)});offset+=n
    return {'domain':'R73_ORDERED_RETAINED_DOUBLE_CHANNEL_ENTRY_V1','entries':rows,'segments':segments,'total_atoms':offset}
def unbatch_ordered(batch):
    result=[];previous=0
    for segment in batch['segments']:
        need(segment['entry_start']==previous and segment['entry_stop']>=previous,'EXACT_CONTIGUOUS_ENTRY_BATCH_SEGMENTS');entries=[]
        for ordinal,row in enumerate(batch['entries'][segment['entry_start']:segment['entry_stop']]):
            r=dict(row);r['src_atom']-=segment['atom_offset'];r['dst_atom']-=segment['atom_offset']
            need(r['entry_ordinal']==ordinal and 0<=r['src_atom']<segment['n_atoms'] and 0<=r['dst_atom']<segment['n_atoms'],'REVERSIBLE_OFFSET_ATOMS_ONLY')
            r['direction']=[r['src_atom'],r['src_channel'],r['dst_atom'],r['dst_channel']];entries.append(r)
        previous=segment['entry_stop'];result.append(entries)
    need(previous==len(batch['entries']),'NO_UNOWNED_BATCHED_ENTRY_SUFFIX');return result
def tensor_eligibility(target,arrays,geometry_id,member_geometry_ids,policy):
    tid=target['target_id'];values=arrays['values/'+tid];mask=arrays['valid/'+tid]
    need(target['kind']=='symmetric_tensor' and target['component_order']==['xx','xy','yy','xz','yz','zz']
      and values.shape==(6,) and mask.shape==(6,),'ONE_ORIGINAL_SIX_MEMBER_TENSOR')
    complete=bool(np.all(mask==1));same=len(member_geometry_ids)==6 and set(member_geometry_ids)=={geometry_id}
    state={'eligible':False,'complete6_original_valid':complete,'same_actual_geometry':same,'numeric_mask_changed':False,
      'actual_task_charge':policy.get('actual_task_charge'),'source_SMILES_formal_charge_used':False,'center':0,'one_target':True}
    scale=policy.get('scale');bound=(policy.get('scale_status')=='ACTUAL_TRAIN_POPULATION_SHA_BOUND' and type(scale) in (int,float)
      and not isinstance(scale,bool) and math.isfinite(scale) and scale>0 and policy.get('scale_reference') is not None
      and policy.get('scale_population_reference') is not None and policy.get('series_key') is not None)
    # This canonical target-local state never becomes a substitute value s=1.
    if not bound:state['status']=DISABLED
    elif policy.get('physical_policy_status')!='ACTUAL_TARGET_CONDITION_SOURCE_ENABLED':state['status']='LOSS_DISABLED_PHYSICAL_POLICY_UNBOUND_OR_DISABLED'
    elif not same:state['status']='LOSS_DISABLED_MEMBER_GEOMETRY_MISMATCH'
    elif not complete:state['status']='LOSS_DISABLED_INCOMPLETE_ORIGINAL_SIX'
    else:state.update(status='LOSS_ELIGIBLE_COMPLETE6',eligible=True,scale=float(scale))
    return state
def annotate(metadata,arrays,schema,policy,member_bindings):
    m=dict(metadata);m['D1_contract_version']='v3.0';m['actual_consumer_ACK']=False;m['full_Common_or_D6_release']=False
    m['ordered_entry_domains']={};m['loss_eligibility']={}
    for tid,t in schema.get('ordered_record_targets',{}).items():
        entries=ordered_entries(arrays,tid,m['n_atoms'],t['members'][0]['field_key']);m['ordered_entry_domains'][tid]={'version':'R73_ORDERED_RETAINED_DOUBLE_CHANNEL_ENTRY_V1',
          'entries':len(entries),'same_atom_endpoint_entries':sum(e['onsite'] for e in entries),'ordinal_scope':'ZERO_BASED_RETAINED_PARSER_LIST',
          'direction_and_duplicates_unchanged':True,'batch_rule':'OFFSET_ATOMS_ONLY_KEEP_CHANNELS_ORDER','onsite_semantics':'ATOM_EQUALITY_CLASSIFICATION_SOURCE_NATIVE_FLAG_SEPARATE'}
    for tid,t in schema.get('compiled',{}).get('physical_targets',{}).items():
        if any(x['registry_id']==674 for x in t['members']):m['loss_eligibility'][tid]=tensor_eligibility(t,arrays,m['export_record_id'],member_bindings[tid],policy.get(tid,{}))
    return m
def tensor_loss(predicted,target,state):
    need(state.get('eligible') is True and state.get('status')=='LOSS_ELIGIBLE_COMPLETE6' and state.get('scale',0)>0,'NO_LOSS_WHEN_SCALE_PHYSICAL_POLICY_OR_COMPLETE6_UNBOUND')
    e=(np.asarray(predicted,dtype='<f8')-np.asarray(target,dtype='<f8'))/state['scale'];need(e.shape==(6,),'EXACT_TENSOR6_LOSS')
    radius=float(np.sqrt(np.dot(e*e,np.asarray([1,2,1,2,2,1]))/9));return .5*radius*radius if radius<=1 else radius-.5
def original_cast_compare(expected,actual):return L['pipeline_v1.verify'].compare(expected,actual)
