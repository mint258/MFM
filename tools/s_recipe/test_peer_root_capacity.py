import pytest
import runtime


@pytest.mark.parametrize('node,peer_GiB', [('compute-0-7', 24), ('compute-0-10', 12),
                                         ('compute-0-17', 12), ('compute-0-20', 0)])
def test_admission_keeps_the_published_peer_root_future_once(node, peer_GiB, monkeypatch):
    checked = []
    monkeypatch.setattr(runtime.socket, 'gethostname', lambda: node)
    monkeypatch.setattr(runtime, 'remaining', lambda: 100)
    monkeypatch.setattr(runtime.disk.m, 'filesystem_status', lambda path: str(path))
    monkeypatch.setattr(runtime.disk.m, 'require_capacity',
                        lambda status, size, inodes: checked.append((status, size, inodes)))
    monkeypatch.setattr(runtime.disk.m, 'quota_headroom', lambda *args: None)
    monkeypatch.setattr(runtime.disk, 'remaining_nfs_other', lambda: 0)
    runtime.capacity()
    root = [check for check in checked if check[0] == '/']
    assert root == [('/', 16*1024**2+peer_GiB*1024**3, 1000)]
    assert checked[1][1] == 100  # Peer root reservations do not inflate S NFS growth.
