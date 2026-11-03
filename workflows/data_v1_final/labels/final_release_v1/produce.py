"""Same-family-Parent final candidate; no independent job/C0 or default policy."""
import copy,json,os,socket,sys
from pathlib import Path
from . import contract as C,originals as O,rho as R,mask_binding as M
from workflows.data_v1_final.labels.common_train_normalization_day_v1 import io as I,audit as U
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import primary_binding
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import identity

def require_family_parent(d,proof,output):
    req=proof['request'];root=Path(output).absolute();parent=Path(d['parent_output_directory'])
    C.need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID')==str(proof['job_id'])
      and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('SLURM_JOB_PARTITION')=='cpu'
      and socket.gethostname().split('.')[0]==req['node'] and os.environ.get('CUDA_VISIBLE_DEVICES')=='',
      'REAL_GENERIC_FAMILY16_PARENT_CPU_ONLY')
    C.need(req['schema']==C.A.REQUEST_SCHEMA and req['kind']=='analysis' and req['cpus']==16 and req['wall_seconds']==86400
      and req['scope_key']=='family_export_day_v1' and req['scope_parameters']['output_directory']==str(parent)
      and root==parent/'final_release_candidate','EXACT_FAMILY_SCOPE_AND_OUTPUT_NO_RESOURCE_ALIAS')
    primary_binding(req,Path(sys.modules['__main__'].__file__).absolute(),sys.argv[1:])
    C.need(C.Q.load(proof['request_reference']['path'])==req,'EXACT_ADMITTED_FAMILY_REQUEST')
    pin=d['root_reviewed_directive_reference'];C.need(pin in req['source_references'],'ORIGINAL_ROOT_DIRECTIVE_PIN')
    original=C.meta(pin);runtime={'runtime_actual_field_claims_reference','root_reviewed_directive_reference'}
    C.need({k:v for k,v in d.items() if k not in runtime}==original,'RESOLVED_COPY_ONLY_ADDS_ACTUAL_CURRENT_CLAIM_REF')
    return root

def configure(validation,proof,root,d):
    dp=copy.deepcopy(validation['d4_plan']);m=validation['d4_manifest'];parent=Path(C.meta(d['d4_closure_reference'])['actual_parent']['manifest']['path']).parent
    req=proof['request'];small={r['path']:r for r in req['source_references']};data={r['path']:r for r in req['data_references']}
    for ref in validation['source_references']:C.need(small.get(ref['path'])==ref,'ALL_FINALIZER_SOURCE_AND_ACTUAL_SMALL_PARENTS_DECLARED')
    for ref in validation['data_references']:C.need(data.get(ref['path'])==ref,'ALL_ROOT_DIRECTIVE_NUMERIC_DATA_PREDECLARED')
    dp.update(source_references=list(small.values()),data_references=list(data.values()),output_directory=str(root),whole_output_cap_bytes=d['candidate_output_cap_bytes'],
      accepted_prior_output_roots=[*dp['accepted_prior_output_roots'],{'manifest_reference':C.meta(d['d4_closure_reference'])['actual_parent']['manifest'],'output_root':str(parent)}])
    I.configure(dp)
    state=I.load_data(m['checkpoint_reference'],512<<20)
    for ref in __import__('workflows.data_v1_final.labels.common_train_normalization_day_v1.run',fromlist=['references']).references(state):
        if ref['path'] not in I.ALLOWED:I.register_prior(ref)
    dp['eligibility_reference']=state['eligibility_reference'];dp['data_references']=C.unique([*dp['data_references'],*I.ALLOWED.values()])
    coverage=I.load_data(dp['coverage_reference'],8<<20);I.require(coverage['parts_catalog']);dp['catalog_frame']=identity(coverage['parts_catalog']['path'])
    return dp,state

def source_numeric(d,validation):
    refs=validation['d4_manifest']['numeric_repetition_references'];C.need(len(refs)==2,'TWO_REAL_FULL_NUMERIC_REPETITIONS')
    a=I.load_data(refs[0],256<<20);b=I.load_data(refs[1],256<<20)
    C.need(I.semantic_sha(a)==I.semantic_sha(b),'REAL_D4_FULL_NUMERIC_REPLAY_EXACT_NOT_MEDIAN_PARITY')
    out={'P_D':{'models':a['models'],'series':a['winsorized_component_and_invariant_audit']['series'],
      'source_reference':refs[0],'geometry_source':'pm7','label_group':'P_D'}}
    if d.get('independent_Pprime_actual_statistics'):
        pp=d['independent_Pprime_actual_statistics'];C.need(pp['full_Common_coverage'] is True and pp['formal_not_diagnostic'] is True,'FORMAL_FULL_INDEPENDENT_PPRIME_NOT_1200_OR_OLD15')
        ppProof,ppManifest=C.actual_accounted_parent(pp['actual_parent']);accept=C.meta(pp['root_acceptance_reference'])
        C.need(accept['reviewer']=='root' and accept['status']=='APPROVED_ACTUAL_FULL_PPRIME_TRAIN_STATISTICS'
          and accept['actual_parent']==pp['actual_parent'],'ACTUAL_INDEPENDENT_PPRIME_STATISTICS_ACCEPTANCE')
        value=I.load_data(pp['numeric_statistics_reference'],256<<20)
        C.need(ppManifest['schema']=='FINAL_NORMALIZATION_RUN_MANIFEST_V1' and ppManifest['normalization_completed'] is True
          and ppManifest['numeric_statistics']==pp['numeric_statistics_reference'] and ppManifest['independent_rebuild']['status']=='INDEPENDENT_FULL_REBUILD_EXACT_SEMANTIC_BYTES_MATCH',
          'ACTUAL_PPRIME_FULL_REPLAY_NUMERIC_SOURCE_NOT_BOUND_DIAGNOSTIC')
        C.need(value['schema']=='FINAL_NORMALIZATION_NUMERICAL_STATISTICS_V1' and value['pending_datasets']==[]
          and value['fit_role']=='TRAIN_ONLY','REAL_ORIGINAL_SEPARATE_PPRIME_STATISTIC_SCHEMA')
        row=value['datasets'][pp['dataset_id']]
        C.need(row['label_group']=='Pprime' and row['geometry_source']=='uff_sprime','PPRIME_CANNOT_ALIAS_PM7_VALUES_OR_REFERENCE_MODELS')
        out['Pprime']={'models':row['element_reference'],'series':row['series'],'source_reference':pp['numeric_statistics_reference'],
          'geometry_source':'uff_sprime','label_group':'Pprime'}
    return out

def scientific_registry(base,fields,rhos,policy):
    registry,reduce,series,compact,masks=O.objects();result=copy.deepcopy(base);ids={f['field_key']:f['field_id'] for f in fields}
    enabled=[r for r in result['fields'] if r['status']=='enabled'];C.need(len(enabled)==146,'PRESERVE_ORIGINAL_ENABLED_FIELDS_NO_HEAD_PER_AUDIT_ROW')
    for field in enabled:
        key=field['field_key'];definition=policy['scientific_field_definitions'][key]
        for kind in ('unit','sign','basis','frame'):
            C.need(definition[kind+'_status'] in ('VERIFIED','NOT_APPLICABLE_WITH_ACTUAL_DEFINITION'),
              'UNRESOLVED_CRITICAL_PHYSICAL_DOMAIN:'+key+':'+kind)
        C.need(definition['evidence_references'] and definition['numeric_transform']=='IDENTITY_NATIVE_STORED_VALUES'
          and definition['definition_based_not_inferred_from_rho'] is True,'NO_UNIMPLEMENTED_PHYSICAL_TRANSFORM_OR_RHO_EXTENSIVITY')
        physical=registry.physical_semantics(field['group'],field['source_path'],field['level'],field['component'])
        physical['extensivity']=definition['extensivity'];physical['definition_reference']=definition['definition_reference']
        family=registry.family_for(field['group'],field['source_path'],field['level']);rho=rhos[key]
        if rho['rho'] is not None and abs(rho['rho'])>=.95:family='size'
        field.update(physical,unit=definition['unit'],reference_frame=definition['reference_frame'],
          field_id=ids[key],family_v1_final=family,physical_definition=definition,
          size_rule={**field['size_rule'],**rho,'status':'FROZEN_ACTUAL_FINAL_TRAIN','abs_spearman_threshold':.95})
    scalars=__import__('collections').Counter(f['group'] for f in enabled if f['level']=='molecule')
    atomSASA=[f['field_key'] for f in enabled if f['group']=='D' and f['source_path'].endswith('SASA_atom_A2')]
    C.need(dict(scalars)=={'P':43,'D':26} and len(atomSASA)==1,'ACTUAL43P26D_PLUS_ATOM_SASA_NOT_FORCED_GUIDE42P27D')
    result.update(schema_version='label_registry_v3.0.0',status='FROZEN_ACTUAL_DEFINITIONS_FAMILIES_AND_SCOPED_STATISTICS',
      guide_count_reconciliation={'guide_P_molecule_scalars':42,'guide_D_molecule_scalars':27,'actual_P_molecule_scalar_fields':[f['field_key'] for f in enabled if f['group']=='P' and f['level']=='molecule'],
      'actual_D_molecule_scalar_fields':[f['field_key'] for f in enabled if f['group']=='D' and f['level']=='molecule'],'additional_D_atom_SASA_fields':atomSASA,
      'source_fields_renamed_deleted_or_reclassified_to_force_counts':False},
      physical_joint_policy_reference=policy['_reference'])
    return result

def normalization(mapping,numeric,policy,registry):
    fields={f['field_key']:f for f in registry['fields'] if f['status']=='enabled'};out={}
    for target in mapping['physical_targets']:
        if target['group']=='S':
            C.need(policy['structure_recipe_reference'],'REAL_MODEL_STRUCTURE_RECIPE');out[target['target_id']]={'model_generated_structure_recipe_reference':policy['structure_recipe_reference'],'WP5_normalizer':False};continue
        recipe=policy['normalization_by_target'][target['target_id']];dataset=recipe['dataset']
        C.need(dataset in numeric,'INDEPENDENT_DATASET_CALIBRATION_MISSING:'+dataset)
        expected='Pprime' if target['condition']=='Pprime' else 'P_D';C.need(dataset==expected,'CONDITION_INDEPENDENT_CALIBRATION_NO_P_SUBSTITUTION')
        rows={r['key']:r for r in numeric[dataset]['series']};physical=target['kind'] in ('vector','symmetric_tensor')
        item=O.exact_series_recipe(rows,recipe,physical=physical);members=[fields[m['field_key']] for m in target['members']]
        energy=[f for f in members if f['element_reference_eligible']]
        if energy:
            C.need(not physical and len(energy)==len(members)==1 and recipe['series_key']==str(energy[0]['field_id'])+'/residual',
              'ENERGY_ONLY_REAL_ELEMENT_REFERENCE_BEFORE_NORMALIZATION')
            item['element_reference']=numeric[dataset]['models'][str(energy[0]['field_id'])]
        item.update(dataset=dataset,source_numeric_statistics_reference=numeric[dataset]['source_reference'],unit=target['unit'],
          partial_mask_policy_reference=policy['partial_mask_policy_reference'],target_id=target['target_id'])
        out[target['target_id']]=item
    return {'schema':'FINAL_TRAIN_TARGET_NORMALIZATION_CANDIDATE_V1','status':'ACTUAL_SERIES_EXACT_JOINT_RECIPE_BOUND',
      'targets':out,'independent_dataset_sources':{k:v['source_reference'] for k,v in numeric.items()},
      'fit_population':'FINAL_COMMON_EFFECTIVE_TRAIN_ANTI_D5_ALL_REAL_DIRECT_CHILDREN','physical_head_recipe_chosen_by_source_agent':False,
      'original_stats_or_values_changed':False,'policy_reference':policy['_reference']}

def materialize_candidate(plan,proof,output_root,*,budget,validate_mapping):
    d=copy.deepcopy(plan);validation=C.validate_directive(d,allow_nonexecutable=False);root=require_family_parent(d,proof,output_root)
    C.need(not root.exists(),'FRESH_CURRENT_PARENT_FINAL_CANDIDATE');root.mkdir();cfg,state=configure(validation,proof,root,d);budget.check()
    policy=copy.deepcopy(validation['joint_policy']);policy['_reference']=d['joint_policy_reference']
    numeric=source_numeric(d,validation);fields=I.load_data(cfg['field_map_reference'],2<<20);base=C.meta(d['base_registry_reference'])
    # Same-parent actual claims are produced first, then supplied by reference; the Root directive stays byte-stable.
    claimref=d['runtime_actual_field_claims_reference'];C.need(Path(d['parent_output_directory']) in Path(claimref['path']).parents,'CURRENT_PARENT_CLAIM_PATH_ONLY')
    I.ALLOWED[claimref['path']]=claimref;claims,module=M.current_claims(d,proof,root)
    C.need(claims['field_policy_reference']==policy['field_geometry_policy_reference'],'ACTUAL_FIELD_GEOMETRY_POLICY_NOT_TASK_NAME_MAP')
    auditref=validation['d4_manifest']['all_population_audit_reference'];audit=I.load_data(auditref,16<<20)
    C.need(audit['quality_hold_fields']==[] and audit['status']=='NUMERIC_MASK_AUDIT_COMPLETE_PENDING_ROOT_AND_PHYSICAL_POLICY_REVIEW',
      'FULL_POPULATION_FIELD_SCOPE_ONE_PERCENT_GATE')
    d['_audit_reference']=auditref;d['_eligibility_reference']=cfg['eligibility_reference']
    for gr in audit['group_reports']:
        group=I.load_data(gr,16<<20)
        for ref in group['masks']:I.register_prior(ref)
    cfg['data_references']=C.unique([*cfg['data_references'],*I.ALLOWED.values()])
    rref=R.run(cfg,fields,numeric['P_D']['models'],policy['size_rules_by_field'],root/'size_rho',budget)
    rhos=I.load_data(rref,64<<20)['fields'];reg=scientific_registry(base,fields,rhos,policy)
    reg['pprime']['computed_labels_available']='Pprime' in numeric;regref=I.save(root/'label_registry_v3.json',reg)
    mapping=copy.deepcopy(C.meta(d['mapping_reference']));bykey={f['field_key']:f for f in reg['fields']}
    for target in mapping['physical_targets']:
        if target['group']=='S':continue
        families={bykey[m['field_key']]['family_v1_final'] for m in target['members']}
        C.need(len(families)==1,'PHYSICAL_TARGET_MEMBERS_REQUIRE_ONE_JOINT_SIZE_FAMILY');target['family']=next(iter(families))
    mapping.update(status='FROZEN',registry_sha256=regref['sha256'],joint_policy_reference=d['joint_policy_reference'])
    validate_mapping(reg,mapping,require_final=True);mapref=I.save(root/'physical_target_mapping_v3.json',mapping)
    normref=I.save(root/'normalization_v1.json',normalization(mapping,numeric,policy,reg))
    maskref=M.bind(d,proof,root/'mask_binding',audit,fields,claims,module,budget)
    candidate={'schema':C.CANDIDATE,'status':'COMPLETE_EXACT_FINAL_CANDIDATE_REQUIRES_ACTUAL_PARENT_C0_AND_ROOT_SEAL',
      'registry_reference':regref,'mapping_reference':mapref,'normalization_reference':normref,'mask_release_reference':maskref,'size_rho_reference':rref,
      'root_reviewed_directive_reference':d['root_reviewed_directive_reference'],'joint_policy_reference':d['joint_policy_reference'],
      'D5_components_reference':d['d5_components_acceptance_reference'],'d4_closure_reference':d['d4_closure_reference'],
      'current_actual_parent_job_id':str(proof['job_id']),'current_startup_proof_reference':C.Q.pin(proof['request']['startup_proof_path']),
      'release_scope':d['release_scope'],'release_id':d['release_id'],'current_parent_C0_claimed':False,'final_consumer_release_created':False,
      'Pprime_complete':'Pprime' in numeric,'all_required_joint_physical_policies_actual':True}
    cref=I.save(root/'candidate.json',candidate)
    return {**candidate,'candidate_reference':cref,'source_references':validation['source_references'],
      'data_references':C.unique([regref,mapref,normref,maskref,rref,cref])}
