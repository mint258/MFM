"""Real owned filesystem identities and metadata mappings; no CUDA/Slurm claim."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
import root_coverage as coverage


class MetadataStorage:
    def binding(self,path):
        path=Path(path); raw=path.read_bytes()
        return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    def read_bound(self,ref):
        assert self.binding(ref['path'])==ref
        return json.loads(Path(ref['path']).read_text())


def prepare(tmp_path,monkeypatch):
    storage=MetadataStorage(); runtime=tmp_path/'runtime'; (runtime/'tools/model_v3').mkdir(parents=True)
    supervisor=runtime/'tools/model_v3/run_supervised.py'; supervisor.write_text('# metadata supervisor fixture only\n')
    private_source=runtime/'tools/model_v3/private_runtime_storage.py'; private_source.write_text('# metadata private fixture only\n')
    child=tmp_path/'child'; scratch=tmp_path/'scratch'; scratch.mkdir(mode=0o700)
    log=tmp_path/'slurm.log'; log.write_text('metadata only\n')
    manifest=tmp_path/'source_snapshot.json'; manifest.write_text('{"metadata_fixture":true}')
    monkeypatch.setenv('SLURM_JOB_ID','123'); monkeypatch.setenv('TMPDIR',str(scratch))
    monkeypatch.setenv('WANDB_CONFIG_DIR',str(child/'wandb_config')); monkeypatch.setattr(sys,'dont_write_bytecode',True)
    info=scratch.stat(); boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    raw=dict(schema='model_v3_private_storage_v1',job_id='123',uid=os.getuid(),node='metadata_fixture',boot_id=boot,
        roots=[dict(path=str(scratch),uid=os.getuid(),device=info.st_dev,inode=info.st_ino,kind='scratch')],
        environment=dict(TMPDIR=str(scratch)),private_storage_budget_bytes=1<<20,peak_semantics='sampled_lower_bound',
        source_sha256=storage.binding(private_source)['sha256'])
    receipt=tmp_path/'storage.json'; receipt.write_text(json.dumps(raw))
    callback=dict(output_root=str(child),private_storage=dict(receipt_path=str(receipt),receipt_sha256=storage.binding(receipt)['sha256'],**raw))
    argv=['python',str(supervisor),'--output-root',str(child),'--output-budget-bytes',str(2<<30),
        '--record',str(tmp_path/'guard.json'),'--observations',str(tmp_path/'guard.jsonl')]
    parent=dict(uid=os.getuid(),argv=argv,stdio=dict(stdout=str(log),stderr=str(log)),boot_id=boot,
        cgroup=Path('/proc/self/cgroup').read_text())
    launch=dict(schema='native_S_actual_supervisor_launch_v2',argv=argv,job_id='123',uid=os.getuid(),
        supervisor_source=storage.binding(supervisor),stdio=parent['stdio'],
        prepared_external_artifacts=[dict(role='source_snapshot',path=str(manifest),type='file',raw_reference=storage.binding(manifest))])
    launch_path=tmp_path/'launch.json'; launch_path.write_text(json.dumps(launch))
    external=[dict(path=str(path),type='file',kind='external_guard',must_exist=False)
        for path in (manifest,tmp_path/'guard.json',tmp_path/'guard.jsonl',log,receipt)]
    admission=dict(job_id='123',supervisor_launch=storage.binding(launch_path),lineage_root=str(tmp_path/'lineage'),external_roots=external,
        private_root_domains=[dict(path=str(scratch),domain='node_local_ephemeral')],
        resource_envelope=dict(outer_output_budget_bytes=2<<30,private_storage_budget_bytes=1<<20,additional_durable_private_growth_hold_bytes=0))
    rows=[('child_output',child,'directory','durable'),('source_snapshot',manifest,'file','durable'),
        ('supervisor_record',tmp_path/'guard.json','file','durable'),('supervisor_observations',tmp_path/'guard.jsonl','file','durable'),
        ('slurm_stdout',log,'file','durable'),('slurm_stderr',log,'file','durable'),('private_receipt',receipt,'file','durable'),
        ('private_root',scratch,'directory','node_local_ephemeral'),('environment:TMPDIR',scratch,'directory','private_environment'),
        ('WANDB_CACHE_DIR',child/'cache','directory','durable'),('WANDB_DATA_DIR',child/'wandb_data','directory','durable'),
        ('WANDB_CONFIG_DIR',child/'wandb_config','directory','durable'),('lineage',tmp_path/'lineage','directory','durable'),
        ('management',tmp_path/'ledger','directory','durable')]
    admission['root_coverage']=[dict(role=role,path=str(path),type=kind,domain=domain,
        accounting_root=str(child if path.is_relative_to(child) else path)) for role,path,kind,domain in rows]
    principal=dict(durable_root=str(tmp_path/'ledger'))
    contract=dict(runtime_root=str(runtime),files=[dict(relative_path='tools/model_v3/private_runtime_storage.py',
        sha256=storage.binding(private_source)['sha256'])])
    return callback,admission,principal,storage,contract,parent


def test_all_actual_env_private_guard_stdio_sdk_and_snapshot_roots_align(tmp_path,monkeypatch):
    args=prepare(tmp_path,monkeypatch)
    result=coverage.observe(*args[:5],parent=args[5])
    assert result['all_actual_outputs_covered'] is True
    assert result['private_receipt']['path'].endswith('storage.json')
    assert any(row['role']=='private_root' and row['device']>=0 for row in result['observed'])


@pytest.mark.parametrize('role',['WANDB_CONFIG_DIR','private_root','supervisor_record','slurm_stdout','source_snapshot'])
def test_omitted_actual_output_cannot_pass_empty_or_partial_declaration(tmp_path,monkeypatch,role):
    args=prepare(tmp_path,monkeypatch)
    args[1]['root_coverage']=[row for row in args[1]['root_coverage'] if row['role']!=role]
    with pytest.raises(ValueError,match='omitted'):
        coverage.observe(*args[:5],parent=args[5])


def test_actual_private_inode_is_not_a_boolean_node_local_claim(tmp_path,monkeypatch):
    args=prepare(tmp_path,monkeypatch)
    args[0]['private_storage']['roots'][0]['inode']+=1
    with pytest.raises((ValueError,AssertionError)):
        coverage.observe(*args[:5],parent=args[5])


def test_unknown_piped_stdio_requires_real_scheduler_protocol(tmp_path,monkeypatch):
    args=prepare(tmp_path,monkeypatch)
    args[5]['stdio']['stdout']='pipe:[1]'
    with pytest.raises(ValueError): coverage.observe(*args[:5],parent=args[5])


def snapshot_fixture(tmp_path):
    storage=MetadataStorage(); root=tmp_path/'snapshot'; (root/'nested').mkdir(parents=True)
    source=root/'nested'/'same_basename.py'; source.write_text('# nested original source\n')
    ref=storage.binding(source)
    manifest=root/'manifest.json'
    manifest.write_text(json.dumps(dict(files=[dict(relative_path='nested/same_basename.py',bytes=ref['bytes'],sha256=ref['sha256'])])))
    artifact=dict(path=str(root),relative_manifest=dict(raw_reference=storage.binding(manifest),
        entries_field='files',path_field='relative_path',bytes_field='bytes',sha256_field='sha256'))
    return storage,artifact,manifest


def test_source_snapshot_resolves_every_original_relative_path_not_basename(tmp_path):
    storage,artifact,_=snapshot_fixture(tmp_path)
    coverage.verify_snapshot_directory(storage,artifact)


def test_source_snapshot_omitted_physical_file_rejected(tmp_path):
    storage,artifact,_=snapshot_fixture(tmp_path)
    (Path(artifact['path'])/'extra.py').write_text('# unenumerated\n')
    with pytest.raises(ValueError,match='every physical'):
        coverage.verify_snapshot_directory(storage,artifact)


def test_source_snapshot_parent_traversal_rejected_without_reading_outside(tmp_path):
    storage,artifact,manifest=snapshot_fixture(tmp_path)
    data=json.loads(manifest.read_text()); data['files'][0]['relative_path']='../outside.py'
    manifest.write_text(json.dumps(data)); artifact['relative_manifest']['raw_reference']=storage.binding(manifest)
    with pytest.raises(ValueError,match='relative'):
        coverage.verify_snapshot_directory(storage,artifact)
