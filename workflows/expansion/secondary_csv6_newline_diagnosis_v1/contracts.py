"""One independent byte-census protocol; not accepted by queue v12."""
from secondary_cpu_queue_v1 import common as Q
ROOT=Q.ROOT;HERE=ROOT/'code/secondary_csv6_newline_diagnosis_v1'
AUTHORITY_HERE=ROOT/'code/secondary_moleculenet_csv6_identity_v1'
MODULE='secondary_csv6_newline_diagnosis_v1.run';CONTAINER_CAP=1<<30
IDS=('hiv','muv','pcba','sider','tox21','toxcast')
COUNTS={'hiv':82255,'muv':186175,'pcba':875859,'sider':1427,'tox21':7831,'toxcast':8597}
FILES=('__init__.py','contracts.py','guard.py','runtime.py','analysis.py','run.py','test_v1.py','README.md','stage_schema.json')
MODES={'newline_diagnosis':{'key':'moleculenet_csv6_newline_diagnosis_alpha_v1',
 'plan':'SECONDARY_CSV6_NEWLINE_DIAGNOSIS_PLAN_V1','proof':'SECONDARY_CSV6_NEWLINE_DIAGNOSIS_STARTUP_V1',
 'stage':'SIX_CSV_RETAINED_NEWLINE_BYTE_CENSUS','pilot':False,'performance_profile':False,
 'scope_mode':'BOUNDED_SIX_CSV_ORIGINAL_BYTES_DIAGNOSIS','wall_max':1800,'cap':64<<20}}

def parameters(mode):
    Q.need(mode=='newline_diagnosis','ONLY_BOUNDED_EXISTING_SIX_CSV_BYTE_CENSUS')
    return {'mode':mode,'source_ids':list(IDS),'format_parent_job_id':'1884792','source_payloads':6,'source_payload_bytes':19961345,
      'expected_decoded_bytes':135667631,'physical_CSV_record_counts_from_792':COUNTS,'effective_molecule_count_claimed':False,
      'raw_CR_LF_CRLF_CRCRLF_counts':True,'literal_empty_and_horizontal_whitespace_physical_line_counts':True,
      'physical_lines_include_header_and_quoted_newlines':True,'original_CSV_summary_exact792_required':True,
      'sampled_pattern_offset_examples_per_pattern':4,'raw_context_or_identity_or_assay_values_persisted':False,
      'source_values_text_decoded_by_new_census':False,'original_selected_identity_field_stats_unchanged':True,
      'maximum_source_threads':6,'allocated_cpus':16,'sixteen_busy_workers_claimed':False,'maximum_pending_sources':6,
      'current_full_payload_SHA_fstat_and_full_decoded_SHA_CRC_EOF':True,'new_fixture_methods':3,'unchanged_format_fixture_methods':8,
      'all11_fixtures_before_any_payload_read':True,'target_python':'3.11.14','new_key_or_X_or_UFF_QM_calls':0,
      'original_reports_or_CSV_kernel_modified':False,'blank_or_no_key_rows_not_removed':True,'global_release':False,
      'algorithm_current_RSS_reference_bytes':48<<30,'runtime_MemAvailable_min_fraction':.15,'cost_overrun_action':'REPORT_AND_CONTINUE'}
