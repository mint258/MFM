"""Deploy a separate Alpha import namespace without changing running NN sources."""
import argparse,ast,hashlib,importlib,json,os,pathlib,runpy,sys
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
D=A/'control/pubchem_completion_environment_20261103'
OLD=A/'code/before_coverage_reuse_20261104_v1'
NEW=A/'code/main_rescue_import_20261104_v1'
def ref(path):
    p=pathlib.Path(path);before=p.stat();raw=p.read_bytes();after=p.stat()
    if after.st_uid!=1264 or p.is_symlink()or(before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError('Actual immutable owned Alpha code only')
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def write(path,text):
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='')as f:f.write(text)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--payload',required=True,type=pathlib.Path);args=p.parse_args()
    assert os.getuid()==1264 and sys.flags.isolated and not NEW.exists()
    payload=json.loads(args.payload.read_text());assert payload['schema']=='MAIN_RESCUE_ALPHA_SOURCE_PAYLOAD_V1'
    old_path=D/'before_coverage_reuse_20261104_v1_source.json';previous=json.loads(old_path.read_text())
    for item in payload['files']:
        name=pathlib.PurePosixPath(item['name']);assert len(name.parts)==1 and name.suffix=='.py'
        raw=item['content'].encode('utf-8')
        assert len(raw)==item['bytes']and hashlib.sha256(raw).hexdigest()==item['sha256']
        compile(raw,str(name),'exec')
    assert len(payload['files'])==7 and len({x['name']for x in payload['files']})==7
    NEW.mkdir(mode=0o700)
    for namespace in ['workflows','workflows/expansion']:
        old_init=OLD/namespace/'__init__.py'
        tree=ast.parse(old_init.read_text());paths=ast.literal_eval(tree.body[0].value)
        write(NEW/namespace/'__init__.py','__path__ = '+repr([str(NEW/namespace),*paths])+'\n')
    entry=NEW/'entry.py';write(entry,(OLD/'entry.py').read_text())
    for item in payload['files']:write(NEW/'workflows/expansion/main_exact_rescue_v1'/item['name'],item['content'])
    runpy.run_path(str(entry),run_name='_source_probe')
    from workflows.expansion.main_exact_rescue_v1 import importer,common
    from workflows.expansion.exact_nn_cached_v1 import engine
    from workflows.expansion.exact_nn_inverted_cpp_v1 import backend
    assert engine.__file__==previous['actual_metadata_probe']['engine']['path']
    assert pathlib.Path(importer.__file__).is_relative_to(NEW)
    code=list(previous['code_references'])
    fresh=[*NEW.rglob('*.py'),pathlib.Path(__file__),args.payload]
    for path in fresh:
        item=ref(path)
        if item not in code:code.append(item)
    for item in code:assert ref(item['path'])==item
    probes=dict(previous['actual_metadata_probe'],main_rescue_importer=ref(importer.__file__),main_rescue_common=ref(common.__file__),
        inverted_backend=ref(backend.__file__))
    result=dict(schema='ALPHA_MAIN_RESCUE_IMPORT_SOURCE_V1',entry=ref(entry),code_references=code,
        actual_metadata_probe=probes,prior_source_references=[ref(old_path)],payload_reference=ref(args.payload),
        deployment_script_reference=ref(__file__),source_execution_commit=payload['execution_commit'],
        source_commit_completeness_claimed=False,production_launched=False,original201_touched=False,
        running232_233_code_or_data_changed=False)
    out=D/'main_rescue_import_20261104_v1_source.json'
    write(out,json.dumps(result,sort_keys=True)+'\n')
    print(json.dumps(dict(source_reference=ref(out),entry=result['entry'],code_references=len(code),probe=probes['main_rescue_importer'])),flush=True)
if __name__=='__main__':main()
