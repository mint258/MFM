"""Small immutable metadata helpers; no Main constants or science imports."""
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid

ENDPOINT = '218.192.171.238:22'
UID = 1264
KIND = 'gluster_directory_quota_deem_statfs'


def need(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def frame(path):
    s = Path(path).lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_uid == os.getuid(), 'Own regular immutable file required')
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_uid


def reference(path):
    path = Path(path).absolute(); before = frame(path); h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    need(before == frame(path), 'Reference changed while hashing')
    return {'path': str(path), 'bytes': before[2], 'sha256': h.hexdigest()}


def verify(ref):
    need(reference(ref['path']) == {k: ref[k] for k in ('path', 'bytes', 'sha256')}, 'Exact Alpha artifact/source pin differs')
    return Path(ref['path'])


def write(path, value, *, replace=False):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.pending.' + uuid.uuid4().hex)
    with temporary.open('xb') as stream:
        stream.write(canonical(value) + b'\n'); stream.flush(); os.fsync(stream.fileno())
    if replace:
        os.replace(temporary, path)
    else:
        os.link(temporary, path); temporary.unlink()
    return reference(path)


def allocated_bytes(root, *, before_unix_seconds=None):
    total, seen = 0, set()
    cutoff = None if before_unix_seconds is None else int(before_unix_seconds * 1000000000)
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in [base, *(str(Path(base) / n) for n in files)]:
            try:s = Path(name).lstat()
            except FileNotFoundError:continue
            need(not stat.S_ISLNK(s.st_mode) and s.st_uid == os.getuid(), 'Aggregate output must contain own non-symlink files/directories only')
            key = s.st_dev, s.st_ino
            if key in seen:continue
            seen.add(key)
            if cutoff is None or max(s.st_mtime_ns, s.st_ctime_ns) < cutoff:
                total += s.st_blocks * 512
        need(all(not Path(base, n).is_symlink() for n in dirs), 'Aggregate scope cannot follow directory symlinks')
    return total
