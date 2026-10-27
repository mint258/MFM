"""Actual full C0 / source authority; metadata never opens the three DATA files."""
import re
from pathlib import Path
from workflows.expansion.marcel_kraken_keys_main_v1 import contract as K
from workflows.expansion.tdc_zip44_identity_main_v1 import contract as T
Q=K.Q
HERE=Q.REPO/'workflows/expansion/marcel_kraken_decontamination_main_v1'
FILES=('__init__.py','contract.py','projection.py','runtime.py','run.py','test_v1.py','materialize.py','README.md')
OLD=tuple(K.HERE/n for n in K.FILES)+K.OLD+(Q.REPO/'workflows/expansion/decontamination.py',)
KEY='marcel_kraken_decontamination_main_v1'
MODULE='workflows.expansion.marcel_kraken_decontamination_main_v1.run'
STAGE='KRAKEN_ACTUAL_FULL_KEYS_TO_ALL_SOURCE_CONSERVATIVE_IDENTITY_ROWS'
CAP=512<<20
COMMIT='dae6b3b824b68d1362ed3b9fa23b34a45fa5366c'
VERSION='MARCEL/Kraken:code-'+COMMIT+':archive-sha256-5152df55775da397e39d98c9e856f371d098e87fc55fea329147afc16b6b0fcc'
PARAMETERS={'actual_full_identity_parent':'4521873','native_roots':1552,'native_conformers':21287,'source_relationships':22839,
    'input_DATA_files':3,'all_source_keys_preserved_as_per_root_conservative_union':True,
    'root_SMILES_MolBlock_differences_retained':1201,'multiple_full_key_roots_retained':134,
    'output_role':'all','role_basis':'CONSUMER_ALL_SOURCE_SCOPE_NOT_A_NEW_NATIVE_SPLIT',
    'original_native_ID_tokens_and_assignment_ordinals_retained':True,'source_record_id_is_archive_plus_native_assignment_locator':True,
    'original_decontamination_identity_keys_and_wp5_function_objects':True,
    'new_graph_SMILES_normalization_or_repair':False,'new_pickle_or_archive_decoding':False,
    'new_pure_fixture_methods':3,'all3_before_any_DATA':True,'allocated_cpus':16,'sequential_streams':1,
    'maximum_JSONL_line_bytes':8<<20,'hash_chunk_bytes':1<<20,'job_owned_SQLite_join_only':True,
    'original_inputs_or_production_once_modified':False,'new_network_UFF_QM_calls':0,
    'output_cap_bytes':CAP,'global_pool_release':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}
unique=K.unique
meta=T.meta


def data_reference(ref):
    Q.need(type(ref) is dict and set(ref)=={'path','bytes','sha256'} and type(ref['bytes']) is int and ref['bytes']>0
        and type(ref['sha256']) is str and re.fullmatch('[0-9a-f]{64}',ref['sha256']) is not None,'EXACT_DATA_TRIPLE_NO_SMALL_REFERENCE_CAP')
    p=Path(ref['path']);Q.need(p.is_absolute() and '..' not in p.parts and Q.ROOT/'artifacts' in p.parents,'LITERAL_MAIN_ARTIFACT_DATA')
    return ref


def inputs(plan):
    b=meta(plan['accepted_full_receipt_reference']);_,raw=K.account(plan['accepted_full_accounting_reference'],b)
    Q.need(b['schema']=='MARCEL_KRAKEN_KEYS_RECEIPT_V1' and b['status']=='EXACT_SELECTED_SOURCE_KEYS_OBSERVED_UNKNOWNS_AND_MISMATCHES_RETAINED'
        and b['mode']=='full' and str(b['job_id'])=='4521873' and b['uid']==1278 and b['endpoint']=='202.38.247.57:22'
        and b['node']=='compute-0-19' and b['complete_source_relationship_rows']==22839
        and b['completed_by_kind']=={'root_SMILES':1552,'conformer_MolBlock':21287}
        and b['unknown_by_kind']=={'root_SMILES':0,'conformer_MolBlock':0}
        and b['identity_state_counts']=={'ROOT_SMILES_FULL_KEYS_DERIVED':1552,'MOLBLOCK_GRAPH_FULL_KEY_DERIVED':21287}
        and b['root_union_counts']=={'root_unions':1552,'partial_conformer_coverage_roots':0,'multiple_observed_full_key_roots':134,
            'unknown_root_SMILES':0,'roots_with_unknown_selected_conformer':0}
        and b['root_SMILES_vs_MolBlock_comparison_counts']=={'FULL_SOURCE_KEYS_EQUAL':20086,'ROOT_SMILES_AND_NATIVE_MOLBLOCK_FULL_KEYS_DIFFER':1201}
        and b['source_or_pool_accepted'] is False and b['source_graph_stereo_or_pool_release'] is False
        and b['fixtures']['tests_run']==3 and all(b['fixtures'][k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),
        'EXACT_ACTUAL4521873_FULL_SOURCE_C0_NOT_POOL_ACCEPTANCE')
    old=meta(b['plan_reference']);proof=meta(b['startup_proof_reference']);request=meta(proof['request_reference'])
    expected=[Q.PY,'-B','-m',K.MODULE,'--plan',b['plan_reference']['path'],'--startup-proof',b['startup_proof_reference']['path']]
    Q.need(proof['schema']=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1' and str(proof['job_id'])=='4521873' and proof['uid']==1278
        and proof['node']==b['node'] and proof['execution_admission_granted'] is True and request==proof['request']
        and request['execution_argv']==expected and request['scope_key']==K.scope_key('full') and request['node']==b['node']
        and request['kind']=='analysis' and request['pilot'] is False and request['cpus']==16
        and request['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and old['schema']=='MARCEL_KRAKEN_KEYS_PLAN_V1'
        and old['mode']=='full' and old['scope_parameters']==request['scope_parameters']==K.parameters('full',1<<30)
        and b['plan_reference'] in request['source_references'] and request['data_references']==[old['archive_reference'],old['inventory_reference']]
        and b['archive_reference']==old['archive_reference'] and b['inventory_reference']==old['inventory_reference'],
        'ACTUAL_OLD_PRIMARY_FULL_ARGV_PLAN_REQUEST_AND_DATA_AUTHORITY')
    for path in [*(K.HERE/n for n in K.FILES),*K.OLD]:Q.need(Q.pin(path) in request['source_references'],'UNCHANGED_ORIGINAL_FULL_PRODUCER_SOURCE')
    refs=[data_reference(b[k]) for k in ('selected_result_journal_reference','all_source_relationship_journal_reference','all_root_union_reference')]
    Q.need(plan['data_references']==refs and len({r['path'] for r in refs})==3,'EXACT_THREE_OLD_OUTPUT_LOCATORS_NEVER_LOGIN_HASH')
    policy=meta(plan['decontamination_policy_reference']);source=[s for s in policy['sources'] if s['dataset']=='marcel_kraken']
    Q.need(policy['schema']=='expansion_decontamination_sources_v1' and len(source)==1 and source[0]['required_roles']==['all']
        and not source[0].get('required_subdatasets') and policy['identity_policy']['exact']=='full_inchikey'
        and policy['identity_policy']['wp5']=='inchikey_first14+colon+last_protonation_character','EXISTING_CONSUMER_KEY_AND_ALL_SOURCE_ROLE_POLICY')
    parents=[plan['accepted_full_receipt_reference'],plan['accepted_full_accounting_reference'],raw,b['plan_reference'],b['startup_proof_reference'],
        proof['request_reference'],plan['decontamination_policy_reference'],b['accepted_structure_receipt_reference'],b['accepted_structure_accounting_reference']]
    parents.extend(old[k] for k in ('accepted_profile_receipt_reference','accepted_profile_accounting_reference','profile_root_review_reference'))
    for ref in parents:Q.need(Q.pin(ref['path'])==ref,'ACTUAL_SMALL_PARENT_OR_POLICY_UNCHANGED')
    return b,unique(parents)
