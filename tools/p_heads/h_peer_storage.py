"""Read shared storage forecasts; inspect file metadata, never active SQLite.

Uses the published D reservation registry and its B0 closure protocol. Existing
model/18GB/followup reservations remain protected. D full-store physical bytes
are already in quota usage and are deducted only from their own declared peak.
"""
import json
import os
from pathlib import Path
import stat


def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError('Unknown storage forecast')
    return value


def read(path):
    return json.loads(Path(path).read_text())


def physical(paths):
    total = 0
    seen = set()
    for path in paths:
        try:
            info = path.lstat()
        except FileNotFoundError:
            # An atomic producer temporary file may disappear after enumeration.
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise OSError('Unknown peer file type/owner')
        identity = (info.st_dev, info.st_ino)
        if identity not in seen:
            seen.add(identity)
            total += min(info.st_size, info.st_blocks * 512)
    return total


def concurrent(policy, *, legacy_model, followup):
    """Re-read peer forecasts and physical growth for each runtime admission."""
    registry = read(policy['peer_storage_registry'])
    if registry['schema'] != 'D_STAGE0_REGISTERED_STORAGE_RESERVATIONS_V1':
        raise ValueError('Unknown peer storage registry')
    model = integer(registry['registered_model_share_future_bytes'])
    components = registry['registered_model_share_components']
    if sum(integer(v) for v in components.values()) != model:
        raise ValueError('Peer model components do not match total')
    model += max(0, integer(legacy_model) - integer(components['existing_model_and_P']))
    total = model + integer(registry['benchmark_peer_environment_bytes'])
    total += integer(registry['benchmark_miscellaneous_future_bytes'])
    for reference in registry['B0_labels']:
        folder = Path(reference['directory'])
        if not folder.is_dir():
            raise OSError('Peer label directory unavailable')
        total += max(2**26, integer(reference['forecast_bytes']) - physical(folder.glob('*.sqlite')))
    for directory in registry['B0_geometry']:
        folder = Path(directory)
        access = read(folder / 'access.json')
        closure = access.get('actual_closure_evidence', {}).get('raw', '')
        sealed = (access.get('immutable') is True and access.get('cross_node_read_allowed') is True
                  and access.get('publishing_uid') == os.getuid()
                  and 'JobState=COMPLETED' in closure and 'ExitCode=0:0' in closure)
        if not sealed:
            forecast = integer(read(folder / 'queue.manifest.json')['storage_forecast_bytes'])
            total += max(2**26, forecast - physical(folder.glob('*.sqlite')))
    plan = read(policy['peer_D_production_plan'])
    if plan['schema'] != 'D_FULL_PRODUCTION_PLAN_V1':
        raise ValueError('Unknown D production plan')
    configuration = plan['configs']['produce']
    joint = integer(configuration['peak_bytes'])
    full_peak = integer(plan['budget']['peak_new_bytes'])
    if full_peak > joint:
        raise ValueError('D full forecast exceeds its joint peak')
    full_root = Path(configuration['output']).parent
    if str(full_root) != policy['peer_D_full_root'] or full_root.is_symlink() or not full_root.is_dir():
        raise OSError('Unknown D full output root')
    files = []
    for directory, folders, names in os.walk(full_root):
        if any((Path(directory) / name).is_symlink() for name in folders):
            raise OSError('Unexpected linked D full directory')
        files.extend(Path(directory) / name for name in names)
    committed = min(full_peak, physical(files))
    remaining = joint - committed
    total += remaining + integer(policy['existing_other_NFS_future_bytes']) + integer(followup)
    return dict(total=total, peer_registry=policy['peer_storage_registry'],
                D_joint_peak=joint, D_full_committed=committed, D_remaining=remaining,
                model_share_future=model, followup_remaining=followup,
                existing_other_NFS_future=policy['existing_other_NFS_future_bytes'])
