"""Real disk headroom checks for taskbook-v2 checkpoint writes."""
from collections.abc import Mapping
import os
from pathlib import Path

GIB = 1024 ** 3
SHARED_RESERVE = 100_000_000_000


def filesystem_status(path):
    path = Path(path).resolve()
    while not path.exists():
        path = path.parent
    stats = os.statvfs(path)
    root_device = path.stat().st_dev == Path('/').stat().st_dev
    return dict(total=stats.f_blocks * stats.f_frsize,
                available=stats.f_bavail * stats.f_frsize,
                inodes=stats.f_favail, total_inodes=stats.f_files, root=root_device)


def require_capacity(status, peak_bytes, new_inodes=1):
    if status['total'] <= 0 or status['total_inodes'] <= 0 or status['inodes'] < 0:
        raise OSError('Disk byte/inode capacity is unknown; refusing new writes')
    reserve = max(10 * GIB, (status['total'] + 9) // 10) if status['root'] else SHARED_RESERVE
    if status['available'] < reserve + peak_bytes or status['inodes'] <= new_inodes:
        raise OSError(f"Insufficient disk headroom: available={status['available']}, "
                      f"peak={peak_bytes}, reserve={reserve}, inodes={status['inodes']}")


def checkpoint_peak_bytes(value):
    """Conservative new-file estimate; existing/partial files already reduce free space."""
    if hasattr(value, 'numel') and hasattr(value, 'element_size'):
        return value.numel() * value.element_size() + 512
    if isinstance(value, Mapping):
        return 128 + sum(checkpoint_peak_bytes(k) + checkpoint_peak_bytes(v) for k,v in value.items())
    if isinstance(value, (list, tuple)):
        return 128 + sum(checkpoint_peak_bytes(v) for v in value)
    if isinstance(value, (str, bytes, bytearray)):
        return len(value.encode('utf-8') if isinstance(value, str) else value) + 128
    return int(getattr(value, 'nbytes', 64)) + 128


class CheckedWriter:
    """Recheck remaining peak during serialization; leave partials on real space failure."""
    def __init__(self, file, path, peak_bytes):
        self.file, self.path, self.peak = file, path, peak_bytes
        self.written = 0
        self.next_check = 0

    def write(self, data):
        size = len(data)
        if self.written + size >= self.next_check:
            require_capacity(filesystem_status(self.path), max(size, self.peak - self.written), 0)
            self.next_check = self.written + size + 8 * 1024 ** 2
        written = self.file.write(data)
        self.written += written
        return written

    def __getattr__(self, name):
        return getattr(self.file, name)


def save_checkpoint(payload, path):
    import torch
    path = Path(path)
    peak = checkpoint_peak_bytes(payload) * 2 + 1024 ** 2
    require_capacity(filesystem_status(path.parent), peak)
    with path.open('wb') as file:
        torch.save(payload, CheckedWriter(file, path.parent, peak))


def _metadata_path(path, peak):
    path = Path(path)
    require_capacity(filesystem_status(path.parent), peak, 3)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save_metadata_parquet(table, path):
    """Guard native-index publication, including serialization's remaining peak."""
    import pyarrow.parquet as pq
    peak = 2 * table.nbytes + 1024 ** 2
    path = _metadata_path(path, peak)
    with path.open('xb') as file:
        pq.write_table(table, CheckedWriter(file, path.parent, peak), compression='zstd')


def save_metadata_json(payload, path):
    import json
    data = (json.dumps(payload, indent=2) + '\n').encode('utf-8')
    path = _metadata_path(path, len(data))
    with path.open('xb') as file:
        CheckedWriter(file, path.parent, len(data)).write(data)
