"""Actual401MB producer log and bounded profile/full Main identity contract."""
import csv,io
from pathlib import Path
from workflows.expansion.marcel_identity_format_probe_v1 import contract as M
from workflows.expansion.tdc_zip44_identity_main_v1 import contract as T
Q=M.Q;HERE=Q.REPO/'workflows/expansion/marcel_drugs_keys_main_v1'
FILES=('__init__.py','contract.py','rows.py','kernel.py','runtime.py','run.py','test_v1.py','materialize.py','README.md')
MODULE='workflows.expansion.marcel_drugs_keys_main_v1.run';STAGE='MARCEL_DRUGS_ALL_NATIVE_CONFORMER_SMILES_CONSERVATIVE_KEYS'
OLD=tuple(M.HERE/n for n in M.FILES)+tuple(Q.REPO/n for n in M.OLD)+tuple(T.HERE/n for n in T.FILES)+tuple(Q.REPO/n for n in T.OLD)
N=558002;CSV_N=75099;PILOT_N=10000;SEED=20261027
def scope_key(mode):Q.need(mode in ('profile','full'),'EXACT_MODE');return 'marcel_drugs_keys_main_v1_'+mode


def unique(refs):
    by={}
    for r in refs:Q.need(r['path'] not in by or by[r['path']]==r,'CONFLICTING_ACTUAL_REFERENCE');by[r['path']]=r
    return [by[k] for k in sorted(by)]


def account(reference,receipt):
    a=M.meta(reference);raw=a['raw_sacct_reference'];Q.need(Q.pin(raw['path'])==raw,'ACTUAL_MAIN_RAW_ACCOUNTING_PIN')
    rows=[r for r in csv.DictReader(io.StringIO(Q.read_small(raw['path']).decode('utf-8')),delimiter='|') if '.' not in r['JobIDRaw']]
    Q.need(a['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and a['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
        and a['endpoint']=='202.38.247.57:22' and a['uid']==1278 and a['query_returncode']==0
        and a['failed_timeout_startup_cleanup_elapsed_retained'] is True and len(a['parents'])==len(rows)==1,'EXACT_ONE_ACTUAL_MAIN_PARENT')
    p=a['parents'][0];r=rows[0];Q.need(p['job_id']==r['JobIDRaw']==str(receipt['job_id']) and p['state']==r['State']=='COMPLETED'
        and p['exit_code']==r['ExitCode']=='0:0' and p['node']==r['NodeList']==receipt['node'] and r['UID']=='1278'
        and p['alloc_cpus']==int(r['AllocCPUS'])==16 and p['elapsed_raw_seconds']==int(r['ElapsedRaw'])
        and a['allocated_core_seconds']==16*p['elapsed_raw_seconds'],'REAL_C0_SAME_MAIN_NODE_UID_AND_ACTUAL_COST')
    return a,raw


def parameters(mode,cap):
    Q.need(mode in ('profile','full') and type(cap) is int and (cap==1<<30 if mode=='profile' else 1<<30<=cap<=16<<30),'EXACT_PROFILE_OR_REVIEWED_FULL_CAP')
    return {'mode':mode,'source_id':'marcel_drugs_zip','producer_job_id':'4521750','input_identity_log_bytes':401229188,
        'all_CSV_name_rows':CSV_N,'all_SDF_conformers':N,'all_input_log_rows':CSV_N+N,
        'selected_SDF_rows':PILOT_N if mode=='profile' else N,'uniform_without_replacement_seed':SEED if mode=='profile' else None,
        'all_source_context_parsed_and_retained_even_in_profile':True,'original_multi_SMILES_byte_name_groups':290,
        'source_scope':'ALL_ORIGINAL_ARCHIVE_MEMBERS_NO_SPLIT_FILTER_OR_NEW_ROLE_ASSIGNMENT',
        'source_ID_name_SMILES_physical_ordinal_record_SHA_preserved':True,'all_original_conformers_and_variants_retained':True,
        'name_identity_policy':'UNION_OF_EVERY_ORIGINAL_CONFORMER_AND_VARIANT_NO_REPRESENTATIVE',
        'original_frozen_key_function_objects':True,'RDKit_version':'2025.09.5','sampler_python':'3.11.14',
        'new_pure_fixture_methods':3,'all3_before_source_log_body':True,'worker_processes':16,'maximum_pending_rows':32,
        'worker_native_threads':1,'source_and_result_durable_before_dispatch_and_aggregate':True,
        'parent_and_direct_children_RSS_soft_cap_bytes':16<<30,'minimum_MemAvailable_bytes':4<<30,
        'output_cap_bytes':cap,'drain_reserve_bytes':256<<20,'input_original_ZIP_SDF_or_old_SQLite_reopened':False,
        'new_job_owned_SQLite_index_only':True,'X_filter_SMILES_repair_neutralization_tautomer_or_stereo_isotope_edit':False,
        'native_SDF_graph_stereo_verified_by_this_job':False,'unknown_is_chemical_exclusion':False,
        'assay_values_decoded':False,'new_network_UFF_QM_calls':0,'global_decontamination_pool_training_release':False,
        'cost_overrun_action':'REPORT_AND_CONTINUE'}


def inputs(plan):
    b=M.meta(plan['accepted_probe_receipt_reference']);Q.need(b['schema']=='MARCEL_IDENTITY_FORMAT_PROBE_RECEIPT_V1'
        and b['status']=='SOURCE_FORMAT_OBSERVATION_COMPLETE_IDENTITY_RELEASE_PENDING' and b['mode']=='drugs_identity'
        and str(b['job_id'])=='4521750' and b['uid']==1278 and b['endpoint']=='202.38.247.57:22'
        and b['fixtures']['tests_run']==3 and all(b['fixtures'][k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),
        'ACTUAL_ORIGINAL_DRUGS_PROBE_CLOSURE_WITH3_PURE_PASS')
    o=b['result']['observation'];p=o['exact_byte_pairing'];Q.need(b['result']['all_member_EOF_CRC_SHA_complete'] is True
        and o['physical_row_counts']=={'CSV':CSV_N,'SDF':N} and o['SDF_physical_records']==N
        and p['CSV']=={'rows':CSV_N,'missing_names':0,'empty_names':0,'duplicate_name_groups':0}
        and p['SDF']['rows']==N and p['SDF']['duplicate_name_groups']==71969
        and p['SDF_rows_without_exact_CSV_name']==p['CSV_rows_without_exact_SDF_name']==p['SDF_duplicate_ID_groups']==0
        and p['SDF_name_groups_with_distinct_smiles_bytes']==290,'ACTUAL_FULL_SOURCE_RELATIONSHIP_CONTEXT_NOT_VALID_MOLECULE_CLAIM')
    old=M.meta(b['plan_reference']);proof=M.meta(b['startup_proof_reference']);_,parents,_=M.authority(old)
    Q.need(old['mode']=='drugs_identity' and proof['uid']==1278 and str(proof['job_id'])==str(b['job_id'])
        and proof['request']['node']==b['node'] and proof['request']['scope_key']=='marcel_identity_format_probe_main_v1'
        and proof['request']['scope_parameters']==old['scope_parameters']==M.parameters('drugs_identity')
        and b['plan_reference'] in proof['request']['source_references'],'ACTUAL_PARENT_PLAN_PROOF_BOOTSTRAP_CHAIN')
    for path in [*(M.HERE/n for n in M.FILES),*(Q.REPO/n for n in M.OLD)]:Q.need(Q.pin(path) in proof['request']['source_references'],'EXACT_ORIGINAL_IDENTITY_LOG_PRODUCER_SOURCE')
    matches=[r for r in b['output_references'] if Path(r['path']).name=='source_identity_rows.jsonl']
    Q.need(len(matches)==1 and matches[0]['bytes']==401229188 and matches[0]==plan['input_reference'],'ONE_PRODUCER_PINNED_IDENTITY_LOG_DATA_ONLY')
    _,raw=account(plan['accepted_probe_accounting_reference'],b)
    refs=[*parents,plan['accepted_probe_receipt_reference'],plan['accepted_probe_accounting_reference'],raw,b['plan_reference'],b['startup_proof_reference']]
    if plan['mode']=='full':
        pilot=M.meta(plan['accepted_profile_receipt_reference']);_,pr=account(plan['accepted_profile_accounting_reference'],pilot)
        Q.need(pilot['schema']=='MARCEL_DRUGS_KEYS_RECEIPT_V1' and pilot['mode']=='profile'
            and pilot['status']=='EXACT_SELECTED_CONFORMER_KEYS_OBSERVED_UNKNOWNS_RETAINED'
            and pilot['input_reference']==plan['input_reference'] and pilot['selected_completed_rows']==PILOT_N
            and pilot['input_context']['all_source_rows']==CSV_N+N and pilot['input_context']['source_multi_SMILES_name_groups']==290,
            'ACTUAL_SAME_INPUT10000_PROFILE_NOT_FULL_ACCEPTANCE')
        pp=M.meta(pilot['plan_reference']);ps=M.meta(pilot['startup_proof_reference'])
        Q.need(pp['mode']=='profile' and pp['scope_parameters']==parameters('profile',1<<30)==ps['request']['scope_parameters']
            and str(ps['job_id'])==str(pilot['job_id']) and ps['uid']==1278 and ps['request']['node']==pilot['node']
            and pilot['plan_reference'] in ps['request']['source_references'],'ACTUAL_PROFILE_PLAN_PROOF_SCOPE')
        for path in [*(HERE/n for n in FILES),*OLD]:Q.need(Q.pin(path) in ps['request']['source_references'],'FULL_SAME_FROZEN_PROFILE_SOURCE_BYTES')
        review=M.meta(plan['profile_root_review_reference']);Q.need(review['schema']=='ROOT_DRUGS_IDENTITY_PROFILE_COST_QUALITY_REVIEW_V1'
            and review['status']=='APPROVED_FOR_FULL_IDENTITY_PROJECTION' and review['reviewer']=='root'
            and review['actual_profile_receipt_reference']==plan['accepted_profile_receipt_reference']
            and review['actual_profile_accounting_reference']==plan['accepted_profile_accounting_reference']
            and review['actual_profile_cost_and_unknowns_reviewed'] is True
            and review['all_original_conformers_variants_and_CSV_memberships_authorized'] is True
            and review['candidate_or_pool_release_authorized'] is False
            and review['wall_seconds']==plan['wall_seconds'] and review['output_cap_bytes']==plan['output_cap_bytes'],
            'ACTUAL_ROOT_REVIEW_COST_UNKNOWNS_AND_EXPLICIT_FULL_CAP_WALL')
        projected=(pilot['selected_result_journal_reference']['bytes']*N+PILOT_N-1)//PILOT_N
        Q.need(review['uniform_journal_projection_bytes']==projected
            and review['observed_profile_nonjournal_bytes']==pilot['owned_output_bytes_before_receipt']-pilot['selected_result_journal_reference']['bytes']
            and review['output_budget_is_descriptive_not_worst_case_bound'] is True
            and review['output_cap_bytes']>=projected+review['observed_profile_nonjournal_bytes']+(512<<20),
            'PROFILE_ACTUAL_UNIFORM_BYTES_PLUS_OBSERVED_FIXED_OUTPUT_AND_DRAIN_ADMIN_RESERVE')
        refs.extend([plan['accepted_profile_receipt_reference'],plan['accepted_profile_accounting_reference'],pr,pilot['plan_reference'],pilot['startup_proof_reference'],plan['profile_root_review_reference']])
    return b,unique(refs)
