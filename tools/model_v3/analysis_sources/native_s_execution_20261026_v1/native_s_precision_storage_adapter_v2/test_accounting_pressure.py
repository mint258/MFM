"""Actual bounded metadata fixture stress; no CUDA/data/quota is simulated."""
from pathlib import Path
import pytest
import native_s_storage as native
from accounting_pressure import materialize_and_measure


@pytest.fixture(scope='module')
def storage():
    return native.load_runtime(metadata_only=True)[0]


def test_distinct_roots_full_chain_metadata_and_inodes_are_really_materialized(storage,tmp_path):
    limits=dict(managed_roots=4,metadata_records=32,metadata_bytes=128<<10,inode_limit=100)
    calls=[]
    result=materialize_and_measure(storage,tmp_path/'owned',limits,lambda:calls.append(True))
    assert result['managed_roots']==4 and result['metadata_records']==32
    assert result['metadata_bytes']==128<<10 and result['inode_entries']==100
    assert result['measurement_passes']==8 and len(result['all_measured_seconds'])==3
    assert result['measured_seconds']>0 and result['operational_metadata_only'] is True and calls
    assert len(list((tmp_path/'owned').glob('owned_fixture_root_*')))==3
    assert len(list((tmp_path/'owned/ledger_fixture/index').glob('*.json')))==14
    assert all(not path.is_symlink() for path in (tmp_path/'owned').rglob('*'))


@pytest.mark.parametrize('changed',[dict(metadata_records=4),dict(inode_limit=10),dict(metadata_bytes=3<<30)])
def test_inconsistent_or_unbounded_fixture_is_rejected_before_creation(storage,tmp_path,changed):
    limits=dict(managed_roots=4,metadata_records=32,metadata_bytes=128<<10,inode_limit=100)
    limits.update(changed)
    with pytest.raises(ValueError):
        materialize_and_measure(storage,tmp_path/'never_created',limits)
    assert not (tmp_path/'never_created').exists()


def test_existing_fixture_is_never_overwritten_or_deleted(storage,tmp_path):
    root=tmp_path/'owned'; root.mkdir(); original=root/'original'; original.write_text('keep')
    with pytest.raises(ValueError,match='Fresh'):
        materialize_and_measure(storage,root,dict(managed_roots=4,metadata_records=32,metadata_bytes=128<<10,inode_limit=100))
    assert original.read_text()=='keep'
