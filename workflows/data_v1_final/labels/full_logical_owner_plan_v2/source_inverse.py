"""CPU-only AST checks of the inherited grouping/file-order statements."""
import ast,inspect
from pathlib import Path
from . import contract as C

def dump(node):return ast.dump(node,include_attributes=False)
def assignments(tree,name):return [n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)]
def proof():
    from . import build
    oldpath=C.REPO/'workflows/data_v1_final/labels/streaming_v1/prepare.py';old=ast.parse(oldpath.read_text(encoding='utf-8-sig'))
    new=ast.parse(inspect.getsource(build.base_sources));selected=[]
    main=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    nodes=list(ast.walk(main));a=next(n for n in nodes if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='all_artifacts' for t in n.targets))
    b=next(n for n in nodes if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='base_refs' for t in n.targets))
    loop=next(n for n in nodes if isinstance(n,ast.For) and isinstance(n.iter,ast.Subscript) and isinstance(n.iter.value,ast.Name)
      and n.iter.value.id=='verification' and isinstance(n.iter.slice,ast.Constant) and n.iter.slice.value=='files_verified')
    C.need([dump(a),dump(b),dump(loop)]==[dump(n) for n in new.body[0].body[:-1]],'EXACT_ORIGINAL_BASE_VERIFIED_LIST_ORDER_BODY')
    ours=ast.parse(Path(C.HERE/'contract.py').read_text(encoding='utf-8-sig'))
    for name in ('jobs','source_files'):
        C.need(any(dump(x)==dump(y) for x in assignments(old,name) for y in assignments(ours,name)),'EXACT_ORIGINAL_FULL_'+name.upper()+'_ORDER_EXPRESSION')
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import support as S
    from . import worker
    from workflows.data_v1_final.labels.streaming_v1 import support as old_support
    C.need(build.legacy is old_support.legacy,'DIRECT_FROZEN_LEGACY_IMPORTER')
    projector=ast.parse(inspect.getsource(build.projector));returns=[n for n in ast.walk(projector) if isinstance(n,ast.Return)]
    C.need(len(returns)==1 and dump(returns[0])==dump(ast.parse('return module.catalog_source_files').body[0]),'DIRECT_ORIGINAL_CATALOG_FUNCTION_OBJECT_RETURN')
    C.need(worker.lookup_batch is S.lookup_batch and worker.sqlite_ro is S.sqlite_ro,'DIRECT_ORIGINAL_OWNER_LOOKUP_AND_READONLY_OBJECTS')
    from . import io as I
    from workflows.data_v1_final.labels.normalization_compact_runtime_v2 import runtime as clock_source
    C.need(I.wall_clock is clock_source.wall_clock and I.remaining_wall is clock_source.remaining_wall,'DIRECT_APPROVED_COMPACT_V2_CLOCK_OBJECTS_NO_THIRD_IMPLEMENTATION')
    frozen=C.REPO/'workflows/data_v1_final/labels/full_logical_owner_plan_v1'
    C.need((C.HERE/'worker.py').read_bytes()==(frozen/'worker.py').read_bytes(),'EXACT_ORIGINAL_FULL_PLAN_IDENTITY_WORKER_BYTES')
    current_build=(C.HERE/'build.py').read_text(encoding='utf-8-sig');inverse=current_build.replace('FULL_LOGICAL_OWNER_PLAN_BUILD_RECEIPT_V2','FULL_LOGICAL_OWNER_PLAN_BUILD_RECEIPT_V1')
    original_build=(frozen/'build.py').read_text(encoding='utf-8-sig')
    C.need(inverse==original_build and dump(ast.parse(inverse))==dump(ast.parse(original_build)),'FULL_BUILD_INVERSE_BYTES_AST_ONLY_RECEIPT_VERSION')
    for filename,names in (('contract.py',('groups','ranges')),('io.py',('opened','data_json'))):
        old_tree=ast.parse((frozen/filename).read_text(encoding='utf-8-sig'));new_tree=ast.parse((C.HERE/filename).read_text(encoding='utf-8-sig'))
        for name in names:
            before=next(n for n in old_tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            after=next(n for n in new_tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
            C.need(dump(before)==dump(after),'EXACT_OLD_PLANNER_READONLY_API_AST:'+name)
    return {'status':'ORIGINAL_GROUP_FILE_ORDER_AST_AND_DIRECT_OWNER_OBJECTS','original_source':str(oldpath),
      'clock_provider':'normalization_compact_runtime_v2.runtime','clock_helpers_direct_objects':True,'original_fullplan_worker_and_inverse_build_bytes_AST':True,
      'grouping_math_changed':False,'physical_part_QR_groups_created':False,'new_numeric_functions_copied':False,'DATA_read':False}
