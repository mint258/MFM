"""Four metadata-only checks inside the actual model-job preflight."""
from pathlib import Path
import pytest
import long_common as c
import long_worker as worker
import long_frames as frames


def test_all_four_members_and_finite_update_endpoints_keep_original_science():
    assert c.MEMBERS==((0,'fp32'),(0,'bf16'),(1,'fp32'),(1,'bf16'))
    assert [c.endpoint(value) for value in (0,955,1000,9999,10000,19999)]==[1000,1000,2000,10000,11000,20000]
    for value in (-1,20000,True):
        with pytest.raises(ValueError):c.endpoint(value)
    assert c.policy()['counts']['successful_segments']==96
    assert c.policy()['counts']['failed_attempts']==12
    assert c.policy()['counts']['launch_attempts']==108


def test_predeclared_slots_cover_early_failures_and_preserve_registry_flags(tmp_path):
    registry=c.initial_roots(tmp_path)
    paths=[Path(row['path']) for row in registry['roots']]
    assert len(paths)==329 and len(set(paths))==329
    assert not any(a!=b and (a.is_relative_to(b) or b.is_relative_to(a)) for a in paths for b in paths)
    slot=c.slot_layout(tmp_path,1)
    assert next(row for row in registry['roots'] if row['path']==str(slot['management']))==dict(
        path=str(slot['management']),kind='external_guard',type='directory',must_exist=False)
    assert len(paths)+1<=c.policy()['managed_roots']


def test_actual_command_preserves_supervisor_and_child_budget_semantics(tmp_path):
    frame=dict(slot=1,runtime_contract={'path':'/runtime_contract.json'})
    argv=worker.command(tmp_path,frame,{'path':'/submission.json','sha256':'a'*64},'12345')
    divider=argv.index('--');head,tail=argv[:divider],argv[divider+1:]
    assert '--observations' not in head and tail.count('--observations')==1
    assert head[head.index('--wall-seconds')+1]=='7100'
    assert head[head.index('--output-budget-bytes')+1]==str(2<<30)
    assert '/tmp/mv3n_12345' in head and str(c.GPU) in head
    assert str(c.HERE/'long_child.py') in tail
    assert c.CHILD==c.OUTER-(96<<20) and c.CHILD_SECONDS==6900


def test_conservative_shared_metadata_charge_fits_two_CP_and_preserves_unknowns(monkeypatch):
    policy=c.policy();assert policy['metadata_bytes']==512<<20
    assert 2*policy['checkpoint_bytes']+(128<<20)+policy['metadata_bytes']+(96<<20)<c.OUTER
    text=(Path(frames.__file__)).read_text()
    assert 'actual_current_shared_ledger_bytes=None' in text
    assert 'shared_ledger_ceiling_charged_bytes' in text
    assert 'ledger_charge=policy()' in text
    # Actual stdlib-only V2/V8 imports in a fresh process must work without
    # relying on environment() for some future child. Foreign preloads fail.
    origin,coverage,adapter=c.operation_modules()
    assert Path(origin.__file__).absolute()==c.V2/'runtime_origin.py'
    assert Path(coverage.__file__).absolute()==c.V8/'root_coverage.py'
    assert adapter.root_coverage is coverage
    import sys
    from types import SimpleNamespace
    monkeypatch.setitem(sys.modules,'runtime_origin',SimpleNamespace(__file__='/foreign/runtime_origin.py',__spec__=None))
    with pytest.raises(ValueError,match='Foreign operational'):
        c.operation_modules()
