"""Deploy immutable UFF metadata-cache tuning; scientific source bodies unchanged."""
import ast,hashlib,json,os,pathlib,shutil,subprocess,sys
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026');D=A/'control/pubchem_completion_environment_20261103'
OLD=A/'code/uff_quality_timed_86e1e2e';NEW=A/'code/uff_index_cache_20261105_v1'
ADDED="    db.execute('PRAGMA cache_size=-4194304')\n    db.execute('PRAGMA temp_store=MEMORY')\n"
def ref(path):
    path=pathlib.Path(path);before=path.stat();raw=path.read_bytes();after=path.stat()
    if path.is_symlink()or after.st_uid!=1264 or(before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('Own stable source frame')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def write(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='')as f:f.write(raw)
def paths(path):
    node=ast.parse(path.read_text()).body[0]
    if not isinstance(node,ast.Assign)or node.targets[0].id!='__path__':raise ValueError('Explicit original namespace path')
    return ast.literal_eval(node.value)
def main():
    if os.getuid()!=1264 or not sys.flags.isolated or NEW.exists():raise ValueError('Fresh isolated Alpha source deployment')
    payload_path=pathlib.Path(sys.argv[1]);payload=json.loads(payload_path.read_bytes());raw=payload['run']
    original=OLD/'workflows/expansion/uff3_candidate_v1/run.py'
    if payload['schema']!='UFF_SOURCE_INDEX_CACHE_PAYLOAD_V1'or raw.count(ADDED)!=1 or raw.replace(ADDED,'').encode()!=original.read_bytes():raise ValueError('Only two cache PRAGMAs may differ')
    for relative in('workflows','workflows/expansion'):
        previous=OLD/relative/'__init__.py';write(NEW/relative/'__init__.py','__path__ = '+repr([str(NEW/relative),*paths(previous)])+'\n')
    package=pathlib.Path('workflows/expansion/uff3_candidate_v1');copied=[]
    for path in sorted((OLD/package).iterdir()):
        if path.name=='__pycache__':continue
        if path.is_symlink()or not path.is_file()or path.suffix not in('.py','.md'):raise ValueError('Only regular source files')
        write(NEW/package/path.name,raw if path.name=='run.py'else path.read_text())
        if path.name!='run.py'and(NEW/package/path.name).read_bytes()!=path.read_bytes():raise ValueError('Other candidate source bytes unchanged')
        copied.append(path.name)
    write(NEW/'layer_entry.py',(OLD/'layer_entry.py').read_text())
    test=NEW/'workflows/expansion/uff_index_cache_v1/test_metadata.py';write(test,payload['test']);write(test.parent/'__init__.py','')
    subprocess.run([sys.executable,'-I','-B',str(test)],cwd=OLD,check=True)
    old_source=D/'uff_quality_timed_86e1e2e_source.json';source=json.loads(old_source.read_bytes());pins={r['path']:r for r in source['code_references']}
    for pin in list(pins.values()):
        if ref(pin['path'])!=pin:raise ValueError('Original complete capsule changed')
    for path in[*NEW.rglob('*.py'),*NEW.rglob('*.md'),payload_path,pathlib.Path(__file__),old_source]:
        pin=ref(path);pins[pin['path']]=pin
    value=dict(schema='UFF_SOURCE_INDEX_CACHE_DEPLOYMENT_V1',entry=ref(NEW/'layer_entry.py'),code_references=list(pins.values()),original_deployment_reference=ref(old_source),original_run_reference=ref(original),cached_run_reference=ref(NEW/package/'run.py'),only_difference_two_connection_PRAGMAs=True,sqlite_cache_maximum_KiB=4194304,temp_store='MEMORY',journal_and_synchronous_unchanged=True,all_original_identity_uniqueness_rank_and_full_census_checks_unchanged=True,all_other_candidate_sources_byte_identical=True,deployed_metadata_tests=dict(tests=2,status='PASS'),UFF_D_native_calls=0,production_started=False)
    output=D/'uff_index_cache_20261105_v1_source.json';write(output,json.dumps(value,sort_keys=True)+'\n');print(json.dumps(dict(source_reference=ref(output),entry=value['entry'],pins=len(pins))),flush=True)
if __name__=='__main__':main()
