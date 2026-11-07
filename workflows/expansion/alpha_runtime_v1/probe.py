"""Read native Gluster volume configuration and scoped directory statfs."""
import hashlib
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import time
from .common import ENDPOINT, UID, KIND, need, reference


def command(args):
    began = time.time()
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=20)
    return {'argv': args, 'query_started_unix_seconds': began, 'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr, 'stdout_sha256': hashlib.sha256(p.stdout.encode()).hexdigest()}


def parse_volume(raw):
    def field(name):
        matches = re.findall(r'^' + re.escape(name) + r':\s*(\S+)\s*$', raw, re.MULTILINE)
        need(len(matches) == 1, 'One actual native Gluster field required: ' + name)
        return matches[0]
    value = {key: field(key) for key in ('Volume Name', 'Volume ID', 'Status', 'features.quota', 'features.inode-quota', 'features.quota-deem-statfs')}
    need(value['Status'] == 'Started' and all(value[k] == 'on' for k in ('features.quota', 'features.inode-quota', 'features.quota-deem-statfs')), 'Native quota/inode-quota/deem-statfs must all be enabled')
    return value


def directory(path):
    p = Path(path); s = p.lstat()
    need(stat.S_ISDIR(s.st_mode), 'Literal regular quota directory required')
    v = os.statvfs(p)
    return {'path': str(p), 'uid': s.st_uid, 'device': s.st_dev, 'inode': s.st_ino, 'frsize': v.f_frsize, 'total_bytes': v.f_blocks * v.f_frsize, 'free_bytes': v.f_bavail * v.f_frsize, 'bfree_bytes': v.f_bfree * v.f_frsize}


def observe(authority):
    need(os.getuid() == UID and authority['endpoint'] == ENDPOINT and authority['uid'] == UID and authority['kind'] == KIND, 'Actual Alpha identity is required, never Main UID1278')
    root, volume = Path(authority['quota_root']), Path(authority['volume_root'])
    need(root == Path('/gfshome/alpha') and volume == root.parent, 'Exact Alpha directory-quota boundary required')
    started = time.time()
    info = command(['gluster', '--remote-host=sonmi1', '--log-file=/dev/null', 'volume', 'info', 'gv1'])
    need(info['returncode'] == 0, 'Native Gluster volume evidence unavailable')
    parsed = parse_volume(info['stdout'])
    need(parsed['Volume Name'] == 'gv1' and parsed['Volume ID'] == authority['volume_id'], 'Actual quota volume identity differs')
    mount = command(['findmnt', '-n', '-T', str(root), '-t', 'fuse.glusterfs', '-o', 'TARGET,FSTYPE,SOURCE'])
    need(mount['returncode'] == 0 and mount['stdout'].split() == [str(volume), 'fuse.glusterfs', authority['volume_source']], 'Exact real Gluster mount differs')
    parent, scoped = directory(volume), directory(root)
    need(scoped['uid'] == UID and scoped['device'] == parent['device'] and 0 < scoped['total_bytes'] < parent['total_bytes'] and 0 <= scoped['free_bytes'] <= scoped['total_bytes'], 'Native quota-deemed directory capacity must be distinct from the whole volume')
    need(scoped['total_bytes'] == authority['hard_limit_bytes'], 'Actual directory hard limit changed; Root must review new authority')
    return {'schema': 'ALPHA_GLUSTER_DIRECTORY_QUOTA_SNAPSHOT_V1', 'status': 'ACTUAL_NATIVE_DIRECTORY_QUOTA_DEEM_STATFS', 'kind': KIND, 'endpoint': ENDPOINT, 'uid': UID, 'quota_query_started_unix_seconds': started, 'generated_unix_seconds': time.time(), 'native_volume_info': info, 'parsed_volume': parsed, 'mount_observation': mount, 'volume_statfs': parent, 'quota_root_statfs': scoped, 'hard_limit_bytes': scoped['total_bytes'], 'used_bytes': scoped['total_bytes'] - scoped['free_bytes'], 'available_bytes': scoped['free_bytes'], 'direct_quota_list_or_xattr_claimed': False, 'whole_filesystem_free_substituted_for_directory_quota': False}


def identity():
    raw = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
    return {'pid': os.getpid(), 'uid': os.getuid(), 'hostname': socket.gethostname(), 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'start_ticks': raw[19], 'source_path': str(Path(__file__).resolve()), 'source_sha256': reference(__file__)['sha256']}
