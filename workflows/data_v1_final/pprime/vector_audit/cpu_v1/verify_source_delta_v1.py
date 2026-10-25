"""Stdlib-only exact declared-edit and scientific-function AST proof; no execution."""
from __future__ import annotations
import argparse,ast,copy,hashlib,json,pathlib


def sha(raw):return hashlib.sha256(raw).hexdigest()
def dump(node):return ast.dump(node,annotate_fields=True,include_attributes=False)
def expression(text):return ast.parse(text).body[0].value
BARRIER=ast.parse("if not getattr(render_state, 'seen', False):\n    render_state.seen = True\n    render_barrier.wait(timeout=180)\n").body[0]
EXTRA={'render_worker_pid':expression('os.getpid()'),'render_worker_tid':expression('threading.get_native_id()')}

class OnlyDeclaredScienceControls(ast.NodeTransformer):
    def visit_Expr(self,node):
        call=node.value
        if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name) and call.func.value.id=='cpu_runtime' and call.func.attr=='checkpoint':
            if call.args or call.keywords:raise ValueError('CHECKPOINT_MUST_HAVE_NO_ARGUMENTS')
            return None
        return self.generic_visit(node)
    def visit_Call(self,node):
        node=self.generic_visit(node)
        if isinstance(node.func,ast.Name) and node.func.id=='checkpoint_iter':
            if len(node.args)!=1 or node.keywords:raise ValueError('ONLY_DIRECT_ITERABLE_CONTROL_ALLOWED')
            return node.args[0]
        if isinstance(node.func,ast.Name) and node.func.id=='dict':
            keep=[]
            for kw in node.keywords:
                if kw.arg in EXTRA:
                    if dump(kw.value)!=dump(EXTRA[kw.arg]):raise ValueError('UNKNOWN_RENDER_METADATA_VALUE')
                else:keep.append(kw)
            node.keywords=keep
        return node
    def visit_If(self,node):
        if dump(node)==dump(BARRIER):return None
        return self.generic_visit(node)


def verify(directory):
    directory=pathlib.Path(directory)
    mapping=json.loads((directory/'edits_v1.json').read_text())
    pin=mapping['baseline'];old_raw=pathlib.Path(pin['path']).read_bytes()
    if len(old_raw)!=pin['bytes'] or sha(old_raw)!=pin['sha256']:raise ValueError('ORIGINAL_SOURCE_CHANGED')
    new_raw=(directory/mapping['candidate_relative_path']).read_bytes()
    old,new=old_raw.decode(),new_raw.decode();forward=old
    for e in mapping['edits']:
        if not e['old'] or not e['new'] or forward.count(e['old'])!=e['occurrences']:raise ValueError('DECLARED_FORWARD_EDIT_ANCHOR_DIFFERS:'+e['reason'])
        forward=forward.replace(e['old'],e['new'])
    if forward.encode()!=new_raw:raise ValueError('CANDIDATE_HAS_UNDECLARED_EDIT')
    reverse=new
    for e in reversed(mapping['edits']):
        if reverse.count(e['new'])!=e['occurrences']:raise ValueError('DECLARED_REVERSE_EDIT_ANCHOR_DIFFERS:'+e['reason'])
        reverse=reverse.replace(e['new'],e['old'])
    if reverse.encode()!=old_raw:raise ValueError('INVERSE_FULL_FILE_BYTES_DIFFER')
    old_tree,new_tree=ast.parse(old),ast.parse(new)
    old_fn={n.name:n for n in ast.walk(old_tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    new_fn={n.name:n for n in ast.walk(new_tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    rows=[]
    for name in mapping['science_functions']:
        n=OnlyDeclaredScienceControls().visit(copy.deepcopy(new_fn[name]))
        if dump(n)!=dump(old_fn[name]):raise ValueError('SCIENTIFIC_FUNCTION_AST_DIFFERS:'+name)
        rows.append({'name':name,'original_source_bytes_identical':ast.get_source_segment(old,old_fn[name])==ast.get_source_segment(new,new_fn[name]),'AST_identical_after_only_declared_checkpoint_barrier_thread_metadata_removal':True})
    return {'schema':'VECTOR_PREPARE_CPU_SOURCE_EQUIVALENCE_V1','status':'PASS','baseline_reference':pin,'candidate_reference':{'path':str((directory/mapping['candidate_relative_path']).absolute()),'bytes':len(new_raw),'sha256':sha(new_raw)},'forward_declared_edit_bytes_equal':True,'inverse_full_file_bytes_equal':True,'science_functions':rows,'scientific_modules_imported':[],'scientific_functions_executed':False,'data_bodies_read':False,'limits':'New control helpers are separately reviewed and tested; this proves source equivalence, not prepared inputs or coordinate-frame acceptance.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=pathlib.Path,default=pathlib.Path(__file__).parent);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();result=verify(a.directory)
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result))
if __name__=='__main__':main()
