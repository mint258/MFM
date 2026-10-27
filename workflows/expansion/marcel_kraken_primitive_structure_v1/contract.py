"""Actual completed opcode parent, exact thirteen-opcode structure-only stage."""
import csv,io
from workflows.expansion.marcel_identity_format_probe_v1 import contract as M
from .primitive import ALLOW
Q=M.Q;HERE=Q.REPO/'workflows/expansion/marcel_kraken_primitive_structure_v1'
FILES=('__init__.py','contract.py','primitive.py','structure.py','run.py','test_v1.py','materialize.py','README.md')
KEY='marcel_kraken_primitive_structure_main_v1';MODULE='workflows.expansion.marcel_kraken_primitive_structure_v1.run'
STAGE='MARCEL_KRAKEN_BOUNDED_NONEXECUTING_PRIMITIVE_STRUCTURE_EVIDENCE';CAP=64<<20
OLD=tuple(M.HERE/n for n in M.FILES)+tuple(Q.REPO/n for n in M.OLD)
PARAMETERS={'source_id':'marcel_kraken_zip','accepted_opcode_parent_job_id':'4521755','pickle_protocol':4,
    'decoded_member_bytes':94805786,'allowed_opcodes':sorted(ALLOW),'exact_parent_opcode_counts_required':True,
    'maximum_primitive_nodes':1000000,'maximum_stack_and_memo_entries':1000000,'maximum_source_assignments':2000000,
    'maximum_string_bytes':16<<20,'maximum_frame_bytes':94805786,'maximum_total_literal_UTF8_bytes':128<<20,
    'maximum_structure_walk_depth':64,'top_literal_examples':8,'secondary_examples_per_top':3,'literal_string_maximum_bytes':512,
    'BINFLOAT_preserved_as_original_eight_bytes':True,'dictionary_assignments_order_duplicates_and_memo_references_preserved':True,
    'pickle_load_Unpickler_GLOBAL_REDUCE_BUILD_or_payload_constructor_execution':False,'payload_named_module_import':False,
    'new_pure_fixture_methods':3,'all3_fixtures_before_archive_and_inventory_bodies':True,'maximum_active_archive_readers':1,
    'sixteen_busy_workers_claimed':False,'source_field_semantics_accepted_before_actual_structure':False,
    'normalized_key_calls':0,'native_graph_stereo_or_population_accepted':False,'assay_numeric_values_persisted':False,
    'author_reported_counts_used_as_cutoff':False,'global_decontamination_pool_training_release':False,
    'new_network_UFF_QM_calls':0,'cost_overrun_action':'REPORT_AND_CONTINUE'}


def unique(refs):
    by={}
    for r in refs:Q.need(r['path'] not in by or by[r['path']]==r,'CONFLICTING_ACTUAL_REFERENCE');by[r['path']]=r
    return [by[k] for k in sorted(by)]


def inputs(plan):
    b=M.meta(plan['accepted_opcode_receipt_reference']);a=M.meta(plan['accepted_opcode_accounting_reference'])
    Q.need(b['schema']=='MARCEL_IDENTITY_FORMAT_PROBE_RECEIPT_V1' and b['status']=='SOURCE_FORMAT_OBSERVATION_COMPLETE_IDENTITY_RELEASE_PENDING'
        and b['mode']=='kraken_opcodes' and str(b['job_id'])=='4521755' and b['uid']==1278 and b['endpoint']=='202.38.247.57:22'
        and b['fixtures']['tests_run']==3 and all(b['fixtures'][k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),
        'ACTUAL_ORIGINAL_OPCODE_PROBE_WITH_PURE3_PASS')
    result=b['result'];o=result['observation'];Q.need(result['all_member_EOF_CRC_SHA_complete'] is True
        and len(result['members'])==1 and result['members'][0]['name']=='Kraken.pickle'
        and result['members'][0]['decoded_bytes']==94805786 and result['members'][0]['EOF_CRC_SHA_complete'] is True
        and o['status']=='NONEXECUTING_OPCODE_STREAM_COMPLETE_IDENTITY_PENDING' and set(o['opcode_counts'])==ALLOW
        and all(type(n) is int and n>0 for n in o['opcode_counts'].values()) and o['protocol_declarations']==[4]
        and o['STOP_observed'] is True and o['parsed_bytes_through_STOP']==94805786
        and o['bytes_after_STOP_or_parser_error']==0 and o['parser_error'] is None
        and o['global_symbols']==[] and o['symbol_resolution_unknown_counts']=={} and o['bounded_call_opcode_examples']==[],
        'EXACT_ACTUAL_NONEXECUTING_THIRTEEN_OPCODE_EOF_EVIDENCE')
    old=M.meta(b['plan_reference']);proof=M.meta(b['startup_proof_reference']);_,parents,_=M.authority(old)
    Q.need(old['mode']=='kraken_opcodes' and old['archive_reference']==result['archive_reference']==plan['archive_reference']
        and old['inventory_reference']==result['producer_inventory_reference']==plan['inventory_reference']
        and proof['uid']==1278 and str(proof['job_id'])==str(b['job_id']) and proof['request']['node']==b['node']
        and proof['request']['scope_key']=='marcel_identity_format_probe_main_v1'
        and proof['request']['scope_parameters']==old['scope_parameters']==M.parameters('kraken_opcodes')
        and b['plan_reference'] in proof['request']['source_references'],'ACTUAL_OPCODE_PLAN_PROOF_AND_BOOTSTRAP_CHAIN')
    for p in OLD:Q.need(Q.pin(p) in proof['request']['source_references'],'EXACT_FROZEN_PROBE_FUNCTION_BYTES_REUSED')
    raw=a['raw_sacct_reference'];Q.need(Q.pin(raw['path'])==raw,'ACTUAL_OPCODE_PARENT_RAW_ACCOUNTING')
    rows=list(csv.DictReader(io.StringIO(Q.read_small(raw['path']).decode('utf-8')),delimiter='|'));rows=[r for r in rows if '.' not in r['JobIDRaw']]
    Q.need(a['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and a['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
        and a['endpoint']=='202.38.247.57:22' and a['uid']==1278 and a['query_returncode']==0
        and a['failed_timeout_startup_cleanup_elapsed_retained'] is True and len(a['parents'])==len(rows)==1,'EXACT_OPCODE_PARENT_ACCOUNTING')
    p=a['parents'][0];r=rows[0];Q.need(p['job_id']==r['JobIDRaw']==str(b['job_id']) and p['state']==r['State']=='COMPLETED'
        and p['exit_code']==r['ExitCode']=='0:0' and p['node']==r['NodeList']==b['node'] and r['UID']=='1278'
        and p['alloc_cpus']==int(r['AllocCPUS'])==16 and p['elapsed_raw_seconds']==int(r['ElapsedRaw'])
        and a['allocated_core_seconds']==16*p['elapsed_raw_seconds'],'REAL_MAIN_C0_AND_ACTUAL_ALLOCATION_COST')
    refs=unique([*parents,plan['accepted_opcode_receipt_reference'],plan['accepted_opcode_accounting_reference'],raw,b['plan_reference'],b['startup_proof_reference']])
    return b,refs
