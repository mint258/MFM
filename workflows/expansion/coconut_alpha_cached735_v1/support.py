"""Owned bounded immutable Alpha references, independent of Main proofs."""
import hashlib
import json
import os
import stat
from pathlib import Path


def need(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode() + b'\n'


def frame(s):
    return (s.st_dev, s.st_ino, s.st_uid, s.st_nlink, s.st_size,
            s.st_mtime_ns, s.st_ctime_ns)


def read(ref, cap=32 << 20):
    p = Path(ref['path'])
    need(p.is_absolute() and type(ref['bytes']) is int and 0 <= ref['bytes'] <= cap,
         'BOUNDED_ABSOLUTE_REFERENCE')
    need(not any(x.is_symlink() for x in (p, *p.parents)), 'NO_INPUT_SYMLINK')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_uid == 1264
             and before.st_nlink == 1 and before.st_size == ref['bytes'],
             'REAL_ALPHA_OWNED_SINGLE_LINK_INPUT')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(cap + 1)
        need(frame(before) == frame(os.fstat(fd)) == frame(p.stat()),
             'IMMUTABLE_SAME_FD_INPUT')
        need(len(raw) == ref['bytes'] and hashlib.sha256(raw).hexdigest() == ref['sha256'],
             'EXACT_MACHINE_REFERENCE_BYTES_AND_SHA')
        return raw
    finally:
        os.close(fd)


def load(ref):
    return json.loads(read(ref))


def pin(path):
    p = Path(path).absolute()
    before = p.stat()
    h = hashlib.sha256()
    with p.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    need(frame(before) == frame(p.stat()), 'IMMUTABLE_OUTPUT_OR_SOURCE')
    return dict(path=str(p), bytes=before.st_size, sha256=h.hexdigest())


def save(path, value):
    with Path(path).open('xb') as stream:
        stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
    return pin(path)
