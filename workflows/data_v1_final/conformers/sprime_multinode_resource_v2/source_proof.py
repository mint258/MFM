"""CPU source-only exact inverse bytes and AST;never execute copied source."""
import ast,hashlib,json
from . import contract as C
def region(text,start=None,end=None):
    if start is None:return text
    C.need(text.count(start)==1 and text.count(end)==1,'UNIQUE_INVERSE_SOURCE_REGION_ANCHORS')
    a=text.index(start);return text[a:text.index(end,a)]
def verify():
    for name in C.FILES:
        if name.endswith('.py'):ast.parse((C.HERE/name).read_bytes().decode(),filename=str(C.HERE/name))
    m=json.loads((C.HERE/'adaptation_manifest.json').read_text());C.need(m['schema']=='SPRIME_MULTINODE_EXPLICIT_RESOURCE_SOURCE_INVERSE_V2'
        and m['scientific_sources_copied_or_changed'] is False,'DECLARED_RESOURCE_SOURCE_MANIFEST')
    rows=[]
    for row in m['files']:
        original=C.pinned(row['origin'],2<<20).read_bytes();text=original.decode();before=region(text,row.get('origin_start'),row.get('origin_end'))
        actual=region((C.HERE/row['target']).read_bytes().decode(),row.get('target_start'),row.get('target_end'));expected=before
        for edit in row['edits']:
            C.need(expected.count(edit['old'])==edit['count'],'EXACT_DECLARED_FORWARD_RESOURCE_EDIT_COUNT');expected=expected.replace(edit['old'],edit['new'])
        C.need(actual==expected,'NO_UNDECLARED_SOURCE_REGION_DIFFERENCES');restored=actual
        for edit in reversed(row['edits']):
            C.need(restored.count(edit['new'])==edit['count'],'EXACT_DECLARED_REVERSE_RESOURCE_EDIT_COUNT');restored=restored.replace(edit['new'],edit['old'])
        C.need(restored==before,'RESOURCE_INVERSE_EXACT_ORIGINAL_REGION_BYTES')
        whole=text.replace(before,restored,1);C.need(whole.encode()==original and ast.dump(ast.parse(whole),include_attributes=False)==ast.dump(ast.parse(text),include_attributes=False),'WHOLE_SOURCE_INVERSE_BYTES_AND_AST')
        rows.append({'target':row['target'],'origin':row['origin'],'inverse_whole_SHA256':hashlib.sha256(whole.encode()).hexdigest()})
    C.need(m['original_science_reference']==C.sources()['science'],'EXACT_UNCOPIED_ORIGINAL_SCIENCE_SOURCE')
    from . import runtime_io as R
    from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import runtime_io as OR
    C.need(R.load_science is OR.load_science and R.read_packet is OR.read_packet,'ORIGINAL_SCIENTIFIC_LOADER_AND_PACKET_READER_OBJECTS')
    compat=ast.parse((C.HERE/'compat32.py').read_text());defs={n.name:n for n in compat.body if isinstance(n,ast.FunctionDef)}
    def calls(function,owner,name):
        return [n for n in ast.walk(defs[function]) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
            and isinstance(n.func.value,ast.Name) and n.func.value.id==owner and n.func.attr==name]
    C.need(len(calls('initialize','R','load_science'))==1 and not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
        and n.func.attr=='worker_init' for n in ast.walk(defs['initialize'])),'ONE_ORIGINAL_LOADER_NO_DUPLICATE_WORKER_INIT')
    C.need(len(calls('one','RUNNER','run_one'))==1 and not calls('one','SCIENCE','process_task'),'EXACT_ORIGINAL_RUN_ONE_NOT_REIMPLEMENTED')
    return {'inverse_bytes_and_AST_equal':True,'scientific_source_modified':False,'rows':rows,'compat_runner_direct_once_and_no_double_init_source_checked':True,'synthetic_multiworker_IO_requires_actual_Source3':True}
