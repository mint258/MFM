"""Exact two-mode Main CPU contract; original successful bootstrap is a prerequisite."""
import csv,io
from pathlib import Path
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared as Q
HERE=Q.REPO/'workflows/expansion/marcel_identity_format_probe_v1'
FILES=('__init__.py','contract.py','projection.py','opcodes.py','run.py','test_v1.py','materialize.py','README.md')
MODULE='workflows.expansion.marcel_identity_format_probe_v1.run'
KEY='marcel_identity_format_probe_main_v1'
STAGE='MARCEL_EXISTING_ARCHIVE_SOURCE_IDENTITY_OR_NONEXECUTING_OPCODE_OBSERVATION'
MODES={'drugs_identity':('marcel_drugs_zip',('Drugs.csv','Drugs.sdf'),2<<30),
       'kraken_opcodes':('marcel_kraken_zip',('Kraken.pickle',),64<<20)}
OLD=('workflows/expansion/__init__.py','workflows/expansion/marcel_archive_bootstrap_v1/__init__.py',
     'workflows/expansion/marcel_archive_bootstrap_v1/archive.py',
     'workflows/expansion/secondary_missing11_identity_format_probe_v1/__init__.py',
     'workflows/expansion/secondary_missing11_identity_format_probe_v1/formats.py')


def meta(r):
    Q.need(set(r)=={'path','bytes','sha256'} and r['bytes']<=2<<20 and Q.pin(r['path'])==r,'ACTUAL_SMALL_REFERENCE')
    return Q.load(r['path'])


def authority(plan):
    mode=plan['mode'];Q.need(mode in MODES,'ONLY_TWO_EXACT_MODES');sid,names,cap=MODES[mode]
    b=meta(plan['accepted_bootstrap_receipt_reference']);a=meta(plan['accepted_bootstrap_accounting_reference'])
    Q.need(b['schema']=='MARCEL_OFFICIAL_ARCHIVE_BOOTSTRAP_RECEIPT_V1'
        and b['status']=='FIRST_SHA_ALL_MEMBER_CRC_INVENTORY_COMPLETE_IDENTITY_PENDING' and b['source_id']==sid
        and b['uid']==1278 and b['endpoint']=='202.38.247.57:22' and b['fixtures']['tests_run']==3
        and all(b['fixtures'][k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),
        'ACTUAL_ORIGINAL_BOOTSTRAP_WITH_THREE_PURE_PASS')
    z=b['result'];Q.need(z['all_member_EOF_CRC_SHA_complete'] is z['expected_names_unique'] is True
        and z['expected_author_member_basename_occurrences']=={n:1 for n in names},'ACTUAL_COMPLETE_ORIGINAL_MEMBER_NAMES')
    Q.need(plan['archive_reference']==z['first_actual_archive_reference'] and plan['inventory_reference']==z['inventory_reference'],
        'EXACT_BOOTSTRAP_ARCHIVE_AND_INVENTORY_PRODUCER_PINS')
    original=meta(b['plan_reference']);bp=meta(b['startup_proof_reference'])
    Q.need(original['schema']=='MARCEL_OFFICIAL_ARCHIVE_BOOTSTRAP_PLAN_V1'
        and original['transport_receipt_reference']==b['transport_receipt_reference']
        and original['scope_parameters']==b['scope_parameters']
        and bp['request']['scope_key']=='marcel_official_archive_bootstrap_main_v1'
        and bp['request']['scope_parameters']==b['scope_parameters'] and b['plan_reference'] in bp['request']['source_references']
        and str(bp['job_id'])==str(b['job_id']) and bp['uid']==1278 and bp['request']['node']==b['node'],
        'ACTUAL_BOOTSTRAP_PLAN_PROOF_SCOPE_AND_IDENTITY')
    Q.need(a['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and a['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
        and a['endpoint']=='202.38.247.57:22' and a['uid']==1278 and a['query_returncode']==0
        and a['failed_timeout_startup_cleanup_elapsed_retained'] is True,'ACTUAL_PARENT_ACCOUNTING')
    raw=a['raw_sacct_reference'];Q.need(Q.pin(raw['path'])==raw,'ACTUAL_RAW_PARENT_ACCOUNTING_PIN')
    text=Q.read_small(raw['path']).decode('utf-8');rows=list(csv.DictReader(io.StringIO(text),delimiter='|'))
    physical={r['JobIDRaw']:r for r in rows if '.' not in r['JobIDRaw']}
    Q.need(len(physical)==len(a['parents']) and len({p['job_id'] for p in a['parents']})==len(a['parents']),'EXACT_ALL_ACCOUNTING_PARENTS')
    total=0;match=[]
    for p in a['parents']:
        r=physical[p['job_id']];Q.need(r['State']==p['state'] and r['ExitCode']==p['exit_code']
            and int(r['ElapsedRaw'])==p['elapsed_raw_seconds'] and int(r['AllocCPUS'])==p['alloc_cpus']
            and r['NodeList']==p['node'] and r['UID']=='1278','RAW_VERSUS_SUMMARY_PARENT_ACCOUNTING')
        total+=p['elapsed_raw_seconds']*p['alloc_cpus']
        if p['job_id']==str(b['job_id']):match.append(p)
    Q.need(total==a['allocated_core_seconds'] and len(match)==1 and match[0]['state']=='COMPLETED'
        and match[0]['exit_code']=='0:0' and match[0]['alloc_cpus']==16 and match[0]['node']==b['node'],
        'EXACT_SUCCESSFUL_BOOTSTRAP_PARENT_NOT_UNRELATED_C0')
    parents=[plan['accepted_bootstrap_receipt_reference'],plan['accepted_bootstrap_accounting_reference'],raw,
             b['plan_reference'],b['startup_proof_reference']]
    return b,parents,cap


def parameters(mode):
    Q.need(mode in MODES,'EXACT_MODE');sid,names,cap=MODES[mode]
    return {'source_id':sid,'mode':mode,'required_member_basenames':list(names),'new_pure_fixture_methods':3,
        'all3_fixtures_before_archive_and_inventory_bodies':True,'archive_current_SHA_fstat_and_all_member_EOF_CRC_SHA':True,
        'maximum_SDF_record_bytes':16<<20,'maximum_native_line_bytes':1<<20,'maximum_identity_field_bytes':1<<20,
        'maximum_pickle_opcode_argument_bytes':16<<20,'maximum_pickle_symbol_stack_and_memo_entries':1000000,
        'maximum_global_symbols':4096,'maximum_active_archive_readers':1,'sixteen_busy_workers_claimed':False,
        'SDF_selected_fields':['_Name_title','ID','smiles'],'CSV_selected_literal_columns':['name'],
        'all_physical_source_rows_and_conformers_retained':True,'name_pairing':'EXACT_UNNORMALIZED_BYTES_NO_TRIMMING',
        'pickle_loaded_or_executed':False,'payload_globals_imported_or_instantiated':False,'assay_values_text_or_numeric_decoded':False,
        'native_graph_or_stereo_verified':False,'normalized_key_calls':0,'source_splits':'ALL_ORIGINAL_ROWS_NO_SPLIT_FILTER',
        'author_counts_used_as_population_cutoff':False,'X_filter_neutralization_tautomerization_or_geometry_changes':False,
        'pool_or_global_decontamination_or_full_identity_release':False,'new_network_UFF_QM_calls':0,
        'output_cap_bytes':cap,'cost_overrun_action':'REPORT_AND_CONTINUE'}
