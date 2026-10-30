"""CPU source witnesses: original statistics unchanged, native direct IO only."""
import ast,hashlib,json
from pathlib import Path
from . import contract as C,geometry as G
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import run as ORIGINAL,bindings as B,source_inverse as OLD_INVERSE
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1.source_inverse import function_source
ORIGINAL_RUN=json.loads(r'''{"path":"/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/labels/existing_sprime_pilot_day_v1/run.py","bytes":14148,"sha256":"e63b71a26ce16192deafac394a19d8fc1544e6ed499189a073519b06c8d9cf7c"}''')

def proof():
    raw=Path(ORIGINAL_RUN['path']).read_bytes()
    C.need(len(raw)==ORIGINAL_RUN['bytes'] and hashlib.sha256(raw).hexdigest()==ORIGINAL_RUN['sha256'],'FROZEN_OLD_COMPLETE_D4_RUN_SOURCE_BYTES')
    old=raw.decode();current=(C.HERE/'run.py').read_bytes().decode()
    for name in ('references','numeric_state','next_route','canonical_numeric','K_bytes'):
        C.need(function_source(old,name)==function_source(current,name),'ENTIRE_ORIGINAL_STATISTICS_SUPPORT_BYTES_AST:'+name)
    expected=old.replace('prefix_ref,prefix,old,oldproof=I.discover_prefix(plan)','prefix_ref,prefix,old,oldproof=G.prepare(plan,proof,root,budget)')
    expected=expected.replace('pre,members,diagnostic=V.cohort(prefix,old)','pre,members,diagnostic=G.cohort(prefix,old)')
    expected=expected.replace('EXISTING_COMPLETE_SPRIME_PILOT_DAY_RECEIPT_V1','EXISTING_SPRIME_NATIVE_PILOT_DAY_RECEIPT_V1')
    expected=expected.replace('PROVISIONAL55K_GEOMETRY_D5_ANTI_JOIN_AND_TRAIN_D4_STATISTICS_COMPLETE_PENDING_ACTUAL_C0_ROOT_SEAL','PROVISIONAL55K_NATIVE_RANDOM_GEOMETRY_ANTI_JOIN_AND_TRAIN_D4_COMPLETE_PENDING_ACTUAL_C0_ROOT_SEAL')
    expected=expected.replace('ACTUAL_SAME_PARENT_BOUNDED_GEOMETRY_ROLE_ORDER_CLOSED_PENDING_ROOT_NOT_FINAL_COMMON','ACTUAL_SAME_PARENT_NATIVE_GEOMETRY_ROLE_RANDOM_ORDER_CLOSED_PENDING_ROOT_NOT_FINAL_COMMON')
    expected=expected.replace('    try:\n        prefix_ref,prefix,old,oldproof=G.prepare','    try:\n        G.schema_header(plan,proof,root)\n        prefix_ref,prefix,old,oldproof=G.prepare')
    expected=expected.replace("'fixture_gate':gate,'checkpoint_reference':latest","'schema_only_header_reference':I.pin(root/'field_schema_only_header.json') if (root/'field_schema_only_header.json').exists() else None,'fixture_gate':gate,'checkpoint_reference':latest")
    expected=expected.replace("'full_Common_D2_D3_D4_D5_D6_release':False,'Model_joint_ACK_claimed':False","'available_orders':['fixed_random'],'full_three_order':False,'D7':False,'full_Common_D2_D3_D4_D5_D6_release':False,'Model_joint_ACK_claimed':False")
    expected=expected.replace("'ordinary_old_complete_Sprime_mother_only':True,","'available_orders':['fixed_random'],'full_three_order':False,'D7':False,'ordinary_old_complete_Sprime_mother_only':True,")
    C.need(function_source(current,'execute')==function_source(expected,'execute'),'WHOLE_EXECUTE_ONLY_NATIVE_SOURCE_HEAD_AND_SCHEMA_QA_AND_TRUTHFUL_LINEAGE_DELTA')
    # R5 only changes main's Budget binding; original execute/statistics remain exact.
    before=current.replace('budget=G.ResourceBudget(plan,proof,root)','budget=I.Budget(plan,proof,root)').encode()
    C.need(len(before)==15750 and hashlib.sha256(before).hexdigest()=='67f8f040d0285f8586d2c5523660d3d1d4d40914c41cbad15c97c67e5c2fbb38',
      'ENTIRE_R4_NATIVE_RUN_BYTES_INVERSE_ONE_RESOURCE_BUDGET_BINDING')
    geometry=(C.HERE/'geometry.py').read_bytes();marker=b'\n# NATIVE_RESOURCE_CENSUS_R5:'
    C.need(geometry.count(marker)==1,'ONE_EXPLICIT_R5_RESOURCE_APPEND')
    prefix=geometry.split(marker)[0]
    C.need(len(prefix)==21746 and hashlib.sha256(prefix).hexdigest()=='289aa519b64db9f6390634dfba7d0dee39172970f88c8636f3cf19b196ba1d26',
      'ENTIRE_R4_NATIVE_GEOMETRY_BYTES_UNCHANGED_RESOURCE_APPEND_ONLY')
    import inspect,textwrap
    for name,keys in (('_observe',{'unique_bytes','R'}),('check',{'unique_bytes'})):
        method=G.budget_function(name,lambda path:0);original=getattr(G.I.Budget,name)
        C.need(method.__code__ is original.__code__ and method.__defaults__ is original.__defaults__
          and method.__closure__ is original.__closure__ and method.__kwdefaults__ is original.__kwdefaults__,
          'EXACT_ORIGINAL_BUDGET_METHOD_CODE_DEFAULTS_CLOSURE:'+name)
        C.need(set(method.__globals__)==set(original.__globals__) and
          all(method.__globals__[key]is original.__globals__[key]for key in original.__globals__ if key not in keys),
          'PRIVATE_RESOURCE_METHOD_GLOBALS_ONLY_DECLARED_CENSUS_STOP_DETAIL:'+name)
        if name=='_observe':C.need(method.__globals__['R'].original is original.__globals__['R'],'ORIGINAL_STOP_OBJECT_NO_GLOBAL_PATCH')
        old_source=inspect.getsource(original);C.need(ast.dump(ast.parse(textwrap.dedent(old_source)))==ast.dump(ast.parse(textwrap.dedent(inspect.getsource(method)))),
          'ENTIRE_ORIGINAL_BUDGET_METHOD_AST_UNCHANGED:'+name)
    C.need(G.ResourceBudget.__bases__==(G.I.Budget,) and G.ResourceBudget.__init__.__globals__['I'] is G.I,
      'DIRECT_ORIGINAL_BUDGET_INIT_OBSERVER_QUOTA_AND_IMMUTABLE_REFERENCES')
    from . import run
    C.need(run.T is ORIGINAL.T and run.B is ORIGINAL.B and run.V is G.COVERAGE and run.ORIGINAL_COVERAGE is ORIGINAL.V and run.E is ORIGINAL.E and run.L is ORIGINAL.L and run.I is ORIGINAL.I,
      'DIRECT_UNCHANGED_STATISTICS_TYPED_COVERAGE_MASK_ELIGIBILITY_AND_R674_OBJECTS')
    adapted=G.coverage_function({},{});old=ORIGINAL.V.build
    C.need(adapted.__code__ is old.__code__ and adapted.__defaults__ is old.__defaults__ and adapted.__closure__ is old.__closure__,
      'EXACT_OLD_COVERAGE_BUILD_CODE_OBJECT_DEFAULTS_CLOSURE')
    C.need(set(adapted.__globals__)==set(old.__globals__) and all(adapted.__globals__[k]is old.__globals__[k]for k in old.__globals__ if k!='I')
      and isinstance(adapted.__globals__['I'],G.AcceptedConfigIO) and adapted.__globals__['I'].original is run.I,
      'PRIVATE_GLOBALS_COPY_ONLY_I_READONLY_CONFIG_PROXY_NO_OLD_GLOBAL_PATCH')
    C.need(adapted.__globals__['I'].require is run.I.require and adapted.__globals__['I'].allow is run.I.allow,
      'ALL_OTHER_IO_ATTRIBUTES_ARE_EXACT_ORIGINAL_OBJECTS')
    C.need(G.metadata_children is G.OLD.metadata_children and G.WORKER is G.P.WORKER and G.WORKER.d7 is G.OLD.OriginalWorker.d7,
      'DIRECT_ORIGINAL_INPUT_RENDERER_REAL_GENERAL_CONTEXT_NO_OLD_GLOBAL_PATCH')
    tree=ast.parse((C.HERE/'geometry.py').read_bytes())
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
            C.need(node.func.attr not in ('d7','rmsd','pm7_compute','geometry_orders_hof','project_remaining'),'NO_D7_RMSD_HOF_CACHE_MATH_CALLED_IN_NATIVE_GEOMETRY')
    B.verify();prior=OLD_INVERSE.proof();worker=G.WORKER.proof()
    from workflows.data_v1_final.export.bounded_old_complete_d5_day_v1 import source_inverse as D5
    native=D5.proof()
    return {'status':'EXACT_ORIGINAL_D4_STATISTICS_WITH_EXPLICIT_NATIVE_GEOMETRY_SOURCE_HEAD',
      'coverage_IO_seam':'EXACT_OLD_BUILD_CODE_ONLY_PRIVATE_I_CONFIG_VIEW',
      'resource_IO_seam':'EXACT_ORIGINAL_BUDGET_METHODS_BOUNDED_WHOLE_CENSUS_MAX3_FNF_ONLY_AND_ACTUAL_STOP_TRACE',
      'historical177_cause':'UNKNOWN_NO_PATH_OR_TRACE_PRESERVED',
      'old_D4_inverse':prior,'native_reader_and_stereo_inverse':native,'worker_context_inverse':worker,
      'TSQR_chunk':256,'logical_groups':171,'ordered_left_fold_unchanged':True,'two_numeric_replays_required':True,
      'HOF_RMSD_D7_or_QM_UFF_called_by_source_proof':False,'old_scientific_globals_patched':False,'Source_only_header_not_Native_unit_verification':True}
