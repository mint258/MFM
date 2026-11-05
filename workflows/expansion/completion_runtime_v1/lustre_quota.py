"""Actual Lustre user quota snapshots; never substitute filesystem free space."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import socket
import subprocess
import time

from .quota import atomic_snapshot, observed_old_own_blocks, require

SCHEMA = 'PUBCHEM_EXPANSION_LUSTRE_QUOTA_SNAPSHOT_V1'


def parse_quota(raw, filesystem, username, uid):
    owner = re.search(r'^Disk quotas for usr (\S+) \(uid (\d+)\):$', raw, re.M)
    require(owner is not None and owner.group(1) == username and
            int(owner.group(2)) == uid, 'Actual Lustre quota owner mismatch')
    lines = raw.splitlines()
    rows = []
    for index, line in enumerate(lines):
        fields = line.split()
        if not fields or fields[0] != filesystem:
            continue
        if len(fields) == 1 and index + 1 < len(lines):
            fields += lines[index + 1].split()
        require(len(fields) >= 4, 'Truncated Lustre user block quota')
        numbers = [value.rstrip('*') for value in fields[1:4]]
        require(all(value.isdecimal() for value in numbers), 'Noninteger Lustre quota')
        used, soft, hard = map(int, numbers)
        require(hard > 0, 'Positive actual user hard limit required')
        # A positive soft limit remains the conservative allowance.
        limit = min(soft, hard) if soft > 0 else hard
        rows.append((used * 1024, limit * 1024))
    require(len(rows) == 1, 'Exactly one selected Lustre user quota row required')
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
    command = ['lfs', 'quota', '-u', user, filesystem]
    started = time.time()
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    require(result.returncode == 0, 'Actual Lustre quota failed: ' + result.stderr.strip())
    used, limit = parse_quota(result.stdout, filesystem, user, os.getuid())
    return dict(schema=SCHEMA, kind='lustre', endpoint=endpoint, uid=os.getuid(),
                username=user, filesystem=filesystem, generated_unix_seconds=time.time(),
                quota_query_started_unix_seconds=started, used_bytes=used,
                hard_limit_bytes=limit, raw_quota_output=result.stdout,
                raw_quota_sha256=hashlib.sha256(result.stdout.encode()).hexdigest(),
                actual_quota_command=command, quota_returncode=0, publisher=identity,
                status='ACTUAL_FRESH_ACCOUNT_QUOTA')


def validate_snapshot(snapshot, expected, now=None):
    now = time.time() if now is None else now
    require(expected['kind'] == 'lustre' and snapshot['schema'] == SCHEMA and
            snapshot['kind'] == 'lustre' and snapshot['status'] == 'ACTUAL_FRESH_ACCOUNT_QUOTA',
            'Separate actual Lustre quota authority required')
    require(snapshot['endpoint'] == expected['endpoint'] and snapshot['uid'] == expected['uid']
            and snapshot['filesystem'] == expected['filesystem'], 'Lustre account/device mismatch')
    require(0 <= now - snapshot['generated_unix_seconds'] <= expected.get('maximum_age_seconds', 120),
            'Lustre quota evidence stale or future')
    require(snapshot['quota_query_started_unix_seconds'] <= snapshot['generated_unix_seconds'],
            'Quota query cannot start after observation')
    require(snapshot['quota_returncode'] == 0 and snapshot['actual_quota_command'] ==
            ['lfs', 'quota', '-u', snapshot['username'], snapshot['filesystem']],
            'Actual Lustre command provenance required')
    raw = snapshot['raw_quota_output']
    require(hashlib.sha256(raw.encode()).hexdigest() == snapshot['raw_quota_sha256'],
            'Raw Lustre evidence changed')
    used, limit = parse_quota(raw, snapshot['filesystem'], snapshot['username'], expected['uid'])
    require((used, limit) == (snapshot['used_bytes'], snapshot['hard_limit_bytes']),
            'Published quota differs from raw Lustre output')
    if 'publisher' in expected:
        require(snapshot['publisher'] == expected['publisher'], 'Lustre publisher changed')
    return dict(used_bytes=used, hard_limit_bytes=limit, free_account_bytes=limit-used)


def budget_check(plan, own_output_bytes, output_directory, prequery_credit_provider=None):
    snapshot_path = Path(plan['quota_snapshot'])
    require(snapshot_path.is_file() and snapshot_path.stat().st_uid == os.getuid(),
            'Own Lustre quota snapshot required')
    snapshot = json.loads(snapshot_path.read_text())
    account = validate_snapshot(snapshot, plan['quota_authority'])
    output = Path(output_directory).resolve(strict=True)
    root = Path(plan['quota_authority']['filesystem']).resolve(strict=True)
    require(output.is_relative_to(root) and output.stat().st_dev == root.stat().st_dev,
            'Output must remain on the quota-authorized Lustre filesystem')
    require(type(own_output_bytes) is int and 0 <= own_output_bytes <= plan['output_cap_bytes'],
            'Finite own output within declared cap required')
    cutoff = snapshot['quota_query_started_unix_seconds']
    if prequery_credit_provider is None:
        old_blocks = observed_old_own_blocks(output, cutoff)
    else:
        require(callable(prequery_credit_provider), 'Internal credit provider required')
        old_blocks = prequery_credit_provider(cutoff)
    require(type(old_blocks) is int and old_blocks >= 0, 'Nonnegative old owned blocks required')
    account_credit = min(own_output_bytes, old_blocks)
    remaining = plan['output_cap_bytes'] - own_output_bytes
    account_remaining = plan['output_cap_bytes'] - account_credit
    reserved = plan['other_future_reserved_bytes']
    minimum = plan['minimum_free_bytes']
    require(type(reserved) is int and reserved >= 0 and type(minimum) is int and minimum >= 0,
            'Explicit nonnegative future reservations and free floor required')
    require(account['free_account_bytes'] - account_remaining - reserved >= minimum,
            'Actual Lustre user quota minus future output insufficient')
    space = os.statvfs(output)
    free = space.f_bavail * space.f_frsize
    require(free - remaining - reserved >= minimum,
            'Actual Lustre physical free space minus future output insufficient')
    return dict(**account, free_filesystem_bytes=free,
                own_remaining_output_reserved_bytes=remaining,
                account_credited_own_pre_query_blocks_bytes=account_credit,
                account_remaining_output_reserved_bytes=account_remaining,
                other_future_reserved_bytes=reserved)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--filesystem', default='/lfshome/zixiao')
    parser.add_argument('--endpoint', default='202.38.247.57:22')
    parser.add_argument('--interval', type=float, default=30)
    parser.add_argument('--stop-file', required=True, type=Path)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    require(socket.gethostname() == 'sonmi' and os.getuid() == 1278,
            'This producer captures Main login metadata only')
    require(args.interval >= 10, 'Avoid excessive login metadata queries')
    identity = publisher_identity()
    while not args.stop_file.exists():
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
