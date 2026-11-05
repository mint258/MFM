"""One real quota backend for all Alpha goal components; no Main imports."""
import argparse
import hashlib
import os
from pathlib import Path
import time
import sys
import socket
from .common import ENDPOINT, UID, KIND, allocated_bytes, load, need, write
from .probe import observe, identity, parse_volume


def validate_snapshot(snapshot, authority, now=None):
    now = time.time() if now is None else now
    q = snapshot
    need(authority['kind'] == q['kind'] == KIND and authority['endpoint'] == q['endpoint'] == ENDPOINT and authority['uid'] == q['uid'] == UID, 'Exact real Alpha quota identity required')
    need(q['schema'] == 'ALPHA_GLUSTER_DIRECTORY_QUOTA_SNAPSHOT_V1' and q['status'] == 'ACTUAL_NATIVE_DIRECTORY_QUOTA_DEEM_STATFS', 'Actual native directory quota snapshot required')
    need(q['publisher'] == authority['publisher'] and q['publisher']['uid'] == UID, 'Registered actual quota publisher identity changed')
    age = now - q['generated_unix_seconds']
    need(0 <= age <= authority['maximum_age_seconds'] and q['quota_query_started_unix_seconds'] <= q['generated_unix_seconds'], 'Native quota observation is stale or from future: age_seconds=' + repr(age) + ' now=' + repr(now) + ' generated=' + repr(q['generated_unix_seconds']) + ' maximum_age=' + repr(authority['maximum_age_seconds']) + ' hostname=' + socket.gethostname())
    raw = q['native_volume_info']
    need(raw['returncode'] == 0 and hashlib.sha256(raw['stdout'].encode()).hexdigest() == raw['stdout_sha256'], 'Native Gluster output SHA differs')
    parsed = parse_volume(raw['stdout'])
    need(parsed == q['parsed_volume'] and parsed['Volume Name'] == 'gv1' and parsed['Volume ID'] == authority['volume_id'], 'Native configured volume/quota identity differs')
    mount = q['mount_observation']
    need(mount['returncode'] == 0 and hashlib.sha256(mount['stdout'].encode()).hexdigest() == mount['stdout_sha256'] and mount['stdout'].split() == [authority['volume_root'], 'fuse.glusterfs', authority['volume_source']], 'Actual Gluster mount source differs')
    root, volume = q['quota_root_statfs'], q['volume_statfs']
    need(root['path'] == authority['quota_root'] == '/gfshome/alpha' and volume['path'] == authority['volume_root'] == '/gfshome' and root['uid'] == UID and root['device'] == volume['device'], 'Exact Alpha directory boundary, not volume root, required')
    need(0 < root['total_bytes'] == q['hard_limit_bytes'] == authority['hard_limit_bytes'] < volume['total_bytes'] and 0 <= root['free_bytes'] == q['available_bytes'] <= root['total_bytes'] and q['used_bytes'] == root['total_bytes'] - root['free_bytes'], 'Actual effective directory limit/usage arithmetic differs')
    need(q['whole_filesystem_free_substituted_for_directory_quota'] is False and q['direct_quota_list_or_xattr_claimed'] is False, 'Do not mislabel the directory-native quota basis')
    return q


def budget_check(plan, own_output_bytes, output_root, prequery_credit_provider=None):
    need(os.getuid() == UID, 'Alpha quota backend cannot run as Main UID1278')
    authority = plan['quota_authority']; q = validate_snapshot(load(plan['quota_snapshot']), authority)
    root = Path(output_root).absolute(); scope = Path(plan.get('output_scope_root', root)).absolute()
    need(root == scope and root.is_relative_to(Path(authority['quota_root'])) and not root.is_symlink() and root.stat().st_uid == UID, 'Quota accounting must use the one declared aggregate output scope')
    cap = plan['output_cap_bytes']; other = plan['other_future_reserved_bytes']; floor = plan['minimum_free_bytes']
    need(all(type(x) is int and x >= 0 for x in (own_output_bytes, cap, other, floor)) and cap > 0 and own_output_bytes <= cap, 'Actual output size and all-future reservations must be valid')
    cutoff = q['quota_query_started_unix_seconds']
    measured = allocated_bytes(root, before_unix_seconds=cutoff) if prequery_credit_provider is None else prequery_credit_provider(cutoff)
    need(type(measured) is int and measured >= 0, 'Credit must be actual pre-query owned immutable blocks')
    credit = min(measured, own_output_bytes, q['used_bytes'], cap)
    remaining = cap - credit
    need(q['available_bytes'] - remaining - other >= floor, 'Actual Alpha directory quota minus all remaining outputs is insufficient')
    need(q['volume_statfs']['free_bytes'] - remaining - other >= floor, 'Actual underlying volume capacity is also insufficient; directory quota cannot replace physical capacity')
    local = os.statvfs(root); local_free = local.f_bavail * local.f_frsize
    need(local.f_blocks * local.f_frsize == q['hard_limit_bytes'], 'Output directory has a different effective quota; review its exact boundary')
    # This second native directory query is local to the actual compute node;
    # no whole-volume banner capacity can replace it.
    need(local_free - max(0, cap - own_output_bytes) - other >= floor, 'Current compute-node directory quota minus future outputs is insufficient')
    return {'quota_root': authority['quota_root'], 'hard_limit_bytes': q['hard_limit_bytes'], 'available_directory_quota_bytes': q['available_bytes'], 'own_prequery_blocks_credit_bytes': credit, 'remaining_own_reserved_bytes': remaining, 'other_future_reserved_bytes': other, 'minimum_free_bytes': floor, 'generated_unix_seconds': q['generated_unix_seconds']}


def publish(authority_path, output, interval=30):
    authority = load(authority_path); publisher = identity()
    while True:
        # Failure retains the last real snapshot; freshness then rejects it.
        try:
            value = observe(authority); value['publisher'] = publisher
            write(output, value, replace=True)
        except Exception as exc:
            print('ALPHA_NATIVE_QUOTA_OBSERVATION_UNAVAILABLE ' + repr(exc), file=sys.stderr, flush=True)
        time.sleep(interval)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--authority', required=True); p.add_argument('--output', required=True)
    p.add_argument('--publish', action='store_true'); p.add_argument('--interval', type=int, default=30)
    a = p.parse_args(); need(1 <= a.interval <= 60, 'Fresh bounded publisher cadence required')
    if a.publish:publish(a.authority, a.output, a.interval)
    else:
        q = observe(load(a.authority)); q['publisher'] = identity(); print(write(a.output, q))


if __name__ == '__main__':main()
