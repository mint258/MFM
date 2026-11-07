"""Direct reuse of actual-profile runtime/math and scientific function objects."""
from pathlib import Path
import sys
from secondary_coconut_identity_norm_profile_v1 import run as profile
from secondary_coconut_identity_norm_profile_v1.runtime import Budget
from . import contracts as c

def source_scope_proof(plan):
    original=c.ROOT/'code/secondary_coconut_identity_norm_profile_v1'
    c.need(Path(profile.__file__).absolute()==original/'run.py' and Path(sys.modules[Budget.__module__].__file__).absolute()==original/'runtime.py' and
      Path(Budget.__init__.__code__.co_filename)==original/'runtime.py',
      'ACTUAL_REGISTERED_PROFILE_MODULE_OBJECTS_REQUIRED')
    refs=[]
    for name,(size,sha) in c.PROFILE.items():
        ref=c.pin(original/name);c.need(ref in plan['source_references'] and (ref['bytes'],ref['sha256'])==(size,sha),'EXACT_ACTUAL_PROFILE_FILE_BYTES');refs.append(ref)
    names=('normalize','load_kernel','init_worker','work','verify_source','selected_rows','observe_environment')
    functions={name:getattr(profile,name) for name in names}
    c.need(all(Path(f.__code__.co_filename)==original/'run.py' for f in functions.values()),'DIRECT_ORIGINAL_FUNCTION_OBJECTS_NOT_REDEFINED')
    c.need(Budget is __import__('secondary_coconut_identity_norm_profile_v1.runtime',fromlist=['Budget']).Budget,'DIRECT_CURRENT_MEMORY_RUNTIME_CLASS')
    return {'basis':'DIRECT_REGISTERED_PROFILE_FUNCTION_OBJECTS_AND_ALL_FOUR_FILE_SHA',
      'profile_source_references':refs,'functions':{name:{'module':f.__module__,'qualified_name':f.__qualname__,'source_file':f.__code__.co_filename,
      'first_line':f.__code__.co_firstlineno} for name,f in functions.items()},'runtime_class':Budget.__module__+'.'+Budget.__qualname__,
      'new_normalization_function_defined':False,'selection_change':'uniform<=10000/table -> every physical Parquet ordinal',
      'resource_only_change_claimed':False,'coordinator_output_and_aggregation_changed':True,'pool_release_authorized':False}

def profile_forecast(prior):
    wall=sum(prior['table_phase_timings'][t]['read_decode_dispatch_result_write_wall_seconds']*c.COUNTS[t]/prior['observed_rows_by_table'][t] for t in c.COUNTS)
    sizes={Path(x['path']).name:x['bytes'] for x in prior['outputs']}
    raw=sizes['completed_observations.jsonl'];pq=sizes['normalization_observations.parquet'];ratio=c.TOTAL/prior['observed_rows']
    return {'basis':'ACTUAL1884785_TABLE_WALL_AND_PHYSICAL_OUTPUT_LINEAR_EXTRAPOLATION_NOT_OBSERVED_FULL_COST',
      'nominal_table_pipeline_wall_seconds':wall,'estimated_journal_plus_Parquet_bytes':(raw+pq)*ratio,
      'profile_actual_journal_bytes':raw,'profile_actual_Parquet_bytes':pq,'profile_actual_parent_allocated_core_seconds':3552,
      'profile_source_hash_already_scanned_same_two_full_files':True,
      'new_SQLite_aggregation_full_IO_final_hash_growth_and_load_cost_not_measured_by_profile':True,
      'ceiling_wall_seconds':172800,'ceiling_output_bytes':32*1024**3,'ceilings_are_not_forecasts':True,
      'overrun_report_threshold_factor':1.5,'on_cost_overrun':'REPORT_AND_CONTINUE','cost_dispatch_STOP':False}
