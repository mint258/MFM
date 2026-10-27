"""Actual1750 archive/source and1818 key profile; no active/full-source database."""
from pathlib import Path
from workflows.expansion.marcel_drugs_keys_main_v1 import contract as D
Q=D.Q;meta=D.M.meta;unique=D.unique;HERE=Q.REPO/'workflows/expansion/marcel_drugs_native_graph_profile_v1'
FILES=('__init__.py','contract.py','reader.py','kernel.py','run.py','test_v1.py','materialize.py','README.md')
OLD=tuple(D.HERE/n for n in D.FILES)+D.OLD
MODULE='workflows.expansion.marcel_drugs_native_graph_profile_v1.run';KEY='marcel_drugs_native_graph_profile_main_v1'
STAGE='MARCEL_DRUGS1000_NATIVE_SDF_GRAPH_AND_ALL_OBSERVED_SOURCE_KEY_UNION_PROFILE'
CAP=2<<30;N=D.N;SOURCE_PROFILE_N=D.PILOT_N;PROFILE_N=1000;SEED=D.SEED
AUTHOR='https://raw.githubusercontent.com/SXKDZ/MARCEL/dae6b3b824b68d1362ed3b9fa23b34a45fa5366c/benchmarks/data/drugs.py'
PARAMETERS={'mode':'profile','producer_source_job_id':'4521750','producer_key_profile_job_id':'4521818','source_SDF_records':N,'source_CSV_rows':D.CSV_N,
    'source_key_profile_rows':SOURCE_PROFILE_N,'native_graph_selected_rows':PROFILE_N,'selection':'FIRST1000_DRAW_ORDER_OF_ORIGINAL_RANDOM_SAMPLE10000',
    'uniform_without_replacement_seed':SEED,'sampler_python':'3.11.14','RDKit_version':'2025.09.5',
    'all_source_rows_bound_to_original401229188_byte_journal':True,'all_ZIP_members_current_SHA_fstat_CRC_EOF':True,
    'original_sdf_rows_and_sdf_record_function_objects':True,'new_readline_seam':'RETAIN_EXACT_CURRENT_RECORD_BYTES_ONLY',
    'native_graph_seam':'Chem.SDMolSupplier(single_original_record_file,removeHs=False); default sanitize and strictParsing',
    'MolFromMolBlock_called':False,'original_literal_ID_name_smiles_and_record_SHA_preserved':True,
    'source_SMILES_keys_recomputed':False,'source_key_profile_journal_current_SHA_and_all10000_events_bound':True,
    'name_union':'ALL_OBSERVED_SOURCE_VARIANT_KEYS_PLUS_ALL_OBSERVED_NATIVE_GRAPH_KEYS_NO_REPRESENTATIVE',
    'unselected_native_graph_state':'NOT_YET_EXAMINED','unknown_is_chemical_exclusion':False,
    'new_fixture_methods':3,'all3_before_any_original_data_body':True,'workers':16,'maximum_pending':32,'worker_threads':1,
    'source_record_bytes_and_source_event_durable_before_dispatch':True,'native_result_durable_before_SQL_or_union':True,
    'raw_record_retention':'ONE_O_APPEND_FSYNC_BLOB_WITH_BYTE_SHA_SEGMENTS_AND_ACTUAL_FINAL_WHOLE_PIN',
    'maximum_node_local_single_record_SDF_bytes_all_workers':256<<20,
    'algorithm_parent_direct_children_RSS_soft_cap_bytes':16<<30,'minimum_MemAvailable_bytes':4<<30,'whole_output_cap_bytes':CAP,
    'drain_reserve_bytes':256<<20,'maximum_SDF_record_bytes':16<<20,'original290_multi_SMILES_name_groups_retained':True,
    'full1858_or_active_SQLite_read':False,'X_filter_repair_neutralization_tautomer_stereo_isotope_or_geometry_edit':False,
    'native_composition_fallback_claimed':False,'new_network_UFF_QM_calls':0,'full_or_pool_or_decontamination_release':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}


def inputs(plan):
    r=meta(plan['accepted_source_key_profile_receipt_reference']);p=meta(r['plan_reference']);proof=meta(r['startup_proof_reference'])
    Q.need(r['schema']=='MARCEL_DRUGS_KEYS_RECEIPT_V1' and r['status']=='EXACT_SELECTED_CONFORMER_KEYS_OBSERVED_UNKNOWNS_RETAINED'
        and r['mode']=='profile' and str(r['job_id'])=='4521818' and r['uid']==1278 and r['endpoint']=='202.38.247.57:22'
        and r['selected_completed_rows']==SOURCE_PROFILE_N and r['selected_unknown_rows']==0
        and r['fixtures']['tests_run']==3 and all(r['fixtures'][k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),
        'ACTUAL1818_BOUNDED_SOURCE_KEY_PROFILE_NOT_FULL_OR_GRAPH_ACCEPTANCE')
    Q.need(p['mode']=='profile' and p['scope_parameters']==D.parameters('profile',1<<30)==proof['request']['scope_parameters']
        and str(proof['job_id'])=='4521818' and proof['uid']==1278 and proof['request']['node']==r['node']
        and proof['request']['scope_key']==D.scope_key('profile') and r['plan_reference'] in proof['request']['source_references']
        and r['input_reference']==p['input_reference'],'ACTUAL1818_SAME_PROFILE_PLAN_PROOF_INPUT')
    for path in OLD:Q.need(Q.pin(path) in proof['request']['source_references'],'UNCHANGED_ORIGINAL_SOURCE_PROFILE_AND_KEY_KERNEL')
    b,parents=D.inputs(p);_,raw=D.account(plan['accepted_source_key_profile_accounting_reference'],r)
    original=meta(b['plan_reference']);archive=original['archive_reference'];inventory=original['inventory_reference'];journal=r['selected_result_journal_reference']
    Q.need(journal['bytes']==21838201 and journal['sha256']=='2aaaeca73541a14a15d1b6d4e0069cd851869eb8afb7426a57dc37b229de7329'
        and r['input_context']['source_multi_SMILES_name_groups']==290,'EXACT_ACTUAL1818_PRODUCER_JOURNAL_NOT_COMPLETION_ORDER_SELECTION')
    data=[archive,inventory,p['input_reference'],journal]
    refs=unique([*parents,plan['accepted_source_key_profile_receipt_reference'],plan['accepted_source_key_profile_accounting_reference'],raw,r['plan_reference'],r['startup_proof_reference']])
    return b,r,original,data,refs
