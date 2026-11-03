"""Immutable metadata, actual quota observations and cooperative resource stops."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import uuid

CATEGORIES = ('accepted', 'chemReject', 'technicalUnresolved')
N = 124857440
BASELINE = dict(zip(CATEGORIES, (110046364, 14764875, 46201)))


def need(value, message):
    if not value:
        raise ValueError(message)


class CooperativeStop(RuntimeError):
    """Resource/source interruption, never a molecular chemical exclusion."""


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def frame(path):
    p = Path(path)
    need(not p.is_symlink() and p.is_file(), 'Literal regular source/output required')
    s = p.stat()
    need(s.st_uid == os.getuid(), 'Own source/output required')
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_uid)


def reference(path):
    path = Path(path).absolute()
    before = frame(path)
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b''):
            h.update(chunk)
    need(frame(path) == before, 'File changed while hashing')
    return {'path': str(path), 'bytes': before[2], 'sha256': h.hexdigest()}


def verify(ref):
    need(reference(ref['path']) == {k: ref[k] for k in ('path', 'bytes', 'sha256')}, 'Pinned input/checkpoint bytes differ: ' + ref['path'])
    return Path(ref['path'])


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.pending.' + uuid.uuid4().hex)
    with pending.open('xb') as stream:
        stream.write(canonical(value) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.link(pending, path)
    pending.unlink()  # This invocation's exact temporary link only.
    return reference(path)


def allocated_bytes(root):
    if not Path(root).exists():
        return 0
    total = 0
    seen = set()
    for base, directories, files in os.walk(root, followlinks=False):
        for path in [Path(base), *(Path(base) / name for name in files)]:
            try:
                need(not path.is_symlink(), 'Output scope must not follow links')
                s = path.stat()
            except FileNotFoundError:
                continue  # Natural SQLite/journal or atomic pending rename.
            identity = (s.st_dev, s.st_ino)
            if identity not in seen:
                seen.add(identity)
                total += s.st_blocks * 512
    return total


def quota_available(raw, device):
    rows = re.findall(r'^\s*' + re.escape(device) + r'\s+(\d+)\s+(\d+)\s+(\d+)(?:\s|$)', raw, re.MULTILINE)
    need(len(rows) == 1, 'One actual user quota device row required')
    used, soft, hard = map(int, rows[0])
    limits = [x for x in (soft, hard) if x > 0]
    need(limits, 'Actual finite positive account quota required')
    return max(0, min(limits) - used) * 1024


class RuntimeGuard:
    def __init__(self, plan, stop):
        self.plan, self.stop = plan, stop
        self.done = threading.Event()
        self.reason = None
        self.samples, self.peak_output = 0, 0
        self.sample()
        self.check()
        self.thread = threading.Thread(target=self.observe, daemon=True)
        self.thread.start()

    def sample(self):
        p = self.plan
        used = allocated_bytes(p['output_directory'])
        self.peak_output = max(self.peak_output, used)
        need(used < p['output_cap_bytes'], 'Actual output allowance reached')
        if 'quota_snapshot' in p:
            if p['quota_authority'].get('kind') == 'lustre':
                from ..completion_runtime_v1.lustre_quota import budget_check
            else:
                from ..completion_runtime_v1.quota import budget_check
            # Reuse Root's live, registered account snapshot and its immutable
            # pre-query inode credit. No second metadata publisher is required.
            budget_check(p, used, Path(p['output_directory']))
            return self.sample_memory()
        q = load(p['quota_feed_path'])
        need(q['schema'] == 'PUBCHEM_RECONSTRUCTION_QUOTA_FEED_V1' and q['status'] == 'AVAILABLE' and q['uid'] == os.getuid() == 1278 and q['username'] == 'zixiao' and q['endpoint'] == '202.38.247.57:22', 'Actual Main user quota observation required')
        need(0 <= time.time() - q['observed_unix_seconds'] <= p.get('maximum_quota_observation_age_seconds', 180), 'Current actual quota observation unavailable')
        need(q['returncode'] == 0 and hashlib.sha256(q['raw_stdout'].encode()).hexdigest() == q['raw_stdout_sha256'], 'Quota raw observation inconsistent')
        need(q['output_directory'] == p['output_directory'] and q['scientific_scope_sha256'] == p['scientific_scope_sha256'], 'Quota output credit belongs to a different exact scope')
        available = quota_available(q['raw_stdout'], p['quota_device'])
        need(available == q['available_bytes'], 'Account capacity must come from actual quota, not whole-disk df')
        credit = min(used, q['output_allocated_bytes_measured_before_quota'])
        remaining_at_quota = max(0, p['output_cap_bytes'] - credit)
        need(available - remaining_at_quota - p['other_future_reserved_bytes'] >= p['minimum_free_bytes'], 'Actual account quota minus all future outputs is insufficient')
        space = os.statvfs(p['output_directory'])
        free = space.f_bavail * space.f_frsize
        need(free - max(0, p['output_cap_bytes'] - used) - p['other_future_reserved_bytes'] >= p['minimum_free_bytes'], 'Actual filesystem capacity minus future outputs is insufficient')
        return self.sample_memory()

    def sample_memory(self):
        p = self.plan
        mem = {line.split(':')[0]: int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemAvailable:', 'MemTotal:'))}
        need(mem['MemAvailable'] >= p['minimum_node_available_bytes'], 'Actual node available memory is insufficient')
        pending, own = [os.getpid()], set()
        rss = 0
        while pending:
            pid = pending.pop()
            if pid in own:
                continue
            own.add(pid)
            try:
                rss += int(Path('/proc', str(pid), 'statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')
                pending.extend(map(int, Path('/proc', str(pid), 'task', str(pid), 'children').read_text().split()))
            except FileNotFoundError:
                continue
        need(rss < p['software_rss_budget_bytes'], 'Actual own process-tree RSS exceeds reviewed working budget')
        self.samples += 1

    def observe(self):
        while not self.done.wait(5):
            try:
                self.sample()
            except BaseException as exc:
                self.reason = repr(exc)
                self.stop.set()
                return

    def check(self):
        if self.stop.is_set():
            raise CooperativeStop(self.reason or 'Root resource/source interruption')

    def close(self):
        self.done.set()
        self.thread.join()

    def receipt(self):
        return {'samples': self.samples, 'peak_output_allocated_bytes': self.peak_output, 'resource_stop_reason': self.reason, 'arbitrary_wall_or_retry_limit': False, 'chemical_state_changed_by_resource_stop': False}
