"""Same science and56GiB output; reuse actual5478 completed prefix certification."""
import types
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v8 import contract as OLD
KEY='existing_sprime_fast55k_resume_v9'
MODULE='workflows.data_v1_final.labels.'+KEY+'.run'
HERE=OLD.REPO/'workflows/data_v1_final/labels'/KEY
FILES=('__init__.py','contract.py','metadata.py','run.py','geometry.py','recovery.py','resource.py','README.md')
def __getattr__(name):return getattr(OLD,name)
def scope(p):
    s=OLD.scope(p)
    s.update(metadata_prefix_origin='ACTUAL5478_C0_RESOURCE_PARTIAL_WITH_COMPLETED_BASE_F64_AND_OLD_PREFIX_SNAPSHOT',
      old_logical_rows='CERTIFIED_OLD_PREFIX_AND_NEW_CLOSED_SUFFIX_SEGMENTS_CHECKED_AT_END',
      whole_census_IO='PRIVATE_ORIGINAL_SAVE_TEXT_INIT_QUOTA_EVENT_OBSERVE_ALL_SAME_COMPLETE_RECENSUS')
    return s
def plan(p):
    f=OLD.OLD.plan;g=dict(f.__globals__,KEY=KEY,scope=scope)
    value=types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(p)
    r=OLD.meta(p['metadata_recovery_reference'])
    OLD.need(r['schema']=='ROOT_D4_PARTIAL5478_CHECKPOINT_RECOVERY_V1'
      and r['status']=='APPROVED_APPEND_ONLY_METADATA_CURSOR_RESOURCE_CONTINUATION' and r['reviewer']=='root'
      and r['old_job_id']=='4525478' and r['new_output_root']==p['output_directory']
      and p['whole_output_cap_bytes']==56<<30 and r['raw_WP5_and_LMDB_unchanged'] is True
      and r['actual_completed_base_F64_and_prefix_snapshot_reused'] is True,
      'EXPLICIT_ACTUAL5478_PREFIX_CERTIFICATION_AND_JOURNAL_IO_FIX')
    return value
