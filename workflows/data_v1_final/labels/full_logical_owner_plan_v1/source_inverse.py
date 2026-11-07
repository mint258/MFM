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
    return {'status':'ORIGINAL_GROUP_FILE_ORDER_AST_AND_DIRECT_OWNER_OBJECTS','original_source':str(oldpath),
      'grouping_math_changed':False,'physical_part_QR_groups_created':False,'new_numeric_functions_copied':False,'DATA_read':False}
