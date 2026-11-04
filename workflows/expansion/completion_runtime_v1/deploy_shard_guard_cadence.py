"""Deploy a fresh resource-poll overlay; require byte equality after two inversions."""
import ast,hashlib,json,os,pathlib,runpy,sys
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026');D=A/'control/pubchem_completion_environment_20261103'
OLD=A/'code/inverted_cache_resume_20261104_v1';NEW=A/'code/shard_guard_cadence_20261105_v2'
def ref(path):
    path=pathlib.Path(path);raw=path.read_bytes();return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def write(path,body):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if path.exists():
        if path.is_symlink() or path.read_text()!=body:raise ValueError('Existing metadata deployment has different bytes')
        return
    with path.open('x',encoding='utf-8',newline='')as f:f.write(body)
def main():
    if os.getuid()!=1264 or not sys.flags.isolated or NEW.is_symlink():raise ValueError('Fresh isolated Alpha resource overlay only')
    previous_path=D/'inverted_cache_resume_20261104_v1_source.json';previous=json.loads(previous_path.read_bytes())
    original=OLD/'workflows/expansion/alpha_sharded_novelty_v1/run.py';old=original.read_text()
    if ref(original)['sha256']!='a85972189719041e7b6910d2f33ea7c1436e7c6db9f6694877317879a018737a':raise ValueError('Actual running producer source changed')
    payload=D/'shard_guard_runtime_run_20261105_v1.py';fresh=payload.read_text()
    pairs=[('            super().poll(force=True, reserve=reserve)','            super().poll(force=True, reserve=reserve)\n            self.last = time.monotonic()  # A slow native check must not trigger another immediately.'),('            known[bucket].append(part); buffers[bucket] = []\n            guard.poll(force=True)','            known[bucket].append(part); buffers[bucket] = []\n            guard.poll()  # Keep the native 30-second quota cadence across small immutable checkpoints.')]
    inverse=fresh
    for before,after in pairs:
        if inverse.count(after)!=1:raise ValueError('Exactly one declared resource edit')
        inverse=inverse.replace(after,before)
    if inverse!=old:raise ValueError('Scientific/query/cache/projection bodies must be byte identical')
    compile(fresh,str(payload),'exec');NEW.mkdir(mode=0o700,exist_ok=True)
    for relative in ('workflows','workflows/expansion'):
        body=(OLD/relative/'__init__.py').read_text();paths=ast.literal_eval(ast.parse(body).body[0].value)
        write(NEW/relative/'__init__.py','__path__ = '+repr([str(NEW/relative),*paths])+'\n')
    relative='workflows/expansion/alpha_sharded_novelty_v1'
    paths=ast.literal_eval(ast.parse((OLD/relative/'__init__.py').read_text()).body[0].value)
    write(NEW/relative/'__init__.py','__path__ = '+repr([str(NEW/relative),*paths])+'\n')
    write(NEW/relative/'run.py',fresh);write(NEW/'entry.py',(OLD/'entry.py').read_text())
    runpy.run_path(str(NEW/'entry.py'),run_name='_cadence_deployment_probe')
    from workflows.expansion.alpha_sharded_novelty_v1 import run
    from workflows.expansion.exact_nn_cached_v1 import engine
    previous_engine=previous['actual_metadata_probe']['engine']
    previous_engine=previous_engine if isinstance(previous_engine,str)else previous_engine['path']
    if pathlib.Path(run.__file__)!=NEW/relative/'run.py' or engine.__file__!=previous_engine:raise ValueError('Fresh resource module and original mathematical oracle paths required')
    code=list(previous['code_references'])
    for path in [*NEW.rglob('*.py'),payload,pathlib.Path(__file__)]:
        item=ref(path)
        if item not in code:code.append(item)
    for item in code:
        if ref(item['path'])!=item:raise ValueError('Pinned prior or new deployment bytes changed')
    value=dict(schema='ALPHA_SHARD_GUARD_CADENCE_SOURCE_V1',entry=ref(NEW/'entry.py'),code_references=code,actual_metadata_probe=dict(previous['actual_metadata_probe'],sharded_runtime=ref(run.__file__)),previous_source_reference=ref(previous_path),original_sharded_runtime_reference=ref(original),resource_changes_only=True,byte_identical_after_exact_two_resource_inversions=True,native_30_second_guard_checks_retained=True,Core5_and_math_and_five_cache_bindings_changed=False,production_launched=False)
    output=D/'shard_guard_cadence_20261105_v2_source.json';write(output,json.dumps(value,sort_keys=True)+'\n')
    print(json.dumps(dict(source_reference=ref(output),entry=value['entry'],code_references=len(code),new_runtime=ref(run.__file__))),flush=True)
if __name__=='__main__':main()