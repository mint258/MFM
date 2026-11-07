"""Deploy independent Alpha score-cache import; keep every live NN source immutable."""
import argparse,ast,hashlib,json,os,pathlib,runpy,sys
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
D=A/'control/pubchem_completion_environment_20261103'
OLD=A/'code/shard_guard_cadence_20261105_v2'
NEW=A/'code/alpha_partition_cache_import_20261105_v2'
PACKAGE='workflows/expansion/alpha_partition_cache_import_v1'
SUPPORT='workflows/expansion/before_coverage_reuse_v1'
def ref(path):
    path=pathlib.Path(path);before=path.stat();raw=path.read_bytes();after=path.stat()
    if path.is_symlink()or after.st_uid!=1264 or(before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError('Immutable own source frame')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def write(path,body):
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='')as f:f.write(body)
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--payload',required=True,type=pathlib.Path);parser.add_argument('--support-payload',required=True,type=pathlib.Path);args=parser.parse_args()
    if os.getuid()!=1264 or not sys.flags.isolated or NEW.exists():raise ValueError('Fresh isolated Alpha source namespace')
    payload=json.loads(args.payload.read_bytes());items=payload['files']
    if payload['schema']!='ALPHA_OWN_PARTITION_IMPORT_SOURCE_PAYLOAD_V1' or {v['name']for v in items}!={'__init__.py','checks.py','run.py','test_checks.py','native_fixture.py','README.md'} or len(items)!=6:
        raise ValueError('Exact declared independent import package')
    support=json.loads(args.support_payload.read_bytes());support_items=support['files']
    if support['schema']!='ALPHA_PARTITION_CLOSED_CATALOG_SUPPORT_V1' or {v['name']for v in support_items}!={'__init__.py','catalog.py'} or len(support_items)!=2:
        raise ValueError('Exact unchanged closed-score catalog support package')
    for item in [*items,*support_items]:
        raw=item['content'].encode('utf-8')
        if len(raw)!=item['bytes']or hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('Payload whole SHA')
        if item['name'].endswith('.py'):compile(raw,str(NEW/PACKAGE/item['name']),'exec')
    old_source=D/'shard_guard_cadence_20261105_v2_source.json';previous=json.loads(old_source.read_bytes())
    if ref(old_source)['sha256']!='67d558f1d5ed9bb2381383bbfbae30b21c6e42e9b3dee9494569db09a3fcf84c':raise ValueError('Actual immutable original NN deployment')
    for item in previous['code_references']:
        if ref(item['path'])!=item:raise ValueError('Previous NN source bytes changed')
    NEW.mkdir(mode=0o700)
    for relative in('workflows','workflows/expansion'):
        paths=ast.literal_eval(ast.parse((OLD/relative/'__init__.py').read_text()).body[0].value)
        write(NEW/relative/'__init__.py','__path__ = '+repr([str(NEW/relative),*paths])+'\n')
    write(NEW/'entry.py',(OLD/'entry.py').read_text())
    for item in items:write(NEW/PACKAGE/item['name'],item['content'])
    for item in support_items:write(NEW/SUPPORT/item['name'],item['content'])
    runpy.run_path(str(NEW/'entry.py'),run_name='_partition_import_metadata_probe')
    from workflows.expansion.alpha_partition_cache_import_v1 import run,checks
    # Import the actual execute() prefix without entering any DATA or scheduler work.
    function=next(n for n in ast.parse(pathlib.Path(run.__file__).read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='execute')
    imports=[]
    for node in function.body:
        if not isinstance(node,(ast.Import,ast.ImportFrom)):break
        imports.append(node)
    if len(imports)!=12:raise ValueError('Actual importer import-prefix shape changed')
    exec(compile(ast.Module(body=imports,type_ignores=[]),run.__file__,'exec'),run.__dict__)
    from workflows.expansion.before_coverage_reuse_v1 import catalog
    if pathlib.Path(catalog.__file__)!=NEW/SUPPORT/'catalog.py':raise ValueError('Actual closed-score catalog routing')
    from workflows.expansion.alpha_sharded_novelty_v1 import run as original
    from workflows.expansion.exact_nn_cached_v1 import engine
    if pathlib.Path(run.__file__)!=NEW/PACKAGE/'run.py' or pathlib.Path(checks.__file__)!=NEW/PACKAGE/'checks.py' or pathlib.Path(original.__file__)!=OLD/'workflows/expansion/alpha_sharded_novelty_v1/run.py':
        raise ValueError('Independent importer and unchanged original NN routing')
    old_engine=previous['actual_metadata_probe']['engine'];old_engine=old_engine if isinstance(old_engine,str)else old_engine['path']
    if engine.__file__!=old_engine:raise ValueError('Original adopted exact mathematical implementation')
    code=list(previous['code_references'])
    for path in[*NEW.rglob('*.py'),args.payload,args.support_payload,pathlib.Path(__file__)]:
        item=ref(path)
        if item not in code:code.append(item)
    for item in code:
        if ref(item['path'])!=item:raise ValueError('Whole old and new source capsule')
    result=dict(schema='ALPHA_OWN_PARTITION_CACHE_IMPORT_SOURCE_V1',entry=ref(NEW/'entry.py'),code_references=code,previous_source_reference=ref(old_source),payload_reference=ref(args.payload),deployment_script_reference=ref(__file__),actual_metadata_probe=dict(importer=ref(run.__file__),checks=ref(checks.__file__),catalog=ref(catalog.__file__),actual_execute_prefix_imports=len(imports),original_sharded_runtime=ref(original.__file__),engine=ref(engine.__file__)),original_scientific_runtime_changed=False,production_launched=False)
    out=D/'alpha_partition_cache_import_20261105_v2_source.json';write(out,json.dumps(result,sort_keys=True)+'\n')
    print(json.dumps(dict(source_reference=ref(out),entry=result['entry'],code_references=len(code))),flush=True)
if __name__=='__main__':main()
