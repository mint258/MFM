"""Actual39633 SDF population, five closed inputs, old3195 results never retried."""
import hashlib,json,re
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from secondary_moleculenet_csv6_identity_v1.guard import account
ROOT=Q.ROOT;HERE=ROOT/'code/secondary_moleculenet_native4_full_v1'
FILES=('__init__.py','contracts.py','guard.py','full.py','run.py','test_v1.py','README.md')
OLD=ROOT/'code/secondary_moleculenet_native4_identity_v1'
OLD_FILES=('__init__.py','contracts.py','guard.py','native.py','run.py','test_v1.py','README.md','authority792.json')
KEY='moleculenet_native4_closed_source_full_inventory_alpha_v1';MODULE='secondary_moleculenet_native4_full_v1.run'
PLAN='SECONDARY_MOLECULENET_NATIVE4_CLOSED_SOURCE_FULL_PLAN_V1';PROOF='SECONDARY_MOLECULENET_NATIVE4_CLOSED_SOURCE_FULL_STARTUP_V1'
STAGE='ALL39633_PHYSICAL_SDF_KEYS_OLD3195_REUSED_MOL2_CONTEXT_UNKNOWN_RETAINED';SCOPE='FULL_PHYSICAL_INVENTORY_NOT_GRAPH_OR_POOL_ACCEPTANCE'
IDS=('qm8_sdf','pdbbind_core','pdbbind_general','pdbbind_refined')
SDF={'qm8_sdf':21786,'pdbbind_core':195,'pdbbind_general':12800,'pdbbind_refined':4852}
REUSED={'qm8_sdf':1000,'pdbbind_core':195,'pdbbind_general':1000,'pdbbind_refined':1000}
NEW={s:SDF[s]-REUSED[s] for s in IDS};N=39633;OLD_N=3195;MAX_NEW=36438
CAP=4<<30;ADMIN=8<<20;SCIENCE_CAP=CAP-ADMIN;WALL=14400;LINE_CAP=16<<20
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
    'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')


def unique(refs):
    values={}
    for r in refs:Q.normalized(r);Q.need(r['path'] not in values or values[r['path']]==r,'CONFLICTING_SOURCE_PIN');values[r['path']]=r
    return [values[k] for k in sorted(values)]


def data_locator(ref):
    # Pure locator validation only: DATA has no small-metadata size ceiling.
    Q.need(isinstance(ref,dict) and set(ref)=={'path','bytes','sha256'} and isinstance(ref['path'],str)
        and type(ref['bytes']) is int and ref['bytes']>0 and isinstance(ref['sha256'],str)
        and re.fullmatch('[0-9a-f]{64}',ref['sha256']),'EXACT_POSITIVE_PRODUCER_DATA_TRIPLE')
    Q.need(ROOT/'artifacts' in Q.literal(ref['path']).parents,'ONLY_LITERAL_ALPHA_ARTIFACT_DATA_LOCATOR')
    return ref


def small(ref,receipt=False):
    Q.normalized(ref);p=Q.literal(ref['path'])
    Q.need(0<ref['bytes']<=2<<20 and (p==ROOT/'artifacts/moleculenet_native4_identity_profile_v1/v1/receipt.json' if receipt else ROOT/'control' in p.parents),
        'ONLY_FIXED_PROFILE_RECEIPT_OR_SMALL_CONTROL_PARENT_NOT_DATA');return ref


def census(receipt):
    p={v['source_id']:v for v in receipt['projection']};rel={v['source_id']:v for v in receipt['relationship_checks']}
    Q.need(set(p)==set(rel)==set(IDS),'ALL_FOUR_ORIGINAL_SOURCES')
    result={}
    for sid in IDS:
        v=p[sid];r=rel[sid];counts=v['native_record_counts']
        Q.need(counts.get('SDF',0)==SDF[sid] and v['complete_gzip_EOF_CRC'] is True and set(counts)<=set(('SDF','MOL2')),'EXACT_ACTUAL_FULL_SOURCE_CENSUS')
        result[sid]={'SDF':counts['SDF'],'MOL2':counts.get('MOL2',0),'IDs':r['physical_index_rows']}
        Q.need(all(type(n) is int and n>=0 for n in result[sid].values()) and r['physical_SDF_records']==result[sid]['SDF']
            and r['physical_MOL2_records']==result[sid]['MOL2'],'PHYSICAL_COUNTS_NOT_ENTITY_DEDUPLICATION')
    return result


def parameters(c):
    Q.need(set(c)==set(IDS) and all(c[s]['SDF']==SDF[s] for s in IDS),'EXACT39633_PHYSICAL_SDF')
    return {'mode':'full','source_census':c,'physical_SDF_records':N,'old_results_reused':OLD_N,'old_selected_by_source':REUSED,
        'new_key_work_calls_max':MAX_NEW,'new_calls_by_source':NEW,'entity_count_is_physical_SDF_count':False,
        'old_success_UNKNOWN_or_technical_result_retried':False,'population_selection_seed':20261026,'sampler_python':'3.11.14',
        'new_sampling_or_deduplication':False,'RDKit':'2025.09.5','original_key_work_initialize_and_frozen_kernels_direct_objects':True,
        'kwargs':{'qm8_sdf':{'sanitize':True,'removeHs':False,'strictParsing':False},'PDB':{'sanitize':True,'removeHs':False,'strictParsing':True}},
        'all_native_IDs_confs_present_variants_and_cross_component_union_retained':True,'MOL2_graph_charge_stereo':'UNKNOWN_COMPOSITION_CONTEXT_ONLY',
        'old_source_graph_or_EOF_flag_repaired':False,'new_network_UFF_QM_calls':0,'workers_max':16,'pending_max':32,
        'new_pure_methods':3,'all3_before_DATA_and_Budget':True,'five_producer_pinned_inputs_whole_SHA_stable_FD':True,
        'source_result_claims_durable_before_worker_or_aggregation':True,'once_protocol':'NATIVE4_CLOSED_SOURCE_FULL_INVENTORY_ONCE_V1',
        'claim_without_result_or_prior_full_attempt':'HOLD_NO_AUTOMATIC_RETRY','scientific_result_journal_authoritative':True,
        'CSV6_Parquet_full_keys_semantics':'ONLY_SOURCE_SMILES_KEYS_NATIVE_UNION_IN_NATIVE_RESULT_INDEX_AND_UNION_OUTPUT',
        'whole_output_cap_bytes':CAP,'control_admin_cap_within_whole_bytes':ADMIN,'algorithm_science_output_cap_bytes':SCIENCE_CAP,
        'wall_seconds':WALL,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','old677_seconds_is_entire_parent_not_pure_key_or_worst_bound':True,
        'automatic_policy_graph_full_pool_decontamination_release':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}


def body_refs(r):return [r['raw_native_blob_reference'],r['source_rows_reference'],r['native_relationship_index_reference'],
    r['profile']['key_result_journal_reference'],r['profile']['actual_population_and_selection_reference']]


def inputs(plan):
    rr=small(plan['native_profile_receipt_reference'],True);ar=small(plan['native_profile_accounting_reference']);ps=plan['parent_evidence_references']
    Q.need(rr in ps and ar in ps,'EXACT_PROFILE_AND_ACCOUNT_PARENTS');r=Q.load_ref(rr)
    Q.need(r['schema']=='SECONDARY_MOLECULENET_NATIVE4_IDENTITY_PROFILE_RECEIPT_V1' and r['status']=='ALL_PHYSICAL_NATIVE_CONTEXT_AND_BOUNDED_KEYS_RECORDED_UNKNOWNS_RETAINED'
        and r['job_id']=='1884856' and r['endpoint']==Q.ENDPOINT and r['uid']==1264 and r['node']=='compute-0-6'
        and r['full_or_pool_or_decontamination_release'] is False and r['profile']['actual_profile_counts']==REUSED,'ACTUAL_CLOSED856_NOT_PROFILE_ACCEPTANCE')
    for ref in (r['plan_reference'],r['startup_proof_reference']):small(ref);Q.need(ref in ps,'REAL856_PLAN_PROOF')
    op=Q.load_ref(r['plan_reference']);proof=Q.load_ref(r['startup_proof_reference'])
    Q.need(proof['endpoint']==Q.ENDPOINT and proof['uid']==1264 and str(proof['job_id'])=='1884856' and proof['node']==r['node']
        and proof['plan_reference']==r['plan_reference'] and proof['scope_key']==op['scope_key']==r['scope_key']
        and op['scope_parameters']==r['scope_parameters'],'EXACT856_SOURCE_SCOPE_PROOF')
    declared={v['path']:{k:v[k] for k in ('path','bytes','sha256')} for v in proof['source_target_verification']}
    for name in OLD_FILES:
        ref=Q.ref(OLD/name);Q.need(ref in op['source_references'] and ref in plan['source_references'] and declared.get(ref['path'])==ref,'UNCHANGED_ORIGINAL_NATIVE8_BYTES')
    a=Q.load_ref(ar);small(a['raw_sacct_reference']);account(ar,'1884856',ps)
    Q.need(a['actual_parent']['ElapsedRaw']=='677' and a['allocated_core_seconds_observed']==10832,'ORIGINAL677_PARENT_COST_RETAINED_NOT_PURE_PHASE')
    audit_ref=plan['accepted_audit_receipt_reference'];Q.normalized(audit_ref)
    Q.need(audit_ref in ps and 0<audit_ref['bytes']<=2<<20 and ROOT/'artifacts' in Q.literal(audit_ref['path']).parents
        and Path(audit_ref['path']).name=='receipt.json','ONLY_ACTUAL858_SMALL_RECEIPT_NOT_A_DATA_ALIAS')
    audit=Q.load_ref(audit_ref);aa=small(plan['accepted_audit_accounting_reference']);Q.need(aa in ps,'ACTUAL858_ACCOUNT')
    Q.need(audit['schema']=='SECONDARY_NATIVE4_KEY_JOURNAL_AUDIT_RECEIPT_V1' and audit['status']=='CLOSED_JOURNAL_AUDIT_COMPLETE_NOT_PROFILE_ACCEPTANCE'
        and audit['job_id']=='1884858' and audit['uid']==1264 and audit['endpoint']==Q.ENDPOINT
        and audit['native_profile_receipt_reference']==rr and audit['input_integrity']['source_rows']==3195
        and audit['input_integrity']['result_rows']==3195,'ACTUAL858_CLOSED3195_0PARSE_AUDIT')
    Q.need(audit['fixtures']['tests_run']==3 and all(audit['fixtures'][k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes'))
        and audit['new_SDF_MOL2_parse_fullkey_UFF_QM_calls']==0,'ACTUAL858_THREE_PURE_AND_ZERO_NEW_PARSE')
    audit_account=Q.load_ref(aa);small(audit_account['raw_sacct_reference']);account(aa,'1884858',ps)
    for ref in (audit['plan_reference'],audit['startup_proof_reference']):small(ref);Q.need(ref in ps,'REAL858_PLAN_PROOF')
    data=body_refs(r);Q.need(len({v['path'] for v in data})==5 and data==plan['data_references'],'FIVE_ORIGINAL_CLOSED_BODY_LOCATORS_ONLY')
    for ref in data:data_locator(ref)
    Q.need(sum(ref['bytes'] for ref in data)==504179407,'EXACT_FIVE_CLOSED_PRODUCER_BODY_BYTES')
    c=census(r);Q.need(plan['source_census']==c and plan['scope_parameters']==parameters(c),'ACTUAL39633_AND_MOL2_ID_CENSUS_FROZEN')
    Q.need(plan['frozen_identity_source_references']==op['frozen_identity_source_references'],'SAME_FROZEN_IDENTITY_FUNCTION_SOURCES')
    Q.need(plan['population_once_path']==str(ROOT/'control/native4_full_once_v1'/('population_'+fingerprint(plan)+'.json')),'EXACT_ONCE_PATH_CANNOT_RESET_BY_WRAPPER')
    return r,c,op


def fingerprint(plan):
    # Only science authority and source inputs: changing a wrapper cannot reset once.
    value={'protocol':'NATIVE4_CLOSED_SOURCE_FULL_INVENTORY_ONCE_V1','inputs':plan['data_references'],'census':plan['source_census'],
        'native_worker_reference':Q.ref(OLD/'native.py'),'frozen_identity_sources':plan['frozen_identity_source_references']}
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
