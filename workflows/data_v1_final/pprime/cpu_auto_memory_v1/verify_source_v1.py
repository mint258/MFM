"""Declared full-file inverse bytes/AST proof, no science or tests executed."""
import argparse,ast,hashlib,json,os,pathlib
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
REPO=ROOT/'repository';PPRIME=REPO/'workflows/data_v1_final/pprime';HERE=PPRIME/'cpu_auto_memory_v1'

def need(ok,message):
    if not ok:raise ValueError(message)

def read(path):
    need(path.is_file() and path.is_absolute() and not path.is_symlink(),'SMALL_LITERAL_SOURCE_REQUIRED')
    with path.open('rb') as f:
        a=os.fstat(f.fileno());need(a.st_size<=2*1024**2 and a.st_uid==1278,'SMALL_SOURCE_OWNER_LIMIT')
        raw=f.read(2*1024**2+1);b=os.fstat(f.fileno())
    need(len(raw)==a.st_size and (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'SOURCE_CHANGED')
    return raw

def ref(path,raw=None):
    raw=read(path) if raw is None else raw
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def prove_edit_map(before,after,edits):
    expected=before
    for edit in edits:
        old,new=edit['old'].encode(),edit['new'].encode()
        need(old and new and expected.count(old)==1,'UNIQUE_DECLARED_EDIT_REQUIRED')
        expected=expected.replace(old,new)
    need(expected==after,'UNDECLARED_SOURCE_EDIT_REJECTED')
    inverse=after
    for edit in reversed(edits):
        old,new=edit['old'].encode(),edit['new'].encode()
        need(inverse.count(new)==1,'UNIQUE_INVERSE_EDIT_REQUIRED');inverse=inverse.replace(new,old)
    need(inverse==before and ast.dump(ast.parse(inverse),include_attributes=False)==ast.dump(ast.parse(before),include_attributes=False),
        'FULL_INVERSE_BYTES_OR_AST_DIFFERS')
    return {'declared_text_edit_count':len(edits),'inverse_full_file_bytes_equal':True,'inverse_normalized_AST_equal':True}

def function_segment(raw,name):
    tree=ast.parse(raw)
    selected=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==name]
    need(len(selected)==1,'EXACT_ORIGINAL_SCIENTIFIC_FUNCTION_REQUIRED')
    node=selected[0]
    return ast.get_source_segment(raw.decode(),node).encode(),ast.dump(node,include_attributes=False)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
    need(pathlib.Path(__file__).absolute()==HERE/'verify_source_v1.py' and ROOT/'control' in a.output.parents and not a.output.exists(),'ROOT_NEW_SOURCE_PROOF_REQUIRED')
    manifest_path=HERE/'source_edits_v1.json';manifest=json.loads(read(manifest_path));rows=[]
    for item in manifest['variants']:
        old=PPRIME/item['old_relative'];new=HERE/item['new_name'];before,after=read(old),read(new)
        result=prove_edit_map(before,after,item['edits'])
        if item['new_name']=='run_frame_v1.py':
            left,left_ast=function_segment(before,'execute_case');right,right_ast=function_segment(after,'execute_case')
            need(left==right and left_ast==right_ast,'FRAME_EXECUTE_CASE_SCIENCE_CHANGED')
            result.update(execute_case_full_bytes_equal=True,execute_case_AST_equal=True)
        rows.append(dict(result,original_source=ref(old,before),variant_source=ref(new,after),declared_edit_names=[e['name'] for e in item['edits']]))
    policy=PPRIME/'retention_v1/retention_policy_v1.py';selector=PPRIME/'raw_policy_proposal_v1/policy_v1.py'
    result={'schema':'PPRIME_CPU_AUTO_MEMORY_SOURCE_EQUIVALENCE_V1','status':'PASS_DECLARED_RESOURCE_DISPATCH_EDITS_ONLY_NOT_SCIENTIFIC_ACCEPTANCE',
        'rows':rows,'edit_manifest':ref(manifest_path),'proof_source':ref(pathlib.Path(__file__).absolute()),
        'unchanged_retention_policy_source':ref(policy),'unchanged_stable_selector_source':ref(selector),
        'unchanged_frame_evaluator_source':ref(PPRIME/'vector_audit/evaluate_v1.py'),
        'new_memory_and_scheduler_sources':[ref(HERE/name) for name in ('controls.py','memory.py')],
        'resource_policy':'SLURM_DEFAULT_UNSPECIFIED','old_sources_or_results_modified':False,
        'science_or_tests_executed':False,'wrapper_AST_claimed_equal_to_old_main':False,
        'limits':'Whole-file inverse proof declares startup/import/CLI/bounded-dispatch/closure edits. Original execute_case and retention selection/union/parquet body unchanged; actual new-policy execution and actual frame/retention gates remain required.'}
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({'status':result['status'],'proof':ref(a.output),'variants':len(rows)}))
if __name__=='__main__':main()
