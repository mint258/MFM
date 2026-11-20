"""Honor published peer futures without changing a running scientific producer."""
import json
import os
from pathlib import Path
import socket

BASE = Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
SCOPES = {str(BASE/'artifacts/benchmark_B0_20261119'), str(BASE/'artifacts/benchmark_B1_20261119')}
POLICY = BASE/'worktrees/benchmark_b1_20261119/workflows/benchmark_data/benchmark_storage_reservations.json'
COMPONENTS = {'model_P_NFS', 'private_environments', 'miscellaneous',
              'S_full_study', 'D_joint_replaces_old_14GiB', 'benchmark_B1_C1'}


def declared_pool(policy):
    if policy.get('schema') != 'benchmark-shared-storage-reservations-v1':
        raise RuntimeError('Unknown peer storage policy schema')
    values = policy.get('components', {})
    if (set(values) != COMPONENTS or set(policy.get('owned_scopes', ())) != SCOPES
            or any(type(v) is not int or v < 0 for v in values.values())):
        raise RuntimeError('Unknown peer storage components, scopes or byte counts')
    total = sum(values.values())
    if type(policy.get('concurrent_total_bytes')) is not int or total != policy['concurrent_total_bytes']:
        raise RuntimeError('Peer storage total differs from its components')
    return total


def combined_pool(legacy, peer, geometry_sealed):
    # Preserve the existing guard. The published pool includes environment/misc
    # futures; a sealed geometry has no new scientific writes. If not sealed,
    # retain both full forecasts conservatively rather than dropping own growth.
    return max(legacy, peer) if geometry_sealed else legacy + peer


def local_peer_guard(policy, node):
    peers = policy.get('node_local_tmp_peer_future_bytes')
    if (not isinstance(peers, dict) or not {'compute-0-7', 'compute-0-17'}.issubset(peers)
            or any(not isinstance(k, str) or type(v) is not int or v < 0 for k, v in peers.items())):
        raise RuntimeError('Unknown node-local peer futures')
    peer = peers.get(node, 0)
    if peer and os.stat('/').st_dev != os.stat('/tmp').st_dev:
        raise RuntimeError('Peer root/tmp future requires actual filesystem reconciliation')
    for target in ('/', '/tmp'):
        s = os.statvfs(target)
        floor = max(10 * 1024**3, s.f_blocks * s.f_frsize // 10)
        if s.f_bavail * s.f_frsize < floor + peer + 16 * 1024**2 or s.f_favail < 2000:
            raise RuntimeError('Root/tmp peer, system or Slurm reserve would be crossed')


def current_pool(root, legacy, policy_path=POLICY):
    root = Path(root).resolve()
    scope = BASE/'artifacts/benchmark_B0_20261119'
    if root != scope and scope not in root.parents:
        raise RuntimeError('B0 peer admission is limited to its own output scope')
    policy = json.loads(Path(policy_path).read_text())
    peer = declared_pool(policy)
    local_peer_guard(policy, socket.gethostname().split('.')[0])
    access = root/'geometry/shared_v1/access.json'
    geometry = json.loads(access.read_text()) if access.exists() else {}
    sealed = bool(geometry.get('immutable') and geometry.get('cross_node_read_allowed')
                  and geometry.get('publishing_uid') == os.getuid())
    return combined_pool(legacy, peer, sealed)
