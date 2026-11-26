"""New logic only: registry sums, expiry, own-file exclusion, reserves, timeout path."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shared_guard as g

GIB = g.GIB


class SharedGuardTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        quota = patch.object(g, 'uid_quota_status', return_value=dict(available=10**15, source='test fixture', uid=os.getuid(), observed_time=0))
        quota.start(); self.addCleanup(quota.stop)

    def disk(self, available, total=100 * GIB, inodes=10**6):
        return dict(total=total, available=available, inodes=inodes, total_inodes=10**7)

    def test_peers_on_same_node_and_path_are_summed_own_file_excluded(self):
        g.claim("d", [dict(id="a", kind="node_disk", node="n7", path="/", bytes=16 * GIB),
                      dict(id="b", kind="node_disk", node="n8", path="/", bytes=99 * GIB)],
                registry=self.dir, now=0)
        g.claim("p", [dict(id="c", kind="node_disk", node="n7", path="/", bytes=50 * GIB)],
                registry=self.dir, now=0)
        self.assertEqual(g.others("p", "node_disk", "n7", "/", self.dir, now=1), 16 * GIB)
        # reserve 10 GiB + own 1 GiB + peer 16 GiB = 27 GiB
        with self.assertRaises(g.AdmissionRefused):
            g.check("p", "node_disk", GIB, "/", "n7", registry=self.dir,
                    status=self.disk(26 * GIB), now=1)
        r = g.check("p", "node_disk", GIB, "/", "n7", registry=self.dir,
                    status=self.disk(28 * GIB), now=1)
        self.assertEqual(r["peers"], 16 * GIB)

    def test_unregistered_node_counts_zero_and_expired_claims_are_ignored(self):
        g.claim("d", [dict(id="a", kind="node_disk", node="n7", path="/", bytes=16 * GIB)],
                ttl=10, registry=self.dir, now=0)
        self.assertEqual(g.others("p", "node_disk", "n9", "/", self.dir, now=1), 0)
        self.assertEqual(g.others("p", "node_disk", "n7", "/", self.dir, now=11), 0)

    def test_release_clears_and_unreadable_file_refuses(self):
        g.claim("d", [dict(id="a", kind="shared_fs", path="/share", bytes=GIB)],
                registry=self.dir, now=0)
        g.release("d", registry=self.dir, now=1)
        self.assertEqual(g.others("p", "shared_fs", None, "/share", self.dir, now=2), 0)
        (self.dir / "x.json").write_text("{broken")
        with self.assertRaises(g.AdmissionRefused):
            g.others("p", "shared_fs", None, "/share", self.dir, now=2)

    def test_shared_reserve_quota_and_ram_reserve(self):
        st = self.disk(g.SHARED_RESERVE + 2 * GIB, total=10**15)
        g.check("p", "shared_fs", GIB, "/share", registry=self.dir, status=st, now=0)
        with self.assertRaises(g.AdmissionRefused):
            g.check("p", "shared_fs", GIB, "/share", registry=self.dir, status=st,
                    quota_available=g.SHARED_RESERVE, now=0)
        ram = dict(total=256 * GIB, available=40 * GIB)
        g.claim("s", [dict(id="r", kind="node_ram", node="n7", bytes=10 * GIB)],
                registry=self.dir, now=0)
        # reserve 25.6 GiB + own 5 GiB + peer 10 GiB = 40.6 GiB > 40 GiB
        with self.assertRaises(g.AdmissionRefused):
            g.check("p", "node_ram", 5 * GIB, node="n7", registry=self.dir, status=ram, now=0)

    def test_tmp_on_root_device_shares_capacity_and_paths_are_canonical(self):
        node = g.node_name()
        g.claim("d", [dict(id="t", kind="node_disk", node=node, path="/tmp", bytes=7 * GIB)],
                registry=self.dir, now=0)
        same = os.stat("/tmp").st_dev == os.stat("/").st_dev
        r = g.check("p", "node_disk", 0, "/", registry=self.dir, status=self.disk(90 * GIB), now=0)
        self.assertEqual(r["peers"], 7 * GIB if same else 0)
        with self.assertRaises(ValueError):
            g.claim("p", [dict(id="a", kind="shared_fs", path="/share/home/x", bytes=1)],
                    registry=self.dir)

    def test_bad_reservations_rejected(self):
        with self.assertRaises(ValueError):
            g.claim("p", [dict(id="a", kind="node_disk", path="/", bytes=1)], registry=self.dir)
        with self.assertRaises(ValueError):
            g.claim("p", [dict(id="a", kind="shared_fs", path="/share", bytes=-1)],
                    registry=self.dir)

    def test_subprocess_check_and_timeout_refusal(self):
        os.environ["MFM_RESERVATION_DIR"] = str(self.dir)
        try:
            r = g.check_with_timeout("p", "node_disk", 0, path="/tmp",
                                     node="localtest", new_inodes=0)
            self.assertEqual(r["own"], 0)
            with self.assertRaises(g.AdmissionRefused):
                g.check_with_timeout("p", "node_disk", 0, path="/", timeout=0.0001)
        finally:
            del os.environ["MFM_RESERVATION_DIR"]


class AutofsTargetTests(unittest.TestCase):
    def test_share_probe_uses_existing_project_directory_not_autofs_root(self):
        from unittest.mock import patch
        with patch.object(g, '__file__', '/share/home/zixiao/descriptor_analysis/MFM_s_recipe/tools/shared_guard.py'):
            self.assertEqual(g.disk_probe_target('/share'),
                '/share/home/zixiao/descriptor_analysis/MFM_s_recipe/tools')
            self.assertEqual(g.disk_probe_target('/'), '/')
            self.assertEqual(g.disk_probe_target('/tmp'), '/tmp')

    @patch.object(g, 'uid_quota_status', return_value=dict(available=10**15, source='test fixture', uid=os.getuid(), observed_time=0))
    def test_share_key_stays_canonical_for_peer_accounting(self, quota):
        with tempfile.TemporaryDirectory() as registry:
            g.claim('peer', [dict(id='write', kind='shared_fs', path='/share', bytes=7*GIB)],
                    registry=Path(registry), now=0)
            status=dict(total=1000*GIB, available=500*GIB, inodes=100000,
                        total_inodes=1000000, probe_target='/share/home/x/project')
            result=g.check('s', 'shared_fs', GIB, path='/share',
                           registry=Path(registry), status=status, now=0)
            self.assertEqual(result['peers'], 7*GIB)
            self.assertEqual(result['path'], '/share')
            self.assertEqual(result['probe_target'], '/share/home/x/project')


if __name__ == "__main__":
    unittest.main()
