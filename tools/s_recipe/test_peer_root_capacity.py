import pytest
import runtime


@pytest.mark.parametrize('node,peer_GiB', [('compute-0-7', 16), ('compute-0-10', 12),
                                         ('compute-0-17', 0), ('compute-0-20', 0)])
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


def test_shared_NFS_pool_counts_S_once_and_retains_unpublished_D6_growth(monkeypatch):
    captured = []
    monkeypatch.setattr(runtime, 'remaining', lambda: 100)
    monkeypatch.setattr(runtime.disk.m, 'filesystem_status', lambda path: str(path))
    monkeypatch.setattr(runtime.disk.m, 'require_capacity', lambda *args: None)
    monkeypatch.setattr(runtime.disk.m, 'quota_headroom', lambda *args: captured.append(args))
    assert runtime.PEER_NFS_FUTURE + runtime.TOTAL_PEAK == 200_546_101_981
    monkeypatch.setattr(runtime.disk, 'remaining_nfs_other', lambda: runtime.LEGACY_NFS_BASE)
    runtime.capacity()
    assert captured[-1][-2:] == (100, 200_546_101_981-runtime.TOTAL_PEAK)
    monkeypatch.setattr(runtime.disk, 'remaining_nfs_other', lambda: runtime.LEGACY_NFS_BASE+123)
    runtime.capacity()
    assert captured[-1][-1] == 200_546_101_981-runtime.TOTAL_PEAK+123
