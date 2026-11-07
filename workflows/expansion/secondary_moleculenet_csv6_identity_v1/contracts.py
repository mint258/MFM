"""Two exact six-CSV phases; the physical population is frozen by actual792."""
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
ROOT=Q.ROOT;HERE=ROOT/'code/secondary_moleculenet_csv6_identity_v1'
MODULE='secondary_moleculenet_csv6_identity_v1.run';IDS=('hiv','muv','pcba','sider','tox21','toxcast')
COUNTS={'hiv':82255,'muv':186175,'pcba':875859,'sider':1427,'tox21':7831,'toxcast':8597}
N=1162144;PROFILE_N=47855;CONTAINER_CAP=1<<30
FILES=('__init__.py','contracts.py','guard.py','projection.py','runtime.py','journal.py','run.py','test_v1.py','README.md','stage_schema.json','format792_authority.json')
MODES={
 'profile':{'key':'moleculenet_csv6_identity_norm_profile_alpha_v1','plan':'SECONDARY_MOLECULENET_CSV6_IDENTITY_PROFILE_PLAN_V1',
   'proof':'SECONDARY_MOLECULENET_CSV6_IDENTITY_PROFILE_STARTUP_V1','stage':'MOLECULENET_CSV6_IDENTITY_NORMALIZATION_PROFILE',
   'pilot':True,'performance_profile':True,'scope_mode':'SIX_CSV_ALL_PHYSICAL_ORDINAL_PROFILE','wall_max':14400,'cap':2<<30},
 'full':{'key':'moleculenet_csv6_identity_norm_full_alpha_v1','plan':'SECONDARY_MOLECULENET_CSV6_IDENTITY_FULL_PLAN_V1',
   'proof':'SECONDARY_MOLECULENET_CSV6_IDENTITY_FULL_STARTUP_V1','stage':'MOLECULENET_CSV6_IDENTITY_NORMALIZATION_FULL',
   'pilot':False,'performance_profile':False,'scope_mode':'SIX_CSV_ALL_PHYSICAL_ROWS','wall_max':172800,'cap':None}}

def parameters(mode):
    if mode not in MODES:raise ValueError('EXACT_PROFILE_OR_FULL_ONLY')
    return {'mode':mode,'source_ids':list(IDS),'frozen_format_job_id':'1884792','physical_rows_by_source':COUNTS,
      'all_physical_source_rows':N,'processed_rows':PROFILE_N if mode=='profile' else N,'role':'ALLSPLITS',
      'train_test_assignment_inferred':False,'maximum_profile_rows_per_source':10000,'seed':20261026,
      'sampler':'DIRECT_FROZEN_B_SELECTED_ORDINALS_SHA256_SOURCE_SEED_PY_RANDOM_SAMPLE_SORTED_V1','sampler_python':'3.11.14',
      'target_python':'3.11.14','target_numpy':'2.2.6','target_RDKit':'2025.09.5','target_pyarrow':'17.0.0',
      'workers':16,'maximum_pending':32,'new_parser_fixture_methods':4,'unchanged_B_kernel_fixture_methods':3,
      'all7_fixtures_before_any_payload_body_reads':True,'current_payload_full_SHA_and_fstat':True,'full_stream_EOF_CRC_and_decoded_SHA':True,
      'original_format_feed_called_directly':True,'new_CSV_grammar_defined':False,'callback_seam_only':True,'only_identity_fields_text_decoded':True,
      'assay_values_text_or_numeric_decoded_or_persisted':False,'blank_invalid_duplicate_ID_zero_ID_no_key_rows_retained':True,
      'physical_ordinal_row_identity_not_opaque_ID_uniqueness':True,'raw_row_dispatch_and_result_durable_before_parquet':True,
      'new_X_rules_or_features':False,'neutralization':False,'tautomer_edits':False,'isotope_stereo_edits':False,
      'native_QM7b_SDF_MOL2_identity':'UNKNOWN_UNCHANGED_NOT_COVERED_BY_SIX_CSV',
      'global_decontamination_or_pool_release':False,'new_network_UFF_QM_training_calls':0,
      'algorithm_current_RSS_reference_bytes':48<<30,'runtime_MemAvailable_min_fraction':.15,'cost_overrun_action':'REPORT_AND_CONTINUE'}
