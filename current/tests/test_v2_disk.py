import io

import pytest
import torch

from phychem_mfm.phase1 import v2_disk as disk


def status(**changes):
    result = dict(total=500*disk.GIB, available=400*disk.GIB,
                  inodes=1_000_000, total_inodes=2_000_000, root=True)
    result.update(changes)
    return result


@pytest.mark.parametrize('total,reserve', [(50*disk.GIB,10*disk.GIB), (500*disk.GIB,50*disk.GIB)])
def test_root_reserve_and_full_new_file_peak(total, reserve):
    peak = 3*disk.GIB
    disk.require_capacity(status(total=total,available=reserve+peak),peak)
    with pytest.raises(OSError, match='headroom'):
        disk.require_capacity(status(total=total,available=reserve+peak-1),peak)


@pytest.mark.parametrize('changes', [dict(total=0),dict(total_inodes=0),dict(inodes=-1)])
def test_unknown_capacity_refuses_new_output(changes):
    with pytest.raises(OSError, match='unknown'):
        disk.require_capacity(status(**changes), 1)


def test_inode_exhaustion_refuses_new_file():
    with pytest.raises(OSError, match='headroom'):
        disk.require_capacity(status(inodes=1), 1)


def test_shared_filesystem_retains_project_floor():
    disk.require_capacity(status(root=False,available=disk.SHARED_RESERVE+10),10)
    with pytest.raises(OSError, match='headroom'):
        disk.require_capacity(status(root=False,available=disk.SHARED_RESERVE+9),10)


def test_concurrent_growth_stops_before_next_write_and_keeps_partial(monkeypatch):
    available = [status(), status(available=0)]
    monkeypatch.setattr(disk,'filesystem_status',lambda path: available.pop(0))
    target = io.BytesIO()
    writer = disk.CheckedWriter(target,'/actual-target',32*1024**2)
    first = b'a'*(8*1024**2)
    writer.write(first)
    with pytest.raises(OSError,match='headroom'):
        writer.write(b'b'*(8*1024**2))
    assert target.getvalue() == first


def test_guarded_checkpoint_roundtrip_and_preflight_keeps_previous_file(tmp_path, monkeypatch):
    path = tmp_path/'checkpoint.pt'
    payload = dict(model=torch.arange(12,dtype=torch.float64).reshape(3,4),
                   samples=123, history=[.5,.25])
    disk.save_checkpoint(payload,path)
    restored = torch.load(path,weights_only=True)
    torch.testing.assert_close(restored['model'],payload['model'],atol=1e-12,rtol=1e-12)
    assert restored['samples'] == 123 and restored['history'] == [.5,.25]
    previous = path.read_bytes()
    monkeypatch.setattr(disk,'filesystem_status',lambda target: status(available=0))
    with pytest.raises(OSError,match='headroom'):
        disk.save_checkpoint(payload,path)
    assert path.read_bytes() == previous