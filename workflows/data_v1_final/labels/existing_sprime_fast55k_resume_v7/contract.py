"""Same closed geometry, all original source scans and scientific operations."""
import types
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v6 import contract as OLD
KEY='existing_sprime_fast55k_resume_v7';MODULE='workflows.data_v1_final.labels.'+KEY+'.run'
HERE=OLD.REPO/'workflows/data_v1_final/labels'/KEY
FILES=('__init__.py','contract.py','metadata.py','run.py','geometry.py','lookup_cache.py','README.md')

def __getattr__(name):return getattr(OLD,name)

def scope(p):
    s=OLD.scope(p);s.update(metadata_base_lookup='EXACT_STATIC_PM7_RID_SET_AND_BOUNDED_ORIGINAL_BLOB_CACHE',
      metadata_base_blob_cache_cap_bytes=8<<30,metadata_decoded_base_cache_cap_bytes=12<<30,
      decoded_base_return_policy='EXACT_VERIFIED_ORIGINAL_BYTES_WITH_PRIVATE_DEEPCOPY',
      metadata_canonical_lookup='ORIGINAL_LOOKUP_ONLY_FOR_PILOT_BASE_RIDS',
      all_original_metadata_rows_scanned=True,original_metadata_entire_code_object=True,
      all_original_input_binding_and_quality_checks_retained=True)
    return s

def plan(p):
    f=OLD.plan;g=dict(f.__globals__,KEY=KEY,scope=scope)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(p)
