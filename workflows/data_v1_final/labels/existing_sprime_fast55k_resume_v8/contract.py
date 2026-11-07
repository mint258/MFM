"""Same scientific plan, explicit checkpoint ownership and56GiB output budget."""
import types
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v7 import contract as OLD
KEY='existing_sprime_fast55k_resume_v8'
MODULE='workflows.data_v1_final.labels.'+KEY+'.run'
HERE=OLD.REPO/'workflows/data_v1_final/labels'/KEY
FILES=('__init__.py','contract.py','metadata.py','run.py','geometry.py','recovery.py','resource.py','README.md')
def __getattr__(name):return getattr(OLD,name)
def scope(p):
    value=OLD.scope(p)
    value.update(original_metadata_entire_code_object=False,
      metadata_recovery_reference=p.get('metadata_recovery_reference'),
      metadata_prefix_origin='ACTUAL5455_C0_RESOURCE_PARTIAL_NOT_COMPLETE_D4',
      metadata_scan='ORIGINAL_COMPLETED_PREFIX_PLUS_ORIGINAL_SUFFIX_WITH_EXACT_PHYSICAL_OFFSETS',
      old_logical_rows='ALL_TABLES_ROWID_PREFIX_FULL_SHA_BEFORE_AND_AFTER',
      all_original_metadata_rows_scanned=True,
      actual_original_decoder_renderer_double_hash_and_quality_unchanged=True)
    return value
def plan(p):
    f=OLD.plan;g=dict(f.__globals__,KEY=KEY,scope=scope)
    value=types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(p)
    r=OLD.meta(p['metadata_recovery_reference'])
    OLD.need(r['schema']=='ROOT_D4_PARTIAL5455_CHECKPOINT_RECOVERY_V1'
      and r['status']=='APPROVED_APPEND_ONLY_METADATA_CURSOR_RESOURCE_CONTINUATION'
      and r['reviewer']=='root' and r['old_job_id']=='4525455'
      and r['new_output_root']==p['output_directory'] and p['whole_output_cap_bytes']==56<<30
      and r['raw_WP5_and_LMDB_unchanged'] is True,'EXPLICIT_CURRENT_CHECKPOINT_AND_RESOURCE_VERSION')
    return value
