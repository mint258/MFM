"""Three body aliases, relocated Main evidence, one exact Alpha observation scope."""
import csv,io,re
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
ROOT=Q.ROOT;HERE=ROOT/'code/secondary_tdc_exact2_composition_v1'
FILES=('__init__.py','contracts.py','guard.py','projection.py','run.py','test_v1.py','README.md','stage_schema.json')
KEY='tdc_exact2_composition_evidence_alpha_v1';MODULE='secondary_tdc_exact2_composition_v1.run'
PLAN='SECONDARY_TDC_EXACT2_COMPOSITION_EVIDENCE_PLAN_V1';PROOF='SECONDARY_TDC_EXACT2_COMPOSITION_EVIDENCE_STARTUP_V1'
STAGE='TDC_EXACT2_ORIGINAL_UNKNOWN_SOURCE_ATOMS_ONLY';SCOPE='TWO_ORIGINAL_UNKNOWN_COMPOSITION_EVIDENCE_NOT_POLICY_ACCEPTANCE'
CAP=2<<30;WALL=600;MEMBER='admet_group/solubility_aqsoldb/test.csv';ORDINALS=(1159,1160)
MAIN='/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025';MAIN_ENDPOINT='202.38.247.57:22'
META_KEYS=('diagnosis','diagnosis_plan','diagnosis_proof','diagnosis_accounting','diagnosis_raw',
    'identity','identity_plan','identity_proof','identity_accounting','identity_raw',
    'header','header_plan','header_proof','header_accounting','header_raw')
PARAMS={'sanitize':False,'removeHs':False,'parseName':False,'allowCXSMILES':False,'strictCXSMILES':True,'debugParse':False}
PARAMETERS={'original_Main_diagnosis_job':'4521907','original_Main_identity_job':'4521757','original_Main_header_job':'4521689',
    'original_all44_rows':81809,'original_full_key_rows':81807,'original_UNKNOWN_rows':2,'selected_member':MEMBER,
    'selected_member_physical_rows':1997,'selected_zero_based_ordinals':list(ORDINALS),'body_files':3,'body_bytes':1475427,
    'original_source_event_bytes':1024,'original_result_event_bytes':1902,'official_ZIP_bytes':1472501,
    'RDKit':'2025.09.5','python':'3.11.14','parser_params':PARAMS,'original_string_unchanged':True,
    'whole_string_requires_nonempty_ASCII33_to126':True,'strip_split_replacement_or_alternative_SMILES':False,
    'composition_evidence_basis':'ORIGINAL_SMILES_EXPLICIT_ATOMIC_NUMBERS_ONLY_NEW_SEAM',
    'all_fragments_included_and_only_Z1_excluded_by_frozen_native_composition':True,
    'query_atom_query_bond_dummy_or_incomplete_atom_table':'UNKNOWN_NO_COMPOSITION',
    'additional_sanitize_property_cache_InChI_SMILES_generation_charge_or_stereo_calls':False,
    'internal_parser_processing_absent_claimed':False,'new_full_keys':0,
    'original_state_fullkeys_and_errors_unchanged':True,'original_N4_warnings_row_or_cause_bound':False,
    'graph_charge_stereo_and_original_failure_cause':'UNKNOWN','automatic_fallback_policy_acceptance':False,
    'new_pure_methods':3,'all3_before_DATA_and_resource_monitor':True,'allocated_cpus':16,'parser_processes':1,
    'maximum_original_strings_parsed':2,'writer':'DIRECT_UNCHANGED_CSV6_BUDGET_AND_WRITER',
    'whole_output_cap_bytes':CAP,'wall_seconds':WALL,'current_registered_caps_plus200GB':True,
    'new_network_UFF_QM_calls':0,'global_decontamination_pool_training_release':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}
REVIEW_FIELDS=('scope_key','scope_parameters','stage','endpoint','uid','run_root','node','cpus','memory_policy','kind','pilot',
    'wall_seconds','output_cap_bytes','execution_argv','data_references','parent_evidence_references','scope_mode','performance_profile')


def unique(refs):
    result={}
    for r in refs:Q.normalized(r);Q.need(r['path'] not in result or result[r['path']]==r,'CONFLICTING_METADATA_PIN');result[r['path']]=r
    return [result[k] for k in sorted(result)]


def triple(r,*,main=False):
    Q.need(isinstance(r,dict) and set(r)=={'path','bytes','sha256'} and type(r['bytes']) is int and r['bytes']>0
        and isinstance(r['sha256'],str) and re.fullmatch('[0-9a-f]{64}',r['sha256']),'EXACT_EXISTING_PRODUCER_TRIPLE')
    p=Path(r['path']);Q.need(p.is_absolute() and '..' not in p.parts,'ABSOLUTE_LITERAL_REFERENCE')
    if main:Q.need(Path(MAIN) in p.parents,'ORIGINAL_MAIN_REFERENCE_PRESERVED_NOT_ALPHA')
    else:Q.literal(p)
    return r


def metadata_origin(key,reference):
    r=triple(reference,main=True);p=Path(r['path'])
    fixed={'diagnosis':Path(MAIN)/'artifacts/expansion/tdc_unresolved2_diagnosis_main_v1/diagnosis_summary.json',
        'identity':Path(MAIN)/'artifacts/expansion/tdc_zip44_identity_main_v1/receipt.json',
        'header':Path(MAIN)/'artifacts/expansion/tdc_zip44_header_main_v2/receipt.json'}
    Q.need(key in META_KEYS and r['bytes']<=2<<20,'ONLY_BOUNDED_DECLARED_MAIN_METADATA')
    Q.need(p==fixed[key] if key in fixed else Path(MAIN)/'control' in p.parents,'NO_ARTIFACT_DATA_DISGUISED_AS_SMALL_METADATA')
    return r


def main_account(value,raw,job,node):
    Q.need(value['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and value['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
        and value['endpoint']==MAIN_ENDPOINT and value['uid']==1278 and value['query_returncode']==0
        and value['failed_timeout_startup_cleanup_elapsed_retained'] is True,'ACTUAL_MAIN_ACCOUNT_NOT_ALPHA')
    rows=[r for r in csv.DictReader(io.StringIO(raw.decode('utf-8')),delimiter='|') if '.' not in r['JobIDRaw']]
    Q.need(len(value['parents'])==len(rows)==1,'ONE_EXACT_MAIN_PARENT');p=value['parents'][0];r=rows[0]
    Q.need(p['job_id']==r['JobIDRaw']==job and p['state']==r['State']=='COMPLETED' and p['exit_code']==r['ExitCode']=='0:0'
        and p['node']==r['NodeList']==node and p['alloc_cpus']==int(r['AllocCPUS'])==16 and r['UID']=='1278'
        and p['elapsed_raw_seconds']==int(r['ElapsedRaw']) and value['allocated_core_seconds']==16*int(r['ElapsedRaw']),
        'EXACT_MAIN_RAW_C0_NODE_UID_AND_COST')


def inputs(plan):
    mr=plan['main_relocation_reference'];Q.need(mr in plan['source_references'],'ROOT_RELOCATION_IS_APPROVED_SOURCE');m=Q.load_ref(mr)
    Q.need(m['schema']=='TDC_EXACT2_MAIN_TO_ALPHA_EVIDENCE_RELOCATION_V1' and m['origin_endpoint']==MAIN_ENDPOINT and m['origin_uid']==1278
        and m['target_endpoint']==Q.ENDPOINT and m['target_uid']==1264 and m['scientific_body_SHA_verified_on_login'] is False,
        'EXACT_CROSS_ENDPOINT_PROVENANCE_AND_PENDING_CPU_BODY_VERIFICATION')
    copies=m['metadata_copies'];Q.need(len(copies)==len(META_KEYS) and {v['key'] for v in copies}==set(META_KEYS),'EXACT15_MAIN_SMALL_EVIDENCE_COPIES')
    by={v['key']:v for v in copies};values={}
    for key,v in by.items():
        a=metadata_origin(key,v['origin_reference']);b=triple(v['target_reference']);p=Path(b['path'])
        Q.need((a['bytes'],a['sha256'])==(b['bytes'],b['sha256']) and b in plan['parent_evidence_references']
            and (ROOT/'control' in p.parents or ROOT/'metadata' in p.parents),'ORIGINAL_SMALL_METADATA_COPIES_ONLY_NOT_ALPHA_DATA')
        values[key]=Q.read_small(Q.verify(b)) if key.endswith('_raw') else Q.load_ref(b)
    d=values['diagnosis'];i=values['identity'];h=values['header']
    Q.need(d['schema']=='TDC_EXACT2_ORIGINAL_UNKNOWN_READONLY_DIAGNOSIS_V1' and d['status']=='BOTH_ORIGINAL_UNKNOWN_ROWS_BYTE_BOUND_STATE_UNCHANGED'
        and d['original2_UNKNOWN_unchanged'] is True and d['original_stderr_reference'] is None
        and d['stderr_observations_are_not_row_or_cause_binding'] is True,'ACTUAL1907_ORIGINAL_UNKNOWNS_NO_WARNING_CAUSE_ATTRIBUTION')
    Q.need(d['journal']['source_rows']==d['journal']['result_rows']==81809 and d['journal']['identity_state_counts']=={'FULL_KEYS_DERIVED':81807,'ORIGINAL_SMILES_UNRESOLVED':2}
        and d['ZIP']['current_whole_SHA_stable_fstat'] is True and d['ZIP']['regular_members']==45
        and len(d['ZIP']['member_counts'])==44 and sum(d['ZIP']['member_counts'].values())==81809
        and d['ZIP']['member_counts'][MEMBER]==1997 and d['ZIP']['selected_rows_bound']==2,'ACTUAL_ALL44_ROWS_AND_TWO_BOUND_UNKNOWNS')
    Q.need(i['schema']=='TDC_ZIP44_IDENTITY_RECEIPT_V1' and i['status']=='ALL81809_ORIGINAL_ROWS_IDENTITY_KEYS_OBSERVED_UNKNOWNS_RETAINED'
        and i['result']['physical_rows_dispatched']==i['result']['physical_rows_with_durable_results']==81809
        and i['result']['identity_state_counts']==d['journal']['identity_state_counts'],'ACTUAL1757_FULL_PHYSICAL_SCOPE_RETAINED')
    Q.need(h['schema']=='TDC_ZIP44_HEADER_PROBE_RECEIPT_V1' and h['status']=='ALL44_HEADER_STRUCTURE_METADATA_CLOSED_IDENTITY_MAPPING_PENDING'
        and h['result']['all68_inventory_entries_matched'] is True and h['result']['all_regular_member_EOF_CRC_passed'] is True
        and h['result']['all44_CSV_metadata_complete'] is True and len(h['result']['members'])==68,'ACTUAL1689_ORIGINAL_ZIP_HEADER_AND_CRC_PARENT')
    specs=(('diagnosis','4521907','tdc_unresolved2_readonly_diagnosis_main_v1',4),('identity','4521757','tdc_zip44_identity_main_v1',3),
        ('header','4521689','tdc_zip44_header_only_main_v2',3))
    for key,job,scope,tests in specs:
        v=values[key];p=values[key+'_plan'];s=values[key+'_proof'];fx=v['fixtures']
        Q.need(str(v['job_id'])==str(s['job_id'])==job and v['endpoint']==MAIN_ENDPOINT and v['uid']==s['uid']==1278
            and s['request']['node']==v['node'] and s['request']['scope_key']==scope
            and s['request']['scope_parameters']==p['scope_parameters'] and v['plan_reference']==by[key+'_plan']['origin_reference']
            and v['startup_proof_reference']==by[key+'_proof']['origin_reference']
            and by[key+'_plan']['origin_reference'] in s['request']['source_references'],'PRESERVED_ACTUAL_MAIN_PLAN_PROOF_SCOPE:'+key)
        Q.need(fx['tests_run']==tests and all(fx[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'ACTUAL_PARENT_PURE_FIXTURES:'+key)
        account=values[key+'_accounting'];Q.need(account['raw_sacct_reference']==by[key+'_raw']['origin_reference'],'ORIGINAL_RAW_ACCOUNTING_ALIAS')
        main_account(account,values[key+'_raw'],job,v['node'])
    Q.need(d['accepted_identity_receipt_reference']==by['identity']['origin_reference'] and d['accepted_identity_accounting_reference']==by['identity_accounting']['origin_reference']
        and values['diagnosis_plan']['accepted_identity_receipt_reference']==by['identity']['origin_reference']
        and values['identity_plan']['accepted_header_receipt_reference']==by['header']['origin_reference']
        and values['identity_plan']['accepted_header_accounting_reference']==by['header_accounting']['origin_reference'],'EXACT1907_TO1757_TO1689_PARENT_CHAIN')
    aliases=m['data_aliases'];Q.need(len(aliases)==3 and [v['key'] for v in aliases]==['source_events','result_events','archive'],'ONLY_THREE_SCIENTIFIC_BODY_ALIASES')
    original=[*d['selected_original_event_DATA_references'],i['input_reference']]
    Q.need(i['input_reference']==h['input_reference']==values['diagnosis_plan']['data_references'][1],'SAME_ORIGINAL_COMPLETE_OFFICIAL_ZIP')
    for v,a,n in zip(aliases,original,(1024,1902,1472501)):
        b=triple(v['target_reference']);Q.need(triple(v['origin_reference'],main=True)==a and a['bytes']==n
            and (a['bytes'],a['sha256'])==(b['bytes'],b['sha256'])
            and (ROOT/'artifacts' in Path(b['path']).parents or ROOT/'inputs' in Path(b['path']).parents),'EXACT_EXISTING_PRODUCER_BODY_ALIAS')
        Q.need(v['target_current_SHA_verification']=='PENDING_THIS_JOB_CPU_AFTER_FIXTURES','NO_FUTURE_OR_LOGIN_SCIENTIFIC_SHA')
    data=[v['target_reference'] for v in aliases];Q.need(plan['data_references']==data and len({v['path'] for v in data})==3,'EXACT_THREE_BODY_LOCATORS')
    Q.need(sum(v['bytes'] for v in data)==PARAMETERS['body_bytes'],'BODY_BYTES_CONSERVED')
    Q.need([(v['member_name'],v['physical_record_ordinal']) for v in d['exact2_bindings']]==[(MEMBER,n) for n in ORDINALS],
        'EXACT_TWO_ORIGINAL_ZERO_BASED_POSITIONS')
    for k in ('projection','formats'):
        alias=plan['frozen_csv_source_references'][k];a=triple(alias['origin_reference'],main=True);b=triple(alias['target_reference'])
        Q.need(a in values['identity_proof']['request']['source_references'] and (a['bytes'],a['sha256'])==(b['bytes'],b['sha256'])
            and b in plan['source_references'],'BYTE_IDENTICAL_ORIGINAL_CSV_CALLBACK_AND_GRAMMAR')
    return d,values,by,m
