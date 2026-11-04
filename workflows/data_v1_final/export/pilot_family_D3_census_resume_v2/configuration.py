"""Actual CPU bounded configuration construction; no full/joint publication."""
import collections,copy,hashlib,math
from pathlib import Path
from . import contract as C,io as I,domain as D,frame_mapping as M
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import originals as ORIGINALS
ORIGINAL=ORIGINALS.objects()[0]
from workflows.data_v1_final.export.family_export_day_v1 import transport as T
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec as K

SCHEMA='ROOT_BOUNDED_PILOT_D2_D3_CONFIGURATION_BUILD_REVIEW_V1'
MODE='CPU_MATERIALIZED_FROM_ACTUAL_D4_LIMITED_COMPONENTS'
TENSOR=('xx','xy','yy','xz','yz','zz')

def review(plan,bounded):
    ref=bounded['configuration_build_review_reference'];v=C.meta(ref)
    C.need(v['schema']==SCHEMA and v['status']=='APPROVED_EXACT_CPU_BOUNDED_CONFIGURATION_CONSTRUCTION'
      and v['reviewer']=='root' and v['pilot_acceptance_reference']==plan['pilot_acceptance_reference']
      and v['D1_design_policy_reference']==plan['D1_design_policy_reference']
      and v['D1_five_layer_reference']==plan['D1_five_layer_reference']
      and v['no_future_output_hash'] is True and v['scientific_grouping_and_original_masks_unchanged'] is True
      and v['not_final_Common_or_Model_ACK'] is True,'ACTUAL_ROOT_BOUNDED_CONFIG_SOURCE_AND_INPUT_REVIEW')
    C.need(v['configuration_builder_source_references'] and v['definition_authority_reference']
      and v['task_protocol_reference'] and v['source_references'],'EXACT_REVIEWED_BUILD_SOURCE_AND_PHYSICAL_DEFINITIONS')
    defs=C.meta(v['definition_authority_reference'])
    C.need(defs['schema']=='ROOT_BOUNDED_NATIVE_FIELD_DEFINITION_AUTHORITY_V1'
      and defs['status']=='APPROVED_EXACT_SOURCE_DEFINITIONS_NOT_FULL_RELEASE' and defs['reviewer']=='root'
      and defs['is_D1_design_only'] is False and defs['scientific_value_or_MID_arrays_present'] is False and defs['evidence_references'],
      'DESIGN_SELECTIONS_ARE_NOT_ACTUAL_UNIT_FRAME_DEFINITION_AUTHORITY')
    C.reference(v['base_registry_reference'])
    native_reference=C.Q.pin(M.POLICY);native=M.physical_policy(native_reference,plan['D1_design_policy_reference'])
    expected={str(C.HERE/n) for n in ('configuration.py','projection.py','frame_mapping.py','run.py')}
    C.need(expected<={r['path'] for r in v['configuration_builder_source_references']},'COMPLETE_EXPLICIT_CONFIGURATION_SOURCE_ENTRY_CLOSURE')
    small=C.unique([ref,v['definition_authority_reference'],v['task_protocol_reference'],native_reference,native['user_decision_reference'],
      *v['configuration_builder_source_references'],*v['source_references'],*defs['evidence_references']])
    return v,defs,small,[v['base_registry_reference']]

def target_identity(fields,condition):
    f=fields[0];grouped=f['level'] in ('molecule_vector','molecule_tensor')
    identity={'condition':condition,'geometry_source':'pm7','task':f['task'],'registry_id':f['registry_id'],
      'source_path':f['source_path'],'level':f['level'],'component':None if grouped else f['component']}
    raw=__import__('json').dumps(identity,sort_keys=True,separators=(',',':')).encode()
    return 'native_'+hashlib.sha256(raw).hexdigest(),identity

def resolve_definitions(definition,fields,element_basis,protocol,native_reference):
    """Root exact source rules expand on CPU field IDs; no numerical defaults."""
    from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import bindings as B
    _,physical=B.inventory({'fields':fields,'plan':{'element_basis':element_basis}})
    group={fid:g['key'] for g in physical for fid in g['field_ids']};out=copy.deepcopy(definition)
    out.setdefault('fields',{});out.setdefault('size_rules_by_field',{});out.setdefault('condition_by_task',{});out.setdefault('actual_task_charge_by_task',{})
    for f in fields:
        key=f['field_key'];d=out['fields'].get(key)
        if d is None:
            hits=[r for r in definition.get('source_rules',[]) if all(f.get(k)==v for k,v in r['match'].items())]
            C.need(hits,'MISSING_ROOT_PHYSICAL_SOURCE_RULE:'+key);rank=max(len(r['match']) for r in hits)
            hits=[r for r in hits if len(r['match'])==rank];C.need(len(hits)==1,'AMBIGUOUS_ROOT_PHYSICAL_SOURCE_RULE:'+key)
            d=copy.deepcopy(hits[0]['definition']);out['fields'][key]=d
        physical_definition=ORIGINAL.physical_semantics(f['group'],f['source_path'],f['level'],f['component'])
        if d['unit']=='ORIGINAL_DECLARED_NATIVE_UNIT':d['unit']=f['unit']
        if d['extensivity']=='ORIGINAL_DEFINITION_BASED_CLASS':d['extensivity']=physical_definition['extensivity']
        if d['reference_frame']=='ORIGINAL_NONAXIAL_DEFINITION_ONLY':
            C.need(physical_definition['reference_frame'] is None,'VECTOR_TENSOR_FRAME_NEEDS_EXPLICIT_ACTUAL_ROOT_APPROVAL');d['reference_frame']=None
        C.need(d['evidence_references'] and all(r in definition['evidence_references'] for r in d['evidence_references']),
          'FIELD_PHYSICAL_EVIDENCE_IS_IN_EXACT_REVIEWED_SOURCE_CLOSURE')
        if isinstance(d['reference_frame'],dict) and d['reference_frame'].get('verification')==M.ASSUMPTION:
            if d['reference_frame'].get('source_convention_policy_reference')=='ACTUAL_FROZEN_NATIVE30_SOURCE_POLICY':
                d['reference_frame']['source_convention_policy_reference']=native_reference
            M.frame_allowed(d['reference_frame'],native_reference)
            C.need(all(r in definition['evidence_references'] for r in d['reference_frame']['source_evidence_references']),
              'FRAME_SOURCE_EVIDENCE_IS_IN_EXACT_REVIEWED_SOURCE_CLOSURE')
        if key not in out['size_rules_by_field']:
            rule=copy.deepcopy(d['size_rule'])
            if 'series_key' in rule:
                for token,value in (('${field_id}',str(f['field_id'])),('${physical_group}',group.get(f['field_id'],'UNBOUND_PHYSICAL_GROUP'))):
                    rule['series_key']=rule['series_key'].replace(token,value)
            out['size_rules_by_field'][key]=rule
        task=f['task']
        if task not in out['condition_by_task']:
            C.need(definition['condition_rule']=='ORIGINAL_TASK_NAME','EXPLICIT_ROOT_TASK_CONDITION_BINDING_REQUIRED');out['condition_by_task'][task]=task
        if task not in out['actual_task_charge_by_task']:
            C.need(definition['charge_rule']=='ACTUAL_ORIGINAL_PROTOCOL_EXPLICIT_CHARGE_NO_SMILES','ORIGINAL_TASK_CHARGE_AUTHORITY_REQUIRED')
            if f['group']=='D':charge=0
            else:
                t=next(t for t in protocol['tasks'] if t['name']==task)
                if t['family']=='xtb':charge=int(t['args'][t['args'].index('--chrg')+1])
                else:
                    tokens=t['keywords'].split() if isinstance(t['keywords'],str) else t['keywords'];charges=[v for v in tokens if v.upper().startswith('CHARGE=')]
                    C.need(len(charges)<=1,'UNAMBIGUOUS_SOURCE_MOPAC_CHARGE');charge=int(charges[0].split('=',1)[1]) if charges else 0
            out['actual_task_charge_by_task'][task]=charge
    return out

def bound_registry(base,fields,definition,rhos,models,native_reference,*,native_pilot=False):
    enabled={f['field_key']:f for f in base['fields'] if f['status']=='enabled'}
    C.need(len(fields)==len(enabled)==146 and {f['field_key'] for f in fields}==set(enabled)
      and {f['field_id'] for f in fields}==set(range(146)),'EXACT_ACTUAL146_FIELD_IDS_NO_REENUMERATION')
    C.need(dict(collections.Counter(f['group'] for f in fields if f['level']=='molecule'))=={'P':43,'D':26}
      and sum(f['group']=='D' and f['source_path'].endswith('SASA_atom_A2') for f in fields)==1,
      'ACTUAL43P26D_PLUS_ATOM_SASA_NOT_FORCED42P27D')
    result=copy.deepcopy(base);out={f['field_key']:f for f in result['fields']}
    for f in fields:
        old=enabled[f['field_key']]
        C.need(all(old[k]==f[k] for k in ('registry_id','task','source_path','component','level','group')),
          'ACTUAL_TYPED_FIELD_SCHEMA_EQUALS_BASE_REGISTRY')
        d=definition['fields'][f['field_key']]
        unknown=native_pilot and M.molmr_unknown(f,d)
        C.need((d['unit_status']=='VERIFIED' or unknown) and d['unit']==f['unit'] and d['evidence_references']
          and d['numeric_transform']=='IDENTITY_NATIVE_STORED_VALUES','NO_GUESSED_UNIT_OR_VALUE_TRANSFORM')
        C.need(all(d[k+'_status'] in ('VERIFIED','NOT_APPLICABLE_WITH_ACTUAL_DEFINITION') for k in ('sign','basis')),
          'UNRESOLVED_SOURCE_SIGN_OR_BASIS_NOT_DESIGN_DEFAULT')
        frame=copy.deepcopy(d['reference_frame'])
        M.frame_allowed(frame,native_reference)
        family=ORIGINAL.family_for(f['group'],f['source_path'],f['level']);rule=definition['size_rules_by_field'][f['field_key']]
        if rule['method']=='ORIGINAL_VIEW_WEIGHTED_SPEARMAN':
            key=rule['series_key'];C.need(key in rhos,'ACTUAL_D4_ORIGINAL_RHO_SERIES_MISSING:'+key)
            if 'heat_of_formation' in f['source_path']:
                C.need(key==str(f['field_id'])+'/residual' and str(f['field_id']) in models,'HOF_SIZE_AFTER_ACTUAL_ELEMENT_REFERENCE')
            rho=rhos[key]['rho'];C.need(rho is None or type(rho)in(int,float) and math.isfinite(rho),'REAL_OR_EXPLICIT_UNDEFINED_RHO')
            if rho is not None and abs(rho)>=.95:family='size'
        else:
            C.need(rule['method']=='PHYSICAL_LOCAL_NOT_MOLECULE_SIZE_APPLICABLE' and f['level']!='molecule'
              and rule['definition_reference'],'NO_NEW_NONSCALAR_SIZE_FORMULA_OR_UNDEFINED_MOLECULE_RULE');rho=None
        physical=ORIGINAL.physical_semantics(f['group'],f['source_path'],f['level'],f['component'])
        physical['extensivity']=d['extensivity'];physical['definition_reference']=d['definition_reference']
        row=out[f['field_key']];row.update(physical);row.update(field_id=f['field_id'],family_v1_final=family,unit=d['unit'],reference_frame=frame,
          bounded_physical_definition=d,bounded_size_rule=dict(rule,rho=rho,abs_spearman_threshold=.95),
          scope_is_temporary_old_complete55k_not_final_Common=True)
        if unknown:row.update(unit_status=M.UNKNOWN_UNIT,physical_loss_status='DISABLED_UNIT_UNSPECIFIED',original_unit_text_unchanged=True)
    result.update(status='FROZEN_BOUNDED55K_METADATA_NOT_FINAL_COMMON_OR_TRAINING_RELEASE',
      definition_authority_scope='ROOT_BOUNDED_NATIVE_FIELD_DEFINITION_AUTHORITY_V1',full_D2_published=False,
      native30_policy_reference=native_reference,historical_192_independent_output_coordinates='UNKNOWN_PRESERVED')
    if native_pilot:result['bounded_order_capability']=C.NATIVE_MODE
    return result

def mapping(registry,definition):
    groups={}
    for f in registry['fields']:
        if f['status']!='enabled':continue
        key=(f['task'],f['registry_id'],f['source_path'],f['level'],None if f['level']in('molecule_vector','molecule_tensor') else f['component'])
        groups.setdefault(key,[]).append(f)
    result=[]
    for group in groups.values():
        f=group[0];d=definition['fields'][f['field_key']];condition=definition['condition_by_task'][f['task']]
        C.need(condition!='Pprime','NO_PPRIME_FROM_PM7_CONFIGURATION')
        kind={'molecule_vector':'vector','atom_vector':'vector','molecule_tensor':'symmetric_tensor'}.get(f['level'],'scalar')
        order=list(TENSOR) if kind=='symmetric_tensor' else ['x','y','z'] if f['level']=='molecule_vector' else None
        if order:
            by={g['component']:g for g in group};C.need(set(by)==set(order) and len(by)==len(group),'EXACT_ORIGINAL_FULL_PHYSICAL_COMPONENT_GROUP')
            group=[by[k] for k in order]
        C.need(len({g['family_v1_final'] for g in group})==1,'ROOT_SIZE_RULES_MUST_GIVE_ONE_PHYSICAL_TARGET_FAMILY')
        tid,identity=target_identity(group,condition)
        target={'target_id':tid,'native_target_identity':identity,'condition':condition,'geometry_source':'pm7','group':f['group'],
          'level':{'molecule_vector':'molecule','molecule_tensor':'molecule','atom_vector':'atom','sparse_atom_pair':'pair'}.get(f['level'],f['level']),
          'kind':kind,'unit':f['unit'],'unit_status':d['unit_status'],'family':f['family_v1_final'],
          'members':[{k:g.get(k) for k in ('field_key','registry_id','source_path','component')} for g in group]}
        if kind in ('vector','symmetric_tensor'):target['mask_reduction']='all_components'
        if order:target['component_order']=order
        if kind=='symmetric_tensor':target['storage']='symmetric6'
        if d['unit_status']==M.UNKNOWN_UNIT:
            C.need(len(group)==1 and registry.get('bounded_order_capability')==C.NATIVE_MODE and M.molmr_unknown(f,d),
              'EXACT_MOLMR_SINGLE_FIELD_DISABLED_UNIT_TARGET_NOT_A_GENERIC_UNKNOWN_UNIT_PATH')
            target.update(physical_loss_status='DISABLED_UNIT_UNSPECIFIED',loss_enabled=False,original_unit_text_unchanged=True,
              source_frame_assumption_applied=False,unit_authority_status='UNKNOWN_ORIGINAL_SOURCE_SCHEMA_NOT_A_FRAME_ASSUMPTION')
        if f['registry_id']==73:target['wire_kind']='SOURCE_ORDERED_RECORDS_V1'
        elif target['level']=='pair':
            target['pair_index_policy']=copy.deepcopy(d['pair_index_policy'])
            C.need(all(type(target['pair_index_policy'][k])is bool for k in ('directed','allow_self')),'ACTUAL_ROOT_ORDINARY_PAIR_POLICY')
        result.append(target)
    return {'status':'FROZEN','physical_targets':sorted(result,key=lambda r:r['target_id']),
      'scope':'BOUNDED55K_PM7_P_D_NOT_FINAL_COMMON_NOT_MODEL_ACK','full_D2_published':False,
      'native30_policy_reference':registry['native30_policy_reference'],
      **({'bounded_order_capability':C.NATIVE_MODE} if registry.get('bounded_order_capability')==C.NATIVE_MODE else {})}

def component_selector(f,definition):
    fid=f['field_id'];leaf=f['source_path'].split('.')[-1]
    dimensions=[] if f['level']in('molecule','molecule_vector','molecule_tensor') else ['n_atoms',3] if f['level']=='atom_vector' else ['n_pairs'] if f['level']=='sparse_atom_pair' else ['n_atoms']
    p={'shape':dimensions,'reshape':True,'compact':{'field_id':fid},'null_value_policy':'masked_nan'}
    if f['group']=='D':
        p['value']={'column':'field_'+str(fid)}
        if leaf=='SASA_atom_A2':p['atom_indices']={'column':'indices_'+str(fid)}
        return p
    p.update(value={'column':'__native_field_'+str(fid)},native_projection='ORIGINAL_TASK_COMPONENTS_V1',
      original_cell_selector={'column':'values','cell_registry_id':f['registry_id']})
    if f['registry_id']==73:
        p.update(record_index_base=0,record_fields={k:k for k in ('atom_i','basis_i','atom_j','basis_j','value','channel','onsite')},
          null_value_policy='EXPLICIT_NULL_TRANSPORT')
    elif f['level']=='sparse_atom_pair':p.update(pairs={'column':'__native_pairs_'+str(fid)},pair_index_base=0)
    elif leaf in ('enpart_one_center_eV','super_heavy_atom_rows'):
        p['atom_indices']={'column':'__native_indices_'+str(fid)}
        if leaf=='super_heavy_atom_rows':
            code=definition['fields'][f['field_key']]['missing_atom_reason_code']
            C.need(type(code)is int and 0<code<65535,'ROOT_ORIGINAL_NATIVE_ATOM_SCOPE_REASON_REQUIRED');p['missing_atom_reason_code']=code
    return p

def recipe(fields,mapped,definition,protocol_reference):
    by={f['field_key']:f for f in fields};tasks={}
    for t in mapped['physical_targets']:
        field=by[t['members'][0]['field_key']];name=field['task'];isD=field['group']=='D'
        tr=tasks.setdefault(name,{'targets':[],'components':{},'input_kind':'ORIGINAL_TYPED_FIELD_ENTRIES' if isD else 'ORIGINAL_REGISTRY_CELL_PARQUET',
          'projection_adapter':'ORIGINAL_COMPONENT_READER_EXPLICIT_PAIR_AND_NULL_IO_V1',
          'geometry_binding':'ORIGINAL_NATIVE_PAYLOAD_PM7_BASE' if isD else 'ACTUAL_WP5_PROGRAM_INPUT_DOUBLE_HASH',
          'actual_task_charge':definition['actual_task_charge_by_task'][name],
          'actual_charge_authority_reference':protocol_reference,'ordinary_target_condition':definition['condition_by_task'][name]})
        tr['targets'].append(t['target_id'])
        for m in t['members']:tr['components'][m['field_key']]=component_selector(by[m['field_key']],definition)
    C.need(len(tasks)==14 and sum(len(t['components']) for t in tasks.values())==146,'ALL14_TASKS146_COMPONENTS_NO_OMISSION')
    return {'schema':'BOUNDED_PILOT_ORIGINAL_FAMILY_PROJECTION_RECIPE_V2','ordinary_PM7_only':True,
      'projection_adapter':'ORIGINAL_COMPONENT_READER_EXPLICIT_PAIR_AND_NULL_IO_V1','tasks':tasks}

def policies(mapped,report,definition,population_reference,fields,element_basis,numeric_references,native_reference):
    from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import bindings as B
    _,physical=B.inventory({'fields':fields,'plan':{'element_basis':element_basis}})
    bykey={f['field_key']:f for f in fields}
    native=M.physical_policy(native_reference)
    off=next(r for r in native['xtb_singlepoint_rules'] if r['selector']=='REGISTRY674_ALL_SYMMETRIC6_CONDITIONS')
    scales={g['physical_group']:g['loss_recipe_candidate'] for g in report['groups']};out={}
    for t in mapped['physical_targets']:
        f=t['members'][0];d=definition['fields'][f['field_key']]
        value={'physical_policy_status':d.get('physical_policy_status','DISABLED_PENDING_ACTUAL_TARGET_REVIEW'),
          'physical_policy_evidence_references':d.get('physical_policy_evidence_references',[]),
          'scale_status':'NOT_R674_TARGET_LOCAL_SCALE_DOMAIN','original_numeric_statistics_reference':numeric_references[0],
          'scope':'BOUNDED55K_NOT_MODEL_TRAINING_ACK','native30_policy_reference':native_reference,
          'historical_192_independent_output_coordinates':'UNKNOWN_PRESERVED'}
        charge=definition['actual_task_charge_by_task'][bykey[f['field_key']]['task']]
        source_field=bykey[f['field_key']]
        if source_field['task'].startswith('xtb_') and charge!=0 and source_field['source_path'].split('.')[-1] in ('dipole_Debye','molecular_quadrupole_traceless_au'):
            value.update(physical_policy_status='DISABLED_PER_USER_5A_FALLBACK',actual_task_charge=charge,
              reason='ORIGIN_SENSITIVE_ACTUAL_QM_CHARGE_NONZERO_TARGETS')
        if any(m['registry_id']==674 for m in t['members']):
            value.update(scale_status='LOSS_DISABLED_SCALE_UNBOUND_OR_DEGENERATE',scale=None)
            ids={bykey[m['field_key']]['field_id'] for m in t['members']}
            groups=[g for g in physical if set(g['field_ids'])==ids]
            C.need(len(groups)==1,'ONE_ORIGINAL_INVENTORY_TENSOR_GROUP_NOT_AN_ALIAS');key=groups[0]['key'];s=scales[key]
            C.need(s['population_version_reference']==population_reference and s['statistic_reference'] in numeric_references,
              'ACTUAL_D4_R674_POPULATION_AND_NUMERIC_PARENT_NOT_ANOTHER_TRAIN')
            if not all(definition['fields'][m['field_key']].get('physical_policy_status')=='ACTUAL_TARGET_CONDITION_SOURCE_ENABLED' for m in t['members']):
                value['physical_policy_status']='DISABLED_PENDING_ACTUAL_TARGET_REVIEW'
            v=s['candidate_scale']
            if type(v)in(int,float) and math.isfinite(v) and v>0:
                value.update(scale_status='ACTUAL_TRAIN_POPULATION_SHA_BOUND',scale=v,scale_reference=s['statistic_reference'],
                  scale_population_reference=s['population_version_reference'],series_key=s['series_key'])
            value.update(center=0,loss='FROBENIUS_RADIAL_HUBER',normalization_denominator=9,huber_delta=1,one_tensor_one_target=True)
            # Frozen actual Native30 policy overrides any optimistic definition.
            value.update(physical_policy_status=off['loss_status'],physical_policy_reason=off['reason'],
              frozen_all_registry674_conditions_OFF=True,source_numeric_masks_changed=False)
        out[t['target_id']]=value
    return {'schema':'BOUNDED_D1_TARGET_LOCAL_EXPOSURE_AND_SCALE_V1','original_numeric_masks_unchanged':True,
      'actual_task_charge_separate_from_SMILES_formal_charge':True,'targets':out,'full_or_Model_release':False}

def materialize(plan,bounded,components,fields,cfg,roots,output,budget):
    v,definition,_,_=review(plan,bounded);root=Path(output);C.need(not root.exists(),'FRESH_ACTUAL_CPU_CONFIG_OUTPUT');root.mkdir()
    for ref in v['configuration_builder_source_references']:C.need(C.Q.pin(ref['path'])==ref,'EXACT_REVIEWED_CPU_CONFIGURATION_SOURCE')
    budget.check();base=I.load_data(v['base_registry_reference'],2<<20)
    native_reference=C.Q.pin(M.POLICY);M.physical_policy(native_reference,plan['D1_design_policy_reference'])
    definition=resolve_definitions(definition,fields,cfg['element_basis'],C.meta(v['task_protocol_reference']),native_reference)
    numeric=D.read(components['numeric_repetitions'][0],roots,256<<20)
    other=D.read(components['numeric_repetitions'][1],roots,256<<20)
    C.need(K.binary_json_dumps(numeric)==K.binary_json_dumps(other),'ACTUAL_D4_TWO_NUMERIC_REPETITIONS_NOT_SOURCE_ASSERTION')
    report=D.read(components['r674_report_reference'],roots,256<<20)
    rho=D.read(report['original_series_size_rho_reference'],roots,64<<20)
    C.need(rho['fit_population_reference']==components['population_reference'] and rho['threshold_abs_rho']==.95,'ACTUAL_D4_BOUNDED_TRAIN_RHO_SCOPE')
    reg=bound_registry(base,fields,definition,rho['series'],numeric['models'],native_reference,native_pilot=C.native_mode(plan));mapped=mapping(reg,definition)
    compiled=M.compile_targets(reg,mapped,require_final=True)
    rec=recipe(fields,mapped,definition,v['task_protocol_reference'])
    from .run import checked_recipe
    checked_recipe(rec,{f['field_key']:f for f in reg['fields'] if f['status']=='enabled'},compiled,fields,plan['source_references'])
    target=policies(mapped,report,definition,components['population_reference'],fields,cfg['element_basis'],components['numeric_repetitions'],native_reference)
    if C.native_mode(plan):
        reg.update(schema_version='label_registry_v3.0.0-v1-pilot-provisional',**C.capabilities(plan),
          publication_scope='FORMAL_METADATA_FOR_THIS_PILOT_PROVISIONAL_SCOPE_NOT_FULL_V1')
        for value in (mapped,rec,target):value.update(**C.capabilities(plan))
    outputs={}
    for name,value in (('registry',reg),('mapping',mapped),('projection_recipe',rec),('target_policy',target)):
        budget.check();ref=I.save(root/(name+'.json'),value);I.add(ref);outputs[name+'_reference']=ref
    header={'schema':'ACTUAL_CPU_BOUNDED_D2_D3_CONFIGURATIONS_V1','status':'ACTUAL_OUTPUTS_NOT_PARENT_C0_OR_FULL_RELEASE',
      'configuration_build_review_reference':bounded['configuration_build_review_reference'],
      'actual_D4_acceptance_reference':plan['pilot_acceptance_reference'],'field_ids_preserved':146,**outputs,
      'future_hash_created':False,'final_Common_or_Model_ACK':False}
    if C.native_mode(plan):header.update(**C.capabilities(plan))
    href=I.save(root/'configuration_references.json',header);I.add(href)
    return dict(outputs,configuration_header_reference=href),reg,mapped,rec,target,compiled
