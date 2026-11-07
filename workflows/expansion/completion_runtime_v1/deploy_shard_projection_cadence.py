"""Deploy one resource-cadence edit for the next planned original NN continuation."""
import ast,hashlib,json,os,pathlib,runpy,sys
A=pathlib.Path('/gfshome/alpha/codex_data_v1_20261026')
D=A/'control/pubchem_completion_environment_20261103'
OLD=A/'code/shard_guard_cadence_20261105_v2'
NEW=A/'code/shard_projection_cadence_20261105_v1'
REL='workflows/expansion/alpha_sharded_novelty_v1'
BEFORE='        result.append(closed(path, batch.num_rows, bucket, journal))\n        guard.poll(force=True)'
AFTER='        result.append(closed(path, batch.num_rows, bucket, journal))\n        guard.poll()  # Retain the real 30-second resource cadence across small closed projections.'
def ref(path):
    path=pathlib.Path(path);before=path.stat();raw=path.read_bytes();after=path.stat()
    if path.is_symlink()or after.st_uid!=1264 or(before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('Own immutable source frame')
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def write(path,body):
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='')as f:f.write(body)
def main():
    if os.getuid()!=1264 or not sys.flags.isolated or NEW.exists():raise ValueError('Fresh isolated Alpha resource namespace')
    previous_path=D/'shard_guard_cadence_20261105_v2_source.json';previous=json.loads(previous_path.read_bytes())
    original=OLD/REL/'run.py';payload=D/'shard_projection_runtime_run_20261105_v1.py'
    if ref(original)!=previous['actual_metadata_probe']['sharded_runtime']:raise ValueError('Actual original running source capsule')
    old=original.read_text();fresh=payload.read_text()
    if old.count(BEFORE)!=1 or fresh.count(AFTER)!=1 or fresh.replace(AFTER,BEFORE)!=old:raise ValueError('Exactly one resource-only edit; original full scientific body unchanged')
    compile(fresh,str(payload),'exec')
    for item in previous['code_references']:
        if ref(item['path'])!=item:raise ValueError('Prior source bytes changed')
    NEW.mkdir(mode=0o700)
    for relative in('workflows','workflows/expansion',REL):
        paths=ast.literal_eval(ast.parse((OLD/relative/'__init__.py').read_text()).body[0].value)
        write(NEW/relative/'__init__.py','__path__ = '+repr([str(NEW/relative),*paths])+'\n')
    write(NEW/REL/'run.py',fresh);write(NEW/'entry.py',(OLD/'entry.py').read_text())
    runpy.run_path(str(NEW/'entry.py'),run_name='_projection_cadence_metadata_probe')
    from workflows.expansion.alpha_sharded_novelty_v1 import run
    from workflows.expansion.exact_nn_cached_v1 import engine
    old_engine=previous['actual_metadata_probe']['engine'];old_engine=old_engine if isinstance(old_engine,str)else old_engine['path']
    if pathlib.Path(run.__file__)!=NEW/REL/'run.py' or engine.__file__!=old_engine:raise ValueError('New resource routing and unchanged original mathematical oracle')
    code=list(previous['code_references'])
    for path in[*NEW.rglob('*.py'),payload,pathlib.Path(__file__)]:
        item=ref(path)
        if item not in code:code.append(item)
    for item in code:
        if ref(item['path'])!=item:raise ValueError('Full actual source capsule verification')
    value=dict(schema='ALPHA_SHARD_PROJECTION_CADENCE_SOURCE_V1',entry=ref(NEW/'entry.py'),code_references=code,previous_source_reference=ref(previous_path),original_sharded_runtime_reference=ref(original),actual_metadata_probe=dict(previous['actual_metadata_probe'],sharded_runtime=ref(run.__file__)),resource_changes_only=True,exactly_one_closed_projection_poll_edit=True,byte_identical_to_previous_runtime_after_one_resource_inversion=True,original_30_second_native_quota_and_RSS_functions_unchanged=True,startup_bucket_and_final_forced_checks_retained=True,Core5_math_queries_F64_and_cache_bindings_changed=False,running_jobs_modified=False,production_launched=False)
    output=D/'shard_projection_cadence_20261105_v1_source.json';write(output,json.dumps(value,sort_keys=True)+'\n')
    print(json.dumps(dict(source_reference=ref(output),entry=value['entry'],new_runtime=ref(run.__file__),code_references=len(code))),flush=True)
if __name__=='__main__':main()
