"""Archive closed native offline W&B execution/diagnostic directories.

The producer writes one gzip archive and one path/size/file-count manifest.
It reads no training weights or scientific datasets. Run on compute-0-20
after registering its destination in the existing global model forecast.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import stat
import tarfile
import time


BASE = Path('/lfshome/zixiao/model_v31_20261105')
PROJECT = Path('/share/home/zixiao/descriptor_analysis')
CONTROL = PROJECT / 'runs/model_v31_20261105'
SYMLINK_NOTE = ('SDK navigation symlinks omitted; every regular file in the '
                'selected closed execution directories is included unchanged')


def closed_roots(manifest, jobs):
    jobs = list(jobs)
    if (not jobs or any(type(job) is not int or job <= 0 for job in jobs)
            or len(set(jobs)) != len(jobs)):
        raise ValueError('Select distinct actual positive Slurm execution IDs')
    entries = manifest['runs']
    for job in jobs:
        if sum(row['job'] == job for row in entries) != 1:
            raise ValueError('Each selected job must occur once in the actual tracking manifest')
    tracking = Path(manifest['tracking_root'])
    roots = []
    for job in jobs:
        for root, state_name in ((tracking / str(job), 'tracking.json'),
                                 (tracking / 'diagnostics' / str(job), 'status.json')):
            path = root / state_name
            if not path.is_file():
                raise ValueError(f'SDK completion not yet available: {path}')
            state = json.loads(path.read_text())
            if state.get('job') != job or state.get('finished') is not True:
                raise ValueError(f'Actual SDK execution is not closed: {path}')
            roots.append(root)
    return tracking, roots


def pack_closed_runs(manifest, jobs, destination, name, *, capacity_check,
                     root_resolver=None, archive_prefix='WANDB_20261110'):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
        raise ValueError('Use a plain archive name, without path separators')
    jobs = list(jobs)
    tracking, roots = (closed_roots if root_resolver is None else root_resolver)(manifest, jobs)
    destination = Path(destination)
    archive = destination / (name + '.tar.gz')
    manifest_path = destination / (name + '.manifest.json')
    if archive.exists() or manifest_path.exists():
        if archive.is_file() and manifest_path.is_file():
            saved = json.loads(manifest_path.read_text())
            if (saved.get('jobs') == jobs and saved.get('archive') == str(archive)
                    and saved.get('source_tracking_root') == str(tracking)
                    and saved.get('bytes') == archive.stat().st_size):
                return saved
        raise FileExistsError('Retain existing archive/manifest; use its actual delivery state')

    files = []
    for root in roots:
        for path in sorted(root.rglob('*')):
            info = path.lstat()
            if stat.S_ISREG(info.st_mode):
                files.append((path, path.relative_to(tracking).as_posix(), info.st_size))
    raw_bytes = sum(size for _, _, size in files)
    # The admission callback includes the complete global forecast/concurrency.
    # Count a worst-case uncompressed archive plus tar/gzip overhead as well.
    peak_bytes = raw_bytes + 2048 * len(files) + 1024 * 1024
    capacity_check(peak_bytes, len(files) + 2)
    destination.mkdir(parents=True, exist_ok=True)
    partial = archive.with_suffix(archive.suffix + '.partial')
    if partial.exists():
        raise FileExistsError('Retain interrupted archive; do not overwrite or delete it')
    started = time.monotonic()
    with tarfile.open(partial, 'x:gz', compresslevel=6) as output:
        for path, relative, _ in files:
            capacity_check(peak_bytes, len(files) + 2)
            output.add(path, arcname=archive_prefix + '/' + relative, recursive=False)
    partial.rename(archive)
    value = dict(schema='MODEL_OFFLINE_WANDB_ARCHIVE_V1', jobs=jobs,
        native_sdk_finished=True, archive=str(archive), bytes=archive.stat().st_size,
        file_count=len(files), uncompressed_bytes=raw_bytes,
        source_tracking_root=str(tracking), files=[
            dict(path=archive_prefix + '/' + relative, bytes=size) for _, relative, size in files],
        symlinks=SYMLINK_NOTE, original_files_retained=True, cloud_synchronized=False,
        created_at=time.time(), elapsed_seconds=time.monotonic()-started)
    capacity_check(peak_bytes, len(files) + 2)
    pending = manifest_path.with_suffix(manifest_path.suffix + '.partial')
    with pending.open('x') as stream:
        stream.write(json.dumps(value, indent=2) + '\n')
    pending.rename(manifest_path)
    return value


def actual_capacity_check(destination):
    spec = importlib.util.spec_from_file_location('existing_model_disk_guard',
        PROJECT / 'MFM_model_v3/tools/model_v3/v2_diagnosis_disk.py')
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)

    def require(archive_peak, files):
        _, remaining = guard.model_growth_forecast()
        guard.m.require_capacity(guard.m.filesystem_status('/'), 0, 0)
        guard.m.require_capacity(guard.m.filesystem_status(destination.parent),
                                 max(remaining, archive_peak), max(10000, files))
        guard.m.require_capacity(guard.m.filesystem_status(CONTROL), 67108864, 1000)
        guard.m.quota_headroom(guard.CONTROL / 'lustre_quota_available_v2_20261107.json',
            '/lfshome', max(remaining, archive_peak), guard.remaining_d6()+6_000_000_000)
        guard.m.quota_headroom(guard.CONTROL / 'share_quota_available_v3.json',
            '/share', 67108864, guard.remaining_nfs_other())
    return require


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--jobs', type=int, nargs='+', required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    if os.getuid() != 1278 or socket.gethostname().split('.')[0] != 'compute-0-20':
        raise ValueError('Archive production runs on the actual owning compute-0-20 node')
    spec = importlib.util.spec_from_file_location('existing_output_registry',
        Path(__file__).with_name('v2_run_development.py'))
    registry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(registry)
    budget = json.loads(registry.REGISTRY.read_text())
    registry.require_registered_output(args.destination, budget)
    manifest = json.loads(args.manifest.read_text())
    registry.require_registered_output(manifest['tracking_root'], budget)
    result = pack_closed_runs(manifest, args.jobs, args.destination, args.name,
                              capacity_check=actual_capacity_check(args.destination))
    print(json.dumps({k:v for k,v in result.items() if k != 'files'}), flush=True)


if __name__ == '__main__':
    main()
