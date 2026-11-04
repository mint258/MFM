"""Bounded storage compiler for the frozen user-accepted Source convention.

UNKNOWN independent coordinates are never rewritten as VERIFIED. Original full
compiler and all structural/math/pair functions remain unchanged.
"""
from . import contract as C
from workflows.data_v1_final.export.family_export_day_v1 import transport as T
ASSUMPTION='SOURCE_EVIDENCE_USER_ACCEPTED_ASSUMPTION'
POLICY=C.REPO/'configs/data_v1/interfaces/physical_exposure_after_native_frame30_20261029_v1.json'
MOLMR_UNIT='molar refractivity; frozen schema does not declare a unit'
UNKNOWN_UNIT='UNKNOWN_ORIGINAL_SOURCE_SCHEMA'
def molmr_unknown(field,definition):
    return (type(field.get('field_id'))is int and field.get('field_id')==7 and field.get('field_key')=='D20.MolMR' and field.get('registry_id') is None
      and field.get('group')=='D' and field.get('task')=='D20' and field.get('level')=='molecule'
      and field.get('source_path')=='MolMR' and field.get('component')=='value'
      and field.get('unit')==field.get('source_unit')==definition.get('unit')==MOLMR_UNIT
      and definition.get('unit_status')==UNKNOWN_UNIT and definition.get('physical_policy_status')=='DISABLED_UNIT_UNSPECIFIED'
      and definition.get('numeric_transform')=='IDENTITY_NATIVE_STORED_VALUES' and definition.get('reference_frame') is None)

def physical_policy(reference,design=None):
    C.need(reference['path']==str(POLICY),'EXACT_FROZEN_NATIVE30_SOURCE_POLICY_NOT_AN_INVENTED_APPROVAL')
    v=C.meta(reference)
    C.need(v['schema']=='ROOT_D1_V3_PHYSICAL_EXPOSURE_AFTER_NATIVE30_V1' and v['contract_version']=='v3.0'
      and v['reviewer']=='root' and v['historical_192_independent_output_coordinates']=='UNKNOWN_PRESERVED'
      and v['A_source_assumptions']['scope']=='EXACT_REVIEWED_NATIVE_GEOMETRY_TASK_SOURCE_CHAIN_ONLY'
      and v['A_source_assumptions']['no_blanket_acceptance_of_unreviewed_conditions'] is True
      and v['user_choices_1_to_4_unchanged'] is True and v['original_numerical_accuracy_and_thresholds_unchanged'] is True,
      'FROZEN_5A_EXACT_SOURCE_ASSUMPTION_AND_INDEPENDENT_UNKNOWN_PRESERVED')
    if design is not None:C.need(v['formal_design_policy_reference']==design,'SAME_USER_FROZEN_D1_DESIGN_POLICY')
    rules=[r for r in v['xtb_singlepoint_rules'] if r['selector']=='REGISTRY674_ALL_SYMMETRIC6_CONDITIONS']
    C.need(len(rules)==1 and rules[0]['loss_status']=='LOSS_DISABLED_PHYSICAL_POLICY_UNBOUND'
      and rules[0]['components_values_masks_reasons_and_F64_retained'] is True,'FROZEN_R674_OFF_WITH_ALL_DATA_RETAINED')
    return v

def frame_allowed(frame,policy_reference):
    if not frame:return
    if frame.get('verification')=='VERIFIED':return
    C.need(frame.get('verification')==ASSUMPTION and frame.get('independent_coordinate_check_status')=='UNKNOWN'
      and frame.get('source_convention_policy_reference')==policy_reference and frame.get('source_evidence_references'),
      'EXACT_USER_ACCEPTED_SOURCE_CONVENTION_NOT_INDEPENDENT_VERIFIED_OR_UNREVIEWED_FRAME')
    for r in frame['source_evidence_references']:C.reference(r)

def compile_targets(registry,mapping,*,require_final=True):
    C.need(require_final is True,'EXPLICIT_FROZEN_BOUNDED_METADATA_NOT_UNREVIEWED_MAPPING')
    fields={f['field_key']:f for f in registry['fields'] if f['status']=='enabled'}
    C.need(len(fields)==sum(f['status']=='enabled' for f in registry['fields'])
      and str(registry.get('status','')).startswith('FROZEN') and mapping['status']=='FROZEN','SAME_ORIGINAL_FROZEN_UNIQUE_FIELD_GATE')
    reference=registry['native30_policy_reference'];C.need(mapping['native30_policy_reference']==reference,'SAME_ACTUAL_NATIVE30_POLICY')
    physical_policy(reference)
    assumed={k for k,f in fields.items() if f.get('reference_frame') and f['reference_frame'].get('verification')==ASSUMPTION}
    unit_unknown={k for k,f in fields.items() if molmr_unknown(f,f.get('bounded_physical_definition',{}))}
    if unit_unknown:C.need(unit_unknown=={'D20.MolMR'} and registry.get('bounded_order_capability')==C.NATIVE_MODE
      and mapping.get('bounded_order_capability')==C.NATIVE_MODE,'ONLY_EXACT_NATIVE_PILOT_MOLMR_UNKNOWN_UNIT_SCOPE_NO_FULL_UNIT_EXCEPTION')
    # Already independently-verified/nonaxial targets use the unmodified compiler.
    deferred=[];direct=[]
    for target in mapping['physical_targets']:
        (deferred if any(m['field_key'] in assumed|unit_unknown for m in target['members']) else direct).append(target)
    keys={m['field_key'] for t in direct for m in t['members']}
    result=T.compile_targets(dict(registry,fields=[f for f in registry['fields'] if f['field_key'] in keys]),
      dict(mapping,physical_targets=direct),require_final=True)
    result=dict(result,physical_targets=dict(result['physical_targets']),ordered_record_targets=dict(result['ordered_record_targets']),
      physical_condition_counts=dict(result['physical_condition_counts']))
    used={(t['condition'],t['geometry_source'],m['field_key']) for t in direct for m in t['members']}
    seen={t['target_id'] for t in direct};domains={}
    for target in deferred:
        unknown=len(target['members'])==1 and target['members'][0]['field_key'] in unit_unknown
        C.need(target['target_id'] not in seen and target['condition']!='Pprime' and target['geometry_source']=='pm7'
          and (target['unit_status']=='VERIFIED' or unknown and target['unit_status']==UNKNOWN_UNIT
            and target.get('physical_loss_status')=='DISABLED_UNIT_UNSPECIFIED')
          and target['unit'] and target['family'],'SAME_FROZEN_UNIT_FAMILY_WITH_EXACT_DISABLED_MOLMR_OR_BOUND_FRAME_DOMAIN')
        if unknown:C.need(target['group']=='D' and target['level']=='molecule' and target['kind']=='scalar'
          and target['unit']==MOLMR_UNIT and not any(m['field_key'] in assumed for m in target['members']),
          'MOLMR_IS_NOT_A_VERIFIED_UNIT_OR_FRAME_ASSUMPTION_AND_CANNOT_MIX_MEMBERS')
        C.need(target.get('wire_kind')!='SOURCE_ORDERED_RECORDS_V1','R73_NATIVE_CHANNEL_DOMAIN_IS_NOT_AN_AXIAL_ASSUMPTION')
        seen.add(target['target_id']);keys={m['field_key'] for m in target['members']}
        for key in keys:
            field=fields[key];frame_allowed(field.get('reference_frame'),reference)
            C.need(field['family_v1_final']==target['family'],'SAME_ORIGINAL_FINAL_WITHIN_BOUNDED_SCOPE_FAMILY')
            identity=(target['condition'],target['geometry_source'],key);C.need(identity not in used,'ORIGINAL_COMPONENT_ONCE_PER_CONDITION');used.add(identity)
        subset=dict(registry,fields=[f for f in registry['fields'] if f['field_key'] in keys])
        # This original object validates all shape/group/order/storage/pair rules.
        # Finality/unit/family are checked above. Only the truthful frame enum is
        # the bounded user-policy seam; no dictionary is relabeled VERIFIED.
        checked=T.WIRE.preflight_registry(subset,dict(mapping,physical_targets=[target]),require_final=False)
        C.need(set(checked['physical_targets'])=={target['target_id']},'ORIGINAL_STRUCTURAL_VALIDATOR_EXACT_TARGET')
        if any(m['registry_id']==674 for m in target['members']):
            C.need(target['kind']=='symmetric_tensor' and len(target['members'])==6
              and tuple(target['component_order'])==T.WIRE.TENSOR6,'ORIGINAL_FULL6_ONE_TENSOR_TARGET')
        result['physical_targets'][target['target_id']]=dict(target)
        domains.setdefault((target['condition'],target['geometry_source']),[]).append(target)
    C.need(set(fields)=={key for _,_,key in used},'ALL_ENABLED_ORIGINAL_FIELDS_COVERED_NO_UNKNOWN_DROP')
    for domain,rows in domains.items():
        name='/'.join(domain);old=result['physical_condition_counts'].get(name,{'source_components':0,'physical_targets':0})
        result['physical_condition_counts'][name]={'source_components':old['source_components']+sum(len(t['members']) for t in rows),
          'physical_targets':old['physical_targets']+len(rows)}
    result.update(source_component_count=len(fields),physical_target_count=len(result['physical_targets'])+len(result['ordered_record_targets']),
      source_frame_policy='USER_ACCEPTED_SOURCE_CONVENTION_WITH_INDEPENDENT_UNKNOWN_RETAINED',
      native30_policy_reference=reference,independent_coordinate_UNKNOWN_relabelled_VERIFIED=False)
    if unit_unknown:result.update(disabled_unit_source_fields=['D20.MolMR'],unknown_original_unit_relabelled_VERIFIED=False)
    return result
