"""Exact actual44-header authority and bounded Main identity-only stage."""
import csv,io
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q
from workflows.expansion.tdc_zip44_header_probe_v2 import contract as H
HERE=Q.REPO/'workflows/expansion/tdc_zip44_identity_main_v1'
FILES=('__init__.py','contract.py','projection.py','kernel.py','run.py','test_v1.py','materialize.py','README.md')
KEY='tdc_zip44_identity_main_v1';MODULE='workflows.expansion.tdc_zip44_identity_main_v1.run'
STAGE='TDC_ALL22_ENDPOINTS_ALL44_ORIGINAL_SPLITS_IDENTITY_KEYS'
CAP=512<<20
FROZEN={'workflows/expansion/common.py':(4312,'8c988f617776ad05354deae1cf69933e7ff95210f7a2609f903e4826172ccbad'),
    'workflows/expansion/identity_v2/projection_v2.py':(8616,'7da54ccb4488950fb567c17cfa161bc339d8a377f2e2fb27362434ce88516d28'),
    'workflows/expansion/identity_v2/readers_v2.py':(8506,'44e24faa045758b889d2dba671c25bbdb24b949e5a48fdf6710f0fc281d497d4')}
OLD=('workflows/expansion/__init__.py','workflows/expansion/identity_v2/__init__.py',*FROZEN,
    'workflows/expansion/tdc_zip44_header_probe_v2/__init__.py','workflows/expansion/tdc_zip44_header_probe_v2/contract.py',
    'workflows/expansion/tdc_zip44_header_probe_v2/projection.py','workflows/expansion/secondary_missing11_identity_format_probe_v1/__init__.py',
    'workflows/expansion/secondary_missing11_identity_format_probe_v1/formats.py',
    'workflows/expansion/marcel_archive_bootstrap_v1/__init__.py','workflows/expansion/marcel_archive_bootstrap_v1/archive.py')
PARAMETERS={'official_dataverse_file_id':'4426004','archive_bytes':1472501,'ZIP_entries':68,'regular_members':45,
    'CSV_members':44,'endpoint_directories':22,'physical_CSV_records':81809,'CSV_decoded_bytes':5428641,
    'all_regular_decoded_bytes':5434789,'literal_header':['Drug_ID','Drug','Y'],'selected_columns':['Drug_ID','Drug'],
    'original_native_ID_bytes_and_zeros_preserved':True,'original_train_val_and_test_members_preserved':True,
    'new_split_generation_or_deduplication':False,'all_blank_invalid_duplicate_or_zero_ID_rows_retained':True,
    'original_frozen_key_function_objects':True,'RDKit_version':'2025.09.5','X_or_feature_filter_or_neutralization_tautomer_isotope_stereo_edit':False,
    'worker_processes':16,'maximum_pending_worker_rows':32,'worker_native_threads':1,
    'parent_and_direct_children_RSS_soft_cap_bytes':16<<30,'minimum_MemAvailable_bytes':4<<30,
    'drain_output_reserve_bytes':256<<20,'new_pure_fixture_methods':3,
    'all3_fixtures_before_archive_body':True,'source_and_result_rows_durable_before_aggregate':True,
    'assay_Y_text_or_numeric_decoded':False,'unknown_is_chemical_exclusion':False,'new_network_UFF_QM_calls':0,
    'parent1884799_failed3_and4521650_failed1_costs_retained':True,'identity_inventory_only':True,
    'global_decontamination_pool_training_or_release':False,'cost_overrun_action':'REPORT_AND_CONTINUE'}


def meta(r):
    Q.need(set(r)=={'path','bytes','sha256'} and r['bytes']<=2<<20 and Q.pin(r['path'])==r,'ACTUAL_SMALL_METADATA_PIN')
    return Q.load(r['path'])


def inputs(plan):
    b=meta(plan['accepted_header_receipt_reference']);a=meta(plan['accepted_header_accounting_reference'])
    Q.need(b['schema']=='TDC_ZIP44_HEADER_PROBE_RECEIPT_V1' and b['status']=='ALL44_HEADER_STRUCTURE_METADATA_CLOSED_IDENTITY_MAPPING_PENDING'
        and str(b['job_id'])=='4521689' and b['uid']==1278 and b['endpoint']=='202.38.247.57:22'
        and b['fixtures']['tests_run']==3 and all(b['fixtures'][k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes'))
        and b['input_current_full_SHA_fstat_verified'] is True,'ACTUAL_4521689_COMPLETE_HEADER_PARENT')
    result=b['result'];Q.need(result['all68_inventory_entries_matched'] is result['all_regular_member_EOF_CRC_passed'] is result['all44_CSV_metadata_complete'] is True
        and not result['failures'] and len(result['reports'])==44 and len(result['members'])==68
        and sum(r['type']=='DIRECTORY' for r in result['members'])==23
        and sum(r['type']=='CSV' for r in result['members'])==44
        and sum(r['type']=='OTHER_REGULAR_NO_IDENTITY' for r in result['members'])==1,'ALL44_REAL_HEADER_AND_ALL_REGULAR_CRC_EVIDENCE')
    bp=meta(b['startup_proof_reference']);old=meta(b['plan_reference'])
    Q.need(bp['uid']==1278 and str(bp['job_id'])==str(b['job_id']) and bp['request']['node']==b['node']
        and bp['request']['scope_key']=='tdc_zip44_header_only_main_v2' and b['plan_reference'] in bp['request']['source_references']
        and old['scope_parameters']==b['scope_parameters']==bp['request']['scope_parameters'],'ACTUAL_HEADER_PLAN_PROOF_BINDING')
    obs,data,entries=H.inputs(old['observation_reference'],old['relocation_reference']);Q.need(data==b['input_reference']==plan['archive_reference']
        and Q.pin(H.OLD/'formats.py')==old['original_formats_reference'],'PRODUCER_PINNED_MAIN_COPY_AND_ORIGINAL_CSV_GRAMMAR_BYTES')
    raw=a['raw_sacct_reference'];Q.need(Q.pin(raw['path'])==raw,'ACTUAL_PARENT_RAW_ACCOUNTING')
    rows=list(csv.DictReader(io.StringIO(Q.read_small(raw['path']).decode('utf-8')),delimiter='|'));parents=[r for r in rows if '.' not in r['JobIDRaw']]
    Q.need(a['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and a['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
        and a['endpoint']=='202.38.247.57:22' and a['uid']==1278 and a['query_returncode']==0
        and len(a['parents'])==len(parents)==1 and a['failed_timeout_startup_cleanup_elapsed_retained'] is True,'ONE_EXACT_REAL_HEADER_PARENT_ACCOUNTING')
    p=a['parents'][0];r=parents[0];Q.need(p['job_id']==r['JobIDRaw']==str(b['job_id']) and p['state']==r['State']=='COMPLETED'
        and p['exit_code']==r['ExitCode']=='0:0' and p['alloc_cpus']==int(r['AllocCPUS'])==16
        and p['elapsed_raw_seconds']==int(r['ElapsedRaw']) and p['node']==r['NodeList']==b['node'] and r['UID']=='1278'
        and a['allocated_core_seconds']==p['elapsed_raw_seconds']*16,'RAW_SUMMARY_C0_AND_ACTUAL_FULL_COST')
    refs=[plan['accepted_header_receipt_reference'],plan['accepted_header_accounting_reference'],raw,b['plan_reference'],b['startup_proof_reference'],
          old['observation_reference'],old['relocation_reference'],old['parent_get_accounting_reference'],old['parent_raw_sacct_copy_reference']]
    headers={};total=0
    for report in result['reports']:
        h=meta(report['report_reference']);name=h['member_name'];parts=Path(name).parts
        Q.need(h['schema']=='TDC_CSV_HEADER_STRUCTURE_METADATA_V1' and h['status']=='HEADER_AND_CSV_STRUCTURE_OBSERVED'
            and h['CSV']['literal_header']==['Drug_ID','Drug','Y'] and h['CSV']['CSV_EOF_complete'] is True
            and not h['parser_error'] and not h['archive_error'] and h['member_EOF_CRC_passed'] is True
            and name==report['member_name'] and len(parts)==3 and parts[0]=='admet_group' and parts[2] in ('train_val.csv','test.csv')
            and name not in headers,'EXACT_REAL_THREE_COLUMN_HEADER_PER_ORIGINAL_MEMBER')
        n=h['CSV']['record_counts'];Q.need(n['physical_data_records']==n['field_count_matches_header']
            and n['field_count_below_header']==n['field_count_above_header']==0,'COMPLETE_ACTUAL_PHYSICAL_WIDTH_COUNTS')
        total+=n['physical_data_records'];headers[name]=h;refs.append(report['report_reference'])
    groups={Path(n).parts[1] for n in headers};Q.need(total==81809 and len(groups)==22
        and all({Path(n).name for n in headers if Path(n).parts[1]==g}=={'train_val.csv','test.csv'} for g in groups),'ALL22_ENDPOINTS_BOTH_ORIGINAL_SPLITS_81809_ROWS')
    return b,data,entries,headers,refs
