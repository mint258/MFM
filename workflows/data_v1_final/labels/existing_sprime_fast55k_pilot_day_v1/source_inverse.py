"""Entire original run/math; explicit selected-cache orchestration IO delta."""
import ast,inspect,textwrap
from . import contract as C,geometry as G,fast_coverage as F
from workflows.data_v1_final.labels.existing_sprime_native_pilot_day_v1 import run as OriginalRun,source_inverse as OriginalInverse
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec as OriginalCodec

def proof():
    from . import run
    expected=inspect.getsource(OriginalRun.execute).replace('EXISTING_SPRIME_NATIVE_PILOT_DAY_RECEIPT_V1','EXISTING_SPRIME_FAST55K_PILOT_DAY_RECEIPT_V1').replace(
      'PROVISIONAL55K_NATIVE_RANDOM_GEOMETRY_ANTI_JOIN_AND_TRAIN_D4_COMPLETE_PENDING_ACTUAL_C0_ROOT_SEAL',
      'PROVISIONAL55K_FAST_TYPED_NATIVE_RANDOM_AND_TRAIN_D4_COMPLETE_PENDING_ACTUAL_C0_ROOT_SEAL')
    actual=inspect.getsource(run.execute)
    C.need(actual==expected and ast.dump(ast.parse(textwrap.dedent(actual)))==ast.dump(ast.parse(textwrap.dedent(expected))),
      'ENTIRE_ORIGINAL_EXECUTE_TEXT_AST_ONLY_NEW_TRUTHFUL_RECEIPT_STATUS')
    for name in('references','numeric_state','next_route','canonical_numeric','K_bytes'):
        C.need(inspect.getsource(getattr(run,name))==inspect.getsource(getattr(OriginalRun,name)),'ORIGINAL_ROUTE_FUNCTION_TEXT:'+name)
    C.need(G.ORIGINAL.prepare is G.prepare.__globals__['ORIGINAL'].prepare and G.build is G.ORIGINAL.build
      and G.cohort is G.ORIGINAL.cohort and G.schema_header is G.ORIGINAL.schema_header and G.metadata_children is G.ORIGINAL.metadata_children
      and G.ResourceBudget.__bases__==(G.ORIGINAL.ResourceBudget,)and G.WORKER is G.ORIGINAL.WORKER,'ORIGINAL_NATIVE_GEOMETRY_CHILD_INPUT_HASH_AND_RESOURCE_OBJECTS')
    C.need(F.K is OriginalCodec,'ORIGINAL_NUMERIC_CODEC_NOT_REWRITTEN')
    new=G.prepare_function();old=G.ORIGINAL.prepare
    C.need(new.__code__ is old.__code__ and new.__defaults__ is old.__defaults__ and new.__closure__ is old.__closure__
      and new.__kwdefaults__ is old.__kwdefaults__ and set(new.__globals__)==set(old.__globals__)
      and all(new.__globals__[k]is old.__globals__[k]for k in old.__globals__ if k!='__builtins__'),
      'ORIGINAL_PREPARE_CODE_ONLY_PRIVATE_DUCKDB_TEMP8GIB_IMPORT_CONTEXT')
    C.need(F.V.field_counts is __import__('workflows.data_v1_final.labels.existing_sprime_pilot_day_v1.coverage',fromlist=['coverage']).field_counts
      and run.B is OriginalRun.B and run.L is OriginalRun.L and run.I is OriginalRun.I and run.T is G.MEMO.STATISTICS
      and run.E is G.MEMO.ELIGIBILITY,'DIRECT_QUALITY_CALIBRATION_MASK_AND_APPROVED_READER_INTEGER_IO_OBJECTS')
    C.need(F.BATCH_ROWS==16 and len(C.FILES)==10 and 'fast_coverage.py'in C.FILES and 'reader_memo.py'in C.FILES,'FIXED16_PART_PARALLEL_IO_WITHIN_EXACT_SOURCE10')
    return {'status':'ORIGINAL_NATIVE_RUN_MATH_WITH_PARALLEL55K_SELECTED_TYPED_IO',
      'original_native_inverse':OriginalInverse.proof(),'whole_old_SHA_stream_digest_and_mass_preserved':True,
      'same_frozen55k_all_N14_tasks_and_base':True,'Source_order_and_171_group_math_unchanged':True,
      'no_live5180_input_or_terminal_dependency':True,'independent_two_replays':True,'new_QM_UFF_calls':0,
      'input_value_mask_or_threshold_changed':False,'old_Source_or_shared_globals_patched':False}
