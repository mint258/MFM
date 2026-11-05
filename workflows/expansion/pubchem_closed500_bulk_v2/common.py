"""Small immutable metadata, same-FD source digests, and resource observations."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import uuid

CATEGORIES = ('accepted', 'chemReject', 'technicalUnresolved')
EXPECTED_COUNTS = dict(zip(CATEGORIES, (110046364, 14764875, 46201)))
EXPECTED_ROWS = 124857440


def need(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def frame(path):
    s = Path(path).lstat()
    need(stat.S_ISREG(s.st_mode), 'Regular file required: ' + str(path))
    need(s.st_uid == os.getuid(), 'Own source/output required: ' + str(path))
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_uid)


def reference(path):
    path = Path(path).absolute()
    before = frame(path)
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b''):
            h.update(chunk)
    need(frame(path) == before, 'File changed while hashing: ' + str(path))
    return {'path': str(path), 'bytes': before[2], 'sha256': h.hexdigest()}


def verify(ref):
    need(reference(ref['path']) == ref, 'Immutable source/checkpoint reference mismatch: ' + ref['path'])
    return Path(ref['path'])


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # A unique attempt is preserved if interrupted. Never overwrite a closed result.
    pending = path.with_name(path.name + '.pending.' + uuid.uuid4().hex)
    with pending.open('xb') as stream:
        stream.write(canonical(value) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.link(pending, path)
    # Remove only this invocation's exact just-linked temporary name.
    pending.unlink()
    return reference(path)


class DigestReader(io.RawIOBase):
    """Arrow seek reader with one forward SHA frontier on the same immutable FD."""
    def __init__(self, stream, ref):
        super().__init__()
        self.stream, self.ref = stream, ref
        self.pos = self.frontier = 0
        self.digest = hashlib.sha256()
        self.before = frame(ref['path'])
        need(self.before[2] == ref['bytes'], 'Source size differs from the closed reference')
        s = os.fstat(stream.fileno())
        need((s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_uid) == self.before, 'Same source FD required')

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        need(whence in (0, 1, 2), 'Invalid source seek origin')
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.ref['bytes'] + offset
        need(self.pos >= 0, 'Negative source seek')
        return self.pos

    def advance(self, target):
        target = min(target, self.ref['bytes'])
        while self.frontier < target:
            chunk = os.pread(self.stream.fileno(), min(8 << 20, target - self.frontier), self.frontier)
            need(chunk, 'Source truncated before the closed byte boundary')
            self.digest.update(chunk)
            self.frontier += len(chunk)

    def read(self, size=-1):
        size = max(0, self.ref['bytes'] - self.pos) if size < 0 else size
        self.stream.seek(self.pos)
        result = self.stream.read(size)
        start = self.pos
        self.pos += len(result)
        self.advance(start)
        if self.frontier < self.pos:
            self.digest.update(result[max(0, self.frontier - start):])
            self.frontier = self.pos
        return result

    def readinto(self, buffer):
        result = self.read(len(buffer))
        buffer[:len(result)] = result
        return len(result)

    def finish(self):
        self.advance(self.ref['bytes'])
        s = os.fstat(self.stream.fileno())
        need((s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_uid) == self.before == frame(self.ref['path']), 'Source changed during projection')
        need(self.digest.hexdigest() == self.ref['sha256'], 'Whole source SHA mismatch')
        return self.digest.hexdigest()


def resource_check(plan, output_root):
    """Real space reservations, with no application wall-clock or retry limit."""
    root = Path(output_root)
    cap = plan['output_cap_bytes']
    used = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    need(used < cap, 'Declared whole-output storage allowance reached')
    space = os.statvfs(root)
    free = space.f_bavail * space.f_frsize
    remaining = max(0, cap - used)
    need(free - remaining - plan['other_future_reserved_bytes'] >= plan['minimum_free_bytes'], 'Actual storage minus all reserved future output is insufficient')
    mem = {line.split(':')[0]: int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemAvailable:', 'MemTotal:'))}
    need(mem['MemAvailable'] >= plan.get('minimum_node_available_bytes', 1 << 30), 'Actual node available memory is insufficient')
    return {'used_output_bytes': used, 'free_filesystem_bytes': free, 'remaining_output_reserved_bytes': remaining, **mem}
