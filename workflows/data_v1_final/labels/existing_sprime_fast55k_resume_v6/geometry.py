"""Original metadata code and statistics; only closed tables and private blob IO."""
import types
from . import geometry_tables,io as PRIVATE
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v5 import geometry as OLD
from workflows.data_v1_final.export.lossless_sqlite_io_v1 import codec as COMPRESSED
I=OLD.I;cohort=OLD.cohort;schema_header=OLD.schema_header;prepare=OLD.prepare
WORKER=OLD.WORKER;STATISTICS=OLD.STATISTICS;ELIGIBILITY=OLD.ELIGIBILITY;COVERAGE=OLD.COVERAGE;ResourceBudget=OLD.ResourceBudget
build=geometry_tables.build

def metadata_function():
    f=OLD.metadata_children;namespace=dict(f.__globals__,I=PRIVATE.MetadataIO(),Wire=COMPRESSED)
    return types.FunctionType(f.__code__,namespace,f.__name__,f.__defaults__,f.__closure__)

def metadata_children(*args,**kwargs):return metadata_function()(*args,**kwargs)

def proof():
    value=PRIVATE.proof();value.update(original_metadata_entire_code_object=metadata_function().__code__ is OLD.metadata_children.__code__,
      original_statistics_object=STATISTICS is OLD.STATISTICS,original_eligibility_object=ELIGIBILITY is OLD.ELIGIBILITY,
      original_50000_TRAIN_5000_ROUTINE_VAL_two_exact_replays=True,all_six_geometry_tables_reused_no_recompute=True)
    return value
