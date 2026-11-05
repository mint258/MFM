"""Synthetic metadata boundaries; never launch an Alpha computation."""
import hashlib
from pathlib import Path
import tempfile
import time
import unittest
from .common import ENDPOINT, KIND, allocated_bytes
from .probe import parse_volume
from .quota import validate_snapshot


def fixture():
    native = 'Volume Name: gv1\nVolume ID: fixture-volume\nStatus: Started\nfeatures.quota: on\nfeatures.inode-quota: on\nfeatures.quota-deem-statfs: on\n'
    mount = '/gfshome fuse.glusterfs sonmi1:/gv1\n'
    authority = {'kind': KIND, 'endpoint': ENDPOINT, 'uid': 1264, 'quota_root': '/gfshome/alpha', 'volume_root': '/gfshome', 'volume_source': 'sonmi1:/gv1', 'volume_id': 'fixture-volume', 'hard_limit_bytes': 2000, 'maximum_age_seconds': 120, 'publisher': {'pid': 42, 'uid': 1264, 'fixture_only': True}}
    q = {'schema': 'ALPHA_GLUSTER_DIRECTORY_QUOTA_SNAPSHOT_V1', 'status': 'ACTUAL_NATIVE_DIRECTORY_QUOTA_DEEM_STATFS', 'kind': KIND, 'endpoint': ENDPOINT, 'uid': 1264, 'quota_query_started_unix_seconds': 999, 'generated_unix_seconds': 1000, 'publisher': authority['publisher'], 'native_volume_info': {'returncode': 0, 'stdout': native, 'stdout_sha256': hashlib.sha256(native.encode()).hexdigest()}, 'parsed_volume': parse_volume(native), 'mount_observation': {'returncode': 0, 'stdout': mount, 'stdout_sha256': hashlib.sha256(mount.encode()).hexdigest()}, 'quota_root_statfs': {'path': '/gfshome/alpha', 'uid': 1264, 'device': 3, 'total_bytes': 2000, 'free_bytes': 1500}, 'volume_statfs': {'path': '/gfshome', 'device': 3, 'total_bytes': 60000, 'free_bytes': 40000}, 'hard_limit_bytes': 2000, 'available_bytes': 1500, 'used_bytes': 500, 'whole_filesystem_free_substituted_for_directory_quota': False, 'direct_quota_list_or_xattr_claimed': False}
    return authority, q


class AlphaRuntimeTests(unittest.TestCase):
    def test_native_directory_boundary_accepts_independent_volume_evidence(self):
        a, q = fixture(); self.assertIs(validate_snapshot(q, a, 1001), q)

    def test_whole_volume_capacity_cannot_replace_directory_quota(self):
        a, q = fixture(); q['quota_root_statfs']['total_bytes'] = q['volume_statfs']['total_bytes']
        with self.assertRaises(ValueError):validate_snapshot(q, a, 1001)

    def test_stale_or_future_snapshot_rejected(self):
        for when in (999, 1121):
            a, q = fixture()
            with self.assertRaises(ValueError):validate_snapshot(q, a, when)

    def test_wrong_publisher_and_main_identity_rejected(self):
        for key, value in (('uid', 1278), ('endpoint', '202.38.247.57:22'), ('publisher', {'pid': 43, 'uid': 1264})):
            a, q = fixture(); q[key] = value
            with self.assertRaises(ValueError):validate_snapshot(q, a, 1001)

    def test_native_config_and_raw_evidence_must_agree(self):
        a, q = fixture(); q['native_volume_info']['stdout'] = q['native_volume_info']['stdout'].replace('features.quota: on', 'features.quota: off')
        with self.assertRaises(ValueError):validate_snapshot(q, a, 1001)
        q['native_volume_info']['stdout_sha256'] = hashlib.sha256(q['native_volume_info']['stdout'].encode()).hexdigest()
        with self.assertRaises(ValueError):validate_snapshot(q, a, 1001)

    def test_changed_mount_or_arithmetic_rejected(self):
        a, q = fixture(); q['used_bytes'] += 1
        with self.assertRaises(ValueError):validate_snapshot(q, a, 1001)
        a, q = fixture(); q['mount_observation']['stdout'] = '/share xfs /dev/sdb\n'
        q['mount_observation']['stdout_sha256'] = hashlib.sha256(q['mount_observation']['stdout'].encode()).hexdigest()
        with self.assertRaises(ValueError):validate_snapshot(q, a, 1001)

    def test_only_prequery_unchanged_own_blocks_earn_credit(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); p = root / 'small_metadata'; p.write_bytes(b'x' * 8192)
            cutoff = time.time() + .001
            self.assertGreaterEqual(allocated_bytes(root, before_unix_seconds=cutoff), p.stat().st_blocks * 512)
            self.assertEqual(allocated_bytes(root, before_unix_seconds=0), 0)

    def test_symlink_scope_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); p = root / 'actual'; p.write_text('metadata')
            (root / 'linked').symlink_to(p)
            with self.assertRaises(ValueError):allocated_bytes(root)


if __name__ == '__main__':unittest.main()
