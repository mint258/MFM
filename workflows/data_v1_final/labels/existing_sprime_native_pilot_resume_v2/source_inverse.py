"""Exact old math/child objects; explicit technical stage adoption and job IO."""
import ast,hashlib,inspect,textwrap
from . import contract as C,geometry as G
from workflows.data_v1_final.labels.existing_sprime_native_pilot_day_v1 import run as NATIVE_RUN,source_inverse as NATIVE_INVERSE

def proof():
    from . import run
    old=inspect.getsource(NATIVE_RUN.execute)
    expected=old.replace('EXISTING_SPRIME_NATIVE_PILOT_DAY_RECEIPT_V1','EXISTING_SPRIME_NATIVE_PILOT_RESUME_RECEIPT_V2')
    expected=expected.replace('PROVISIONAL55K_NATIVE_RANDOM_GEOMETRY_ANTI_JOIN_AND_TRAIN_D4_COMPLETE_PENDING_ACTUAL_C0_ROOT_SEAL',
      'PROVISIONAL55K_NATIVE_RANDOM_CONTINUATION_AND_TRAIN_D4_COMPLETE_PENDING_ACTUAL_C0_ROOT_SEAL')
    expected=expected.replace("'fixture_gate':gate,'checkpoint_reference':latest","'fixture_gate':gate,'checkpoint_reference':latest,'resume_origin_review_reference':plan['resume_origin_review_reference']")
    expected=expected.replace("'output_root':str(root/'typed_coverage')","'output_root':coverage['original_parts_output_root']")
    current=inspect.getsource(run.execute)
    C.need(current==expected and ast.dump(ast.parse(textwrap.dedent(current)))==ast.dump(ast.parse(textwrap.dedent(expected))),
      'ENTIRE_OLD_EXECUTE_BYTES_AST_ONLY_TRUTHFUL_RECEIPT_ORIGIN_AND_OLD_TYPED_PART_ROOT')
    for name in ('references','numeric_state','next_route','canonical_numeric','K_bytes'):
        C.need(inspect.getsource(getattr(run,name))==inspect.getsource(getattr(NATIVE_RUN,name)),'ORIGINAL_SUPPORT_FUNCTION_BYTES:'+name)
    C.need(run.ORIGINAL_STATISTICS is NATIVE_RUN.T and run.T.original is NATIVE_RUN.T and run.B is NATIVE_RUN.B and run.L is NATIVE_RUN.L and run.I is NATIVE_RUN.I
      and G.WORKER is G.N.WORKER and G.metadata_children is G.N.metadata_children and G.ResourceBudget is G.N.ResourceBudget,
      'ORIGINAL_STATISTICS_MATH_PRIVATE_READER_IO_AND_DIRECT_CHILD_RENDER_INPUT_HASH_RESOURCE_OBJECTS')
    function=G.eligibility_function();original=G.E.build
    C.need(function.__code__ is original.__code__ and function.__defaults__ is original.__defaults__ and function.__closure__ is original.__closure__
      and function.__kwdefaults__ is original.__kwdefaults__,'ORIGINAL_ELIGIBILITY_BUILD_CODE_DEFAULTS_CLOSURE')
    C.need(set(function.__globals__)==set(original.__globals__)and all(function.__globals__[k]is original.__globals__[k]
      for k in original.__globals__ if k!='sqlite3')and isinstance(function.__globals__['sqlite3'],G.SQLiteSchema),
      'PRIVATE_GLOBALS_ONLY_EXACT_NEW_DATABASE_JOB_INTEGER_DDL_NO_OLD_PATCH')
    C.need(G.ELIGIBILITY.lookup is G.E.lookup and run.ORIGINAL_ELIGIBILITY is G.E,'ALL_ORIGINAL_READERS_GET_REAL_INTEGER_ON_DISK_NOT_LOOKUP_MOCK')
    tree=ast.parse((C.HERE/'geometry.py').read_bytes())
    for node in ast.walk(tree):
        if isinstance(node,ast.Call)and isinstance(node.func,ast.Attribute):
            C.need(node.func.attr not in ('compute','native_record_and_value','checked_uff','rmsd','pm7_compute','geometry_orders'),
              'NO_ORIGINAL_NATIVE_SCIENCE_RECALC_OPTIMIZATION_OR_D7_CALLED_DURING_ADOPTION')
    C.need(len(C.RESUME_PARENT_KEYS)==6 and 'receipt_reference'not in C.RESUME_PARENT_KEYS
      and set(C.deferred_stage_locators('/source-witness-only'))=={'receipt','prefix','coverage_manifest','ordinary_root'},
      'OLD_SCIENTIFIC_RECEIPT_ONLY_FIXED_DEFERRED_CPU_LOCATOR_NOT_LOGIN_POSITIVE_REF')
    C.need(C.FILES==('__init__.py','contract.py','metadata.py','run.py','geometry.py','source_inverse.py','test_boundaries.py','README.md'),
      'EXACT_ISOLATED_SOURCE8_NO_SHARED_SOURCE_EDITS')
    prior=NATIVE_INVERSE.proof()
    memo=G.ReaderMemo();io,part,records,observations=G.reader_functions(memo)
    for new,original,allowed in ((part,G.ORIGINAL_READER.one_part,{'I'}),(records,G.ORIGINAL_READER.records,{'I','one_part','sqlite_ro'}),
      (observations,G.ORIGINAL_READER.observations,{'records'})):
        C.need(new.__code__ is original.__code__ and new.__defaults__ is original.__defaults__ and new.__closure__ is original.__closure__
          and new.__kwdefaults__ is original.__kwdefaults__ and set(new.__globals__)==set(original.__globals__)
          and all(new.__globals__[k]is original.__globals__[k]for k in original.__globals__ if k not in allowed),
          'ENTIRE_ORIGINAL_READER_CODE_ONLY_PRIVATE_DECLARED_IO_BINDINGS')
    body=G.private_reader_function(G.ORIGINAL_STATISTICS._group_pass,observations=observations)
    C.need(body.__code__ is G.ORIGINAL_STATISTICS._group_pass.__code__ and all(body.__globals__[k]is G.ORIGINAL_STATISTICS._group_pass.__globals__[k]
      for k in body.__globals__ if k!='observations')and run.T.B is run.B and G.MEMO_BYTES==64<<20 and G.MEMO_ENTRIES==65536,
      'ORIGINAL_STATISTICAL_ARITHMETIC_CALIBRATION_OBJECTS_BATCH1_AND_FINITE_64MIB_WORKER_MEMO')
    C.need(G.ORIGINAL_READER.I is run.I and G.ORIGINAL_STATISTICS.I is run.I
      and G.ORIGINAL_READER.sqlite_ro is G.sqlite_ro and G.ORIGINAL_STATISTICS.observations is G.ORIGINAL_READER.observations,
      'OLD_SHARED_READER_AND_STATISTICS_GLOBALS_NOT_PATCHED')
    for original,bindings in ((G.ORIGINAL_STATISTICS.initialize,{'I':io}),
      (G.ORIGINAL_STATISTICS.execute,{'I':io,'dispatch_groups':G.ORIGINAL_STATISTICS.dispatch_groups}),
      (G.ORIGINAL_STATISTICS.dispatch_groups,{'day_group':G.memo_day_group,'PROGRESS_CALLBACK':None})):
        function=G.private_reader_function(original,**bindings)
        C.need(function.__code__ is original.__code__ and function.__defaults__ is original.__defaults__ and function.__closure__ is original.__closure__
          and function.__kwdefaults__ is original.__kwdefaults__ and set(function.__globals__)==set(original.__globals__)
          and all(function.__globals__[k]is original.__globals__[k]for k in original.__globals__ if k not in bindings),
          'PRIVATE_STATISTICS_CODE_ONLY_DECLARED_IO_AND_IMPORTABLE_WORKER_DISPATCH_BINDINGS')
    return {'status':'EXACT_ORIGINAL_NATIVE_D4_MATH_CHILD_AND_RESOURCE_WITH_READONLY_STAGE_ADOPTION_AND_INTEGER_IO',
      'original_native_inverse':prior,'old_shared_globals_patched':False,'old_files_writable':False,
      'selected_job_TEXT_to_INTEGER_current_parent_copy_only':True,'eligibility_job_INTEGER_real_disk_all_original_consumers':True,
      'original_child_code_object_direct':True,'all12_input_double_hash_checks_required':True,'two_numeric_replays_required':True,
      'TSQR_chunk':256,'logical_groups':171,'ordered_left_fold_unchanged':True,'historical_parent_D4_complete_claimed':False,
      'geometry_recalculated':False,'old_typed_parts_copied':False,
      'old_receipt_reference_established_on_CPU_after_Source6':True,'metadata_old_receipt_body_or_SHA_read':False,
      'reader_batch_size1_unchanged':True,'reader_memo_bytes_per_process':G.MEMO_BYTES,'reader_memo_entries_per_process':G.MEMO_ENTRIES,
      'memo_miss_uses_original_query_and_whole_SHA':True,'memo_query_results_are_fresh_copies':True,
      'lookup_FD_frame_checked_before_after_each_group':True,'new_numeric_stream_format':False}
