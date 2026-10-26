"""Stdlib source-only proof: unchanged scan/math and original six test bodies."""
from __future__ import annotations
import argparse,ast,hashlib,json
from pathlib import Path

def pin(path):
    raw=path.read_bytes()
    if len(raw)>2<<20:raise ValueError('SMALL_SOURCE_ONLY')
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def function(source,name):
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name)
    return node,''.join(source.splitlines(keepends=True)[node.lineno-1:node.end_lineno])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--main-repository',type=Path,required=True)
    p.add_argument('--alpha-source-directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    original=a.main_repository/'workflows/data_v1_final/labels/payload_audit_v1';alpha=a.alpha_source_directory
    before=(original/'run.py').read_text();after=(alpha/'run.py').read_text();checks=[]
    for name in ('init_worker','source_columns','json_safe','bounded_worst','run_group'):
        old_node,old=function(before,name);new_node,new=function(after,name)
        if old!=new or ast.dump(old_node,include_attributes=False)!=ast.dump(new_node,include_attributes=False):raise ValueError('SCIENCE_SCAN_FUNCTION_CHANGED:'+name)
        checks.append({'function':name,'full_source_bytes_equal':True,'AST_equal':True})
    old_node,old_gate=function(before,'pre_scan_fixture_gate');new_node,new_gate=function(after,'pre_scan_fixture_gate')
    inverse=new_gate.replace("expected_path=FROZEN/'workflows/data_v1_final/labels/payload_audit_v1/test_payload.py'","expected_path=Path(__file__).absolute().with_name('test_payload.py')")
    inverse=inverse.replace("source=small_ref(expected_path);request=load(load(proof_path)['plan_reference']['path'])","source=small_ref(expected_path);request=load(proof_path)['request']")
    if inverse!=old_gate:raise ValueError('ORIGINAL_SIX_FIXTURE_GATE_MATH_OR_LOGIC_CHANGED')
    if (original/'payload.py').read_bytes()!=(alpha/'payload.py').read_bytes():raise ValueError('PAYLOAD_NUMERIC_MASK_OR_SHAPE_KERNEL_CHANGED')
    result={'schema':'ALPHA_LABEL_PAYLOAD512_SOURCE_PORT_EQUIVALENCE_V1','status':'PASS','science_functions':checks,
      'fixture_gate_inverse_only_two_endpoint_locator_edits':True,'numeric_mask_shape_kernel_byte_equal':True,
      'original_six_test_reference':pin(original/'test_payload.py'),'original_kernel_reference':pin(original/'payload.py'),
      'original_run_reference':pin(original/'run.py'),'alpha_kernel_reference':pin(alpha/'payload.py'),'alpha_run_reference':pin(alpha/'run.py'),
      'other_changes':['independent Alpha startup guard','exact per-file IO relocation helpers','Alpha observer output paths','in-allocation body hash before scan','plan CLI and output endpoint metadata'],
      'scientific_test_or_data_body_executed':False,'AST_science_equivalence_is_not_actual_Arrow17_data_acceptance':True}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps({'status':result['status'],'science_functions':len(checks)}))
if __name__=='__main__':main()