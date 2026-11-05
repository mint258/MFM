"""Deploy a new fullN coverage provider; never change an active scientific namespace."""
import argparse,ast,hashlib,importlib,json,os,pathlib,runpy,sys
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026');D=A/'control/pubchem_completion_environment_20261103';B=A/'control/pubchem_expansion_runtime_20261103'
NEW=A/'code/after_coverage_inverted_20261105_v3';GUARD=A/'code/shard_guard_cadence_20261105_v2';AFTER=A/'code/after_coverage_1471c84'
PACKAGE='workflows/expansion/coverage_inverted_followup_v1'
def ref(p):
    p=pathlib.Path(p);before=p.stat();raw=p.read_bytes();after=p.stat()
    if p.is_symlink()or after.st_uid!=1264 or(before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('Own immutable source frame')
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def write(p,raw):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='')as f:f.write(raw)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--payload',required=True,type=pathlib.Path);args=parser.parse_args()
    if os.getuid()!=1264 or not sys.flags.isolated or NEW.exists():raise ValueError('Fresh actual Alpha namespace')
    payload=json.loads(args.payload.read_bytes());files=payload['files'];expected={'__init__.py','general_workers.py','coverage.py','admission.py','entry_template.py','test_metadata.py','README.md'}
    if payload['schema']!='AFTER_COVERAGE_INVERTED_PAYLOAD_V1'or len(files)!=len(expected)or {v['name']for v in files}!=expected:raise ValueError('Exact declared overlay package')
    for v in files:
        raw=v['content'].encode()
        if len(raw)!=v['bytes']or hashlib.sha256(raw).hexdigest()!=v['sha256']:raise ValueError('Payload bytes differ')
        if v['name'].endswith('.py'):compile(raw,str(NEW/PACKAGE/v['name']),'exec')
    cfg_path=B/'after_coverage32_20261105_v1_runtime_config.json';cfg=json.loads(cfg_path.read_bytes())
    previous_path=pathlib.Path(cfg['deployment_reference']['path']);guard_path=D/'shard_guard_cadence_20261105_v2_source.json'
    if ref(previous_path)!=cfg['deployment_reference']:raise ValueError('Actual old resource deployment')
    previous=json.loads(previous_path.read_bytes());guard=json.loads(guard_path.read_bytes())
    code={}
    for value in(previous,guard):
        for r in value['code_references']:
            if ref(r['path'])!=r:raise ValueError('Inherited source changed')
            if r['path']in code and code[r['path']]!=r:raise ValueError('Conflicting inherited pin')
            code[r['path']]=r
    NEW.mkdir(mode=0o700)
    for relative in('workflows','workflows/expansion'):
        paths=[str(NEW/relative),str(AFTER/relative)]
        for layer in(AFTER,GUARD):
            paths.append(str(layer/relative))
            paths.extend(ast.literal_eval(ast.parse((layer/relative/'__init__.py').read_text()).body[0].value))
        write(NEW/relative/'__init__.py','__path__ = '+repr(list(dict.fromkeys(paths)))+'\n')
    proof_path=B/'inverted_native_equivalence_20261104_v1.json';native_proof=json.loads(proof_path.read_bytes())
    alpha_ref=native_proof['alpha_result_reference']
    if ref(alpha_ref['path'])!=alpha_ref:raise ValueError('Pinned native Alpha descriptor')
    alpha=json.loads(pathlib.Path(alpha_ref['path']).read_bytes())
    new_build=json.loads(pathlib.Path(alpha['builds']['new']['path']).read_bytes());old_build=json.loads(pathlib.Path(alpha['builds']['old']['path']).read_bytes())
    for pin in [alpha['builds']['new'],alpha['builds']['old'],new_build['oracle_source_reference'],*new_build['source_references'],*old_build['source_references'],new_build['binary_reference'],old_build['binary_reference']]:
        if ref(pin['path'])!=pin:raise ValueError('Actual Alpha native build/source pin')
        code[pin['path']]=pin
    oracle=pathlib.Path(new_build['oracle_source_reference']['path'])
    old_cached=ast.literal_eval(ast.parse((AFTER/'workflows/expansion/exact_nn_cached_v1/__init__.py').read_text()).body[0].value)
    old_engine=next(pathlib.Path(folder)/'engine.py'for folder in old_cached if (pathlib.Path(folder)/'engine.py').exists())
    if old_engine.read_bytes()!=oracle.read_bytes():raise ValueError('The original mathematical oracle body must remain byte-identical')
    write(NEW/'workflows/expansion/exact_nn_cached_v1/__init__.py','__path__ = '+repr([str(oracle.parent),*old_cached])+'\n')
    old_native=pathlib.Path(next(r['path']for r in old_build['source_references']if pathlib.Path(r['path']).name=='backend.py')).parent
    write(NEW/'workflows/expansion/exact_nn_popcount_cpp_v1/__init__.py',(old_native/'__init__.py').read_text()+'\n__path__ = '+repr([str(old_native)])+'\n')
    for v in files:write(NEW/PACKAGE/v['name'],v['content'])
    write(NEW/'entry.py',next(v['content']for v in files if v['name']=='entry_template.py'))
    runpy.run_path(str(NEW/'entry.py'),run_name='_coverage_inverted_deploy_metadata')
    from workflows.expansion.coverage_inverted_followup_v1 import general_workers as worker,coverage,admission
    from workflows.expansion.expansion_coverage_followup_v1 import general_workers as old_worker,coverage as old_coverage
    from workflows.expansion.exact_nn_inverted_production_v1 import authority as fast_authority
    from workflows.expansion.exact_nn_popcount_production_v1 import authority as old_authority
    back=pathlib.Path(worker.__file__).read_text().replace('from ..exact_nn_inverted_cpp_v1 import backend','from ..exact_nn_popcount_cpp_v1 import backend').replace('from ..exact_nn_inverted_production_v1 import authority','from ..exact_nn_popcount_production_v1 import authority')
    if back!=pathlib.Path(old_worker.__file__).read_text():raise ValueError('Exactly two native-provider imports, all fullN worker code otherwise identical')
    back=pathlib.Path(coverage.__file__).read_text().replace('from .admission import after_equivalence\n','').replace("    equivalence_ref = after_equivalence(plan, proof, Path(plan_path).parent / 'augmented_kernel_equivalence.json')\n",'').replace('                  augmented_reference_native_equivalence_reference=equivalence_ref,\n','')
    if back!=pathlib.Path(old_coverage.__file__).read_text()or coverage.original.run.__code__ is not old_coverage.original.run.__code__:raise ValueError('Original fixed1M scientific body must remain exact')
    fast_ref=ref(B/'inverted_native_equivalence_20261104_v1.json')
    fast,_=fast_authority.adopted(fast_ref)
    old=json.loads(pathlib.Path(cfg['backend_adoption_reference']['path']).read_bytes())
    if fast['previous_backend_adoption_reference']!=cfg['backend_adoption_reference']:raise ValueError('Original old206 descriptor binding')
    from workflows.expansion.exact_nn_popcount_cpp_v1 import backend as comparator_backend
    comparator_backend.load_kernel(alpha['builds']['old'])
    if fast['reference_manifest_reference']!=old['reference_manifest_reference']:raise ValueError('Original complete196 reference differs')
    import unittest
    suite=unittest.defaultTestLoader.loadTestsFromName('workflows.expansion.coverage_inverted_followup_v1.test_metadata');result=unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful()or result.testsRun!=5:raise ValueError('Actual deployed metadata tests failed')
    for p in[*NEW.rglob('*.py'),args.payload,pathlib.Path(__file__),cfg_path,previous_path,guard_path]:
        r=ref(p);code[r['path']]=r
    for r in code.values():
        if ref(r['path'])!=r:raise ValueError('Final whole source capsule differs')
    out=D/'after_coverage_inverted_20261105_v3_source.json'
    body=dict(schema='AFTER_COVERAGE_INVERTED_FULLN_SOURCE_V1',entry=ref(NEW/'entry.py'),code_references=list(code.values()),old_resource_deployment_reference=ref(previous_path),original_generic_worker_reference=ref(old_worker.__file__),new_generic_worker_reference=ref(worker.__file__),original_coverage_wrapper_reference=ref(old_coverage.__file__),new_coverage_wrapper_reference=ref(coverage.__file__),actual_original_coverage_body_reference=ref(coverage.original.__file__),fast_before_native_equivalence_reference=fast_ref,comparison_backend_adoption_reference=cfg['backend_adoption_reference'],worker_two_import_inversion_byte_equal=True,original_coverage_code_object_preserved=True,actual_augmented_reference_native_equivalence_pending=True,deployed_metadata_tests=dict(tests=result.testsRun,failures=0,errors=0,status='PASS'),production_resources=dict(workers=32,worker_rss_cap_bytes=5<<29,parent_rss_cap_bytes=8<<30,software_rss_budget_bytes=96<<30,minimum_node_available_bytes=24<<30),new_Root_approval_required=False,production_launched=False)
    write(out,json.dumps(body,sort_keys=True)+'\n');print(json.dumps(dict(source_reference=ref(out),code_references=len(code),entry=body['entry'])),flush=True)
if __name__=='__main__':main()
