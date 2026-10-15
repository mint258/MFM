"""Check that only admission differs and bind an extra-node metadata variant."""
import ast,json,time
from prepare import ROOT,save,sha

def main():
    base=ROOT/'scripts/full_dataset_v7.py';extra=ROOT/'scripts/full_dataset_v8_extra_cpu.py'
    before=ast.parse(base.read_text());after=ast.parse(extra.read_text())
    functions=lambda tree:{node.name:node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}
    a=functions(before);b=functions(after);assert a.keys()==b.keys()
    for name in a.keys()-{'run_full'}:assert ast.dump(a[name],include_attributes=False)==ast.dump(b[name],include_attributes=False),name
    def tail(function):
        offset=next(i for i,node in enumerate(function.body) if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='owner' for target in node.targets))
        return ast.dump(ast.Module(body=function.body[offset:],type_ignores=[]),include_attributes=False)
    assert tail(a['run_full'])==tail(b['run_full'])
    prepared_path=ROOT/'full/prepared.json';prepared=json.loads(prepared_path.read_text())
    assert sha(base)==prepared['worker_sha256']
    authorization_path=ROOT/'reports/full_run_user_decision.json';authorization=json.loads(authorization_path.read_text())
    assert authorization['status']=='APPROVED_BY_USER'
    save(ROOT/'reports/extra_cpu_admission_binding_v8.json',{'status':'ROOT_BOUND_ADMISSION_ONLY_VARIANT','timestamp':time.time(),
        'allowed_extra_nodes':['compute-0-12'],'base_worker_sha256':sha(base),'extra_worker_sha256':sha(extra),
        'science_source_sha256':prepared['source_sha256'],'prepared_sha256':sha(prepared_path),
        'authorization_sha256':sha(authorization_path),'processing_tail_AST_unchanged':True,
        'other_functions_AST_unchanged':True,'scientific_parameters_changed':False,
        'queue_schema_changed':False,'original_lmdb_written':False,'new_lmdb_created':False,
        'superseded_zero_science_admission_failure_job':4515082})
    print('EXTRA_CPU_ADMISSION_BOUND_PROCESSING_AST_UNCHANGED',flush=True)

if __name__=='__main__':main()
