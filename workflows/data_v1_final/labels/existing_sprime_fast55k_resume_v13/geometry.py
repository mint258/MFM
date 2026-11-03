"""Original metadata code and statistics, with exact closed-file serialization reuse."""
import types
from . import recovery,io as PARQUET_IO
from .resource import ResourceBudget,SafeIO,SafeMetadataIO
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v10 import geometry as OLD
I=SafeIO();cohort=OLD.cohort;schema_header=OLD.schema_header;prepare=OLD.prepare;build=OLD.build
WORKER=OLD.WORKER;STATISTICS=OLD.STATISTICS;ELIGIBILITY=OLD.ELIGIBILITY;COVERAGE=OLD.COVERAGE
def metadata_function(root='.',context=None):
    old=OLD.metadata_function(root)
    namespace=dict(old.__globals__,I=SafeMetadataIO(context),Recovery=recovery.Recovery)
    function=types.FunctionType(old.__code__,namespace,old.__name__,old.__defaults__,old.__closure__)
    function.__kwdefaults__=old.__kwdefaults__;function.lookup_context=old.lookup_context
    function.original_code=old.__code__
    return function
def metadata_children(plan,proof,root,budget,base_result,diagnostic_mids):
    context=PARQUET_IO.ReuseContext(plan,root,budget)
    return metadata_function(root,context)(plan,proof,root,budget,base_result,diagnostic_mids)
def proof():
    from .resource import proof as resource_proof
    current=metadata_function()
    assert current.__code__ is current.original_code
    return dict(original_metadata_code_object_retained=True,prior_source_witness=OLD.proof(),
      actual_completed5478_base_and_prefix_proof_reused=True,resource=resource_proof())
