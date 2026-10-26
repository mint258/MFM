"""Exact source inverse, small authorization and pre-body fixture receipt."""
from __future__ import annotations
import ast,pathlib,unittest
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as C,runtime_io as R
from workflows.data_v1_final.conformers.formal_cpu_auto_prepare_mapping_v1 import mapping as M

HERE=pathlib.Path(__file__).absolute().parent
ORIGINAL=C.HERE/'finalize.py'
ORIGINAL_SHA='4363462a918a55401c9d176d0cf7f5f7bc71a7daebd0e89c7ebfcf704e03e439'
RUNTIME_SHA='be42f5033ee3fd9fe95da09e8b8efb8ca1dedb711a3766049380b0ed5d7ea300'
FILES=('__init__.py','adapter.py','finalize.py','test_adapter.py','README.md')
UNCHANGED=('normalize_package','merge_counts','membership','exclusion_gates','scaffold_chunk')


def edits():
    return (
        ('from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as C,runtime_io as R',
         'from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as C,runtime_io as R\n'
         'from workflows.data_v1_final.conformers.formal_cpu_auto_prepare_mapping_v1 import mapping as M\n'
         'from workflows.data_v1_final.conformers.formal_cpu_auto_finalize_mapping_v2 import adapter as A'),
        ('formal=formal_source(value)','formal=M.formal_source(value,proof,args.source_mapping_review)'),
        ('    import duckdb\n','    C.pinned(value["per_molecule"]) # fresh CPU whole-SHA; numeric algorithms unchanged\n    import duckdb\n'),
        ("'quota-reuse-review','descriptor'","'quota-reuse-review','source-mapping-review','descriptor'"),
        ("required=name in {'config','root-preflight','quota-reuse-review','output'}",
         "required=name in {'config','root-preflight','quota-reuse-review','source-mapping-review','output'}"),
        ("args.mode,OPTIONS)\n","args.mode,OPTIONS)\n    A.authorize(proof,args.source_mapping_review)\n"),
        ("    try:\n        if args.mode=='close':","    try:\n        A.preflight(proof,args.source_mapping_review)\n        if args.mode=='close':"),
    )


def transform(text):
    for before,after in edits():
        C.need(text.count(before)==1,'EXACT_SINGLE_FINALIZER_SOURCE_EDIT_REQUIRED:'+before);text=text.replace(before,after)
    return text


def inverse(text):
    for before,after in reversed(edits()):
        C.need(text.count(after)==1,'EXACT_SINGLE_INVERSE_FINALIZER_SOURCE_EDIT_REQUIRED:'+after);text=text.replace(after,before)
    return text


def import_bindings(text):
    """Inspect actual AST, never execute/import DuckDB or Arrow for this proof.

    Literal inverses alone do not prove that a generated import survived a
    line comment. Require all three original imports as direct statements in
    finalize_common, with their actual binding names preceding each use.
    """
    tree=ast.parse(text)
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='finalize_common']
    C.need(len(functions)==1,'IMPORT_BINDING_EXACT_FINALIZE_FUNCTION_REQUIRED')
    fn=functions[0];expected={'duckdb':('duckdb',None),'pa':('pyarrow','pa'),'pq':('pyarrow.parquet','pq')}
    result={}
    for binding,(module,alias) in expected.items():
        matches=[node for node in fn.body if isinstance(node,ast.Import)
            and any(item.name==module and item.asname==alias for item in node.names)]
        C.need(len(matches)==1,'ACTUAL_DIRECT_IMPORT_BINDING_REQUIRED:'+binding)
        uses=[n.lineno for n in ast.walk(fn) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load) and n.id==binding]
        C.need(uses and matches[0].end_lineno<min(uses),'DIRECT_IMPORT_MUST_PRECEDE_ACTUAL_NAME_USE:'+binding)
        C.need(not any(isinstance(n,ast.Name) and isinstance(n.ctx,(ast.Store,ast.Del)) and n.id==binding
            for n in ast.walk(fn)),'ORIGINAL_IMPORT_BINDING_MUST_NOT_BE_SHADOWED:'+binding)
        result[binding]={'module':module,'asname':alias,'import_lineno':matches[0].lineno,'first_use_lineno':min(uses)}
    return result


def verify_texts(before,after):
    old_imports,new_imports=import_bindings(before),import_bindings(after)
    C.need({k:(v['module'],v['asname']) for k,v in old_imports.items()}==
        {k:(v['module'],v['asname']) for k,v in new_imports.items()},'ORIGINAL_EXECUTABLE_IMPORT_BINDINGS_CHANGED')
    C.need(transform(before)==after and inverse(after)==before,'ONLY_ENUMERATED_FINALIZER_ENTRY_EDITS_ALLOWED')
    def functions(text):return {n.name:n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
    def body(text,node):return ''.join(text.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
    a,b=functions(before),functions(after)
    for name in UNCHANGED:
        C.need(body(before,a[name])==body(after,b[name]) and ast.dump(a[name],include_attributes=False)==ast.dump(b[name],include_attributes=False),
            'ORIGINAL_FINALIZER_SCIENTIFIC_OR_QUALITY_FUNCTION_CHANGED:'+name)
    # Reversing the mount call and removing the added pre-read whole-SHA guard
    # restores the entire merge/exclusion/scaffold/SQL/physical/int64 body.
    restored=body(after,b['finalize_common']).replace('formal=M.formal_source(value,proof,args.source_mapping_review)','formal=formal_source(value)')
    restored=restored.replace('    C.pinned(value["per_molecule"]) # fresh CPU whole-SHA; numeric algorithms unchanged\n','')
    C.need(restored==body(before,a['finalize_common']) and ast.dump(ast.parse(restored).body[0],include_attributes=False)==ast.dump(a['finalize_common'],include_attributes=False),
        'FINALIZATION_BODY_CHANGED_BEYOND_MOUNT_AND_INPUT_SHA_GUARD')
    return {'status':'EXACT_SOURCE_INVERSE_AND_SCIENCE_AST_EQUAL','unchanged_function_names':list(UNCHANGED),
        'finalize_common_inverse_body_equal':True,'entire_file_inverse_equal':True,'IO_R_IO_binding_unchanged':True,
        'original_actual_import_bindings':old_imports,'new_actual_import_bindings':new_imports,
        'duckdb_pa_pq_direct_executable_imports_before_first_use':True,
        'source_proof_reads_actual_finalize_file_not_only_ideal_transform':True,
        'scientific_quality_thresholds_unchanged':True,'physical_int64_and_sparse_append_algorithms_unchanged':True,
        'fresh_per_molecule_whole_SHA_guard_added':True}


def source_proof():
    C.need(C.ref(ORIGINAL)['sha256']==ORIGINAL_SHA and C.ref(C.HERE/'runtime_io.py')['sha256']==RUNTIME_SHA,
        'EXACT_ORIGINAL_FROZEN_FINALIZER_AND_RUNTIME_BYTES_REQUIRED')
    proof=verify_texts(ORIGINAL.read_bytes().decode(),(HERE/'finalize.py').read_bytes().decode())
    proof.update(original_finalizer_reference=C.ref(ORIGINAL),actual_new_finalizer_reference=C.ref(HERE/'finalize.py'),
        original_runtime_reference=C.ref(C.HERE/'runtime_io.py'),inherited_mapping_reference=C.ref(M.HERE/'mapping.py'))
    return proof


def authorize(proof,review_path):
    own=[C.ref(HERE/name) for name in FILES];mapping=[C.ref(M.HERE/name) for name in ('__init__.py','mapping.py','prepare_batch.py')]
    review_ref=R.input_ref(pathlib.Path(proof['request']['startup_proof_path']),review_path);review=C.read(review_ref)
    refs=[review[k] for k in ('formal_source_receipt','prior_cpu_source_validation','same_storage_mapping','quota_provider_review')]
    # Locators only: the 1.24GB canonical DATA body is hashed by the unchanged
    # actual-CPU mapping helper at its sole original finalization callsite.
    R.authorized(proof,[*own,*mapping,review_ref,*refs,review['canonical_reference']])
    C.need(proof['request']['kind']=='analysis' and proof['request']['node']=='compute-0-13'
        and proof['request']['cpus']==16 and proof['request']['pilot'] is False
        and proof['request']['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED','ONLY_FRESH_ACTUAL_MAIN_CPU16_ANALYSIS_FINALIZER')


def fixtures():
    from .test_adapter import FinalizerBoundaries
    result=unittest.TestResult();unittest.defaultTestLoader.loadTestsFromTestCase(FinalizerBoundaries).run(result)
    ok=result.testsRun==8 and result.wasSuccessful() and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses)
    return {'status':'PASS' if ok else 'FAIL','expected_methods':8,'tests_run':result.testsRun,
        'failures':[{'test':t.id(),'traceback':error} for t,error in result.failures],
        'errors':[{'test':t.id(),'traceback':error} for t,error in result.errors],
        'skips':[str(row) for row in result.skipped],'expected_failures':[str(row) for row in result.expectedFailures],
        'unexpected_successes':[str(row) for row in result.unexpectedSuccesses],
        'scientific_bodies_read_by_fixtures':False,'new_UFF_calls':0,'new_QM_calls':0}


def preflight(proof,review_path):
    authorize(proof,review_path);source=source_proof();source_ref=R.write_json_new(R.OUT/'finalizer_source_inverse_proof.json',source)
    tests=fixtures();tests_ref=R.write_json_new(R.OUT/'finalizer_pure_boundaries.json',tests)
    C.need(tests['status']=='PASS','ALL8_PURE_FINALIZER_BOUNDARIES_REQUIRED_BEFORE_SCIENTIFIC_BODIES')
    R.write_json_new(R.OUT/'finalizer_entry_adaptation.json',{'schema':'SPRIME_FINALIZER_EXACT_MOUNT_ENTRY_ADAPTATION_V2',
        'job_id':str(proof['job_id']),'uid':1278,'node':proof['node'],'startup_proof_reference':R.SESSION['proof_reference'],
        'source_inverse_reference':source_ref,'actual_fixture_reference':tests_ref,
        'source_mapping_review_reference':R.input_ref(pathlib.Path(proof['request']['startup_proof_path']),review_path),
        'actual_new_source_references':[C.ref(HERE/name) for name in FILES],
        'IO_binding':'UNCHANGED_R_IO; geometry_sha delegates to frozen R.common()',
        'scientific_quality_thresholds_unchanged':True,'common_frozen_by_this_preflight':False,
        'physical_int64_frozen_by_this_preflight':False,'new_UFF_calls':0,'new_QM_calls':0})
