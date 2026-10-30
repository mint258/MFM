"""No DATA in login metadata; real final parents and Model ACK, never draft release."""
from pathlib import Path
from workflows.data_v1_final.export.d5_materialize_cpu_v1 import contract as D
Q=D.Q;ROOT=D.ROOT;REPO=D.REPO;PY=D.PY;need=D.need;reference=D.reference;unique=D.unique;meta=D.meta
HERE=REPO/'workflows/data_v1_final/export/family_export_day_v1';EXPORT=REPO/'workflows/data_v1_final/export'
MODULE='workflows.data_v1_final.export.family_export_day_v1.run';SCOPE='family_export_day_v1'
FILES=('__init__.py','contract.py','metadata.py','io.py','project.py','claims.py','transport.py','store.py','writer.py','verify.py','run.py','transfer.py','source_inverse.py','test_boundaries.py','frozen_sources.json','README.md')
OUTPUT=ROOT/'artifacts/export/family_export_day_v1'
REQUIRED=('final_release_directive_reference','D5_components_reference','source_release_reference','field_geometry_policy_reference','field_map_reference','resource_authority_reference','resource_review_reference','cost_decision_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')


def legacy():
    import importlib,sys
    if str(EXPORT) not in sys.path:sys.path.insert(0,str(EXPORT))
    result={}
    for name in ('wire_v1.codec','wire_v1.mapping','wire_v1.store','pipeline_v1.source','pipeline_v1.source_v2',
        'pipeline_v1.masks','pipeline_v1.granular_store','pipeline_v1.export','pipeline_v1.verify','pipeline_v1.mask_binding','pipeline_v1.io'):
        m=importlib.import_module(name);need(Path(m.__file__).absolute()==EXPORT/(name.replace('.','/')+'.py'),'DIRECT_ORIGINAL_MODULE_NOT_CLONE:'+name);result[name]=m
    return result


def sources():
    frozen=Q.load(HERE/'frozen_sources.json');refs=[]
    for row in frozen['files']:
        r={'path':str(REPO/row['root_relative_path']),'bytes':row['bytes'],'sha256':row['sha256']}
        need(Q.pin(r['path'])==r,'ORIGINAL_EXPORT_SOURCE_CHANGED');refs.append(r)
    from workflows.data_v1_final.export.d5_inputs_builder_v1.contract import source_check
    refs.extend(source_check().values())
    refs.extend(Q.pin(HERE/n) for n in FILES)
    return unique(refs)


def resource_output(p):
    import hashlib
    return ROOT/'artifacts/labels/source_status_v1/family_export_day_v1_resources'/hashlib.sha256(p['output_directory'].encode()).hexdigest()[:24]


def parameters(p):
    return {'output_directory':p['output_directory'],'purpose':p['purpose'],'workers':16,'pending':32,'wall_seconds':86400,'whole_output_cap_bytes':p['output_cap_bytes'],
        'resource_evidence_output':str(resource_output(p)),'resource_evidence_cap_bytes':512<<20,'resource_evidence_included_in16GiB_drain_reserve':True,
        'pilot_TRAIN_molecules':50000,'pilot_ROUTINE_VAL_molecules':5000,'sample_source_records':10000,'sample_seed':20261025,
        'one_real_parent_no_per_shard_Slurm':True,'float32_conversion':'ONCE_AT_ORIGINAL_MFM3_ENCODER',
        'permanent_source_float64_unchanged':True,'r73_source_order_basis_channel_onsite_duplicate_transport':True,
        'r674_one_six_member_tensor_source_masks_precision_preserved':True,'pickle_in_new_export':False,
        'science_algorithms_selected_by_exporter':False,'new_QM_UFF_calls':0,'final_release_not_signed_by_producer':True}


def final_parents(p):
    """Prior actual parents authorize a same-parent candidate, never a future C0."""
    need(p['schema']=='FAMILY_EXPORT_DAY_PLAN_V1' and p['purpose'] in ('pilot55k','full') and p['wall_seconds']==86400
        and type(p['output_cap_bytes']) is int and 32<<30<=p['output_cap_bytes']<=1<<40
        and p['scope_parameters']==parameters(p),'FINITE_EXACT_EXPORT_SCOPE_NO_SMALL_FAKE_PILOT')
    from workflows.data_v1_final.labels.final_release_v1.contract import validate_directive
    directive=meta(p['final_release_directive_reference']);checked=validate_directive(directive,allow_nonexecutable=False)
    need(checked['status']=='READY_ACTUAL_PARENTS_BOUND' and (directive['parent_output_directory']==p['output_directory'] or p.get('resume_adoption_reference'))
        and directive['claim_mode']=='CURRENT_PARENT_DERIVED_EXACT_FIELD_CLAIMS'
        and directive['d5_components_acceptance_reference']==p['D5_components_reference'],
        'PRIOR_ACTUAL_D4_AND_JOINT_POLICY_AUTHORIZE_INLINE_CANDIDATE_NOT_CURRENT_C0')
    need(directive['release_scope']==('BOUNDED_D3_50K_TRAIN_5K_ROUTINE_VAL' if p['purpose']=='pilot55k' else 'FULL_V1'),
        'DIRECTIVE_SCOPE_EXACT_NO_PILOT_TO_FULL_PROMOTION')
    need(checked['joint_policy']['field_geometry_policy_reference']==p['field_geometry_policy_reference']
        and checked['d4_plan']['field_map_reference']==p['field_map_reference'],'EXACT_D4_FIELD_IDS_AND_JOINT_FIELD_GEOMETRY_POLICY')
    joint=checked['joint_policy'];registry=meta(directive['base_registry_reference']);mapping=meta(directive['mapping_reference'])
    d5=meta(p['D5_components_reference']);source=meta(p['source_release_reference'])
    need(d5['schema']=='ROOT_ACCEPTED_D5_COMPOUND_COMPONENTS_V1' and d5['status']=='ACTUAL_C0_COMPONENTS_ACCEPTED_NOT_JOINT_D5'
        and d5.get('ordinary_D5_artifacts') and d5.get('ordinary_input_tables'),'ACTUAL_D5_COMPONENTS')
    from workflows.data_v1_final.export.d5_inputs_compound_day_v1.contract import closure
    receipt,_,parents=closure(d5['actual_closure_references'])
    need(receipt['technical_phase_closed'] is True and receipt['whole_true_Common_coverage_verified'] is True
        and receipt['D5_sampling_and_readback'] is not None,'TRUE_FULL_D5_NOT_SOURCE_ONLY_OR512')
    need(source['schema']=='ROOT_FROZEN_FAMILY_EXPORT_SOURCE_RELEASE_V1' and source['status']=='APPROVED_EXACT_FULL_SOURCE_PROJECTION'
        and source['reviewer']=='root' and source['D5_components_reference']==p['D5_components_reference']
        and source['joint_policy_reference']==directive['joint_policy_reference']
        and source['field_geometry_policy_reference']==p['field_geometry_policy_reference']
        and source['field_map_reference']==p['field_map_reference']
        and source['all_physical_geometry_and_child_sources_bound'] is True and source['Pprime_not_copied_from_PM7'] is True
        and source['source_identity_or_mask_gaps']==0,'ROOT_REVIEWED_EXACT_SOURCE_DOMAIN_NOT_INVENTED_CHILD_OR_FRAME')
    policy=meta(p['field_geometry_policy_reference']);need(policy['status']=='MODEL_DATA_FIELD_GEOMETRY_BINDINGS_FROZEN'
        and policy['model_confirmation'] and policy['data_confirmation'],'EXPLICIT_FIELD_NOT_TASK_NAME_GEOMETRY_POLICY')
    refs=unique([*(p[k] for k in REQUIRED),*checked['source_references'],*parents,*source['source_references']])
    data=unique([*checked['data_references'],*source['data_references'],*d5['ordinary_D5_artifacts'].values(),
        *d5['ordinary_input_tables'].values(),source['source_specification_reference'],p['field_map_reference']])
    if p['purpose']=='full' or any(t['condition']=='Pprime' for t in mapping['physical_targets']):
        need(source.get('independent_Pprime_field_and_mask_authority_reference'),'MISSING_ACTUAL_INDEPENDENT_PPRIME_FIELD_AND_MASK_AUTHORITY')
        pp=independent_pprime(source['independent_Pprime_field_and_mask_authority_reference'],p['D5_components_reference'])
        refs=unique([*refs,source['independent_Pprime_field_and_mask_authority_reference'],*pp['source_references'],*pp['actual_parent'].values()])
        data=unique([*data,*pp['data_references'],pp['claim_database_reference'],pp['mask_release_reference']])
    if p.get('resume_adoption_reference'):
        adopt=meta(p['resume_adoption_reference']);need(adopt['schema']=='ROOT_FAMILY_SOURCE_CURSOR_ADOPTION_V1'
            and adopt['status']=='APPROVED_EXACT_C0_CLOSED_SOURCE_TASKS' and adopt['reviewer']=='root'
            and adopt['source_release_reference']==p['source_release_reference']
            and adopt['field_geometry_policy_reference']==p['field_geometry_policy_reference'],'STRICT_EXPLICIT_CURSOR_ADOPTION_NOT_AUTOMATIC_RETRY')
        chain=adopt['actual_closure_references'];prior=meta(chain['receipt']);proof=meta(chain['startup_proof']);pp=meta(prior['plan_reference'])
        from workflows.data_v1_final.export.common_day_parent_v1 import parent as B
        B.account(chain['accounting'],str(proof['job_id']),proof['request']['node'],16)
        need(prior['schema']=='FAMILY_EXPORT_DAY_RECEIPT_V1' and prior['status'] in ('PARTIAL_OR_UNKNOWN_NO_EXPORT_RELEASE','COMPLETE_TECHNICAL_EXPORT_PENDING_EXTERNAL_SEAL')
            and prior['startup_proof_reference']==chain['startup_proof'] and prior['errors']==[]
            and pp['purpose']==p['purpose'] and pp['final_release_directive_reference']==p['final_release_directive_reference']
            and prior['source_release_reference']==p['source_release_reference']
            and prior.get('inline_final_label_candidate') and prior.get('field_claims_reference')
            and adopt['only_actual_closed_source_tasks_and_closed_stores'] is True,
            'PRIOR_ACTUAL_C0_PRESERVED_EXACT_CANDIDATE_NOT_FAILED_UNKNOWN_OR_POLICY_SWITCH')
        need(adopt['closed_source_tasks_reference']==prior['source_tasks_reference'],'EXACT_PERSISTED_SOURCE_CURSOR')
        data=unique([*data,*adopt['exact_prior_DATA_references']]);refs=unique([*refs,p['resume_adoption_reference'],*chain.values(),prior['plan_reference']])
    # field-map JSON and source specifications are DATA, not small metadata even
    # when a bounded instance happens to be tiny.
    data_paths={r['path'] for r in data};refs=[r for r in refs if r['path'] not in data_paths]
    if p['purpose']=='full':
        pilot=meta(p['actual_D3_pilot_review_reference']);ack=meta(p['model_loader_ACK_reference'])
        need(pilot['schema']=='ROOT_ACTUAL_FAMILY_D3_PILOT_ACCEPTANCE_V1' and pilot['status']=='APPROVED_ACTUAL55K_AND10000_SOURCE_PARITY'
            and pilot['reviewer']=='root' and pilot['joint_policy_reference']==directive['joint_policy_reference'],
            'REAL_PILOT_C0_AND_ROOT_REVIEW_BEFORE_FULL')
        validate_actual_closure(pilot['actual_closure_references'])
        need(ack['schema']=='ROOT_ACCEPTED_ACTUAL_MODEL_D3_LOADER_ACK_V1' and ack['status']=='ACTUAL_MODEL_LOADER_ACCEPTED_EXACT_D3'
            and ack['reviewer']=='root' and ack['pilot_review_reference']==p['actual_D3_pilot_review_reference']
            and ack['actual_loader_execution_reference'] and ack['actual_loaded_export_reference']==pilot['accepted_export_reference']
            and ack['mock_or_source_only_or_inferred_ACK'] is False,'NO_FAKE_MODEL_ACK')
        meta(ack['actual_loader_execution_reference']);refs=unique([*refs,p['actual_D3_pilot_review_reference'],p['model_loader_ACK_reference'],ack['actual_loader_execution_reference']])
    # tuple positions are intentional: DATA at 7 is shared with the guard.
    return joint,registry,mapping,directive,checked,d5,source,data,refs


def independent_pprime(reference,d5_reference):
    a=meta(reference);need(a['schema']=='ROOT_ACCEPTED_INDEPENDENT_PPRIME_FIELD_AND_MASK_AUTHORITY_V1'
        and a['status']=='ACTUAL_FULL_SOURCE_HASH_BOUND_FIELD_GEOMETRY_AND_ORIGINAL_MASKS' and a['reviewer']=='root'
        and a['D5_components_reference']==d5_reference and a['full_Common_coverage'] is True
        and a['unknown_or_duplicate_field_claims']==0 and a['original_input_double_SHA_and_actual_child_bound'] is True
        and a['source_mask_semantics']=='ORIGINAL_PER_FIELD_PER_LEAF_VALIDITY_AND_RECORDED_CAUSES'
        and a['PM7_D4_mask_or_statistics_substitution'] is False,'ACTUAL_INDEPENDENT_PPRIME_NO_PM7_MASK_SUBSTITUTION')
    chain=a['actual_parent'];need(set(chain)=={'manifest','proof','accounting','raw'},'FOUR_REAL_FORMAL_PPRIME_PARENT_REFERENCES')
    r=meta(chain['manifest']);proof=meta(chain['proof']);req=proof['request'];account=meta(chain['accounting'])
    need(type(req['cpus']) is int and req['cpus']>=16 and req['execution_argv']==a['actual_execution_argv']
        and str(proof['job_id'])==str(a['actual_parent_job_id']) and r['schema']==a['actual_manifest_schema']
        and account['raw_sacct_reference']==chain['raw'],'ACTUAL_FOREIGN_FORMAL_SOURCE_NOT_FAKE_FAMILY16_PARENT')
    from workflows.data_v1_final.export.common_day_parent_v1 import parent as B
    B.account(chain['accounting'],str(proof['job_id']),req['node'],req['cpus'])
    return a

def validate_actual_closure(chain):
    from workflows.data_v1_final.export.common_day_parent_v1 import parent as B
    need(set(chain)=={'receipt','startup_proof','accounting'},'THREE_TRUE_EXTERNAL_PARENT_REFERENCES')
    r=meta(chain['receipt']);proof=meta(chain['startup_proof']);plan=meta(r['plan_reference']);req=proof['request']
    need(r['schema']=='FAMILY_EXPORT_DAY_RECEIPT_V1' and r['status']=='COMPLETE_TECHNICAL_EXPORT_PENDING_EXTERNAL_SEAL'
        and r['source_roundtrip_records']==10000 and r['all_handles_closed'] is True and r['errors']==[]
        and r['remaining_shards']==0 and r['pilot_counts_exact'] is True and r['preflight_methods']==15
        and r['source_inverse']['status']=='EXACT_THREE_FUNCTION_BYTES_AST_AND_TEN_ORIGINAL_OBJECTS','ACTUAL_FULL_REQUESTED_SCOPE_AND_READBACK_NOT_PARTIAL')
    need(proof['schema']=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1' and req['schema']=='CPU_AUTO_MEMORY_QUEUED_REQUEST_V1'
        and req['scope_key']==SCOPE and req['execution_argv']==[PY,'-B','-m',MODULE,'--plan',r['plan_reference']['path'],'--startup-proof',chain['startup_proof']['path']]
        and req['cpus']==16 and req['wall_seconds']==86400 and r['actual_parent_job_id']==str(proof['job_id']),
        'ACTUAL_PRIMARY_AND_UNIFIED_CPU16_PARENT_NOT_FAKE_CHILD_C0')
    B.account(chain['accounting'],str(proof['job_id']),req['node'],16)
    need(r['startup_proof_reference']==chain['startup_proof'] and req['producer_plan_reference']==r['plan_reference'],
        'PRODUCER_PLAN_PROOF_RECEIPT_CHAIN')
    return r,proof,plan

def assert_publication_links(release,review,before,receipt,labels,label_review,label_before,candidate):
    """Pure equality/authority gate; every input is separately SHA-pinned by IO."""
    need(release['schema']=='ROOT_ACCEPTED_FAMILY_EXPORT_RELEASE_V1' and release['consumer_release'] is True
        and review['schema']=='ROOT_FAMILY_EXPORT_PUBLICATION_REVIEW_V1'
        and review['status']=='APPROVED_EXACT_ACTUAL_C0_AND_SAME_OBJECTS' and review['reviewer']=='root',
        'REAL_INDEPENDENT_FAMILY_PUBLICATION_REVIEW_NOT_C0_OR_FILENAME')
    need(before['schema']=='FAMILY_EXPORT_EXTERNAL_SEAL_CANDIDATE_V1'
        and before['status']=='PENDING_INDEPENDENT_ROOT_C0_AND_EXACT_FINAL_LABEL_RELEASE_REVIEW'
        and release['actual_closure_references']==before['actual_closure_references']
        and before['inline_final_label_candidate']==receipt['inline_final_label_candidate'],
        'FAMILY_REVIEW_EXACT_ACTUAL_C0_CANDIDATE_CHAIN')
    for key in ('stores_catalogue_reference','verification_reference','selection_reference','source_release_reference'):
        need(release[key]==before[key]==receipt[key],'EXACT_EXTERNAL_RELEASE_OBJECT:'+key)
    need(review['stores_catalogue_reference']==release['stores_catalogue_reference']
        and review['final_label_release_reference']==release['final_label_release_reference'],'EXACT_FAMILY_REVIEW_OUTPUTS')
    need(labels['schema']=='ROOT_FINAL_LABEL_RELEASE_V1' and labels['final_consumer_release'] is True
        and label_review['schema']=='ROOT_FINAL_LABEL_PUBLICATION_REVIEW_V1'
        and label_review['status']=='APPROVED_EXACT_ACTUAL_C0_RELEASE' and label_review['reviewer']=='root'
        and label_before['schema']=='FINAL_LABEL_POST_C0_ROOT_REVIEW_CANDIDATE_V1'
        and label_before['status']=='PENDING_INDEPENDENT_ROOT_FINAL_REVIEW',
        'INDEPENDENT_LABEL_PUBLICATION_REVIEW_NOT_INNER_CANDIDATE_BOOLEAN')
    need(candidate['schema']=='FINAL_LABEL_RELEASE_CANDIDATE_V1'
        and candidate['status']=='COMPLETE_EXACT_FINAL_CANDIDATE_REQUIRES_ACTUAL_PARENT_C0_AND_ROOT_SEAL'
        and candidate['current_parent_C0_claimed'] is False
        and labels['candidate_reference']==label_before['actual_parent_references']['candidate']==receipt['inline_final_label_candidate']['candidate_reference']
        and labels['actual_parent_references']==label_before['actual_parent_references'],
        'EXACT_CANDIDATE_PRODUCING_PARENT_MAY_PRECEDE_REVIEWED_CONTINUATION')
    outputs={k:candidate[k] for k in ('registry_reference','mapping_reference','normalization_reference','mask_release_reference','size_rho_reference')}
    need(label_review['exact_outputs']==label_before['exact_outputs']==outputs,'ROOT_LABEL_REVIEW_EXACT_SAME_SCIENTIFIC_OBJECTS')
    need(all(labels[k]==receipt['inline_final_label_candidate'][k]==v for k,v in outputs.items()),'NO_SUBSTITUTED_CONFIGURATION_SHA')
    need(release['joint_policy_reference']==before['joint_policy_reference']==labels['joint_policy_reference']==label_review['joint_policy_reference']==candidate['joint_policy_reference'],
        'SAME_JOINT_POLICY_ACROSS_BOTH_PUBLICATIONS')
    full=release['purpose']=='full'
    need(release['status']==('FULL_V1_FROZEN' if full else 'BOUNDED_D3_50K_TRAIN_5K_VAL_FROZEN_NOT_FULL')
        and labels['status']==('FULL_V1_FROZEN' if full else 'BOUNDED_DIAGNOSTIC_P_D_RELEASE_NOT_FULL_V1')
        and labels['release_scope']==candidate['release_scope']==('FULL_V1' if full else 'BOUNDED_D3_50K_TRAIN_5K_ROUTINE_VAL')
        and release['training_ready'] is full and labels['training_ready'] is full,
        'EXACT_BOUNDED_OR_FULL_PUBLICATION_NO_PROMOTION')
    return outputs


def validate_published_release(release):
    """Read-only complete outside seal chain; never writes or accepts just C0."""
    review=meta(release['root_publication_review_reference']);before=meta(review['candidate_reference'])
    receipt,proof,plan=validate_actual_closure(before['actual_closure_references'])
    labels=meta(release['final_label_release_reference']);label_review=meta(labels['root_publication_review_reference'])
    label_before=meta(label_review['candidate_reference']);parents=label_before['actual_parent_references']
    from workflows.data_v1_final.labels.final_release_v1.metadata import actual_family
    candidate,_=actual_family(*(parents[k] for k in ('candidate','startup_proof','accounting','raw')))
    outputs=assert_publication_links(release,review,before,receipt,labels,label_review,label_before,candidate)
    need(release['purpose']==plan['purpose'] and label_before['joint_policy_reference']==candidate['joint_policy_reference'],
        'CURRENT_EXPORT_SCOPE_AND_ACTUAL_LABEL_CANDIDATE_POLICY')
    policy=meta(candidate['joint_policy_reference']);need(policy['status']=='JOINTLY_FROZEN' and policy['actual_final_Model_ack_not_conditional'] is True,
        'REAL_FINAL_JOINT_POLICY_STILL_BOUND')
    for key,reference0 in labels['configurations'].items():
        wrapper=meta(reference0);need(key in outputs and wrapper['schema']=='FINAL_LABEL_CONFIGURATION_REFERENCE_V1'
            and wrapper['configuration_kind']==key and wrapper['configuration_reference']==outputs[key]
            and wrapper['actual_parent_references']==parents and wrapper['joint_policy_reference']==candidate['joint_policy_reference']
            and wrapper['root_publication_review_reference']==labels['root_publication_review_reference'],
            'VERSIONED_WRAPPER_EXACT_PIN_CONTENT_NOT_FILENAME')
    need(set(labels['configurations'])==set(outputs),'ALL_FIVE_PUBLISHED_CONFIGURATION_WRAPPERS')
    if release['purpose']=='full':
        need(candidate['Pprime_complete'] is True and labels['D4_published'] is True
            and label_review['model_actual_acceptance_reference']==labels['model_actual_acceptance_reference'],
            'FULL_FORMAL_PPRIME_AND_MODEL_ACCEPTANCE_STILL_REQUIRED')
        model=meta(labels['model_actual_acceptance_reference'])
        need(model['schema']=='ROOT_MODEL_ACTUAL_NATIVE_CONSUMER_ACCEPTANCE_V1'
            and model['status']=='ACTUAL_REQUIRED_NATIVE_MODEL_CHECKS_ACCEPTED'
            and model['release_candidate_reference']==parents['candidate'] and model['all_required_model_checks_passed'] is True
            and model['actual_runtime_evidence_references'],'ACTUAL_MODEL_NATIVE_RUNTIME_NOT_SOURCE_ONLY')
        for reference0 in model['actual_runtime_evidence_references']:meta(reference0)
        source=meta(plan['source_release_reference']);need(release['independent_Pprime_field_and_mask_authority_reference']==source['independent_Pprime_field_and_mask_authority_reference'],
            'EXACT_INDEPENDENT_PPRIME_MASK_PUBLICATION')
        independent_pprime(source['independent_Pprime_field_and_mask_authority_reference'],plan['D5_components_reference'])
    return receipt,proof,plan