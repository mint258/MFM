"""New compound metadata; original numerical contracts and COUNTS are inherited."""
from pathlib import Path
from workflows.data_v1_final.export.d5_inputs_builder_v1 import contract as OLD
from workflows.data_v1_final.export.d5_materialize_cpu_v1 import contract as D
from workflows.data_v1_final.export.common_day_parent_v1 import parent as Bridge
Q=D.Q;ROOT=D.ROOT;REPO=D.REPO;PY=D.PY;need=D.need;meta=D.meta;reference=D.reference;unique=D.unique
HERE=REPO/'workflows/data_v1_final/export/d5_inputs_compound_day_v1';MODULE='workflows.data_v1_final.export.d5_inputs_compound_day_v1.run'
FILES=('__init__.py','contract.py','resources.py','reader.py','prepare.py','core.py','canonical_children.py','executor.py','verify.py','run.py','metadata.py','source_inverse.py','test_boundaries.py','README.md')
OUTPUT=ROOT/'artifacts/labels/source_status_v1/d5_inputs_compound_day_v1';COUNTS=D.COUNTS;ORDER_SEED=20261025

def parameters(p):
    return {'allocated_cpus':p['cpus'],'node':p['node'],'purpose':p['purpose'],'phase':p['phase'],'workers':16,'pending':32,'wall_seconds':86400,'output_cap_bytes':p['output_cap_bytes'],
      'common_closure_references':p['common_closure_references'],'order_seed':20261025,'guide_counts':COUNTS,
      'logical_partition_molecules':p['logical_partition_molecules'],'single_real_parent_no_internal_child_C0':True,
      'actual512_C0_and_Root_review_before_full':True,'original_sampling_seed_and_anti_join_objects':True,
      'derived_DATA_authority':'CURRENT_ALLOCATED_PARENT_EXACT_PREPARED_LOCATORS_AND_REGISTERED_REF_CATALOGUE',
      'new_QM_UFF_calls':0,'N1_extra_not_ordinary_or_child':True,'source_methods':12,'D5_joint_release':False}

def source_paths():
    from workflows.data_v1_final.execution.cpu_analysis_day_v2 import contract as Resource
    from workflows.data_v1_final.labels.normalization_compact_runtime_v2 import runtime as Clock
    return sorted(set([*(HERE/n for n in FILES),*OLD.source_paths(),*(Path(r['path']) for r in Bridge.sources()),
        *Resource.sources(),Path(Clock.__file__),Path(Clock.C.__file__)]))

def common(p):
    # Exact old common/hof/ordinary review predicates are mechanically retained
    # below with the one Common-parent reader replaced by the truthful day bridge.
    return common_body(p)

def common_body(plan):
    m,refs=Bridge.common_parent(plan['common_closure_references'])
    review=meta(plan['ordinary_source_review_reference']);policy=meta(plan['ordinary_N1_preparation_policy_reference'])
    for value in (review,policy):
        need(value['reviewer']=='root' and value['common_manifest_reference']==plan['common_closure_references']['manifest'],
            'INDEPENDENT_SAME_ACTUAL_COMMON_ORDINARY_REVIEW')
    need(review['schema']=='ROOT_D5_ORDINARY_BASE_SOURCE_REVIEW_V1'
        and review['status']=='ROOT_REVIEWED_EXACT_ORDINARY_BASE_SOURCES'
        and review['ordinary_physical_tables']==m['physical_geometry_tables']
        and review['no_N1_extras_or_perturbed_children_in_ordinary_bases'] is True
        and review['finalizer_actual_source_and_attempt_chains_reviewed'] is True,'ACTUAL_ORDINARY_SOURCE_CHAIN_NOT_N1_OR_LABEL_SUCCESS_FILTER')
    need(policy['schema']=='ROOT_D5_ORDINARY_N1_PREPARATION_POLICY_V1'
        and policy['status']=='ROOT_REVIEWED_ORDINARY_N1_INPUT_PREPARATION_ONLY'
        and policy['ordinary_counts_unchanged'] is True and policy['N1_less_than_two_remains_pending'] is True
        and policy['Pprime_generation_or_QM_authorized'] is False,'N1_PREPARATION_SCOPE_NOT_FINAL_N1_EXTRA_AUTHORITY')
    formal=meta(m['formal_population_authority_receipt']);rows=[r for r in formal['outputs'] if r['name']=='formal_population']
    need(formal['status']=='ALL_BOUND_INPUTS_SHA_VERIFIED' and len(rows)==1,'EXACT_CLOSED_CANONICAL_POINTER_POPULATION')
    validation=meta(review['canonical_node13_source_validation_reference'])
    observed=[r for r in validation['inputs'] if r['reference']==rows[0]['reference']]
    need(validation['status']=='ALL_ACTUAL_SOURCE_SHA_VERIFIED' and len(observed)==1
        and observed[0]['actual']==rows[0]['reference'] and observed[0]['status']=='ACTUAL_FULL_SHA_MATCH'
        and observed[0]['uid']==rows[0]['after']['uid']==1278
        and observed[0]['inode']==rows[0]['after']['inode'] and observed[0]['mtime_ns']==rows[0]['after']['mtime_ns'],
        'REAL_PRIOR_CPU13_CANONICAL_SOURCE_FRAME_NOT_ASSUMED_CROSS_NODE_DEVICE')
    hof=meta(plan['hof_authority_reference']);projection=meta(hof['projection_receipt_reference'])
    need(hof['schema']=='ROOT_PM7_CACHE_CANONICAL_HOF_AUTHORITY_V1' and hof['reviewer']=='root'
        and hof['status']=='VERIFIED_FROZEN_PM7_B_SCALAR_READER' and hof['registry_id']==60
        and hof['unit']=='kcal/mol' and hof['native_energy_fallback_allowed'] is False
        and projection['status']=='CATALOG_METADATA_PROJECTION_VERIFIED'
        and hof['source_files_reference']==projection['source_files'],'ORIGINAL_REGISTRY60_HOF_OWNER_AUTHORITY')
    data=unique([*m['membership_tables'],*m['physical_geometry_tables'],reference(rows[0]['reference']),
        reference(hof['latest_owner_reference']),reference(projection['source_files'])])
    refs=unique([*refs,plan['ordinary_source_review_reference'],plan['ordinary_N1_preparation_policy_reference'],
        plan['hof_authority_reference'],hof['projection_receipt_reference'],m['formal_population_authority_receipt'],m['old_sprime_manifest'],m['config'],
        review['canonical_node13_source_validation_reference']])
    return m,rows[0]['reference'],hof,data,refs

def closure(chain):
    need(set(chain)=={'receipt','startup_proof','accounting'},'EXACT_ACTUAL_COMPOUND_PARENT_CLOSURE')
    r=meta(chain['receipt']);proof=meta(chain['startup_proof']);p=meta(r['plan_reference']);req=proof['request']
    need(r['schema']=='D5_COMPOUND_DAY_RECEIPT_V1' and r['status'] in ('COMPLETE_TECHNICAL_COMPOUND_REQUIRES_ROOT_REVIEW','PARTIAL_SAFE_PREFIX_REQUIRES_ROOT_CONTINUATION_REVIEW')
      and str(r['job_id'])==str(proof['job_id']) and type(req['cpus']) is int and req['cpus']>=16 and req['node'] in ('compute-0-14','compute-0-18')
      and req['scope_key']=='d5_inputs_compound_day_v1' and req['scope_parameters']==parameters(p)
      and req['execution_argv']==[PY,'-B','-m',MODULE,'--plan',r['plan_reference']['path'],'--startup-proof',chain['startup_proof']['path']]
      and req['cpus']==p['cpus'] and req['node']==p['node'] and req['schema']=='CPU_ANALYSIS_DAY_REQUEST_V2' and proof['schema']=='FRESH_CPU_ANALYSIS_DAY_EXECUTION_ADMISSION_V2'
      and r['plan_reference'] in req['source_references'] and Path(chain['receipt']['path'])==Path(p['output_directory'])/'receipt.json','REAL_ONE_COMPOUND_PARENT_NO_INTERNAL_C0')
    need(proof['uid']==r['uid']==1278 and r['node']==req['node'] and r['actual_allocated_cpus']==req['cpus']
        and r['startup_proof_reference']==chain['startup_proof'] and req['producer_plan_reference']==r['plan_reference']
        and meta(proof['request_reference'])==req and req['kind']=='analysis' and req['pilot'] is False
        and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['wall_seconds']==86400,
        'EXACT_ACTUAL_REQUEST_PROOF_C0_LINEAGE_NOT_ALIAS_OR_OLD16')
    for ref in p['source_references']:need(ref in req['source_references'] and Q.pin(ref['path'])==ref,'ACTUAL_IMMUTABLE_SOURCE_PARENT_CHAIN')
    _,raw=Bridge.account(chain['accounting'],r['job_id'],req['node'],req['cpus']);g=meta(r['source12_reference'])
    need(g['tests_run']==12 and all(type(g[k]) is int and g[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'ACTUAL_SOURCE12_NO_SKIP')
    need(g['source_inverse']['status']=='EXACT_COMPOUND_SOURCE_INVERSE_AND_ORIGINAL_OBJECTS'
        and g['source_inverse']['all_mechanical_inverses_bytes_AST_equal'] is True and r['held_molecules']==0,
        'ACTUAL_INVERSE_AND_ZERO_HELD_PREFIX_NOT_COUNT_ONLY')
    return r,p,unique([*chain.values(),raw,r['plan_reference'],r['source12_reference']])

def inputs(p):
    need(p['schema']=='D5_COMPOUND_DAY_PLAN_V1' and p['purpose'] in ('pilot512','full') and p['phase'] in ('ordinary_base','ordinary_WP5_and_D5','all_actual_children_and_D5')
      and type(p['cpus']) is int and p['cpus']>=16 and p['node'] in ('compute-0-14','compute-0-18') and p['wall_seconds']==86400 and type(p['output_cap_bytes']) is int and 32<<30<=p['output_cap_bytes']<=1<<40
      and type(p['logical_partition_molecules']) is int and 1<=p['logical_partition_molecules']<=512
      and type(p['seed']) is int and 0<=p['seed']<2**63 and p['scope_parameters']==parameters(p),'EXPLICIT_ONE_DAY_SCOPE_AND_UNCHANGED_COUNTS')
    m,formal,hof,data,refs=common(p);post=meta(p['postprocess_entry_reference']);review=meta(m['root_component_review'])
    postplan=meta(post['plan_reference']);cacheplan=meta(postplan['cache_plan_reference'])
    need(cacheplan['hof_authority_review']==p['hof_authority_reference'],'SAME_ACTUAL_POSTPROCESS_CANONICAL_HOF_AUTHORITY')
    mapping=meta(p['native_source_frame_review_reference'])
    need(mapping['schema']=='ROOT_D5_COMPOUND_SHARED_SOURCE_FRAME_REVIEW_V1' and mapping['status']=='APPROVED_EXACT_SOURCE_LOCATOR'
        and mapping['reviewer']=='root' and mapping['compute_node']==p['node'] and mapping['canonical_reference']==formal
        and mapping['prior_CPU13_validation_reference']==meta(p['ordinary_source_review_reference'])['canonical_node13_source_validation_reference']
        and mapping['whole_CPU_SHA_and_stable_current_device_required'] is True and mapping['inode_size_mtime_uid_unchanged'] is True,
        'INDEPENDENT_REAL_NODE_SHARED_MAPPING_NOT_FAKE_CPU13_DEVICE')
    meta(mapping['actual_same_storage_mapping_probe_reference'])
    refs=unique([*refs,p['native_source_frame_review_reference'],mapping['actual_same_storage_mapping_probe_reference'],post['plan_reference'],postplan['cache_plan_reference']])
    need(p['postprocess_entry_reference']==p['common_closure_references']['entry'] and review['approve_D7'] is True
      and post['three_order_Common_release_eligible'] is True and post['ordinary_Common_D7_geometry_complete'] is True,'REAL_ACCEPTED_COMPLETE_D7_CACHE_AND_ORDERS_BEFORE_D5_REUSE')
    data=unique([*data,post['catalog_reference']]);refs=unique([*refs,p['postprocess_entry_reference'],m['root_component_review']])
    if p['purpose']=='full':
        v=meta(p['actual512_review_reference']);r,prior,more=closure(v['pilot_closure_references'])
        need(v['schema']=='ROOT_D5_COMPOUND_ACTUAL512_REVIEW_V1' and v['status']=='APPROVED_EXACT_SOURCE_TYPED_ORDER_PARITY'
          and v['reviewer']=='root' and prior['purpose']=='pilot512' and prior['common_closure_references']==p['common_closure_references']
          and r['technical_phase_closed'] is True and r['status']=='COMPLETE_TECHNICAL_COMPOUND_REQUIRES_ROOT_REVIEW' and r['molecules']==512 and r['full_typed_source_order_identity_parity'] is True and r['held_molecules']==0,'REAL_COMPOUND512_C0_BEFORE_FULL')
        refs=unique([*refs,p['actual512_review_reference'],*more])
    previous=p.get('previous_compound_closures',[]);adoptions=p.get('previous_prefix_adoption_review_references',[])
    need(len(previous)==len(adoptions),'ROOT_EXPLICIT_ADOPTION_PER_ACTUAL_VERIFIED_PREFIX')
    for chain,adoption in zip(previous,adoptions):
        r,old,more=closure(chain);need(old['common_closure_references']==p['common_closure_references'] and old['seed']==p['seed']
          and old['phase']==p['phase'] and (old['purpose']==p['purpose'] or (old['purpose']=='pilot512' and p['purpose']=='full')),'EXACT_SAME_COMPOUND_DOMAIN_FOR_SAFE_PREFIX_ADOPTION')
        a=meta(adoption);need(a['schema']=='ROOT_D5_COMPOUND_VERIFIED_PREFIX_ADOPTION_V1' and a['status']=='APPROVED_EXACT_ACTUAL_PREFIX'
            and a['reviewer']=='root' and a['closure_references']==chain and a['never_started_or_unknown_claimed_complete'] is False
            and r['unresolved_molecules']==0 and r['unverified_partition_reference'] is None,'NO_AUTO_ADOPTION_OF_UNKNOWN_OR_FAILED_WORK')
        need(old['source_compatibility_references']==p['source_compatibility_references'],'EXACT_SAME_FROZEN_PRODUCER_FOR_PREFIX')
        data=unique([*data,r['verified_partition_catalogue_reference']]);refs=unique([*refs,*more,adoption])
    if p['phase']!='ordinary_base':
        v=meta(p['WP5_input_derivation_authority_reference'])
        need(v['schema']=='ROOT_D5_CANONICAL_WP5_INPUT_DERIVATION_AUTHORITY_V1' and v['status']=='APPROVED_EXACT_ORIGINAL_INPUT_HASH_DERIVATION'
            and v['reviewer']=='root' and v['common_manifest_reference']==p['common_closure_references']['manifest']
            and v['source_files_reference']==hof['source_files_reference'] and v['canonical_owner_reference']==hof['latest_owner_reference']
            and v['actual_per_call_both_input_hashes_required'] is True and v['original_UUID_missing_remains_UNKNOWN'] is True
            and v['canonical_occurrence_identity_domain_explicit'] is True and v['no_new_QM_UFF_or_graph_repair'] is True,
            'REAL_WHOLE_CANONICAL_WP5_INPUT_SOURCE_AUTHORITY_NOT_ONLY_RETAINED32')
        need(v['expected_perturbed_tasks'] and v['package_protocol_references'],'EXACT_ORIGINAL_PROTOCOL_AND_PACKAGE_SET')
        refs=unique([*refs,p['WP5_input_derivation_authority_reference']])
        for r in v['package_protocol_references']:
            pkg=meta(r['package_reference']);protocol=meta(r['protocol_reference'])
            need(pkg['status']=='REPRODUCTION_PACKAGE_CLOSED' and pkg['protocol']['path']==r['protocol_reference']['path']
                and pkg['protocol']['sha256']==r['protocol_reference']['sha256']
                and {t['name'] for t in protocol['tasks'] if t.get('perturbed') is True}==set(v['expected_perturbed_tasks']),
                'EXACT_ACTUAL_REPRODUCTION_PROTOCOL_NOT_GUESSED_INPUT_RECIPE')
            refs=unique([*refs,r['package_reference'],r['protocol_reference']])
    if p['phase']!='ordinary_base' and p['purpose']=='full':
        views=meta(p['D5_input_view_review_reference']);need(views['reviewer']=='root'
            and views['common_manifest_reference']==p['common_closure_references']['manifest'],'ROOT_EXPLICIT_D5_INPUT_VIEW')
        roles=meta(meta(m['config'])['roles_authority']);source_roles=meta(roles['source_role_manifest'])
        role_tables=[reference(r) for r in source_roles['outputs'] if '/molecule_roles/' in r['path']]
        need(role_tables and views['feature_tables']==m['membership_tables'] and views['feature_filter_column']=='common_population'
            and set(views['columns'])==set(D.TABLES),'ROOT_EXPLICIT_FULL_SAMPLER_COLUMNS_ROLES_AND_FEATURES')
        refs=unique([*refs,p['D5_input_view_review_reference'],meta(m['config'])['roles_authority'],roles['source_role_manifest']]);data=unique([*data,*role_tables])
    if p['phase']=='all_actual_children_and_D5':
        need(p.get('actual_child_input_authority_reference') and p.get('N1_final_policy_reference') and p.get('D5_input_view_review_reference'),
          'NO_INVENTED_FULL_CHILD_OR_N1_DOMAIN')
        child=meta(p['actual_child_input_authority_reference']);policy=meta(p['N1_final_policy_reference']);views=meta(p['D5_input_view_review_reference'])
        need(child['reviewer']=='root' and child['status']=='ROOT_REVIEWED_COMPLETE_ACTUAL_INPUT_EVIDENCE'
          and child['common_manifest_reference']==p['common_closure_references']['manifest'] and child['all_actual_direct_children_covered'] is True
          and child['unobserved_future_calls_included'] is False and child['independent_diagnostic_calls_used_as_production_children'] is False
          and all(type(child[k]) is int and child[k]==0 for k in ('missing_input_hash_count','unknown_call_domain_count','unverified_call_count')),
          'COMPLETE_REAL_CHILD_DOMAIN_ONLY_NO_QA_OR_FUTURE_CALLS')
        need(policy['status']=='ROOT_REVIEWED_N1_N2_ORDINARY_D5_POLICY' and policy['ordinary_sprime_count_unchanged'] is True
          and policy['Pprime_extra_not_ordinary'] is True,'REAL_FINAL_N1_POLICY_NOT_CREATED_BY_HELPER')
        need(child['additional_child_domain']=='ACTUAL_ORDINARY_UFF_PPRIME_ONLY' and child['schema']=='ROOT_D5_ACTUAL_CHILD_INPUT_AUTHORITY_V1' and policy['reviewer']=='root' and policy['common_manifest_reference']==p['common_closure_references']['manifest'],'EXACT_ACTUAL_CHILD_AND_N1_POLICY_SCHEMA')
        need(views['reviewer']=='root' and views['common_manifest_reference']==p['common_closure_references']['manifest'],'ROOT_EXPLICIT_D5_INPUT_COLUMN_VIEW')
        roles=meta(meta(m['config'])['roles_authority']);source_roles=meta(roles['source_role_manifest'])
        role_tables=[reference(r) for r in source_roles['outputs'] if '/molecule_roles/' in r['path']]
        need(role_tables and views['feature_tables']==m['membership_tables'] and views['feature_filter_column']=='common_population'
            and set(views['columns'])==set(D.TABLES),'ROOT_EXPLICIT_FULL_SAMPLER_COLUMNS_ROLES_AND_FEATURES')
        refs=unique([*refs,meta(m['config'])['roles_authority'],roles['source_role_manifest']])
        data=unique([*data,*role_tables,child['binding_index_reference'],*child['evidence_DATA_references']]);refs=unique([*refs,p['actual_child_input_authority_reference'],p['N1_final_policy_reference'],p['D5_input_view_review_reference'],*child['protocol_source_references']])
    return m,formal,hof,data,refs
