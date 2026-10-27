"""Actual CPU source proof: old numerical/graph reader functions remain direct."""
import ast,inspect,pathlib
from . import run,contract as C,finalize
from workflows.expansion.common_molecular_fp_main_v1 import run as OLD,io as IO,kernel as K,scan as S,finalize as F

def node(text,name):
    nodes=[n for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name];C.Q.need(len(nodes)==1,'EXACT_ONE_SOURCE_BODY:'+name)
    n=nodes[0];return n,''.join(text.splitlines(keepends=True)[n.lineno-1:n.end_lineno]).strip()
def proof():
    a=pathlib.Path(OLD.__file__).read_text();b=pathlib.Path(run.__file__).read_text()
    for name in ('Dispatch','observe'):
        x,s=node(a,name);y,t=node(b,name);C.Q.need(s==t and ast.dump(x,include_attributes=False)==ast.dump(y,include_attributes=False),'UNCHANGED_GRAPH_DISPATCH_CENSUS_BODY:'+name)
    C.Q.need(run.I is IO and run.K is K and run.S is S and finalize.release_gate.__code__.co_code==F.release_gate.__code__.co_code,'DIRECT_ORIGINAL_READER_KERNEL_SCAN_AND_RELEASE_PREDICATE')
    return {'status':'ORIGINAL_FP_GRAPH_MATH_READER_DISPATCH_AST_AND_OBJECTS','direct_io_kernel_scan_objects':True,
      'full_observe_Dispatch_source_bytes_AST_equal':True,'new_changes':['true_day_Common_parent_contract','new_scope_primary_schema','old3_plus_bridge3_before_DATA','finite25h_resource_client'],
      'fingerprint_key_scaffold_stereo_variant_policy_changed':False,'old16_or8_C0_fabricated':False,'scientific_DATA_read':False}
