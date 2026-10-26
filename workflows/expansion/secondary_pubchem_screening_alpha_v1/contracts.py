"""Three finite Alpha protocols; no full dispatch is authorized by a template."""
from pathlib import Path
ROOT=Path('/gfshome/alpha/codex_data_v1_20261026')
HERE=ROOT/'code/secondary_pubchem_screening_alpha_v1'
FROZEN=ROOT/'code/pubchem_science_frozen_v1'
MODULE='secondary_pubchem_screening_alpha_v1.run'
STORAGE_SCOPE=ROOT/'control/secondary_cpu_queue/storage_scope_v7_pubchem_uniform_index_copy_v1.json'
N=124857440;RAW_BYTES=1488715010;UNCOMPRESSED_BYTES=8880849781
RAW_SHA='2504bc00da1b0587ae208d8a5fb2a4fe6043c215436150f2023d59c57c5cd2b7'
PARTS=500;PART_ROWS=250000;PART_BYTES=67108864;MAX_LINE=3786
SEED=20261026;COUNT=10000;LONGEST=16;INDEX_CAP=4096;CONTAINER_CAP=1<<30
MODES={
 'inventory':{'key':'pubchem_original_index_inventory_alpha_v1','plan':'SECONDARY_PUBCHEM_PHYSICAL_INVENTORY_PLAN_V1',
  'proof':'SECONDARY_PUBCHEM_PHYSICAL_INVENTORY_STARTUP_V1','stage':'PUBCHEM_ORIGINAL_GZIP_PHYSICAL_INVENTORY','pilot':False,'cap':10<<30,'wall':14400,'scope_mode':'BOUNDED_SOURCE_INVENTORY','performance_profile':False},
 'profile':{'key':'pubchem_raw_uniform10000_profile_alpha_v1','plan':'SECONDARY_PUBCHEM_UNIFORM10000_PROFILE_PLAN_V1',
  'proof':'SECONDARY_PUBCHEM_UNIFORM10000_PROFILE_STARTUP_V1','stage':'PUBCHEM_UNIFORM10000_EQUIVALENCE_AND_COST','pilot':True,'cap':2<<30,'wall':14400,'scope_mode':'BOUNDED_UNIFORM_EQUIVALENCE_COST_PROFILE','performance_profile':True},
 'full_shard':{'key':'pubchem_raw_feature_shard_alpha_v1','plan':'SECONDARY_PUBCHEM_ORDINAL_FEATURE_SHARD_PLAN_V1',
  'proof':'SECONDARY_PUBCHEM_ORDINAL_FEATURE_SHARD_STARTUP_V1','stage':'PUBCHEM_EXCLUSIVE_ORDINAL_FEATURE_SHARD','pilot':False,'cap':None,'wall':None,'scope_mode':'EXCLUSIVE_ORDINAL_FEATURE_SHARD','performance_profile':False}}
FILES=('__init__.py','contracts.py','guard.py','runtime.py','source.py','journal.py','kernel.py','run.py','test_v1.py',
 'materialize_shards.py','frozen_manifest.json','stage_schema.json','README.md')

def parameters(mode,first_part=None,last_part=None,lo=None,hi=None):
    if mode not in MODES:raise ValueError('ONLY_THREE_EXACT_ALPHA_PUBCHEM_PROTOCOLS')
    shared={'mode':mode,'population_N':N,'source_compressed_bytes':RAW_BYTES,'source_compressed_sha256':RAW_SHA,
      'source_uncompressed_bytes':UNCOMPRESSED_BYTES,'source_physical_parts':PARTS,'seed':SEED,
      'RDKit':'2025.09.5','target_python':'3.11.14','target_pyarrow':'17.0.0','workers':16,'maximum_pending':32,
      'strict_UTF8':True,'source_ordinal_starts_one':True,'source_values_unchanged':True,'heavy_atom_upper_bound':None,
      'neutralization':False,'tautomer_canonicalization':False,'isotope_policy':'preserve','stereo_policy':'preserve_source',
      'chemical_dispatch':'ORIGINAL_597_OLD_SUCCESS_PASSTHROUGH_EXACT_RING_KEKULIZE_ONLY',
      'technical_unknown_is_chemical_exclusion':False,'global_pool_release':False,'filtered_dedup_1M_guide_stage_completed':False,
      'decontamination_novelty_UFF_QM_training':False,'cost_overrun_action':'REPORT_AND_CONTINUE',
      'algorithm_current_RSS_reference_bytes':48<<30,'runtime_MemAvailable_min_fraction':.15,'new_pure_fixture_methods':5,'all5_fixtures_before_real_data':True}
    if mode=='inventory':
        return {**shared,'chemical_parsing':False,'part_max_records':PART_ROWS,'part_max_bytes':PART_BYTES,
          'physical_index_entry_cap_bytes':INDEX_CAP,'uniform_physical_locators':COUNT,'independent_longest_locators':LONGEST,
          'original_Main_index_part_SHA_row_byte_equivalence':True,'original_gzip_is_input_not_output':True}
    if mode=='profile':
        return {**shared,'uniform_raw_rows':COUNT,'sampling':'sorted(random.Random(20261026).sample(range(1,N+1),10000))',
          'longest_diagnostic_rows':LONGEST,'longest_excluded_from_uniform_mean':True,'maximum_reference_rows_in_memory':COUNT+LONGEST,
          'main_original10000_journal_is_scientific_data':True,'scientific_object_comparison':'ALL_FIELDS_TYPED_BINARY64',
          'journal_before_parquet':True,'new_pure_fixture_methods':5}
    if not all(type(x) is int for x in (first_part,last_part,lo,hi)) or not(0<=first_part<=last_part<PARTS and 1<=lo<=hi<=N):
        raise ValueError('EXACT_FINITE_CONTIGUOUS_FULL_SHARD_REQUIRED')
    return {**shared,'first_part':first_part,'last_part':last_part,'first_ordinal':lo,'last_ordinal':hi,
      'expected_rows':hi-lo+1,'selection':'ALL_PHYSICAL_ROWS_IN_EXCLUSIVE_CONTIGUOUS_PART_RANGE',
      'durable_dispatch_before_submit':True,'durable_full_result_before_parquet':True,'new_pure_fixture_methods':5}
