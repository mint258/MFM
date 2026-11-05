"""Actual native3547/full-keys1858 parents and finite full graph review."""
from __future__ import annotations
import math,pathlib,re
from workflows.expansion.marcel_drugs_native_graph_profile_v1 import contract as P
Q=P.Q;meta=P.meta;unique=P.unique;D=P.D
HERE=Q.REPO/'workflows/expansion/marcel_drugs_native_graph_full_v1'
FILES=('__init__.py','contract.py','materialize.py','cache.py','run.py','test_v1.py','frozen_original_sources.json','README.md')
MODULE='workflows.expansion.marcel_drugs_native_graph_full_v1.run';KEY='marcel_drugs_native_graph_full_main_v1'
N=D.N;CSV_N=D.CSV_N;INHERITED=P.PROFILE_N;NEW=N-INHERITED;CAP=12<<30;WALL=12*3600
NODE_SDF_RESERVE=256<<20;SHARED_CAP=CAP-NODE_SDF_RESERVE
STAGE='MARCEL_DRUGS_ALL558002_NATIVE_GRAPH_OBSERVATIONS_1000_ACTUAL_C0_ADOPTED_557002_NEW'
OLD=tuple(P.HERE/n for n in P.FILES)+P.OLD


def triple(value):
    r={k:value[k] for k in ('path','bytes','sha256')};p=pathlib.Path(r['path'])
    Q.need(p.is_absolute() and '..' not in p.parts and type(r['bytes']) is int and r['bytes']>0
        and type(r['sha256']) is str and re.fullmatch('[0-9a-f]{64}',r['sha256']) is not None,'EXACT_LARGE_DATA_LOCATOR_NO_SMALL_SOURCE_CEILING')
    return r


def parameters():
    return {'mode':'full','source_SDF_records':N,'source_CSV_names':CSV_N,'source_context_rows':N+CSV_N,
        'original_multi_SMILES_name_groups':290,'inherited_actual_native_profile_rows':INHERITED,'new_native_graph_dispatches':NEW,
        'native_profile_job_id':'4523547','full_source_key_job_id':'4521858','workers':16,'maximum_pending':32,'worker_threads':1,
        'original_source_and_graph_function_objects':True,'source_SMILES_keys_recomputed':False,
        'physical_SDF_once_per_full_scan':True,'already_closed1000_native_graphs_not_reinvoked':True,
        'all_original_name_ID_SMILES_variants_records_and_raw_preserved':True,'unknown_is_chemical_exclusion':False,
        'all6_before_original_DATA_bodies':True,'original_profile_fixtures':3,'new_full_fixtures':3,
        'RDKit_version':'2025.09.5','python_version':'3.11.14','source_record_max_bytes':16<<20,
        'native_graph_seam':'ORIGINAL_Chem.SDMolSupplier_REMOVE_HS_FALSE_DEFAULT_SANITIZE_STRICT',
        'original_raw_SDF_blob_retained_all558002':True,'full_source_key_cache':'NEW_JOB_SQLITE_ONLY_STREAMED_ORIGINAL_FULL_JOURNAL',
        'wall_seconds':WALL,'whole_output_cap_bytes':CAP,'parent_children_RSS_soft_cap_bytes':16<<30,
        'node_local_max_simultaneous_SDF_bytes':NODE_SDF_RESERVE,'shared_output_cap_bytes':SHARED_CAP,'minimum_MemAvailable_bytes':4<<30,
        'all_ZIP_members_full_CRC_SHA_EOF':True,'source_and_result_durable_before_dispatch_and_union':True,
        'new_network_UFF_QM_calls':0,'native_composition_fallback_claimed':False,
        'graph_repair_neutralization_tautomer_stereo_isotope_or_geometry_edit':False,
        'global_decontamination_pool_or_training_release':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}


def project(profile):
    journal=(profile['native_result_journal_reference']['bytes']*N+INHERITED-1)//INHERITED
    sdf=next(r for r in profile['all_member_observations'] if r['name']=='Drugs.sdf')
    fixed=profile['owned_output_bytes_before_receipt']-profile['native_result_journal_reference']['bytes']-profile['original_selected_records_blob_reference']['bytes']-profile['all_name_union_reference']['bytes']
    return {'native_journal_linear_bytes':journal,'exact_all_SDF_raw_blob_bytes':sdf['decoded_bytes'],
        'profile_observed_fixed_excluding_journal_raw_and_names_bytes':fixed,
            'profile_observed_name_union_bytes':profile['all_name_union_reference']['bytes'],
        'new_cache_and_SQLite_index_additional_reserve_bytes':3<<30,'drain_and_admin_reserve_bytes':512<<20,
        'projection_is_descriptive_not_worst_case_or_performance_guarantee':True}


def inputs(plan,require_review=True):
    native=meta(plan['accepted_native_profile_receipt_reference']);native_plan=meta(native['plan_reference']);native_proof=meta(native['startup_proof_reference'])
    Q.need(native['schema']=='MARCEL_DRUGS_NATIVE_GRAPH_PROFILE_RECEIPT_V1'
        and native['status']=='EXACT1000_NATIVE_GRAPH_OBSERVATIONS_COMPLETE_UNKNOWNS_AND_UNIONS_RETAINED'
        and str(native['job_id'])=='4523547' and native['mode']=='profile' and native['uid']==1278
        and native['endpoint']=='202.38.247.57:22' and native['native_graph_completed_rows']==INHERITED
        and native['native_graph_unknown_rows']==native['native_graph_source_key_set_mismatch_rows']==native['native_graph_source_key_comparison_UNKNOWN_rows']==0
        and native['native_graph_NOT_YET_EXAMINED_rows']==NEW and native['all_current_ZIP_EOF_CRC_SHA_and_source_row_bindings_complete'] is True,
        'REAL_NATIVE3547_CLOSED1000_NOT_FULL_ACCEPTANCE')
    Q.need(native_plan['mode']=='profile' and native_plan['scope_parameters']==native_proof['request']['scope_parameters']==P.PARAMETERS
        and native_proof['request']['scope_key']==P.KEY and str(native_proof['job_id'])=='4523547'
        and native_proof['uid']==1278 and native_proof['request']['node']==native['node']
        and native['plan_reference'] in native_proof['request']['source_references'],'NATIVE_PROFILE_EXACT_PLAN_PROOF_IDENTITY')
    for p in OLD:Q.need(Q.pin(p) in native_proof['request']['source_references'],'ALL_ORIGINAL_NATIVE_PROFILE_SOURCES_STILL_EXACT')
    _,_,original,data0,parents=P.inputs(native_plan);_,native_raw=D.account(plan['accepted_native_profile_accounting_reference'],native)
    full=meta(plan['accepted_source_key_full_receipt_reference']);full_plan=meta(full['plan_reference']);full_proof=meta(full['startup_proof_reference'])
    Q.need(full['schema']=='MARCEL_DRUGS_KEYS_RECEIPT_V1' and full['mode']=='full' and str(full['job_id'])=='4521858'
        and full['uid']==1278 and full['endpoint']=='202.38.247.57:22'
        and full['status']=='EXACT_SELECTED_CONFORMER_KEYS_OBSERVED_UNKNOWNS_RETAINED'
        and full['selected_completed_rows']==N and full['selected_unknown_rows']==0
        and full['input_reference']==data0[2] and full['input_context']==native['input_context']
        and full['name_identity_union_counts']['partial_names']==0,'ACTUAL_FULL1858_ALL_VARIANT_KEY_COVERAGE')
    _,full_parents=D.inputs(full_plan);_,full_raw=D.account(plan['accepted_source_key_full_accounting_reference'],full)
    Q.need(full_plan['mode']=='full' and full_plan['scope_parameters']==full_proof['request']['scope_parameters']==D.parameters('full',full_plan['output_cap_bytes'])
        and full_proof['request']['scope_key']==D.scope_key('full') and str(full_proof['job_id'])=='4521858'
        and full_proof['uid']==1278 and full_proof['request']['node']==full['node']
        and full['plan_reference'] in full_proof['request']['source_references'],'FULL_KEY_SOURCE_EXACT_FROZEN_PLAN_PROOF')
    for p in [*(D.HERE/n for n in D.FILES),*D.OLD]:Q.need(Q.pin(p) in full_proof['request']['source_references'],'UNCHANGED_ORIGINAL_FULL_SOURCE_KEY_FUNCTIONS')
    for receipt in (native,full):
        f=receipt['fixtures'];Q.need(f['tests_run']==3 and all(f[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'REAL_PARENT_PURE3_PASS')
    data=[data0[0],data0[1],data0[2],full['selected_result_journal_reference'],native['native_result_journal_reference'],native['original_selected_records_blob_reference']]
    data=[triple(r) for r in data];Q.need(len({r['path'] for r in data})==6,'EXACT6_ORIGINAL_PRODUCER_DATA_FILES')
    refs=unique([*parents,*full_parents,plan['accepted_native_profile_receipt_reference'],plan['accepted_native_profile_accounting_reference'],native_raw,
        native['plan_reference'],native['startup_proof_reference'],plan['accepted_source_key_full_receipt_reference'],
        plan['accepted_source_key_full_accounting_reference'],full_raw,full['plan_reference'],full['startup_proof_reference']])
    frozen=meta(Q.pin(HERE/'frozen_original_sources.json'))
    Q.need(frozen['schema']=='MARCEL_DRUGS_NATIVE_FULL_FROZEN_ORIGINAL_SOURCES_V1'
        and len(frozen['source_references'])==15,'EXACT_FROZEN_ORIGINAL_SOURCE_CLOSURE')
    for r in frozen['source_references']:Q.need(Q.pin(r['path'])==r,'ORIGINAL_SOURCE_BYTE_IDENTITY_REQUIRED')
    refs=unique([*refs,*frozen['source_references']])
    if require_review:
        review=meta(plan['profile_budget_root_review_reference']);projection=project(native)
        Q.need(review['schema']=='ROOT_DRUGS_NATIVE_FULL_COST_STORAGE_REVIEW_V1' and review['status']=='APPROVED_FOR_EXACT_FULL_NATIVE_GRAPH_OBSERVATION'
            and review['reviewer']=='root' and review['accepted_native_profile_receipt_reference']==plan['accepted_native_profile_receipt_reference']
            and review['accepted_native_profile_accounting_reference']==plan['accepted_native_profile_accounting_reference']
            and review['accepted_source_key_full_receipt_reference']==plan['accepted_source_key_full_receipt_reference']
            and review['accepted_source_key_full_accounting_reference']==plan['accepted_source_key_full_accounting_reference']
            and review['actual_profile_cost_unknowns_and_source_mismatches_reviewed'] is True
            and review['all558002_native_graphs_1000_adopted557002_new_authorized'] is True
            and review['all75099_names_all633101_context_rows_and290_variant_groups_retained'] is True
            and review['projection']==projection and review['wall_seconds']==plan['wall_seconds']==WALL
            and review['output_cap_bytes']==plan['output_cap_bytes']==CAP and review['storage_and_200GB_reserve_reviewed'] is True
            and review['shared_output_cap_bytes']==SHARED_CAP and review['node_local_SDF_reserved_bytes']==NODE_SDF_RESERVE
            and review['exact_DATA_references']==data
            and review['actual_native_profile_allocated_core_seconds']==meta(plan['accepted_native_profile_accounting_reference'])['allocated_core_seconds']
            and review['actual_source_key_full_allocated_core_seconds']==meta(plan['accepted_source_key_full_accounting_reference'])['allocated_core_seconds']
            and review['unknown_or_graph_mismatch_is_chemical_exclusion'] is False
            and review['pool_or_global_decontamination_release_authorized'] is False,'ROOT_ACTUAL_PROFILE_COST_STORAGE_AND_COMPLETE_NATIVE_SCOPE_REVIEW')
        Q.need(CAP>=sum(v for k,v in projection.items() if k.endswith('_bytes')),'REVIEWED_CAP_COVERS_DESCRIPTIVE_PROJECTION_AND_RESERVES')
        refs=unique([*refs,plan['profile_budget_root_review_reference']])
    return native,full,original,data,refs


def source_paths():
    paths=[*(HERE/n for n in FILES),*OLD]
    paths.extend((Q.REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2').glob('*.py'))
    Q.need(all(p.exists() for p in paths),'ALL_NEW_AND_REUSED_FULL_NATIVE_SOURCES_INSTALLED')
    return list(dict.fromkeys(paths))
