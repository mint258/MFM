"""Original metadata code with a private bounded SQLite/owner lookup cache."""
import builtins,json,types
from . import lookup_cache
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v6 import geometry as OLD
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v6 import io as PRIVATE
from workflows.data_v1_final.export.lossless_sqlite_io_v1 import codec as COMPRESSED
I=OLD.I;cohort=OLD.cohort;schema_header=OLD.schema_header;prepare=OLD.prepare;build=OLD.build
WORKER=OLD.WORKER;STATISTICS=OLD.STATISTICS;ELIGIBILITY=OLD.ELIGIBILITY;COVERAGE=OLD.COVERAGE;ResourceBudget=OLD.ResourceBudget

def metadata_function(root='.'):
    f=OLD.metadata_function();context=lookup_cache.Context(f.__globals__['lookup_batch'])
    module=lookup_cache.Module(root,context)
    def importing(name,globals=None,locals=None,fromlist=(),level=0):
        return module if level==0 and name=='sqlite3' else builtins.__import__(name,globals,locals,fromlist,level)
    namespace=dict(f.__globals__,I=PRIVATE.MetadataIO(),Wire=lookup_cache.Codec(COMPRESSED,context),
      lookup_batch=context.lookup_batch,__builtins__=dict(vars(builtins),__import__=importing))
    value=types.FunctionType(f.__code__,namespace,f.__name__,f.__defaults__,f.__closure__)
    value.lookup_context=context;return value

def metadata_children(plan,proof,root,budget,base_result,diagnostic_mids):
    f=metadata_function(root)
    try:return f(plan,proof,root,budget,base_result,diagnostic_mids)
    finally:print('METADATA_LOOKUP_CACHE',json.dumps(f.lookup_context.report(),sort_keys=True),flush=True)

def proof():
    value=OLD.proof();value['bounded_base_and_canonical_lookup_cache']=lookup_cache.proof()
    value['original_metadata_entire_code_object']=metadata_function().__code__ is OLD.metadata_function().__code__
    assert value['original_metadata_entire_code_object']
    return value
