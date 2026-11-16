"""New native-index write protection; no existing corpus or label rereads."""
import json

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from phychem_mfm.phase1 import v2_disk as disk


def capacity(available=400 * disk.GIB, inodes=1000):
    return dict(total=500 * disk.GIB, available=available, inodes=inodes,
                total_inodes=2000, root=True)


def test_index_parquet_and_summary_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(disk, 'filesystem_status', lambda path: capacity())
    table = pa.table(dict(molecule_id=['a', 'b'], real_index=[7, 11]))
    path = tmp_path / 'new' / 'records.parquet'
    disk.save_metadata_parquet(table, path)
    assert pq.read_table(path).equals(table)
    summary = dict(records=len(table), bytes=path.stat().st_size)
    disk.save_metadata_json(summary, path.parent / 'summary.json')
    assert json.loads((path.parent / 'summary.json').read_text()) == summary


@pytest.mark.parametrize('space', [capacity(available=0), capacity(inodes=3)])
def test_index_admission_preserves_existing_file(tmp_path, monkeypatch, space):
    path = tmp_path / 'records.parquet'
    path.write_bytes(b'previous-index')
    monkeypatch.setattr(disk, 'filesystem_status', lambda path: space)
    with pytest.raises(OSError, match='headroom'):
        disk.save_metadata_parquet(pa.table(dict(x=[1])), path)
    assert path.read_bytes() == b'previous-index'


def test_index_runtime_shortfall_keeps_partial(tmp_path, monkeypatch):
    observations = iter([capacity(), capacity(), capacity(available=0)])
    monkeypatch.setattr(disk, 'filesystem_status', lambda path: next(observations))
    def serialize(table, file, **kwargs):
        file.write(b'a' * (8 * 1024 ** 2))
        file.write(b'b' * (8 * 1024 ** 2))
    monkeypatch.setattr(pq, 'write_table', serialize)
    path = tmp_path / 'records.parquet'
    with pytest.raises(OSError, match='headroom'):
        disk.save_metadata_parquet(pa.table(dict(x=[1])), path)
    assert path.stat().st_size == 8 * 1024 ** 2
    assert path.read_bytes().endswith(b'a')


def test_summary_admission_refuses_before_creating_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(disk, 'filesystem_status', lambda path: capacity(available=0))
    directory = tmp_path / 'not-created'
    with pytest.raises(OSError, match='headroom'):
        disk.save_metadata_json(dict(records=1), directory / 'summary.json')
    assert not directory.exists()
