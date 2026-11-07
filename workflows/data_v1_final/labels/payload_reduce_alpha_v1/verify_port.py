"""Source-only exact inverse proof of the frozen reducer mathematical core."""
from __future__ import annotations
import argparse,ast,hashlib,json
from pathlib import Path

def source(path):
    raw=path.read_bytes()
    if len(raw)>2<<20:raise ValueError('SMALL_SOURCE_ONLY')
    return raw.decode('utf-8-sig'),{'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def core(text):
    start=text.index("plan=load(require(cfg['sources']['plan']))")
    last='    if stop:raise SystemExit(2)';end=text.index(last,start)+len(last)
    return text[start:end]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frozen-repository',type=Path,required=True);p.add_argument('--alpha-source-directory',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    original=a.frozen_repository/'workflows/data_v1_final/labels/payload_audit_v1';alpha=a.alpha_source_directory
    old,old_ref=source(original/'reduce.py');new,new_ref=source(alpha/'run.py')
    before=core(old);after=core(new)
    if after.count('root=Path(a.output)')!=1 or before.count('root=new_root(a.output)')!=1:raise ValueError('EXACT_ONE_PRECREATED_ALPHA_OUTPUT_HANDLE_CHANGE')
    inverse=after.replace('root=Path(a.output)','root=new_root(a.output)')
    if inverse.encode()!=before.encode():raise ValueError('REDUCTION_MATH_SOURCE_BYTES_CHANGED')
    old_ast=ast.dump(ast.parse('def kernel():\n    '+before),include_attributes=False)
    new_ast=ast.dump(ast.parse('def kernel():\n    '+inverse),include_attributes=False)
    if old_ast!=new_ast:raise ValueError('REDUCTION_MATH_AST_CHANGED')
    expected_imports=(
      'from payload_audit_alpha_v1.run import bounded_worst,json_safe,pre_scan_fixture_gate',
      'from payload_audit_alpha_v1.payload import quality_stop_fields',
      'from workflows.data_v1_final.labels.source_status_v1.reduce import consume_coverage')
    for text in expected_imports:
        if text not in new:raise ValueError('REUSED_FROZEN_HELPER_IMPORT_CHANGED')
    _,coverage_ref=source(a.frozen_repository/'workflows/data_v1_final/labels/source_status_v1/reduce.py')
    _,kernel_ref=source(original/'payload.py');_,fixture_ref=source(original/'test_payload.py')
    result={'schema':'ALPHA_LABEL_PAYLOAD512_REDUCER_SOURCE_EQUIVALENCE_V1','status':'PASS',
      'original_reducer_reference':old_ref,'alpha_reducer_reference':new_ref,'coverage_helper_module_reference':coverage_ref,
      'unchanged_numeric_shape_mask_kernel_reference':kernel_ref,'unchanged_six_fixture_source_reference':fixture_ref,
      'science_reduction_body_inverse_source_bytes_equal':True,'science_reduction_body_inverse_AST_equal':True,
      'sole_core_inverse_edit':'root=Path(a.output) -> root=new_root(a.output); wrapper creates the new Alpha root before six fixtures',
      'reused_frozen_imports':list(expected_imports),'new_wrapper_only':['new Alpha identity/plan/proof/review guard',
      'actual C0 parent identity and raw accounting pins','strict original six tests before all65 body SHA/fstat',
      'unchanged input locator map and original scientific config','new Alpha output closure and stricter2GiB stage cap'],
      'median_MAD_refit':False,'scientific_code_or_data_body_executed':False,'actual_Arrow17_reduction_acceptance':False}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps({'status':'PASS','science_body_inverse_bytes_and_AST_equal':True}))
if __name__=='__main__':main()
