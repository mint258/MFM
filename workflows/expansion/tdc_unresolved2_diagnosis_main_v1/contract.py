"""Main CPU metadata authority; no body hashing during login materialization."""
from pathlib import Path
from workflows.expansion.tdc_zip44_identity_main_v1 import contract as T
from workflows.expansion.marcel_drugs_keys_main_v1 import contract as D
Q=T.Q;HERE=Q.REPO/'workflows/expansion/tdc_unresolved2_diagnosis_main_v1'
FILES=('__init__.py','contract.py','projection.py','run.py','test_v1.py','materialize.py','README.md')
KEY='tdc_unresolved2_readonly_diagnosis_main_v1';MODULE='workflows.expansion.tdc_unresolved2_diagnosis_main_v1.run'
STAGE='TDC_EXACT_TWO_ORIGINAL_UNKNOWN_ROWS_READONLY_BINDING';CAP=128<<20;LINE_CAP=8<<20
OLD=tuple(T.HERE/n for n in T.FILES)+tuple(Q.REPO/n for n in T.OLD)+tuple(D.HERE/n for n in D.FILES)+D.OLD
PARAMETERS={'producer_job_id':'4521757','original_rows':81809,'original_result_states':{'FULL_KEYS_DERIVED':81807,'ORIGINAL_SMILES_UNRESOLVED':2},
    'selected_unresolved_original_rows':2,'input_journal_bytes':114667955,'input_ZIP_bytes':1472501,
    'source_result_pairs_and_all44_member_counts_conserved':True,'ZIP_original_grammar_and_all_member_EOF_CRC_SHA':True,
    'selected_columns':['Drug_ID','Drug'],'assay_Y_text_or_numeric_decoded':False,'input_line_bound_bytes':LINE_CAP,
    'new_pure_fixture_methods':4,'all4_before_any_scientific_body':True,'new_identity_key_computations':0,
    'key_rule_or_original_error_modification':False,'graph_repair_or_alternative_SMILES':False,'native_IDs_and_original_variants_retained':True,
    'sequential_input_streams':1,'allocated_cpus':16,'output_cap_bytes':CAP,'frozen_drugs_Budget_Writer_dispatch_argument':False,
    'explicit_original_stop_new_checked_before_each_input_chunk':True,'runtime_statvfs_is_not_fresh_account_quota':True,
    'new_network_UFF_QM_calls':0,'production_once_ledger_opened':False,'all2_unknowns_remain_original_unknowns':True,
    'global_decontamination_pool_training_release':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}


def unique(refs):return D.unique(refs)


def inputs(plan):
    b=T.meta(plan['accepted_identity_receipt_reference']);account,raw=D.account(plan['accepted_identity_accounting_reference'],b)
    Q.need(b['schema']=='TDC_ZIP44_IDENTITY_RECEIPT_V1' and b['status']=='ALL81809_ORIGINAL_ROWS_IDENTITY_KEYS_OBSERVED_UNKNOWNS_RETAINED'
        and b['job_id']=='4521757' and b['uid']==1278 and b['endpoint']=='202.38.247.57:22'
        and b['fixtures']['tests_run']==3 and all(b['fixtures'][k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),
        'ACTUAL1757_ALL81809_PARENT_WITH3_PASS_AND_REAL_C0_RAW')
    result=b['result'];Q.need(result['physical_rows_dispatched']==result['physical_rows_with_durable_results']==81809
        and result['identity_state_counts']==PARAMETERS['original_result_states'] and len(result['member_result_counts'])==44
        and result['unknowns_dropped_or_reclassified_as_chemical_exclusions'] is False,'EXACT_TWO_REAL_UNRESOLVED_NOT_SYNTHETIC_FIXTURE')
    old=T.meta(b['plan_reference']);proof=T.meta(b['startup_proof_reference'])
    Q.need(proof['job_id']=='4521757' and proof['uid']==1278 and proof['request']['node']==b['node']
        and proof['request']['scope_key']==T.KEY and proof['request']['scope_parameters']==old['scope_parameters']==T.PARAMETERS
        and b['plan_reference'] in proof['request']['source_references'],'ACTUAL_ORIGINAL_PARENT_PROOF_PLAN_SOURCE_SCOPE')
    for path in [*(T.HERE/n for n in T.FILES),*(Q.REPO/n for n in T.OLD)]:Q.need(Q.pin(path) in proof['request']['source_references'],'FROZEN_ORIGINAL_SOURCE_PIN')
    headers,archive,entries,by_member,parents=T.inputs(old)
    journal=result['journal_reference'];Q.need(journal['bytes']==114667955 and archive['bytes']==1472501
        and archive==b['input_reference'] and plan['data_references']==[journal,archive]
        and result['member_result_counts']=={n:r['CSV']['record_counts']['physical_data_records'] for n,r in by_member.items()},'ONLY_REAL_JOURNAL_AND_ZIP_DATA_REFS')
    for r in (journal,archive):
        p=Path(r['path']);Q.need(set(r)=={'path','bytes','sha256'} and p.is_absolute() and Q.ROOT/'artifacts' in p.parents
            and '..' not in p.parts and type(r['bytes']) is int and r['bytes']>0 and len(r['sha256'])==64,'EXACT_DECLARED_DATA_LOCATOR_NOT_LOGIN_READ')
    refs=unique([*parents,plan['accepted_identity_receipt_reference'],plan['accepted_identity_accounting_reference'],raw,b['plan_reference'],b['startup_proof_reference']])
    if plan.get('original_stderr_reference'):
        r=plan['original_stderr_reference'];Q.need(Q.ROOT/'control' in Path(r['path']).parents and r['bytes']<=2<<20 and Q.pin(r['path'])==r,'OPTIONAL_ACTUAL_SMALL_ORIGINAL_STDERR')
        refs=unique([*refs,r])
    return b,entries,by_member,refs
