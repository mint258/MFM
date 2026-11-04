"""Deploy Alpha external transport support in a fresh namespace; old jobs stay immutable."""
import argparse,ast,hashlib,importlib,json,os,pathlib,runpy,sys
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
D=A/'control/pubchem_completion_environment_20261103'
OLD=A/'code/main_rescue_import_20261104_v1'
NEW=A/'code/main_rescue_import_transport_20261104_v2'
def ref(p):
    p=pathlib.Path(p);before=p.stat();raw=p.read_bytes();after=p.stat()
    assert after.st_uid==1264 and not p.is_symlink()
    assert(before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns)
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def write(p,text):
    p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8',newline='')as f:f.write(text)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--payload',required=True,type=pathlib.Path);a=p.parse_args()
    assert os.getuid()==1264 and sys.flags.isolated and not NEW.exists()
    payload=json.loads(a.payload.read_text());assert payload['schema']=='MAIN_RESCUE_EXTERNAL_TRANSPORT_SOURCE_PAYLOAD_V1'
    old_ref=D/'main_rescue_import_20261104_v1_source.json';previous=json.loads(old_ref.read_text())
    assert len(payload['files'])==3 and len({v['name']for v in payload['files']})==3
    for item in payload['files']:
        name=pathlib.PurePosixPath(item['name']);assert len(name.parts)==1 and name.suffix=='.py'
        raw=item['content'].encode();assert len(raw)==item['bytes']and hashlib.sha256(raw).hexdigest()==item['sha256']
        compile(raw,str(name),'exec')
    NEW.mkdir(mode=0o700)
    for namespace in ['workflows','workflows/expansion']:
        old_init=OLD/namespace/'__init__.py';paths=ast.literal_eval(ast.parse(old_init.read_text()).body[0].value)
        write(NEW/namespace/'__init__.py','__path__ = '+repr([str(NEW/namespace),*paths])+'\n')
    entry=NEW/'entry.py';write(entry,(OLD/'entry.py').read_text())
    folder='workflows/expansion/main_exact_rescue_v1'
    for path in(OLD/folder).glob('*.py'):
        body=path.read_text()
        if path.name=='common.py':body+='\nfrom ..main_exact_rescue_transport_v1.transport import Transport\n'
        if path.name=='importer.py':
            body=body.replace("pins=[C.reference(p)for p in Path(__file__).parent.glob('*.py')]",
                "pins=[C.reference(p)for p in Path(__file__).parent.glob('*.py')]\n    from ..main_exact_rescue_transport_v1 import transport as exact_transport\n    pins.append(C.reference(exact_transport.__file__))")
        write(NEW/folder/path.name,body)
    for item in payload['files']:
        write(NEW/'workflows/expansion/main_exact_rescue_transport_v1'/item['name'],item['content'])
    runpy.run_path(str(entry),run_name='_source_probe')
    from workflows.expansion.main_exact_rescue_v1 import importer,common
    from workflows.expansion.main_exact_rescue_transport_v1 import transport
    from workflows.expansion.exact_nn_cached_v1 import engine
    assert common.Transport is transport.Transport and pathlib.Path(importer.__file__).is_relative_to(NEW)
    assert engine.__file__==previous['actual_metadata_probe']['engine']['path']
    code=list(previous['code_references'])
    for path in [*NEW.rglob('*.py'),pathlib.Path(__file__),a.payload]:
        item=ref(path)
        if item not in code:code.append(item)
    for item in code:assert ref(item['path'])==item
    probes=dict(previous['actual_metadata_probe'],main_rescue_importer=ref(importer.__file__),
        main_rescue_common=ref(common.__file__),external_transport=ref(transport.__file__))
    result=dict(schema='ALPHA_MAIN_RESCUE_IMPORT_EXTERNAL_TRANSPORT_SOURCE_V2',entry=ref(entry),code_references=code,
        actual_metadata_probe=probes,prior_source_references=[ref(old_ref)],payload_reference=ref(a.payload),
        deployment_script_reference=ref(__file__),production_launched=False,original201_touched=False,
        running_Main875_or_Alpha232_233_code_or_data_changed=False,
        transport_catalog_maximum_bytes=64<<20,scientific_rows_or_math_changed=False)
    out=D/'main_rescue_import_transport_20261104_v2_source.json';write(out,json.dumps(result,sort_keys=True)+'\n')
    print(json.dumps(dict(source_reference=ref(out),entry=result['entry'],code_references=len(code),probe=probes['external_transport'])),flush=True)
if __name__=='__main__':main()
