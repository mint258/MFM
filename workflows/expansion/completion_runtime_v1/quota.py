"""Fresh account quota evidence for long, restartable expansion jobs.

The publisher is metadata-only. It runs on the login node, and publishes the
actual quota command output, not the whole filesystem's free space. Consumers
independently parse the original quota text and also check their own filesystem.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import subprocess
import tempfile
import time

SCHEMA = 'PUBCHEM_EXPANSION_QUOTA_SNAPSHOT_V1'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def parse_quota(raw, filesystem):
    """Parse exactly one selected quota device; soft limit zero means unlimited."""
    rows = []
    lines = raw.splitlines()
    for index, line in enumerate(lines):
        parts = line.split()
        if not parts or parts[0] != filesystem:
            continue
        if len(parts) == 1 and index + 1 < len(lines):
            parts += lines[index + 1].split()
        require(len(parts) >= 4, 'Truncated real quota record')
        fields = [part.rstrip('*') for part in parts[1:4]]
        require(all(part.isdecimal() for part in fields), 'Noninteger quota blocks')
        used, soft, hard = map(int, fields)
        limits = [number for number in (soft, hard) if number > 0]
        require(limits, 'Unknown or unlimited account allowance cannot prove free quota')
        rows.append((used * 1024, min(limits) * 1024))
    require(len(rows) == 1, 'Exactly one selected account quota filesystem required')
    return rows[0]


def publisher_identity():
    fields = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
    source = Path(__file__).resolve()
    return dict(pid=os.getpid(), uid=os.getuid(), start_ticks=fields[19],
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                hostname=socket.gethostname(), source_path=str(source),
                source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())


def capture(filesystem, endpoint, identity):
    user = pwd.getpwuid(os.getuid()).pw_name
    command = ['quota', '-v', '-u', user]
    query_started = time.time()
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    require(result.returncode == 0, 'Actual quota command failed: ' + result.stderr.strip())
    used, limit = parse_quota(result.stdout, filesystem)
    return dict(schema=SCHEMA, endpoint=endpoint, uid=os.getuid(), username=user,
                generated_unix_seconds=time.time(), filesystem=filesystem,
                quota_query_started_unix_seconds=query_started,
                used_bytes=used, hard_limit_bytes=limit,
                raw_quota_output=result.stdout,
                raw_quota_sha256=hashlib.sha256(result.stdout.encode()).hexdigest(),
                actual_quota_command=command, quota_returncode=0,
                publisher=identity, status='ACTUAL_FRESH_ACCOUNT_QUOTA')


def atomic_snapshot(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + '.writing.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate_snapshot(snapshot, expected, now=None):
    now = time.time() if now is None else now
    require(snapshot['schema'] == SCHEMA and snapshot['status'] == 'ACTUAL_FRESH_ACCOUNT_QUOTA',
            'Fresh real account quota evidence required')
    require(snapshot['endpoint'] == expected['endpoint'] and snapshot['uid'] == expected['uid']
            and snapshot['filesystem'] == expected['filesystem'], 'Quota account/device mismatch')
    require(0 <= now - snapshot['generated_unix_seconds'] <= expected.get('maximum_age_seconds', 120),
            'Quota evidence stale or from the future')
    if 'quota_query_started_unix_seconds' in snapshot:
        require(snapshot['quota_query_started_unix_seconds'] <= snapshot['generated_unix_seconds'],
                'Quota query start cannot be after its actual observation')
    require(snapshot['quota_returncode'] == 0 and
            snapshot['actual_quota_command'] == ['quota', '-v', '-u', snapshot['username']],
            'Actual quota command provenance required')
    raw = snapshot['raw_quota_output']
    owner = re.search(r'Disk quotas for user (\S+) \(uid (\d+)\):', raw)
    require(owner is not None and owner.group(1) == snapshot['username'] and
            int(owner.group(2)) == expected['uid'], 'Raw quota user/UID mismatch')
    require(hashlib.sha256(raw.encode()).hexdigest() == snapshot['raw_quota_sha256'],
            'Raw account quota evidence changed')
    used, limit = parse_quota(raw, snapshot['filesystem'])
    require((used, limit) == (snapshot['used_bytes'], snapshot['hard_limit_bytes']),
            'Published quota numbers differ from actual raw output')
    if 'publisher' in expected:
        require(snapshot['publisher'] == expected['publisher'], 'Registered publisher identity changed')
    return dict(used_bytes=used, hard_limit_bytes=limit, free_account_bytes=limit - used)


def observed_old_own_blocks(output_directory, cutoff):
    """Only unchanged owned inodes older than the quota query can earn credit.

    New writes after that query are absent from its account total. Crediting
    those bytes against the still-future cap would under-reserve storage.
    """
    if cutoff is None:
        return 0
    seen, credit = set(), 0
    cutoff_ns = int(cutoff * 1_000_000_000)
    for directory, subdirs, files in os.walk(output_directory, followlinks=False):
        for name in ['.', *subdirs, *files]:
            path = Path(directory) if name == '.' else Path(directory) / name
            try:
                before = path.lstat()
            except FileNotFoundError:
                # An atomic producer rename cannot earn any account credit;
                # it is not evidence of corrupt data or a reason to stop work.
                continue
            require(not stat.S_ISLNK(before.st_mode) and before.st_uid == os.getuid(),
                    'Output quota credit must stay within own regular tree')
            require(stat.S_ISDIR(before.st_mode) or stat.S_ISREG(before.st_mode),
                    'Unexpected output inode type')
            key = (before.st_dev, before.st_ino)
            if key in seen:
                continue
            seen.add(key)
            if max(before.st_mtime_ns, before.st_ctime_ns) > cutoff_ns:
                continue
            try:
                after = path.lstat()
            except FileNotFoundError:
                continue
            if (before.st_dev, before.st_ino, before.st_blocks, before.st_mtime_ns,
                before.st_ctime_ns, before.st_size) != (
                after.st_dev, after.st_ino, after.st_blocks, after.st_mtime_ns,
                after.st_ctime_ns, after.st_size):
                continue
            credit += before.st_blocks * 512
    return credit


def budget_check(plan, own_output_bytes, output_directory, prequery_credit_provider=None):
    path = Path(plan['quota_snapshot'])
    require(path.is_file() and path.stat().st_uid == os.getuid(), 'Own real quota snapshot required')
    snapshot = json.loads(path.read_text())
    account = validate_snapshot(snapshot, plan['quota_authority'])
    require(type(own_output_bytes) is int and 0 <= own_output_bytes <= plan['output_cap_bytes'],
            'Finite actual own-output usage within declared allowance required')
    cutoff = snapshot.get('quota_query_started_unix_seconds')
    if prequery_credit_provider is None:
        old_blocks = observed_old_own_blocks(output_directory, cutoff)
    else:
        # Large generation parents keep an immutable closed-file ledger when
        # they publish each batch. Do not walk millions of outputs every poll.
        require(callable(prequery_credit_provider), 'Internal closed-output credit provider required')
        old_blocks = 0 if cutoff is None else prequery_credit_provider(cutoff)
        require(type(old_blocks) is int and old_blocks >= 0, 'Nonnegative exact old owned block credit required')
    account_credit = min(own_output_bytes, old_blocks)
    account_remaining = plan['output_cap_bytes'] - account_credit
    remaining = plan['output_cap_bytes'] - own_output_bytes
    require(account['free_account_bytes'] - account_remaining -
            plan['other_future_reserved_bytes'] >= plan['minimum_free_bytes'],
            'Actual account quota minus all future output is insufficient')
    space = os.statvfs(output_directory)
    free = space.f_bavail * space.f_frsize
    require(free - remaining - plan['other_future_reserved_bytes'] >= plan['minimum_free_bytes'],
            'Actual physical free space minus all future output is insufficient')
    return dict(**account, free_filesystem_bytes=free,
                own_remaining_output_reserved_bytes=remaining,
                account_credited_own_pre_query_blocks_bytes=account_credit,
                account_remaining_output_reserved_bytes=account_remaining,
                other_future_reserved_bytes=plan['other_future_reserved_bytes'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--filesystem', default='/dev/sda1')
    parser.add_argument('--endpoint', default='202.38.247.57:22')
    parser.add_argument('--interval', type=float, default=30)
    parser.add_argument('--stop-file', required=True, type=Path)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    require(socket.gethostname() == 'sonmi' and os.getuid() == 1278,
            'This quota producer is Main login metadata only')
    require(args.interval >= 10, 'Avoid excessive login metadata polling')
    identity = publisher_identity()
    while not args.stop_file.exists():
        # If a capture fails, keep the old snapshot stale; never publish empty success.
        try:
            atomic_snapshot(args.snapshot, capture(args.filesystem, args.endpoint, identity))
        except Exception as error:
            print(type(error).__name__ + ': ' + str(error), flush=True)
            if args.once:
                raise
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
