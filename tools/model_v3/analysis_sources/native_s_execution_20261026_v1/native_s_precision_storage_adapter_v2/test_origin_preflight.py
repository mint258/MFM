"""Fresh subprocesses audit canonical origins without Inputs/data construction."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
import runtime_origin as origin


@pytest.mark.parametrize('mode',['fresh','native-first','075-first-metadata','075-bare-first-metadata'])
def test_combined_origin_preflight_real_fresh_imports_and_foreign_metadata_rejection(mode):
    contract=os.environ.get('MODEL_V3_NATIVE_S_RUNTIME_CONTRACT')
    assert contract,'Root must bind actual combined metadata contract; no silent skip'
    command=[sys.executable,str(Path(__file__).with_name('origin_probe.py')),'--contract',contract,'--mode',mode,'--metadata-only']
    result=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        text=True,timeout=120,env={**os.environ,'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1'})
    assert result.returncode==0,result.stderr
    receipt=json.loads(result.stdout.splitlines()[-1])
    assert receipt['data_inputs_constructed'] is False and receipt['CUDA_or_training_acceptance'] is False
    if mode.startswith('075-'): assert receipt['status']=='FOREIGN_ORIGIN_REJECTED_METADATA_ONLY'
    else:
        assert receipt['status']=='ORIGIN_METADATA_VERIFIED' and receipt['class_relationships']
        root=Path(json.loads(Path(contract).read_text())['runtime_root'])
        assert all(Path(row['file']).is_relative_to(root) for row in receipt['modules'])


def test_placeholder_never_admits_production_runtime():
    with pytest.raises(ValueError,match='pin missing'):
        origin.read_contract(Path(__file__).with_name('runtime_contract.json'))


def test_operational_QA_stage_change_does_not_change_immutable_source_identity():
    before=dict(runtime_root='/immutable',combined_commit='a'*40,combined_tree='b'*40,public_commit='c'*40,
        accounting_leaf_provenance={'implementation_commit':'075'},files=[dict(relative_path='source.py',bytes=1,sha256='d'*64)],
        status='CANDIDATE_PROFILE_ONLY',production_20k_allowed=False,candidate_profile_admission={'stage':'candidate'})
    after={**before,'status':'PUBLISHED_IMMUTABLE_RUNTIME','production_20k_allowed':True,
        'full_runtime_verification':{'stage':'full'}}
    assert origin.canonical(origin.runtime_identity(before))==origin.canonical(origin.runtime_identity(after))
    after['files']=[dict(relative_path='source.py',bytes=1,sha256='e'*64)]
    assert origin.canonical(origin.runtime_identity(before))!=origin.canonical(origin.runtime_identity(after))


def test_candidate_contract_is_not_default20k_authority(tmp_path):
    path=tmp_path/'candidate.json'
    path.write_text(json.dumps(dict(schema='native_S_single_combined_runtime_v2',status='CANDIDATE_PROFILE_ONLY')))
    with pytest.raises(ValueError,match='no production admission'):
        origin.read_contract(path)
