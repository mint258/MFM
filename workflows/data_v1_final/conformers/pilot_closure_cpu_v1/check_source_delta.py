"""Static AST equivalence proof only; no AST exec, imports of entries, or data IO."""
from __future__ import annotations
import ast
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).parent
OLD=HERE.parent/"pilot_closure_v1/close_pilot.py"
CPU=HERE/"close_pilot_cpu.py"
OLD_SHA="e7c8992c06c305a53c3d706e0335b6a94db752d9053594c7bc0571f3e642907f"


def dump(node):return ast.dump(node,include_attributes=False)


def main():
    raw=OLD.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=OLD_SHA:raise ValueError("OLD_FROZEN_CLOSURE_SOURCE_CHANGED")
    previous=ast.parse(raw);current=ast.parse(CPU.read_bytes())
    a={n.name:n for n in previous.body if isinstance(n,ast.FunctionDef)}
    b={n.name:n for n in current.body if isinstance(n,ast.FunctionDef)}
    names=("require_complete","accounting_from_raw","review_draft","checked_ids","read_package","distribution")
    for name in names:
        if dump(a[name])!=dump(b[name]):raise ValueError("DATA_VALIDATION_FUNCTION_CHANGED:"+name)
    old_guards=[]
    for node in a["main"].body:
        if isinstance(node,ast.If) and any(isinstance(x,ast.Constant) and x.value=="ROOT_16CPU_NODE20_ANALYSIS_ALLOCATION_REQUIRED" for x in ast.walk(node)):
            old_guards.append(node)
        if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and node.value.func.attr=="require_preflight":
            old_guards.append(node)
    if len(old_guards)!=2:raise ValueError("OLD_GUARD_SHAPE_CHANGED")
    counts={"cpu_guard":0,"cpu_arg":0,"bounded_map":0}
    class Normalize(ast.NodeTransformer):
        def visit_Assign(self,node):
            node=self.generic_visit(node)
            if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=="cpu_admit":
                counts["cpu_guard"]+=1;return copy.deepcopy(old_guards)
            return node
        def visit_Expr(self,node):
            if isinstance(node.value,ast.Call):
                call=node.value
                if isinstance(call.func,ast.Name) and call.func.id=="checkpoint" and not call.args:return None
                if isinstance(call.func,ast.Attribute) and call.func.attr=="add_argument" and call.args and isinstance(call.args[0],ast.Constant) and call.args[0].value=="--cpu-runconfig":
                    counts["cpu_arg"]+=1;return None
            return self.generic_visit(node)
        def visit_Call(self,node):
            node=self.generic_visit(node)
            if isinstance(node.func,ast.Name) and node.func.id=="bounded_map":
                if not isinstance(node.args[0],ast.Name) or node.args[0].id!="pool":raise ValueError("UNKNOWN_BOUNDED_POOL")
                counts["bounded_map"]+=1;node.func=ast.Attribute(value=ast.Name(id="pool",ctx=ast.Load()),attr="map",ctx=ast.Load());node.args=node.args[1:]
            return node
        def visit_Dict(self,node):
            node=self.generic_visit(node);pairs=[]
            for k,v in zip(node.keys,node.values):
                if isinstance(k,ast.Constant) and k.value in {"cpu_runconfig","cpu_guard","execution_variant"}:continue
                pairs.append((k,v))
            node.keys=[k for k,_ in pairs];node.values=[v for _,v in pairs];return node
    normalized=Normalize().visit(copy.deepcopy(b["main"]))
    if counts!={"cpu_guard":1,"cpu_arg":1,"bounded_map":1} or dump(normalized)!=dump(a["main"]):
        raise ValueError("CPU_MAIN_HAS_CHANGES_OUTSIDE_EXPLICIT_GUARD_POOL_CHECKPOINT_PROOF_DELTA")
    print(json.dumps({"status":"STATIC_CPU_DELTA_PROVED","old_source_sha256":OLD_SHA,
        "cpu_source_sha256":hashlib.sha256(CPU.read_bytes()).hexdigest(),
        "unchanged_validation_functions":list(names),"normalized_main_ast_equal":True,
        "only_runtime_guard_pool_checkpoints_and_proof_metadata_differ":True,
        "ast_executed":False,"entry_imported":False,"data_pages_read":False}))


if __name__=="__main__":main()
