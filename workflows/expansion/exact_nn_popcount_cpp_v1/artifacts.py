"""Small own-artifact pins for explicit native build/load; no project runtime effects."""
import hashlib
import json
import os
from pathlib import Path
import stat


def need(value, message):
    if not value:
        raise ValueError(message)


def frame(path, *, owned=True):
    s = Path(path).lstat()
    need(stat.S_ISREG(s.st_mode) and (not owned or s.st_uid == os.getuid()), 'Regular actual source/binary/metadata owner required')
    return (s.st_dev, s.st_ino, s.st_uid, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def reference(path, *, owned=True):
    path = Path(path).absolute(); before = frame(path, owned=owned)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        s = os.fstat(stream.fileno())
        need((s.st_dev, s.st_ino, s.st_uid, s.st_size, s.st_mtime_ns, s.st_ctime_ns) == before, 'Same artifact FD required')
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
        s = os.fstat(stream.fileno())
        need((s.st_dev, s.st_ino, s.st_uid, s.st_size, s.st_mtime_ns, s.st_ctime_ns) == before, 'Artifact FD changed')
    need(frame(path, owned=owned) == before, 'Artifact path changed')
    return dict(path=str(path), bytes=before[3], sha256=digest.hexdigest())


def verify(ref):
    need(reference(ref['path']) == {k: ref[k] for k in ('path', 'bytes', 'sha256')}, 'Explicit source/binary pin differs')
    return Path(ref['path'])


def load_metadata(ref):
    need(type(ref['bytes']) is int and 0 <= ref['bytes'] <= 2 << 20, 'Small exact native metadata reference required')
    return json.loads(verify(ref).read_text(encoding='utf-8'))


def write_new(path, value):
    with Path(path).open('xb') as stream:
        stream.write(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode() + b'\n')
        stream.flush(); os.fsync(stream.fileno())
    return reference(path)
